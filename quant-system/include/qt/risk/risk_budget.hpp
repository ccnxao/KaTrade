#pragma once

#include <string>
#include <vector>

#include "qt/types.hpp"

namespace qt {
struct CycleResult;
}

namespace qt::risk {

struct StrategyBudgetUsage {
    std::string strategy_id;
    double allocated_weight{};
    double current_weight{};
    double pnl{};
};

struct RiskBudgetInput {
    const CycleResult* cycle_result{nullptr};
    double max_risk_budget{0.02};
};

struct RiskBudgetConfig {
    double max_risk_budget{0.02};
    double max_strategy_weight{0.30};
    double turnover_limit{0.50};
    double reduction_scale{0.70};
    int lookback_cycles{50};
};

struct RiskBudgetCheck {
    std::string name;
    bool passed{true};
    std::string detail;
};

struct RiskBudgetDecision {
    RiskAction action{RiskAction::Approve};
    double scale{1.0};
    std::string reason;
    TargetPortfolio adjusted_portfolio;
    std::vector<RiskBudgetCheck> checks;
};

class RiskBudgetAllocator {
public:
    explicit RiskBudgetAllocator(const RiskBudgetConfig& config = {});
    RiskBudgetDecision allocate(const RiskBudgetInput& input);

private:
    RiskBudgetConfig config_;
};

}  // namespace qt::risk
