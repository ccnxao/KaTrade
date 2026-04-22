#include "qt/portfolio_book.hpp"

#include <algorithm>
#include <cmath>

namespace qt {

namespace {

constexpr double kEpsilon = 1e-9;

double signed_fill_qty(OrderSide side, double qty) {
    return side == OrderSide::Buy ? qty : -qty;
}

}  // namespace

PortfolioBook::PortfolioBook(double initial_cash)
    : cash_(initial_cash), equity_(initial_cash) {}

void PortfolioBook::apply_reports(std::span<const ExecutionReport> reports) {
    for (const auto& report : reports) {
        if (report.last_fill_qty <= kEpsilon) {
            continue;
        }

        auto& holding = ensure_holding(report.instrument);
        const double trade_qty = signed_fill_qty(report.side, report.last_fill_qty);
        const double previous_qty = holding.quantity;

        cash_ -= trade_qty * report.last_fill_price;
        cash_ -= report.commission;

        if (std::abs(previous_qty) <= kEpsilon ||
            previous_qty * trade_qty > 0.0) {
            const double new_qty = previous_qty + trade_qty;
            const double weighted_cost =
                std::abs(previous_qty) * holding.avg_cost +
                std::abs(trade_qty) * report.last_fill_price;
            holding.quantity = new_qty;
            holding.avg_cost =
                std::abs(new_qty) <= kEpsilon ? 0.0 : weighted_cost / std::abs(new_qty);
        } else {
            const double closed_qty =
                std::min(std::abs(previous_qty), std::abs(trade_qty));
            realized_pnl_ +=
                closed_qty * (report.last_fill_price - holding.avg_cost) *
                (previous_qty > 0.0 ? 1.0 : -1.0);

            const double new_qty = previous_qty + trade_qty;
            if (std::abs(new_qty) <= kEpsilon) {
                holding.quantity = 0.0;
                holding.avg_cost = 0.0;
            } else if (previous_qty * new_qty > 0.0) {
                holding.quantity = new_qty;
            } else {
                holding.quantity = new_qty;
                holding.avg_cost = report.last_fill_price;
            }
        }

        holding.last_price = report.last_fill_price;
        realized_pnl_ -= report.commission;
        remove_if_flat(report.instrument);
    }
}

void PortfolioBook::mark_to_market(const PriceMap& prices) {
    unrealized_pnl_ = 0.0;
    double market_value_sum = 0.0;

    for (auto& [key, holding] : holdings_) {
        const auto it = prices.find(key);
        if (it != prices.end()) {
            holding.last_price = it->second;
        }

        const double market_value = holding.quantity * holding.last_price;
        market_value_sum += market_value;
        unrealized_pnl_ += holding.quantity * (holding.last_price - holding.avg_cost);
    }

    equity_ = cash_ + market_value_sum;
}

PortfolioSnapshot PortfolioBook::snapshot() const {
    PortfolioSnapshot snapshot;
    snapshot.cash = cash_;
    snapshot.equity = equity_;
    snapshot.realized_pnl = realized_pnl_;
    snapshot.unrealized_pnl = unrealized_pnl_;
    snapshot.cash_weight = std::abs(equity_) <= kEpsilon ? 1.0 : cash_ / equity_;

    snapshot.positions.reserve(holdings_.size());
    for (const auto& [_, holding] : holdings_) {
        if (std::abs(holding.quantity) <= kEpsilon) {
            continue;
        }

        const double market_value = holding.quantity * holding.last_price;
        const double weight =
            std::abs(equity_) <= kEpsilon ? 0.0 : market_value / equity_;
        snapshot.positions.push_back(Position{holding.instrument,
                                              holding.quantity,
                                              holding.avg_cost,
                                              holding.last_price,
                                              market_value,
                                              weight});
    }

    std::sort(snapshot.positions.begin(),
              snapshot.positions.end(),
              [](const Position& lhs, const Position& rhs) {
                  return instrument_key(lhs.instrument) < instrument_key(rhs.instrument);
              });
    return snapshot;
}

PortfolioBook::Holding& PortfolioBook::ensure_holding(const InstrumentId& instrument) {
    const auto key = instrument_key(instrument);
    auto it = holdings_.find(key);
    if (it == holdings_.end()) {
        it = holdings_
                 .emplace(key, Holding{instrument, 0.0, 0.0, 0.0})
                 .first;
    }
    return it->second;
}

void PortfolioBook::remove_if_flat(const InstrumentId& instrument) {
    const auto key = instrument_key(instrument);
    const auto it = holdings_.find(key);
    if (it != holdings_.end() && std::abs(it->second.quantity) <= kEpsilon) {
        holdings_.erase(it);
    }
}

}  // namespace qt
