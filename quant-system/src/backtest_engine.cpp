#include "qt/backtest_engine.hpp"

namespace qt {

BacktestEngine::BacktestEngine(TraderEngine& trader_engine, EventBus* event_bus)
    : trader_engine_(trader_engine), event_bus_(event_bus) {}

BacktestReport BacktestEngine::run(std::span<const BacktestStep> steps) {
    BacktestReport report;
    double peak_equity = 0.0;
    double initial_equity = 0.0;

    if (event_bus_ != nullptr) {
        event_bus_->clear();
    }

    for (const auto& step : steps) {
        auto cycle = trader_engine_.run_cycle(step.bars, step.label);
        for (const auto& fill : cycle.reports) {
            if (fill.last_fill_qty > 0.0) {
                ++report.total_fills;
            }
            report.total_commission += fill.commission;
        }

        const double equity = cycle.post_trade_portfolio.equity;
        if (report.equity_curve.empty()) {
            initial_equity = equity;
        }
        peak_equity = std::max(peak_equity, equity);
        if (peak_equity > 0.0) {
            report.max_drawdown =
                std::max(report.max_drawdown, (peak_equity - equity) / peak_equity);
        }

        report.equity_curve.push_back(EquityPoint{cycle.cycle_index,
                                                  cycle.cycle_label,
                                                  equity,
                                                  cycle.post_trade_portfolio.cash,
                                                  gross_exposure(cycle.post_trade_portfolio),
                                                  cycle.post_trade_portfolio.realized_pnl,
                                                  cycle.post_trade_portfolio
                                                      .unrealized_pnl});
        report.cycles.push_back(std::move(cycle));
    }

    report.event_count = event_bus_ == nullptr ? 0 : event_bus_->history().size();
    if (!report.equity_curve.empty() && initial_equity > 0.0) {
        report.total_return =
            report.equity_curve.back().equity / initial_equity - 1.0;
    }
    return report;
}

}  // namespace qt
