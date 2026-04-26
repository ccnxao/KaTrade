#include "qt/agents.hpp"

#include <algorithm>
#include <cmath>
#include <numeric>

namespace qt {

namespace {

double clamp_score(double value) {
    return std::clamp(value, -1.0, 1.0);
}

double tail_mean(const std::vector<double>& values, std::size_t window) {
    if (values.empty()) {
        return 0.0;
    }
    const std::size_t count = std::min(window, values.size());
    const auto first = values.end() - static_cast<std::ptrdiff_t>(count);
    return std::accumulate(first, values.end(), 0.0) / static_cast<double>(count);
}

template <typename T>
void trim_history(std::vector<T>& history, std::size_t max_size) {
    if (history.size() <= max_size) {
        return;
    }
    history.erase(history.begin(),
                  history.begin() +
                      static_cast<std::ptrdiff_t>(history.size() - max_size));
}

}  // namespace

DonchianBreakoutAgent::DonchianBreakoutAgent(std::size_t lookback)
    : lookback_(std::max<std::size_t>(2, lookback)) {}

std::string_view DonchianBreakoutAgent::name() const noexcept {
    return "donchian_breakout";
}

std::vector<Signal> DonchianBreakoutAgent::generate_signals(
    const std::vector<Bar>& bars,
    const FeatureFrame&,
    const PortfolioSnapshot&,
    const RegimeState& regime) {
    std::vector<Signal> signals;

    // 唐奇安突破只使用“上一段历史”的高低点判断本周期是否突破。
    // 当前 bar 在判断完成后才写入 history，避免用未来数据污染信号。
    const double regime_boost = regime.regime == Regime::Trending ? 1.0 : 0.65;

    for (const auto& bar : bars) {
        const auto key = instrument_key(bar.instrument);
        auto& history = history_[key];

        if (history.size() >= lookback_) {
            double channel_high = history.front().high;
            double channel_low = history.front().low;
            for (const auto& prior : history) {
                channel_high = std::max(channel_high, prior.high);
                channel_low = std::min(channel_low, prior.low);
            }

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

        history.push_back(bar);
        trim_history(history, lookback_);
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
    const std::vector<Bar>& bars,
    const FeatureFrame&,
    const PortfolioSnapshot&,
    const RegimeState& regime) {
    std::vector<Signal> signals;
    const double confidence =
        regime.regime == Regime::Trending ? 0.74
        : regime.regime == Regime::Crisis ? 0.35
                                          : 0.52;

    for (const auto& bar : bars) {
        const auto key = instrument_key(bar.instrument);
        auto& closes = closes_[key];
        closes.push_back(bar.close);
        trim_history(closes, slow_window_ + 2);

        if (closes.size() < slow_window_) {
            continue;
        }

        // 快均线在慢均线上方给多头信号，反之给空头信号。
        // 分数按价差比例缩放，交给组合优化器和风险层裁剪最终仓位。
        const double fast = tail_mean(closes, fast_window_);
        const double slow = tail_mean(closes, slow_window_);
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
    const std::vector<Bar>& bars,
    const FeatureFrame&,
    const PortfolioSnapshot&,
    const RegimeState& regime) {
    std::vector<Signal> signals;
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
            state.signal_ema = 0.0;
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

}  // namespace qt
