#pragma once

#include <span>
#include <unordered_map>

#include "qt/types.hpp"

namespace qt {

class PortfolioBook {
public:
    explicit PortfolioBook(double initial_cash);

    void apply_reports(std::span<const ExecutionReport> reports);
    void mark_to_market(const PriceMap& prices);
    PortfolioSnapshot snapshot() const;

private:
    struct Holding {
        InstrumentId instrument;
        double quantity{};
        double avg_cost{};
        double last_price{};
    };

    Holding& ensure_holding(const InstrumentId& instrument);
    void remove_if_flat(const InstrumentId& instrument);

    std::unordered_map<std::string, Holding> holdings_;
    double cash_{};
    double realized_pnl_{};
    double unrealized_pnl_{};
    double equity_{};
};

}  // namespace qt
