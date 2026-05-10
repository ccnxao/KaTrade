#include "qt/backend/order/order_read_model.hpp"

#include <algorithm>
#include <cctype>
#include <optional>

#include "qt/backend/common/json.hpp"

namespace qt::backend {

static std::optional<std::string> json_get_string_after_anchor(std::string_view object,
                                                               std::string_view anchor,
                                                               std::string_view key) {
    const std::string needle = "\"" + std::string(anchor) + "\"";
    const auto pos = object.find(needle);
    if (pos == std::string_view::npos) {
        return std::nullopt;
    }
    return json_get_string(object.substr(pos + needle.size()), key);
}

static std::string to_lower_ascii(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    return value;
}

std::string normalize_order_state(std::string state) {
    state = to_lower_ascii(std::move(state));
    if (state == "submitted" || state == "pending_maker" || state == "pending_tick_maker" || state == "live") {
        return "pending";
    }
    if (state == "partiallyfilled") {
        return "partially_filled";
    }
    if (state == "canceled" || state == "cancelled" || state == "mmp_canceled") {
        return "cancelled";
    }
    if (state.empty()) {
        return "unknown";
    }
    return state;
}

std::string order_key_from_event(const std::string& line) {
    if (auto key = json_get_string(line, "order_key"); key && !key->empty()) {
        return *key;
    }
    const auto session = json_get_string(line, "paper_session_id").value_or("unknown");
    const auto order = json_get_string(line, "order_id").value_or("unknown");
    return session + ":" + order;
}

std::vector<OrderReadModel> reduce_order_events(const std::vector<std::string>& events) {
    std::map<std::string, OrderReadModel> states;
    for (const auto& line : events) {
        if (!looks_like_json_object(line)) {
            continue;
        }
        const auto key = order_key_from_event(line);
        auto& row = states[key];
        row.key = key;
        row.source_order_id = json_get_string(line, "source_order_id").value_or(row.source_order_id);
        row.session_id = json_get_string(line, "paper_session_id").value_or(row.session_id);
        row.order_id = json_get_string(line, "order_id").value_or(row.order_id);
        row.inst_id = json_get_string(line, "inst_id").value_or(row.inst_id);
        row.source = json_get_string(line, "source").value_or(row.source);
        row.strategy_id = json_get_string(line, "strategy_id").value_or(row.strategy_id);
        row.agent_id = json_get_string(line, "agent_id").value_or(row.agent_id);
        row.trading_unit_id = json_get_string(line, "trading_unit_id").value_or(row.trading_unit_id);
        row.trading_unit_name = json_get_string(line, "trading_unit_name").value_or(row.trading_unit_name);
        row.parent_decision_id = json_get_string(line, "parent_decision_id").value_or(row.parent_decision_id);
        row.side = json_get_string(line, "side").value_or(row.side);
        row.order_type = json_get_string(line, "order_type").value_or(row.order_type);
        row.time_in_force = json_get_string(line, "time_in_force").value_or(row.time_in_force);
        row.broker_status = json_get_string(line, "broker_status").value_or(row.broker_status);
        row.broker_state = json_get_string(line, "broker_state").value_or(row.broker_state);
        row.reason = json_get_string(line, "reason").value_or(row.reason);
        row.updated_at = json_get_string(line, "ts").value_or(row.updated_at);
        row.updated_ms = json_get_int(line, "ts_ms").value_or(row.updated_ms);
        if (row.created_at.empty()) {
            row.created_at = row.updated_at;
        }

        const auto type = json_get_string(line, "type").value_or("");
        if (type == "order.created") {
            row.quantity = json_get_double(line, "quantity").value_or(row.quantity);
            row.remaining_qty = json_get_double(line, "remaining_qty").value_or(row.remaining_qty);
            row.limit_price = json_get_double(line, "limit_price").value_or(row.limit_price);
            row.state = normalize_order_state(json_get_string(line, "state").value_or("pending"));
        } else if (type == "order.fill") {
            const double filled = json_get_double(line, "filled_qty").value_or(0.0);
            row.filled_qty += filled;
            row.remaining_qty = json_get_double(line, "remaining_qty").value_or(std::max(row.quantity - row.filled_qty, 0.0));
            row.avg_price = json_get_double(line, "avg_price").value_or(json_get_double(line, "fill_price").value_or(row.avg_price));
            row.commission += json_get_double(line, "commission").value_or(0.0);
            row.position_effect = json_get_string(line, "position_effect").value_or(row.position_effect);
            row.close_gross_pnl += json_get_double(line, "close_gross_pnl").value_or(0.0);
            row.close_fee += json_get_double(line, "close_fee").value_or(0.0);
            row.close_net_pnl += json_get_double(line, "close_net_pnl").value_or(0.0);
            row.closed_qty += json_get_double(line, "closed_qty").value_or(0.0);
            row.opened_qty += json_get_double(line, "opened_qty").value_or(0.0);
            row.broker_order_id = json_get_string(line, "broker_order_id").value_or(row.broker_order_id);
            row.broker_cl_ord_id = json_get_string(line, "broker_cl_ord_id").value_or(row.broker_cl_ord_id);
            row.state = normalize_order_state(json_get_string(line, "state").value_or(
                row.remaining_qty <= 1e-12 ? "filled" : "partially_filled"));
        } else if (type == "order.expired") {
            row.remaining_qty = json_get_double(line, "remaining_qty").value_or(row.remaining_qty);
            row.limit_price = json_get_double(line, "limit_price").value_or(row.limit_price);
            row.state = "expired";
        } else if (type == "order.broker_sync") {
            row.broker_order_id = json_get_string(line, "broker_order_id").value_or(row.broker_order_id);
            row.broker_cl_ord_id = json_get_string(line, "broker_cl_ord_id").value_or(row.broker_cl_ord_id);
            row.broker_state = json_get_string(line, "broker_state").value_or(row.broker_state);
            row.broker_updated_at = json_get_string(line, "broker_updated_at").value_or(row.broker_updated_at);
            row.avg_price = json_get_double(line, "broker_avg_price").value_or(row.avg_price);
            row.limit_price = json_get_double(line, "limit_price").value_or(row.limit_price);
            row.filled_qty = json_get_double(line, "broker_filled_base_qty").value_or(
                json_get_double(line, "broker_filled_qty").value_or(row.filled_qty));
            row.quantity = std::max(row.quantity, json_get_double(line, "broker_order_base_qty").value_or(row.quantity));
            row.remaining_qty = std::max(row.quantity - row.filled_qty, 0.0);
            row.broker_order_qty = json_get_double(line, "broker_order_qty").value_or(row.broker_order_qty);
            row.broker_order_base_qty = json_get_double(line, "broker_order_base_qty").value_or(row.broker_order_base_qty);
            row.broker_filled_qty = json_get_double(line, "broker_filled_qty").value_or(row.broker_filled_qty);
            row.broker_filled_base_qty = json_get_double(line, "broker_filled_base_qty").value_or(row.broker_filled_base_qty);
            row.broker_contract_value = json_get_double(line, "broker_contract_value").value_or(row.broker_contract_value);
            row.state = normalize_order_state(json_get_string(line, "broker_state").value_or(
                json_get_string(line, "state").value_or(row.state)));
        } else if (type.find("cancel") != std::string::npos) {
            row.state = "cancelled";
        }
        if (row.source_order_id.empty()) {
            row.source_order_id = row.key;
        }
    }

    std::vector<OrderReadModel> out;
    out.reserve(states.size());
    for (auto& [_, row] : states) {
        out.push_back(std::move(row));
    }
    std::sort(out.begin(), out.end(), [](const auto& lhs, const auto& rhs) {
        if (lhs.updated_ms != rhs.updated_ms) {
            return lhs.updated_ms > rhs.updated_ms;
        }
        return lhs.key > rhs.key;
    });
    return out;
}

std::map<std::string, int> count_order_states(const std::vector<OrderReadModel>& rows) {
    std::map<std::string, int> counts;
    for (const auto& row : rows) {
        counts[row.state]++;
    }
    return counts;
}

std::unordered_map<std::string, ExecutionTraceReadModel> reduce_execution_traces(
    const std::vector<std::string>& rows) {
    std::unordered_map<std::string, ExecutionTraceReadModel> latest;
    for (const auto& line : rows) {
        if (!looks_like_json_object(line)) {
            continue;
        }
        const auto source_order_id = json_get_string(line, "source_order_id").value_or("");
        if (source_order_id.empty()) {
            continue;
        }
        const auto ts_ms = json_get_int(line, "ts_ms").value_or(0);
        auto it = latest.find(source_order_id);
        if (it != latest.end() && it->second.ts_ms > ts_ms) {
            continue;
        }
        ExecutionTraceReadModel row;
        row.source_order_id = source_order_id;
        row.status = json_get_string(line, "status").value_or("");
        row.message = json_get_string(line, "message").value_or("");
        row.trace_key = json_get_string(line, "trace_key").value_or(json_get_string(line, "id").value_or(""));
        row.tradeability_status = json_get_string(line, "tradeability_status").value_or("");
        row.ts = json_get_string(line, "ts").value_or("");
        row.ts_ms = ts_ms;
        row.approved = json_get_bool(line, "approved").value_or(false);
        row.planned_notional = json_get_double(line, "planned_notional").value_or(0.0);
        latest[source_order_id] = std::move(row);
    }
    return latest;
}

static bool audit_action_is_terminal(std::string action) {
    std::transform(action.begin(), action.end(), action.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    return action.find("cancel") != std::string::npos || action.find("filled") != std::string::npos;
}

std::unordered_map<std::string, AuditOrderReadModel> reduce_okx_audit_orders(
    const std::vector<std::string>& rows) {
    std::unordered_map<std::string, AuditOrderReadModel> latest;
    for (const auto& line : rows) {
        if (!looks_like_json_object(line)) {
            continue;
        }
        const auto source_order_id = json_get_string(line, "source_order_id").value_or("");
        if (source_order_id.empty()) {
            continue;
        }
        AuditOrderReadModel row;
        row.source_order_id = source_order_id;
        row.action = json_get_string(line, "action").value_or("");
        row.audit_id = json_get_string(line, "id").value_or("");
        row.ts = json_get_string(line, "ts").value_or("");
        row.ok = json_get_bool(line, "ok").value_or(false);
        row.state = normalize_order_state(json_get_string_after_anchor(line, "order_detail", "state")
                                              .value_or(json_get_string(line, "state").value_or("")));
        row.ord_id = json_get_string_after_anchor(line, "order_detail", "ord_id")
                         .value_or(json_get_string(line, "ordId").value_or(""));
        row.cl_ord_id = json_get_string_after_anchor(line, "order_detail", "cl_ord_id")
                            .value_or(json_get_string(line, "clOrdId").value_or(""));
        if (row.state == "unknown" && audit_action_is_terminal(row.action)) {
            row.state = row.action.find("cancel") != std::string::npos ? "cancelled" : "filled";
        }
        latest[source_order_id] = std::move(row);
    }
    return latest;
}

}  // namespace qt::backend
