#pragma once

#include <functional>
#include <memory>
#include <string>
#include <vector>

#include "qt/agent/agent_capital.hpp"
#include "qt/agents.hpp"
#include "qt/data/calendar.hpp"
#include "qt/data/feature_store.hpp"
#include "qt/event_bus.hpp"
#include "qt/execution.hpp"
#include "qt/oms.hpp"
#include "qt/portfolio_book.hpp"
#include "qt/portfolio.hpp"
#include "qt/risk.hpp"

namespace qt {

struct CycleResult {
    std::size_t cycle_index{};
    std::string cycle_label;
    double initial_equity{};
    PriceMap prices;
    FeatureFrame features;
    PortfolioSnapshot pre_trade_portfolio;
    PortfolioSnapshot post_trade_portfolio;
    RegimeState regime;
    std::unordered_map<std::string, RegimeState> regime_by_instrument;
    std::vector<Signal> signals;
    TargetPortfolio target_portfolio;
    RiskDecision risk_decision;
    risk::RiskBudgetDecision risk_budget_decision;
    std::vector<OrderIntent> orders;
    std::vector<execution::OmsOrderRecord> order_records;
    std::vector<ExecutionReport> reports;
};

class TraderEngine {
public:
    using RiskBudgetReviewer = std::function<risk::RiskBudgetDecision(const CycleResult&)>;

    TraderEngine(std::unique_ptr<IMetaAgent> meta_agent,
                 std::vector<std::unique_ptr<ISignalAgent>> signal_agents,
                 std::unique_ptr<IPortfolioOptimizer> optimizer,
                 std::unique_ptr<RiskAgent> risk_agent,
                 std::unique_ptr<IExecutionAlgo> execution_algo,
                 std::unique_ptr<OrderManagementSystem> order_management_system,
                 double account_equity,
                 EventBus* event_bus = nullptr);

    CycleResult run_cycle(const std::vector<Bar>& bars, std::string cycle_label = {});
    PortfolioSnapshot portfolio() const;
    void set_risk_budget_reviewer(RiskBudgetReviewer reviewer);
    void setup_agent_capital(const agent::AgentCapitalConfig& config,
                             const std::vector<std::string>& strategy_ids,
                             double total_equity);
    agent::CapitalAllocator& capital_allocator() { return capital_allocator_; }
    const agent::CapitalAllocator& capital_allocator() const { return capital_allocator_; }

    // GAP-008: 暴露风控对象
    RiskAgent* risk_agent() { return risk_agent_.get(); }
    const RiskAgent* risk_agent() const { return risk_agent_.get(); }

    // GAP-017/018: 可配置执行参数
    void set_execution_params(double, double, double, const std::string& ord_type) {
        exec_default_ord_type_ = ord_type;
    }

private:
    FeatureFrame build_features(const std::vector<Bar>& bars);
    PriceMap build_prices(const std::vector<Bar>& bars) const;

    std::unique_ptr<IMetaAgent> meta_agent_;
    std::vector<std::unique_ptr<ISignalAgent>> signal_agents_;
    std::unique_ptr<IPortfolioOptimizer> optimizer_;
    std::unique_ptr<RiskAgent> risk_agent_;
    std::unique_ptr<IExecutionAlgo> execution_algo_;
    std::unique_ptr<OrderManagementSystem> order_management_system_;
    PortfolioBook portfolio_book_;
    data::FeatureEngine feature_engine_;  // GAP-019: 跨周期有状态
    data::TradingCalendar calendar_;      // GAP-033: 交易日历
    double account_equity_;
    double peak_equity_{0.0};  // GAP-012: 跨周期峰值追踪
    std::string exec_default_ord_type_{"limit"};
    std::size_t cycle_id_{0};
    EventBus* event_bus_;
    RiskBudgetReviewer risk_budget_reviewer_;
    agent::CapitalAllocator capital_allocator_;
};

}  // namespace qt
