#include <exception>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

#include "qt/backtest_engine.hpp"
#include "qt/event_bus.hpp"
#include "qt/oms.hpp"
#include "qt/report_io.hpp"
#include "qt/replay_data.hpp"
#include "qt/runtime_config.hpp"
#include "qt/strategy_module.hpp"
#include "qt/trader_engine.hpp"

int main(int argc, char** argv) {
    try {
        const std::string config_path =
            argc > 1 ? argv[1] : "config/default.cfg";
        const std::string golden_path =
            argc > 2 ? argv[2] : "tests/golden/sample_metrics.txt";

        const auto config = qt::load_runtime_config(config_path);
        const auto golden = qt::load_golden_metrics(golden_path);

        qt::EventBus event_bus;
        auto agents = qt::make_signal_agents(config);

        qt::TraderEngine engine(
            std::make_unique<qt::RuleBasedRegimeAgent>(),
            std::move(agents),
            std::make_unique<qt::SimplePortfolioOptimizer>(
                config.optimizer_max_single_weight,
                config.optimizer_max_gross),
            std::make_unique<qt::RiskAgent>(config.risk_max_single_weight,
                                            config.risk_max_gross),
            std::make_unique<qt::NaiveExecutionAlgo>(
                config.execution_min_rebalance_delta),
            std::make_unique<qt::OrderManagementSystem>(
                std::make_unique<qt::PaperBrokerGateway>(
                    config.execution_max_participation_rate)),
            config.initial_cash,
            &event_bus);

        const auto steps = qt::ReplayDataSource::load(config);
        qt::BacktestEngine backtest(engine, &event_bus);
        const auto report = backtest.run(steps);

        std::string failure_reason;
        if (!qt::matches_golden_metrics(report, golden, &failure_reason)) {
            std::cerr << "replay check failed: " << failure_reason << "\n";
            qt::write_report_summary(report, "logs/last_replay_summary.txt");
            return 1;
        }

        std::cout << "replay check passed\n";
        std::cout << "final equity="
                  << (report.equity_curve.empty() ? 0.0
                                                  : report.equity_curve.back().equity)
                  << "\n";
        return 0;
    } catch (const std::exception& ex) {
        std::cerr << "fatal: " << ex.what() << "\n";
        return 1;
    }
}
