#pragma once

#include <memory>
#include <vector>

#include "qt/agents.hpp"
#include "qt/execution.hpp"
#include "qt/portfolio.hpp"
#include "qt/risk.hpp"

namespace qt {

struct CycleResult {
    FeatureFrame features;
    RegimeState regime;
    std::vector<Signal> signals;
    TargetPortfolio target_portfolio;
    RiskDecision risk_decision;
    std::vector<OrderIntent> orders;
    std::vector<ExecutionReport> reports;
};

class TraderEngine {
public:
    TraderEngine(std::unique_ptr<IMetaAgent> meta_agent,
                 std::vector<std::unique_ptr<ISignalAgent>> signal_agents,
                 std::unique_ptr<IPortfolioOptimizer> optimizer,
                 std::unique_ptr<RiskAgent> risk_agent,
                 std::unique_ptr<IExecutionAlgo> execution_algo,
                 std::unique_ptr<IBrokerGateway> broker_gateway,
                 double account_equity);

    CycleResult run_cycle(const std::vector<Bar>& bars);
    const PortfolioSnapshot& portfolio() const noexcept;

private:
    FeatureFrame build_features(const std::vector<Bar>& bars) const;
    PriceMap build_prices(const std::vector<Bar>& bars) const;
    void apply_target_portfolio(const TargetPortfolio& portfolio);

    std::unique_ptr<IMetaAgent> meta_agent_;
    std::vector<std::unique_ptr<ISignalAgent>> signal_agents_;
    std::unique_ptr<IPortfolioOptimizer> optimizer_;
    std::unique_ptr<RiskAgent> risk_agent_;
    std::unique_ptr<IExecutionAlgo> execution_algo_;
    std::unique_ptr<IBrokerGateway> broker_gateway_;
    PortfolioSnapshot portfolio_;
    double account_equity_;
    std::size_t cycle_id_{0};
};

}  // namespace qt
