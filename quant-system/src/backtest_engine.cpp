#include "qt/backtest_engine.hpp"

namespace qt {

BacktestEngine::BacktestEngine(TraderEngine& trader_engine, EventBus* event_bus)
    : trader_engine_(trader_engine), event_bus_(event_bus) {}

BacktestReport BacktestEngine::run(std::span<const BacktestStep> steps) {
    BacktestReport report;

    if (event_bus_ != nullptr) {
        event_bus_->clear();
    }

    for (const auto& step : steps) {
        auto cycle = trader_engine_.run_cycle(step.bars, step.label);
        for (const auto& fill : cycle.reports) {
            ++report.total_fills;
            report.total_commission += fill.commission;
        }
        report.cycles.push_back(std::move(cycle));
    }

    report.event_count = event_bus_ == nullptr ? 0 : event_bus_->history().size();
    return report;
}

}  // namespace qt
