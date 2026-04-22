#include "qt/execution.hpp"

#include <algorithm>
#include <cmath>

namespace qt {

NaiveExecutionAlgo::NaiveExecutionAlgo(double min_rebalance_delta)
    : min_rebalance_delta_(min_rebalance_delta) {}

std::vector<OrderIntent> NaiveExecutionAlgo::plan(const RiskDecision& decision,
                                                  const PortfolioSnapshot& current,
                                                  const PriceMap& prices,
                                                  double account_equity) {
    std::vector<OrderIntent> orders;
    if (decision.action == RiskAction::Reject || decision.action == RiskAction::Halt) {
        return orders;
    }

    for (const auto& target : decision.adjusted_portfolio.positions) {
        const double current_weight = find_weight(current, target.instrument).value_or(0.0);
        const double delta = target.target_weight - current_weight;
        if (std::abs(delta) < min_rebalance_delta_) {
            continue;
        }

        const auto price_it = prices.find(instrument_key(target.instrument));
        const double price = price_it == prices.end() ? 100.0 : price_it->second;
        const double quantity = std::abs(delta) * account_equity / std::max(price, 1.0);

        orders.push_back(OrderIntent{target.instrument,
                                     delta >= 0.0 ? OrderSide::Buy : OrderSide::Sell,
                                     OrderType::Market,
                                     quantity,
                                     price,
                                     "rebalance"});
    }

    return orders;
}

PaperBrokerGateway::PaperBrokerGateway(double max_participation_rate)
    : max_participation_rate_(max_participation_rate) {}

std::string PaperBrokerGateway::submit(const OrderIntent& order) {
    const std::string order_id = "PAPER-" + std::to_string(next_id_++);
    working_orders_.push_back(
        WorkingOrder{order_id, order, order.quantity, 0.0, 0.0});
    return order_id;
}

void PaperBrokerGateway::cancel_open_orders() {
    for (const auto& order : working_orders_) {
        pending_reports_.push_back(ExecutionReport{
            order.order_id,
            order.intent.instrument,
            order.intent.side,
            0.0,
            0.0,
            order.cumulative_filled_qty,
            order.remaining_qty,
            order.cumulative_filled_qty > 0.0
                ? order.cumulative_notional / order.cumulative_filled_qty
                : 0.0,
            0.0,
            0.0,
            OrderStatus::Cancelled,
            "CANCELLED",
        });
    }
    working_orders_.clear();
}

void PaperBrokerGateway::on_market_snapshot(std::span<const Bar> bars) {
    std::vector<WorkingOrder> still_working;
    still_working.reserve(working_orders_.size());

    for (auto& order : working_orders_) {
        const Bar* bar = find_bar(bars, order.intent.instrument);
        if (bar == nullptr) {
            still_working.push_back(order);
            continue;
        }

        const double max_fill_qty =
            std::max(1.0, bar->volume * max_participation_rate_);
        const double fill_qty = std::min(order.remaining_qty, max_fill_qty);
        if (fill_qty <= 1e-9) {
            still_working.push_back(order);
            continue;
        }

        const double participation = fill_qty / std::max(1.0, bar->volume);
        const double slippage_bps = 4.0 + participation * 2000.0;
        const double fill_multiplier =
            order.intent.side == OrderSide::Buy
                ? (1.0 + slippage_bps / 10000.0)
                : (1.0 - slippage_bps / 10000.0);
        const double fill_price = bar->close * fill_multiplier;
        const double fill_commission = std::max(1.0, fill_qty * 0.005);

        order.remaining_qty -= fill_qty;
        order.cumulative_filled_qty += fill_qty;
        order.cumulative_notional += fill_qty * fill_price;

        const OrderStatus status =
            order.remaining_qty <= 1e-9 ? OrderStatus::Filled
                                        : OrderStatus::PartiallyFilled;
        const std::string broker_status =
            status == OrderStatus::Filled ? "FILLED" : "PARTIALLY_FILLED";

        pending_reports_.push_back(ExecutionReport{
            order.order_id,
            order.intent.instrument,
            order.intent.side,
            fill_qty,
            fill_price,
            order.cumulative_filled_qty,
            std::max(0.0, order.remaining_qty),
            order.cumulative_notional /
                std::max(order.cumulative_filled_qty, 1e-9),
            fill_commission,
            slippage_bps,
            status,
            broker_status,
        });

        if (status != OrderStatus::Filled) {
            still_working.push_back(order);
        }
    }

    working_orders_.swap(still_working);
}

std::vector<ExecutionReport> PaperBrokerGateway::flush_reports() {
    auto reports = pending_reports_;
    pending_reports_.clear();
    return reports;
}

const Bar* PaperBrokerGateway::find_bar(std::span<const Bar> bars,
                                        const InstrumentId& instrument) const {
    const auto key = instrument_key(instrument);
    for (const auto& bar : bars) {
        if (instrument_key(bar.instrument) == key) {
            return &bar;
        }
    }
    return nullptr;
}

}  // namespace qt
