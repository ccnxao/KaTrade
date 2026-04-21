#pragma once

#include <memory>
#include <span>
#include <vector>

#include "qt/execution.hpp"

namespace qt {

class OrderManagementSystem {
public:
    explicit OrderManagementSystem(std::unique_ptr<IBrokerGateway> broker_gateway);

    std::vector<OrderRecord> submit_orders(std::span<const OrderIntent> orders);
    std::vector<ExecutionReport> collect_reports();

    const std::vector<OrderRecord>& order_history() const noexcept;

private:
    OrderRecord* find_order(const std::string& order_id);

    std::unique_ptr<IBrokerGateway> broker_gateway_;
    std::vector<OrderRecord> order_history_;
};

}  // namespace qt
