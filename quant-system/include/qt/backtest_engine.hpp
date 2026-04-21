#pragma once

#include <span>
#include <string>
#include <vector>

#include "qt/event_bus.hpp"
#include "qt/trader_engine.hpp"

namespace qt {

struct BacktestStep {
    std::string label;
    std::vector<Bar> bars;
};

struct BacktestReport {
    std::vector<CycleResult> cycles;
    std::size_t event_count{};
    std::size_t total_fills{};
    double total_commission{};
};

class BacktestEngine {
public:
    BacktestEngine(TraderEngine& trader_engine, EventBus* event_bus = nullptr);

    BacktestReport run(std::span<const BacktestStep> steps);

private:
    TraderEngine& trader_engine_;
    EventBus* event_bus_;
};

}  // namespace qt
