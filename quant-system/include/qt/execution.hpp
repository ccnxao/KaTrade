#pragma once

#include <string>
#include <vector>

#include "qt/types.hpp"

namespace qt {

class IBrokerGateway {
public:
    virtual ~IBrokerGateway() = default;
    virtual std::string submit(const OrderIntent& order) = 0;
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
    std::string submit(const OrderIntent& order) override;
    std::vector<ExecutionReport> flush_reports() override;

private:
    std::vector<ExecutionReport> pending_reports_;
    std::size_t next_id_{1};
};

}  // namespace qt
