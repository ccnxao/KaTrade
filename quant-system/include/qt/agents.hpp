#pragma once

#include <deque>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include "qt/agent/agent.hpp"
#include "qt/agent/meta_agent.hpp"
#include "qt/agent/signal_agent.hpp"
#include "qt/agent/llm_feature_agent.hpp"

namespace qt {
using qt::agent::IAgent;
using qt::agent::ISignalAgent;
using qt::agent::IMetaAgent;
using qt::agent::MetaAgent;
using qt::agent::IRegimeAgent;
using qt::agent::RuleBasedRegimeAgent;
using qt::agent::HMMRegimeAgent;
using qt::agent::OnlineEMRegimeAgent;
using qt::agent::MomentumAgent;
using qt::agent::MeanReversionAgent;
using qt::agent::DefensiveAgent;
using qt::agent::BufferedStrategyAgent;
using qt::agent::LLMFeatureAgent;

class DonchianBreakoutAgent final : public BufferedStrategyAgent {
public:
    explicit DonchianBreakoutAgent(std::size_t lookback = 20);
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const FeatureFrame& features,
                                         const PortfolioSnapshot& portfolio,
                                         const RegimeState& regime) override;

private:
    void reset_state() override { state_.clear(); }
    struct ChannelState {
        std::deque<std::pair<std::size_t, double>> highs;
        std::deque<std::pair<std::size_t, double>> lows;
        std::size_t next_index{};
        std::size_t count{};
    };
    std::size_t lookback_;
    std::unordered_map<std::string, ChannelState> state_;
};

class MovingAverageCrossAgent final : public BufferedStrategyAgent {
public:
    MovingAverageCrossAgent(std::size_t fast_window = 5, std::size_t slow_window = 20);
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const FeatureFrame& features,
                                         const PortfolioSnapshot& portfolio,
                                         const RegimeState& regime) override;

private:
    void reset_state() override { state_.clear(); }
    struct MovingAverageState {
        std::deque<double> closes;
        double fast_sum{};
        double slow_sum{};
    };
    std::size_t fast_window_;
    std::size_t slow_window_;
    std::unordered_map<std::string, MovingAverageState> state_;
};

class MacdTrendAgent final : public BufferedStrategyAgent {
public:
    MacdTrendAgent(double fast_alpha = 0.35,
                   double slow_alpha = 0.12,
                   double signal_alpha = 0.20);
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const FeatureFrame& features,
                                         const PortfolioSnapshot& portfolio,
                                         const RegimeState& regime) override;

private:
    void reset_state() override { state_.clear(); }
    struct MacdState {
        bool initialized{};
        double fast_ema{};
        double slow_ema{};
        double signal_ema{};
    };
    double fast_alpha_;
    double slow_alpha_;
    double signal_alpha_;
    std::unordered_map<std::string, MacdState> state_;
};

class EmaSlopeTrendAgent final : public BufferedStrategyAgent {
public:
    EmaSlopeTrendAgent(double alpha = 0.25, double min_slope = 0.001);
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const FeatureFrame& features,
                                         const PortfolioSnapshot& portfolio,
                                         const RegimeState& regime) override;

private:
    void reset_state() override { state_.clear(); }
    struct EmaState {
        bool initialized{};
        double ema{};
        double previous_ema{};
    };
    double alpha_;
    double min_slope_;
    std::unordered_map<std::string, EmaState> state_;
};

class KeltnerBreakoutAgent final : public BufferedStrategyAgent {
public:
    KeltnerBreakoutAgent(double alpha = 0.20, double multiplier = 1.5);
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const FeatureFrame& features,
                                         const PortfolioSnapshot& portfolio,
                                         const RegimeState& regime) override;

private:
    void reset_state() override { state_.clear(); }
    struct KeltnerState {
        bool initialized{};
        double ema_close{};
        double atr{};
        double previous_close{};
    };
    double alpha_;
    double multiplier_;
    std::unordered_map<std::string, KeltnerState> state_;
};

class VolumeSpikeMomentumAgent final : public BufferedStrategyAgent {
public:
    VolumeSpikeMomentumAgent(double alpha = 0.20, double volume_multiplier = 2.0);
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const FeatureFrame& features,
                                         const PortfolioSnapshot& portfolio,
                                         const RegimeState& regime) override;

