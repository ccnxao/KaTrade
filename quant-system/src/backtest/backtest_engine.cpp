#include "qt/backtest_engine.hpp"

#include <algorithm>
#include <cmath>

namespace qt {

BacktestEngine::BacktestEngine(TraderEngine& trader_engine, EventBus* event_bus)
    : trader_engine_(trader_engine), event_bus_(event_bus), metrics_options_{} {}

BacktestEngine::BacktestEngine(TraderEngine& trader_engine,
                               EventBus* event_bus,
                               BacktestMetricsOptions metrics_options)
    : trader_engine_(trader_engine),
      event_bus_(event_bus),
      metrics_options_(metrics_options) {
    metrics_options_.drawdown_stride =
        std::max<std::size_t>(1, metrics_options_.drawdown_stride);
}

BacktestReport BacktestEngine::run(std::span<const BacktestStep> steps) {
    BacktestReport report;
    double peak_equity = 0.0;
    double initial_equity = 0.0;
    double previous_equity = 0.0;
    double return_sum = 0.0;
    double return_square_sum = 0.0;
    std::size_t return_count = 0;
    double turnover_sum = 0.0;
    double cost_bps_sum = 0.0;
    double gross_sum = 0.0;

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
            previous_equity = equity;  // R21: 首周期也记录，使第二周期能计算收益
        }
        if (report.equity_curve.size() >= 1 && previous_equity > 0.0) {
            const double period_return = equity / previous_equity - 1.0;
            return_sum += period_return;
            return_square_sum += period_return * period_return;
            ++return_count;
        }
        previous_equity = equity;
        const std::size_t next_cycle_count = report.equity_curve.size() + 1;
        // R22: 始终追踪峰值，避免 stride 间漏计
        peak_equity = std::max(peak_equity, equity);
        const bool update_drawdown =
            metrics_options_.drawdown_stride <= 1 ||
            next_cycle_count % metrics_options_.drawdown_stride == 0 ||
            next_cycle_count == steps.size();
        if (update_drawdown && peak_equity > 0.0) {
            report.max_drawdown =
                std::max(report.max_drawdown, (peak_equity - equity) / peak_equity);
        }
        const double cycle_gross = gross_exposure(cycle.post_trade_portfolio);
        gross_sum += cycle_gross;
        report.max_gross_exposure = std::max(report.max_gross_exposure, cycle_gross);
        turnover_sum += cycle.risk_decision.adjusted_portfolio.expected_turnover;
        cost_bps_sum += cycle.risk_decision.adjusted_portfolio.expected_cost_bps;

        report.equity_curve.push_back(EquityPoint{cycle.cycle_index,
                                                  cycle.cycle_label,
                                                  equity,
                                                  cycle.post_trade_portfolio.cash,
                                                  cycle_gross,
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
    if (!report.equity_curve.empty()) {
        const double cycle_count = static_cast<double>(report.equity_curve.size());
        report.average_turnover = turnover_sum / cycle_count;
        report.average_cost_bps = cost_bps_sum / cycle_count;
        report.average_gross_exposure = gross_sum / cycle_count;
    }
    if (return_count > 1) {
        const double mean = return_sum / static_cast<double>(return_count);
        const double variance =
            (return_square_sum - return_sum * return_sum / static_cast<double>(return_count)) /
            static_cast<double>(return_count - 1);
        const double stddev = std::sqrt(std::max(variance, 0.0));
        if (stddev > 0.0) {
            report.annualized_sharpe = mean / stddev * std::sqrt(252.0);
        }
    }

    // GAP-030: 基准对比 (等权买入持有第一个品种)
    if (!steps.empty() && !report.equity_curve.empty()) {
        double bench_equity = initial_equity;
        double bench_peak = initial_equity;
        double bench_dd = 0.0;
        std::vector<double> bench_returns;
        for (const auto& step : steps) {
            if (step.bars.empty()) continue;
            double ret = 0.0;
            if (step.bars[0].open > 0.0) {
                ret = (step.bars[0].close - step.bars[0].open) / step.bars[0].open;
            }
            bench_returns.push_back(ret);
            bench_equity *= (1.0 + ret);
            bench_peak = std::max(bench_peak, bench_equity);
            bench_dd = std::max(bench_dd, 1.0 - bench_equity / bench_peak);
        }
        report.benchmark_return = initial_equity > 0.0 ? bench_equity / initial_equity - 1.0 : 0.0;
        report.excess_return = report.total_return - report.benchmark_return;
        if (bench_returns.size() > 1) {
            double bm = 0.0, bv = 0.0;
            for (auto r : bench_returns) bm += r;
            bm /= bench_returns.size();
            for (auto r : bench_returns) bv += (r - bm) * (r - bm);
            bv /= (bench_returns.size() - 1);
            double bstd = std::sqrt(std::max(bv, 0.0));
            report.benchmark_sharpe = bstd > 0.0 ? bm / bstd * std::sqrt(252.0) : 0.0;
        }
    }

    return report;
}

}  // namespace qt
