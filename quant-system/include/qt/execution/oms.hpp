#pragma once

#include <chrono>
#include <cstdint>
#include <functional>
#include <memory>
#include <span>
#include <string>
#include <unordered_map>
#include <vector>

#include "qt/execution/broker_gateway.hpp"
#include "qt/types.hpp"

namespace qt::execution {

using OmsOrderRecord = OrderRecord;

class OrderManagementSystem {
public:
    explicit OrderManagementSystem(std::unique_ptr<IBrokerGateway> broker_gateway);

    std::vector<OmsOrderRecord> submit_orders(std::span<const OrderIntent> orders);
    void apply_fills(const std::vector<ExecutionReport>& reports,
                     std::function<void(const ExecutionReport&)> on_fill = {});
    void cancel_open_orders();
    void expire_stale_orders(int ttl_seconds);
    void on_market_snapshot(std::span<const Bar> bars);
    std::vector<ExecutionReport> collect_reports();
    const std::vector<OrderRecord>& order_history() const noexcept;

private:
    bool transition_order(OrderRecord& order, OrderStatus to);
    std::unique_ptr<IBrokerGateway> broker_gateway_;
    std::vector<OrderRecord> order_history_;
    std::unordered_map<std::string, int64_t> submission_times_;
    OrderRecord* find_order(const std::string& order_id);
};

}  // namespace qt::execution
