#include "qt/backend/account/account_read_model.hpp"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdlib>
#include <sstream>
#include <unordered_map>
#include <utility>

#include "qt/backend/common/json.hpp"
#include "qt/backend/common/service_context.hpp"

namespace qt::backend {

static double parse_double_or(std::string_view value, double fallback) {
    const auto text = trim(value);
    if (text.empty()) {
        return fallback;
    }
    char* end = nullptr;
    const double parsed = std::strtod(text.c_str(), &end);
    return end == text.c_str() ? fallback : parsed;
}

static double json_number_or_string(std::string_view object, std::string_view key, double fallback) {
    if (const auto text = json_get_string(object, key)) {
        return parse_double_or(*text, fallback);
    }
    return json_get_double(object, key).value_or(fallback);
}

static std::int64_t json_int_or_string(std::string_view object,
                                       std::string_view key,
                                       std::int64_t fallback) {
    if (const auto text = json_get_string(object, key)) {
        return static_cast<std::int64_t>(parse_double_or(*text, static_cast<double>(fallback)));
    }
    return json_get_int(object, key).value_or(fallback);
}

static double config_double(ServiceContext& ctx, const std::string& key, double fallback) {
    auto path = ctx.config().config_path;
    if (path.is_relative()) {
        path = ctx.root() / path;
    }
    const auto text = ctx.read_text(path, 2'000'000);
    std::istringstream input(text);
    std::string line;
    while (std::getline(input, line)) {
        line = trim(line);
        if (line.empty() || line.front() == '#') {
            continue;
        }
        const auto eq = line.find('=');
        if (eq == std::string::npos) {
            continue;
        }
        const auto lhs = trim(std::string_view(line).substr(0, eq));
        if (lhs != key) {
            continue;
        }
        return parse_double_or(std::string_view(line).substr(eq + 1), fallback);
    }
    return fallback;
}

static std::string to_lower_ascii(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    return value;
}

static bool is_generic_strategy_label(const std::string& value) {
    return value == "realtime-maker-rebalance" ||
           value == "paper-tick-rebalance" ||
           value == "tick-maker-rebalance";
}

struct StrategyAllocation {
    std::string strategy_id{"unknown"};
    std::string direction{"unknown"};
    double share{1.0};
    double weighted_score{0.0};
    double net_score{0.0};
};

struct TradingUnitInfo {
    std::string id;
    std::string name;
};

struct OrderContextReadModel {
    std::string key;
    std::string source_order_id;
    std::string strategy_id;
    std::string agent_id;
    std::string trading_unit_id;
    std::string trading_unit_name;
    std::string inst_id;
    std::string side;
    std::string attribution_raw;
};

struct LedgerOrderMeta {
    std::string source_order_id;
    std::string strategy_id;
    std::string agent_id;
    std::string trading_unit_id;
    std::string inst_id;
    std::string side;
};

struct ResolvedFillContext {
    std::string source_order_id;
    std::string order_key;
    std::string strategy_id{"unknown"};
    std::string agent_id{"unknown"};
    std::string trading_unit_id;
    std::string trading_unit_name;
    std::string attribution_source{"unknown"};
    std::string attribution_raw;
};

struct MarketTickerReadModel {
    std::string inst_id;
    std::string source{"none"};
    double price{0.0};
    double bid{0.0};
    double ask{0.0};
    std::int64_t ts_ms{0};
};

struct InstrumentSpecReadModel {
    std::string inst_id;
    std::string contract_type;
    double contract_value{1.0};
};

static std::string order_key_from_line(const std::string& line) {
    if (auto key = json_get_string(line, "order_key"); key && !key->empty()) {
        return *key;
    }
    const auto session = json_get_string(line, "paper_session_id").value_or("unknown");
    const auto order = json_get_string(line, "order_id").value_or("unknown");
    return session + ":" + order;
}

static TradingUnitInfo trading_unit_for_strategy(const std::string& strategy_id) {
    static const std::map<std::string, TradingUnitInfo> units = {
        {"momentum", {"unit_trend", "趋势交易单元"}},
        {"donchian_breakout", {"unit_trend", "趋势交易单元"}},
        {"ma_cross", {"unit_trend", "趋势交易单元"}},
        {"macd_trend", {"unit_trend", "趋势交易单元"}},
        {"ema_slope_trend", {"unit_trend", "趋势交易单元"}},
        {"keltner_breakout", {"unit_trend", "趋势交易单元"}},
        {"volume_spike_momentum", {"unit_trend", "趋势交易单元"}},
        {"mean_reversion", {"unit_reversion", "均值回归交易单元"}},
        {"bollinger_reversion", {"unit_reversion", "均值回归交易单元"}},
        {"rsi_reversion", {"unit_reversion", "均值回归交易单元"}},
        {"zscore_reversion", {"unit_reversion", "均值回归交易单元"}},
        {"range_fade", {"unit_reversion", "均值回归交易单元"}},
        {"micro_scalper", {"unit_maker", "做市/高频交易单元"}},
        {"spread_capture_maker", {"unit_maker", "做市/高频交易单元"}},
        {"order_flow_imbalance", {"unit_maker", "做市/高频交易单元"}},
        {"inventory_skew_maker", {"unit_maker", "做市/高频交易单元"}},
    };
    const auto it = units.find(strategy_id);
    return it == units.end() ? TradingUnitInfo{} : it->second;
}

static std::string non_empty_or(std::string value, const std::string& fallback) {
    return value.empty() ? fallback : std::move(value);
}

static std::string raw_strategy_attribution(std::string_view line) {
    const auto raw = json_get_raw_value(line, "strategy_attribution").value_or("");
    const auto trimmed = trim(raw);
    if (trimmed.size() <= 2 || trimmed == "null") {
        return "";
    }
    return trimmed;
}

static std::vector<StrategyAllocation> parse_strategy_allocations(const std::string& raw) {
    std::vector<StrategyAllocation> allocations;
    const auto objects = json_array_objects(raw);
    allocations.reserve(objects.size());
    double share_total = 0.0;
    double weighted_total = 0.0;
    for (const auto& object : objects) {
        StrategyAllocation allocation;
        allocation.strategy_id = json_get_string(object, "strategy_id").value_or("unknown");
        if (allocation.strategy_id.empty()) {
            allocation.strategy_id = "unknown";
        }
        allocation.direction = json_get_string(object, "direction").value_or("unknown");
        allocation.share = std::max(0.0, json_get_double(object, "share").value_or(0.0));
        allocation.weighted_score = json_get_double(object, "weighted_score").value_or(0.0);
        allocation.net_score = json_get_double(object, "net_score").value_or(0.0);
        share_total += allocation.share;
        weighted_total += std::abs(allocation.weighted_score);
        allocations.push_back(std::move(allocation));
    }
    if (allocations.empty()) {
        return allocations;
    }
    const double denom = share_total > 1e-12 ? share_total : weighted_total;
    if (denom > 1e-12) {
        for (auto& allocation : allocations) {
            const double raw_share =
                share_total > 1e-12 ? allocation.share : std::abs(allocation.weighted_score);
            allocation.share = raw_share / denom;
        }
    } else {
        const double equal = 1.0 / static_cast<double>(allocations.size());
        for (auto& allocation : allocations) {
            allocation.share = equal;
        }
    }
    double normalized_total = 0.0;
    for (const auto& allocation : allocations) {
        normalized_total += allocation.share;
    }
    if (normalized_total > 1e-12) {
        for (auto& allocation : allocations) {
            allocation.share /= normalized_total;
        }
    }
    return allocations;
}

static std::string primary_strategy_from_attribution_raw(const std::string& raw) {
    std::string best_id;
    double best_score = -1.0;
    for (const auto& object : json_array_objects(raw)) {
        const auto strategy_id = json_get_string(object, "strategy_id").value_or("");
        if (strategy_id.empty()) {
            continue;
        }
        const double score = std::max({
            json_get_double(object, "share").value_or(0.0),
            std::abs(json_get_double(object, "weighted_score").value_or(0.0)),
            std::abs(json_get_double(object, "net_score").value_or(0.0)),
        });
        if (score > best_score) {
            best_id = strategy_id;
            best_score = score;
        }
    }
    return best_id;
}

static std::string first_strategy_id_from_line(std::string_view line) {
    if (auto value = json_get_string(line, "strategy_id"); value && !value->empty()) {
        if (!is_generic_strategy_label(*value)) {
            return *value;
        }
    }
    if (const auto raw_ids = json_get_raw_value(line, "strategy_ids")) {
        for (const auto& strategy_id : json_array_strings(*raw_ids)) {
            if (!strategy_id.empty() && !is_generic_strategy_label(strategy_id)) {
                return strategy_id;
            }
        }
    }
    return primary_strategy_from_attribution_raw(raw_strategy_attribution(line));
}

static std::unordered_map<std::string, OrderContextReadModel> reduce_order_contexts(
    const std::vector<std::string>& events) {
    std::unordered_map<std::string, OrderContextReadModel> states;
    for (const auto& line : events) {
        if (!looks_like_json_object(line)) {
            continue;
        }
        const auto key = order_key_from_line(line);
        auto& row = states[key];
        row.key = key;
        row.source_order_id = json_get_string(line, "source_order_id").value_or(row.source_order_id);
        row.inst_id = non_empty_or(json_get_string(line, "inst_id").value_or(""), row.inst_id);
        row.side = non_empty_or(json_get_string(line, "side").value_or(""), row.side);
        row.strategy_id = non_empty_or(first_strategy_id_from_line(line), row.strategy_id);
        row.agent_id = non_empty_or(json_get_string(line, "agent_id").value_or(""), row.agent_id);
        row.trading_unit_id = non_empty_or(json_get_string(line, "trading_unit_id").value_or(""), row.trading_unit_id);
        row.trading_unit_name = non_empty_or(json_get_string(line, "trading_unit_name").value_or(""), row.trading_unit_name);
        row.attribution_raw = non_empty_or(raw_strategy_attribution(line), row.attribution_raw);
        if (row.source_order_id.empty()) {
            row.source_order_id = key;
        }
    }
    return states;
}

static std::unordered_map<std::string, LedgerOrderMeta> reduce_ledger_meta(
    const std::vector<std::string>& rows) {
    std::unordered_map<std::string, LedgerOrderMeta> by_source;
    for (const auto& line : rows) {
        if (!looks_like_json_object(line)) {
            continue;
        }
        const auto source_order_id = json_get_string(line, "source_order_id").value_or("");
        if (source_order_id.empty()) {
            continue;
        }
        auto& row = by_source[source_order_id];
        row.source_order_id = source_order_id;
        const auto strategy_id = json_get_string(line, "strategy_id").value_or("");
        if (!strategy_id.empty() && !is_generic_strategy_label(strategy_id)) {
            row.strategy_id = strategy_id;
        }
        row.agent_id = non_empty_or(json_get_string(line, "agent_id").value_or(""), row.agent_id);
        row.trading_unit_id = non_empty_or(json_get_string(line, "trading_unit_id").value_or(""), row.trading_unit_id);
        row.inst_id = non_empty_or(json_get_string(line, "inst_id").value_or(""), row.inst_id);
        row.side = non_empty_or(json_get_string(line, "side").value_or(""), row.side);
    }
    return by_source;
}

static ResolvedFillContext resolve_fill_context(
    const std::string& line,
    const std::unordered_map<std::string, OrderContextReadModel>& order_contexts,
    const std::unordered_map<std::string, LedgerOrderMeta>& ledger_meta) {
    ResolvedFillContext context;
    context.order_key = order_key_from_line(line);
    context.source_order_id = json_get_string(line, "source_order_id").value_or(context.order_key);
    const auto order_it = order_contexts.find(context.order_key);
    const OrderContextReadModel* order = order_it == order_contexts.end() ? nullptr : &order_it->second;
    auto ledger_it = ledger_meta.find(context.source_order_id);
    if (ledger_it == ledger_meta.end() && order != nullptr) {
        ledger_it = ledger_meta.find(order->source_order_id);
    }
    const LedgerOrderMeta* ledger = ledger_it == ledger_meta.end() ? nullptr : &ledger_it->second;

    context.strategy_id = first_strategy_id_from_line(line);
    if (context.strategy_id.empty() && order != nullptr) {
        context.strategy_id = order->strategy_id;
    }
    if ((context.strategy_id.empty() || context.strategy_id == "unknown") &&
        ledger != nullptr &&
        !is_generic_strategy_label(ledger->strategy_id)) {
        context.strategy_id = ledger->strategy_id;
    }
    if (context.strategy_id.empty()) {
        context.strategy_id = "unknown";
    }

    context.agent_id = json_get_string(line, "agent_id").value_or("");
    if (context.agent_id.empty() && order != nullptr) {
        context.agent_id = order->agent_id;
    }
    if (context.agent_id.empty() && ledger != nullptr) {
        context.agent_id = ledger->agent_id;
    }
    if (context.agent_id.empty()) {
        context.agent_id = context.strategy_id;
    }

    const auto unit = trading_unit_for_strategy(context.strategy_id);
    context.trading_unit_id = json_get_string(line, "trading_unit_id").value_or("");
    context.trading_unit_name = json_get_string(line, "trading_unit_name").value_or("");
    if (context.trading_unit_id.empty() && order != nullptr) {
        context.trading_unit_id = order->trading_unit_id;
        context.trading_unit_name = order->trading_unit_name;
    }
    if (context.trading_unit_id.empty() && ledger != nullptr) {
        context.trading_unit_id = ledger->trading_unit_id;
    }
    if (context.trading_unit_id.empty()) {
        context.trading_unit_id = unit.id;
    }
    if (context.trading_unit_name.empty()) {
        context.trading_unit_name = unit.name;
    }

    context.attribution_raw = raw_strategy_attribution(line);
    if (context.attribution_raw.empty() && order != nullptr) {
        context.attribution_raw = order->attribution_raw;
    }
    if (!raw_strategy_attribution(line).empty() || json_get_string(line, "strategy_id").value_or("") != "") {
        context.attribution_source = "order_journal";
    } else if (ledger != nullptr && !ledger->strategy_id.empty() && !is_generic_strategy_label(ledger->strategy_id)) {
        context.attribution_source = "execution_ledger_join";
    } else if (order != nullptr && (!order->strategy_id.empty() || !order->attribution_raw.empty())) {
        context.attribution_source = "order_state_join";
    }
    return context;
}

static double side_signed_qty(const std::string& side, double quantity) {
    const auto normalized = to_lower_ascii(side);
    if (normalized == "buy" || normalized == "long") {
        return quantity;
    }
    if (normalized == "sell" || normalized == "short") {
        return -quantity;
    }
    return 0.0;
}

static void apply_fill_to_position(PositionReadModel& position,
                                   double signed_qty,
                                   double price,
                                   double commission,
                                   double close_gross,
                                   double close_fee,
                                   double close_net,
                                   double closed_qty,
                                   const std::string& ts) {
    const double fill_abs = std::abs(signed_qty);
    if (fill_abs <= 1e-12) {
        return;
    }

    position.fill_count += 1.0;
    position.last_fill_at = std::max(position.last_fill_at, ts);
    position.last_fill_price = price;
    position.notional += fill_abs * price;
    position.commission += commission;
    position.realized_gross_pnl += close_gross;
    position.realized_net_pnl += close_net;
    if (closed_qty > 1e-12 || std::abs(close_gross) > 1e-12 || std::abs(close_net) > 1e-12 || close_fee > 1e-12) {
        position.close_fill_count += 1.0;
    }
    if (signed_qty > 0.0) {
        position.buy_qty += fill_abs;
    } else {
        position.sell_qty += fill_abs;
    }

    // This is only the read-model inventory cost.  Realized PnL still comes
    // from the paper position book's order.fill fields above, so display PnL
    // stays aligned with the execution journal even if historical fills are
    // partially outside the requested tail window.
    const double old_qty = position.net_qty;
    const double old_abs = std::abs(old_qty);
    if (old_abs <= 1e-12) {
        position.net_qty = signed_qty;
        position.avg_entry_price = price;
    } else if ((old_qty > 0.0 && signed_qty > 0.0) || (old_qty < 0.0 && signed_qty < 0.0)) {
        const double new_abs = old_abs + fill_abs;
        position.avg_entry_price =
            new_abs > 1e-12 ? (old_abs * position.avg_entry_price + fill_abs * price) / new_abs : 0.0;
        position.net_qty = old_qty + signed_qty;
    } else if (fill_abs < old_abs - 1e-12) {
        position.net_qty = old_qty + signed_qty;
    } else if (std::abs(fill_abs - old_abs) <= 1e-12) {
        position.net_qty = 0.0;
        position.avg_entry_price = 0.0;
    } else {
        position.net_qty = old_qty + signed_qty;
        position.avg_entry_price = price;
    }

    position.abs_qty = std::abs(position.net_qty);
    if (position.net_qty > 1e-12) {
        position.side = "long";
    } else if (position.net_qty < -1e-12) {
        position.side = "short";
    } else {
        position.side = "flat";
    }
}

static std::string strip_okx_derivative_suffix(std::string inst_id) {
    constexpr std::string_view swap_suffix = "-SWAP";
    if (inst_id.size() > swap_suffix.size() &&
        inst_id.compare(inst_id.size() - swap_suffix.size(), swap_suffix.size(), swap_suffix) == 0) {
        inst_id.erase(inst_id.size() - swap_suffix.size());
    }
    return inst_id;
}

static std::map<std::string, MarketTickerReadModel> read_market_tickers(ServiceContext& ctx) {
    std::map<std::string, MarketTickerReadModel> tickers;
    const auto path = ctx.root() / "logs" / "market_stream" / "okx_public.jsonl";
    const auto rows = ctx.read_tail_lines(path, 20'000, 24'000'000);
    for (const auto& line : rows) {
        if (!looks_like_json_object(line) || json_get_string(line, "channel").value_or("") != "tickers") {
            continue;
        }
        const std::string inst_id = json_get_string(line, "inst_id").value_or("");
        if (inst_id.empty()) {
            continue;
        }
        const auto raw_rows = json_get_raw_value(line, "rows").value_or("");
        const auto objects = json_array_objects(raw_rows);
        if (objects.empty()) {
            continue;
        }
        const auto& row = objects.back();
        MarketTickerReadModel ticker;
        ticker.inst_id = inst_id;
        ticker.source = "market_stream_ticker";
        ticker.price = json_number_or_string(row, "last", 0.0);
        ticker.bid = json_number_or_string(row, "bid", 0.0);
        ticker.ask = json_number_or_string(row, "ask", 0.0);
        ticker.ts_ms = json_int_or_string(row, "timestamp", json_get_int(line, "ts").value_or(0));
        if (ticker.price <= 0.0 && ticker.bid > 0.0 && ticker.ask > 0.0) {
            ticker.price = (ticker.bid + ticker.ask) / 2.0;
        }
        if (ticker.price > 0.0) {
            tickers[inst_id] = ticker;
        }
    }
    return tickers;
}

static std::map<std::string, InstrumentSpecReadModel> read_swap_instrument_specs(ServiceContext& ctx) {
    std::map<std::string, InstrumentSpecReadModel> specs;
    const auto path = ctx.root() / "logs" / "okx_reference" / "instruments_swap.json";
    const auto text = ctx.read_text(path, 8'000'000);
    const auto raw_rows = json_get_raw_value(text, "instruments").value_or("");
    for (const auto& row : json_array_objects(raw_rows)) {
        InstrumentSpecReadModel spec;
        spec.inst_id = json_get_string(row, "inst_id").value_or("");
        spec.contract_type = json_get_string(row, "ct_type").value_or("");
        spec.contract_value = json_number_or_string(row, "ct_val", 1.0);
        if (!spec.inst_id.empty()) {
            specs[spec.inst_id] = spec;
        }
    }
    return specs;
}

static const MarketTickerReadModel* find_mark_ticker(const std::map<std::string, MarketTickerReadModel>& tickers,
                                                     const std::string& inst_id,
                                                     std::string& source) {
    if (const auto exact = tickers.find(inst_id); exact != tickers.end()) {
        source = "exact_ticker";
        return &exact->second;
    }
    const auto spot_inst_id = strip_okx_derivative_suffix(inst_id);
    if (spot_inst_id != inst_id) {
        if (const auto spot = tickers.find(spot_inst_id); spot != tickers.end()) {
            source = "spot_ticker_fallback";
            return &spot->second;
        }
    }
    return nullptr;
}

static double position_mark_multiplier(const InstrumentSpecReadModel* spec) {
    if (spec == nullptr) {
        return 1.0;
    }
    if (spec->contract_type.empty() || spec->contract_type == "linear") {
        return spec->contract_value > 0.0 ? spec->contract_value : 1.0;
    }
    // Inverse contracts need a different valuation formula.  Leave them
    // unlevered in this read model until inverse PnL is implemented end to end.
    return 0.0;
}

static void apply_market_marks(PortfolioReadModel& model, ServiceContext& ctx) {
    const auto tickers = read_market_tickers(ctx);
    const auto specs = read_swap_instrument_specs(ctx);
    const auto now_ms = ctx.now_epoch_ms();
    for (auto& [inst_id, position] : model.positions) {
        if (position.abs_qty <= 1e-12) {
            position.mark_price = position.last_fill_price;
            position.mark_notional = 0.0;
            position.unrealized_pnl = 0.0;
            position.mark_source = "flat";
            continue;
        }
        std::string mark_source;
        const auto* ticker = find_mark_ticker(tickers, inst_id, mark_source);
        const auto spec_it = specs.find(inst_id);
        const auto* spec = spec_it == specs.end() ? nullptr : &spec_it->second;
        if (spec != nullptr) {
            position.contract_type = spec->contract_type;
            position.contract_value = spec->contract_value > 0.0 ? spec->contract_value : 1.0;
        }
        const double multiplier = position_mark_multiplier(spec);
        if (ticker == nullptr || multiplier <= 0.0 || position.avg_entry_price <= 0.0) {
            position.mark_price = position.last_fill_price > 0.0 ? position.last_fill_price : position.avg_entry_price;
            position.mark_notional = position.abs_qty * position.mark_price * std::max(multiplier, 1.0);
            position.unrealized_pnl = 0.0;
            position.mark_source = multiplier <= 0.0 ? "inverse_contract_unmarked" : "last_fill_fallback";
            continue;
        }
        position.mark_price = ticker->price;
        position.mark_inst_id = ticker->inst_id;
        position.mark_ts_ms = ticker->ts_ms;
        position.mark_age_seconds = ticker->ts_ms > 0 ? static_cast<double>(now_ms - ticker->ts_ms) / 1000.0 : -1.0;
        position.mark_source = mark_source;
        position.mark_notional = position.abs_qty * position.mark_price * multiplier;
        position.unrealized_pnl = position.net_qty * (position.mark_price - position.avg_entry_price) * multiplier;
        model.total_mark_notional += position.mark_notional;
        model.total_unrealized_pnl += position.unrealized_pnl;
        ++model.marked_position_count;
    }
}

static AttributionReadModel make_attribution_row(const std::string& key,
                                                 const ResolvedFillContext& context,
                                                 const std::string& kind) {
    AttributionReadModel row;
    row.key = key;
    row.strategy_id = kind == "strategy" ? key : context.strategy_id;
    row.agent_id = kind == "agent" ? key : context.agent_id;
    row.trading_unit_id = kind == "trading_unit" ? key : context.trading_unit_id;
    row.trading_unit_name = context.trading_unit_name;
    row.display_name = key;
    if (kind == "trading_unit" && !context.trading_unit_name.empty()) {
        row.display_name = context.trading_unit_name;
    }
    const auto unit = trading_unit_for_strategy(row.strategy_id);
    if (row.trading_unit_id.empty()) {
        row.trading_unit_id = unit.id;
    }
    if (row.trading_unit_name.empty()) {
        row.trading_unit_name = unit.name;
    }
    if (row.style == "unknown") {
        if (row.trading_unit_id == "unit_maker") {
            row.style = "maker";
        } else if (row.trading_unit_id == "unit_trend") {
            row.style = "trend";
        } else if (row.trading_unit_id == "unit_reversion") {
            row.style = "mean_reversion";
        }
    }
    return row;
}

static void add_attribution_amounts(AttributionReadModel& row,
                                    double share,
                                    double fill_qty,
                                    double closed_qty,
                                    double opened_qty,
                                    double notional,
                                    double commission,
                                    double close_gross,
                                    double close_fee,
                                    double close_net,
                                    bool close_event,
                                    const std::string& source,
                                    const std::string& ts) {
    row.fill_count += share;
    row.filled_qty += fill_qty * share;
    row.closed_qty += closed_qty * share;
    row.opened_qty += opened_qty * share;
    row.notional += notional * share;
    row.commission += commission * share;
    row.close_gross_pnl += close_gross * share;
    row.close_fee += close_fee * share;
    row.close_net_pnl += close_net * share;
    if (close_event) {
        row.close_fill_count += share;
        if (close_net > 0.0) {
            row.win_count += share;
        } else if (close_net < 0.0) {
            row.loss_count += share;
        }
    } else {
        row.open_fill_count += share;
    }
    row.attribution_sources[source.empty() ? "unknown" : source] += share;
    row.last_fill_at = std::max(row.last_fill_at, ts);
}

PortfolioReadModel build_portfolio_read_model(ServiceContext& ctx,
                                                     int limit,
                                                     int recent_limit,
                                                     const std::string& session_filter) {
    PortfolioReadModel model;
    const auto events = ctx.read_tail_lines(ctx.order_journal_path(), static_cast<std::size_t>(limit));
    const auto ledger_rows = ctx.read_tail_lines(ctx.execution_ledger_path(), static_cast<std::size_t>(std::max(5000, limit / 2)));
    const auto order_contexts = reduce_order_contexts(events);
    const auto ledger_meta = reduce_ledger_meta(ledger_rows);
    model.order_events_scanned = static_cast<int>(events.size());
    model.ledger_events_scanned = static_cast<int>(ledger_rows.size());

    const auto latest_report = ctx.read_text(ctx.root() / "logs" / "paper_trading" / "latest_report.json", 2'000'000);
    model.reported_final_equity = json_get_double(latest_report, "final_equity").value_or(0.0);

    for (const auto& line : events) {
        if (!looks_like_json_object(line) || json_get_string(line, "type").value_or("") != "order.fill") {
            continue;
        }
        if (!session_filter.empty() && json_get_string(line, "paper_session_id").value_or("") != session_filter) {
            continue;
        }
        const double fill_qty = json_get_double(line, "filled_qty").value_or(0.0);
        if (fill_qty <= 1e-12) {
            continue;
        }
        const auto context = resolve_fill_context(line, order_contexts, ledger_meta);
        const std::string inst_id = json_get_string(line, "inst_id").value_or("");
        const std::string side = json_get_string(line, "side").value_or("");
        const double fill_price = json_get_double(line, "fill_price").value_or(json_get_double(line, "avg_price").value_or(0.0));
        const double notional = fill_qty * fill_price;
        const double commission = json_get_double(line, "commission").value_or(0.0);
        const double close_gross = json_get_double(line, "close_gross_pnl").value_or(0.0);
        const double close_fee = json_get_double(line, "close_fee").value_or(0.0);
        const double close_net = json_get_double(line, "close_net_pnl").value_or(0.0);
        const double closed_qty = json_get_double(line, "closed_qty").value_or(0.0);
        const double opened_qty = json_get_double(line, "opened_qty").value_or(0.0);
        const std::string ts = json_get_string(line, "ts").value_or("");
        const bool close_event = closed_qty > 1e-12 || std::abs(close_net) > 1e-12 || std::abs(close_gross) > 1e-12 || close_fee > 1e-12;

        ++model.fill_count;
        model.total_notional += notional;
        model.total_commission += commission;
        if (close_event) {
            ++model.close_fill_count;
            model.total_close_gross_pnl += close_gross;
            model.total_close_fee += close_fee;
            model.total_close_net_pnl += close_net;
        }

        if (!inst_id.empty()) {
            auto& position = model.positions[inst_id];
            position.inst_id = inst_id;
            apply_fill_to_position(position,
                                   side_signed_qty(side, fill_qty),
                                   fill_price,
                                   commission,
                                   close_gross,
                                   close_fee,
                                   close_net,
                                   closed_qty,
                                   ts);
        }

        auto allocations = parse_strategy_allocations(context.attribution_raw);
        if (allocations.empty()) {
            StrategyAllocation fallback;
            fallback.strategy_id = context.strategy_id.empty() ? "unknown" : context.strategy_id;
            allocations.push_back(std::move(fallback));
        }
        const bool has_known_allocation = std::any_of(allocations.begin(), allocations.end(), [](const auto& row) {
            return !row.strategy_id.empty() && row.strategy_id != "unknown";
        });
        if (close_event) {
            if (has_known_allocation) {
                model.attributed_close_net_pnl += close_net;
            } else {
                model.unknown_close_net_pnl += close_net;
            }
        }
        if (!has_known_allocation) {
            ++model.unknown_fill_count;
        }

        for (const auto& allocation : allocations) {
            if (allocation.share <= 1e-12) {
                continue;
            }
            ResolvedFillContext alloc_context = context;
            alloc_context.strategy_id = allocation.strategy_id.empty() ? "unknown" : allocation.strategy_id;
            const auto unit = trading_unit_for_strategy(alloc_context.strategy_id);
            if (!unit.id.empty()) {
                alloc_context.trading_unit_id = unit.id;
                alloc_context.trading_unit_name = unit.name;
            }
            if (alloc_context.agent_id.empty() || alloc_context.agent_id == "unknown") {
                alloc_context.agent_id = alloc_context.strategy_id;
            }
            auto& strategy_row = model.by_strategy.try_emplace(
                alloc_context.strategy_id,
                make_attribution_row(alloc_context.strategy_id, alloc_context, "strategy")).first->second;
            add_attribution_amounts(strategy_row,
                                    allocation.share,
                                    fill_qty,
                                    closed_qty,
                                    opened_qty,
                                    notional,
                                    commission,
                                    close_gross,
                                    close_fee,
                                    close_net,
                                    close_event,
                                    context.attribution_source,
                                    ts);

            auto& agent_row = model.by_agent.try_emplace(
                alloc_context.agent_id,
                make_attribution_row(alloc_context.agent_id, alloc_context, "agent")).first->second;
            agent_row.strategy_ids.insert(alloc_context.strategy_id);
            add_attribution_amounts(agent_row,
                                    allocation.share,
                                    fill_qty,
                                    closed_qty,
                                    opened_qty,
                                    notional,
                                    commission,
                                    close_gross,
                                    close_fee,
                                    close_net,
                                    close_event,
                                    context.attribution_source,
                                    ts);

            const std::string unit_key = alloc_context.trading_unit_id.empty() ? "unknown" : alloc_context.trading_unit_id;
            auto& unit_row = model.by_trading_unit.try_emplace(
                unit_key,
                make_attribution_row(unit_key, alloc_context, "trading_unit")).first->second;
            unit_row.strategy_ids.insert(alloc_context.strategy_id);
            add_attribution_amounts(unit_row,
                                    allocation.share,
                                    fill_qty,
                                    closed_qty,
                                    opened_qty,
                                    notional,
                                    commission,
                                    close_gross,
                                    close_fee,
                                    close_net,
                                    close_event,
                                    context.attribution_source,
                                    ts);
        }

        if (recent_limit > 0) {
            RecentFillReadModel recent;
            recent.ts = ts;
            recent.source_order_id = context.source_order_id;
            recent.order_id = json_get_string(line, "order_id").value_or("");
            recent.inst_id = inst_id;
            recent.side = side;
            recent.strategy_id = context.strategy_id;
            if ((recent.strategy_id.empty() || recent.strategy_id == "unknown") && !allocations.empty()) {
                recent.strategy_id = allocations.front().strategy_id;
            }
            recent.agent_id = context.agent_id;
            recent.trading_unit_id = context.trading_unit_id;
            recent.position_effect = json_get_string(line, "position_effect").value_or("");
            recent.attribution_source = context.attribution_source;
            recent.filled_qty = fill_qty;
            recent.fill_price = fill_price;
            recent.closed_qty = closed_qty;
            recent.opened_qty = opened_qty;
            recent.close_net_pnl = close_net;
            model.recent_fills.push_back(std::move(recent));
            if (model.recent_fills.size() > static_cast<std::size_t>(recent_limit * 4)) {
                model.recent_fills.erase(model.recent_fills.begin(),
                                         model.recent_fills.begin() + static_cast<std::ptrdiff_t>(recent_limit));
            }
        }
    }
    apply_market_marks(model, ctx);
    return model;
}

static void keep_tail(std::vector<EquityCurvePoint>& rows, std::size_t limit) {
    if (rows.size() > limit) {
        rows.erase(rows.begin(), rows.begin() + static_cast<std::ptrdiff_t>(rows.size() - limit));
    }
}

static std::vector<EquityCurvePoint> parse_report_equity_curve(const std::string& latest_report,
                                                               std::size_t limit) {
    std::vector<EquityCurvePoint> points;
    const auto raw_curve = json_get_raw_value(latest_report, "equity_curve").value_or("");
    const auto raw_points = json_array_objects(raw_curve);
    points.reserve(std::min(raw_points.size(), limit));
    int fallback_cycle_index = 1;
    for (const auto& raw : raw_points) {
        EquityCurvePoint point;
        point.source = "paper_latest_report";
        point.cycle_index = static_cast<int>(json_get_int(raw, "cycle_index").value_or(fallback_cycle_index));
        point.label = json_get_string(raw, "label").value_or("");
        point.ts = json_get_string(raw, "ts").value_or(point.label);
        point.ts_ms = json_get_int(raw, "ts_ms").value_or(0);
        point.equity = json_get_double(raw, "equity").value_or(0.0);
        point.cash = json_get_double(raw, "cash").value_or(point.equity);
        point.gross_exposure = json_get_double(raw, "gross_exposure").value_or(
            json_get_double(raw, "gross").value_or(0.0));
        point.realized_pnl = json_get_double(raw, "realized_pnl").value_or(0.0);
        point.unrealized_pnl = json_get_double(raw, "unrealized_pnl").value_or(0.0);
        points.push_back(std::move(point));
        ++fallback_cycle_index;
    }
    keep_tail(points, limit);
    return points;
}

static std::vector<EquityCurvePoint> build_realized_equity_curve(const std::vector<std::string>& events,
                                                                 double initial_cash,
                                                                 const std::string& session_filter,
                                                                 std::size_t limit,
                                                                 EquityCurveReadModel& model) {
    std::vector<EquityCurvePoint> points;
    points.reserve(std::min<std::size_t>(events.size(), limit));
    double cumulative_close_gross = 0.0;
    double cumulative_commission = 0.0;
    int cycle_index = 0;

    for (const auto& line : events) {
        if (!looks_like_json_object(line) || json_get_string(line, "type").value_or("") != "order.fill") {
            continue;
        }
        if (!session_filter.empty() && json_get_string(line, "paper_session_id").value_or("") != session_filter) {
            continue;
        }
        ++model.fill_events_scanned;
        ++cycle_index;
        const double commission = json_get_double(line, "commission").value_or(0.0);
        const double close_gross = json_get_double(line, "close_gross_pnl").value_or(0.0);
        const double close_net = json_get_double(line, "close_net_pnl").value_or(close_gross - commission);
        cumulative_close_gross += close_gross;
        cumulative_commission += commission;
        const double realized_net = cumulative_close_gross - cumulative_commission;

        EquityCurvePoint point;
        point.source = "cpp_order_fill_replay";
        point.cycle_index = cycle_index;
        point.ts = json_get_string(line, "ts").value_or("");
        point.ts_ms = json_get_int(line, "ts_ms").value_or(0);
        point.label = point.ts.empty() ? std::to_string(point.ts_ms) : point.ts;
        point.source_order_id = json_get_string(line, "source_order_id").value_or(order_key_from_line(line));
        point.inst_id = json_get_string(line, "inst_id").value_or("");
        point.run_id = json_get_string(line, "run_id").value_or("");
        point.close_net_pnl = close_net;
        point.cumulative_close_gross_pnl = cumulative_close_gross;
        point.cumulative_commission = cumulative_commission;
        point.cumulative_realized_net_pnl = realized_net;
        point.realized_pnl = realized_net;
        point.unrealized_pnl = 0.0;
        point.equity = initial_cash + realized_net;
        point.cash = point.equity;
        point.gross_exposure = 0.0;
        points.push_back(std::move(point));

        if (points.size() > limit * 2) {
            keep_tail(points, limit);
        }
    }

    keep_tail(points, limit);
    model.cpp_cumulative_close_gross_pnl = cumulative_close_gross;
    model.cpp_cumulative_commission = cumulative_commission;
    model.cpp_cumulative_realized_net_pnl = cumulative_close_gross - cumulative_commission;
    model.cpp_realized_final_equity = initial_cash + model.cpp_cumulative_realized_net_pnl;
    return points;
}

static std::string latest_fill_session_id(const std::vector<std::string>& events) {
    for (auto it = events.rbegin(); it != events.rend(); ++it) {
        if (!looks_like_json_object(*it) || json_get_string(*it, "type").value_or("") != "order.fill") {
            continue;
        }
        const auto session_id = json_get_string(*it, "paper_session_id").value_or("");
        if (!session_id.empty()) {
            return session_id;
        }
    }
    return "";
}

EquityCurveReadModel build_equity_curve_read_model(ServiceContext& ctx,
                                                          int point_limit,
                                                          std::string requested_session,
                                                          int order_limit) {
    EquityCurveReadModel model;
    model.requested_session = requested_session.empty() ? "latest" : requested_session;
    model.initial_cash = config_double(ctx, "initial_cash", 1'000'000.0);

    const auto latest_report_path = ctx.root() / "logs" / "paper_trading" / "latest_report.json";
    const auto latest_report = ctx.read_text(latest_report_path, 10'000'000);
    model.report_final_equity = json_get_double(latest_report, "final_equity").value_or(0.0);
    model.report_points = parse_report_equity_curve(latest_report, static_cast<std::size_t>(point_limit));

    const auto events = ctx.read_tail_lines(ctx.order_journal_path(),
                                            static_cast<std::size_t>(order_limit),
                                            16'000'000);
    model.order_events_scanned = static_cast<int>(events.size());
    model.latest_session = latest_fill_session_id(events);
    if (model.requested_session == "all") {
        model.resolved_session.clear();
    } else if (model.requested_session == "latest") {
        model.resolved_session = model.latest_session;
    } else {
        model.resolved_session = model.requested_session;
    }
    model.realized_points = build_realized_equity_curve(events,
                                                        model.initial_cash,
                                                        model.resolved_session,
                                                        static_cast<std::size_t>(point_limit),
                                                        model);
    const auto portfolio = build_portfolio_read_model(ctx, order_limit, 0, model.resolved_session);
    model.cpp_open_unrealized_pnl = portfolio.total_unrealized_pnl;
    model.cpp_gross_mark_notional = portfolio.total_mark_notional;
    model.marked_position_count = portfolio.marked_position_count;
    model.cpp_mark_to_market_equity = model.cpp_realized_final_equity + model.cpp_open_unrealized_pnl;
    if (!model.realized_points.empty() && portfolio.marked_position_count > 0) {
        model.mark_to_market_points = model.realized_points;
        EquityCurvePoint point = model.realized_points.back();
        point.source = "cpp_mark_to_market_snapshot";
        point.label = ctx.now_iso();
        point.ts = point.label;
        point.ts_ms = ctx.now_epoch_ms();
        point.cycle_index += 1;
        point.equity = model.cpp_mark_to_market_equity;
        point.cash = model.cpp_realized_final_equity;
        point.gross_exposure = model.cpp_gross_mark_notional;
        point.realized_pnl = model.cpp_cumulative_realized_net_pnl;
        point.unrealized_pnl = model.cpp_open_unrealized_pnl;
        point.close_net_pnl = 0.0;
        model.mark_to_market_points.push_back(std::move(point));
        keep_tail(model.mark_to_market_points, static_cast<std::size_t>(point_limit));
    }
    return model;
}

}  // namespace qt::backend