private:
    void reset_state() override { state_.clear(); }
    struct VolumeState {
        bool initialized{};
        double volume_ema{};
        double previous_close{};
    };
    double alpha_;
    double volume_multiplier_;
    std::unordered_map<std::string, VolumeState> state_;
};

class MicroScalperAgent final : public BufferedStrategyAgent {
public:
    MicroScalperAgent(double min_return = 0.0005, double min_body_ratio = 0.35);
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const FeatureFrame& features,
                                         const PortfolioSnapshot& portfolio,
                                         const RegimeState& regime) override;

private:
    void reset_state() override { state_.clear(); }
    struct MicroState {
        bool initialized{};
        double previous_close{};
    };
    double min_return_;
    double min_body_ratio_;
    std::unordered_map<std::string, MicroState> state_;
};

class SpreadCaptureMakerAgent final : public BufferedStrategyAgent {
public:
    SpreadCaptureMakerAgent(double alpha = 0.20, double threshold = 0.60);
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const FeatureFrame& features,
                                         const PortfolioSnapshot& portfolio,
                                         const RegimeState& regime) override;

private:
    void reset_state() override { state_.clear(); }
    struct SpreadState {
        bool initialized{};
        double fair_price{};
        double range_ema{};
    };
    double alpha_;
    double threshold_;
    std::unordered_map<std::string, SpreadState> state_;
};

class OrderFlowImbalanceAgent final : public BufferedStrategyAgent {
public:
    OrderFlowImbalanceAgent(double volume_alpha = 0.20,
                            double imbalance_threshold = 0.45);
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const FeatureFrame& features,
                                         const PortfolioSnapshot& portfolio,
                                         const RegimeState& regime) override;

private:
    void reset_state() override { state_.clear(); }
    struct FlowState {
        bool initialized{};
        double volume_ema{};
    };
    double volume_alpha_;
    double imbalance_threshold_;
    std::unordered_map<std::string, FlowState> state_;
};

class InventorySkewMakerAgent final : public BufferedStrategyAgent {
public:
    explicit InventorySkewMakerAgent(double neutral_band = 0.04);
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const FeatureFrame& features,
                                         const PortfolioSnapshot& portfolio,
                                         const RegimeState& regime) override;

private:
    double neutral_band_;
};

class BollingerReversionAgent final : public BufferedStrategyAgent {
public:
    BollingerReversionAgent(std::size_t window = 20, double band_width = 2.0);
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const FeatureFrame& features,
                                         const PortfolioSnapshot& portfolio,
                                         const RegimeState& regime) override;

private:
    void reset_state() override { state_.clear(); }
    struct RollingState {
        std::deque<double> closes;
        double sum{};
        double square_sum{};
    };
    std::size_t window_;
    double band_width_;
    std::unordered_map<std::string, RollingState> state_;
};

class RsiReversionAgent final : public BufferedStrategyAgent {
public:
    RsiReversionAgent(std::size_t window = 14,
                      double oversold = 30.0,
                      double overbought = 70.0);
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const FeatureFrame& features,
                                         const PortfolioSnapshot& portfolio,
                                         const RegimeState& regime) override;

private:
    void reset_state() override { state_.clear(); }
    struct RsiState {
        bool has_previous{};
        double previous_close{};
        std::deque<double> gains;
        std::deque<double> losses;
        double gain_sum{};
        double loss_sum{};
    };
    std::size_t window_;
    double oversold_;
    double overbought_;
    std::unordered_map<std::string, RsiState> state_;
};

class ZScoreReversionAgent final : public BufferedStrategyAgent {
public:
    ZScoreReversionAgent(std::size_t window = 20, double threshold = 1.5);
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const FeatureFrame& features,
                                         const PortfolioSnapshot& portfolio,
                                         const RegimeState& regime) override;

private:
    void reset_state() override { state_.clear(); }
    struct RollingState {
        std::deque<double> closes;
        double sum{};
        double square_sum{};
    };
    std::size_t window_;
    double threshold_;
    std::unordered_map<std::string, RollingState> state_;
};

class RangeFadeAgent final : public BufferedStrategyAgent {
public:
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const FeatureFrame& features,
                                         const PortfolioSnapshot& portfolio,
                                         const RegimeState& regime) override;
};
}  // namespace qt
