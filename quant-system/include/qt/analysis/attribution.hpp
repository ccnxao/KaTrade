#pragma once

#include <string>
#include <unordered_map>
#include <vector>

#include "qt/types.hpp"

namespace qt {
struct CycleResult;  // forward-declare from trader_engine.hpp
}

namespace qt::analysis {

// ---- 绩效归因结果 (GAP-038) -------------------------------------------
// 将组合总收益分解为:
//   1. Brinson 归因: Allocation + Selection + Interaction
//   2. 策略归因: 每个 signal agent 的 PnL 贡献
//   3. 因子归因: 风格因子暴露 × 因子收益
// ----------------------------------------------------------------------

struct AttributionResult {
    // ---- 总览 ----
    double total_return{0.0};
    double benchmark_return{0.0};   // 等权基准
    double excess_return{0.0};      // 超额收益

    // ---- Brinson 分解 ----
    // allocation_effect  = sum_i (w_p,i - w_b,i) * r_b,i
    // selection_effect   = sum_i w_b,i * (r_p,i - r_b,i)
    // interaction_effect = sum_i (w_p,i - w_b,i) * (r_p,i - r_b,i)
    double allocation_effect{0.0};
    double selection_effect{0.0};
    double interaction_effect{0.0};

    // ---- 策略归因 ----
    // key = strategy_id, value = PnL contribution
    std::unordered_map<std::string, double> strategy_contributions;

    // ---- 因子归因 ----
    // key = factor name ("momentum", "value", "quality", "low_vol")
    // value = 因子贡献
    std::unordered_map<std::string, double> factor_contributions;

    // ---- 周期级明细 ----
    std::vector<double> period_excess_returns;
};

// ---- 绩效归因分析器 ---------------------------------------------------

class PerformanceAttribution {
public:
    PerformanceAttribution();

    // 主入口: 对一组回测周期进行归因分析
    AttributionResult analyze(const std::vector<CycleResult>& cycles,
                               const PortfolioSnapshot& initial_portfolio);

    // 单独计算 Brinson 分解（给定组合权重、基准权重、收益）
    static void brinson_decomposition(
        const std::vector<double>& portfolio_weights,
        const std::vector<double>& benchmark_weights,
        const std::vector<double>& portfolio_returns,
        const std::vector<double>& benchmark_returns,
        double& allocation,
        double& selection,
        double& interaction);

    // 因子暴露计算
    // 从 FeatureFrame 中估计各因子暴露
    static std::unordered_map<std::string, double> estimate_factor_exposures(
        const std::vector<Position>& positions,
        const FeatureFrame& features);

    // 因子收益估计（使用常见风格因子）
    static std::unordered_map<std::string, double> factor_returns(
        const FeatureFrame& features);

private:
    // 单周期归因
    void attribute_cycle(const CycleResult& cycle,
                          const PortfolioSnapshot& prev_portfolio,
                          std::unordered_map<std::string, double>& strategy_pnl,
                          std::vector<double>& excess_rets);

    // 策略 PnL 结算
    void settle_cycle_pnl(const CycleResult& cycle,
                           std::unordered_map<std::string, double>& strategy_pnl);
};

}  // namespace qt::analysis
