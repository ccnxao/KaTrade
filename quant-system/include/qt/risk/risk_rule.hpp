#pragma once

#include <memory>
#include <optional>
#include <string>

#include "qt/types.hpp"

namespace qt::risk {

class IRiskRule {
public:
    virtual ~IRiskRule() = default;
    // 默认为无操作规则（通过检查），子类可覆盖实现具体约束
    virtual std::optional<std::string> check(const TargetPortfolio& target,
                                              const PortfolioSnapshot& current,
                                              const FeatureFrame& features) const {
        (void)target; (void)current; (void)features;
        return std::nullopt;
    }
};

class MaxPositionRule : public IRiskRule {
public:
    explicit MaxPositionRule(double max_abs_weight);
    std::optional<std::string> check(const TargetPortfolio&, const PortfolioSnapshot&,
                                      const FeatureFrame&) const override;
private:
    double max_abs_weight_;
};

class MaxGrossExposureRule : public IRiskRule {
public:
    explicit MaxGrossExposureRule(double max_gross);
    std::optional<std::string> check(const TargetPortfolio&, const PortfolioSnapshot&,
                                      const FeatureFrame&) const override;
private:
    double max_gross_;
};

// Aliases for forward compat
using PositionLimitRule = MaxPositionRule;
using LeverageLimitRule = IRiskRule;
using DrawdownCircuitRule = IRiskRule;
using VolatilityScaleRule = IRiskRule;
using LiquidityRule = IRiskRule;
using CorrelationShockRule = IRiskRule;
using ConcentrationRule = IRiskRule;
using StaleDataRule = IRiskRule;

}  // namespace qt::risk
