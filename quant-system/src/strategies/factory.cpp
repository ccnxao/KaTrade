#include "qt/strategy_module.hpp"

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
    // 策略注册表是策略模块的中心目录。
    // 新增策略时先补 descriptor，再补 build，避免工厂逻辑散落在业务代码里。
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
        {{"range_fade",
          "区间边缘反转",
          StrategyStyle::MeanReversion,
          "日频",
          "收盘靠近日内区间边缘时押注回到区间内部。",
          true},
         [](const RuntimeConfig&) { return std::make_unique<RangeFadeAgent>(); }},
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
    // 所有策略实例在这里创建，主程序只依赖 strategy.enabled。
    // unknown id 直接报错，避免配置拼写错误悄悄被忽略。
    const auto ids = config.strategy_ids.empty() ? default_strategy_ids() : config.strategy_ids;
    std::vector<std::unique_ptr<ISignalAgent>> agents;
    agents.reserve(ids.size());

    for (const auto& id : ids) {
        agents.push_back(find_registration(id).build(config));
    }
    return agents;
}

}  // namespace qt
