#pragma once

#include <string>
#include <string_view>
#include <vector>

#include "qt/execution/execution_agent.hpp"
#include "qt/execution/broker_gateway.hpp"
#include "qt/execution/execution_ledger.hpp"
#include "qt/execution/normalizer.hpp"

namespace qt {
using qt::execution::IExecutionAlgo;
using qt::execution::TwapExecutionAlgo;
using qt::execution::VwapExecutionAlgo;
using qt::execution::MarketExecutionAlgo;
using qt::execution::ExecutionConfig;
using qt::execution::IBrokerGateway;
using qt::execution::SimulatedBrokerGateway;
using qt::execution::PaperBrokerGateway;
using qt::execution::BrokerHealth;
using qt::execution::SymbolNormalizer;
using qt::execution::BrokerOrderId;

struct PreTradeCheckItem {
    std::string name;
    bool ok{false};
    std::string severity{"halt"};
    std::string message;
};

struct PreTradeDecision {
    bool approved{false};
    double estimated_notional{};
    std::vector<PreTradeCheckItem> checks;
};

struct OkxExecutionContext {
    bool configured{false};
    bool simulated{false};
    bool trading_enabled{false};
    bool kill_switch{false};
    double max_order_notional{};
    std::vector<std::string> instrument_whitelist;
};

struct OkxOrderRequest {
    std::string inst_id;
    std::string td_mode{"cash"};
    std::string side;
    std::string ord_type{"post_only"};
    double px{};
    double sz{};
};

struct OkxDerivativesExecutionContext {
    bool configured{false};
    bool simulated{false};
    bool trading_enabled{false};
    bool kill_switch{false};
    bool derivatives_enabled{false};
    double max_order_notional{};
    double max_exchange_leverage{3.0};
    double max_effective_leverage{2.0};
    double max_unit_effective_leverage{1.0};
    std::vector<std::string> instrument_whitelist;
};

struct OkxDerivativesOrderRequest {
    std::string inst_id;
    std::string inst_type{"SWAP"};
    std::string td_mode{"isolated"};
    std::string pos_side{"net"};
    std::string side;
    std::string ord_type{"post_only"};
    double px{};
    double sz{};
    double notional_usdt{};
    double exchange_leverage{1.0};
    double effective_leverage{};
    double unit_effective_leverage{};
    bool reduce_only{false};
    std::string unit_id;
};

struct TradingUnitRiskLimits {
    bool derivatives_enabled{false};
    bool agent_leverage_enabled{true};
    double base_order_notional_usdt{1.0};
    double max_exchange_leverage{3.0};
    double max_effective_leverage{2.0};
    double max_unit_effective_leverage{1.0};
    double max_agent_leverage_step{0.5};
};

struct AgentLeverageProposal {
    std::string agent_id;
    std::string unit_id;
    double requested_effective_leverage{};
    double confidence{};
    double statistical_edge{};
    std::string reason;
};

struct TradingUnitLeverageDecision {
    bool approved{false};
    double effective_leverage{};
    double exchange_leverage{};
    double base_order_notional_usdt{1.0};
    std::string reason;
    std::vector<PreTradeCheckItem> checks;
};

struct OkxTradeabilityInput {
    std::string inst_id;
    bool instrument_live{false};
    bool quote_ready{false};
    double spread_bps{};
    double max_spread_bps{20.0};
    double target_notional{};
    double estimated_size{};
    double min_size{};
    bool depth_ready{false};
    double usable_depth_usdt{};
    double required_depth_usdt{};
    double volume_24h_usdt{};
    double min_24h_volume_usdt{};
    double maker_fee_bps{1.0};
    double max_expected_cost_bps{50.0};
    bool block_warnings{false};
};

struct OkxTradeabilityDecision {
    bool approved{false};
    std::string status{"block"};
    double spread_cost_bps{};
    double depth_cost_bps{};
    double expected_cost_bps{};
    double expected_cost_usdt{};
    std::vector<PreTradeCheckItem> checks;
};

bool is_okx_spot_cash_order_type(std::string_view ord_type);
PreTradeDecision validate_okx_spot_order(const OkxExecutionContext& context,
                                         const OkxOrderRequest& order);
PreTradeDecision validate_okx_derivatives_order(const OkxDerivativesExecutionContext& context,
                                                const OkxDerivativesOrderRequest& order);
TradingUnitLeverageDecision decide_trading_unit_leverage(
    const TradingUnitRiskLimits& limits,
    const AgentLeverageProposal& proposal,
    double current_effective_leverage = 0.0);
OkxTradeabilityDecision evaluate_okx_tradeability(const OkxTradeabilityInput& input);
}  // namespace qt
