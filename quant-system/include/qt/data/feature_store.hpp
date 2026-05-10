#pragma once

#include <cstddef>
#include <string>
#include <unordered_map>
#include <vector>

#include "qt/types.hpp"

namespace qt::data {

class FeatureEngine {
public:
    FeatureEngine() = default;

    // 增量积累 bar（GAP-019: 跨周期有状态）
    void feed_bars(const std::vector<Bar>& bars);
    // 从累积的 bar 计算特征
    FeatureFrame compute() const;
    // 兼容旧接口: 直接计算
    FeatureFrame compute(const std::vector<Bar>& bars) const;

    // GAP-032: 协方差矩阵估计（用于 Markowitz / Risk Parity 组合优化）
    // 返回 key="cov:INST_A:INST_B" -> covariance 值（年化）
    // lookback 指定用于估计的最大 bar 数
    std::unordered_map<std::string, double> compute_covariance_map(int lookback) const;

    // 暴露历史数据，供外部做更复杂的协方差估计
    const std::vector<Bar>& history() const { return history_; }

private:
    std::vector<Bar> history_;
    static constexpr std::size_t MAX_HISTORY = 6000;
};

}  // namespace qt::data
