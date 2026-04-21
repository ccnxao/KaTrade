#pragma once

#include <cmath>
#include <cstdint>
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

inline std::string instrument_key(const InstrumentId& instrument) {
    return instrument.symbol + "." + instrument.exchange;
}

struct Bar {
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
    double momentum_weight{0.33};
    double mean_revert_weight{0.33};
    double defensive_weight{0.34};
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
};

struct ExecutionReport {
    std::string order_id;
    InstrumentId instrument;
    double filled_qty{};
    double avg_price{};
    double commission{};
    double slippage_bps{};
    std::string broker_status;
};

struct Position {
    InstrumentId instrument;
    double weight{};
};

struct PortfolioSnapshot {
    std::vector<Position> positions;
    double cash_weight{1.0};
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

}  // namespace qt
