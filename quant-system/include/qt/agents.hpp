#pragma once

#include <memory>
#include <string_view>
#include <vector>

#include "qt/types.hpp"

namespace qt {

class IAgent {
public:
    virtual ~IAgent() = default;
    virtual std::string_view name() const noexcept = 0;
};

class IMetaAgent : public IAgent {
public:
    virtual RegimeState detect_regime(const FeatureFrame& features) = 0;
};

class ISignalAgent : public IAgent {
public:
    virtual std::vector<Signal> generate_signals(const std::vector<Bar>& bars,
                                                 const FeatureFrame& features,
                                                 const PortfolioSnapshot& portfolio,
                                                 const RegimeState& regime) = 0;
};

class RuleBasedRegimeAgent final : public IMetaAgent {
public:
    std::string_view name() const noexcept override;
    RegimeState detect_regime(const FeatureFrame& features) override;
};

class MomentumAgent final : public ISignalAgent {
public:
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const std::vector<Bar>& bars,
                                         const FeatureFrame& features,
                                         const PortfolioSnapshot& portfolio,
                                         const RegimeState& regime) override;
};

class MeanReversionAgent final : public ISignalAgent {
public:
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const std::vector<Bar>& bars,
                                         const FeatureFrame& features,
                                         const PortfolioSnapshot& portfolio,
                                         const RegimeState& regime) override;
};

class DefensiveAgent final : public ISignalAgent {
public:
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const std::vector<Bar>& bars,
                                         const FeatureFrame& features,
                                         const PortfolioSnapshot& portfolio,
                                         const RegimeState& regime) override;
};

}  // namespace qt
