#include "qt/risk.hpp"

#include <algorithm>
#include <cmath>

namespace qt {

MaxPositionRule::MaxPositionRule(double max_abs_weight)
    : max_abs_weight_(max_abs_weight) {}

std::optional<std::string> MaxPositionRule::check(const TargetPortfolio& target,
                                                  const PortfolioSnapshot&,
                                                  const FeatureFrame&) const {
    for (const auto& position : target.positions) {
        if (std::abs(position.target_weight) > max_abs_weight_ + 1e-9) {
            return "position weight exceeds single-name limit";
        }
    }
    return std::nullopt;
}

MaxGrossExposureRule::MaxGrossExposureRule(double max_gross)
    : max_gross_(max_gross) {}

std::optional<std::string> MaxGrossExposureRule::check(const TargetPortfolio& target,
                                                       const PortfolioSnapshot&,
                                                       const FeatureFrame&) const {
    if (gross_exposure(target) > max_gross_ + 1e-9) {
        return "gross exposure exceeds portfolio limit";
    }
    return std::nullopt;
}

RiskAgent::RiskAgent(double max_abs_weight, double max_gross)
    : max_abs_weight_(max_abs_weight), max_gross_(max_gross) {
    rules_.push_back(std::make_unique<MaxPositionRule>(max_abs_weight_));
    rules_.push_back(std::make_unique<MaxGrossExposureRule>(max_gross_));
}

RiskDecision RiskAgent::review(const TargetPortfolio& target,
                               const PortfolioSnapshot& current,
                               const FeatureFrame& features) {
    TargetPortfolio adjusted = target;
    bool changed = false;

    for (auto& position : adjusted.positions) {
        const double clamped =
            std::clamp(position.target_weight, -max_abs_weight_, max_abs_weight_);
        if (std::abs(clamped - position.target_weight) > 1e-9) {
            position.target_weight = clamped;
            changed = true;
        }
    }

    double gross = gross_exposure(adjusted);
    if (gross > max_gross_ && gross > 0.0) {
        const double scale = max_gross_ / gross;
        for (auto& position : adjusted.positions) {
            position.target_weight *= scale;
        }
        changed = true;
    }

    const auto vol_it = features.find("market.realized_vol_20d");
    const double vol = vol_it == features.end() ? 0.15 : vol_it->second;
    if (vol > 0.30) {
        for (auto& position : adjusted.positions) {
            position.target_weight *= 0.5;
        }
        changed = true;
    }

    for (const auto& rule : rules_) {
        if (const auto error = rule->check(adjusted, current, features)) {
            return {RiskAction::Reject, *error, {}};
        }
    }

    adjusted.expected_turnover = target.expected_turnover;
    adjusted.expected_cost_bps = target.expected_cost_bps;
    adjusted.optimizer_version = target.optimizer_version;

    if (adjusted.positions.empty()) {
        return {RiskAction::Reject, "risk agent produced an empty portfolio", {}};
    }

    return {changed ? RiskAction::Reduce : RiskAction::Approve,
            changed ? "risk-adjusted portfolio" : "approved",
            adjusted};
}

}  // namespace qt
