#include "qt/agent/llm_feature_agent.hpp"

#include <algorithm>
#include <cmath>
#include <deque>
#include <numeric>
#include <sstream>

namespace qt::agent {

// ---- 内部工具 --------------------------------------------------------
//
// LLMFeatureAgent 通过分析多维特征的交互关系生成信号。
// 模拟 LLM 的 in-context learning: 历史特征窗口 = context window
// ----------------------------------------------------------------------

namespace {

constexpr std::size_t MAX_HISTORY = 200;

// 预定义的特征交互规则集（模拟 LLM 从训练数据学到的模式）
std::vector<FeatureRule> default_rules() {
    return {
        {"adx_20d",         "ret_20d",         0.6, 0.4, FeatureRule::BothHigh},
        {"realized_vol_20d","ret_20d",         0.4, 0.6, FeatureRule::Divergence},
        {"realized_vol_20d","adx_20d",         0.3, 0.7, FeatureRule::Convergence},
        {"avg_corr_20d",    "ret_20d",         0.5, 0.5, FeatureRule::BothHigh},
        {"volume",          "realized_vol_20d",0.4, 0.6, FeatureRule::BothHigh},
    };
}

double safe_get(const FeatureFrame& features, const std::string& key,
                double fallback = 0.0) {
    auto it = features.find(key);
    if (it != features.end()) return it->second;
    // 若 bare key 未找到，尝试 "market.xxx" 前缀版本
    if (!key.starts_with("market.")) {
        it = features.find("market." + key);
        if (it != features.end()) return it->second;
    }
    return fallback;
}

double rolling_zscore(const std::deque<double>& history, double current) {
    if (history.size() < 4) return 0.0;
    double sum = 0.0, sq = 0.0;
    for (auto v : history) {
        sum += v;
        sq += v * v;
    }
    double mean = sum / history.size();
    // R28: 样本方差 n-1
    double n_d = static_cast<double>(history.size());
    double var = (sq - sum * sum / n_d) / (n_d - 1);
    if (var < 1e-9) return 0.0;
    return (current - mean) / std::sqrt(var);
}

double trend_slope(const std::deque<double>& history) {
    if (history.size() < 3) return 0.0;
    int n = static_cast<int>(history.size());
    double sum_x = 0.0, sum_y = 0.0, sum_xy = 0.0, sum_xx = 0.0;
    int i = 0;
    for (auto v : history) {
        sum_x += i;
        sum_y += v;
        sum_xy += i * v;
        sum_xx += i * i;
        ++i;
    }
    double denom = n * sum_xx - sum_x * sum_x;
    if (std::abs(denom) < 1e-9) return 0.0;
    return (n * sum_xy - sum_x * sum_y) / denom;
}

}  // namespace

// ---- LLMFeatureAgent -------------------------------------------------

std::string_view LLMFeatureAgent::name() const noexcept {
    return "llm_feature";
}

void LLMFeatureAgent::on_bar(const Bar& bar) {
    bar_history_.push_back(bar);
    while (bar_history_.size() > MAX_HISTORY) {
        bar_history_.pop_front();
    }
}

void LLMFeatureAgent::reset() {
    bar_history_.clear();
    feature_history_.clear();
    narrative_buffer_.clear();
}

std::vector<Signal> LLMFeatureAgent::generate_signals(
    const FeatureFrame& features,
    const PortfolioSnapshot& portfolio,
    const RegimeState& regime) {

    (void)portfolio;

    std::vector<Signal> signals;

    update_feature_history(features);
    auto narrative = generate_narrative(features, regime);

    auto rules = default_rules();
    for (const auto& rule : rules) {
        auto signal = evaluate_rule(rule, features, regime);
        if (signal && std::abs(signal->score) > 0.05) {
            signals.push_back(std::move(*signal));
        }
    }

    auto anomaly_signals = detect_anomalies(features, regime);
    for (auto& sig : anomaly_signals) {
        if (std::abs(sig.score) > 0.03) {
            signals.push_back(std::move(sig));
        }
    }

    std::unordered_map<std::string, Signal> merged;
    std::unordered_map<std::string, int> merge_counts;  // 跟踪合并次数
    for (auto& sig : signals) {
        auto key = instrument_key(sig.instrument);
        auto it = merged.find(key);
        if (it == merged.end()) {
            merged[key] = sig;
            merge_counts[key] = 1;
        } else {
            // 递增平均: 用真实合并次数，最后信号不会主导
            int n = merge_counts[key] + 1;
            it->second.score = (it->second.score * (n - 1) + sig.score) / n;
            it->second.confidence = std::max(it->second.confidence, sig.confidence);
            merge_counts[key] = n;
        }
    }

    signals.clear();
    for (auto& [_, sig] : merged) {
        signals.push_back(std::move(sig));
    }

    return signals;
}

void LLMFeatureAgent::update_feature_history(const FeatureFrame& features) {
    feature_history_.push_back(features);
    while (feature_history_.size() > MAX_HISTORY) {
        feature_history_.pop_front();
    }
}

std::string LLMFeatureAgent::generate_narrative(
    const FeatureFrame& features,
    const RegimeState& regime) {

    (void)regime;

    std::ostringstream narrative;
    double vol = safe_get(features, "realized_vol_20d", 0.15);
    double ret = safe_get(features, "ret_20d", 0.0);
    double adx = safe_get(features, "adx_20d", 20.0);
    double corr = safe_get(features, "avg_corr_20d", 0.30);

    if (vol > 0.40) narrative << "extremely_high_volatility ";
    else if (vol > 0.25) narrative << "elevated_volatility ";
    else if (vol < 0.10) narrative << "low_volatility ";
    else narrative << "normal_volatility ";

    if (adx > 30.0) narrative << "strong_trend ";
    else if (adx > 20.0) narrative << "moderate_trend ";
    else narrative << "ranging ";

    if (ret > 0.05) narrative << "bullish ";
    else if (ret < -0.05) narrative << "bearish ";
    else narrative << "neutral ";

    if (corr > 0.70) narrative << "high_correlation";
    else if (corr > 0.40) narrative << "moderate_correlation";
    else narrative << "low_correlation";

    narrative_buffer_.push_back(narrative.str());
    while (narrative_buffer_.size() > 50) {
        narrative_buffer_.pop_front();
    }

    return narrative.str();
}

std::optional<Signal> LLMFeatureAgent::evaluate_rule(
    const FeatureRule& rule,
    const FeatureFrame& features,
    const RegimeState& regime) {

    double pv = safe_get(features, rule.primary, 0.0);
    double sv = safe_get(features, rule.secondary, 0.0);

    std::deque<double> p_hist, s_hist;
    for (const auto& hist : feature_history_) {
        p_hist.push_back(safe_get(hist, rule.primary, 0.0));
        s_hist.push_back(safe_get(hist, rule.secondary, 0.0));
    }

    double pz = rolling_zscore(p_hist, pv);
    double sz = rolling_zscore(s_hist, sv);

    double score = 0.0;
    double confidence = 0.0;

    switch (rule.type) {
    case FeatureRule::BothHigh: {
        double combo = (pz + sz) * 0.5;
        score = std::clamp(combo, -2.0, 2.0) * 0.5;
        confidence = std::min(std::abs(pz), std::abs(sz)) / 2.0;
        break;
    }
    case FeatureRule::BothLow: {
        double combo = -(pz + sz) * 0.5;
        score = std::clamp(combo, -2.0, 2.0) * 0.3;
        confidence = std::min(std::abs(pz), std::abs(sz)) / 3.0;
        break;
    }
    case FeatureRule::Divergence: {
        double divergence = pz - sz;
        score = std::clamp(divergence, -2.0, 2.0) * 0.4;
        confidence = std::abs(divergence) / 3.0;
        break;
    }
    case FeatureRule::Convergence: {
        double dist = std::sqrt(pz * pz + sz * sz);
        if (dist < 0.5) {
            score = (pz + sz) * 0.3;
            confidence = 1.0 - std::min(dist, 1.0);
        }
        break;
    }
    }

    double regime_adj = regime.momentum_weight * 0.5 + regime.mean_revert_weight * 0.5;
    score *= (0.5 + regime_adj);
    score *= rule.primary_weight * 0.6 + rule.secondary_weight * 0.4;

    if (std::abs(score) < 0.02) return std::nullopt;

    Signal sig;
    sig.strategy_id = "llm_feature";
    // R30: 从 bar_history_ 获取实际交易品种
    if (!bar_history_.empty()) {
        sig.instrument = bar_history_.back().instrument;
    } else {
        sig.instrument = InstrumentId{"BTC-USDT-SWAP", "OKX"};
    }
    sig.score = std::clamp(score, -1.0, 1.0);
    sig.confidence = std::clamp(confidence, 0.05, 1.0);

    return sig;
}

std::vector<Signal> LLMFeatureAgent::detect_anomalies(
    const FeatureFrame& features,
    const RegimeState& regime) {

    (void)regime;

    std::vector<Signal> signals;
    if (feature_history_.size() < 10) return signals;

    double vol = safe_get(features, "realized_vol_20d", 0.15);
    double ret = safe_get(features, "ret_20d", 0.0);

    std::deque<double> vol_hist;
    for (const auto& hist : feature_history_) {
        vol_hist.push_back(safe_get(hist, "realized_vol_20d", 0.15));
    }
    double vol_z = rolling_zscore(vol_hist, vol);

    if (vol_z > 3.0) {
        Signal sig;
        sig.strategy_id = "llm_feature";
        // R30: 动态品种
        sig.instrument = bar_history_.empty() ? InstrumentId{"BTC-USDT-SWAP", "OKX"} : bar_history_.back().instrument;
        sig.score = -0.5;
        sig.confidence = std::min(vol_z / 5.0, 1.0);
        signals.push_back(sig);
    }

    std::deque<double> ret_hist;
    for (const auto& hist : feature_history_) {
        ret_hist.push_back(safe_get(hist, "ret_20d", 0.0));
    }
    double ret_z = rolling_zscore(ret_hist, ret);
    double ret_slope = trend_slope(ret_hist);

    if (std::abs(ret_z) > 2.5 && std::abs(ret_slope) > 0.001) {
        Signal sig;
        sig.strategy_id = "llm_feature";
        // R30: 动态品种
        sig.instrument = bar_history_.empty() ? InstrumentId{"BTC-USDT-SWAP", "OKX"} : bar_history_.back().instrument;
        sig.score = std::clamp(ret_z * 0.3, -1.0, 1.0);
        sig.confidence = std::min(std::abs(ret_z) / 4.0, 1.0);
        signals.push_back(sig);
    }

    return signals;
}

}  // namespace qt::agent
