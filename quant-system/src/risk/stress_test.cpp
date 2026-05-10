#include "qt/risk/stress_test.hpp"

#include <algorithm>
#include <cmath>

namespace qt::risk {

StressTester::StressTester() {
    scenarios_ = {
        {"flash_crash",    1.8, 0.70, -0.25},
        {"vol_spike",      2.5, 0.50, -0.08},
        {"corr_breakdown", 1.2, 0.95, -0.05},
        {"liquidity_crunch", 2.0, 0.60, -0.20},
        {"black_swan",     3.0, 0.85, -0.40},
    };
}

std::vector<StressTestResult> StressTester::run(
    const PortfolioSnapshot& portfolio,
    const FeatureFrame& features) const {

    std::vector<StressTestResult> results;
    double equity = portfolio.equity;
    // R26: 零/负权益时返回失败结果，而非空（空=通过）
    if (equity <= 0.0) {
        results.push_back({"insolvent", 0.0, 1.0, false});
        return results;
    }

    // 从 features 提取当前市场条件
    double current_vol = 0.15;
    auto vol_it = features.find("market.realized_vol_20d");
    if (vol_it != features.end()) current_vol = vol_it->second;

    for (const auto& scenario : scenarios_) {
        double total_impact = 0.0;

        for (const auto& pos : portfolio.positions) {
            if (std::abs(pos.weight) < 1e-6) continue;

            // 简化模型: 冲击 = 头寸权重 * (价格冲击 + 波动率冲击调整)
            // 不同资产对波动率放大的敏感度不同:
            // - 高波动资产在 vol shock 时回撤更大
            // - 相关性崩溃时分散化失效
            double asset_vol = current_vol; // 简化: 使用市场平均波动
            double shock = scenario.price_shock
                         + (scenario.vol_shock - 1.0) * asset_vol * 0.5
                         + (scenario.corr_shock > 0.60 ? -0.05 : 0.0);

            total_impact += pos.weight * shock;
        }

        double equity_impact = total_impact;

        results.push_back({
            scenario.name,
            equity_impact * equity,
            equity_impact,
            std::abs(equity_impact) <= tolerance_,
        });
    }

    return results;
}

}  // namespace qt::risk
