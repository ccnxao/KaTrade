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
        auto meta_agent = std::make_unique<qt::agent::MetaAgent>(
            std::make_unique<qt::agent::RuleBasedRegimeAgent>(
                config.regime_rule_crisis_vol,
                config.regime_rule_crisis_corr,
                config.regime_rule_trending_adx,
                config.regime_rule_trending_ret,
                config.regime_rule_trending_vol_cap,
                config.regime_rule_mean_revert_adx,
                config.regime_rule_mean_revert_vol_cap));
        auto agents = qt::make_signal_agents(config);
        auto risk_agent = std::make_unique<qt::RiskAgent>(
            config.risk_max_single_weight,
            config.risk_max_gross,
            config.risk_kill_switch);
        risk_agent->set_thresholds(
            config.risk_drawdown_limit,
            config.risk_vol_threshold,
            config.risk_vol_reduction,
            config.risk_stress_tolerance);
        auto execution = std::make_unique<qt::execution::NaiveExecutionAlgo>(
            config.execution_min_rebalance_delta);
        auto broker = std::make_unique<qt::execution::SimulatedBrokerGateway>(
            config.execution_max_participation_rate,
            config.execution_slippage_bps,
            config.execution_commission_bps,
            config.execution_partial_fill_prob);
        auto oms =
            std::make_unique<qt::execution::OrderManagementSystem>(std::move(broker));

        qt::TraderEngine engine(
            std::move(meta_agent),
            std::move(agents),
            std::make_unique<qt::SimplePortfolioOptimizer>(
                config.optimizer_max_single_weight,
                config.optimizer_max_gross),
            std::move(risk_agent),
            std::move(execution),
            std::move(oms),
            config.initial_cash,
            &event_bus);
        engine.set_execution_params(
            config.execution_slippage_bps,
            config.execution_commission_bps,
            config.execution_partial_fill_prob,
            config.execution_default_ord_type);

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
