#include "qt/strategy_module.hpp"

#include "qt/agent/llm_feature_agent.hpp"
#include "qt/runtime_config.hpp"

#include <functional>
#include <stdexcept>

namespace qt {

namespace {

struct StrategyRegistration {
    StrategyDescriptor descriptor;
    std::function<std::unique_ptr<ISignalAgent>(const RuntimeConfig&)> build;
};

const RuntimeConfig& default_config() {
    static const RuntimeConfig config;
    return config;
}

const std::vector<StrategyRegistration>& strategy_registry() {
    static const std::vector<StrategyRegistration> registry{
        {{"momentum",
          "动量基线",
          StrategyStyle::Trend,
          "日频",
          "日内收益为正时给多头信号，用作趋势策略基线。",
          true},
         [](const RuntimeConfig&) { return std::make_unique<MomentumAgent>(); }},
        {{"mean_reversion",
          "均值回归基线",
          StrategyStyle::MeanReversion,
          "日频",
          "对异常大的日内涨跌做反向信号，用作震荡策略基线。",
          true},
         [](const RuntimeConfig&) { return std::make_unique<MeanReversionAgent>(); }},
        {{"defensive",
          "防御资产",
          StrategyStyle::Defensive,
          "日频",
          "危机状态下偏向黄金、债券等防御资产。",
          true},
         [](const RuntimeConfig&) { return std::make_unique<DefensiveAgent>(); }},
        {{"donchian_breakout",
          "唐奇安突破",
          StrategyStyle::Trend,
          "日频",
          "突破上一段历史高低点后顺势跟随。",
          true},
         [](const RuntimeConfig& config) {
             return std::make_unique<DonchianBreakoutAgent>(
                 static_cast<std::size_t>(config.strategy_donchian_lookback));
         }},
        {{"ma_cross",
          "均线交叉",
          StrategyStyle::Trend,
          "日频",
          "快慢均线价差作为趋势方向和强度。",
          true},
         [](const RuntimeConfig& config) {
             return std::make_unique<MovingAverageCrossAgent>(
                 static_cast<std::size_t>(config.strategy_ma_cross_fast_window),
                 static_cast<std::size_t>(config.strategy_ma_cross_slow_window));
         }},
        {{"macd_trend",
          "MACD 趋势",
          StrategyStyle::Trend,
          "日频",
          "用快慢 EMA 差和信号线判断趋势动量。",
          true},
         [](const RuntimeConfig& config) {
             return std::make_unique<MacdTrendAgent>(
                 config.strategy_macd_fast_alpha,
                 config.strategy_macd_slow_alpha,
                 config.strategy_macd_signal_alpha);
         }},
        {{"ema_slope_trend",
          "EMA 斜率趋势",
          StrategyStyle::Trend,
          "日频/分钟",
          "用递推 EMA 斜率识别短周期趋势方向。",
          true},
         [](const RuntimeConfig& config) {
             return std::make_unique<EmaSlopeTrendAgent>(
                 config.strategy_ema_slope_alpha,
                 config.strategy_ema_slope_min_slope);
         }},
        {{"keltner_breakout",
          "Keltner 通道突破",
          StrategyStyle::Trend,
          "日频/分钟",
          "用上一周期 EMA 与 ATR 通道判断突破。",
          true},
         [](const RuntimeConfig& config) {
             return std::make_unique<KeltnerBreakoutAgent>(
                 config.strategy_keltner_alpha,
                 config.strategy_keltner_multiplier);
         }},
        {{"volume_spike_momentum",
          "量能放大动量",
          StrategyStyle::Trend,
          "分钟",
          "成交量显著高于递推均量时跟随同向价格变动。",
          true},
         [](const RuntimeConfig& config) {
             return std::make_unique<VolumeSpikeMomentumAgent>(
                 config.strategy_volume_spike_alpha,
                 config.strategy_volume_spike_multiplier);
         }},
        {{"micro_scalper",
          "微结构剥头皮",
          StrategyStyle::Hybrid,
          "分钟/高频",
          "用分钟 bar 的实体、区间和相邻收盘收益代理短周期冲击方向。",
          true},
         [](const RuntimeConfig& config) {
             return std::make_unique<MicroScalperAgent>(
                 config.strategy_micro_scalper_min_return,
                 config.strategy_micro_scalper_min_body_ratio);
         }},
        {{"spread_capture_maker",
          "价差捕获做市",
          StrategyStyle::Hybrid,
          "分钟/做市",
          "用 fair price EMA 和 bar 区间代理中轴与价差，价格偏离时做反向信号。",
          true},
         [](const RuntimeConfig& config) {
             return std::make_unique<SpreadCaptureMakerAgent>(
                 config.strategy_spread_capture_alpha,
                 config.strategy_spread_capture_threshold);
         }},
        {{"order_flow_imbalance",
          "订单流失衡",
          StrategyStyle::Hybrid,
          "分钟/高频",
          "用收盘位置和成交量放大代理主动买卖压力。",
          true},
         [](const RuntimeConfig& config) {
             return std::make_unique<OrderFlowImbalanceAgent>(
                 config.strategy_order_flow_volume_alpha,
                 config.strategy_order_flow_imbalance_threshold);
         }},
        {{"inventory_skew_maker",
          "库存倾斜做市",
          StrategyStyle::Hybrid,
          "分钟/做市",
          "根据当前持仓权重输出反向信号，模拟做市商控制库存回到中性。",
          true},
         [](const RuntimeConfig& config) {
             return std::make_unique<InventorySkewMakerAgent>(
                 config.strategy_inventory_skew_neutral_band);
         }},
        {{"bollinger_reversion",
          "布林带反转",
          StrategyStyle::MeanReversion,
          "日频",
          "价格偏离滚动均值超过阈值时做反向信号。",
          true},
         [](const RuntimeConfig& config) {
             return std::make_unique<BollingerReversionAgent>(
                 static_cast<std::size_t>(config.strategy_bollinger_window),
                 config.strategy_bollinger_band_width);
         }},
        {{"rsi_reversion",
          "RSI 反转",
          StrategyStyle::MeanReversion,
          "日频",
          "RSI 高位视作过热、低位视作超卖。",
          true},
         [](const RuntimeConfig& config) {
             return std::make_unique<RsiReversionAgent>(
                 static_cast<std::size_t>(config.strategy_rsi_window),
                 config.strategy_rsi_oversold,
                 config.strategy_rsi_overbought);
         }},
        {{"zscore_reversion",
          "Z-score 反转",
          StrategyStyle::MeanReversion,
          "日频/分钟",
          "价格偏离滚动均值超过阈值时做轻量反向信号。",
          true},
         [](const RuntimeConfig& config) {
             return std::make_unique<ZScoreReversionAgent>(
                 static_cast<std::size_t>(config.strategy_zscore_window),
                 config.strategy_zscore_threshold);
         }},
        {{"range_fade",
          "区间边缘反转",
          StrategyStyle::MeanReversion,
          "日频",
          "收盘靠近日内区间边缘时押注回到区间内部。",
          true},
         [](const RuntimeConfig&) { return std::make_unique<RangeFadeAgent>(); }},
        // GAP-037: LLM 特征推理智能体
        {{"llm_feature",
          "LLM 特征推理",
          StrategyStyle::Hybrid,
          "可变",
          "通过多维特征交互分析和异常检测生成交易信号，模拟 LLM in-context reasoning。",
          false},  // 默认关闭，需显式配置启用
         [](const RuntimeConfig&) { return std::make_unique<agent::LLMFeatureAgent>(); }},
    };
    return registry;
}

const StrategyRegistration& find_registration(const std::string& id) {
    for (const auto& registration : strategy_registry()) {
        if (registration.descriptor.id == id) {
            return registration;
        }
    }
    throw std::runtime_error("unknown strategy id: " + id);
}

}  // namespace

std::string_view to_string(StrategyStyle style) {
    switch (style) {
        case StrategyStyle::Trend:
            return "trend";
        case StrategyStyle::MeanReversion:
            return "mean_reversion";
        case StrategyStyle::Defensive:
            return "defensive";
        case StrategyStyle::Hybrid:
            return "hybrid";
    }
    return "unknown";
}

const std::vector<StrategyDescriptor>& strategy_catalog() {
    static const std::vector<StrategyDescriptor> catalog = [] {
        std::vector<StrategyDescriptor> descriptors;
        for (const auto& registration : strategy_registry()) {
            descriptors.push_back(registration.descriptor);
        }
        return descriptors;
    }();
    return catalog;
}

std::vector<std::string> default_strategy_ids() {
    std::vector<std::string> ids;
    for (const auto& strategy : strategy_catalog()) {
        if (strategy.default_enabled) {
            ids.push_back(strategy.id);
        }
    }
    return ids;
}

std::vector<std::unique_ptr<ISignalAgent>> make_signal_agents(
    const std::vector<std::string>& strategy_ids) {
    RuntimeConfig config = default_config();
    config.strategy_ids = strategy_ids;
    return make_signal_agents(config);
}

std::vector<std::unique_ptr<ISignalAgent>> make_signal_agents(
    const RuntimeConfig& config) {
    const auto ids = config.strategy_ids.empty() ? default_strategy_ids() : config.strategy_ids;
    std::vector<std::unique_ptr<ISignalAgent>> agents;
    agents.reserve(ids.size());

    for (const auto& id : ids) {
        agents.push_back(find_registration(id).build(config));
    }
    return agents;
}

}  // namespace qt
