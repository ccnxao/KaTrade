#pragma once

#include <memory>
#include <string>
#include <string_view>
#include <vector>

#include "qt/agents.hpp"

namespace qt {

struct RuntimeConfig;

enum class StrategyStyle {
    Trend,
    MeanReversion,
    Defensive,
    Hybrid,
};

struct StrategyDescriptor {
    std::string id;
    std::string display_name;
    StrategyStyle style{StrategyStyle::Hybrid};
    std::string horizon;
    std::string description;
    bool default_enabled{false};
};

std::string_view to_string(StrategyStyle style);
const std::vector<StrategyDescriptor>& strategy_catalog();
std::vector<std::string> default_strategy_ids();
std::vector<std::unique_ptr<ISignalAgent>> make_signal_agents(
    const std::vector<std::string>& strategy_ids);
std::vector<std::unique_ptr<ISignalAgent>> make_signal_agents(
    const RuntimeConfig& config);

}  // namespace qt
