#pragma once

#include <memory>
#include <optional>
#include <string>
#include <vector>

#include "qt/risk/risk_rule.hpp"
#include "qt/risk/stress_test.hpp"
#include "qt/types.hpp"

namespace qt::risk {

struct AccountState {
    double equity{};
    double cash{};
    double initial_equity{};
    double peak_equity{};
};

struct MarketState {
    double vix{};
    double realized_vol{};
    double avg_correlation{};
};

class RiskAgent {
public:
    RiskAgent(double max_abs_weight = 0.25, double max_gross = 1.2, bool kill_switch = false);

    void add_rule(std::unique_ptr<IRiskRule> rule);
    void set_kill_switch(bool enabled);
    bool kill_switch() const noexcept { return kill_switch_; }
    // Configurable thresholds (P1#3)
    void set_thresholds(double drawdown_limit, double vol_threshold,
                        double vol_reduction, double stress_tolerance);

    RiskDecision review(const TargetPortfolio& target,
                        const PortfolioSnapshot& current,
                        const FeatureFrame& features);
    RiskDecision review(const TargetPortfolio& target,
                        const PortfolioSnapshot& current,
                        const MarketState& market,
                        const AccountState& account);

private:
    double max_abs_weight_;
    double max_gross_;
    bool kill_switch_;
    double drawdown_limit_{0.20};
    double vol_threshold_{0.30};
    double vol_reduction_{0.50};
    double stress_tolerance_{0.20};
    std::vector<std::unique_ptr<class IRiskRule>> rules_;
    StressTester stress_tester_;  // R25: 复用，避免每次 review 新建
};

}  // namespace qt::risk
