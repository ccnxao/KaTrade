#pragma once

#include <memory>
#include <string>
#include <vector>

#include "qt/agents.hpp"
#include "qt/event_bus.hpp"
#include "qt/execution.hpp"
#include "qt/oms.hpp"
#include "qt/portfolio_book.hpp"
#include "qt/portfolio.hpp"
#include "qt/risk.hpp"

namespace qt {

struct CycleResult {
    std::size_t cycle_index{};
    std::string cycle_label;
    PriceMap prices;
    FeatureFrame features;
    PortfolioSnapshot pre_trade_portfolio;
    PortfolioSnapshot post_trade_portfolio;
    RegimeState regime;
    std::vector<Signal> signals;
    TargetPortfolio target_portfolio;
    RiskDecision risk_decision;
    std::vector<OrderIntent> orders;
    std::vector<OrderRecord> order_records;
    std::vector<ExecutionReport> reports;
};

class TraderEngine {
public:
    TraderEngine(std::unique_ptr<IMetaAgent> meta_agent,
                 std::vector<std::unique_ptr<ISignalAgent>> signal_agents,
                 std::unique_ptr<IPortfolioOptimizer> optimizer,
                 std::unique_ptr<RiskAgent> risk_agent,
                 std::unique_ptr<IExecutionAlgo> execution_algo,
                 std::unique_ptr<OrderManagementSystem> order_management_system,
                 double account_equity,
                 EventBus* event_bus = nullptr);

    CycleResult run_cycle(const std::vector<Bar>& bars, std::string cycle_label = {});
    PortfolioSnapshot portfolio() const;

private:
    FeatureFrame build_features(const std::vector<Bar>& bars) const;
    PriceMap build_prices(const std::vector<Bar>& bars) const;

    std::unique_ptr<IMetaAgent> meta_agent_;
    std::vector<std::unique_ptr<ISignalAgent>> signal_agents_;
    std::unique_ptr<IPortfolioOptimizer> optimizer_;
    std::unique_ptr<RiskAgent> risk_agent_;
    std::unique_ptr<IExecutionAlgo> execution_algo_;
    std::unique_ptr<OrderManagementSystem> order_management_system_;
    PortfolioBook portfolio_book_;
    double account_equity_;
    std::size_t cycle_id_{0};
    EventBus* event_bus_;
};

}  // namespace qt
