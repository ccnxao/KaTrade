#include "qt/backend/account/account_read_model.hpp"
#include "qt/backend/common/service_context.hpp"

#include <chrono>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {

void require(bool ok, const std::string& message) {
    if (!ok) {
        throw std::runtime_error(message);
    }
}

void require_near(double actual, double expected, double epsilon, const std::string& message) {
    if (std::abs(actual - expected) > epsilon) {
        throw std::runtime_error(message + ": actual=" + std::to_string(actual) +
                                 " expected=" + std::to_string(expected));
    }
}

void write_text(const std::filesystem::path& path, const std::string& text) {
    std::filesystem::create_directories(path.parent_path());
    std::ofstream out(path, std::ios::trunc);
    if (!out) {
        throw std::runtime_error("failed to write " + path.string());
    }
    out << text;
}

std::filesystem::path make_temp_root() {
    const auto nonce = std::chrono::duration_cast<std::chrono::nanoseconds>(
                           std::chrono::steady_clock::now().time_since_epoch())
                           .count();
    return std::filesystem::temp_directory_path() /
           ("katrade_account_read_model_check_" + std::to_string(nonce));
}

void write_fixture(const std::filesystem::path& root) {
    write_text(root / "config" / "default.cfg", "initial_cash=1000000\n");
    write_text(root / "logs" / "execution_ledger" / "events.jsonl",
               "{\"event_type\":\"submit\",\"source_order_id\":\"s1:open\",\"strategy_id\":\"mean_reversion\",\"agent_id\":\"agent-a\",\"trading_unit_id\":\"unit_reversion\",\"inst_id\":\"BTC-USDT-SWAP\",\"side\":\"buy\"}\n"
               "{\"event_type\":\"submit\",\"source_order_id\":\"s1:close\",\"strategy_id\":\"mean_reversion\",\"agent_id\":\"agent-a\",\"trading_unit_id\":\"unit_reversion\",\"inst_id\":\"BTC-USDT-SWAP\",\"side\":\"sell\"}\n");
    write_text(root / "logs" / "okx_reference" / "instruments_swap.json",
               "{\"instruments\":[{\"inst_id\":\"BTC-USDT-SWAP\",\"ct_type\":\"linear\",\"ct_val\":\"0.01\"}]}\n");
    write_text(root / "logs" / "market_stream" / "okx_public.jsonl",
               "{\"channel\":\"tickers\",\"inst_id\":\"BTC-USDT-SWAP\",\"ts\":1700000005000,\"rows\":[{\"last\":\"120\",\"bid\":\"119.9\",\"ask\":\"120.1\",\"timestamp\":\"1700000005000\"}]}\n");
    write_text(root / "logs" / "paper_trading" / "latest_report.json",
               "{\"final_equity\":1000003.8,\"equity_curve\":[{\"cycle_index\":1,\"label\":\"2026-01-01T00:00:00Z\",\"equity\":1000000,\"cash\":1000000,\"gross_exposure\":0,\"realized_pnl\":0,\"unrealized_pnl\":0}]}\n");
    write_text(root / "logs" / "order_journal" / "orders.jsonl",
               "{\"type\":\"order.created\",\"paper_session_id\":\"s1\",\"order_id\":\"open\",\"source_order_id\":\"s1:open\",\"inst_id\":\"BTC-USDT-SWAP\",\"side\":\"buy\",\"strategy_id\":\"mean_reversion\",\"agent_id\":\"agent-a\",\"trading_unit_id\":\"unit_reversion\",\"quantity\":2,\"limit_price\":100,\"state\":\"live\",\"ts\":\"2026-01-01T00:00:00Z\",\"ts_ms\":1700000000000,\"strategy_attribution\":[{\"strategy_id\":\"mean_reversion\",\"share\":1,\"weighted_score\":1,\"net_score\":1}]}\n"
               "{\"type\":\"order.fill\",\"paper_session_id\":\"s1\",\"order_id\":\"open\",\"source_order_id\":\"s1:open\",\"inst_id\":\"BTC-USDT-SWAP\",\"side\":\"buy\",\"filled_qty\":2,\"fill_price\":100,\"avg_price\":100,\"commission\":1,\"closed_qty\":0,\"opened_qty\":2,\"close_gross_pnl\":0,\"close_fee\":0,\"close_net_pnl\":0,\"ts\":\"2026-01-01T00:00:01Z\",\"ts_ms\":1700000001000,\"strategy_attribution\":[{\"strategy_id\":\"mean_reversion\",\"share\":1,\"weighted_score\":1,\"net_score\":1}]}\n"
               "{\"type\":\"order.created\",\"paper_session_id\":\"s1\",\"order_id\":\"close\",\"source_order_id\":\"s1:close\",\"inst_id\":\"BTC-USDT-SWAP\",\"side\":\"sell\",\"strategy_id\":\"mean_reversion\",\"agent_id\":\"agent-a\",\"trading_unit_id\":\"unit_reversion\",\"quantity\":0.5,\"limit_price\":110,\"state\":\"live\",\"ts\":\"2026-01-01T00:00:02Z\",\"ts_ms\":1700000002000,\"strategy_attribution\":[{\"strategy_id\":\"mean_reversion\",\"share\":1,\"weighted_score\":1,\"net_score\":1}]}\n"
               "{\"type\":\"order.fill\",\"paper_session_id\":\"s1\",\"order_id\":\"close\",\"source_order_id\":\"s1:close\",\"inst_id\":\"BTC-USDT-SWAP\",\"side\":\"sell\",\"filled_qty\":0.5,\"fill_price\":110,\"avg_price\":110,\"commission\":0.5,\"closed_qty\":0.5,\"opened_qty\":0,\"close_gross_pnl\":5,\"close_fee\":0.5,\"close_net_pnl\":4.5,\"ts\":\"2026-01-01T00:00:03Z\",\"ts_ms\":1700000003000,\"strategy_attribution\":[{\"strategy_id\":\"mean_reversion\",\"share\":1,\"weighted_score\":1,\"net_score\":1}]}\n");
}

