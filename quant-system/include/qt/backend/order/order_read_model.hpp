#pragma once

#include <map>
#include <string>
#include <unordered_map>
#include <vector>

#include "qt/backend/order/order_maintenance.hpp"

namespace qt::backend {

std::string normalize_order_state(std::string state);
std::string order_key_from_event(const std::string& line);
std::vector<OrderReadModel> reduce_order_events(const std::vector<std::string>& events);
std::map<std::string, int> count_order_states(const std::vector<OrderReadModel>& rows);
std::unordered_map<std::string, ExecutionTraceReadModel> reduce_execution_traces(
    const std::vector<std::string>& rows);
std::unordered_map<std::string, AuditOrderReadModel> reduce_okx_audit_orders(
    const std::vector<std::string>& rows);

}  // namespace qt::backend
