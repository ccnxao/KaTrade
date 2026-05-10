#pragma once

#include <deque>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

#include "qt/agent/agent.hpp"
#include "qt/types.hpp"

namespace qt::agent {

// BufferedStrategyAgent: stores bars via on_bar(), drains them for generate_signals()
class BufferedStrategyAgent : public ISignalAgent {
public:
    void on_bar(const Bar& bar) override { pending_bars_.push_back(bar); }
    void reset() override {
        pending_bars_.clear();
        reset_state();
    }

protected:
    std::vector<Bar> drain_pending_bars() { return std::exchange(pending_bars_, {}); }
    virtual void reset_state() {}

private:
    std::vector<Bar> pending_bars_;
};

class MomentumAgent : public BufferedStrategyAgent {
public:
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const FeatureFrame& features,
                                          const PortfolioSnapshot& portfolio,
                                          const RegimeState& regime) override;
};

class MeanReversionAgent : public BufferedStrategyAgent {
public:
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const FeatureFrame& features,
                                          const PortfolioSnapshot& portfolio,
                                          const RegimeState& regime) override;
};

class DefensiveAgent : public BufferedStrategyAgent {
public:
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const FeatureFrame& features,
                                          const PortfolioSnapshot& portfolio,
                                          const RegimeState& regime) override;
};

}  // namespace qt::agent
