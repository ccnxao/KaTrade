#include "qt/agents.hpp"

#include <algorithm>
#include <cmath>

namespace qt {

namespace {

double clamp_score(double value) {
    return std::clamp(value, -1.0, 1.0);
}

double bar_return(const Bar& bar) {
    if (bar.open <= 0.0) return 0.0;
    return (bar.close - bar.open) / bar.open;
}

}  // namespace

BollingerReversionAgent::BollingerReversionAgent(std::size_t window,
                                                 double band_width)
    : window_(std::max<std::size_t>(3, window)), band_width_(band_width) {}

std::string_view BollingerReversionAgent::name() const noexcept {
    return "bollinger_reversion";
}

std::vector<Signal> BollingerReversionAgent::generate_signals(
    const FeatureFrame&,
    const PortfolioSnapshot&,
    const RegimeState& regime) {
    std::vector<Signal> signals;
    const auto bars = drain_pending_bars();
    const double confidence =
        regime.regime == Regime::MeanReverting ? 0.78
        : regime.regime == Regime::Trending    ? 0.42
                                               : 0.58;

    for (const auto& bar : bars) {
        const auto key = instrument_key(bar.instrument);
        auto& state = state_[key];
        state.closes.push_back(bar.close);
        state.sum += bar.close;
        state.square_sum += bar.close * bar.close;
        if (state.closes.size() > window_) {
            const double old = state.closes.front();
            state.closes.pop_front();
            state.sum -= old;
            state.square_sum -= old * old;
        }

        if (state.closes.size() < window_) {
            continue;
        }

        // 布林带策略把价格偏离均值的 z-score 转成反向信号。
        // 高于上轨倾向卖出，低于下轨倾向买入，适合震荡市。
        const double n_d = static_cast<double>(window_);
        const double average = state.sum / n_d;
        const double variance =
            std::max(state.square_sum / n_d - average * average, 0.0) *
            n_d / (n_d - 1.0);  // 样本方差 (N/(N-1) 修正)
        const double sigma = std::max(std::sqrt(variance), 1e-9);
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
    const FeatureFrame&,
    const PortfolioSnapshot&,
    const RegimeState& regime) {
    std::vector<Signal> signals;
    const auto bars = drain_pending_bars();
    const double confidence =
        regime.regime == Regime::MeanReverting ? 0.76
        : regime.regime == Regime::Trending    ? 0.38
                                               : 0.56;

    for (const auto& bar : bars) {
        const auto key = instrument_key(bar.instrument);
        auto& state = state_[key];
        if (!state.has_previous) {
            state.has_previous = true;
            state.previous_close = bar.close;
            continue;
        }

        const double diff = bar.close - state.previous_close;
        state.previous_close = bar.close;
        const double gain = diff >= 0.0 ? diff : 0.0;
        const double loss = diff < 0.0 ? -diff : 0.0;
        state.gains.push_back(gain);
        state.losses.push_back(loss);
        state.gain_sum += gain;
        state.loss_sum += loss;
        if (state.gains.size() > window_) {
            state.gain_sum -= state.gains.front();
            state.loss_sum -= state.losses.front();
            state.gains.pop_front();
            state.losses.pop_front();
        }

        if (state.gains.size() < window_) {
            continue;
        }

        // RSI 只使用截至当前 bar 的收盘序列。
        // 高于 overbought 做短期回落预期，低于 oversold 做短期反弹预期。
        const double value =
            state.loss_sum <= 1e-9
                ? 100.0
                : 100.0 - 100.0 / (1.0 + state.gain_sum / state.loss_sum);
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

ZScoreReversionAgent::ZScoreReversionAgent(std::size_t window,
                                           double threshold)
    : window_(std::max<std::size_t>(3, window)),
      threshold_(std::clamp(threshold, 0.1, 10.0)) {}

std::string_view ZScoreReversionAgent::name() const noexcept {
    return "zscore_reversion";
}

std::vector<Signal> ZScoreReversionAgent::generate_signals(
    const FeatureFrame&,
    const PortfolioSnapshot&,
    const RegimeState& regime) {
    std::vector<Signal> signals;
    const auto bars = drain_pending_bars();
    const double confidence =
        regime.regime == Regime::MeanReverting ? 0.74
        : regime.regime == Regime::Trending    ? 0.36
                                               : 0.54;

    for (const auto& bar : bars) {
        const auto key = instrument_key(bar.instrument);
        auto& state = state_[key];
        state.closes.push_back(bar.close);
        state.sum += bar.close;
        state.square_sum += bar.close * bar.close;
        if (state.closes.size() > window_) {
            const double old = state.closes.front();
            state.closes.pop_front();
            state.sum -= old;
            state.square_sum -= old * old;
        }

        if (state.closes.size() < window_) {
            continue;
        }

        const double count = static_cast<double>(window_);
        const double average = state.sum / count;
        const double variance =
            std::max(state.square_sum / count - average * average, 0.0) *
            count / (count - 1.0);  // 样本方差 (N/(N-1) 修正)
        const double sigma = std::max(std::sqrt(variance), 1e-9);
        const double z_score = (bar.close - average) / sigma;
        if (std::abs(z_score) < threshold_) {
            continue;
        }
        signals.push_back(Signal{std::string{name()},
                                 bar.instrument,
                                 clamp_score(-z_score / 3.0),
                                 confidence});
    }
    return signals;
}

std::string_view RangeFadeAgent::name() const noexcept {
    return "range_fade";
}

std::vector<Signal> RangeFadeAgent::generate_signals(const FeatureFrame&,
                                                     const PortfolioSnapshot&,
                                                     const RegimeState& regime) {
    std::vector<Signal> signals;
    const auto bars = drain_pending_bars();
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

// ---- MicroScalperAgent: 日内微小波动剥头皮 ----
// 高实体占比 + 方向明确 → 顺势短线信号
MicroScalperAgent::MicroScalperAgent(double min_return, double min_body_ratio)
    : min_return_(std::clamp(min_return, 0.0001, 0.05)), min_body_ratio_(std::clamp(min_body_ratio, 0.05, 0.95)) {}
std::string_view MicroScalperAgent::name() const noexcept { return "micro_scalper"; }
std::vector<Signal> MicroScalperAgent::generate_signals(const FeatureFrame&,
                                                         const PortfolioSnapshot&,
                                                         const RegimeState& regime) {
    auto bars = drain_pending_bars();
    std::vector<Signal> signals;
    const bool trend_ok = regime.regime != Regime::Crisis;
    for (const auto& bar : bars) {
        double range = std::max(bar.high - bar.low, 1e-9);
        double body = std::abs(bar.close - bar.open);
        double body_ratio = body / range;
        double ret = bar_return(bar);
        if (!trend_ok || body_ratio < min_body_ratio_ || std::abs(ret) < min_return_)
            continue;
        // 顺势短线: 阳线做多, 阴线做空
        double score = clamp_score(ret / min_return_ * 0.4);
        signals.push_back(Signal{std::string{name()}, bar.instrument, score, 0.55});
    }
    return signals;
}

// ---- SpreadCaptureMakerAgent: 价差捕获/均值回复做市 ----
// 用 EMA 跟踪fair price, 偏离阈值以上时反向交易
SpreadCaptureMakerAgent::SpreadCaptureMakerAgent(double alpha, double threshold)
    : alpha_(std::clamp(alpha, 0.01, 1.0)), threshold_(std::clamp(threshold, 0.05, 5.0)) {}
std::string_view SpreadCaptureMakerAgent::name() const noexcept { return "spread_capture"; }
std::vector<Signal> SpreadCaptureMakerAgent::generate_signals(const FeatureFrame&,
                                                                const PortfolioSnapshot&,
                                                                const RegimeState& regime) {
    auto bars = drain_pending_bars();
    std::vector<Signal> signals;
    if (regime.regime == Regime::Trending) return signals; // 趋势市不做均值回复

    for (const auto& bar : bars) {
        const auto key = instrument_key(bar.instrument);
        auto& st = state_[key];
        double mid = (bar.high + bar.low) * 0.5;
        if (!st.initialized) {
            st.fair_price = mid;
            st.range_ema = bar.high - bar.low;
            st.initialized = true;
            continue;
        }
        // EMA 更新 fair price
        st.fair_price = st.fair_price * (1.0 - alpha_) + mid * alpha_;
        st.range_ema  = st.range_ema  * (1.0 - alpha_) + (bar.high - bar.low) * alpha_;

        double deviation = (bar.close - st.fair_price) / std::max(st.range_ema, 1e-9);
        if (std::abs(deviation) < threshold_) continue;

        // 价格高于fair → 卖出, 低于fair → 买入
        double score = clamp_score(-deviation / threshold_ * 0.5);
        double conf = regime.regime == Regime::MeanReverting ? 0.70 : 0.50;
        signals.push_back(Signal{std::string{name()}, bar.instrument, score, conf});
    }
    return signals;
}

// ---- OrderFlowImbalanceAgent: 量价失衡检测 ----
// 成交量相对EMA飙升 + 价格单向运动 → 主力资金入场信号
OrderFlowImbalanceAgent::OrderFlowImbalanceAgent(double volume_alpha, double imbalance_threshold)
    : volume_alpha_(std::clamp(volume_alpha, 0.01, 1.0)), imbalance_threshold_(std::clamp(imbalance_threshold, 0.05, 0.95)) {}
std::string_view OrderFlowImbalanceAgent::name() const noexcept { return "order_flow_imbalance"; }
std::vector<Signal> OrderFlowImbalanceAgent::generate_signals(const FeatureFrame&,
                                                                const PortfolioSnapshot&,
                                                                const RegimeState&) {
    auto bars = drain_pending_bars();
    std::vector<Signal> signals;

    for (const auto& bar : bars) {
        const auto key = instrument_key(bar.instrument);
        auto& st = state_[key];
        if (!st.initialized) {
            st.volume_ema = bar.volume;
            st.initialized = true;
            continue;
        }
        st.volume_ema = st.volume_ema * (1.0 - volume_alpha_) + bar.volume * volume_alpha_;

        double vol_ratio = bar.volume / std::max(st.volume_ema, 1e-9);
        if (vol_ratio < 1.0 + imbalance_threshold_) continue;

        // 成交量异常放大: 价格方向即资金方向
        double ret = bar_return(bar);
        double score = clamp_score(ret * vol_ratio * 0.3);
        double conf = std::min(0.75, 0.45 + (vol_ratio - 1.0) * 0.3);
        signals.push_back(Signal{std::string{name()}, bar.instrument, score, conf});
    }
    return signals;
}

// ---- InventorySkewMakerAgent: 库存感知做市偏斜 ----
// 唯一使用 PortfolioSnapshot 的策略: 根据当前持仓偏斜信号方向
InventorySkewMakerAgent::InventorySkewMakerAgent(double neutral_band)
    : neutral_band_(std::clamp(neutral_band, 0.005, 0.30)) {}
std::string_view InventorySkewMakerAgent::name() const noexcept { return "inventory_skew"; }
std::vector<Signal> InventorySkewMakerAgent::generate_signals(const FeatureFrame&,
                                                                const PortfolioSnapshot& portfolio,
                                                                const RegimeState& regime) {
    auto bars = drain_pending_bars();
    std::vector<Signal> signals;
    if (regime.regime == Regime::Crisis) return signals;

    for (const auto& bar : bars) {
        double current_weight = find_weight(portfolio, bar.instrument).value_or(0.0);
        double abs_w = std::abs(current_weight);
        if (abs_w < neutral_band_) continue; // 仓位在 neutral band 内, 无需调整

        // 仓位偏向一侧时, 向中性方向产生信号
        // 多头过重 → 卖出, 空头过重 → 买入
        double skew = -current_weight / std::max(neutral_band_, 0.01);
        double score = clamp_score(skew * 0.5);
        double conf = 0.60 + std::min(abs_w, 0.15) * 2.0;
        signals.push_back(Signal{std::string{name()}, bar.instrument, score, conf});
    }
    return signals;
}

}  // namespace qt
