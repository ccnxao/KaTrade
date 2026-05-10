#pragma once

#include <memory>
#include <string>
#include <string_view>
#include <vector>

#include "qt/types.hpp"

namespace qt::agent {

class IAgent {
public:
    virtual ~IAgent() = default;
    virtual std::string_view name() const noexcept = 0;
};

class ISignalAgent : public IAgent {
public:
    virtual void on_bar(const Bar& bar) = 0;
    virtual void reset() = 0;
    virtual std::vector<Signal> generate_signals(const FeatureFrame& features,
                                                  const PortfolioSnapshot& portfolio,
                                                  const RegimeState& regime) = 0;
};

class IMetaAgent : public IAgent {
public:
    virtual void on_bar(const Bar& bar) = 0;
    virtual RegimeState detect_regime(const FeatureFrame& features) = 0;
    virtual void record_cycle_pnl(double cycle_pnl) = 0;
    virtual void reset() = 0;
};

class IRegimeAgent : public IAgent {
public:
    virtual RegimeState detect_regime(const FeatureFrame& features) = 0;
    virtual void fit_online(const FeatureFrame&) {}
};

}  // namespace qt::agent
