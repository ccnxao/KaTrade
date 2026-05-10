#pragma once

#include <string>
#include <vector>

#include "qt/types.hpp"

namespace qt::execution {

struct ExecutionConfig {
    double max_participation_rate{0.04};
    double maker_offset_bps{1.0};
    int pending_ttl_seconds{60};
    std::string default_ord_type{"limit"};  // GAP-018: market | limit | post_only
};

class IExecutionAlgo {
public:
    virtual ~IExecutionAlgo() = default;
    virtual std::vector<OrderIntent> plan(const RiskDecision& decision,
                                           const PortfolioSnapshot& current,
                                           const FeatureFrame& features,
                                           const ExecutionConfig& config) = 0;
    virtual std::vector<OrderIntent> plan(const RiskDecision& decision,
                                           const PortfolioSnapshot& current,
                                           const PriceMap&,
                                           double) {
        ExecutionConfig cfg;
        FeatureFrame features;
        return plan(decision, current, features, cfg);
    }
};

class TwapExecutionAlgo : public IExecutionAlgo {
public:
    explicit TwapExecutionAlgo(int slices = 4, double min_rebalance_delta = 0.005);
    std::vector<OrderIntent> plan(const RiskDecision&, const PortfolioSnapshot&,
                                   const FeatureFrame&, const ExecutionConfig&) override;
private:
    int slices_;
    double min_rebalance_delta_;
};

class VwapExecutionAlgo : public IExecutionAlgo {
public:
    explicit VwapExecutionAlgo(double min_rebalance_delta = 0.005);
    std::vector<OrderIntent> plan(const RiskDecision&, const PortfolioSnapshot&,
                                   const FeatureFrame&, const ExecutionConfig&) override;
private:
    double min_rebalance_delta_;
};

class MarketExecutionAlgo : public IExecutionAlgo {
public:
    explicit MarketExecutionAlgo(double min_rebalance_delta = 0.002);
    std::vector<OrderIntent> plan(const RiskDecision&, const PortfolioSnapshot&,
                                   const FeatureFrame&, const ExecutionConfig&) override;
private:
    double min_rebalance_delta_;
};

class NaiveExecutionAlgo : public IExecutionAlgo {
public:
    explicit NaiveExecutionAlgo(double min_rebalance_delta = 0.005);
    std::vector<OrderIntent> plan(const RiskDecision& decision,
                                   const PortfolioSnapshot& current,
                                   const FeatureFrame& features,
                                   const ExecutionConfig& config) override;

private:
    double min_rebalance_delta_;
};

}  // namespace qt::execution
