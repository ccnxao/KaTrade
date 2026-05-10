#include "qt/agents.hpp"

#include <algorithm>
#include <cmath>

namespace qt {

namespace {

double clamp_score(double value) {
    return std::clamp(value, -1.0, 1.0);
}

}  // namespace

DonchianBreakoutAgent::DonchianBreakoutAgent(std::size_t lookback)
    : lookback_(std::max<std::size_t>(2, lookback)) {}

std::string_view DonchianBreakoutAgent::name() const noexcept {
    return "donchian_breakout";
}

std::vector<Signal> DonchianBreakoutAgent::generate_signals(
    const FeatureFrame&,
    const PortfolioSnapshot&,
    const RegimeState& regime) {
    std::vector<Signal> signals;
    const auto bars = drain_pending_bars();

    // 唐奇安突破只使用“上一段历史”的高低点判断本周期是否突破。
    // 当前 bar 在判断完成后才写入 history，避免用未来数据污染信号。
    const double regime_boost = regime.regime == Regime::Trending ? 1.0 : 0.65;

    for (const auto& bar : bars) {
        const auto key = instrument_key(bar.instrument);
        auto& state = state_[key];

        if (state.count >= lookback_ && !state.highs.empty() && !state.lows.empty()) {
            const double channel_high = state.highs.front().second;
            const double channel_low = state.lows.front().second;
            const double channel_width = std::max(channel_high - channel_low, 1e-9);
            if (bar.close > channel_high) {
                const double distance = (bar.close - channel_high) / channel_width;
                signals.push_back(Signal{std::string{name()},
                                         bar.instrument,
                                         clamp_score(0.35 + distance * 1.2),
                                         0.72 * regime_boost});
            } else if (bar.close < channel_low) {
                const double distance = (channel_low - bar.close) / channel_width;
                signals.push_back(Signal{std::string{name()},
                                         bar.instrument,
                                         clamp_score(-0.35 - distance * 1.2),
                                         0.72 * regime_boost});
            }
        }

        const std::size_t index = state.next_index;
        while (!state.highs.empty() && state.highs.back().second <= bar.high) {
            state.highs.pop_back();
        }
        state.highs.emplace_back(index, bar.high);
        while (!state.lows.empty() && state.lows.back().second >= bar.low) {
            state.lows.pop_back();
        }
        state.lows.emplace_back(index, bar.low);

        ++state.next_index;
        ++state.count;
        const std::size_t first_live =
            state.next_index > lookback_ ? state.next_index - lookback_ : 0;
        while (!state.highs.empty() && state.highs.front().first < first_live) {
            state.highs.pop_front();
        }
        while (!state.lows.empty() && state.lows.front().first < first_live) {
            state.lows.pop_front();
        }
    }
    return signals;
}

MovingAverageCrossAgent::MovingAverageCrossAgent(std::size_t fast_window,
                                                 std::size_t slow_window)
    : fast_window_(std::max<std::size_t>(1, fast_window)),
      slow_window_(std::max<std::size_t>(fast_window_ + 1, slow_window)) {}

std::string_view MovingAverageCrossAgent::name() const noexcept {
    return "ma_cross";
}

std::vector<Signal> MovingAverageCrossAgent::generate_signals(
    const FeatureFrame&,
    const PortfolioSnapshot&,
    const RegimeState& regime) {
    std::vector<Signal> signals;
    const auto bars = drain_pending_bars();
    const double confidence =
        regime.regime == Regime::Trending ? 0.74
        : regime.regime == Regime::Crisis ? 0.35
                                          : 0.52;

    for (const auto& bar : bars) {
        const auto key = instrument_key(bar.instrument);
        auto& state = state_[key];
        state.closes.push_back(bar.close);
        state.fast_sum += bar.close;
        state.slow_sum += bar.close;
        if (state.closes.size() > fast_window_) {
            state.fast_sum -= state.closes[state.closes.size() - fast_window_ - 1];
        }
        if (state.closes.size() > slow_window_) {
            state.slow_sum -= state.closes.front();
            state.closes.pop_front();
        }

        if (state.closes.size() < slow_window_) {
            continue;
        }

        // 快均线在慢均线上方给多头信号，反之给空头信号。
        // 分数按价差比例缩放，交给组合优化器和风险层裁剪最终仓位。
        const double fast = state.fast_sum / static_cast<double>(fast_window_);
        const double slow = state.slow_sum / static_cast<double>(slow_window_);
        const double spread = (fast - slow) / std::max(std::abs(slow), 1e-9);
        if (std::abs(spread) < 0.003) {
            continue;
        }
        signals.push_back(Signal{std::string{name()},
                                 bar.instrument,
                                 clamp_score(spread * 35.0),
                                 confidence});
    }
    return signals;
}

MacdTrendAgent::MacdTrendAgent(double fast_alpha,
                               double slow_alpha,
                               double signal_alpha)
    : fast_alpha_(std::clamp(fast_alpha, 0.01, 1.0)),
      slow_alpha_(std::clamp(slow_alpha, 0.01, 1.0)),
      signal_alpha_(std::clamp(signal_alpha, 0.01, 1.0)) {}

std::string_view MacdTrendAgent::name() const noexcept {
    return "macd_trend";
}

std::vector<Signal> MacdTrendAgent::generate_signals(
    const FeatureFrame&,
    const PortfolioSnapshot&,
    const RegimeState& regime) {
    std::vector<Signal> signals;
    const auto bars = drain_pending_bars();
    const double confidence =
        regime.regime == Regime::Trending ? 0.76
        : regime.regime == Regime::Crisis ? 0.34
                                          : 0.50;

    for (const auto& bar : bars) {
        const auto key = instrument_key(bar.instrument);
        auto& state = state_[key];
        if (!state.initialized) {
            state.initialized = true;
            state.fast_ema = bar.close;
            state.slow_ema = bar.close;
            state.signal_ema = 0.0;  // bar.close-bar.close=0，首 bar 直方图为 0，避免虚假信号
            continue;
        }

        // MACD 使用递推 EMA，只依赖已经到达的价格。
        // macd_line 代表快慢均线差，histogram 代表趋势动量的二阶变化。
        state.fast_ema = fast_alpha_ * bar.close + (1.0 - fast_alpha_) * state.fast_ema;
        state.slow_ema = slow_alpha_ * bar.close + (1.0 - slow_alpha_) * state.slow_ema;
        const double macd_line = state.fast_ema - state.slow_ema;
        state.signal_ema =
            signal_alpha_ * macd_line + (1.0 - signal_alpha_) * state.signal_ema;
        const double histogram = macd_line - state.signal_ema;
        const double scaled = histogram / std::max(std::abs(bar.close), 1e-9);
        if (std::abs(scaled) < 0.001) {
            continue;
        }
        signals.push_back(Signal{std::string{name()},
                                 bar.instrument,
                                 clamp_score(scaled * 80.0),
                                 confidence});
    }
    return signals;
}

EmaSlopeTrendAgent::EmaSlopeTrendAgent(double alpha, double min_slope)
    : alpha_(std::clamp(alpha, 0.01, 1.0)),
      min_slope_(std::clamp(min_slope, 0.0001, 0.20)) {}

std::string_view EmaSlopeTrendAgent::name() const noexcept {
    return "ema_slope_trend";
}

std::vector<Signal> EmaSlopeTrendAgent::generate_signals(
    const FeatureFrame&,
    const PortfolioSnapshot&,
    const RegimeState& regime) {
    std::vector<Signal> signals;
    const auto bars = drain_pending_bars();
    const double confidence =
        regime.regime == Regime::Trending ? 0.72
        : regime.regime == Regime::Crisis ? 0.32
                                          : 0.48;

    for (const auto& bar : bars) {
        const auto key = instrument_key(bar.instrument);
        auto& state = state_[key];
        if (!state.initialized) {
            state.initialized = true;
            state.ema = bar.close;
            state.previous_ema = bar.close;
            continue;
        }

        state.previous_ema = state.ema;
        state.ema = alpha_ * bar.close + (1.0 - alpha_) * state.ema;
        const double slope = (state.ema - state.previous_ema) / std::max(std::abs(bar.close), 1e-9);
        if (std::abs(slope) < min_slope_) {
            continue;
        }
        signals.push_back(Signal{std::string{name()},
                                 bar.instrument,
                                 clamp_score(slope / (min_slope_ * 4.0)),
                                 confidence});
    }
    return signals;
}

KeltnerBreakoutAgent::KeltnerBreakoutAgent(double alpha, double multiplier)
    : alpha_(std::clamp(alpha, 0.01, 1.0)),
      multiplier_(std::clamp(multiplier, 0.1, 10.0)) {}

std::string_view KeltnerBreakoutAgent::name() const noexcept {
    return "keltner_breakout";
}

std::vector<Signal> KeltnerBreakoutAgent::generate_signals(
    const FeatureFrame&,
    const PortfolioSnapshot&,
    const RegimeState& regime) {
    std::vector<Signal> signals;
    const auto bars = drain_pending_bars();
    const double confidence =
        regime.regime == Regime::Trending ? 0.78
        : regime.regime == Regime::Crisis ? 0.36
                                          : 0.54;

    for (const auto& bar : bars) {
        const auto key = instrument_key(bar.instrument);
        auto& state = state_[key];
        if (!state.initialized) {
            state.initialized = true;
            state.ema_close = bar.close;
            state.atr = std::max(bar.high - bar.low, 1e-9);
            state.previous_close = bar.close;
            continue;
        }

        const double safe_atr = std::max(state.atr, 1e-9);
        const double upper = state.ema_close + multiplier_ * safe_atr;
        const double lower = state.ema_close - multiplier_ * safe_atr;
        if (bar.close > upper) {
            const double distance = (bar.close - upper) / safe_atr;
            signals.push_back(Signal{std::string{name()},
                                     bar.instrument,
                                     clamp_score(0.25 + distance / multiplier_),
                                     confidence});
        } else if (bar.close < lower) {
            const double distance = (lower - bar.close) / safe_atr;
            signals.push_back(Signal{std::string{name()},
                                     bar.instrument,
                                     clamp_score(-0.25 - distance / multiplier_),
                                     confidence});
        }

        const double true_range = std::max({
            bar.high - bar.low,
            std::abs(bar.high - state.previous_close),
            std::abs(bar.low - state.previous_close),
        });
        state.ema_close = alpha_ * bar.close + (1.0 - alpha_) * state.ema_close;
        state.atr = alpha_ * true_range + (1.0 - alpha_) * state.atr;
        state.previous_close = bar.close;
    }
    return signals;
}

VolumeSpikeMomentumAgent::VolumeSpikeMomentumAgent(double alpha,
                                                   double volume_multiplier)
    : alpha_(std::clamp(alpha, 0.01, 1.0)),
      volume_multiplier_(std::clamp(volume_multiplier, 1.0, 20.0)) {}

std::string_view VolumeSpikeMomentumAgent::name() const noexcept {
    return "volume_spike_momentum";
}

std::vector<Signal> VolumeSpikeMomentumAgent::generate_signals(
    const FeatureFrame&,
    const PortfolioSnapshot&,
    const RegimeState& regime) {
    std::vector<Signal> signals;
    const auto bars = drain_pending_bars();
    const double confidence =
        regime.regime == Regime::Trending ? 0.68
        : regime.regime == Regime::Crisis ? 0.30
                                          : 0.50;

    for (const auto& bar : bars) {
        const auto key = instrument_key(bar.instrument);
        auto& state = state_[key];
        if (!state.initialized) {
            state.initialized = true;
            state.volume_ema = std::max(bar.volume, 1e-9);
            state.previous_close = bar.close;
            continue;
        }

        const double previous_close = std::max(std::abs(state.previous_close), 1e-9);
        const double ret = (bar.close - state.previous_close) / previous_close;
        const double volume_ratio = bar.volume / std::max(state.volume_ema, 1e-9);
        if (volume_ratio >= volume_multiplier_ && std::abs(ret) >= 0.001) {
            const double spike_strength = std::min(volume_ratio / volume_multiplier_, 4.0);
            signals.push_back(Signal{std::string{name()},
                                     bar.instrument,
                                     clamp_score(ret * 80.0 * spike_strength),
                                     confidence});
        }

        state.volume_ema = alpha_ * std::max(bar.volume, 0.0) + (1.0 - alpha_) * state.volume_ema;
        state.previous_close = bar.close;
    }
    return signals;
}

}  // namespace qt
