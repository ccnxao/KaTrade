#include "qt/execution.hpp"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <functional>
#include <string>
#include <utility>

namespace qt {

namespace {

std::string lower_copy(std::string_view value) {
    std::string output;
    output.reserve(value.size());
    for (const unsigned char ch : value) {
        output.push_back(static_cast<char>(std::tolower(ch)));
    }
    return output;
}

bool contains_instrument(const std::vector<std::string>& whitelist,
                         const std::string& inst_id) {
    if (whitelist.empty()) {
        return true;
    }
    return std::find(whitelist.begin(), whitelist.end(), inst_id) != whitelist.end();
}

PreTradeCheckItem pre_trade_check(std::string name,
                                  bool ok,
                                  std::string severity,
                                  std::string message) {
    return PreTradeCheckItem{
        .name = std::move(name),
        .ok = ok,
        .severity = ok ? "ok" : std::move(severity),
        .message = std::move(message),
    };
}

}  // namespace

bool is_okx_spot_cash_order_type(std::string_view ord_type) {
    const auto normalized = lower_copy(ord_type);
    return normalized == "limit" || normalized == "post_only";
}

PreTradeDecision validate_okx_spot_order(const OkxExecutionContext& context,
                                         const OkxOrderRequest& order) {
    PreTradeDecision decision;
    const auto td_mode = lower_copy(order.td_mode);
    const auto side = lower_copy(order.side);
    const auto ord_type = lower_copy(order.ord_type);
    decision.estimated_notional =
        order.px > 0.0 && order.sz > 0.0 ? order.px * order.sz : 0.0;
    const bool instrument_allowed =
        !order.inst_id.empty() &&
        contains_instrument(context.instrument_whitelist, order.inst_id);
    const bool ord_type_allowed = is_okx_spot_cash_order_type(ord_type);
    const bool notional_allowed =
        decision.estimated_notional > 0.0 &&
        decision.estimated_notional <= context.max_order_notional;

    // 这里集中维护 OKX 模拟盘执行的硬门禁。Python 平台层后续只负责
    // 把 API/UI 请求映射为 OkxOrderRequest，并展示这些检查结果。
    auto& checks = decision.checks;
    checks.push_back(pre_trade_check(
        "OKX 配置",
        context.configured,
        "halt",
        context.configured ? "OKX API 已配置。" : "OKX API 未配置。"));
    checks.push_back(pre_trade_check(
        "模拟盘环境",
        context.simulated,
        "halt",
        context.simulated ? "OKX simulated trading 已开启。"
                          : "只允许 OKX simulated trading。"));
    checks.push_back(pre_trade_check(
        "下单开关",
        context.trading_enabled,
        "halt",
        context.trading_enabled ? "模拟盘下单开关已开启。"
                                : "OKX_TRADING_ENABLED=false。"));
    checks.push_back(pre_trade_check(
        "Kill switch",
        !context.kill_switch,
        "halt",
        context.kill_switch ? "Kill switch 已开启。" : "Kill switch 关闭。"));
    checks.push_back(pre_trade_check(
        "现货白名单",
        instrument_allowed,
        "halt",
        order.inst_id.empty()
            ? "缺少 OKX instId。"
            : instrument_allowed ? "合约通过 OKX 现货白名单。"
                                 : "合约不在当前 OKX 现货白名单内。"));
    checks.push_back(pre_trade_check(
        "tdMode",
        td_mode == "cash",
        "halt",
        td_mode == "cash" ? "tdMode=cash。" : "只允许 OKX cash 模式。"));
    checks.push_back(pre_trade_check(
        "side",
        side == "buy" || side == "sell",
        "halt",
        side == "buy" || side == "sell" ? "side 合法。"
                                        : "side 必须是 buy 或 sell。"));
    checks.push_back(pre_trade_check(
        "ordType",
        ord_type_allowed,
        "halt",
        ord_type_allowed ? "仅限 limit/post_only。"
                         : "市价、IOC、FOK 和合约订单暂时禁用。"));
    checks.push_back(pre_trade_check(
        "价格",
        order.px > 0.0,
        "halt",
        order.px > 0.0 ? "价格为正。" : "限价单价格必须为正。"));
    checks.push_back(pre_trade_check(
        "数量",
        order.sz > 0.0,
        "halt",
        order.sz > 0.0 ? "数量为正。" : "下单数量必须为正。"));
    checks.push_back(pre_trade_check(
        "单笔名义金额",
        notional_allowed,
        "halt",
        decision.estimated_notional <= 0.0
            ? "无法计算有效名义金额。"
            : notional_allowed ? "名义金额在上限内。"
                               : "单笔名义金额超过风控上限。"));

    decision.approved =
        std::all_of(checks.begin(), checks.end(), [](const auto& item) {
            return item.ok;
        });
    return decision;
}

OkxTradeabilityDecision evaluate_okx_tradeability(const OkxTradeabilityInput& input) {
    OkxTradeabilityDecision decision;
    auto& checks = decision.checks;
    const double spread_bps = std::max(0.0, input.spread_bps);
    const double maker_fee_bps = std::max(0.0, input.maker_fee_bps);
    decision.spread_cost_bps = spread_bps * 0.5;
    if (input.depth_ready && input.usable_depth_usdt > 1e-9 && input.target_notional > 0.0) {
        const double depth_ratio = input.target_notional / input.usable_depth_usdt;
        decision.depth_cost_bps = std::min(100.0, depth_ratio * std::max(spread_bps, 1.0));
    }
    decision.expected_cost_bps =
        maker_fee_bps + decision.spread_cost_bps + decision.depth_cost_bps;
    decision.expected_cost_usdt =
        input.target_notional > 0.0 ? input.target_notional * decision.expected_cost_bps / 10'000.0
                                    : 0.0;

    // halt 表示不能自动提交；warn 表示可继续观察，必要时可配置为阻断。
    checks.push_back(pre_trade_check(
        "规则状态",
        input.instrument_live,
        "halt",
        input.instrument_live ? "OKX instrument state=live。"
                              : "OKX instrument 不可交易。"));
    checks.push_back(pre_trade_check(
        "盘口报价",
        input.quote_ready,
        "halt",
        input.quote_ready ? "bid/ask 报价有效。" : "缺少有效 bid/ask 报价。"));
    checks.push_back(pre_trade_check(
        "最小下单",
        input.target_notional > 0.0 && input.estimated_size > 0.0 &&
            (input.min_size <= 0.0 || input.estimated_size + 1e-12 >= input.min_size),
        "halt",
        input.estimated_size > 0.0 ? "目标名义金额可折算为合法数量。"
                                   : "目标名义金额无法折算为合法数量。"));
    checks.push_back(pre_trade_check(
        "价差",
        input.spread_bps >= 0.0 && input.spread_bps <= input.max_spread_bps,
        "warn",
        input.spread_bps <= input.max_spread_bps ? "价差在阈值内。"
                                                 : "价差超过当前阈值。"));
    checks.push_back(pre_trade_check(
        "五档深度",
        !input.depth_ready || input.usable_depth_usdt >= input.required_depth_usdt,
        "warn",
        !input.depth_ready ? "WS 深度暂未就绪。"
                           : "五档可用深度满足目标名义金额。"));
    checks.push_back(pre_trade_check(
        "24h成交量",
        input.min_24h_volume_usdt <= 0.0 ||
            input.volume_24h_usdt >= input.min_24h_volume_usdt,
        "warn",
        input.volume_24h_usdt >= input.min_24h_volume_usdt ? "24h 成交量满足阈值。"
                                                           : "24h 成交量低于阈值。"));
    checks.push_back(pre_trade_check(
        "预计成本",
        decision.expected_cost_bps <= input.max_expected_cost_bps,
        "warn",
        decision.expected_cost_bps <= input.max_expected_cost_bps
            ? "预计执行成本在阈值内。"
            : "预计执行成本超过阈值。"));

    const bool has_halt = std::any_of(checks.begin(), checks.end(), [](const auto& item) {
        return !item.ok && item.severity == "halt";
    });
    const bool has_warn = std::any_of(checks.begin(), checks.end(), [](const auto& item) {
        return !item.ok && item.severity == "warn";
    });
    decision.status = has_halt ? "block" : has_warn ? "warn" : "pass";
    decision.approved = !has_halt && (!input.block_warnings || !has_warn);
    return decision;
}

execution::NaiveExecutionAlgo::NaiveExecutionAlgo(double min_rebalance_delta)
    : min_rebalance_delta_(min_rebalance_delta) {}

std::vector<OrderIntent> execution::NaiveExecutionAlgo::plan(const RiskDecision& decision,
                                                  const PortfolioSnapshot& current,
                                                  const FeatureFrame&,
                                                  const ExecutionConfig& config) {
    std::vector<OrderIntent> orders;
    if (decision.action == RiskAction::Reject || decision.action == RiskAction::Halt) {
        return orders;
    }

    for (const auto& target : decision.adjusted_portfolio.positions) {
        const double current_weight = find_weight(current, target.instrument).value_or(0.0);
        const double delta = target.target_weight - current_weight;
        if (std::abs(delta) < min_rebalance_delta_) {
            continue;
        }

        // 价格由 trader_engine 在 plan 返回后从 result.prices 填入
        const double price = 0.0;
        // 返回 weight delta，由 trader_engine 统一归一化为币数量。
        // 避免与其他 IExecutionAlgo 实现（Twap/Vwap/Market）返回权重不一致
        // 导致 trader_engine 的 <= 1.0 归一化条件对币数量二次换算。
        const double quantity = std::abs(delta);

        // GAP-018: 使用配置的订单类型
        OrderType otype = (config.default_ord_type == "market") ? OrderType::Market : OrderType::Limit;
        orders.push_back(OrderIntent{target.instrument,
                                     delta >= 0.0 ? OrderSide::Buy : OrderSide::Sell,
                                     otype,
                                     quantity,
                                     price,
                                     "rebalance",
                                     target.strategy_id});
    }

    return orders;
}

// ---- TwapExecutionAlgo ----
execution::TwapExecutionAlgo::TwapExecutionAlgo(int slices, double min_rebalance_delta)
    : slices_(std::max(1, slices)), min_rebalance_delta_(min_rebalance_delta) {}

std::vector<OrderIntent> execution::TwapExecutionAlgo::plan(
    const RiskDecision& decision,
    const PortfolioSnapshot& current,
    const FeatureFrame&,
    const ExecutionConfig&) {

    std::vector<OrderIntent> orders;
    if (decision.action == RiskAction::Reject || decision.action == RiskAction::Halt) {
        return orders;
    }

    for (const auto& target : decision.adjusted_portfolio.positions) {
        const double current_weight = find_weight(current, target.instrument).value_or(0.0);
        const double delta = target.target_weight - current_weight;
        if (std::abs(delta) < min_rebalance_delta_) continue;

        // TWAP: 等分订单为多个切片，降低单笔市场冲击
        double slice_delta = delta / slices_;
        OrderSide side = delta >= 0.0 ? OrderSide::Buy : OrderSide::Sell;
        for (int s = 0; s < slices_; ++s) {
            orders.push_back(OrderIntent{target.instrument, side, OrderType::Limit,
                                         std::abs(slice_delta), 0.0,
                                         "twap_slice_" + std::to_string(s),
                                         target.strategy_id});
        }
    }
    return orders;
}

// ---- VwapExecutionAlgo ----
execution::VwapExecutionAlgo::VwapExecutionAlgo(double min_rebalance_delta)
    : min_rebalance_delta_(min_rebalance_delta) {}

std::vector<OrderIntent> execution::VwapExecutionAlgo::plan(
    const RiskDecision& decision,
    const PortfolioSnapshot& current,
    const FeatureFrame& features,
    const ExecutionConfig&) {

    std::vector<OrderIntent> orders;
    if (decision.action == RiskAction::Reject || decision.action == RiskAction::Halt) {
        return orders;
    }

    // 用最近成交量缩放订单激进程度
    auto vol_it = features.find("volume");
    double vol_scale = (vol_it != features.end() && vol_it->second > 0.0)
                           ? std::min(2.0, 1.0 + vol_it->second / 10000.0)
                           : 1.0;

    for (const auto& target : decision.adjusted_portfolio.positions) {
        const double current_weight = find_weight(current, target.instrument).value_or(0.0);
        const double delta = target.target_weight - current_weight;
        if (std::abs(delta) < min_rebalance_delta_) continue;

        // VWAP: 高成交量时更激进（单笔大），低成交量时分拆
        int slices = vol_scale > 1.5 ? 2 : 4;
        double slice_delta = delta / static_cast<double>(slices);
        OrderSide side = delta >= 0.0 ? OrderSide::Buy : OrderSide::Sell;
        for (int s = 0; s < slices; ++s) {
            orders.push_back(OrderIntent{target.instrument, side, OrderType::Limit,
                                         std::abs(slice_delta), 0.0,
                                         "vwap_slice_" + std::to_string(s),
                                         target.strategy_id});
        }
    }
    return orders;
}

// ---- MarketExecutionAlgo ----
execution::MarketExecutionAlgo::MarketExecutionAlgo(double min_rebalance_delta)
    : min_rebalance_delta_(min_rebalance_delta) {}

std::vector<OrderIntent> execution::MarketExecutionAlgo::plan(
    const RiskDecision& decision,
    const PortfolioSnapshot& current,
    const FeatureFrame&,
    const ExecutionConfig&) {

    std::vector<OrderIntent> orders;
    if (decision.action == RiskAction::Reject || decision.action == RiskAction::Halt) {
        return orders;
    }

    // Market: 快速执行，不做分拆
    for (const auto& target : decision.adjusted_portfolio.positions) {
        const double current_weight = find_weight(current, target.instrument).value_or(0.0);
        const double delta = target.target_weight - current_weight;
        if (std::abs(delta) < min_rebalance_delta_) continue;

        orders.push_back(OrderIntent{target.instrument,
                                     delta >= 0.0 ? OrderSide::Buy : OrderSide::Sell,
                                     OrderType::Market,
                                     std::abs(delta), 0.0,
                                     "market_exec",
                                     target.strategy_id});
    }
    return orders;
}

execution::SimulatedBrokerGateway::SimulatedBrokerGateway(
    double max_participation_rate,
    double base_slippage_bps,
    double commission_bps,
    double partial_fill_probability)
    : max_participation_rate_(std::clamp(max_participation_rate, 0.0, 1.0))
    , base_slippage_bps_(std::max(0.0, base_slippage_bps))
    , commission_bps_(std::max(0.0, commission_bps))
    , partial_fill_probability_(std::clamp(partial_fill_probability, 0.0, 1.0)) {}

std::string execution::SimulatedBrokerGateway::submit(const OrderIntent& order) {
    const std::string order_id = "PAPER-" + std::to_string(next_id_++);
    working_orders_.push_back(
        WorkingOrder{order_id, order, order.quantity, 0.0, 0.0});
    return order_id;
}

void execution::SimulatedBrokerGateway::cancel_open_orders() {
    for (const auto& order : working_orders_) {
        pending_reports_.push_back(ExecutionReport{
            order.order_id,
            order.intent.instrument,
            order.intent.side,
            0.0,
            0.0,
            order.cumulative_filled_qty,
            0.0,
            order.cumulative_filled_qty > 0.0
                ? order.cumulative_notional / order.cumulative_filled_qty
                : 0.0,
            0.0,
            0.0,
            OrderStatus::Cancelled,
            "CANCELLED",
        });
    }
    working_orders_.clear();
}

void execution::SimulatedBrokerGateway::on_market_snapshot(std::span<const Bar> bars) {
    std::vector<WorkingOrder> still_working;
    still_working.reserve(working_orders_.size());

    for (auto& order : working_orders_) {
        const Bar* bar = find_bar(bars, order.intent.instrument);
        if (bar == nullptr) {
            still_working.push_back(order);
            continue;
        }

        const double volume_cap =
            bar->volume > 1e-9 ? bar->volume * max_participation_rate_ : 0.0;
        const double max_fill_qty = volume_cap * deterministic_fill_scale(order, *bar);
        const double fill_qty = std::min(order.remaining_qty, max_fill_qty);
        if (fill_qty <= 1e-9) {
            still_working.push_back(order);
            continue;
        }

        const double participation = fill_qty / std::max(1.0, bar->volume);
        // 由 broker 统一处理成交约束、sqrt 冲击和手续费；TraderEngine 只提交意图。
        const double slippage_bps =
            base_slippage_bps_ + 15.0 * std::sqrt(std::min(participation, 0.25));
        const double fill_multiplier =
            order.intent.side == OrderSide::Buy
                ? (1.0 + slippage_bps / 10000.0)
                : (1.0 - slippage_bps / 10000.0);
        const double fill_price = bar->close * fill_multiplier;
        const double fill_commission = fill_qty * fill_price * (commission_bps_ / 10000.0);

        order.remaining_qty -= fill_qty;
        order.cumulative_filled_qty += fill_qty;
        order.cumulative_notional += fill_qty * fill_price;

        const OrderStatus status =
            order.remaining_qty <= 1e-9 ? OrderStatus::Filled
                                        : OrderStatus::PartiallyFilled;
        const std::string broker_status =
            status == OrderStatus::Filled ? "FILLED" : "PARTIALLY_FILLED";

        pending_reports_.push_back(ExecutionReport{
            order.order_id,
            order.intent.instrument,
            order.intent.side,
            fill_qty,
            fill_price,
            order.cumulative_filled_qty,
            std::max(0.0, order.remaining_qty),
            order.cumulative_notional /
                std::max(order.cumulative_filled_qty, 1e-9),
            fill_commission,
            order.intent.side == OrderSide::Buy ? slippage_bps : -slippage_bps,
            status,
            broker_status,
        });

        if (status != OrderStatus::Filled) {
            still_working.push_back(order);
        }
    }

    working_orders_.swap(still_working);
}

std::vector<ExecutionReport> execution::SimulatedBrokerGateway::flush_reports() {
    auto reports = pending_reports_;
    pending_reports_.clear();
    return reports;
}

const Bar* execution::SimulatedBrokerGateway::find_bar(std::span<const Bar> bars,
                                        const InstrumentId& instrument) const {
    const auto key = instrument_key(instrument);
    for (const auto& bar : bars) {
        if (instrument_key(bar.instrument) == key) {
            return &bar;
        }
    }
    return nullptr;
}

double execution::SimulatedBrokerGateway::deterministic_fill_scale(
    const WorkingOrder& order,
    const Bar& bar) const {
    if (partial_fill_probability_ <= 0.0) {
        return 1.0;
    }

    const std::string seed = order.order_id + "|" + std::to_string(bar.timestamp);
    const auto hash_value = std::hash<std::string>{}(seed);
    const double uniform = static_cast<double>(hash_value % 10'000) / 10'000.0;
    if (uniform >= partial_fill_probability_) {
        return 1.0;
    }
    return 0.3 + 0.6 * uniform;
}

}  // namespace qt
