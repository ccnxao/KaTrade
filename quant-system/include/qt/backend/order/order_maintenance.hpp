#pragma once

#include <cstddef>
#include <cstdint>
#include <map>
#include <string>
#include <unordered_map>
#include <vector>

namespace qt::backend {

struct OrderReadModel {
    std::string key;
    std::string source_order_id;
    std::string session_id;
    std::string order_id;
    std::string inst_id;
    std::string source;
    std::string strategy_id;
    std::string agent_id;
    std::string trading_unit_id;
    std::string trading_unit_name;
    std::string parent_decision_id;
    std::string side;
    std::string order_type;
    std::string time_in_force;
    std::string state{"unknown"};
    std::string broker_status;
    std::string broker_state;
    std::string broker_order_id;
    std::string broker_cl_ord_id;
    std::string broker_updated_at;
    std::string position_effect;
    std::string reason;
    std::string created_at;
    std::string updated_at;
    std::int64_t updated_ms{0};
    double quantity{0.0};
    double filled_qty{0.0};
    double remaining_qty{0.0};
    double avg_price{0.0};
    double limit_price{0.0};
    double commission{0.0};
    double close_gross_pnl{0.0};
    double close_fee{0.0};
    double close_net_pnl{0.0};
    double closed_qty{0.0};
    double opened_qty{0.0};
    double broker_order_qty{0.0};
    double broker_order_base_qty{0.0};
    double broker_filled_qty{0.0};
    double broker_filled_base_qty{0.0};
    double broker_contract_value{0.0};
};

struct ExecutionTraceReadModel {
    std::string source_order_id;
    std::string status;
    std::string message;
    std::string trace_key;
    std::string tradeability_status;
    std::string ts;
    std::int64_t ts_ms{0};
    bool approved{false};
    double planned_notional{0.0};
};

struct AuditOrderReadModel {
    std::string source_order_id;
    std::string action;
    std::string audit_id;
    std::string state;
    std::string ord_id;
    std::string cl_ord_id;
    std::string ts;
    bool ok{false};
};

struct OrderConsistencyIssue {
    std::string code;
    std::string severity;
    std::string message;
    std::string recommended_action;
    double age_seconds{0.0};
    OrderReadModel order;
    ExecutionTraceReadModel trace;
    AuditOrderReadModel audit;
    bool has_trace{false};
    bool has_audit{false};
};

struct OrderConsistencyModel {
    int active{0};
    int stale{0};
    int missing_broker_identity{0};
    int active_without_recent_success_trace{0};
    int active_after_failed_execution{0};
    int local_terminal_with_live_broker_audit{0};
    int broker_terminal_not_reflected_locally{0};
    int checked_orders{0};
    int checked_traces{0};
    int checked_audits{0};
    std::map<std::string, int> issue_counts;
    std::vector<OrderConsistencyIssue> issues;
};

struct OrderMaintenancePlan {
    std::vector<OrderConsistencyIssue> actions;
    std::vector<OrderConsistencyIssue> keep;
    std::size_t actionable_total{0};
    int candidate_issues{0};
};

bool order_is_active(const OrderReadModel& row);
bool order_is_terminal_state(const std::string& state);
bool order_is_terminal(const OrderReadModel& row);
bool order_has_broker_identity(const OrderReadModel& row);
bool audit_state_is_live(const AuditOrderReadModel* audit);
bool audit_state_is_terminal(const AuditOrderReadModel* audit);

OrderConsistencyModel build_order_consistency_model(
    const std::vector<OrderReadModel>& states,
    const std::unordered_map<std::string, ExecutionTraceReadModel>& traces,
    const std::unordered_map<std::string, AuditOrderReadModel>& audits,
    std::int64_t now_epoch_ms,
    int stale_seconds);

OrderMaintenancePlan build_local_order_repair_plan(const OrderConsistencyModel& model,
                                                   int min_age_seconds,
                                                   int max_orders,
                                                   bool enabled);
OrderMaintenancePlan build_broker_terminal_sync_plan(const OrderConsistencyModel& model,
                                                     int max_orders,
                                                     bool enabled);
OrderMaintenancePlan build_stale_broker_reconcile_plan(const OrderConsistencyModel& model,
                                                       int min_age_seconds,
                                                       int max_orders,
                                                       bool enabled);

}  // namespace qt::backend