void account_model_replays_fills_and_marks_linear_swap() {
    const auto root = make_temp_root();
    try {
        write_fixture(root);
        qt::backend::BackendConfig config;
        config.root = root;
        config.config_path = "config/default.cfg";
        qt::backend::ServiceContext ctx(config);

        const auto portfolio = qt::backend::build_portfolio_read_model(ctx, 100, 10);
        require(portfolio.fill_count == 2, "portfolio should replay two fills");
        require(portfolio.close_fill_count == 1, "portfolio should identify one close fill");
        require_near(portfolio.total_commission, 1.5, 1e-9, "portfolio commission mismatch");
        require_near(portfolio.total_close_net_pnl, 4.5, 1e-9, "portfolio close net pnl mismatch");
        require(portfolio.marked_position_count == 1, "open linear swap should be marked from ticker");
        require_near(portfolio.total_unrealized_pnl, 0.3, 1e-9, "portfolio unrealized pnl mismatch");

        const auto pos_it = portfolio.positions.find("BTC-USDT-SWAP");
        require(pos_it != portfolio.positions.end(), "BTC-USDT-SWAP position should exist");
        const auto& position = pos_it->second;
        require(position.side == "long", "position side should be long");
        require_near(position.net_qty, 1.5, 1e-9, "position net qty mismatch");
        require_near(position.avg_entry_price, 100.0, 1e-9, "position average entry mismatch");
        require_near(position.mark_price, 120.0, 1e-9, "position mark price mismatch");
        require_near(position.contract_value, 0.01, 1e-12, "position contract value mismatch");
        require(position.mark_source == "exact_ticker", "position should use exact ticker mark");

        const auto strategy_it = portfolio.by_strategy.find("mean_reversion");
        require(strategy_it != portfolio.by_strategy.end(), "strategy attribution should exist");
        require_near(strategy_it->second.close_net_pnl, 4.5, 1e-9, "strategy close net pnl mismatch");
        require_near(strategy_it->second.win_count, 1.0, 1e-9, "strategy win count mismatch");

        const auto equity = qt::backend::build_equity_curve_read_model(ctx, 10, "latest", 100);
        require(equity.latest_session == "s1", "latest paper session should be resolved");
        require(equity.fill_events_scanned == 2, "equity model should scan two fills");
        require_near(equity.cpp_realized_final_equity, 1000003.5, 1e-9, "realized equity mismatch");
        require_near(equity.cpp_open_unrealized_pnl, 0.3, 1e-9, "equity unrealized pnl mismatch");
        require_near(equity.cpp_mark_to_market_equity, 1000003.8, 1e-9, "mark-to-market equity mismatch");
        require(!equity.mark_to_market_points.empty(), "mark-to-market curve should contain snapshot");

        std::filesystem::remove_all(root);
    } catch (...) {
        std::filesystem::remove_all(root);
        throw;
    }
}

}  // namespace

int main() {
    try {
        account_model_replays_fills_and_marks_linear_swap();
    } catch (const std::exception& exc) {
        std::cerr << "account_read_model_check failed: " << exc.what() << "\n";
        return 1;
    }
    std::cout << "account_read_model_check passed\n";
    return 0;
}
