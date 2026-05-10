#pragma once

#include <deque>
#include <span>
#include <string>
#include <unordered_map>
#include <vector>

#include "qt/types.hpp"

namespace qt {

// ---- 协方差工具类型 --------------------------------------------------

// 协方差矩阵 (N x N)
using CovarianceMatrix = std::vector<std::vector<double>>;

// 从 FeatureFrame 中提取协方差矩阵（读取 "cov:INST_A:INST_B" 格式的 key）
CovarianceMatrix extract_covariance(const FeatureFrame& features,
                                    const std::vector<std::string>& instruments);

// ---- 组合优化器接口 ---------------------------------------------------

class IPortfolioOptimizer {
public:
    virtual ~IPortfolioOptimizer() = default;
    virtual TargetPortfolio optimize(std::span<const Signal> signals,
                                     const PortfolioSnapshot& current,
                                     const FeatureFrame& features,
                                     const RegimeState& regime) = 0;
};

// ---- SimplePortfolioOptimizer (保留，默认实现) ------------------------

class SimplePortfolioOptimizer final : public IPortfolioOptimizer {
public:
    SimplePortfolioOptimizer(double max_single_weight, double max_gross);

    TargetPortfolio optimize(std::span<const Signal> signals,
                             const PortfolioSnapshot& current,
                             const FeatureFrame& features,
                             const RegimeState& regime) override;

private:
    double max_single_weight_;
    double max_gross_;
};

// ---- MarkowitzPortfolioOptimizer (GAP-032) ---------------------------
// 均值-方差优化:
//   maximize  w'*alpha - (lambda/2) * w'*Sigma*w
//   subject to sum(|w_i|) <= max_gross, |w_i| <= max_single
//
// alpha 来自信号分数 (score * confidence * strategy_weight),
// Sigma 来自 FeatureFrame 中的历史协方差估计。
// 使用梯度投影法求解。

class MarkowitzPortfolioOptimizer final : public IPortfolioOptimizer {
public:
    MarkowitzPortfolioOptimizer(double max_single_weight,
                                double max_gross,
                                double risk_aversion,
                                double target_vol);

    TargetPortfolio optimize(std::span<const Signal> signals,
                             const PortfolioSnapshot& current,
                             const FeatureFrame& features,
                             const RegimeState& regime) override;

private:
    double max_single_weight_;
    double max_gross_;
    double risk_aversion_;   // lambda: 风险厌恶系数 (default=1.0)
    double target_vol_;      // 目标年化波动率 (default=0.15)

    // 梯度投影法求解带约束的二次规划
    // w_opt = argmax w'*alpha - (lambda/2)*w'*Sigma*w
    //         s.t. sum(|w_i|) <= max_gross, |w_i| <= max_single
    std::vector<double> solve_qp(const std::vector<double>& alpha,
                                 const CovarianceMatrix& sigma,
                                 int max_iter) const;
};

// ---- RiskParityOptimizer (GAP-032) -----------------------------------
// 风险平价 (Equal Risk Contribution):
//   使每个资产的 risk contribution = w_i * (Sigma*w)_i 相等
//
// 使用迭代算法 (Griveau-Billion 2013 的简化版):
//   w_i^(k+1) = w_i^(k) * target_rc / RC_i^(k)
//   然后按 max_gross 缩放，按 max_single 截断

class RiskParityOptimizer final : public IPortfolioOptimizer {
public:
    RiskParityOptimizer(double max_single_weight,
                        double max_gross,
                        double target_vol);

    TargetPortfolio optimize(std::span<const Signal> signals,
                             const PortfolioSnapshot& current,
                             const FeatureFrame& features,
                             const RegimeState& regime) override;

private:
    double max_single_weight_;
    double max_gross_;
    double target_vol_;

    // ERC 迭代求解
    std::vector<double> solve_erc(const CovarianceMatrix& sigma,
                                  const std::vector<double>& init_weights,
                                  int max_iter,
                                  double tol) const;
};

}  // namespace qt
