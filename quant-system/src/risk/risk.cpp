#include "qt/risk.hpp"
#include "qt/risk/stress_test.hpp"

#include <algorithm>
#include <cmath>

namespace qt {

risk::MaxPositionRule::MaxPositionRule(double max_abs_weight)
    : max_abs_weight_(max_abs_weight) {}

std::optional<std::string> risk::MaxPositionRule::check(const TargetPortfolio& target,
                                                  const PortfolioSnapshot&,
                                                  const FeatureFrame&) const {
    for (const auto& position : target.positions) {
        if (std::abs(position.target_weight) > max_abs_weight_ + 1e-9) {
            return "position weight exceeds single-name limit";
        }
    }
    return std::nullopt;
}

risk::MaxGrossExposureRule::MaxGrossExposureRule(double max_gross)
    : max_gross_(max_gross) {}

std::optional<std::string> risk::MaxGrossExposureRule::check(const TargetPortfolio& target,
                                                       const PortfolioSnapshot&,
                                                       const FeatureFrame&) const {
    if (gross_exposure(target) > max_gross_ + 1e-9) {
        return "gross exposure exceeds portfolio limit";
    }
    return std::nullopt;
}

void risk::RiskAgent::add_rule(std::unique_ptr<IRiskRule> rule) {
    rules_.push_back(std::move(rule));
}

void risk::RiskAgent::set_kill_switch(bool enabled) {
    kill_switch_ = enabled;
}

void risk::RiskAgent::set_thresholds(double drawdown_limit, double vol_threshold,
                                      double vol_reduction, double stress_tolerance) {
    drawdown_limit_ = drawdown_limit;
    vol_threshold_ = vol_threshold;
    vol_reduction_ = vol_reduction;
    stress_tolerance_ = stress_tolerance;
}

risk::RiskAgent::RiskAgent(double max_abs_weight, double max_gross, bool kill_switch)
    : max_abs_weight_(max_abs_weight),
      max_gross_(max_gross),
      kill_switch_(kill_switch) {
    rules_.push_back(std::make_unique<risk::MaxPositionRule>(max_abs_weight_));
    rules_.push_back(std::make_unique<risk::MaxGrossExposureRule>(max_gross_));
}

RiskDecision risk::RiskAgent::review(const TargetPortfolio& target,
                               const PortfolioSnapshot& current,
                               const MarketState& market,
                               const AccountState& account) {
    // 从 MarketState 构建 FeatureFrame，避免用空 map 做基础检查
    FeatureFrame market_features;
    double vol = market.vix > 0 ? market.vix : (market.realized_vol > 0 ? market.realized_vol : 0.15);
    market_features["market.realized_vol_20d"] = vol;
    market_features["realized_vol_20d"] = vol;
    if (market.avg_correlation > 0.0) {
        market_features["market.avg_corr_20d"] = market.avg_correlation;
        market_features["avg_corr_20d"] = market.avg_correlation;
    }

    // 先执行基础检查（带真实市场特征）
    RiskDecision base = review(target, current, market_features);
    if (base.action == RiskAction::Halt || base.action == RiskAction::Reject) {
        return base;
    }

    // 压力测试 (GAP-006): 在极端市场条件下检查组合抗风险能力
    stress_tester_.set_tolerance(stress_tolerance_);
    FeatureFrame stress_features = market_features;
    auto results = stress_tester_.run(current, stress_features);
    for (const auto& r : results) {
        if (!r.within_tolerance) {
            // 风控已调整的组合（含权重 clamp），而非原始目标
            auto reduced = base.adjusted_portfolio;
            for (auto& pos : reduced.positions) {
                pos.target_weight *= 0.7;  // 压力情景下额外削减 30%
            }
            return {RiskAction::Reduce,
                    "stress test failed: " + r.scenario,
                    reduced};
        }
    }

    // 回撤熔断 (GAP-008): 从峰值回撤超 20% 触发
    if (account.peak_equity > 0.0 && account.equity > 0.0) {
        double drawdown = 1.0 - account.equity / account.peak_equity;
        if (drawdown > drawdown_limit_) {
            return {RiskAction::Halt,
                    "drawdown limit: " + std::to_string(drawdown * 100) + "% from peak",
                    {}};
        }
    }

    return base;
}

RiskDecision risk::RiskAgent::review(const TargetPortfolio& target,
                               const PortfolioSnapshot& current,
                               const FeatureFrame& features) {
    if (kill_switch_) {
        return {RiskAction::Halt, "kill switch enabled", {}};
    }

    TargetPortfolio adjusted = target;
    bool changed = false;

    // R10: clamp 单品种，被 clamp 的品种锁死不再缩放
    double locked_gross = 0.0;   // 被 clamp 品种的暴露（不可再缩）
    double free_gross = 0.0;     // 未 clamp 品种的暴露（可按比例缩放）
    for (auto& position : adjusted.positions) {
        double original = position.target_weight;
        double clamped = std::clamp(original, -max_abs_weight_, max_abs_weight_);
        if (std::abs(clamped - original) > 1e-9) {
            position.target_weight = clamped;
            changed = true;
            locked_gross += std::abs(clamped);
        } else {
            free_gross += std::abs(clamped);
        }
    }

    // 只缩放未被 clamp 的品种，保留 clamp 品种不动
    double total_gross = locked_gross + free_gross;
    if (total_gross > max_gross_ && total_gross > 0.0) {
        double remaining_budget = max_gross_ - locked_gross;
        if (remaining_budget <= 0.0) {
            // clamp 品种已占满预算，清空其余品种
            for (auto& position : adjusted.positions) {
                if (std::abs(position.target_weight) >= max_abs_weight_ - 1e-9) continue;
                position.target_weight = 0.0;
                changed = true;
            }
        } else if (free_gross > 0.0) {
            double scale = remaining_budget / free_gross;
            for (auto& position : adjusted.positions) {
                if (std::abs(std::abs(position.target_weight) - max_abs_weight_) < 1e-9) continue;
                position.target_weight *= scale;
                changed = true;
            }
        }
    }

    const auto vol_it = features.find("market.realized_vol_20d");
    const double vol = vol_it == features.end() ? 0.15 : vol_it->second;
    if (vol > vol_threshold_) {
        for (auto& position : adjusted.positions) {
            position.target_weight *= vol_reduction_;
        }
        changed = true;
    }

    for (const auto& rule : rules_) {
        if (const auto error = rule->check(adjusted, current, features)) {
            return {RiskAction::Reject, *error, {}};
        }
    }

    adjusted.expected_turnover = target.expected_turnover;
    adjusted.expected_cost_bps = target.expected_cost_bps;
    adjusted.optimizer_version = target.optimizer_version;

    if (adjusted.positions.empty()) {
        return {RiskAction::Reject, "risk agent produced an empty portfolio", {}};
    }

    return {changed ? RiskAction::Reduce : RiskAction::Approve,
            changed ? "risk-adjusted portfolio" : "approved",
            adjusted};
}

}  // namespace qt
