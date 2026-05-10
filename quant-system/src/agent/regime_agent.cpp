#include "qt/agent/meta_agent.hpp"

#include <algorithm>
#include <cmath>
#include <numeric>
#include <random>

namespace qt::agent {

namespace {

// --- Helpers ------------------------------------------------------
double feature_or(const FeatureFrame& f, const std::string& key, double fallback) {
    auto it = f.find(key);
    if (it != f.end()) return it->second;
    // 若 "market.xxx" 未找到，尝试 bare key "xxx"
    if (key.starts_with("market.")) {
        it = f.find(key.substr(7));
        if (it != f.end()) return it->second;
    }
    return fallback;
}

// Student-t log-pdf (unnormalized, for softmax)
// log p(x | μ, σ², ν) ∝ -(ν+1)/2 * log(1 + (x-μ)² / (ν σ²)) - 0.5*log(σ²)
double student_t_log_prob(double x, double mean, double var, double nu) {
    double sigma2 = std::max(var, 1e-6);
    double z = (x - mean) * (x - mean) / (nu * sigma2);
    return -0.5 * (nu + 1.0) * std::log1p(z) - 0.5 * std::log(sigma2);
}

// 多元 Student-t log-pdf (含协方差/相关性)
// Σ = block-diagonal: dim0-dim1 有相关性, dim2+ 为对角独立
// d=1: 单变量 Student-t
// d>=2: 2x2 相关块 + 对角独立项
double multi_student_t_log_prob(const std::vector<double>& x,
                                 const std::vector<double>& mean,
                                 const std::vector<double>& var,
                                 double corr,
                                 double nu) {
    size_t d = x.size();
    if (d == 0 || d > 4) return -1e9;

    if (d == 1) {
        return student_t_log_prob(x[0], mean[0], var[0], nu);
    }

    // ---- dim0-dim1: 2x2 相关协方差块 ----
    double v0 = std::max(var[0], 1e-6);
    double v1 = std::max(var[1], 1e-6);
    double r = std::clamp(corr, -0.99, 0.99);
    double cov01 = r * std::sqrt(v0 * v1);

    double det = v0 * v1 - cov01 * cov01;
    if (det < 1e-12) det = 1e-12;

    double inv00 = v1 / det, inv01 = -cov01 / det;
    double inv11 = v0 / det;

    double diff0 = x[0] - mean[0];
    double diff1 = x[1] - mean[1];
    double mahal = diff0 * diff0 * inv00 + 2.0 * diff0 * diff1 * inv01 + diff1 * diff1 * inv11;

    // ---- dim2+: 对角独立项 ----
    double log_det = std::log(det);
    for (size_t i = 2; i < d; ++i) {
        double vi = std::max(var[i], 1e-6);
        double diff = x[i] - mean[i];
        mahal += diff * diff / vi;      // (x_i - μ_i)² / σ_i²
        log_det += std::log(vi);         // det *= σ_i²
    }

    double dim_d = static_cast<double>(d);
    return -0.5 * (nu + dim_d) * std::log1p(mahal / nu) - 0.5 * log_det;
}

// Extract observation vector from features
std::vector<double> extract_obs(const FeatureFrame& features, int dim) {
    std::vector<double> obs(dim, 0.0);
    // 特征标准化: 统一量纲，避免大方差维度主导似然
    obs[0] = feature_or(features, "market.realized_vol_20d", 0.15) / 0.20;  // ~[0.25, 2.5]
    if (dim >= 2) {
        obs[1] = feature_or(features, "market.adx_20d", 20.0) / 25.0;       // ~[0.4, 1.6]
    }
    if (dim >= 3) {
        obs[2] = feature_or(features, "market.avg_corr_20d", 0.35) / 0.50;   // ~[0, 2.0]
    }
    if (dim >= 4) {
        obs[3] = feature_or(features, "market.ret_20d", 0.0) / 0.10;          // ~[-3.0, 3.0]
    }
    return obs;
}

// Softmax
std::vector<double> softmax(const std::vector<double>& logits) {
    std::vector<double> probs(logits.size());
    double max_l = *std::max_element(logits.begin(), logits.end());
    double sum = 0.0;
    for (size_t i = 0; i < logits.size(); ++i) {
        probs[i] = std::exp(logits[i] - max_l);
        sum += probs[i];
    }
    if (sum > 1e-12) {
        for (auto& p : probs) p /= sum;
    } else {
        double eq = 1.0 / probs.size();
        std::fill(probs.begin(), probs.end(), eq);
    }
    return probs;
}

// Entropy of a probability distribution
double entropy(const std::vector<double>& probs) {
    double h = 0.0;
    for (double p : probs) {
        if (p > 1e-12) h -= p * std::log(p);
    }
    return h;
}

// Map state index to Regime based on mean characteristics
// State 0 = low vol = MeanReverting, State 2 = high vol/trend = Trending
// State 1 = mid = Crisial/transition
Regime map_regime(int best_state, const std::vector<double>& means, int dim) {
    if (means.empty() || best_state < 0 ||
        static_cast<size_t>(best_state) >= means.size() / dim) {
        return Regime::Uncertain;
    }
    double vol_mean = means[best_state * dim];
    // R27: 结合 ADX（dim 1）做更准确的 regime 分类
    double adx_mean = dim >= 2 ? means[best_state * dim + 1] : 0.0;
    if (vol_mean > 0.30) return Regime::Crisis;
    // 高 ADX + 中等波动 = 趋势；低 ADX + 低波动 = 均值回复
    if (adx_mean > 0.40 && vol_mean > 0.12) return Regime::Trending;
    if (vol_mean > 0.18) return Regime::Trending;
    if (adx_mean > 0.50 && vol_mean > 0.08) return Regime::Trending;
    return Regime::MeanReverting;
}

}  // namespace

// ===================================================================
// RuleBasedRegimeAgent (existing, from src/agent/agents.cpp)
// ===================================================================
// Implementation is in src/agent/agents.cpp; this file adds the other two.

// ===================================================================
// HMMRegimeAgent — 高斯 HMM (简单版本, 向后兼容)
// ===================================================================
HMMRegimeAgent::HMMRegimeAgent(int states)
    : states_(states), dim_(1) {
    // 先验初始化 (打破对称性)
    means_.resize(states_);
    vars_.resize(states_, 0.01);
    trans_.resize(states_ * states_, 0.0);
    forward_.resize(states_, 1.0 / states_);

    // 均值先验: 10%, 22%, 38% vol
    double priors[] = {0.10, 0.22, 0.38};
    for (int i = 0; i < states_; ++i) {
        means_[i] = priors[i % 3] + (i >= 3 ? 0.02 * i : 0.0);
    }

    // 转移矩阵: 80% 自留, 20% 均匀分布到其他状态
    for (int i = 0; i < states_; ++i) {
        for (int j = 0; j < states_; ++j) {
            trans_[i * states_ + j] = (i == j) ? 0.80 : 0.20 / (states_ - 1);
        }
    }
}

std::string_view HMMRegimeAgent::name() const noexcept {
    return "hmm_gaussian";
}

RegimeState HMMRegimeAgent::detect_regime(const FeatureFrame& features) {
    if (obs_count_ < 10) {
        return {Regime::Uncertain, 0.10, 0.33, 0.33, 0.34,
                0.33, 0.33, 0.34, "hmm_cold"};
    }

    double vol = feature_or(features, "market.realized_vol_20d", 0.15);
    double adx = feature_or(features, "market.adx_20d", 20.0);
    double obs = dim_ >= 2 ? (vol * 0.6 + adx / 100.0 * 0.4) : vol;

    // 发射概率
    std::vector<double> log_emis(states_);
    for (int j = 0; j < states_; ++j) {
        double diff = obs - means_[j];
        double var = std::max(vars_[j], 1e-3);
        log_emis[j] = -0.5 * (std::log(2 * M_PI * var) + diff * diff / var);
    }

    // GAP-013: 前向滤波 α_t(j) ∝ b_j(o_t) × Σ_i α_{t-1}(i) × a_{ij}
    std::vector<double> alpha(states_, 0.0);
    if (obs_count_ <= 10 || forward_.empty()) {
        alpha = softmax(log_emis);
    } else {
        for (int j = 0; j < states_; ++j) {
            double sum_i = 0.0;
            for (int i = 0; i < states_; ++i) {
                sum_i += forward_[i] * trans_[i * states_ + j];
            }
            alpha[j] = std::exp(log_emis[j]) * sum_i;
        }
        double sum_a = 0.0;
        for (auto& a : alpha) sum_a += a;
        if (sum_a > 1e-12)
            for (auto& a : alpha) a /= sum_a;
        else
            std::fill(alpha.begin(), alpha.end(), 1.0 / states_);
    }
    forward_ = alpha;
    const auto& probs = forward_;

    int best = std::max_element(probs.begin(), probs.end()) - probs.begin();
    double conf = probs[best];

    Regime regime = Regime::Uncertain;
    if (means_[best] > 0.30) regime = Regime::Crisis;
    else if (means_[best] > 0.18) regime = Regime::Trending;
    else regime = Regime::MeanReverting;

    // 权重: 基于概率分配
    double tp = probs.size() >= 3 ? probs[2] : probs[0];
    double rp = probs.size() >= 1 ? probs[0] : 0.33;
    double dp = probs.size() >= 2 ? probs[1] : 0.34;
    double mw = tp, rw = rp, dw = dp;

    // 重新计算: tp = 高mean状态概率, rp = 低mean状态概率
    if (probs.size() == 3) {
        tp = probs[2]; // 高vol = 趋势
        rp = probs[0]; // 低vol = 反转
        dp = probs[1]; // 中间 = 防御
        mw = tp; rw = rp; dw = dp;
    }

    return {regime, conf, mw, rw, dw, tp, rp, dp,
             conf >= 0.50 ? "hmm_v3" : "hmm_uncertain"};
}

void HMMRegimeAgent::fit_online(const FeatureFrame& features) {
    double vol = feature_or(features, "market.realized_vol_20d", 0.15);
    double adx = feature_or(features, "market.adx_20d", 20.0);
    double obs = dim_ >= 2 ? (vol * 0.6 + adx / 100.0 * 0.4) : vol;

    // 在线 k-means: 赢家通吃
    int best = 0;
    double min_dist = std::numeric_limits<double>::max();
    for (int j = 0; j < states_; ++j) {
        double d = std::abs(obs - means_[j]);
        if (d < min_dist) { min_dist = d; best = j; }
    }

    // Robbins-Monro 增量更新
    double n = static_cast<double>(obs_count_ + 1);
    // Robbins-Monro: 学习率必须趋零才收敛
    double rho = 0.98 * std::exp(-n / 200.0) + 0.02; // 自适应学习率

    means_[best] += rho * (obs - means_[best]);
    vars_[best]  += rho * ((obs - means_[best]) * (obs - means_[best]) - vars_[best]);
    vars_[best] = std::max(vars_[best], 1e-3); // 方差地板

    obs_count_++;
    fitted_ = (obs_count_ >= 50);
}

// ===================================================================
// OnlineEMRegimeAgent — Student-t + Online EM
// ===================================================================
OnlineEMRegimeAgent::OnlineEMRegimeAgent(int states, int dim)
    : states_(states), dim_(dim) {
    int n_params = states_ * dim_;

    means_.resize(n_params, 0.0);
    vars_.resize(n_params, 0.01);
    corr_.resize(states_, 0.0);  // GAP-016: 初始零相关
    trans_.resize(states_ * states_, 0.0);
    trans_counts_.resize(states_ * states_, 0.0);
    forward_.resize(states_, 1.0 / states_);
    prev_forward_.resize(states_, 1.0 / states_);

    // 先验初始化每维均值 — 打破对称性
    // dim 0 = vol:  10%, 22%, 38%
    // dim 1 = adx:  0.30, 0.50, 0.70 (scaled)
    // dim 2 = corr: 0.25, 0.50, 0.75
    double vol_priors[]   = {0.10, 0.22, 0.38};
    double adx_priors[]   = {0.30, 0.50, 0.70};
    double corr_priors[]  = {0.25, 0.50, 0.75};
    double ret_priors[]   = {-0.02, 0.0, 0.03};

    for (int s = 0; s < states_; ++s) {
        for (int d = 0; d < dim_; ++d) {
            double val = 0.0;
            if (d == 0) val = vol_priors[s % 3];
            else if (d == 1) val = adx_priors[s % 3];
            else if (d == 2) val = corr_priors[s % 3];
            else if (d == 3) val = ret_priors[s % 3];
            // 加随机抖动 ±1.5%
            val *= 1.0 + (static_cast<double>(s * 7 + d * 13) / 100.0 - 0.05) * 0.3;
            means_[s * dim_ + d] = val;
        }
    }

    // 转移矩阵: 85% 自留
    for (int i = 0; i < states_; ++i) {
        for (int j = 0; j < states_; ++j) {
            trans_[i * states_ + j] = (i == j) ? 0.85 : 0.15 / (states_ - 1);
        }
    }

    // Student-t 自由度
    nu_ = 4.0;
}

std::string_view OnlineEMRegimeAgent::name() const noexcept {
    return "online_em_regime";
}

// ---- forward_filter (用于推断) ----
std::vector<double> OnlineEMRegimeAgent::forward_filter(
    const std::vector<double>& obs) {

    std::vector<double> alpha(states_, 0.0);
    std::vector<double> log_emis(states_);

    for (int j = 0; j < states_; ++j) {
        double* mean_j = &means_[j * dim_];
        double* var_j  = &vars_[j * dim_];
        log_emis[j] = multi_student_t_log_prob(obs,
            std::vector<double>(mean_j, mean_j + dim_),
            std::vector<double>(var_j, var_j + dim_), corr_[j], nu_);
    }

    if (obs_count_ == 0 || prev_forward_.empty()) {
        // 第一个观测: 只用发射概率
        double max_e = *std::max_element(log_emis.begin(), log_emis.end());
        double sum = 0.0;
        for (int j = 0; j < states_; ++j) {
            alpha[j] = std::exp(log_emis[j] - max_e);
            sum += alpha[j];
        }
        if (sum > 1e-12) {
            for (auto& a : alpha) a /= sum;
        } else {
            std::fill(alpha.begin(), alpha.end(), 1.0 / states_);
        }
    } else {
        // α_t(j) ∝ b_j(o_t) ⋅ Σ_i α_{t-1}(i) ⋅ a_{ij}
        for (int j = 0; j < states_; ++j) {
            double sum_i = 0.0;
            for (int i = 0; i < states_; ++i) {
                sum_i += prev_forward_[i] * trans_[i * states_ + j];
            }
            alpha[j] = std::exp(log_emis[j]) * sum_i;
        }
        double sum_a = 0.0;
        for (auto& a : alpha) sum_a += a;
        if (sum_a > 1e-12) {
            for (auto& a : alpha) a /= sum_a;
        } else {
            std::fill(alpha.begin(), alpha.end(), 1.0 / states_);
        }
    }

    return alpha;
}

// ---- online_em_step (软分配 EM, Robbins-Monro) ----
void OnlineEMRegimeAgent::online_em_step(const std::vector<double>& obs) {
    // 保存旧 forward (用于下一轮 forward_filter)
    prev_forward_ = forward_;

    // GAP-014: 计算一步前向滤波作为软 responsibilities
    // forward_resp[s] ∝ emission(s) × Σ_i prev_forward_[i] × trans[i][s]
    // 这包含马尔可夫转移先验，比裸发射 softmax 更准确
    std::vector<double> log_emis(states_);
    for (int s = 0; s < states_; ++s) {
        log_emis[s] = multi_student_t_log_prob(obs,
            std::vector<double>(&means_[s * dim_], &means_[s * dim_ + dim_]),
            std::vector<double>(&vars_[s * dim_], &vars_[s * dim_ + dim_]), corr_[s], nu_);
    }

    std::vector<double> resp(states_, 0.0);
    if (obs_count_ == 0 || prev_forward_.empty()) {
        // 第一个观测: 仅用发射概率
        double max_e = *std::max_element(log_emis.begin(), log_emis.end());
        double sum_r = 0.0;
        for (int s = 0; s < states_; ++s) {
            resp[s] = std::exp(log_emis[s] - max_e);
            sum_r += resp[s];
        }
        if (sum_r > 1e-12)
            for (int s = 0; s < states_; ++s) resp[s] /= sum_r;
        else
            std::fill(resp.begin(), resp.end(), 1.0 / states_);
    } else {
        // 后续观测: 发射概率 × 转移加权前向概率
        double sum_r = 0.0;
        for (int j = 0; j < states_; ++j) {
            double trans_weight = 0.0;
            for (int i = 0; i < states_; ++i) {
                trans_weight += prev_forward_[i] * trans_[i * states_ + j];
            }
            resp[j] = std::exp(log_emis[j]) * trans_weight;
            sum_r += resp[j];
        }
        if (sum_r > 1e-12)
            for (int s = 0; s < states_; ++s) resp[s] /= sum_r;
        else
            std::fill(resp.begin(), resp.end(), 1.0 / states_);
    }

    // 自适应学习率 ρ
    double entropy_prev = entropy(prev_forward_);
    double max_entropy = std::log(static_cast<double>(states_));
    double uncertainty = entropy_prev / max_entropy;
    double rho = 0.99 - uncertainty * 0.09;
    rho = std::clamp(rho, 0.90, 0.99);

    // M-step: Robbins-Monro 增量更新，按 responsibility 加权
    for (int s = 0; s < states_; ++s) {
        double w = resp[s];
        if (w < 0.01) continue; // 保护未分配状态的先验均值
        for (int d = 0; d < dim_; ++d) {
            int idx = s * dim_ + d;
            double old_mean = means_[idx];
            means_[idx] += rho * w * (obs[d] - old_mean);
            vars_[idx]  += rho * w * ((obs[d] - old_mean) * (obs[d] - old_mean) - vars_[idx]);
            vars_[idx] = std::max(vars_[idx], 1e-3);
        }
        // GAP-016: 在线更新相关系数 (仅 dim>=2 时)
        if (dim_ >= 2) {
            double diff0 = obs[0] - means_[s * dim_];
            double diff1 = obs[1] - means_[s * dim_ + 1];
            double s0 = std::max(vars_[s * dim_], 1e-3);
            double s1 = std::max(vars_[s * dim_ + 1], 1e-3);
            double inst_corr = diff0 * diff1 / std::sqrt(s0 * s1);
            corr_[s] += rho * w * (inst_corr - corr_[s]);
            corr_[s] = std::clamp(corr_[s], -0.99, 0.99);
        }
    }

    // 转移计数: 用 forward 概率加权 (软计数)
    if (obs_count_ > 0) {
        for (int i = 0; i < states_; ++i) {
            for (int j = 0; j < states_; ++j) {
                // resp[j] 已含转移先验，用 prev_forward_[i] 做软计数即可
                trans_counts_[i * states_ + j] += prev_forward_[i] * resp[j];
            }
        }
    }

    obs_count_++;
    trans_count_++;
    fitted_ = (obs_count_ >= 50);

    // 每 20 步更新一次转移矩阵 (EMA)
    if (trans_count_ > 0 && trans_count_ % 20 == 0) {
        std::vector<double> row_sum(states_, 1e-6);
        for (int i = 0; i < states_; ++i) {
            for (int j = 0; j < states_; ++j) {
                row_sum[i] += trans_counts_[i * states_ + j];
            }
        }
        for (int i = 0; i < states_; ++i) {
            for (int j = 0; j < states_; ++j) {
                double p = trans_counts_[i * states_ + j] / row_sum[i];
                trans_[i * states_ + j] = trans_[i * states_ + j] * 0.90 + p * 0.10;
            }
            double rsum = 0.0;
            for (int j = 0; j < states_; ++j) rsum += trans_[i * states_ + j];
            if (rsum > 1e-12) {
                for (int j = 0; j < states_; ++j) trans_[i * states_ + j] /= rsum;
            }
        }
    }
}

// ---- detect_regime (使用前向滤波信念状态) ----
RegimeState OnlineEMRegimeAgent::detect_regime(const FeatureFrame& features) {
    // 冷启动处理
    if (obs_count_ < 10) {
        return {Regime::Uncertain, 0.10, 0.33, 0.33, 0.34,
                0.33, 0.33, 0.34, "oem_cold"};
    }

    auto obs = extract_obs(features, dim_);

    // R08: 若 fit_online() 已在本周期更新过模型，跳过重复更新
    if (!fitted_this_cycle_) {
        online_em_step(obs);
        forward_ = forward_filter(obs);
    }

    // 使用 forward filter 的信念状态作为状态概率 (GAP-013)
    // forward_[s] = P(state_s | observations up to t), 包含转移先验
    const auto& probs = forward_;

    int best = std::max_element(probs.begin(), probs.end()) - probs.begin();
    double conf = probs[best];

    // 根据状态均值特征映射 Regime
    std::vector<double> vol_means(states_);
    for (int s = 0; s < states_; ++s) {
        vol_means[s] = means_[s * dim_]; // dim 0 = vol
    }
    Regime regime = map_regime(best, means_, dim_);

    // 状态概率: 按均值排序分配 T/M/D
    // 创建 (index, vol_mean) pairs
    std::vector<std::pair<int, double>> sorted;
    for (int s = 0; s < states_; ++s) {
        sorted.emplace_back(s, means_[s * dim_]);
    }
    std::sort(sorted.begin(), sorted.end(),
              [](auto& a, auto& b) { return a.second < b.second; });

    double tp = 0.0, rp = 0.0, dp = 0.0;
    if (states_ == 3) {
        int lo = sorted[0].first, mid = sorted[1].first, hi = sorted[2].first;
        rp = probs[lo];   // 低vol = 均值回复
        dp = probs[mid];  // 中等 = 防御/过渡
        tp = probs[hi];   // 高vol高adx = 趋势
    } else if (states_ == 2) {
        rp = probs[sorted[0].first];
        tp = probs[sorted[1].first];
        dp = 0.0;
    } else {
        // >3 states: 聚合
        int n = states_;
        rp = probs[sorted[0].first] + (n > 4 ? probs[sorted[1].first] * 0.5 : 0.0);
        tp = probs[sorted.back().first] + (n > 4 ? probs[sorted[n-2].first] * 0.5 : 0.0);
        dp = 1.0 - tp - rp;
    }
    // 归一化
    double sum_p = tp + rp + dp;
    if (sum_p > 1e-12) { tp /= sum_p; rp /= sum_p; dp /= sum_p; }

    // 策略权重 = 概率 (可以后续加入 Kelly/风险调整)
    double mw = tp, rw = rp, dw = dp;

    // model_version
    std::string version;
    if (obs_count_ < 10) version = "oem_cold";
    else if (obs_count_ < 30) version = "oem_warmup";
    else if (conf < 0.50) version = "oem_uncertain";
    else version = "oem_v1";

    return {regime, conf, mw, rw, dw, tp, rp, dp, version};
}

void OnlineEMRegimeAgent::fit_online(const FeatureFrame& features) {
    // R08: 每个新周期重置标记，防止同周期内 detect_regime 重复更新
    fitted_this_cycle_ = false;
    auto obs = extract_obs(features, dim_);
    online_em_step(obs);
    forward_ = forward_filter(obs);
    fitted_this_cycle_ = true;
}

}  // namespace qt::agent
