#include "qt/oms.hpp"

namespace qt {

OrderManagementSystem::OrderManagementSystem(
    std::unique_ptr<IBrokerGateway> broker_gateway)
    : broker_gateway_(std::move(broker_gateway)) {}

std::vector<OrderRecord> OrderManagementSystem::submit_orders(
    std::span<const OrderIntent> orders) {
    std::vector<OrderRecord> submitted;
    submitted.reserve(orders.size());

    for (const auto& order : orders) {
        const auto order_id = broker_gateway_->submit(order);
        OrderRecord record{
            order_id,
            order,
            OrderStatus::Submitted,
            0.0,
            order.quantity,
            0.0,
            0.0,
        };
        order_history_.push_back(record);
        submitted.push_back(record);
    }

    return submitted;
}

void OrderManagementSystem::cancel_open_orders() {
    broker_gateway_->cancel_open_orders();
}

void OrderManagementSystem::on_market_snapshot(std::span<const Bar> bars) {
    broker_gateway_->on_market_snapshot(bars);
}

std::vector<ExecutionReport> OrderManagementSystem::collect_reports() {
    auto reports = broker_gateway_->flush_reports();
    for (const auto& report : reports) {
        if (auto* order = find_order(report.order_id)) {
            order->filled_qty = report.cumulative_filled_qty;
            order->remaining_qty = report.remaining_qty;
            order->avg_price = report.avg_price;
            order->commission += report.commission;
            order->status = report.status;
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

}  // namespace qt
