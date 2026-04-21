#pragma once

#include <memory>
#include <optional>
#include <string>
#include <vector>

#include "qt/types.hpp"

namespace qt {

class IRiskRule {
public:
    virtual ~IRiskRule() = default;
    virtual std::optional<std::string> check(const TargetPortfolio& target,
                                             const PortfolioSnapshot& current,
                                             const FeatureFrame& features) const = 0;
};

class MaxPositionRule final : public IRiskRule {
public:
    explicit MaxPositionRule(double max_abs_weight);
    std::optional<std::string> check(const TargetPortfolio& target,
                                     const PortfolioSnapshot& current,
                                     const FeatureFrame& features) const override;

private:
    double max_abs_weight_;
};

class MaxGrossExposureRule final : public IRiskRule {
public:
    explicit MaxGrossExposureRule(double max_gross);
    std::optional<std::string> check(const TargetPortfolio& target,
                                     const PortfolioSnapshot& current,
                                     const FeatureFrame& features) const override;

private:
    double max_gross_;
};

class RiskAgent {
public:
    RiskAgent(double max_abs_weight, double max_gross);

    RiskDecision review(const TargetPortfolio& target,
                        const PortfolioSnapshot& current,
                        const FeatureFrame& features);

private:
    double max_abs_weight_;
    double max_gross_;
    std::vector<std::unique_ptr<IRiskRule>> rules_;
};

}  // namespace qt
