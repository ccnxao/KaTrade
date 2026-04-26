#pragma once

#include <memory>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

#include "qt/types.hpp"

namespace qt {

class IAgent {
public:
    virtual ~IAgent() = default;
    virtual std::string_view name() const noexcept = 0;
};

// 元策略只负责判断市场状态，例如趋势、震荡、危机。
// 它不直接给标的打分，也不产生订单，避免状态判断和交易动作耦合。
class IMetaAgent : public IAgent {
public:
    virtual RegimeState detect_regime(const FeatureFrame& features) = 0;
};

// 信号策略只输出 Signal。Signal 是“研究观点”，不是订单。
// 仓位大小、风控裁剪和订单生命周期统一交给后面的组合、风控和 OMS 层处理。
class ISignalAgent : public IAgent {
public:
    virtual std::vector<Signal> generate_signals(const std::vector<Bar>& bars,
                                                 const FeatureFrame& features,
                                                 const PortfolioSnapshot& portfolio,
                                                 const RegimeState& regime) = 0;
};

class RuleBasedRegimeAgent final : public IMetaAgent {
public:
    std::string_view name() const noexcept override;
    RegimeState detect_regime(const FeatureFrame& features) override;
};

// 基础趋势策略：日内收益为正时给多头信号，作为最小可解释基线。
class MomentumAgent final : public ISignalAgent {
public:
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const std::vector<Bar>& bars,
                                         const FeatureFrame& features,
                                         const PortfolioSnapshot& portfolio,
                                         const RegimeState& regime) override;
};

// 基础反转策略：对异常大的日内涨跌做反向信号，适合震荡市基线测试。
class MeanReversionAgent final : public ISignalAgent {
public:
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const std::vector<Bar>& bars,
                                         const FeatureFrame& features,
                                         const PortfolioSnapshot& portfolio,
                                         const RegimeState& regime) override;
};

// 防御策略：危机状态下偏向黄金、债券等防御资产。
// 这类策略应保持低复杂度，主要用于风险环境下的组合保护。
class DefensiveAgent final : public ISignalAgent {
public:
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const std::vector<Bar>& bars,
                                         const FeatureFrame& features,
                                         const PortfolioSnapshot& portfolio,
                                         const RegimeState& regime) override;
};

// 趋势策略：唐奇安通道突破。
// 使用上一段历史的最高/最低价判断突破，当前 bar 不参与通道计算。
class DonchianBreakoutAgent final : public ISignalAgent {
public:
    explicit DonchianBreakoutAgent(std::size_t lookback = 3);
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const std::vector<Bar>& bars,
                                         const FeatureFrame& features,
                                         const PortfolioSnapshot& portfolio,
                                         const RegimeState& regime) override;

private:
    std::size_t lookback_;
    std::unordered_map<std::string, std::vector<Bar>> history_;
};

// 趋势策略：快慢均线价差。
// 只负责给方向和强度，最终仓位仍由 PortfolioOptimizer 和 RiskAgent 决定。
class MovingAverageCrossAgent final : public ISignalAgent {
public:
    MovingAverageCrossAgent(std::size_t fast_window = 2, std::size_t slow_window = 4);
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const std::vector<Bar>& bars,
                                         const FeatureFrame& features,
                                         const PortfolioSnapshot& portfolio,
                                         const RegimeState& regime) override;

private:
    std::size_t fast_window_;
    std::size_t slow_window_;
    std::unordered_map<std::string, std::vector<double>> closes_;
};

// 趋势策略：MACD 动量。
// 用快慢 EMA 价差和信号线判断趋势方向，适合趋势延续环境。
class MacdTrendAgent final : public ISignalAgent {
public:
    MacdTrendAgent(double fast_alpha = 0.55,
                   double slow_alpha = 0.30,
                   double signal_alpha = 0.45);
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const std::vector<Bar>& bars,
                                         const FeatureFrame& features,
                                         const PortfolioSnapshot& portfolio,
                                         const RegimeState& regime) override;

private:
    struct State {
        bool initialized{false};
        double fast_ema{};
        double slow_ema{};
        double signal_ema{};
    };

    double fast_alpha_;
    double slow_alpha_;
    double signal_alpha_;
    std::unordered_map<std::string, State> state_;
};

// 震荡策略：布林带反转。
// 当价格偏离滚动均值超过阈值时做反向信号。
class BollingerReversionAgent final : public ISignalAgent {
public:
    BollingerReversionAgent(std::size_t window = 4, double band_width = 1.2);
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const std::vector<Bar>& bars,
                                         const FeatureFrame& features,
                                         const PortfolioSnapshot& portfolio,
                                         const RegimeState& regime) override;

private:
    std::size_t window_;
    double band_width_;
    std::unordered_map<std::string, std::vector<double>> closes_;
};

// 震荡策略：RSI 反转。
// RSI 高位视作短期过热，低位视作短期超卖。
class RsiReversionAgent final : public ISignalAgent {
public:
    RsiReversionAgent(std::size_t window = 4,
                      double oversold = 35.0,
                      double overbought = 65.0);
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const std::vector<Bar>& bars,
                                         const FeatureFrame& features,
                                         const PortfolioSnapshot& portfolio,
                                         const RegimeState& regime) override;

private:
    std::size_t window_;
    double oversold_;
    double overbought_;
    std::unordered_map<std::string, std::vector<double>> closes_;
};

// 震荡策略：区间边缘反转。
// 当收盘接近当期高低区间边缘时，假设短期价格可能回到区间内部。
class RangeFadeAgent final : public ISignalAgent {
public:
    std::string_view name() const noexcept override;
    std::vector<Signal> generate_signals(const std::vector<Bar>& bars,
                                         const FeatureFrame& features,
                                         const PortfolioSnapshot& portfolio,
                                         const RegimeState& regime) override;
};

}  // namespace qt
