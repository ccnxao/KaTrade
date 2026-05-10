#include "qt/data/feature_store.hpp"

#include <algorithm>
#include <cmath>
#include <map>
#include <numeric>

namespace qt::data {

namespace {

constexpr std::size_t MIN_ADX_BARS = 40;

// --- Wilder's ADX -------------------------------------------------
// 标准 Wilder ADX:
//   1. True Range TR = max(H-L, |H-C_prev|, |L-C_prev|)
//   2. +DM = H - H_prev if H-H_prev > L_prev-L and H-H_prev > 0 else 0
//      -DM = L_prev - L if L_prev-L > H-H_prev and L_prev-L > 0 else 0
//   3. 平滑 TR14, +DM14, -DM14 (Wilder smoothing, alpha=1/14)
//   4. +DI = 100 * +DM14/TR14, -DI = 100 * -DM14/TR14
//   5. DX  = 100 * |+DI - -DI| / (+DI + -DI)
//   6. ADX = Wilder smooth of DX (alpha=1/14)
// ------------------------------------------------------------------
double compute_adx(const std::vector<Bar>& bars) {
    if (bars.size() < MIN_ADX_BARS) return 20.0;

    const double alpha = 1.0 / 14.0;
    double tr14 = 0.0, pdm14 = 0.0, ndm14 = 0.0, adx_val = 0.0;
    double prev_close = bars[0].close;
    double prev_high  = bars[0].high;
    double prev_low   = bars[0].low;

    for (std::size_t i = 1; i < bars.size(); ++i) {
        double h = bars[i].high, l = bars[i].low, c = bars[i].close;

        double tr = std::max({h - l, std::abs(h - prev_close), std::abs(l - prev_close)});
        double up = h - prev_high, down = prev_low - l;
        double pdm = (up > down && up > 0.0) ? up : 0.0;
        double ndm = (down > up && down > 0.0) ? down : 0.0;

        if (i < 14) {
            tr14  += tr;
            pdm14 += pdm;
            ndm14 += ndm;
        } else {
            tr14  = tr14  * (1.0 - alpha) + tr  * alpha;
            pdm14 = pdm14 * (1.0 - alpha) + pdm * alpha;
            ndm14 = ndm14 * (1.0 - alpha) + ndm * alpha;

            double pdi = (tr14 > 1e-9) ? 100.0 * pdm14 / tr14 : 0.0;
            double ndi = (tr14 > 1e-9) ? 100.0 * ndm14 / tr14 : 0.0;
            double dx  = (pdi + ndi > 1e-9) ? 100.0 * std::abs(pdi - ndi) / (pdi + ndi) : 0.0;

            if (i == 14) {
                adx_val = dx;
            } else {
                adx_val = adx_val * (1.0 - alpha) + dx * alpha;
            }
        }

        prev_close = c;
        prev_high  = h;
        prev_low   = l;
    }

    return (bars.size() >= MIN_ADX_BARS) ? adx_val : 20.0;
}

// --- Realized vol (annualized) -----------------------------------
// 根据相邻 bar 的时间间隔估计年化因子
// e.g. 1m bar → 362880 periods/year, 1d bar → 252 periods/year
static double annualization_factor(const std::vector<Bar>& bars) {
    if (bars.size() < 2) return std::sqrt(252.0);
    // 采样前 10 个 bar 的时间间隔（毫秒）取中位数
    std::vector<std::int64_t> diffs;
    for (size_t i = 1; i < std::min(bars.size(), size_t(11)); ++i) {
        auto d = bars[i].timestamp - bars[i - 1].timestamp;
        if (d > 0) diffs.push_back(d);
    }
    if (diffs.empty()) return std::sqrt(252.0);
    std::sort(diffs.begin(), diffs.end());
    auto median_ms = diffs[diffs.size() / 2];
    double periods_per_year = (365.25 * 24 * 3600 * 1000.0) / static_cast<double>(median_ms);
    return std::sqrt(periods_per_year);
}

double compute_realized_vol(const std::vector<Bar>& bars, std::size_t window) {
    if (bars.size() < 2) return 0.15;
    std::size_t n = std::min(window, bars.size() - 1);
    if (n < 2) return 0.15;

    double sum = 0.0;
    auto start = bars.size() - n - 1;
    for (std::size_t i = start; i < bars.size() - 1; ++i) {
        double r = std::log(bars[i + 1].close / bars[i].close);
        sum += r;
    }
    double mean = sum / n;
    // R24: 两遍算法，避免 catastrophic cancellation
    double var = 0.0;
    for (std::size_t i = start; i < bars.size() - 1; ++i) {
        double r = std::log(bars[i + 1].close / bars[i].close);
        double d = r - mean;
        var += d * d;
    }
    var /= (n - 1);  // 样本方差
    double ann = annualization_factor(bars);
    return std::sqrt(var) * ann;
}

// --- Period return ------------------------------------------------
double compute_ret(const std::vector<Bar>& bars, std::size_t window) {
    if (bars.size() < 2) return 0.0;
    std::size_t start = bars.size() > window ? bars.size() - window - 1 : 0;
    double p0 = bars[start].close;
    double p1 = bars.back().close;
    return p0 > 0.0 ? (p1 - p0) / p0 : 0.0;
}

}  // namespace

void FeatureEngine::feed_bars(const std::vector<Bar>& bars) {
    for (const auto& b : bars) {
        history_.push_back(b);
    }
    while (history_.size() > MAX_HISTORY) {
        history_.erase(history_.begin(), history_.begin() + (history_.size() - MAX_HISTORY));
    }
}

FeatureFrame FeatureEngine::compute() const {
    return compute(history_);
}

FeatureFrame FeatureEngine::compute(const std::vector<Bar>& bars) const {
    FeatureFrame frame;

    if (bars.empty()) return frame;

    // 按品种分组，避免跨品种 bar 串扰导致特征值失真
    std::unordered_map<std::string, std::vector<Bar>> by_inst;
    for (const auto& b : bars) {
        by_inst[instrument_key(b.instrument)].push_back(b);
    }

    frame["last_price"] = bars.back().close;
    frame["volume"] = bars.back().volume;

    // 每个品种独立计算特征，再汇总为市场级特征
    double vol_sum = 0.0, ret_sum = 0.0, adx_max = 0.0;
    int inst_count = 0;
    for (const auto& [key, inst_bars] : by_inst) {
        if (inst_bars.size() < 2) continue;
        ++inst_count;
        vol_sum += compute_realized_vol(inst_bars, 20);
        ret_sum += compute_ret(inst_bars, 20);
        adx_max = std::max(adx_max, compute_adx(inst_bars));
    }
    if (inst_count > 0) {
        frame["realized_vol_20d"] = vol_sum / inst_count;
        frame["ret_20d"] = ret_sum / inst_count;
        frame["adx_20d"] = adx_max;
    } else {
        frame["realized_vol_20d"] = 0.15;
        frame["ret_20d"] = 0.0;
        frame["adx_20d"] = 20.0;
    }

    // 计算平均品种间相关性
    double avg_corr = 0.0;
    if (inst_count >= 2) {
        // 每个品种取对数收益率序列
        std::unordered_map<std::string, std::vector<double>> inst_rets;
        for (const auto& [key, inst_bars] : by_inst) {
            if (inst_bars.size() < 2) continue;
            auto& rets = inst_rets[key];
            for (size_t i = 1; i < inst_bars.size(); ++i) {
                if (inst_bars[i-1].close > 0.0 && inst_bars[i].close > 0.0)
                    rets.push_back(std::log(inst_bars[i].close / inst_bars[i-1].close));
            }
        }
        // 取最小长度对齐
        size_t min_len = SIZE_MAX;
        for (const auto& [_, rets] : inst_rets) min_len = std::min(min_len, rets.size());
        if (min_len >= 2) {
            double corr_sum = 0.0;
            int corr_count = 0;
            std::vector<std::string> keys;
            for (const auto& [k, _] : inst_rets) keys.push_back(k);
            for (size_t i = 0; i < keys.size(); ++i) {
                for (size_t j = i + 1; j < keys.size(); ++j) {
                    const auto& ra = inst_rets[keys[i]];
                    const auto& rb = inst_rets[keys[j]];
                    double ma = 0.0, mb = 0.0;
                    for (size_t t = 0; t < min_len; ++t) { ma += ra[t]; mb += rb[t]; }
                    ma /= min_len; mb /= min_len;
                    double cov = 0.0, va = 0.0, vb = 0.0;
                    for (size_t t = 0; t < min_len; ++t) {
                        double da = ra[t] - ma, db = rb[t] - mb;
                        cov += da * db; va += da * da; vb += db * db;
                    }
                    double denom = std::sqrt(std::max(va * vb, 1e-12));
                    if (denom > 0) { corr_sum += cov / denom; ++corr_count; }
                }
            }
            if (corr_count > 0) avg_corr = corr_sum / corr_count;
        }
    }
    frame["avg_corr_20d"] = avg_corr;

    return frame;
}

// ---- GAP-032: 协方差矩阵估计 ----------------------------------------
// 方法：
//   1. 将历史 bar 按 timestamp 分桶，每桶内按 instrument 存 close
//   2. 对每个 instrument 构建时间对齐的价格序列
//   3. 计算对数收益率 r_t = log(p_t / p_{t-1})
//   4. 样本协方差: cov(i,j) = sum((r_i - mu_i)(r_j - mu_j)) / (T-1)
//   5. 年化: cov * 252
// ------------------------------------------------------------------
std::unordered_map<std::string, double> FeatureEngine::compute_covariance_map(
    int lookback) const {
    std::unordered_map<std::string, double> cov_map;

    if (history_.size() < 3) return cov_map;

    // 1. 按 timestamp 分桶（用 ordered map 保证时间顺序）
    std::map<std::int64_t, std::unordered_map<std::string, double>> time_buckets;
    for (const auto& bar : history_) {
        time_buckets[bar.timestamp][instrument_key(bar.instrument)] = bar.close;
    }

    // 2. 收集出现足够多次的 instrument
    std::unordered_map<std::string, int> inst_counts;
    for (const auto& [ts, bucket] : time_buckets) {
        for (const auto& [inst, price] : bucket) {
            inst_counts[inst]++;
        }
    }

    std::vector<std::string> instruments;
    for (const auto& [inst, cnt] : inst_counts) {
        if (cnt >= 2) instruments.push_back(inst);
    }
    if (instruments.size() < 2) return cov_map;

    // 3. 构建价格矩阵: 行=时间, 列=instrument (只用最近 lookback 个时间桶)
    std::vector<std::vector<double>> price_matrix;
    {
        auto it = time_buckets.end();
        int collected = 0;
        while (it != time_buckets.begin() && collected < lookback) {
            --it;
            ++collected;
        }
        for (; it != time_buckets.end(); ++it) {
            std::vector<double> row(instruments.size(), std::nan(""));
            for (std::size_t j = 0; j < instruments.size(); ++j) {
                auto pit = it->second.find(instruments[j]);
                if (pit != it->second.end()) {
                    row[j] = pit->second;
                }
            }
            price_matrix.push_back(std::move(row));
        }
    }

    // 4. 对数收益率矩阵 (T-1 x N)
    std::vector<std::vector<double>> ret_matrix;
    for (std::size_t t = 1; t < price_matrix.size(); ++t) {
        std::vector<double> row(instruments.size(), std::nan(""));
        bool any_valid = false;
        for (std::size_t j = 0; j < instruments.size(); ++j) {
            if (!std::isnan(price_matrix[t][j]) && !std::isnan(price_matrix[t-1][j]) &&
                price_matrix[t-1][j] > 0.0) {
                row[j] = std::log(price_matrix[t][j] / price_matrix[t-1][j]);
                any_valid = true;
            }
        }
        if (any_valid) {
            ret_matrix.push_back(std::move(row));
        }
    }

    if (ret_matrix.size() < 2) return cov_map;

    // 5. 计算均值
    std::vector<double> means(instruments.size(), 0.0);
    std::vector<int> counts(instruments.size(), 0);
    for (const auto& row : ret_matrix) {
        for (std::size_t j = 0; j < instruments.size(); ++j) {
            if (!std::isnan(row[j])) {
                means[j] += row[j];
                counts[j]++;
            }
        }
    }
    for (std::size_t j = 0; j < instruments.size(); ++j) {
        if (counts[j] > 0) means[j] /= counts[j];
    }

    // 6. 样本协方差 + 年化
    int T = static_cast<int>(ret_matrix.size());
    for (std::size_t i = 0; i < instruments.size(); ++i) {
        for (std::size_t j = i; j < instruments.size(); ++j) {
            double cov = 0.0;
            int pair_count = 0;
            for (const auto& row : ret_matrix) {
                if (!std::isnan(row[i]) && !std::isnan(row[j])) {
                    cov += (row[i] - means[i]) * (row[j] - means[j]);
                    pair_count++;
                }
            }
            if (pair_count > 1) {
                cov *= static_cast<double>(T - 1) / (pair_count - 1);
                cov *= 252.0;  // 年化
                std::string key_ij = "cov:" + instruments[i] + ":" + instruments[j];
                cov_map[key_ij] = cov;
                if (i != j) {
                    std::string key_ji = "cov:" + instruments[j] + ":" + instruments[i];
                    cov_map[key_ji] = cov;
                }
            }
        }
    }

    // 附加入口: instrument 列表标识
    std::string inst_list;
    for (std::size_t i = 0; i < instruments.size(); ++i) {
        if (i > 0) inst_list += ",";
        inst_list += instruments[i];
    }
    cov_map["cov:__count__"] = static_cast<double>(instruments.size());
    cov_map["cov:__list__"] = 0.0;  // 标记位，实际列表通过 key pattern 读取

    return cov_map;
}

}  // namespace qt::data
