#include "qt/risk/risk_budget.hpp"

#include <algorithm>
#include <cmath>

#include "qt/trader_engine.hpp"  // for CycleResult

namespace qt::risk {

RiskBudgetAllocator::RiskBudgetAllocator(const RiskBudgetConfig& config)
    : config_(config) {}

RiskBudgetDecision RiskBudgetAllocator::allocate(const RiskBudgetInput& input) {
    RiskBudgetDecision decision;
    std::vector<RiskBudgetCheck> checks;

    if (!input.cycle_result) {
        decision.action = RiskAction::Reject;
        decision.reason = "risk budget: no cycle result";
        return decision;
    }

    const auto& target = input.cycle_result->target_portfolio;

    // 检查 1: 总敞口是否超出预算
    double gross = gross_exposure(target);
    checks.push_back({
        "gross_exposure",
        gross <= 1.2,
        "gross=" + std::to_string(gross) + " limit=1.2",
    });

    // 检查 2: 单策略最大权重
    bool any_overweight = false;
    for (const auto& pos : target.positions) {
        if (std::abs(pos.target_weight) > config_.max_strategy_weight) {
            any_overweight = true;
            break;
        }
    }
    checks.push_back({
        "max_strategy_weight",
        !any_overweight,
        "limit=" + std::to_string(config_.max_strategy_weight),
    });

    // 检查 3: 换手率是否过高 (简化: 使用 expected_turnover)
    double turnover = target.expected_turnover;
    bool turnover_ok = turnover <= config_.turnover_limit;
    checks.push_back({
        "turnover",
        turnover_ok,
        "turnover=" + std::to_string(turnover) + " limit=" + std::to_string(config_.turnover_limit),
    });

    // 汇总
    bool all_ok = true;
    for (const auto& c : checks) {
        if (!c.passed) all_ok = false;
    }
    decision.checks = checks;

    if (all_ok) {
        decision.action = RiskAction::Approve;
        decision.scale = 1.0;
        decision.reason = "risk budget: all checks passed";
        decision.adjusted_portfolio = target;
    } else {
        // 降低风险: 等比缩放到预算内
        decision.action = RiskAction::Reduce;
        decision.scale = config_.reduction_scale;
        decision.reason = "risk budget: scaled down to " + std::to_string(int(config_.reduction_scale * 100)) + "%";
        decision.adjusted_portfolio = target;
        for (auto& pos : decision.adjusted_portfolio.positions) {
            pos.target_weight *= decision.scale;
        }
    }

    return decision;
}

}  // namespace qt::risk
