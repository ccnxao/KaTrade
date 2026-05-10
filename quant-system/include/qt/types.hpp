#pragma once

#include <cmath>
#include <cstdint>
#include <deque>
#include <map>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

namespace qt {

using FeatureFrame = std::unordered_map<std::string, double>;
using PriceMap = std::unordered_map<std::string, double>;

struct InstrumentId {
    std::string symbol;
    std::string exchange;
};

inline const std::string& instrument_key(const InstrumentId& instrument) {
    // node-based map 保证引用稳定；每个品种 key 只拼接一次
    static std::map<std::string, std::string> cache;
    auto combined = instrument.symbol + "." + instrument.exchange;
    auto [it, _] = cache.try_emplace(combined, combined);
    return it->second;
}

struct Bar {
    std::int64_t timestamp{};
    InstrumentId instrument;
    double open{};
    double high{};
    double low{};
    double close{};
    double volume{};
};

enum class Regime { Trending, MeanReverting, Crisis, Uncertain };

struct RegimeState {
    Regime regime{Regime::Uncertain};
    double confidence{0.0};
    double momentum_weight{0.33};     // M：趋势策略资金权重
    double mean_revert_weight{0.33};  // R：反转策略资金权重
    double defensive_weight{0.34};    // D：防御策略资金权重
    double trending_prob{0.33};       // P(Trending) — 趋势状态概率
    double mean_revert_prob{0.33};    // P(MeanReverting) — 反转状态概率
    double defensive_prob{0.34};      // P(Defensive/Crisis) — 防御状态概率
    std::string model_version{"rule_v1"};
};

struct Signal {
    std::string strategy_id;
    InstrumentId instrument;
    double score{};
    double confidence{};
};

struct TargetPosition {
    InstrumentId instrument;
    double target_weight{};
    std::string strategy_id;
};

struct TargetPortfolio {
    std::vector<TargetPosition> positions;
    double expected_turnover{};
    double expected_cost_bps{};
    std::string optimizer_version{"simple_v1"};
};

enum class RiskAction { Approve, Reduce, Reject, Halt };

struct RiskDecision {
    RiskAction action{RiskAction::Approve};
    std::string reason;
    TargetPortfolio adjusted_portfolio;
};

enum class OrderSide { Buy, Sell };
enum class OrderType { Market, Limit };

struct OrderIntent {
    InstrumentId instrument;
    OrderSide side{OrderSide::Buy};
    OrderType type{OrderType::Market};
    double quantity{};
    double reference_price{};
    std::string parent_decision_id;
    std::string strategy_id;
};

enum class OrderStatus {
    Created,
    Submitted,
    PartiallyFilled,
    Filled,
    Cancelled,
    Rejected
};

struct OrderRecord {
    std::string order_id;
    OrderIntent intent;
    OrderStatus status{OrderStatus::Created};
    double filled_qty{};
    double remaining_qty{};
    double avg_price{};
    double commission{};
};

struct ExecutionReport {
    std::string order_id;
    InstrumentId instrument;
    OrderSide side{OrderSide::Buy};
    double last_fill_qty{};
    double last_fill_price{};
    double cumulative_filled_qty{};
    double remaining_qty{};
    double avg_price{};
    double commission{};
    double slippage_bps{};
    OrderStatus status{OrderStatus::Submitted};
    std::string broker_status;
};

struct Position {
    InstrumentId instrument;
    double quantity{};
    double avg_cost{};
    double market_price{};
    double market_value{};
    double weight{};
};

struct PortfolioSnapshot {
    std::vector<Position> positions;
    double cash{};
    double equity{};
    double cash_weight{1.0};
    double realized_pnl{};
    double unrealized_pnl{};
};

struct EquityPoint {
    std::size_t cycle_index{};
    std::string label;
    double equity{};
    double cash{};
    double gross_exposure{};
    double realized_pnl{};
    double unrealized_pnl{};
};

inline double gross_exposure(const TargetPortfolio& portfolio) {
    double gross = 0.0;
    for (const auto& position : portfolio.positions) {
        gross += std::abs(position.target_weight);
    }
    return gross;
}

inline double gross_exposure(const PortfolioSnapshot& portfolio) {
    double gross = 0.0;
    for (const auto& position : portfolio.positions) {
        gross += std::abs(position.weight);
    }
    return gross;
}

inline std::optional<double> find_weight(const PortfolioSnapshot& portfolio,
                                         const InstrumentId& instrument) {
    const auto key = instrument_key(instrument);
    for (const auto& position : portfolio.positions) {
        if (instrument_key(position.instrument) == key) {
            return position.weight;
        }
    }
    return std::nullopt;
}

inline std::string to_string(Regime regime) {
    switch (regime) {
        case Regime::Trending:
            return "Trending";
        case Regime::MeanReverting:
            return "MeanReverting";
        case Regime::Crisis:
            return "Crisis";
        case Regime::Uncertain:
            return "Uncertain";
    }
    return "Unknown";
}

inline std::string to_string(RiskAction action) {
    switch (action) {
        case RiskAction::Approve:
            return "Approve";
        case RiskAction::Reduce:
            return "Reduce";
        case RiskAction::Reject:
            return "Reject";
        case RiskAction::Halt:
            return "Halt";
    }
    return "Unknown";
}

inline std::string to_string(OrderSide side) {
    switch (side) {
        case OrderSide::Buy:
            return "Buy";
        case OrderSide::Sell:
            return "Sell";
    }
    return "Unknown";
}

inline std::string to_string(OrderStatus status) {
    switch (status) {
        case OrderStatus::Created:
            return "Created";
        case OrderStatus::Submitted:
            return "Submitted";
        case OrderStatus::PartiallyFilled:
            return "PartiallyFilled";
        case OrderStatus::Filled:
            return "Filled";
        case OrderStatus::Cancelled:
            return "Cancelled";
        case OrderStatus::Rejected:
            return "Rejected";
    }
    return "Unknown";
}

}  // namespace qt
