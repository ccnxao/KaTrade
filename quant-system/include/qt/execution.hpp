#pragma once

#include <span>
#include <string>
#include <vector>

#include "qt/types.hpp"

namespace qt {

class IBrokerGateway {
public:
    virtual ~IBrokerGateway() = default;
    virtual std::string submit(const OrderIntent& order) = 0;
    virtual void cancel_open_orders() = 0;
    virtual void on_market_snapshot(std::span<const Bar> bars) = 0;
    virtual std::vector<ExecutionReport> flush_reports() = 0;
};

class IExecutionAlgo {
public:
    virtual ~IExecutionAlgo() = default;
    virtual std::vector<OrderIntent> plan(const RiskDecision& decision,
                                          const PortfolioSnapshot& current,
                                          const PriceMap& prices,
                                          double account_equity) = 0;
};

class NaiveExecutionAlgo final : public IExecutionAlgo {
public:
    explicit NaiveExecutionAlgo(double min_rebalance_delta = 0.02);

    std::vector<OrderIntent> plan(const RiskDecision& decision,
                                  const PortfolioSnapshot& current,
                                  const PriceMap& prices,
                                  double account_equity) override;

private:
    double min_rebalance_delta_;
};

class PaperBrokerGateway final : public IBrokerGateway {
public:
    explicit PaperBrokerGateway(double max_participation_rate = 0.10);

    std::string submit(const OrderIntent& order) override;
    void cancel_open_orders() override;
    void on_market_snapshot(std::span<const Bar> bars) override;
    std::vector<ExecutionReport> flush_reports() override;

private:
    struct WorkingOrder {
        std::string order_id;
        OrderIntent intent;
        double remaining_qty{};
        double cumulative_filled_qty{};
        double cumulative_notional{};
    };

    const Bar* find_bar(std::span<const Bar> bars, const InstrumentId& instrument) const;

    double max_participation_rate_;
    std::vector<WorkingOrder> working_orders_;
    std::vector<ExecutionReport> pending_reports_;
    std::size_t next_id_{1};
};

}  // namespace qt
