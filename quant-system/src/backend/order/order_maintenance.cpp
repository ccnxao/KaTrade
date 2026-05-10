#include "qt/backend/order/order_maintenance.hpp"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <set>

namespace qt::backend {

namespace {

std::string to_lower_ascii(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    return value;
}

bool trace_is_submitted(const ExecutionTraceReadModel* trace) {
    return trace != nullptr && trace->status == "submitted";
}

OrderConsistencyIssue make_order_issue(const OrderReadModel& row,
                                       const ExecutionTraceReadModel* trace,
                                       const AuditOrderReadModel* audit,
                                       const std::string& code,
                                       const std::string& severity,
                                       const std::string& message,
                                       const std::string& recommended_action,
                                       double age_seconds) {
    OrderConsistencyIssue issue;
    issue.code = code;
    issue.severity = severity;
    issue.message = message;
    issue.recommended_action = recommended_action;
    issue.age_seconds = age_seconds;
    issue.order = row;
    if (trace != nullptr) {
        issue.trace = *trace;
        issue.has_trace = true;
    }
    if (audit != nullptr) {
        issue.audit = *audit;
        issue.has_audit = true;
    }
    return issue;
}

std::string issue_order_key(const OrderConsistencyIssue& issue) {
    return issue.order.key.empty() ? issue.order.source_order_id : issue.order.key;
}

bool local_order_repair_actionable(const OrderConsistencyIssue& issue, int min_age_seconds) {
    if (!order_is_active(issue.order) || order_has_broker_identity(issue.order)) {
        return false;
    }
    if (issue.age_seconds < static_cast<double>(min_age_seconds)) {
        return false;
    }
    if (issue.has_trace && to_lower_ascii(issue.trace.status) == "submitted") {
        return false;
    }
    if (issue.has_audit) {
        if (!issue.audit.ord_id.empty() || !issue.audit.cl_ord_id.empty() || audit_state_is_live(&issue.audit)) {
            return false;
        }
    }
    return issue.code == "active_without_okx_submit" ||
           issue.code == "active_after_failed_execution" ||
           issue.code == "stale_active_order";
}

bool broker_terminal_sync_actionable(const OrderConsistencyIssue& issue) {
    if (issue.code != "broker_terminal_not_reflected_locally") {
        return false;
    }
    if (!order_is_active(issue.order) || !order_has_broker_identity(issue.order) || !issue.has_audit) {
        return false;
    }
    if (!audit_state_is_terminal(&issue.audit)) {
        return false;
    }
    if (issue.audit.state == "filled" &&
        issue.order.broker_filled_qty <= 1e-12 &&
        issue.order.broker_filled_base_qty <= 1e-12) {
        return false;
    }
    const bool same_ord = !issue.audit.ord_id.empty() && issue.audit.ord_id == issue.order.broker_order_id;
    const bool same_cl_ord = !issue.audit.cl_ord_id.empty() && issue.audit.cl_ord_id == issue.order.broker_cl_ord_id;
    return same_ord || same_cl_ord;
}

bool stale_broker_reconcile_actionable(const OrderConsistencyIssue& issue, int min_age_seconds) {
    if (issue.code != "stale_active_order") {
        return false;
    }
    if (!order_is_active(issue.order) || !order_has_broker_identity(issue.order)) {
        return false;
    }
    if (issue.age_seconds < static_cast<double>(min_age_seconds)) {
        return false;
    }
    // Broker terminal audits are handled by the terminal sync plan first.
    return !audit_state_is_terminal(issue.has_audit ? &issue.audit : nullptr);
}

void sort_and_cap_actions(OrderMaintenancePlan& plan, int max_orders) {
    const auto by_age_desc = [](const auto& lhs, const auto& rhs) {
        return lhs.age_seconds > rhs.age_seconds;
    };
    std::sort(plan.actions.begin(), plan.actions.end(), by_age_desc);
    std::sort(plan.keep.begin(), plan.keep.end(), by_age_desc);
    plan.actionable_total = plan.actions.size();
    if (plan.actions.size() > static_cast<std::size_t>(max_orders)) {
        plan.actions.resize(static_cast<std::size_t>(max_orders));
    }
}

}  // namespace

bool order_is_active(const OrderReadModel& row) {
    return row.state == "pending" || row.state == "partially_filled" || row.state == "live";
}

bool order_is_terminal_state(const std::string& state) {
    return state == "filled" || state == "expired" || state == "cancelled" || state == "rejected";
}

bool order_is_terminal(const OrderReadModel& row) {
    return order_is_terminal_state(row.state);
}

bool order_has_broker_identity(const OrderReadModel& row) {
    return !row.broker_order_id.empty() || !row.broker_cl_ord_id.empty();
}

bool audit_state_is_live(const AuditOrderReadModel* audit) {
    return audit != nullptr && (audit->state == "live" || audit->state == "pending");
}

bool audit_state_is_terminal(const AuditOrderReadModel* audit) {
    return audit != nullptr && order_is_terminal_state(audit->state);
}

OrderConsistencyModel build_order_consistency_model(
    const std::vector<OrderReadModel>& states,
    const std::unordered_map<std::string, ExecutionTraceReadModel>& traces,
    const std::unordered_map<std::string, AuditOrderReadModel>& audits,
    std::int64_t now_epoch_ms,
    int stale_seconds) {
    OrderConsistencyModel model;
    model.checked_orders = static_cast<int>(states.size());
    model.checked_traces = static_cast<int>(traces.size());
    model.checked_audits = static_cast<int>(audits.size());

    for (const auto& row : states) {
        const std::string source_order_id = row.source_order_id.empty() ? row.key : row.source_order_id;
        const auto trace_it = traces.find(source_order_id);
        const auto audit_it = audits.find(source_order_id);
        const ExecutionTraceReadModel* trace = trace_it == traces.end() ? nullptr : &trace_it->second;
        const AuditOrderReadModel* audit = audit_it == audits.end() ? nullptr : &audit_it->second;
        const bool active_order = order_is_active(row);
        const bool terminal_order = order_is_terminal(row);
        const bool has_broker_identity = order_has_broker_identity(row);
        const double age_seconds = row.updated_ms > 0
                                       ? static_cast<double>(now_epoch_ms - row.updated_ms) / 1000.0
                                       : -1.0;
        if (active_order) {
            ++model.active;
            if (row.updated_ms > 0 && now_epoch_ms - row.updated_ms > static_cast<std::int64_t>(stale_seconds) * 1000) {
                ++model.stale;
                model.issues.push_back(make_order_issue(
                    row,
                    trace,
                    audit,
                    "stale_active_order",
                    has_broker_identity ? "warn" : "halt",
                    has_broker_identity
                        ? "本地订单仍为活跃态且超过陈旧阈值，需要和 OKX 查询结果对齐。"
                        : "本地订单仍为活跃态、超过陈旧阈值，且没有 OKX 单号。",
                    has_broker_identity
                        ? "reconcile_okx_order_then_cancel_or_sync_fill"
                        : "expire_local_order_if_latest_trace_not_submitted",
                    age_seconds));
                model.issue_counts["stale_active_order"]++;
            }
            if (!has_broker_identity) {
                ++model.missing_broker_identity;
                if (trace == nullptr) {
                    ++model.active_without_recent_success_trace;
                    model.issues.push_back(make_order_issue(
                        row,
                        trace,
                        audit,
                        "active_without_okx_submit",
                        "halt",
                        "本地订单活跃，但没有 OKX 单号，也没有找到对应的执行轨迹。",
                        "expire_local_order_or_replay_submission_trace",
                        age_seconds));
                    model.issue_counts["active_without_okx_submit"]++;
                } else if (!trace_is_submitted(trace)) {
                    ++model.active_without_recent_success_trace;
                    ++model.active_after_failed_execution;
                    model.issues.push_back(make_order_issue(
                        row,
                        trace,
                        audit,
                        "active_after_failed_execution",
                        "halt",
                        "本地订单活跃，但最近执行轨迹不是 submitted，说明它没有真正挂到 OKX。",
                        "expire_local_order_after_confirming_no_broker_identity",
                        age_seconds));
                    model.issue_counts["active_after_failed_execution"]++;
                } else {
                    model.issues.push_back(make_order_issue(
                        row,
                        trace,
                        audit,
                        "active_without_broker_identity",
                        "warn",
                        "执行轨迹显示已提交，但本地订单尚未同步到 OKX ordId/clOrdId。",
                        "run_broker_sync_or_backfill_okx_identity",
                        age_seconds));
                    model.issue_counts["active_without_broker_identity"]++;
                }
            }
            if (audit_state_is_terminal(audit)) {
                ++model.broker_terminal_not_reflected_locally;
                model.issues.push_back(make_order_issue(
                    row,
                    trace,
                    audit,
                    "broker_terminal_not_reflected_locally",
                    "halt",
                    "OKX 审计显示订单已终态，但本地订单还处于活跃态。",
                    "backfill_broker_terminal_state_to_order_journal",
                    age_seconds));
                model.issue_counts["broker_terminal_not_reflected_locally"]++;
            }
        } else if (terminal_order && audit_state_is_live(audit)) {
            ++model.local_terminal_with_live_broker_audit;
            model.issues.push_back(make_order_issue(
                row,
                trace,
                audit,
                "local_terminal_with_live_broker_audit",
                "halt",
                "本地订单已终态，但最近 OKX 审计仍显示 live/pending。",
                "cancel_okx_live_order_or_sync_latest_broker_state",
                age_seconds));
            model.issue_counts["local_terminal_with_live_broker_audit"]++;
        }
    }

    std::stable_sort(model.issues.begin(), model.issues.end(), [](const auto& lhs, const auto& rhs) {
        const auto severity_rank = [](const std::string& severity) {
            if (severity == "halt") return 0;
            if (severity == "warn") return 1;
            return 2;
        };
        const int ls = severity_rank(lhs.severity);
        const int rs = severity_rank(rhs.severity);
        if (ls != rs) {
            return ls < rs;
        }
        return lhs.age_seconds > rhs.age_seconds;
    });
    return model;
}

OrderMaintenancePlan build_local_order_repair_plan(const OrderConsistencyModel& model,
                                                   int min_age_seconds,
                                                   int max_orders,
                                                   bool enabled) {
    OrderMaintenancePlan plan;
    plan.candidate_issues = static_cast<int>(model.issues.size());
    std::set<std::string> seen;
    for (const auto& issue : model.issues) {
        const auto order_key = issue_order_key(issue);
        if (order_key.empty() || seen.find(order_key) != seen.end()) {
            continue;
        }
        seen.insert(order_key);
        const bool eligible = enabled && local_order_repair_actionable(issue, min_age_seconds);
        if (eligible) {
            plan.actions.push_back(issue);
        } else {
            plan.keep.push_back(issue);
        }
    }
    sort_and_cap_actions(plan, max_orders);
    return plan;
}

OrderMaintenancePlan build_broker_terminal_sync_plan(const OrderConsistencyModel& model,
                                                     int max_orders,
                                                     bool enabled) {
    OrderMaintenancePlan plan;
    plan.candidate_issues = model.broker_terminal_not_reflected_locally + model.local_terminal_with_live_broker_audit;
    std::set<std::string> seen;
    for (const auto& issue : model.issues) {
        if (issue.code != "broker_terminal_not_reflected_locally" &&
            issue.code != "local_terminal_with_live_broker_audit") {
            continue;
        }
        const auto order_key = issue_order_key(issue);
        if (order_key.empty() || seen.find(order_key) != seen.end()) {
            continue;
        }
        seen.insert(order_key);
        const bool eligible = enabled && broker_terminal_sync_actionable(issue);
        if (eligible) {
            plan.actions.push_back(issue);
        } else {
            plan.keep.push_back(issue);
        }
    }
    sort_and_cap_actions(plan, max_orders);
    return plan;
}

OrderMaintenancePlan build_stale_broker_reconcile_plan(const OrderConsistencyModel& model,
                                                       int min_age_seconds,
                                                       int max_orders,
                                                       bool enabled) {
    OrderMaintenancePlan plan;
    std::set<std::string> seen;
    for (const auto& issue : model.issues) {
        if (issue.code != "stale_active_order" || !order_has_broker_identity(issue.order)) {
            continue;
        }
        ++plan.candidate_issues;
        const auto order_key = issue_order_key(issue);
        if (order_key.empty() || seen.find(order_key) != seen.end()) {
            continue;
        }
        seen.insert(order_key);
        const bool eligible = enabled && stale_broker_reconcile_actionable(issue, min_age_seconds);
        if (eligible) {
            plan.actions.push_back(issue);
        } else {
            plan.keep.push_back(issue);
        }
    }
    sort_and_cap_actions(plan, max_orders);
    return plan;
}

}  // namespace qt::backend
