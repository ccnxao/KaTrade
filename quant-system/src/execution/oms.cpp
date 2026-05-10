#include "qt/oms.hpp"

#include <algorithm>
#include <chrono>
#include <sstream>

namespace qt {

OrderManagementSystem::OrderManagementSystem(
    std::unique_ptr<IBrokerGateway> broker_gateway)
    : broker_gateway_(std::move(broker_gateway)) {}

// GAP-020: 集中订单状态转换，验证合法性
bool OrderManagementSystem::transition_order(OrderRecord& order, OrderStatus to) {
    OrderStatus from = order.status;

    // 合法转换表:
    // Created -> Submitted (正常)
    // Submitted -> Acknowledged, PartiallyFilled, Filled, Cancelled, Rejected
    // PartiallyFilled -> PartiallyFilled, Filled, Cancelled
    // 终态 (Filled, Cancelled, Rejected) 不可再转换
    if (from == OrderStatus::Filled || from == OrderStatus::Cancelled ||
        from == OrderStatus::Rejected) {
        return false;
    }
    order.status = to;
    if (to == OrderStatus::Cancelled || to == OrderStatus::Rejected) {
        order.remaining_qty = 0.0;
    }
    return true;
}

std::vector<OmsOrderRecord> OrderManagementSystem::submit_orders(
    std::span<const OrderIntent> orders) {
    if (!broker_gateway_) return {};
    std::vector<OmsOrderRecord> submitted;
    submitted.reserve(orders.size());

    auto now_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();

    for (const auto& order : orders) {
        const auto order_id = broker_gateway_->submit(order);
        OrderRecord record{
            order_id, order, OrderStatus::Created, 0.0, order.quantity, 0.0, 0.0,
        };
        transition_order(record, OrderStatus::Submitted);
        order_history_.push_back(record);
        submission_times_[order_id] = now_ms;  // R06: 记录提交时间
        submitted.push_back(record);
    }

    return submitted;
}

void OrderManagementSystem::cancel_open_orders() {
    if (!broker_gateway_) return;
    broker_gateway_->cancel_open_orders();
    for (auto& order : order_history_) {
        if (order.status == OrderStatus::Submitted ||
            order.status == OrderStatus::PartiallyFilled) {
            transition_order(order, OrderStatus::Cancelled);
        }
    }
}

void OrderManagementSystem::on_market_snapshot(std::span<const Bar> bars) {
    if (!broker_gateway_) return;
    broker_gateway_->on_market_snapshot(bars);
}

void OrderManagementSystem::expire_stale_orders(int ttl_seconds) {
    if (ttl_seconds <= 0) return;  // 非正 TTL 不启用过期

    auto now_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    int64_t cutoff_ms = now_ms - static_cast<int64_t>(ttl_seconds) * 1000;

    for (auto& order : order_history_) {
        if (order.status != OrderStatus::Submitted &&
            order.status != OrderStatus::PartiallyFilled) {
            continue;
        }
        auto it = submission_times_.find(order.order_id);
        if (it != submission_times_.end() && it->second < cutoff_ms) {
            transition_order(order, OrderStatus::Cancelled);
            if (broker_gateway_) broker_gateway_->cancel_open_orders();
        }
    }
}

std::vector<ExecutionReport> OrderManagementSystem::collect_reports() {
    auto reports = broker_gateway_->flush_reports();
    for (const auto& report : reports) {
        if (auto* order = find_order(report.order_id)) {
            order->filled_qty = report.cumulative_filled_qty;
            const bool terminal_without_open_qty =
                report.status == OrderStatus::Cancelled ||
                report.status == OrderStatus::Rejected;
            order->remaining_qty = terminal_without_open_qty ? 0.0 : report.remaining_qty;
            order->avg_price = report.avg_price;
            order->commission += report.commission;
            OrderStatus new_status = report.status;
            if (report.status != OrderStatus::Cancelled &&
                report.status != OrderStatus::Rejected) {
                new_status = (report.remaining_qty < 1e-10)
                    ? OrderStatus::Filled : OrderStatus::PartiallyFilled;
            }
            transition_order(*order, new_status);
        }
    }
    return reports;
}

const std::vector<OrderRecord>& OrderManagementSystem::order_history() const noexcept {
    return order_history_;
}

OrderRecord* OrderManagementSystem::find_order(const std::string& order_id) {
    for (auto& order : order_history_) {
        if (order.order_id == order_id) {
            return &order;
        }
    }
    return nullptr;
}

void OrderManagementSystem::apply_fills(const std::vector<ExecutionReport>& reports,
                                         std::function<void(const ExecutionReport&)> on_fill) {
    for (const auto& report : reports) {
        if (auto* order = find_order(report.order_id)) {
            order->filled_qty = report.cumulative_filled_qty;
            order->remaining_qty = report.remaining_qty;
            order->avg_price = report.avg_price;
            order->commission += report.commission;
            // GAP-020: 状态机: 部分成交 / 完全成交 / 拒绝
            OrderStatus to = OrderStatus::PartiallyFilled;
            if (report.remaining_qty < 1e-10) to = OrderStatus::Filled;
            if (report.status == OrderStatus::Rejected) to = OrderStatus::Rejected;
            transition_order(*order, to);
        }
        if (on_fill) on_fill(report);
    }
}

}  // namespace qt
