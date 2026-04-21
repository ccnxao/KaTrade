#include <iomanip>
#include <iostream>
#include <memory>
#include <vector>

#include "qt/trader_engine.hpp"

namespace {

std::vector<qt::Bar> trending_snapshot() {
    return {
        {{"AAPL", "NASDAQ"}, 180.0, 187.0, 179.0, 186.5, 2'500'000.0},
        {{"MSFT", "NASDAQ"}, 410.0, 421.0, 408.0, 420.0, 2'000'000.0},
        {{"GLD", "ARCA"}, 213.0, 214.0, 212.0, 213.8, 800'000.0},
    };
}

std::vector<qt::Bar> crisis_snapshot() {
    return {
        {{"AAPL", "NASDAQ"}, 186.5, 187.0, 168.0, 171.0, 4'100'000.0},
        {{"MSFT", "NASDAQ"}, 420.0, 422.0, 385.0, 392.0, 3'600'000.0},
        {{"GLD", "ARCA"}, 213.8, 220.0, 213.0, 219.2, 1'700'000.0},
    };
}

void print_cycle(const std::string& label, const qt::CycleResult& result) {
    std::cout << "\n=== " << label << " ===\n";
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

    std::cout << "Orders:\n";
    for (const auto& order : result.orders) {
        std::cout << "  - " << qt::to_string(order.side)
                  << " " << order.quantity
                  << " of " << qt::instrument_key(order.instrument)
                  << " @ ref " << order.reference_price << "\n";
    }

    std::cout << "Reports:\n";
    for (const auto& report : result.reports) {
        std::cout << "  - " << report.order_id << " "
                  << qt::instrument_key(report.instrument)
                  << " qty=" << report.filled_qty
                  << " avg_px=" << report.avg_price
                  << " slippage_bps=" << report.slippage_bps << "\n";
    }
}

}  // namespace

int main() {
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
        std::make_unique<qt::PaperBrokerGateway>(),
        1'000'000.0);

    const auto cycle1 = engine.run_cycle(trending_snapshot());
    print_cycle("Cycle 1 - Trending market", cycle1);

    const auto cycle2 = engine.run_cycle(crisis_snapshot());
    print_cycle("Cycle 2 - Crisis market", cycle2);

    return 0;
}
