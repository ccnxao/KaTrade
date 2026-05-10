#include "qt/portfolio.hpp"

#include <algorithm>
#include <cmath>
#include <numeric>
#include <unordered_map>

namespace qt {

namespace {

double strategy_weight(const std::string& strategy_id, const RegimeState& regime) {
    if (strategy_id == "momentum" || strategy_id == "donchian_breakout" ||
        strategy_id == "ma_cross" || strategy_id == "macd_trend" ||
        strategy_id == "ema_slope_trend" || strategy_id == "keltner_breakout" ||
        strategy_id == "volume_spike_momentum") {
        return regime.momentum_weight;
    }
    if (strategy_id == "micro_scalper" || strategy_id == "spread_capture_maker" ||
        strategy_id == "order_flow_imbalance" || strategy_id == "inventory_skew_maker") {
        return std::max(0.12, (regime.momentum_weight + regime.mean_revert_weight) * 0.50);
    }
    if (strategy_id == "mean_reversion" ||
        strategy_id == "bollinger_reversion" ||
        strategy_id == "rsi_reversion" ||
        strategy_id == "zscore_reversion" ||
        strategy_id == "range_fade") {
        return regime.mean_revert_weight;
    }
    if (strategy_id == "defensive") {
        return regime.defensive_weight;
    }
    return 0.10;
}

// ---- 协方差提取工具 --------------------------------------------------
// 从 FeatureFrame 中按 "cov:INST_A:INST_B" 格式读取协方差值

CovarianceMatrix build_covariance_from_features(
    const FeatureFrame& features,
    const std::vector<std::string>& instruments) {
    int N = static_cast<int>(instruments.size());
    CovarianceMatrix cov(N, std::vector<double>(N, 0.0));

    for (int i = 0; i < N; ++i) {
        for (int j = 0; j < N; ++j) {
            std::string key = "cov:" + instruments[i] + ":" + instruments[j];
            auto it = features.find(key);
            if (it != features.end()) {
                cov[i][j] = it->second;
            } else if (i == j) {
                // 对角缺省: 使用全局 realized_vol^2
                auto vit = features.find("realized_vol_20d");
                double vol = vit != features.end() ? vit->second : 0.20;
                cov[i][j] = vol * vol;
            }
        }
    }
    return cov;
}

// 从信号计算 alpha（预期超额收益）
std::vector<double> compute_alpha(std::span<const Signal> signals,
                                   const std::vector<std::string>& instruments,
                                   const RegimeState& regime) {
    int N = static_cast<int>(instruments.size());
    std::vector<double> alpha(N, 0.0);

    for (const auto& signal : signals) {
        const auto key = instrument_key(signal.instrument);
        auto it = std::find(instruments.begin(), instruments.end(), key);
        if (it == instruments.end()) continue;
        int idx = static_cast<int>(std::distance(instruments.begin(), it));
        double w = strategy_weight(signal.strategy_id, regime);
        alpha[idx] += signal.score * signal.confidence * w;
    }

    // 年化 alpha 缩放 (假设日频信号, 252 交易日)
    for (auto& a : alpha) {
        a *= 252.0;
    }
    return alpha;
}

// 项目 w 到可行域: |w_i| <= max_single, sum(|w_i|) <= max_gross
void project_weights(std::vector<double>& w, double max_single, double max_gross) {
    int N = static_cast<int>(w.size());

    // 1. 截断单品种限制
    for (int i = 0; i < N; ++i) {
        w[i] = std::clamp(w[i], -max_single, max_single);
    }

    // 2. 缩放总暴露
    double gross = 0.0;
    for (auto wi : w) gross += std::abs(wi);
    if (gross > max_gross && gross > 1e-9) {
        double scale = max_gross / gross;
        for (auto& wi : w) wi *= scale;
    }
}

}  // namespace

// ---- 公共接口 --------------------------------------------------------

CovarianceMatrix extract_covariance(const FeatureFrame& features,
                                    const std::vector<std::string>& instruments) {
    return build_covariance_from_features(features, instruments);
}

// ---- SimplePortfolioOptimizer ----------------------------------------

SimplePortfolioOptimizer::SimplePortfolioOptimizer(double max_single_weight,
                                                   double max_gross)
    : max_single_weight_(max_single_weight), max_gross_(max_gross) {}

TargetPortfolio SimplePortfolioOptimizer::optimize(std::span<const Signal> signals,
                                                   const PortfolioSnapshot& current,
                                                   const FeatureFrame&,
                                                   const RegimeState& regime) {
    struct Accumulator {
        InstrumentId instrument;
        double score{0.0};
        std::string strategy_id;
        double max_abs_score{0.0};
    };

    std::unordered_map<std::string, Accumulator> accumulated;
    for (const auto& signal : signals) {
        const auto key = instrument_key(signal.instrument);
        auto& entry = accumulated[key];
        entry.instrument = signal.instrument;
        double weighted = signal.score * signal.confidence *
                          strategy_weight(signal.strategy_id, regime);
        entry.score += weighted;
        if (std::abs(weighted) > entry.max_abs_score) {
            entry.max_abs_score = std::abs(weighted);
            entry.strategy_id = signal.strategy_id;
        }
    }

    double total_abs_score = 0.0;
    for (const auto& [_, entry] : accumulated) {
        total_abs_score += std::abs(entry.score);
    }

    TargetPortfolio target;
    if (total_abs_score <= 1e-9) {
        return target;
    }

    for (const auto& [_, entry] : accumulated) {
        double weight = (entry.score / total_abs_score) * max_gross_;
        weight = std::clamp(weight, -max_single_weight_, max_single_weight_);
        if (std::abs(weight) < 0.01) {
            continue;
        }
        target.positions.push_back(TargetPosition{entry.instrument, weight, entry.strategy_id});
    }

    double gross = gross_exposure(target);
    if (gross > max_gross_ && gross > 0.0) {
        const double scale = max_gross_ / gross;
        for (auto& position : target.positions) {
            position.target_weight *= scale;
        }
    }

    double turnover = 0.0;
    for (const auto& position : target.positions) {
        const auto current_weight = find_weight(current, position.instrument).value_or(0.0);
        turnover += std::abs(position.target_weight - current_weight);
    }

    target.expected_turnover = turnover;
    target.expected_cost_bps = turnover * 8.0;
    target.optimizer_version = "simple_v1";
    return target;
}

// ---- MarkowitzPortfolioOptimizer (GAP-032) ---------------------------

MarkowitzPortfolioOptimizer::MarkowitzPortfolioOptimizer(
    double max_single_weight,
    double max_gross,
    double risk_aversion,
    double target_vol)
    : max_single_weight_(max_single_weight)
    , max_gross_(max_gross)
    , risk_aversion_(risk_aversion)
    , target_vol_(target_vol) {}

std::vector<double> MarkowitzPortfolioOptimizer::solve_qp(
    const std::vector<double>& alpha,
    const CovarianceMatrix& sigma,
    int max_iter) const {

    int N = static_cast<int>(alpha.size());
    if (N == 0) return {};

    // 初始化: inverse-vol weighted
    std::vector<double> w(N, 0.0);
    double total_inv_vol = 0.0;
    for (int i = 0; i < N; ++i) {
        double vol = sigma[i][i] > 0.0 ? std::sqrt(sigma[i][i]) : 0.20;
        w[i] = 1.0 / vol;
        total_inv_vol += w[i];
    }
    if (total_inv_vol > 1e-9) {
        for (auto& wi : w) wi = wi / total_inv_vol * max_gross_ * 0.5;
    }

    // 梯度投影法:
    //   目标: f(w) = w'*alpha - (lambda/2)*w'*Sigma*w
    //   梯度: grad = alpha - lambda*Sigma*w
    //   更新: w_new = project(w + step_size * grad)
    //
    //   对偶目标: 等价于最小化 (1/2)*w'*Sigma*w - (1/lambda)*w'*alpha
    //   梯度: grad = Sigma*w - alpha/lambda

    double step_size = 0.5 / std::max(1.0, risk_aversion_);

    for (int iter = 0; iter < max_iter; ++iter) {
        // 计算梯度: grad_i = (Sigma*w)_i - alpha_i/lambda
        std::vector<double> grad(N, 0.0);
        for (int i = 0; i < N; ++i) {
            double sw = 0.0;
            for (int j = 0; j < N; ++j) {
                sw += sigma[i][j] * w[j];
            }
            grad[i] = sw - alpha[i] / std::max(risk_aversion_, 1e-6);
        }

        // 梯度下降步
        std::vector<double> w_new(N);
        for (int i = 0; i < N; ++i) {
            w_new[i] = w[i] - step_size * grad[i];
        }

        // 投影到可行域
        project_weights(w_new, max_single_weight_, max_gross_);

        // 收敛检查
        double delta = 0.0;
        for (int i = 0; i < N; ++i) {
            delta += (w_new[i] - w[i]) * (w_new[i] - w[i]);
        }
        w.swap(w_new);

        if (delta < 1e-8) break;

        // 衰减步长
        step_size *= 0.95;
    }

    return w;
}

TargetPortfolio MarkowitzPortfolioOptimizer::optimize(
    std::span<const Signal> signals,
    const PortfolioSnapshot& current,
    const FeatureFrame& features,
    const RegimeState& regime) {

    TargetPortfolio target;
    if (signals.empty()) return target;

    // 1. 收集受信号影响的 instrument
    std::vector<std::string> instruments;
    std::unordered_map<std::string, InstrumentId> inst_map;
    for (const auto& sig : signals) {
        const auto key = instrument_key(sig.instrument);
        if (inst_map.find(key) == inst_map.end()) {
            instruments.push_back(key);
            inst_map[key] = sig.instrument;
        }
    }
    if (instruments.empty()) return target;

    // 2. 提取协方差矩阵
    CovarianceMatrix sigma = build_covariance_from_features(features, instruments);

    // 3. 计算 alpha (预期收益)
    std::vector<double> alpha = compute_alpha(signals, instruments, regime);

    // 4. 求解最优权重
    std::vector<double> w = solve_qp(alpha, sigma, 200);

    // 5. 波动率缩放: 使组合波动率接近 target_vol
    double port_var = 0.0;
    int N = static_cast<int>(w.size());
    for (int i = 0; i < N; ++i) {
        for (int j = 0; j < N; ++j) {
            port_var += w[i] * sigma[i][j] * w[j];
        }
    }
    if (port_var > 1e-9) {
        double port_vol = std::sqrt(port_var);
        double vol_scale = target_vol_ / std::max(port_vol, 1e-6);
        vol_scale = std::min(vol_scale, 2.0);  // 缩放上限 2x
        for (auto& wi : w) wi *= vol_scale;
        project_weights(w, max_single_weight_, max_gross_);
    }

    // 6. 构建 TargetPortfolio
    for (int i = 0; i < N; ++i) {
        if (std::abs(w[i]) < 0.005) continue;
        // 取最高分信号的 strategy_id
        std::string best_strategy;
        double best_score = -1e9;
        for (const auto& sig : signals) {
            if (instrument_key(sig.instrument) == instruments[i]) {
                double sw = sig.score * sig.confidence * strategy_weight(sig.strategy_id, regime);
                if (sw > best_score) {
                    best_score = sw;
                    best_strategy = sig.strategy_id;
                }
            }
        }
        target.positions.push_back(TargetPosition{
            inst_map[instruments[i]], w[i], best_strategy});
    }

    double turnover = 0.0;
    for (const auto& pos : target.positions) {
        double cw = find_weight(current, pos.instrument).value_or(0.0);
        turnover += std::abs(pos.target_weight - cw);
    }
    target.expected_turnover = turnover;
    target.expected_cost_bps = turnover * 8.0;
    target.optimizer_version = "markowitz_v1";
    return target;
}

// ---- RiskParityOptimizer (GAP-032) -----------------------------------

RiskParityOptimizer::RiskParityOptimizer(
    double max_single_weight,
    double max_gross,
    double target_vol)
    : max_single_weight_(max_single_weight)
    , max_gross_(max_gross)
    , target_vol_(target_vol) {}

std::vector<double> RiskParityOptimizer::solve_erc(
    const CovarianceMatrix& sigma,
    const std::vector<double>& init_weights,
    int max_iter,
    double tol) const {

    int N = static_cast<int>(init_weights.size());
    if (N == 0) return {};

    std::vector<double> w = init_weights;

    // 迭代 ERC:
    //   RC_i = w_i * (Sigma*w)_i
    //   target_rc = sum(RC_i) / N
    //   w_i^(k+1) = w_i^(k) * target_rc / RC_i^(k)
    //   然后重新归一化

    for (int iter = 0; iter < max_iter; ++iter) {
        // 计算 Sigma*w
        std::vector<double> sw(N, 0.0);
        for (int i = 0; i < N; ++i) {
            for (int j = 0; j < N; ++j) {
                sw[i] += sigma[i][j] * w[j];
            }
        }

        // 计算风险贡献
        std::vector<double> rc(N, 0.0);
        double total_rc = 0.0;
        for (int i = 0; i < N; ++i) {
            rc[i] = w[i] * sw[i];
            if (rc[i] < 0.0) rc[i] = 0.0;  // 负贡献截断
            total_rc += rc[i];
        }

        double target_rc = total_rc / N;
        if (target_rc < 1e-12) break;

        // 更新权重
        double max_change = 0.0;
        for (int i = 0; i < N; ++i) {
            double new_w = w[i] * target_rc / std::max(rc[i], 1e-12);
            max_change = std::max(max_change, std::abs(new_w - w[i]));
            w[i] = new_w;
        }

        // 归一化到 max_gross
        double sum_w = 0.0;
        for (auto wi : w) sum_w += std::abs(wi);
        if (sum_w > 1e-9) {
            for (auto& wi : w) wi = wi * max_gross_ / sum_w;
        }

        if (max_change < tol) break;
    }

    // 截断单品种限制
    for (auto& wi : w) {
        wi = std::clamp(wi, -max_single_weight_, max_single_weight_);
    }

    return w;
}

TargetPortfolio RiskParityOptimizer::optimize(
    std::span<const Signal> signals,
    const PortfolioSnapshot& current,
    const FeatureFrame& features,
    const RegimeState& regime) {

    TargetPortfolio target;
    if (signals.empty()) return target;

    // 1. 收集 instrument
    std::vector<std::string> instruments;
    std::unordered_map<std::string, InstrumentId> inst_map;
    for (const auto& sig : signals) {
        const auto key = instrument_key(sig.instrument);
        if (inst_map.find(key) == inst_map.end()) {
            instruments.push_back(key);
            inst_map[key] = sig.instrument;
        }
    }
    if (instruments.empty()) return target;

    // 2. 提取协方差矩阵
    CovarianceMatrix sigma = build_covariance_from_features(features, instruments);

    // 3. 初始权重: 信号方向 + inverse-vol
    std::vector<double> init_w(instruments.size(), 0.0);
    double total_iv = 0.0;
    for (size_t i = 0; i < instruments.size(); ++i) {
        double vol = sigma[i][i] > 0.0 ? std::sqrt(std::max(sigma[i][i], 1e-6)) : 0.20;
        init_w[i] = 1.0 / vol;
        total_iv += init_w[i];
    }
    if (total_iv > 1e-9) {
        for (auto& wi : init_w) wi = wi / total_iv * max_gross_ * 0.5;
    }

    // 用信号方向修正初始权重符号
    for (size_t i = 0; i < instruments.size(); ++i) {
        double signal_score = 0.0;
        for (const auto& sig : signals) {
            if (instrument_key(sig.instrument) == instruments[i]) {
                signal_score += sig.score * sig.confidence *
                                strategy_weight(sig.strategy_id, regime);
            }
        }
        if (signal_score < 0.0) init_w[i] = -std::abs(init_w[i]);
        else init_w[i] = std::abs(init_w[i]);
    }

    // 4. ERC 求解
    std::vector<double> w = solve_erc(sigma, init_w, 100, 1e-6);

    // 5. 波动率缩放
    double port_var = 0.0;
    int N = static_cast<int>(w.size());
    for (int i = 0; i < N; ++i) {
        for (int j = 0; j < N; ++j) {
            port_var += w[i] * sigma[i][j] * w[j];
        }
    }
    if (port_var > 1e-9) {
        double port_vol = std::sqrt(port_var);
        double vol_scale = target_vol_ / std::max(port_vol, 1e-6);
        vol_scale = std::min(vol_scale, 2.0);
        for (auto& wi : w) wi *= vol_scale;
        project_weights(w, max_single_weight_, max_gross_);
    }

    // 6. 构建 TargetPortfolio
    for (int i = 0; i < N; ++i) {
        if (std::abs(w[i]) < 0.005) continue;
        std::string best_strategy;
        double best_score = -1e9;
        for (const auto& sig : signals) {
            if (instrument_key(sig.instrument) == instruments[i]) {
                double sw = sig.score * sig.confidence * strategy_weight(sig.strategy_id, regime);
                if (sw > best_score) {
                    best_score = sw;
                    best_strategy = sig.strategy_id;
                }
            }
        }
        target.positions.push_back(TargetPosition{
            inst_map[instruments[i]], w[i], best_strategy});
    }

    double turnover = 0.0;
    for (const auto& pos : target.positions) {
        double cw = find_weight(current, pos.instrument).value_or(0.0);
        turnover += std::abs(pos.target_weight - cw);
    }
    target.expected_turnover = turnover;
    target.expected_cost_bps = turnover * 8.0;
    target.optimizer_version = "risk_parity_v1";
    return target;
}

}  // namespace qt
