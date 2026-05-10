#pragma once

#include <string>
#include <vector>

#include "qt/types.hpp"

namespace qt::risk {

struct StressScenario {
    std::string name;
    double vol_shock{1.5};    // multiplier on current vol
    double corr_shock{0.8};   // correlation spike
    double price_shock{-0.15}; // % price drop
};

struct StressTestResult {
    std::string scenario;
    double estimated_pnl{};
    double equity_impact_pct{};
    bool within_tolerance{true};
};

class StressTester {
public:
    StressTester();
    void set_tolerance(double tol) { tolerance_ = tol; }
    std::vector<StressTestResult> run(const PortfolioSnapshot& portfolio,
                                       const FeatureFrame& features) const;

private:
    double tolerance_{0.20};
    std::vector<StressScenario> scenarios_;
};

}  // namespace qt::risk
