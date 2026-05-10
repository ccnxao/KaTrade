#include "qt/analysis/attribution.hpp"
#include "qt/trader_engine.hpp"

#include <algorithm>
#include <cmath>
#include <numeric>

namespace qt::analysis {

// ---- PerformanceAttribution -------------------------------------------

PerformanceAttribution::PerformanceAttribution() = default;

AttributionResult PerformanceAttribution::analyze(
    const std::vector<CycleResult>& cycles,
    const PortfolioSnapshot& initial_portfolio) {

    AttributionResult result;
    if (cycles.empty()) return result;

    // R40: 权益无效时返回空结果而非假设 $1M
    if (initial_portfolio.equity <= 0.0) return result;
    double initial_equity = initial_portfolio.equity;

    // 1. 计算总收益和超额收益
    double final_equity = cycles.back().post_trade_portfolio.equity;
    result.total_return = final_equity / initial_equity - 1.0;

    // 等权基准: 所有品种等权持有
    // 从周期数据中收集所有品种的收益，取平均
    double bench_ret_sum = 0.0;
    int bench_count = 0;
    for (const auto& cycle : cycles) {
        for (const auto& pos : cycle.post_trade_portfolio.positions) {
            if (pos.avg_cost > 0.0 && pos.market_price > 0.0) {
                double ret = pos.market_price / pos.avg_cost - 1.0;
                bench_ret_sum += ret;
                bench_count++;
            }
        }
    }
    if (bench_count > 0) {
        result.benchmark_return = bench_ret_sum / bench_count;
    }
    result.excess_return = result.total_return - result.benchmark_return;

    // 2. Brinson 分解: 需要在各周期汇总
    // 简化实现: 用平均权重和平均收益
    if (cycles.size() > 1) {
        std::unordered_map<std::string, double> avg_port_weight;
        std::unordered_map<std::string, double> avg_port_return;
        std::unordered_map<std::string, int> weight_counts;

        for (const auto& cycle : cycles) {
            for (const auto& pos : cycle.pre_trade_portfolio.positions) {
                auto key = instrument_key(pos.instrument);
                avg_port_weight[key] += pos.weight;
                weight_counts[key]++;
                if (pos.avg_cost > 0.0 && pos.market_price > 0.0) {
                    avg_port_return[key] += pos.market_price / pos.avg_cost - 1.0;
                }
            }
        }

        // 收集有数据的 instrument
        std::vector<std::string> instruments;
        for (const auto& [key, cnt] : weight_counts) {
            if (cnt > 0) {
                instruments.push_back(key);
            }
        }

        int N = static_cast<int>(instruments.size());
        if (N >= 2) {
            std::vector<double> pw(N), bw(N), pr(N), br(N);
            for (int i = 0; i < N; ++i) {
                pw[i] = avg_port_weight[instruments[i]] / weight_counts[instruments[i]];
                pr[i] = avg_port_return[instruments[i]] / weight_counts[instruments[i]];
            }
            // 等权基准
            double eq_w = 1.0 / N;
            for (int i = 0; i < N; ++i) {
                bw[i] = eq_w;
                br[i] = pr[i];  // 简化: 基准收益 = 品种自身收益
            }

            brinson_decomposition(pw, bw, pr, br,
                                   result.allocation_effect,
                                   result.selection_effect,
                                   result.interaction_effect);
        }
    }

    // 3. 策略归因
    {
        PortfolioSnapshot prev = initial_portfolio;
        for (const auto& cycle : cycles) {
            attribute_cycle(cycle, prev, result.strategy_contributions,
                            result.period_excess_returns);
            prev = cycle.post_trade_portfolio;
        }
    }

    // 4. 因子归因（使用最后一个周期的特征）
    if (!cycles.empty()) {
        const auto& last_cycle = cycles.back();
        auto exposures = estimate_factor_exposures(
            last_cycle.post_trade_portfolio.positions,
            last_cycle.features);
        auto f_returns = factor_returns(last_cycle.features);

        for (const auto& [factor, exposure] : exposures) {
            auto it = f_returns.find(factor);
            if (it != f_returns.end()) {
                result.factor_contributions[factor] = exposure * it->second;
            }
        }
    }

    return result;
}

// ---- Brinson 分解 (静态) ----------------------------------------------

void PerformanceAttribution::brinson_decomposition(
    const std::vector<double>& portfolio_weights,
    const std::vector<double>& benchmark_weights,
    const std::vector<double>& portfolio_returns,
    const std::vector<double>& benchmark_returns,
    double& allocation,
    double& selection,
    double& interaction) {

    allocation = 0.0;
    selection = 0.0;
    interaction = 0.0;

    int N = static_cast<int>(portfolio_weights.size());
    if (N == 0) return;

    for (int i = 0; i < N; ++i) {
        double dw = portfolio_weights[i] - benchmark_weights[i];
        double dr = portfolio_returns[i] - benchmark_returns[i];

        allocation  += dw * benchmark_returns[i];
        selection   += benchmark_weights[i] * dr;
        interaction += dw * dr;
    }
}

// ---- 因子暴露估计 ----------------------------------------------------

std::unordered_map<std::string, double>
PerformanceAttribution::estimate_factor_exposures(
    const std::vector<Position>& positions,
    const FeatureFrame& features) {

    std::unordered_map<std::string, double> exposures;

    if (positions.empty()) return exposures;

    // 动量暴露: 用 ret_20d 作为 proxy
    auto ret_it = features.find("ret_20d");
    double ret = ret_it != features.end() ? ret_it->second : 0.0;
    exposures["momentum"] = std::clamp(ret * 5.0, -1.0, 1.0);

    // 低波动暴露: neg(vol) 越高越偏低波
    auto vol_it = features.find("realized_vol_20d");
    double vol = vol_it != features.end() ? vol_it->second : 0.15;
    exposures["low_vol"] = std::clamp(1.0 - vol / 0.30, -1.0, 1.0);

    // 质量暴露: 用 avg_corr 的反向（低相关=alpha=高质量）
    auto corr_it = features.find("avg_corr_20d");
    double corr = corr_it != features.end() ? corr_it->second : 0.30;
    exposures["quality"] = std::clamp(1.0 - corr, -1.0, 1.0);

    // 价值暴露: 用价格偏离的 proxy（TODO: 真正的 value 需要基本面数据）
    auto prc_it = features.find("last_price");
    if (prc_it != features.end()) {
        // 简化: 用价格倒数作为 "便宜" / "贵" 的 proxy
        exposures["value"] = std::clamp(50000.0 / std::max(prc_it->second, 1.0) - 0.5, -1.0, 1.0);
    }

    // 规模暴露: 用 volume 作为 proxy
    auto vol_ratio = features.find("volume");
    double vr = vol_ratio != features.end() ? vol_ratio->second : 0.0;
    exposures["size"] = std::clamp(std::log(std::max(vr, 1.0)) / 10.0, -1.0, 1.0);

    return exposures;
}

// ---- 因子收益 --------------------------------------------------------

std::unordered_map<std::string, double>
PerformanceAttribution::factor_returns(const FeatureFrame& features) {
    std::unordered_map<std::string, double> returns;

    // 动量因子: ret_20d
    auto ret_it = features.find("ret_20d");
    returns["momentum"] = ret_it != features.end() ? ret_it->second * 0.5 : 0.0;

    // 低波因子: 负相关于 vol
    auto vol_it = features.find("realized_vol_20d");
    returns["low_vol"] = vol_it != features.end()
        ? (0.15 - vol_it->second) * 0.3 : 0.0;

    // 质量因子: 低相关环境通常优质股表现好
    auto corr_it = features.find("avg_corr_20d");
    returns["quality"] = corr_it != features.end()
        ? (0.30 - corr_it->second) * 0.3 : 0.0;

    // 价值因子: proxy
    returns["value"] = 0.01;

    // 规模因子: proxy
    returns["size"] = 0.005;

    return returns;
}

// ---- 周期归因 --------------------------------------------------------

void PerformanceAttribution::attribute_cycle(
    const CycleResult& cycle,
    const PortfolioSnapshot& prev_portfolio,
    std::unordered_map<std::string, double>& strategy_pnl,
    std::vector<double>& excess_rets) {

    double cycle_pnl = cycle.post_trade_portfolio.realized_pnl
                     - prev_portfolio.realized_pnl;
    double cycle_equity = prev_portfolio.equity;
    double cycle_return = cycle_equity > 0.0 ? cycle_pnl / cycle_equity : 0.0;
    excess_rets.push_back(cycle_return);

    settle_cycle_pnl(cycle, strategy_pnl);
}

void PerformanceAttribution::settle_cycle_pnl(
    const CycleResult& cycle,
    std::unordered_map<std::string, double>& strategy_pnl) {

    // 按订单的策略 ID 分配 PnL
    std::unordered_map<std::string, double> notional_by_strategy;
    double total_notional = 0.0;

    for (const auto& report : cycle.reports) {
        if (report.last_fill_qty <= 0.0 || report.last_fill_price <= 0.0) continue;
        double notional = report.last_fill_qty * report.last_fill_price;

        // 查找对应的 order record 获取 strategy_id
        for (const auto& rec : cycle.order_records) {
            if (rec.order_id == report.order_id && !rec.intent.strategy_id.empty()) {
                notional_by_strategy[rec.intent.strategy_id] += notional;
                total_notional += notional;
                break;
            }
        }
    }

    // 如果是信号驱动的，按信号分配
    if (total_notional <= 0.0 && !cycle.signals.empty()) {
        for (const auto& sig : cycle.signals) {
            notional_by_strategy[sig.strategy_id] += std::abs(sig.score) * sig.confidence;
            total_notional += std::abs(sig.score) * sig.confidence;
        }
    }

    if (total_notional > 0.0) {
        // 用本周期 PnL 增量，而非累计值
        double cycle_pnl = 0.0;
        for (const auto& report : cycle.reports) {
            if (report.last_fill_qty > 0.0 && report.last_fill_price > 0.0) {
                double fill_pnl = report.last_fill_qty * report.last_fill_price;
                cycle_pnl += (report.side == OrderSide::Sell ? fill_pnl : -fill_pnl);
            }
        }
        // 按名义金额比例分配（完整实现需要仓位级追踪）
        for (const auto& [strategy, notional] : notional_by_strategy) {
            strategy_pnl[strategy] += cycle_pnl * (notional / total_notional);
        }
    }
}

}  // namespace qt::analysis
