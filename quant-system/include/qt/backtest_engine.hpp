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
    std::vector<EquityPoint> equity_curve;
    std::size_t event_count{};
    std::size_t total_fills{};
    double total_commission{};
    double total_return{};
    double max_drawdown{};
    double annualized_sharpe{};
    double average_turnover{};
    double average_cost_bps{};
    double average_gross_exposure{};
    double max_gross_exposure{};
    // GAP-030: 基准对比
    double benchmark_return{};
    double benchmark_sharpe{};
    double excess_return{};
};

struct BacktestMetricsOptions {
    std::size_t drawdown_stride{1};
};

class BacktestEngine {
public:
    BacktestEngine(TraderEngine& trader_engine, EventBus* event_bus = nullptr);
    BacktestEngine(TraderEngine& trader_engine,
                   EventBus* event_bus,
                   BacktestMetricsOptions metrics_options);

    BacktestReport run(std::span<const BacktestStep> steps);

private:
    TraderEngine& trader_engine_;
    EventBus* event_bus_;
    BacktestMetricsOptions metrics_options_;
};

}  // namespace qt
