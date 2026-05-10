#pragma once

#include <span>
#include <string>
#include <vector>

#include "qt/types.hpp"

namespace qt::execution {

struct BrokerHealth {
    bool connected{false};
    std::string status{"offline"};
};

struct BrokerOrderId {
    std::string order_id;
    std::string broker_order_id;
};

class IBrokerGateway {
public:
    virtual ~IBrokerGateway() = default;
    virtual std::string submit(const OrderIntent& order) = 0;
    virtual void cancel_open_orders() = 0;
    virtual void on_market_snapshot(std::span<const Bar> bars) = 0;
    virtual std::vector<ExecutionReport> flush_reports() = 0;
};

class SimulatedBrokerGateway : public IBrokerGateway {
public:
    explicit SimulatedBrokerGateway(double max_participation_rate = 0.04,
                                    double base_slippage_bps = 3.0,
                                    double commission_bps = 1.0,
                                    double partial_fill_probability = 0.0);
    std::string submit(const OrderIntent& order) override;
    void cancel_open_orders() override;
    void on_market_snapshot(std::span<const Bar> bars) override;
    std::vector<ExecutionReport> flush_reports() override;

private:
    struct WorkingOrder {
        std::string order_id;
        OrderIntent intent;
        double remaining_qty;
        double cumulative_filled_qty;
        double cumulative_notional;
    };
    std::vector<WorkingOrder> working_orders_;
    std::vector<ExecutionReport> pending_reports_;
    double max_participation_rate_;
    double base_slippage_bps_;
    double commission_bps_;
    double partial_fill_probability_;
    int next_id_{1};
    const Bar* find_bar(std::span<const Bar>, const InstrumentId&) const;
    double deterministic_fill_scale(const WorkingOrder& order, const Bar& bar) const;
};

// PaperBrokerGateway is an alias for backward compat
using PaperBrokerGateway = SimulatedBrokerGateway;

class SymbolNormalizer {
public:
    std::string normalize(const std::string& symbol) const;
};

}  // namespace qt::execution
