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

std::string PaperBrokerGateway::submit(const OrderIntent& order) {
    const std::string order_id = "PAPER-" + std::to_string(next_id_++);
    const double slippage_bps = 5.0;
    const double slippage_multiplier =
        order.side == OrderSide::Buy ? (1.0 + slippage_bps / 10000.0)
                                     : (1.0 - slippage_bps / 10000.0);

    pending_reports_.push_back(ExecutionReport{
        order_id,
        order.instrument,
        order.quantity,
        order.reference_price * slippage_multiplier,
        std::max(1.0, order.quantity * 0.005),
        slippage_bps,
        "FILLED",
    });

    return order_id;
}

std::vector<ExecutionReport> PaperBrokerGateway::flush_reports() {
    auto reports = pending_reports_;
    pending_reports_.clear();
    return reports;
}

}  // namespace qt
