#include <exception>
#include <iomanip>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

#include "qt/backtest_engine.hpp"
#include "qt/event_bus.hpp"
#include "qt/oms.hpp"
#include "qt/replay_data.hpp"
#include "qt/trader_engine.hpp"

namespace {

void print_cycle(const qt::CycleResult& result) {
    std::cout << "\n=== " << result.cycle_label << " ===\n";
    std::cout << "Regime: " << qt::to_string(result.regime.regime)
              << " (confidence=" << std::fixed << std::setprecision(2)
              << result.regime.confidence << ")\n";
    std::cout << "Features: ret=" << result.features.at("market.ret_20d")
              << ", vol=" << result.features.at("market.realized_vol_20d")
              << ", adx=" << result.features.at("market.adx_20d")
              << ", corr=" << result.features.at("market.avg_corr_20d") << "\n";

    std::cout << "Signals:\n";
    for (const auto& signal : result.signals) {
        std::cout << "  - " << signal.strategy_id << " -> "
                  << qt::instrument_key(signal.instrument)
                  << " score=" << signal.score
                  << " confidence=" << signal.confidence << "\n";
    }

    std::cout << "Risk: " << qt::to_string(result.risk_decision.action)
              << " (" << result.risk_decision.reason << ")\n";
    std::cout << "Target portfolio:\n";
    for (const auto& position : result.risk_decision.adjusted_portfolio.positions) {
        std::cout << "  - " << qt::instrument_key(position.instrument)
                  << " weight=" << position.target_weight << "\n";
    }
    std::cout << "Pre-trade equity=" << result.pre_trade_portfolio.equity
              << " cash=" << result.pre_trade_portfolio.cash
              << " gross=" << qt::gross_exposure(result.pre_trade_portfolio) << "\n";

    std::cout << "OMS records:\n";
    for (const auto& record : result.order_records) {
        std::cout << "  - " << record.order_id
                  << " " << qt::to_string(record.intent.side)
                  << " " << record.intent.quantity
                  << " of " << qt::instrument_key(record.intent.instrument)
                  << " status=" << qt::to_string(record.status)
                  << " remaining=" << record.remaining_qty << "\n";
    }

    std::cout << "Reports:\n";
    for (const auto& report : result.reports) {
        std::cout << "  - " << report.order_id << " "
                  << qt::instrument_key(report.instrument)
                  << " fill_qty=" << report.last_fill_qty
                  << " fill_px=" << report.last_fill_price
                  << " avg_px=" << report.avg_price
                  << " remaining=" << report.remaining_qty
                  << " status=" << qt::to_string(report.status)
                  << " slippage_bps=" << report.slippage_bps << "\n";
    }
    std::cout << "Post-trade equity=" << result.post_trade_portfolio.equity
              << " cash=" << result.post_trade_portfolio.cash
              << " realized=" << result.post_trade_portfolio.realized_pnl
              << " unrealized=" << result.post_trade_portfolio.unrealized_pnl
              << "\n";
}

void print_event_stream(const qt::EventBus& event_bus) {
    std::cout << "\nEvent stream:\n";
    for (const auto& event : event_bus.history()) {
        std::cout << "  [" << event.sequence << "] " << qt::describe_event(event)
                  << "\n";
    }
}

void print_report(const qt::BacktestReport& report) {
    std::cout << "\n=== Backtest summary ===\n";
    std::cout << "Cycles: " << report.cycles.size() << "\n";
    std::cout << "Events: " << report.event_count << "\n";
    std::cout << "Fills: " << report.total_fills << "\n";
    std::cout << "Commission: " << std::fixed << std::setprecision(2)
              << report.total_commission << "\n";
    std::cout << "Total return: " << report.total_return * 100.0 << "%\n";
    std::cout << "Max drawdown: " << report.max_drawdown * 100.0 << "%\n";

    std::cout << "Equity curve:\n";
    for (const auto& point : report.equity_curve) {
        std::cout << "  - " << point.label
                  << " equity=" << point.equity
                  << " cash=" << point.cash
                  << " gross=" << point.gross_exposure << "\n";
    }
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const std::string replay_path =
            argc > 1 ? argv[1] : "data/sample_bars.csv";
        std::cout << "Replay file: " << replay_path << "\n";

        qt::EventBus event_bus;
        std::vector<std::unique_ptr<qt::ISignalAgent>> agents;
        agents.push_back(std::make_unique<qt::MomentumAgent>());
        agents.push_back(std::make_unique<qt::MeanReversionAgent>());
        agents.push_back(std::make_unique<qt::DefensiveAgent>());

        qt::TraderEngine engine(
            std::make_unique<qt::RuleBasedRegimeAgent>(),
            std::move(agents),
            std::make_unique<qt::SimplePortfolioOptimizer>(0.35, 0.90),
            std::make_unique<qt::RiskAgent>(0.30, 0.80),
            std::make_unique<qt::NaiveExecutionAlgo>(),
            std::make_unique<qt::OrderManagementSystem>(
                std::make_unique<qt::PaperBrokerGateway>(0.04)),
            1'000'000.0,
            &event_bus);

        const auto steps = qt::CsvReplayLoader::load(replay_path);
        qt::BacktestEngine backtest(engine, &event_bus);
        const auto report = backtest.run(steps);

        for (const auto& cycle : report.cycles) {
            print_cycle(cycle);
        }
        print_event_stream(event_bus);
        print_report(report);

        return 0;
    } catch (const std::exception& ex) {
        std::cerr << "fatal: " << ex.what() << "\n";
        return 1;
    }
}
