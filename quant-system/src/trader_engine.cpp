#include "qt/trader_engine.hpp"

#include <algorithm>
#include <cmath>
#include <numeric>

namespace qt {

TraderEngine::TraderEngine(std::unique_ptr<IMetaAgent> meta_agent,
                           std::vector<std::unique_ptr<ISignalAgent>> signal_agents,
                           std::unique_ptr<IPortfolioOptimizer> optimizer,
                           std::unique_ptr<RiskAgent> risk_agent,
                           std::unique_ptr<IExecutionAlgo> execution_algo,
                           std::unique_ptr<OrderManagementSystem> order_management_system,
                           double account_equity,
                           EventBus* event_bus)
    : meta_agent_(std::move(meta_agent)),
      signal_agents_(std::move(signal_agents)),
      optimizer_(std::move(optimizer)),
      risk_agent_(std::move(risk_agent)),
      execution_algo_(std::move(execution_algo)),
      order_management_system_(std::move(order_management_system)),
      account_equity_(account_equity),
      event_bus_(event_bus) {}

CycleResult TraderEngine::run_cycle(const std::vector<Bar>& bars, std::string cycle_label) {
    ++cycle_id_;

    CycleResult result;
    result.cycle_index = cycle_id_;
    result.cycle_label = cycle_label.empty() ? "Cycle " + std::to_string(cycle_id_)
                                             : std::move(cycle_label);

    if (event_bus_ != nullptr) {
        event_bus_->publish(
            CycleStartedEvent{result.cycle_index, result.cycle_label, bars.size()});
    }

    result.features = build_features(bars);
    result.regime = meta_agent_->detect_regime(result.features);
    if (event_bus_ != nullptr) {
        event_bus_->publish(RegimeDetectedEvent{result.cycle_index, result.regime});
    }

    for (auto& agent : signal_agents_) {
        auto agent_signals =
            agent->generate_signals(bars, result.features, portfolio_, result.regime);
        result.signals.insert(result.signals.end(), agent_signals.begin(),
                              agent_signals.end());
    }

    result.target_portfolio =
        optimizer_->optimize(result.signals, portfolio_, result.features, result.regime);
    result.risk_decision =
        risk_agent_->review(result.target_portfolio, portfolio_, result.features);
    if (event_bus_ != nullptr) {
        event_bus_->publish(RiskReviewedEvent{result.cycle_index, result.risk_decision});
    }

    const auto prices = build_prices(bars);
    result.orders = execution_algo_->plan(result.risk_decision, portfolio_, prices,
                                          account_equity_);
    result.order_records = order_management_system_->submit_orders(result.orders);
    if (event_bus_ != nullptr) {
        for (const auto& record : result.order_records) {
            event_bus_->publish(OrderSubmittedEvent{result.cycle_index, record});
        }
    }

    result.reports = order_management_system_->collect_reports();
    for (const auto& report : result.reports) {
        for (auto& record : result.order_records) {
            if (record.order_id == report.order_id) {
                record.filled_qty = report.filled_qty;
                record.avg_price = report.avg_price;
                record.commission = report.commission;
                record.status = report.broker_status == "FILLED"
                                    ? OrderStatus::Filled
                                    : OrderStatus::Rejected;
            }
        }
    }
    if (event_bus_ != nullptr) {
        for (const auto& report : result.reports) {
            event_bus_->publish(OrderFilledEvent{result.cycle_index, report});
        }
    }

    if (result.risk_decision.action != RiskAction::Reject &&
        result.risk_decision.action != RiskAction::Halt) {
        apply_target_portfolio(result.risk_decision.adjusted_portfolio);
    }

    if (event_bus_ != nullptr) {
        event_bus_->publish(CycleCompletedEvent{result.cycle_index,
                                                result.cycle_label,
                                                result.signals.size(),
                                                result.order_records.size(),
                                                result.reports.size()});
    }

    return result;
}

const PortfolioSnapshot& TraderEngine::portfolio() const noexcept {
    return portfolio_;
}

FeatureFrame TraderEngine::build_features(const std::vector<Bar>& bars) const {
    FeatureFrame features;
    if (bars.empty()) {
        return features;
    }

    std::vector<double> returns;
    returns.reserve(bars.size());
    for (const auto& bar : bars) {
        if (bar.open == 0.0) {
            continue;
        }
        returns.push_back((bar.close - bar.open) / bar.open);
    }

    if (returns.empty()) {
        return features;
    }

    const double sum = std::accumulate(returns.begin(), returns.end(), 0.0);
    const double mean = sum / static_cast<double>(returns.size());

    double variance = 0.0;
    for (const double value : returns) {
        const double diff = value - mean;
        variance += diff * diff;
    }
    variance /= static_cast<double>(returns.size());

    const double vol =
        std::sqrt(variance) * std::sqrt(static_cast<double>(returns.size())) * 4.0;
    const double adx_proxy = 12.0 + (std::abs(mean) / std::max(vol, 0.005)) * 80.0;
    const double corr_proxy =
        std::clamp(0.25 + vol * 2.0 + std::abs(mean) * 1.5, 0.10, 0.95);

    features["market.ret_20d"] = mean;
    features["market.realized_vol_20d"] = vol;
    features["market.adx_20d"] = adx_proxy;
    features["market.avg_corr_20d"] = corr_proxy;

    return features;
}

PriceMap TraderEngine::build_prices(const std::vector<Bar>& bars) const {
    PriceMap prices;
    for (const auto& bar : bars) {
        prices[instrument_key(bar.instrument)] = bar.close;
    }
    return prices;
}

void TraderEngine::apply_target_portfolio(const TargetPortfolio& portfolio) {
    portfolio_.positions.clear();
    double gross = 0.0;
    for (const auto& position : portfolio.positions) {
        portfolio_.positions.push_back(Position{position.instrument, position.target_weight});
        gross += std::abs(position.target_weight);
    }
    portfolio_.cash_weight = std::max(0.0, 1.0 - gross);
}

}  // namespace qt
