#include "qt/backend/order/order_maintenance.hpp"

#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

namespace {

using qt::backend::AuditOrderReadModel;
using qt::backend::ExecutionTraceReadModel;
using qt::backend::OrderReadModel;
using qt::backend::build_broker_terminal_sync_plan;
using qt::backend::build_local_order_repair_plan;
using qt::backend::build_order_consistency_model;
using qt::backend::build_stale_broker_reconcile_plan;

constexpr std::int64_t kNowMs = 1'700'000'000'000;

void require(bool ok, const std::string& message) {
    if (!ok) {
        throw std::runtime_error(message);
    }
}

OrderReadModel active_order(std::string key, std::int64_t age_seconds) {
    OrderReadModel row;
    row.key = key;
    row.source_order_id = key;
    row.order_id = key;
    row.state = "live";
    row.inst_id = "BTC-USDT-SWAP";
    row.updated_ms = kNowMs - age_seconds * 1000;
    row.quantity = 1.0;
    row.remaining_qty = 1.0;
    return row;
}

ExecutionTraceReadModel trace(std::string source_order_id, std::string status) {
    ExecutionTraceReadModel row;
    row.source_order_id = source_order_id;
    row.status = status;
    row.ts_ms = kNowMs - 30'000;
    row.approved = status == "submitted";
    return row;
}

AuditOrderReadModel audit(std::string source_order_id,
                          std::string state,
                          std::string ord_id,
                          std::string cl_ord_id) {
    AuditOrderReadModel row;
    row.source_order_id = source_order_id;
    row.state = state;
    row.ord_id = ord_id;
    row.cl_ord_id = cl_ord_id;
    row.ok = true;
    return row;
}

void local_failed_order_can_be_repaired() {
    auto order = active_order("local-failed", 900);
    const auto model = build_order_consistency_model(
        {order},
        {{"local-failed", trace("local-failed", "rejected")}},
        {},
        kNowMs,
        300);

    const auto plan = build_local_order_repair_plan(model, 300, 10, true);
    require(plan.actions.size() == 1, "failed local-only order should be repairable");
    require(plan.actions.front().order.key == "local-failed", "repair action should reference the local order");
    require(plan.actionable_total == 1, "actionable_total should count uncapped local repair actions");
}

void submitted_local_order_is_not_expired_locally() {
    auto order = active_order("submitted-without-broker-id", 900);
    const auto model = build_order_consistency_model(
        {order},
        {{"submitted-without-broker-id", trace("submitted-without-broker-id", "submitted")}},
        {},
        kNowMs,
        300);

    const auto plan = build_local_order_repair_plan(model, 300, 10, true);
    require(plan.actions.empty(), "submitted order without broker id must wait for broker sync");
    require(plan.keep.size() == 1, "submitted order should remain visible in keep list");
}

void stale_broker_order_requires_reconcile() {
    auto order = active_order("stale-broker", 1'200);
    order.broker_order_id = "okx-ord-1";
    order.broker_cl_ord_id = "client-ord-1";

    const auto model = build_order_consistency_model({order}, {}, {}, kNowMs, 300);
    const auto plan = build_stale_broker_reconcile_plan(model, 180, 10, true);
    require(plan.actions.size() == 1, "stale active broker order should require OKX reconcile");
    require(plan.actions.front().order.broker_order_id == "okx-ord-1", "reconcile action should keep broker id");
}

void broker_terminal_fill_can_be_synced() {
    auto order = active_order("broker-filled", 1'200);
    order.broker_order_id = "okx-ord-2";
    order.broker_cl_ord_id = "client-ord-2";
    order.broker_filled_qty = 1.0;

    const auto model = build_order_consistency_model(
        {order},
        {},
        {{"broker-filled", audit("broker-filled", "filled", "okx-ord-2", "client-ord-2")}},
        kNowMs,
        300);

    const auto plan = build_broker_terminal_sync_plan(model, 10, true);
    require(plan.actions.size() == 1, "terminal broker fill with matched id should be syncable");
    require(plan.keep.empty(), "matched terminal broker fill should not stay in keep list");
}

void zero_fill_terminal_audit_is_kept_for_manual_review() {
    auto order = active_order("zero-fill-terminal", 1'200);
    order.broker_order_id = "okx-ord-3";
    order.broker_cl_ord_id = "client-ord-3";

    const auto model = build_order_consistency_model(
        {order},
        {},
        {{"zero-fill-terminal", audit("zero-fill-terminal", "filled", "okx-ord-3", "client-ord-3")}},
        kNowMs,
        300);

    const auto plan = build_broker_terminal_sync_plan(model, 10, true);
    require(plan.actions.empty(), "filled audit with zero broker fill must not auto-sync");
    require(plan.keep.size() == 1, "zero-fill terminal audit should be kept for review");
}

void action_cap_keeps_total_count() {
    auto older = active_order("older-broker", 2'000);
    older.broker_order_id = "okx-older";
    auto newer = active_order("newer-broker", 1'000);
    newer.broker_order_id = "okx-newer";

    const auto model = build_order_consistency_model({older, newer}, {}, {}, kNowMs, 300);
    const auto plan = build_stale_broker_reconcile_plan(model, 180, 1, true);

    require(plan.actions.size() == 1, "max_orders should cap returned actions");
    require(plan.actionable_total == 2, "actionable_total should expose all eligible actions before cap");
    require(plan.actions.front().order.key == "older-broker", "oldest broker order should be handled first");
}

void disabled_plan_never_actions() {
    auto order = active_order("disabled-local-repair", 900);
    const auto model = build_order_consistency_model(
        {order},
        {{"disabled-local-repair", trace("disabled-local-repair", "rejected")}},
        {},
        kNowMs,
        300);

    const auto plan = build_local_order_repair_plan(model, 300, 10, false);
    require(plan.actions.empty(), "disabled maintenance plan should not emit actions");
    require(plan.keep.size() == 1, "disabled maintenance plan should retain candidate in keep list");
}

}  // namespace

int main() {
    try {
        local_failed_order_can_be_repaired();
        submitted_local_order_is_not_expired_locally();
        stale_broker_order_requires_reconcile();
        broker_terminal_fill_can_be_synced();
        zero_fill_terminal_audit_is_kept_for_manual_review();
        action_cap_keeps_total_count();
        disabled_plan_never_actions();
    } catch (const std::exception& exc) {
        std::cerr << "order_maintenance_check failed: " << exc.what() << "\n";
        return 1;
    }

    std::cout << "order_maintenance_check passed\n";
    return 0;
}
