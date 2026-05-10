#include "qt/backend/api/route_registry.hpp"

#include "qt/backend/account/account_routes.hpp"

#include <algorithm>
#include <map>
#include <sstream>
#include <string_view>
#include <vector>

#include "qt/backend/common/json.hpp"
#include "qt/backend/order/order_maintenance.hpp"
#include "qt/backend/order/order_read_model.hpp"
#include "qt/backend/common/route_utils.hpp"
#include "qt/backend/common/service_context.hpp"

namespace qt::backend {

void RouteRegistry::add(std::string path, RouteHandler handler) {
    handlers_[std::move(path)] = std::move(handler);
}

bool RouteRegistry::contains(const std::string& path) const {
    return handlers_.find(path) != handlers_.end();
}

std::string RouteRegistry::handle(ServiceContext& context, const Request& request) const {
    const auto it = handlers_.find(request.path);
    if (it == handlers_.end()) {
        return "{"
               "\"ok\":false,"
               "\"error\":\"unknown backendd route\","
               "\"route\":" + json_quote(request.path) + ","
               "\"generated_at\":" + json_quote(context.now_iso()) +
               "}";
    }
    return it->second(context, request);
}

static int hex_value(char ch) {
    if (ch >= '0' && ch <= '9') return ch - '0';
    if (ch >= 'a' && ch <= 'f') return ch - 'a' + 10;
    if (ch >= 'A' && ch <= 'F') return ch - 'A' + 10;
    return -1;
}

static std::string url_decode(std::string_view value) {
    std::string out;
    out.reserve(value.size());
    for (std::size_t i = 0; i < value.size(); ++i) {
        if (value[i] == '+' ) {
            out.push_back(' ');
        } else if (value[i] == '%' && i + 2 < value.size()) {
            const int hi = hex_value(value[i + 1]);
            const int lo = hex_value(value[i + 2]);
            if (hi >= 0 && lo >= 0) {
                out.push_back(static_cast<char>((hi << 4) | lo));
                i += 2;
            } else {
                out.push_back(value[i]);
            }
        } else {
            out.push_back(value[i]);
        }
    }
    return out;
}

Request parse_route_request(std::string method, std::string target) {
    Request req;
    req.method = method.empty() ? "GET" : std::move(method);
    const auto qpos = target.find('?');
    req.path = qpos == std::string::npos ? target : target.substr(0, qpos);
    if (req.path.empty()) {
        req.path = "/api/backend/summary";
    }
    if (qpos != std::string::npos) {
        std::string query = target.substr(qpos + 1);
        std::istringstream iss(query);
        std::string item;
        while (std::getline(iss, item, '&')) {
            const auto eq = item.find('=');
            const auto key = url_decode(eq == std::string::npos ? item : item.substr(0, eq));
            const auto val = url_decode(eq == std::string::npos ? "" : item.substr(eq + 1));
            if (!key.empty()) {
                req.query[key] = val;
            }
        }
    }
    return req;
}

static std::string order_json(const OrderReadModel& row) {
    return "{"
           "\"order_key\":" + json_quote(row.key) + ","
           "\"source_order_id\":" + json_quote(row.source_order_id) + ","
           "\"paper_session_id\":" + json_quote(row.session_id) + ","
           "\"order_id\":" + json_quote(row.order_id) + ","
           "\"inst_id\":" + json_quote(row.inst_id) + ","
           "\"source\":" + json_quote(row.source) + ","
           "\"strategy_id\":" + json_quote(row.strategy_id) + ","
           "\"agent_id\":" + json_quote(row.agent_id) + ","
           "\"trading_unit_id\":" + json_quote(row.trading_unit_id) + ","
           "\"trading_unit_name\":" + json_quote(row.trading_unit_name) + ","
           "\"parent_decision_id\":" + json_quote(row.parent_decision_id) + ","
           "\"side\":" + json_quote(row.side) + ","
           "\"order_type\":" + json_quote(row.order_type) + ","
           "\"time_in_force\":" + json_quote(row.time_in_force) + ","
           "\"state\":" + json_quote(row.state) + ","
           "\"broker_status\":" + json_quote(row.broker_status) + ","
           "\"broker_state\":" + json_quote(row.broker_state) + ","
           "\"broker_order_id\":" + json_quote(row.broker_order_id) + ","
           "\"broker_cl_ord_id\":" + json_quote(row.broker_cl_ord_id) + ","
           "\"broker_updated_at\":" + json_quote(row.broker_updated_at) + ","
           "\"position_effect\":" + json_quote(row.position_effect) + ","
           "\"reason\":" + json_quote(row.reason) + ","
           "\"created_at\":" + json_quote(row.created_at) + ","
           "\"updated_at\":" + json_quote(row.updated_at) + ","
           "\"updated_ts_ms\":" + std::to_string(row.updated_ms) + ","
           "\"quantity\":" + json_double(row.quantity) + ","
           "\"filled_qty\":" + json_double(row.filled_qty) + ","
           "\"remaining_qty\":" + json_double(row.remaining_qty) + ","
           "\"avg_price\":" + json_double(row.avg_price) + ","
           "\"limit_price\":" + json_double(row.limit_price) + ","
           "\"commission\":" + json_double(row.commission) + ","
           "\"close_gross_pnl\":" + json_double(row.close_gross_pnl) + ","
           "\"close_fee\":" + json_double(row.close_fee) + ","
           "\"close_net_pnl\":" + json_double(row.close_net_pnl) + ","
           "\"closed_qty\":" + json_double(row.closed_qty) + ","
           "\"opened_qty\":" + json_double(row.opened_qty) + ","
           "\"broker_order_qty\":" + json_double(row.broker_order_qty) + ","
           "\"broker_order_base_qty\":" + json_double(row.broker_order_base_qty) + ","
           "\"broker_filled_qty\":" + json_double(row.broker_filled_qty) + ","
           "\"broker_filled_base_qty\":" + json_double(row.broker_filled_base_qty) + ","
           "\"broker_contract_value\":" + json_double(row.broker_contract_value) + ","
           "\"terminal\":" + json_bool(row.state == "filled" || row.state == "expired" || row.state == "cancelled" || row.state == "rejected") +
           "}";
}

static std::string orders_array_json(const std::vector<OrderReadModel>& rows, std::size_t limit) {
    std::ostringstream oss;
    oss << "[";
    bool first = true;
    for (std::size_t i = 0; i < rows.size() && i < limit; ++i) {
        if (!first) {
            oss << ",";
        }
        first = false;
        oss << order_json(rows[i]);
    }
    oss << "]";
    return oss.str();
}

static std::string order_state_payload(ServiceContext& ctx, const Request& req, bool include_events) {
    const int limit = query_int(req, "limit", 500, 1, 5000);
    const auto events = ctx.read_tail_lines(ctx.order_journal_path(), static_cast<std::size_t>(std::max(limit * 10, 1000)));
    const auto states = reduce_order_events(events);
    const auto counts = count_order_states(states);
    return "{"
           "\"ok\":true,"
           "\"service\":\"backendd\","
           "\"generated_at\":" + json_quote(ctx.now_iso()) + ","
           "\"journal_path\":" + json_quote(ctx.order_journal_path().string()) + ","
           "\"summary\":{\"orders\":" + std::to_string(states.size()) +
           ",\"events\":" + std::to_string(events.size()) +
           ",\"state_counts\":" + int_map_json(counts) + "},"
           "\"orders\":" + orders_array_json(states, static_cast<std::size_t>(limit)) +
           (include_events ? ",\"events\":" + json_object_array_from_lines(events, static_cast<std::size_t>(limit)) : "") +
           "}";
}

static std::string trace_payload(ServiceContext& ctx, const Request& req, bool include_events) {
    const int limit = query_int(req, "limit", 300, 1, 5000);
    const auto rows = ctx.read_tail_lines(ctx.execution_trace_path(), static_cast<std::size_t>(limit));
    std::map<std::string, int> status_counts;
    std::map<std::string, int> type_counts;
    std::map<std::string, int> tradeability_counts;
    double planned_notional = 0.0;
    for (const auto& row : rows) {
        status_counts[json_get_string(row, "status").value_or("unknown")]++;
        type_counts[json_get_string(row, "type").value_or("unknown")]++;
        tradeability_counts[json_get_string(row, "tradeability_status").value_or("unknown")]++;
        planned_notional += json_get_double(row, "planned_notional").value_or(0.0);
    }
    return "{"
           "\"ok\":true,"
           "\"service\":\"backendd\","
           "\"generated_at\":" + json_quote(ctx.now_iso()) + ","
           "\"journal_path\":" + json_quote(ctx.execution_trace_path().string()) + ","
           "\"summary\":{\"events\":" + std::to_string(rows.size()) +
           ",\"status_counts\":" + int_map_json(status_counts) +
           ",\"type_counts\":" + int_map_json(type_counts) +
           ",\"tradeability_counts\":" + int_map_json(tradeability_counts) +
           ",\"total_planned_notional_usdt\":" + json_double(planned_notional) + "}" +
           (include_events ? ",\"events\":" + json_object_array_from_lines(rows, static_cast<std::size_t>(limit)) : "") +
           "}";
}

static std::string okx_audit_summary(ServiceContext& ctx, int limit = 1000) {
    const auto rows = ctx.read_tail_lines(ctx.okx_audit_path(), static_cast<std::size_t>(limit));
    std::map<std::string, int> action_counts;
    int ok = 0;
    int failed = 0;
    for (const auto& row : rows) {
        action_counts[json_get_string(row, "action").value_or("unknown")]++;
        if (json_get_bool(row, "ok").value_or(false)) {
            ++ok;
        } else {
            ++failed;
        }
    }
    return "{"
           "\"events\":" + std::to_string(rows.size()) + ","
           "\"ok_events\":" + std::to_string(ok) + ","
           "\"failed_events\":" + std::to_string(failed) + ","
           "\"action_counts\":" + int_map_json(action_counts) +
           "}";
}

static std::string ledger_summary(ServiceContext& ctx, int limit = 1000) {
    const auto rows = ctx.read_tail_lines(ctx.execution_ledger_path(), static_cast<std::size_t>(limit));
    std::map<std::string, int> type_counts;
    std::map<std::string, int> error_counts;
    double close_pnl = 0.0;
    double fee = 0.0;
    for (const auto& row : rows) {
        type_counts[json_get_string(row, "event_type").value_or("unknown")]++;
        const auto error = json_get_string(row, "error_category").value_or("");
        if (!error.empty()) {
            error_counts[error]++;
        }
        close_pnl += json_get_double(row, "close_pnl").value_or(0.0);
        fee += json_get_double(row, "fee").value_or(0.0);
    }
    return "{"
           "\"events\":" + std::to_string(rows.size()) + ","
           "\"type_counts\":" + int_map_json(type_counts) + ","
           "\"error_counts\":" + int_map_json(error_counts) + ","
           "\"close_pnl\":" + json_double(close_pnl) + ","
           "\"fee\":" + json_double(fee) +
           "}";
}

static std::string market_quality_payload(ServiceContext& ctx) {
    const auto snap = ctx.file_snapshot(ctx.market_quality_path(), false);
    const auto raw = trim(ctx.read_text(ctx.market_quality_path(), 2'000'000));
    return "{"
           "\"ok\":" + json_bool(snap.exists && looks_like_json_object(raw)) + ","
           "\"service\":\"backendd\","
           "\"generated_at\":" + json_quote(ctx.now_iso()) + ","
           "\"file\":" + file_snapshot_json(snap) + ","
           "\"latest\":" + (looks_like_json_object(raw) ? raw : "{}") +
           "}";
}

static std::string consistency_issue_json(const OrderConsistencyIssue& issue) {
    const auto& row = issue.order;
    return "{"
           "\"code\":" + json_quote(issue.code) + ","
           "\"severity\":" + json_quote(issue.severity) + ","
           "\"message\":" + json_quote(issue.message) + ","
           "\"recommended_action\":" + json_quote(issue.recommended_action) + ","
           "\"order_key\":" + json_quote(row.key) + ","
           "\"source_order_id\":" + json_quote(row.source_order_id) + ","
           "\"paper_session_id\":" + json_quote(row.session_id) + ","
           "\"order_id\":" + json_quote(row.order_id) + ","
           "\"inst_id\":" + json_quote(row.inst_id) + ","
           "\"side\":" + json_quote(row.side) + ","
           "\"state\":" + json_quote(row.state) + ","
           "\"broker_status\":" + json_quote(row.broker_status) + ","
           "\"broker_state\":" + json_quote(row.broker_state) + ","
           "\"broker_order_id\":" + json_quote(row.broker_order_id) + ","
           "\"broker_cl_ord_id\":" + json_quote(row.broker_cl_ord_id) + ","
           "\"strategy_id\":" + json_quote(row.strategy_id) + ","
           "\"agent_id\":" + json_quote(row.agent_id) + ","
           "\"trading_unit_id\":" + json_quote(row.trading_unit_id) + ","
           "\"parent_decision_id\":" + json_quote(row.parent_decision_id) + ","
           "\"updated_at\":" + json_quote(row.updated_at) + ","
           "\"updated_ts_ms\":" + std::to_string(row.updated_ms) + ","
           "\"age_seconds\":" + json_double(issue.age_seconds) + ","
           "\"remaining_qty\":" + json_double(row.remaining_qty) + ","
           "\"limit_price\":" + json_double(row.limit_price) + ","
           "\"close_net_pnl\":" + json_double(row.close_net_pnl) + ","
           "\"latest_trace_status\":" + json_quote(issue.has_trace ? issue.trace.status : "") + ","
           "\"latest_trace_message\":" + json_quote(issue.has_trace ? issue.trace.message : "") + ","
           "\"latest_trace_key\":" + json_quote(issue.has_trace ? issue.trace.trace_key : "") + ","
           "\"latest_trace_ts\":" + json_quote(issue.has_trace ? issue.trace.ts : "") + ","
           "\"latest_trace_approved\":" + json_bool(issue.has_trace && issue.trace.approved) + ","
           "\"latest_trace_planned_notional\":" + json_double(issue.has_trace ? issue.trace.planned_notional : 0.0) + ","
           "\"latest_audit_action\":" + json_quote(issue.has_audit ? issue.audit.action : "") + ","
           "\"latest_audit_state\":" + json_quote(issue.has_audit ? issue.audit.state : "") + ","
           "\"latest_audit_id\":" + json_quote(issue.has_audit ? issue.audit.audit_id : "") + ","
           "\"latest_audit_ok\":" + json_bool(issue.has_audit && issue.audit.ok) + ","
           "\"latest_audit_ord_id\":" + json_quote(issue.has_audit ? issue.audit.ord_id : "") + ","
           "\"latest_audit_cl_ord_id\":" + json_quote(issue.has_audit ? issue.audit.cl_ord_id : "") +
           "}";
}

static bool issue_code_matches(const OrderConsistencyIssue& issue, const std::vector<std::string>& codes) {
    if (codes.empty()) {
        return true;
    }
    return std::find(codes.begin(), codes.end(), issue.code) != codes.end();
}

static std::string consistency_issues_array_json(const std::vector<OrderConsistencyIssue>& issues,
                                                 std::size_t limit,
                                                 const std::vector<std::string>& codes = {}) {
    std::ostringstream oss;
    oss << "[";
    bool first = true;
    std::size_t written = 0;
    for (const auto& issue : issues) {
        if (!issue_code_matches(issue, codes)) {
            continue;
        }
        if (written >= limit) {
            break;
        }
        if (!first) {
            oss << ",";
        }
        first = false;
        oss << consistency_issue_json(issue);
        ++written;
    }
    oss << "]";
    return oss.str();
}

static OrderConsistencyModel load_order_consistency_model(ServiceContext& ctx, int limit, int stale_seconds) {
    const auto events = ctx.read_tail_lines(ctx.order_journal_path(), static_cast<std::size_t>(std::max(limit * 10, 1000)));
    const auto states = reduce_order_events(events);
    const auto traces = reduce_execution_traces(
        ctx.read_tail_lines(ctx.execution_trace_path(), static_cast<std::size_t>(std::max(limit * 5, 1000))));
    const auto audits = reduce_okx_audit_orders(
        ctx.read_tail_lines(ctx.okx_audit_path(), static_cast<std::size_t>(std::max(limit * 5, 1000))));
    return build_order_consistency_model(states, traces, audits, ctx.now_epoch_ms(), stale_seconds);
}

static std::string consistency_summary_json(const OrderConsistencyModel& model) {
    return "{\"active_local_orders\":" + std::to_string(model.active) +
           ",\"stale_active_orders\":" + std::to_string(model.stale) +
           ",\"active_without_broker_identity\":" + std::to_string(model.missing_broker_identity) +
           ",\"active_without_recent_success_trace\":" + std::to_string(model.active_without_recent_success_trace) +
           ",\"active_after_failed_execution\":" + std::to_string(model.active_after_failed_execution) +
           ",\"local_terminal_with_live_broker_audit\":" + std::to_string(model.local_terminal_with_live_broker_audit) +
           ",\"broker_terminal_not_reflected_locally\":" + std::to_string(model.broker_terminal_not_reflected_locally) +
           ",\"issues\":" + std::to_string(model.issues.size()) +
           ",\"checked_orders\":" + std::to_string(model.checked_orders) +
           ",\"checked_traces\":" + std::to_string(model.checked_traces) +
           ",\"checked_audits\":" + std::to_string(model.checked_audits) +
           ",\"issue_counts\":" + int_map_json(model.issue_counts) + "}";
}

static std::string backend_summary(ServiceContext& ctx, const Request&) {
    // Health and status routes must stay O(1) with respect to log size.  Deep
    // scans belong in explicit drill-down routes, otherwise the Python UI shell
    // can mark backendd offline simply because journals have grown large.
    const auto order_file = ctx.file_snapshot(ctx.order_journal_path(), false);
    const auto trace_file = ctx.file_snapshot(ctx.execution_trace_path(), false);
    const auto ledger_file = ctx.file_snapshot(ctx.execution_ledger_path(), false);
    const auto audit_file = ctx.file_snapshot(ctx.okx_audit_path(), false);
    const auto quality_file = ctx.file_snapshot(ctx.market_quality_path(), false);
    return "{"
           "\"ok\":true,"
           "\"service\":\"backendd\","
           "\"version\":\"backendd.v1.full-skeleton\","
           "\"generated_at\":" + json_quote(ctx.now_iso()) + ","
           "\"root\":" + json_quote(ctx.root().string()) + ","
           "\"ownership\":{\"orders\":\"cpp_read_model\",\"account_positions\":\"cpp_read_model\",\"pnl_attribution\":\"cpp_read_model\",\"execution_trace\":\"cpp_read_model\",\"market_quality\":\"cpp_read_model\",\"strategy_decision\":\"migration_pending\",\"oms\":\"migration_pending\",\"okx_gateway\":\"migration_pending\"},"
           "\"files\":{\"order_journal\":" + file_snapshot_json(order_file) +
           ",\"execution_trace\":" + file_snapshot_json(trace_file) +
           ",\"execution_ledger\":" + file_snapshot_json(ledger_file) +
           ",\"okx_audit\":" + file_snapshot_json(audit_file) +
           ",\"market_quality\":" + file_snapshot_json(quality_file) + "},"
           "\"summaries\":{\"okx_audit\":" + okx_audit_summary(ctx, 1000) +
           ",\"execution_ledger\":" + ledger_summary(ctx, 1000) + "},"
           "\"migration\":{\"python_shell\":true,\"cpp_core\":true,\"note\":\"Python serves UI/proxy; backendd now owns the first C++ read models and is ready for strategy/OMS migration.\"}"
           "}";
}

static std::string orders_consistency(ServiceContext& ctx, const Request& req) {
    const int limit = query_int(req, "limit", 1000, 1, 5000);
    const int issue_limit = query_int(req, "issue_limit", 80, 1, 500);
    const int stale_seconds = query_int(req, "stale_seconds", 600, 30, 86400);
    const auto model = load_order_consistency_model(ctx, limit, stale_seconds);
    const bool ok = model.issues.empty();
    return "{"
           "\"ok\":" + json_bool(ok) + ","
           "\"service\":\"backendd\","
           "\"generated_at\":" + json_quote(ctx.now_iso()) + ","
           "\"route\":\"/api/backend/orders/consistency\","
           "\"parameters\":{\"limit\":" + std::to_string(limit) +
           ",\"issue_limit\":" + std::to_string(issue_limit) +
           ",\"stale_seconds\":" + std::to_string(stale_seconds) + "},"
           "\"summary\":" + consistency_summary_json(model) + ","
           "\"decision\":" + json_quote(ok ? "allow" : "review") + ","
           "\"message\":" + json_quote(ok ? "local order read model is consistent"
                                           : "active local orders need broker reconciliation") + ","
           "\"issues\":" + consistency_issues_array_json(model.issues, static_cast<std::size_t>(issue_limit)) + ","
           "\"stale_active_orders\":" + consistency_issues_array_json(
               model.issues, static_cast<std::size_t>(issue_limit), {"stale_active_order"}) + ","
           "\"active_without_broker_identity\":" + consistency_issues_array_json(
               model.issues,
               static_cast<std::size_t>(issue_limit),
               {"active_without_okx_submit", "active_after_failed_execution", "active_without_broker_identity"}) + ","
           "\"local_pending_without_recent_trace\":" + consistency_issues_array_json(
               model.issues,
               static_cast<std::size_t>(issue_limit),
               {"active_without_okx_submit", "active_after_failed_execution"}) + ","
           "\"local_terminal_with_live_broker_audit\":" + consistency_issues_array_json(
               model.issues, static_cast<std::size_t>(issue_limit), {"local_terminal_with_live_broker_audit"}) + ","
           "\"broker_terminal_not_reflected_locally\":" + consistency_issues_array_json(
               model.issues, static_cast<std::size_t>(issue_limit), {"broker_terminal_not_reflected_locally"}) +
           "}";
}

static std::string local_order_repair_row_json(const OrderConsistencyIssue& issue, bool eligible) {
    const auto& row = issue.order;
    return "{"
           "\"order_key\":" + json_quote(row.key) + ","
           "\"source_order_id\":" + json_quote(row.source_order_id) + ","
           "\"paper_session_id\":" + json_quote(row.session_id) + ","
           "\"order_id\":" + json_quote(row.order_id) + ","
           "\"inst_id\":" + json_quote(row.inst_id) + ","
           "\"side\":" + json_quote(row.side) + ","
           "\"state\":" + json_quote(row.state) + ","
           "\"broker_status\":" + json_quote(row.broker_status) + ","
           "\"broker_state\":" + json_quote(row.broker_state) + ","
           "\"broker_order_id\":" + json_quote(row.broker_order_id) + ","
           "\"broker_cl_ord_id\":" + json_quote(row.broker_cl_ord_id) + ","
           "\"remaining_qty\":" + json_double(row.remaining_qty) + ","
           "\"limit_price\":" + json_double(row.limit_price) + ","
           "\"age_seconds\":" + json_double(issue.age_seconds) + ","
           "\"issue_code\":" + json_quote(issue.code) + ","
           "\"latest_trace_status\":" + json_quote(issue.has_trace ? issue.trace.status : "") + ","
           "\"latest_trace_message\":" + json_quote(issue.has_trace ? issue.trace.message : "") + ","
           "\"latest_audit_state\":" + json_quote(issue.has_audit ? issue.audit.state : "") + ","
           "\"latest_audit_ord_id\":" + json_quote(issue.has_audit ? issue.audit.ord_id : "") + ","
           "\"latest_audit_cl_ord_id\":" + json_quote(issue.has_audit ? issue.audit.cl_ord_id : "") + ","
           "\"action\":" + json_quote(eligible ? "expire_local_order" : "keep") + ","
           "\"eligible\":" + json_bool(eligible) + ","
           "\"reason\":" + json_quote(
               eligible
                   ? "C++一致性诊断 " + issue.code + ": " + issue.message
                   : "未达到本地修复条件，或可能存在 OKX 侧订单，需要交给对账/撤单链路。") +
           "}";
}

static std::string local_order_repair_rows_json(const std::vector<OrderConsistencyIssue>& rows,
                                                std::size_t limit,
                                                bool eligible) {
    std::ostringstream oss;
    oss << "[";
    bool first = true;
    for (std::size_t i = 0; i < rows.size() && i < limit; ++i) {
        if (!first) {
            oss << ",";
        }
        first = false;
        oss << local_order_repair_row_json(rows[i], eligible);
    }
    oss << "]";
    return oss.str();
}

static std::string orders_local_repair_plan(ServiceContext& ctx, const Request& req) {
    const int limit = query_int(req, "limit", 5000, 1, 5000);
    const int min_age_seconds = query_int_any(req, {"min_age_seconds", "minAgeSeconds"}, 300, 30, 86400);
    const int max_orders = query_int_any(req, {"max_orders", "maxOrders"}, 20, 1, 200);
    const int stale_seconds = query_int(req, "stale_seconds", min_age_seconds, 30, 86400);
    const bool enabled = query_bool_any(req, {"enabled", "auto_apply_enabled"}, true);
    const auto model = load_order_consistency_model(ctx, limit, stale_seconds);

    const auto plan = build_local_order_repair_plan(model, min_age_seconds, max_orders, enabled);
    const bool consistency_ok = model.issues.empty();
    return "{"
           "\"ok\":" + json_bool(consistency_ok) + ","
           "\"service\":\"backendd\","
           "\"generated_at\":" + json_quote(ctx.now_iso()) + ","
           "\"route\":\"/api/backend/orders/local_repair_plan\","
           "\"execution_mode\":\"dry_run\","
           "\"auto_apply_enabled\":" + json_bool(enabled) + ","
           "\"min_age_seconds\":" + std::to_string(min_age_seconds) + ","
           "\"max_orders\":" + std::to_string(max_orders) + ","
           "\"stale_seconds\":" + std::to_string(stale_seconds) + ","
           "\"summary\":{\"consistency_issues\":" + std::to_string(model.issues.size()) +
           ",\"actionable\":" + std::to_string(plan.actions.size()) +
           ",\"actionable_total\":" + std::to_string(plan.actionable_total) +
           ",\"kept\":" + std::to_string(plan.keep.size()) +
           ",\"checked_orders\":" + std::to_string(model.checked_orders) + "},"
           "\"actions\":" + local_order_repair_rows_json(plan.actions, static_cast<std::size_t>(max_orders), true) + ","
           "\"keep\":" + local_order_repair_rows_json(plan.keep, static_cast<std::size_t>(max_orders), false) + ","
           "\"consistency\":{\"summary\":" + consistency_summary_json(model) +
           ",\"route\":\"/api/backend/orders/consistency\"}"
           "}";
}

static std::string broker_terminal_sync_row_json(const OrderConsistencyIssue& issue, bool eligible) {
    const auto& row = issue.order;
    return "{"
           "\"order_key\":" + json_quote(row.key) + ","
           "\"source_order_id\":" + json_quote(row.source_order_id) + ","
           "\"paper_session_id\":" + json_quote(row.session_id) + ","
           "\"order_id\":" + json_quote(row.order_id) + ","
           "\"inst_id\":" + json_quote(row.inst_id) + ","
           "\"side\":" + json_quote(row.side) + ","
           "\"local_state\":" + json_quote(row.state) + ","
           "\"broker_state\":" + json_quote(row.broker_state) + ","
           "\"broker_status\":" + json_quote(row.broker_status) + ","
           "\"broker_order_id\":" + json_quote(row.broker_order_id) + ","
           "\"broker_cl_ord_id\":" + json_quote(row.broker_cl_ord_id) + ","
           "\"broker_order_qty\":" + json_double(row.broker_order_qty) + ","
           "\"broker_order_base_qty\":" + json_double(row.broker_order_base_qty) + ","
           "\"broker_filled_qty\":" + json_double(row.broker_filled_qty) + ","
           "\"broker_filled_base_qty\":" + json_double(row.broker_filled_base_qty) + ","
           "\"broker_contract_value\":" + json_double(row.broker_contract_value) + ","
           "\"limit_price\":" + json_double(row.limit_price) + ","
           "\"age_seconds\":" + json_double(issue.age_seconds) + ","
           "\"audit_id\":" + json_quote(issue.has_audit ? issue.audit.audit_id : "") + ","
           "\"audit_action\":" + json_quote(issue.has_audit ? issue.audit.action : "") + ","
           "\"audit_state\":" + json_quote(issue.has_audit ? issue.audit.state : "") + ","
           "\"audit_ord_id\":" + json_quote(issue.has_audit ? issue.audit.ord_id : "") + ","
           "\"audit_cl_ord_id\":" + json_quote(issue.has_audit ? issue.audit.cl_ord_id : "") + ","
           "\"action\":" + json_quote(eligible ? "backfill_broker_terminal_state" : "keep") + ","
           "\"eligible\":" + json_bool(eligible) + ","
           "\"reason\":" + json_quote(
               eligible
                   ? "OKX 审计已经给出终态，本地订单仍活跃，可回写 order.broker_sync 终态。"
                   : "缺少可匹配的 OKX 终态审计或本地状态已不适合自动回补。") +
           "}";
}

static std::string broker_terminal_sync_rows_json(const std::vector<OrderConsistencyIssue>& rows,
                                                  std::size_t limit,
                                                  bool eligible) {
    std::ostringstream oss;
    oss << "[";
    bool first = true;
    for (std::size_t i = 0; i < rows.size() && i < limit; ++i) {
        if (!first) {
            oss << ",";
        }
        first = false;
        oss << broker_terminal_sync_row_json(rows[i], eligible);
    }
    oss << "]";
    return oss.str();
}

static std::string orders_broker_terminal_sync_plan(ServiceContext& ctx, const Request& req) {
    const int limit = query_int(req, "limit", 5000, 1, 5000);
    const int max_orders = query_int_any(req, {"max_orders", "maxOrders"}, 20, 1, 200);
    const int stale_seconds = query_int(req, "stale_seconds", 600, 30, 86400);
    const bool enabled = query_bool_any(req, {"enabled", "auto_apply_enabled"}, true);
    const auto model = load_order_consistency_model(ctx, limit, stale_seconds);

    const auto plan = build_broker_terminal_sync_plan(model, max_orders, enabled);
    return "{"
           "\"ok\":true,"
           "\"service\":\"backendd\","
           "\"generated_at\":" + json_quote(ctx.now_iso()) + ","
           "\"route\":\"/api/backend/orders/broker_terminal_sync_plan\","
           "\"execution_mode\":\"dry_run\","
           "\"auto_apply_enabled\":" + json_bool(enabled) + ","
           "\"max_orders\":" + std::to_string(max_orders) + ","
           "\"stale_seconds\":" + std::to_string(stale_seconds) + ","
           "\"summary\":{\"terminal_mismatch_issues\":" +
           std::to_string(model.broker_terminal_not_reflected_locally + model.local_terminal_with_live_broker_audit) +
           ",\"actionable\":" + std::to_string(plan.actions.size()) +
           ",\"actionable_total\":" + std::to_string(plan.actionable_total) +
           ",\"kept\":" + std::to_string(plan.keep.size()) +
           ",\"checked_orders\":" + std::to_string(model.checked_orders) + "},"
           "\"actions\":" + broker_terminal_sync_rows_json(plan.actions, static_cast<std::size_t>(max_orders), true) + ","
           "\"keep\":" + broker_terminal_sync_rows_json(plan.keep, static_cast<std::size_t>(max_orders), false) + ","
           "\"consistency\":{\"summary\":" + consistency_summary_json(model) +
           ",\"route\":\"/api/backend/orders/consistency\"}"
           "}";
}

static std::string stale_broker_reconcile_row_json(const OrderConsistencyIssue& issue, bool eligible) {
    const auto& row = issue.order;
    return "{"
           "\"order_key\":" + json_quote(row.key) + ","
           "\"source_order_id\":" + json_quote(row.source_order_id.empty() ? row.key : row.source_order_id) + ","
           "\"paper_session_id\":" + json_quote(row.session_id) + ","
           "\"order_id\":" + json_quote(row.order_id) + ","
           "\"inst_id\":" + json_quote(row.inst_id) + ","
           "\"side\":" + json_quote(row.side) + ","
           "\"local_state\":" + json_quote(row.state) + ","
           "\"broker_state\":" + json_quote(row.broker_state) + ","
           "\"broker_status\":" + json_quote(row.broker_status) + ","
           "\"broker_order_id\":" + json_quote(row.broker_order_id) + ","
           "\"broker_cl_ord_id\":" + json_quote(row.broker_cl_ord_id) + ","
           "\"broker_order_qty\":" + json_double(row.broker_order_qty) + ","
           "\"broker_order_base_qty\":" + json_double(row.broker_order_base_qty) + ","
           "\"broker_filled_qty\":" + json_double(row.broker_filled_qty) + ","
           "\"broker_filled_base_qty\":" + json_double(row.broker_filled_base_qty) + ","
           "\"broker_contract_value\":" + json_double(row.broker_contract_value) + ","
           "\"remaining_qty\":" + json_double(row.remaining_qty) + ","
           "\"limit_price\":" + json_double(row.limit_price) + ","
           "\"age_seconds\":" + json_double(issue.age_seconds) + ","
           "\"latest_trace_status\":" + json_quote(issue.has_trace ? issue.trace.status : "") + ","
           "\"latest_trace_key\":" + json_quote(issue.has_trace ? issue.trace.trace_key : "") + ","
           "\"latest_audit_id\":" + json_quote(issue.has_audit ? issue.audit.audit_id : "") + ","
           "\"latest_audit_action\":" + json_quote(issue.has_audit ? issue.audit.action : "") + ","
           "\"latest_audit_state\":" + json_quote(issue.has_audit ? issue.audit.state : "") + ","
           "\"action\":" + json_quote(eligible ? "query_okx_order_then_cancel_or_sync" : "keep") + ","
           "\"eligible\":" + json_bool(eligible) + ","
           "\"reason\":" + json_quote(
               eligible
                   ? "本地订单已陈旧且有 OKX 单号，需要主动查 OKX；若仍 live 则进入陈旧挂单撤单链路，若终态则回补本地 journal。"
                   : "未达到陈旧 OKX 订单主动对账条件，或已有终态审计应交给 broker_terminal_sync_plan。") +
           "}";
}

static std::string stale_broker_reconcile_rows_json(const std::vector<OrderConsistencyIssue>& rows,
                                                    std::size_t limit,
                                                    bool eligible) {
    std::ostringstream oss;
    oss << "[";
    bool first = true;
    for (std::size_t i = 0; i < rows.size() && i < limit; ++i) {
        if (!first) {
            oss << ",";
        }
        first = false;
        oss << stale_broker_reconcile_row_json(rows[i], eligible);
    }
    oss << "]";
    return oss.str();
}

static std::string orders_stale_broker_reconcile_plan(ServiceContext& ctx, const Request& req) {
    const int limit = query_int(req, "limit", 5000, 1, 5000);
    const int max_orders = query_int_any(req, {"max_orders", "maxOrders"}, 20, 1, 200);
    const int min_age_seconds = query_int_any(req, {"min_age_seconds", "minAgeSeconds"}, 180, 30, 86400);
    const bool enabled = query_bool_any(req, {"enabled", "auto_apply_enabled"}, true);
    const auto model = load_order_consistency_model(ctx, limit, min_age_seconds);

    const auto plan = build_stale_broker_reconcile_plan(model, min_age_seconds, max_orders, enabled);
    return "{"
           "\"ok\":true,"
           "\"service\":\"backendd\","
           "\"generated_at\":" + json_quote(ctx.now_iso()) + ","
           "\"route\":\"/api/backend/orders/stale_broker_reconcile_plan\","
           "\"execution_mode\":\"dry_run\","
           "\"auto_apply_enabled\":" + json_bool(enabled) + ","
           "\"min_age_seconds\":" + std::to_string(min_age_seconds) + ","
           "\"max_orders\":" + std::to_string(max_orders) + ","
           "\"summary\":{\"stale_broker_issues\":" + std::to_string(plan.candidate_issues) +
           ",\"actionable\":" + std::to_string(plan.actions.size()) +
           ",\"actionable_total\":" + std::to_string(plan.actionable_total) +
           ",\"kept\":" + std::to_string(plan.keep.size()) +
           ",\"checked_orders\":" + std::to_string(model.checked_orders) + "},"
           "\"actions\":" + stale_broker_reconcile_rows_json(plan.actions, static_cast<std::size_t>(max_orders), true) + ","
           "\"keep\":" + stale_broker_reconcile_rows_json(plan.keep, static_cast<std::size_t>(max_orders), false) + ","
           "\"consistency\":{\"summary\":" + consistency_summary_json(model) +
           ",\"route\":\"/api/backend/orders/consistency\"}"
           "}";
}

static std::string orders_center(ServiceContext& ctx, const Request& req) {
    const int limit = query_int(req, "limit", 500, 1, 5000);
    const int consistency_limit = query_int(req, "consistency_limit", 1000, 1, 5000);
    auto order_req = req;
    order_req.query["limit"] = std::to_string(limit);
    auto consistency_req = req;
    consistency_req.query["limit"] = std::to_string(consistency_limit);
    return "{"
           "\"ok\":true,"
           "\"service\":\"backendd\","
           "\"generated_at\":" + json_quote(ctx.now_iso()) + ","
           "\"order_state\":" + order_state_payload(ctx, order_req, false) + ","
           "\"execution_trace\":" + trace_payload(ctx, order_req, false) + ","
           "\"execution_ledger\":" + ledger_summary(ctx, limit) + ","
           "\"okx_audit\":" + okx_audit_summary(ctx, limit) + ","
           "\"consistency\":" + orders_consistency(ctx, consistency_req) +
           "}";
}

void register_backend_routes(RouteRegistry& registry) {
    registry.add("/api/health", [](ServiceContext& ctx, const Request&) {
        return "{\"ok\":true,\"service\":\"backendd\",\"generated_at\":" + json_quote(ctx.now_iso()) + "}";
    });
    registry.add("/api/backend/summary", backend_summary);
    registry.add("/api/backend/orders/summary", [](ServiceContext& ctx, const Request& req) {
        return order_state_payload(ctx, req, false);
    });
    registry.add("/api/backend/orders/state", [](ServiceContext& ctx, const Request& req) {
        return order_state_payload(ctx, req, true);
    });
    registry.add("/api/backend/orders/center", orders_center);
    registry.add("/api/backend/orders/consistency", orders_consistency);
    registry.add("/api/backend/orders/local_repair_plan", orders_local_repair_plan);
    registry.add("/api/backend/orders/broker_terminal_sync_plan", orders_broker_terminal_sync_plan);
    registry.add("/api/backend/orders/stale_broker_reconcile_plan", orders_stale_broker_reconcile_plan);
    register_account_routes(registry);
    registry.add("/api/backend/execution/trace_summary", [](ServiceContext& ctx, const Request& req) {
        return trace_payload(ctx, req, false);
    });
    registry.add("/api/backend/execution/trace", [](ServiceContext& ctx, const Request& req) {
        return trace_payload(ctx, req, true);
    });
    registry.add("/api/backend/market/quality", [](ServiceContext& ctx, const Request&) {
        return market_quality_payload(ctx);
    });
}

}  // namespace qt::backend
