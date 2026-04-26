#include "qt/agents.hpp"

#include <algorithm>
#include <cmath>
#include <numeric>

namespace qt {

namespace {

double clamp_score(double value) {
    return std::clamp(value, -1.0, 1.0);
}

double mean(const std::vector<double>& values) {
    if (values.empty()) {
        return 0.0;
    }
    return std::accumulate(values.begin(), values.end(), 0.0) /
           static_cast<double>(values.size());
}

double stddev(const std::vector<double>& values, double average) {
    if (values.size() < 2) {
        return 0.0;
    }
    double variance = 0.0;
    for (const double value : values) {
        const double diff = value - average;
        variance += diff * diff;
    }
    variance /= static_cast<double>(values.size());
    return std::sqrt(variance);
}

std::vector<double> tail_values(const std::vector<double>& values,
                                std::size_t window) {
    if (values.empty()) {
        return {};
    }
    const std::size_t count = std::min(window, values.size());
    return {values.end() - static_cast<std::ptrdiff_t>(count), values.end()};
}

void trim_history(std::vector<double>& history, std::size_t max_size) {
    if (history.size() <= max_size) {
        return;
    }
    history.erase(history.begin(),
                  history.begin() +
                      static_cast<std::ptrdiff_t>(history.size() - max_size));
}

double rsi(const std::vector<double>& closes, std::size_t window) {
    if (closes.size() <= window) {
        return 50.0;
    }
    double gains = 0.0;
    double losses = 0.0;
    const auto start = closes.end() - static_cast<std::ptrdiff_t>(window + 1);
    for (auto it = start + 1; it != closes.end(); ++it) {
        const double diff = *it - *(it - 1);
        if (diff >= 0.0) {
            gains += diff;
        } else {
            losses += -diff;
        }
    }
    if (losses <= 1e-9) {
        return 100.0;
    }
    const double rs = gains / losses;
    return 100.0 - 100.0 / (1.0 + rs);
}

}  // namespace

BollingerReversionAgent::BollingerReversionAgent(std::size_t window,
                                                 double band_width)
    : window_(std::max<std::size_t>(3, window)), band_width_(band_width) {}

std::string_view BollingerReversionAgent::name() const noexcept {
    return "bollinger_reversion";
}

std::vector<Signal> BollingerReversionAgent::generate_signals(
    const std::vector<Bar>& bars,
    const FeatureFrame&,
    const PortfolioSnapshot&,
    const RegimeState& regime) {
    std::vector<Signal> signals;
    const double confidence =
        regime.regime == Regime::MeanReverting ? 0.78
        : regime.regime == Regime::Trending    ? 0.42
                                               : 0.58;

    for (const auto& bar : bars) {
        const auto key = instrument_key(bar.instrument);
        auto& closes = closes_[key];
        closes.push_back(bar.close);
        trim_history(closes, window_);

        if (closes.size() < window_) {
            continue;
        }

        // 布林带策略把价格偏离均值的 z-score 转成反向信号。
        // 高于上轨倾向卖出，低于下轨倾向买入，适合震荡市。
        const auto window_values = tail_values(closes, window_);
        const double average = mean(window_values);
        const double sigma = std::max(stddev(window_values, average), 1e-9);
        const double z_score = (bar.close - average) / sigma;
        if (std::abs(z_score) < band_width_) {
            continue;
        }
        signals.push_back(Signal{std::string{name()},
                                 bar.instrument,
                                 clamp_score(-z_score / 3.0),
                                 confidence});
    }
    return signals;
}

RsiReversionAgent::RsiReversionAgent(std::size_t window,
                                     double oversold,
                                     double overbought)
    : window_(std::max<std::size_t>(2, window)),
      oversold_(std::clamp(oversold, 1.0, 49.0)),
      overbought_(std::clamp(overbought, 51.0, 99.0)) {}

std::string_view RsiReversionAgent::name() const noexcept {
    return "rsi_reversion";
}

std::vector<Signal> RsiReversionAgent::generate_signals(
    const std::vector<Bar>& bars,
    const FeatureFrame&,
    const PortfolioSnapshot&,
    const RegimeState& regime) {
    std::vector<Signal> signals;
    const double confidence =
        regime.regime == Regime::MeanReverting ? 0.76
        : regime.regime == Regime::Trending    ? 0.38
                                               : 0.56;

    for (const auto& bar : bars) {
        const auto key = instrument_key(bar.instrument);
        auto& closes = closes_[key];
        closes.push_back(bar.close);
        trim_history(closes, window_ + 1);

        if (closes.size() <= window_) {
            continue;
        }

        // RSI 只使用截至当前 bar 的收盘序列。
        // 高于 overbought 做短期回落预期，低于 oversold 做短期反弹预期。
        const double value = rsi(closes, window_);
        if (value < oversold_) {
            const double distance = (oversold_ - value) / oversold_;
            signals.push_back(Signal{std::string{name()},
                                     bar.instrument,
                                     clamp_score(0.25 + distance),
                                     confidence});
        } else if (value > overbought_) {
            const double distance = (value - overbought_) / (100.0 - overbought_);
            signals.push_back(Signal{std::string{name()},
                                     bar.instrument,
                                     clamp_score(-0.25 - distance),
                                     confidence});
        }
    }
    return signals;
}

std::string_view RangeFadeAgent::name() const noexcept {
    return "range_fade";
}

std::vector<Signal> RangeFadeAgent::generate_signals(const std::vector<Bar>& bars,
                                                     const FeatureFrame&,
                                                     const PortfolioSnapshot&,
                                                     const RegimeState& regime) {
    std::vector<Signal> signals;
    const double confidence =
        regime.regime == Regime::MeanReverting ? 0.70
        : regime.regime == Regime::Trending    ? 0.35
                                               : 0.55;

    for (const auto& bar : bars) {
        const double range = std::max(bar.high - bar.low, 1e-9);
        const double close_location = (bar.close - bar.low) / range;

        // 当收盘贴近日内区间底部时做反弹预期，贴近顶部时做回落预期。
        // 这是简单的区间 fade，不试图预测趋势延续。
        if (close_location < 0.22) {
            signals.push_back(Signal{std::string{name()},
                                     bar.instrument,
                                     clamp_score((0.35 - close_location) * 1.7),
                                     confidence});
        } else if (close_location > 0.78) {
            signals.push_back(Signal{std::string{name()},
                                     bar.instrument,
                                     clamp_score(-(close_location - 0.65) * 1.7),
                                     confidence});
        }
    }
    return signals;
}

}  // namespace qt
