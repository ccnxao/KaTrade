#include "qt/backend/account/account_routes.hpp"

#include <algorithm>
#include <cmath>
#include <map>
#include <sstream>
#include <string>
#include <vector>

#include "qt/backend/account/account_read_model.hpp"
#include "qt/backend/common/json.hpp"
#include "qt/backend/api/route_registry.hpp"
#include "qt/backend/common/route_utils.hpp"
#include "qt/backend/common/service_context.hpp"

namespace qt::backend {

static std::string position_json(const PositionReadModel& row) {
    const double mark_price = row.mark_price > 0.0
                                  ? row.mark_price
                                  : (row.last_fill_price > 0.0 ? row.last_fill_price : row.avg_entry_price);
    const double mark_notional = row.mark_notional > 0.0 ? row.mark_notional : row.abs_qty * mark_price;
    return "{"
           "\"inst_id\":" + json_quote(row.inst_id) + ","
           "\"side\":" + json_quote(row.side) + ","
           "\"net_qty\":" + json_double(row.net_qty) + ","
           "\"abs_qty\":" + json_double(row.abs_qty) + ","
           "\"avg_entry_price\":" + json_double(row.avg_entry_price) + ","
           "\"last_fill_price\":" + json_double(row.last_fill_price) + ","
           "\"mark_price\":" + json_double(mark_price) + ","
           "\"mark_notional\":" + json_double(mark_notional) + ","
           "\"unrealized_pnl\":" + json_double(row.unrealized_pnl) + ","
           "\"mark_source\":" + json_quote(row.mark_source) + ","
           "\"mark_inst_id\":" + json_quote(row.mark_inst_id) + ","
           "\"mark_ts_ms\":" + std::to_string(row.mark_ts_ms) + ","
           "\"mark_age_seconds\":" + json_double(row.mark_age_seconds) + ","
           "\"contract_value\":" + json_double(row.contract_value) + ","
           "\"contract_type\":" + json_quote(row.contract_type) + ","
           "\"buy_qty\":" + json_double(row.buy_qty) + ","
           "\"sell_qty\":" + json_double(row.sell_qty) + ","
           "\"notional\":" + json_double(row.notional) + ","
           "\"commission\":" + json_double(row.commission) + ","
           "\"realized_gross_pnl\":" + json_double(row.realized_gross_pnl) + ","
           "\"realized_net_pnl\":" + json_double(row.realized_net_pnl) + ","
           "\"fill_count\":" + json_double(row.fill_count) + ","
           "\"close_fill_count\":" + json_double(row.close_fill_count) + ","
           "\"last_fill_at\":" + json_quote(row.last_fill_at) +
           "}";
}

static std::string positions_array_json(const std::map<std::string, PositionReadModel>& rows) {
    std::vector<PositionReadModel> values;
    values.reserve(rows.size());
    for (const auto& [_, row] : rows) {
        values.push_back(row);
    }
    std::sort(values.begin(), values.end(), [](const auto& lhs, const auto& rhs) {
        if (lhs.abs_qty != rhs.abs_qty) {
            return lhs.abs_qty > rhs.abs_qty;
        }
        return lhs.inst_id < rhs.inst_id;
    });
    std::ostringstream oss;
    oss << "[";
    bool first = true;
    for (const auto& row : values) {
        if (row.abs_qty <= 1e-12 && row.fill_count <= 0.0) {
            continue;
        }
        if (!first) {
            oss << ",";
        }
        first = false;
        oss << position_json(row);
    }
    oss << "]";
    return oss.str();
}

static std::string attribution_row_json(const AttributionReadModel& row) {
    const double win_rate = row.close_fill_count > 1e-12 ? row.win_count / row.close_fill_count : 0.0;
    const double pnl_bps = row.notional > 1e-12 ? row.close_net_pnl / row.notional * 10000.0 : 0.0;
    return "{"
           "\"key\":" + json_quote(row.key) + ","
           "\"strategy_id\":" + json_quote(row.strategy_id) + ","
           "\"agent_id\":" + json_quote(row.agent_id) + ","
           "\"display_name\":" + json_quote(row.display_name) + ","
           "\"style\":" + json_quote(row.style) + ","
           "\"trading_unit_id\":" + json_quote(row.trading_unit_id) + ","
           "\"trading_unit_name\":" + json_quote(row.trading_unit_name) + ","
           "\"fill_count\":" + json_double(row.fill_count) + ","
           "\"close_fill_count\":" + json_double(row.close_fill_count) + ","
           "\"open_fill_count\":" + json_double(row.open_fill_count) + ","
           "\"win_count\":" + json_double(row.win_count) + ","
           "\"loss_count\":" + json_double(row.loss_count) + ","
           "\"win_rate\":" + json_double(win_rate) + ","
           "\"filled_qty\":" + json_double(row.filled_qty) + ","
           "\"closed_qty\":" + json_double(row.closed_qty) + ","
           "\"opened_qty\":" + json_double(row.opened_qty) + ","
           "\"notional\":" + json_double(row.notional) + ","
           "\"commission\":" + json_double(row.commission) + ","
           "\"close_gross_pnl\":" + json_double(row.close_gross_pnl) + ","
           "\"close_fee\":" + json_double(row.close_fee) + ","
           "\"close_net_pnl\":" + json_double(row.close_net_pnl) + ","
           "\"pnl_bps\":" + json_double(pnl_bps) + ","
           "\"last_fill_at\":" + json_quote(row.last_fill_at) + ","
           "\"attribution_sources\":" + double_map_json(row.attribution_sources) + ","
           "\"strategy_ids\":" + string_set_json(row.strategy_ids) +
           "}";
}

static std::string attribution_array_json(const std::map<std::string, AttributionReadModel>& rows) {
    std::vector<AttributionReadModel> values;
    values.reserve(rows.size());
    for (const auto& [_, row] : rows) {
        values.push_back(row);
    }
    std::sort(values.begin(), values.end(), [](const auto& lhs, const auto& rhs) {
        const double lp = std::abs(lhs.close_net_pnl);
        const double rp = std::abs(rhs.close_net_pnl);
        if (lp != rp) {
            return lp > rp;
        }
        return lhs.notional > rhs.notional;
    });
    std::ostringstream oss;
    oss << "[";
    bool first = true;
    for (const auto& row : values) {
        if (!first) {
            oss << ",";
        }
        first = false;
        oss << attribution_row_json(row);
    }
    oss << "]";
    return oss.str();
}

static std::string recent_fill_json(const RecentFillReadModel& row) {
    return "{"
           "\"ts\":" + json_quote(row.ts) + ","
           "\"source_order_id\":" + json_quote(row.source_order_id) + ","
           "\"order_id\":" + json_quote(row.order_id) + ","
           "\"inst_id\":" + json_quote(row.inst_id) + ","
           "\"side\":" + json_quote(row.side) + ","
           "\"strategy_id\":" + json_quote(row.strategy_id) + ","
           "\"agent_id\":" + json_quote(row.agent_id) + ","
           "\"trading_unit_id\":" + json_quote(row.trading_unit_id) + ","
           "\"filled_qty\":" + json_double(row.filled_qty) + ","
           "\"fill_price\":" + json_double(row.fill_price) + ","
           "\"closed_qty\":" + json_double(row.closed_qty) + ","
           "\"opened_qty\":" + json_double(row.opened_qty) + ","
           "\"close_net_pnl\":" + json_double(row.close_net_pnl) + ","
           "\"position_effect\":" + json_quote(row.position_effect) + ","
           "\"attribution_source\":" + json_quote(row.attribution_source) +
           "}";
}

static std::string recent_fills_json(const std::vector<RecentFillReadModel>& rows, std::size_t limit) {
    std::ostringstream oss;
    oss << "[";
    bool first = true;
    std::size_t written = 0;
    for (auto it = rows.rbegin(); it != rows.rend() && written < limit; ++it, ++written) {
        if (!first) {
            oss << ",";
        }
        first = false;
        oss << recent_fill_json(*it);
    }
    oss << "]";
    return oss.str();
}

static std::string equity_point_json(const EquityCurvePoint& point) {
    return "{"
           "\"label\":" + json_quote(point.label) + ","
           "\"ts\":" + json_quote(point.ts) + ","
           "\"ts_ms\":" + std::to_string(point.ts_ms) + ","
           "\"cycle_index\":" + std::to_string(point.cycle_index) + ","
           "\"source\":" + json_quote(point.source) + ","
           "\"source_order_id\":" + json_quote(point.source_order_id) + ","
           "\"inst_id\":" + json_quote(point.inst_id) + ","
           "\"run_id\":" + json_quote(point.run_id) + ","
           "\"equity\":" + json_double(point.equity) + ","
           "\"cash\":" + json_double(point.cash) + ","
           "\"gross_exposure\":" + json_double(point.gross_exposure) + ","
           "\"realized_pnl\":" + json_double(point.realized_pnl) + ","
           "\"unrealized_pnl\":" + json_double(point.unrealized_pnl) + ","
           "\"close_net_pnl\":" + json_double(point.close_net_pnl) + ","
           "\"cumulative_close_gross_pnl\":" + json_double(point.cumulative_close_gross_pnl) + ","
           "\"cumulative_commission\":" + json_double(point.cumulative_commission) + ","
           "\"cumulative_realized_net_pnl\":" + json_double(point.cumulative_realized_net_pnl) +
           "}";
}

static std::string equity_curve_points_json(const std::vector<EquityCurvePoint>& points) {
    std::ostringstream oss;
    oss << "[";
    bool first = true;
    for (const auto& point : points) {
        if (!first) {
            oss << ",";
        }
        first = false;
        oss << equity_point_json(point);
    }
    oss << "]";
    return oss.str();
}

static std::string equity_curve_summary_json(const EquityCurveReadModel& model) {
    return "{"
           "\"requested_session\":" + json_quote(model.requested_session) + ","
           "\"resolved_session\":" + json_quote(model.resolved_session.empty() ? "all" : model.resolved_session) + ","
           "\"latest_session\":" + json_quote(model.latest_session) + ","
           "\"initial_cash\":" + json_double(model.initial_cash) + ","
           "\"report_points\":" + std::to_string(model.report_points.size()) + ","
           "\"realized_points\":" + std::to_string(model.realized_points.size()) + ","
           "\"order_events_scanned\":" + std::to_string(model.order_events_scanned) + ","
           "\"fill_events_scanned\":" + std::to_string(model.fill_events_scanned) + ","
           "\"report_final_equity\":" + json_double(model.report_final_equity) + ","
           "\"cpp_realized_final_equity\":" + json_double(model.cpp_realized_final_equity) + ","
           "\"cpp_mark_to_market_equity\":" + json_double(model.cpp_mark_to_market_equity) + ","
           "\"cpp_open_unrealized_pnl\":" + json_double(model.cpp_open_unrealized_pnl) + ","
           "\"cpp_gross_mark_notional\":" + json_double(model.cpp_gross_mark_notional) + ","
           "\"marked_position_count\":" + std::to_string(model.marked_position_count) + ","
           "\"cpp_cumulative_close_gross_pnl\":" + json_double(model.cpp_cumulative_close_gross_pnl) + ","
           "\"cpp_cumulative_commission\":" + json_double(model.cpp_cumulative_commission) + ","
           "\"cpp_cumulative_realized_net_pnl\":" + json_double(model.cpp_cumulative_realized_net_pnl) + ","
           "\"primary_source\":" + json_quote(model.report_points.empty()
                                                   ? (model.mark_to_market_points.empty()
                                                          ? "cpp_order_fill_replay"
                                                          : "cpp_mark_to_market_snapshot")
                                                   : "paper_latest_report") + ","
           "\"method\":\"report equity curve with C++ order.fill realized replay and conservative ticker mark-to-market snapshot\""
           "}";
}

static std::string account_equity_payload(ServiceContext& ctx, const Request& req) {
    const int point_limit = query_int_any(req, {"limit", "points"}, 500, 1, 5000);
    const int order_limit = query_int(req, "order_limit", 50000, 100, 200000);
    const auto session_it = req.query.find("session");
    const std::string requested_session = session_it == req.query.end() ? "latest" : session_it->second;
    const auto model = build_equity_curve_read_model(ctx, point_limit, requested_session, order_limit);
    const auto& primary = model.report_points.empty()
                              ? (model.mark_to_market_points.empty() ? model.realized_points : model.mark_to_market_points)
                              : model.report_points;
    return "{"
           "\"ok\":true,"
           "\"service\":\"backendd\","
           "\"generated_at\":" + json_quote(ctx.now_iso()) + ","
           "\"route\":\"/api/backend/account/equity\","
           "\"parameters\":{\"limit\":" + std::to_string(point_limit) +
           ",\"order_limit\":" + std::to_string(order_limit) +
           ",\"session\":" + json_quote(model.requested_session) + "},"
           "\"source\":{\"order_journal_path\":" + json_quote(ctx.order_journal_path().string()) +
           ",\"paper_latest_report_path\":" + json_quote((ctx.root() / "logs" / "paper_trading" / "latest_report.json").string()) +
           ",\"market_stream_path\":" + json_quote((ctx.root() / "logs" / "market_stream" / "okx_public.jsonl").string()) +
           ",\"swap_instrument_cache_path\":" + json_quote((ctx.root() / "logs" / "okx_reference" / "instruments_swap.json").string()) +
           ",\"config_path\":" + json_quote((ctx.config().config_path.is_relative()
                                                ? (ctx.root() / ctx.config().config_path)
                                                : ctx.config().config_path).string()) + "},"
           "\"summary\":" + equity_curve_summary_json(model) + ","
           "\"equity_curve\":" + equity_curve_points_json(primary) + ","
           "\"report_equity_curve\":" + equity_curve_points_json(model.report_points) + ","
           "\"cpp_mark_to_market_curve\":" + equity_curve_points_json(model.mark_to_market_points) + ","
           "\"realized_equity_curve\":" + equity_curve_points_json(model.realized_points) +
           "}";
}

static std::string portfolio_summary_json(const PortfolioReadModel& model) {
    return "{"
           "\"order_events_scanned\":" + std::to_string(model.order_events_scanned) + ","
           "\"ledger_events_scanned\":" + std::to_string(model.ledger_events_scanned) + ","
           "\"fill_count\":" + std::to_string(model.fill_count) + ","
           "\"close_fill_count\":" + std::to_string(model.close_fill_count) + ","
           "\"unknown_fill_count\":" + std::to_string(model.unknown_fill_count) + ","
           "\"position_count\":" + std::to_string(model.positions.size()) + ","
           "\"marked_position_count\":" + std::to_string(model.marked_position_count) + ","
           "\"strategy_count\":" + std::to_string(model.by_strategy.size()) + ","
           "\"agent_count\":" + std::to_string(model.by_agent.size()) + ","
           "\"trading_unit_count\":" + std::to_string(model.by_trading_unit.size()) + ","
           "\"total_notional\":" + json_double(model.total_notional) + ","
           "\"total_mark_notional\":" + json_double(model.total_mark_notional) + ","
           "\"total_unrealized_pnl\":" + json_double(model.total_unrealized_pnl) + ","
           "\"total_commission\":" + json_double(model.total_commission) + ","
           "\"total_close_gross_pnl\":" + json_double(model.total_close_gross_pnl) + ","
           "\"total_close_fee\":" + json_double(model.total_close_fee) + ","
           "\"total_close_net_pnl\":" + json_double(model.total_close_net_pnl) + ","
           "\"attributed_close_net_pnl\":" + json_double(model.attributed_close_net_pnl) + ","
           "\"unknown_close_net_pnl\":" + json_double(model.unknown_close_net_pnl) + ","
           "\"reported_final_equity\":" + json_double(model.reported_final_equity) + ","
           "\"method\":\"order_journal.order.fill close PnL replayed in C++, joined with execution_ledger, and conservatively marked from OKX ticker stream\""
           "}";
}

static std::string account_portfolio_payload(ServiceContext& ctx,
                                             const Request& req,
                                             const std::string& view) {
    const int limit = query_int(req, "limit", 20000, 100, 100000);
    const int recent = query_int(req, "recent", 100, 0, 1000);
    const auto model = build_portfolio_read_model(ctx, limit, recent);
    std::string body = "{"
                       "\"ok\":true,"
                       "\"service\":\"backendd\","
                       "\"generated_at\":" + json_quote(ctx.now_iso()) + ","
                       "\"route\":" + json_quote("/api/backend/account/" + view) + ","
                       "\"parameters\":{\"limit\":" + std::to_string(limit) +
                       ",\"recent\":" + std::to_string(recent) + "},"
                       "\"source\":{\"order_journal_path\":" + json_quote(ctx.order_journal_path().string()) +
                       ",\"execution_ledger_path\":" + json_quote(ctx.execution_ledger_path().string()) +
                       ",\"paper_latest_report_path\":" + json_quote((ctx.root() / "logs" / "paper_trading" / "latest_report.json").string()) +
                       ",\"market_stream_path\":" + json_quote((ctx.root() / "logs" / "market_stream" / "okx_public.jsonl").string()) +
                       ",\"swap_instrument_cache_path\":" + json_quote((ctx.root() / "logs" / "okx_reference" / "instruments_swap.json").string()) + "},"
                       "\"summary\":" + portfolio_summary_json(model);
    if (view == "positions" || view == "portfolio") {
        body += ",\"positions\":" + positions_array_json(model.positions);
    }
    if (view == "pnl" || view == "portfolio") {
        body += ",\"recent_fills\":" + recent_fills_json(model.recent_fills, static_cast<std::size_t>(recent));
    }
    if (view == "attribution" || view == "portfolio") {
        body += ",\"by_strategy\":" + attribution_array_json(model.by_strategy) +
                ",\"by_agent\":" + attribution_array_json(model.by_agent) +
                ",\"by_trading_unit\":" + attribution_array_json(model.by_trading_unit);
        if (view == "attribution") {
            body += ",\"recent_fills\":" + recent_fills_json(model.recent_fills, static_cast<std::size_t>(recent));
        }
    }
    body += "}";
    return body;
}

void register_account_routes(RouteRegistry& registry) {
    registry.add("/api/backend/account/positions", [](ServiceContext& ctx, const Request& req) {
        return account_portfolio_payload(ctx, req, "positions");
    });
    registry.add("/api/backend/account/pnl", [](ServiceContext& ctx, const Request& req) {
        return account_portfolio_payload(ctx, req, "pnl");
    });
    registry.add("/api/backend/account/attribution", [](ServiceContext& ctx, const Request& req) {
        return account_portfolio_payload(ctx, req, "attribution");
    });
    registry.add("/api/backend/account/portfolio", [](ServiceContext& ctx, const Request& req) {
        return account_portfolio_payload(ctx, req, "portfolio");
    });
    registry.add("/api/backend/account/equity", account_equity_payload);
}

}  // namespace qt::backend
