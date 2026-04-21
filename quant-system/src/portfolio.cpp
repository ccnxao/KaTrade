#include "qt/portfolio.hpp"

#include <algorithm>
#include <cmath>
#include <unordered_map>

namespace qt {

namespace {

double strategy_weight(const std::string& strategy_id, const RegimeState& regime) {
    if (strategy_id == "momentum") {
        return regime.momentum_weight;
    }
    if (strategy_id == "mean_reversion") {
        return regime.mean_revert_weight;
    }
    if (strategy_id == "defensive") {
        return regime.defensive_weight;
    }
    return 0.10;
}

}  // namespace

SimplePortfolioOptimizer::SimplePortfolioOptimizer(double max_single_weight,
                                                   double max_gross)
    : max_single_weight_(max_single_weight), max_gross_(max_gross) {}

TargetPortfolio SimplePortfolioOptimizer::optimize(std::span<const Signal> signals,
                                                   const PortfolioSnapshot& current,
                                                   const FeatureFrame&,
                                                   const RegimeState& regime) {
    struct Accumulator {
        InstrumentId instrument;
        double score{0.0};
    };

    std::unordered_map<std::string, Accumulator> accumulated;
    for (const auto& signal : signals) {
        const auto key = instrument_key(signal.instrument);
        auto& entry = accumulated[key];
        entry.instrument = signal.instrument;
        entry.score += signal.score * signal.confidence *
                       strategy_weight(signal.strategy_id, regime);
    }

    double total_abs_score = 0.0;
    for (const auto& [_, entry] : accumulated) {
        total_abs_score += std::abs(entry.score);
    }

    TargetPortfolio target;
    if (total_abs_score <= 1e-9) {
        return target;
    }

    for (const auto& [_, entry] : accumulated) {
        double weight = (entry.score / total_abs_score) * max_gross_;
        weight = std::clamp(weight, -max_single_weight_, max_single_weight_);
        if (std::abs(weight) < 0.01) {
            continue;
        }
        target.positions.push_back(TargetPosition{entry.instrument, weight});
    }

    double gross = gross_exposure(target);
    if (gross > max_gross_ && gross > 0.0) {
        const double scale = max_gross_ / gross;
        for (auto& position : target.positions) {
            position.target_weight *= scale;
        }
    }

    double turnover = 0.0;
    for (const auto& position : target.positions) {
        const auto current_weight = find_weight(current, position.instrument).value_or(0.0);
        turnover += std::abs(position.target_weight - current_weight);
    }

    target.expected_turnover = turnover;
    target.expected_cost_bps = turnover * 8.0;
    return target;
}

}  // namespace qt
