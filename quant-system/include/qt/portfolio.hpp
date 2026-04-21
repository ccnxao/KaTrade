#pragma once

#include <span>

#include "qt/types.hpp"

namespace qt {

class IPortfolioOptimizer {
public:
    virtual ~IPortfolioOptimizer() = default;
    virtual TargetPortfolio optimize(std::span<const Signal> signals,
                                     const PortfolioSnapshot& current,
                                     const FeatureFrame& features,
                                     const RegimeState& regime) = 0;
};

class SimplePortfolioOptimizer final : public IPortfolioOptimizer {
public:
    SimplePortfolioOptimizer(double max_single_weight, double max_gross);

    TargetPortfolio optimize(std::span<const Signal> signals,
                             const PortfolioSnapshot& current,
                             const FeatureFrame& features,
                             const RegimeState& regime) override;

private:
    double max_single_weight_;
    double max_gross_;
};

}  // namespace qt
