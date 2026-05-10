#pragma once

#include <deque>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "qt/agent/agent.hpp"
#include "qt/types.hpp"

namespace qt::agent {

// ---- 特征交互规则 ----------------------------------------------------

struct FeatureRule {
    std::string primary;     // 主特征名
    std::string secondary;   // 辅助特征名
    double primary_weight{0.5};
    double secondary_weight{0.5};

    enum Type { BothHigh, BothLow, Divergence, Convergence };
    Type type{BothHigh};
};

// ---- LLMFeatureAgent (GAP-037) ---------------------------------------
// 通过分析多维特征的交互关系生成交易信号。
// 模拟 LLM 的 in-context reasoning 能力:
//   - 滚动窗口特征历史 = context window
//   - 特征交互规则 = learned patterns from training
//   - Regime 感知 = adaptive weighting
//   - 异常检测 = 3-sigma + 趋势斜率
// ----------------------------------------------------------------------

class LLMFeatureAgent : public ISignalAgent {
public:
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const FeatureFrame& features,
                                          const PortfolioSnapshot& portfolio,
                                          const RegimeState& regime) override;
    void on_bar(const Bar& bar) override;
    void reset() override;

    // R48: 暴露分析结果
    const std::deque<std::string>& narrative_history() const { return narrative_buffer_; }
    const std::deque<Bar>& bar_history() const { return bar_history_; }

private:
    void update_feature_history(const FeatureFrame& features);
    std::string generate_narrative(const FeatureFrame& features,
                                    const RegimeState& regime);
    std::optional<Signal> evaluate_rule(const FeatureRule& rule,
                                         const FeatureFrame& features,
                                         const RegimeState& regime);
    std::vector<Signal> detect_anomalies(const FeatureFrame& features,
                                          const RegimeState& regime);

    std::deque<Bar> bar_history_;
    std::deque<FeatureFrame> feature_history_;
    std::deque<std::string> narrative_buffer_;
};

}  // namespace qt::agent
