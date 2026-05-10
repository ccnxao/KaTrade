#include "qt/pricing.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <vector>

namespace qt {

namespace {

double payoff(const OptionContract& contract, double spot) {
    if (contract.right == OptionRight::Call) {
        return std::max(spot - contract.strike, 0.0);
    }
    return std::max(contract.strike - spot, 0.0);
}

double normal_cdf(double x) {
    return 0.5 * std::erfc(-x / std::sqrt(2.0));
}

void validate_contract(const OptionContract& contract) {
    if (contract.spot <= 0.0) {
        throw std::runtime_error("option spot must be positive");
    }
    if (contract.strike <= 0.0) {
        throw std::runtime_error("option strike must be positive");
    }
    if (contract.volatility < 0.0) {
        throw std::runtime_error("option volatility must be non-negative");
    }
    if (contract.maturity_years <= 0.0) {
        throw std::runtime_error("option maturity must be positive");
    }
    if (contract.steps == 0) {
        throw std::runtime_error("binomial steps must be positive");
    }
}

}  // namespace

PricingResult BinomialOptionPricer::price(const OptionContract& contract) const {
    validate_contract(contract);

    const double dt = contract.maturity_years / static_cast<double>(contract.steps);
    const double sigma_sqrt_dt = contract.volatility * std::sqrt(dt);
    const double up = std::exp(sigma_sqrt_dt);
    const double down = up == 0.0 ? 0.0 : 1.0 / up;
    const double growth = std::exp((contract.rate - contract.dividend_yield) * dt);
    const double discount = std::exp(-contract.rate * dt);

    if (std::abs(up - down) <= 1e-12) {
        throw std::runtime_error("binomial tree degenerated: up == down");
    }

    const double probability = (growth - down) / (up - down);
    if (probability < 0.0 || probability > 1.0) {
        throw std::runtime_error(
            "risk-neutral probability is out of bounds; adjust steps or parameters");
    }

    std::vector<double> values(contract.steps + 1, 0.0);
    for (std::size_t down_moves = 0; down_moves <= contract.steps; ++down_moves) {
        const std::size_t up_moves = contract.steps - down_moves;
        const double terminal_spot =
            contract.spot * std::pow(up, static_cast<double>(up_moves)) *
            std::pow(down, static_cast<double>(down_moves));
        values[down_moves] = payoff(contract, terminal_spot);
    }

    double step2_uu = std::numeric_limits<double>::quiet_NaN();
    double step2_ud = std::numeric_limits<double>::quiet_NaN();
    double step2_dd = std::numeric_limits<double>::quiet_NaN();
    double step1_up = std::numeric_limits<double>::quiet_NaN();
    double step1_down = std::numeric_limits<double>::quiet_NaN();

    for (std::size_t step = contract.steps; step > 0; --step) {
        for (std::size_t node = 0; node < step; ++node) {
            const double continuation =
                discount * (probability * values[node] +
                            (1.0 - probability) * values[node + 1]);

            if (contract.style == OptionStyle::American) {
                const std::size_t up_moves = (step - 1) - node;
                const std::size_t down_moves = node;
                const double spot =
                    contract.spot * std::pow(up, static_cast<double>(up_moves)) *
                    std::pow(down, static_cast<double>(down_moves));
                values[node] = std::max(continuation, payoff(contract, spot));
            } else {
                values[node] = continuation;
            }
        }

        if (step == 3) {
            step2_uu = values[0];
            step2_ud = values[1];
            step2_dd = values[2];
        }
        if (step == 2) {
            step1_up = values[0];
            step1_down = values[1];
        }
    }

    PricingResult result;
    result.price = values[0];
    result.up_factor = up;
    result.down_factor = down;
    result.risk_neutral_probability = probability;

    const double spot_up = contract.spot * up;
    const double spot_down = contract.spot * down;
    if (!std::isnan(step1_up) && !std::isnan(step1_down) &&
        std::abs(spot_up - spot_down) > 1e-12) {
        result.delta = (step1_up - step1_down) / (spot_up - spot_down);
    }

    if (!std::isnan(step2_uu) && !std::isnan(step2_ud) && !std::isnan(step2_dd)) {
        const double spot_uu = contract.spot * up * up;
        const double spot_ud = contract.spot;
        const double spot_dd = contract.spot * down * down;

        const double delta_up = (step2_uu - step2_ud) / (spot_uu - spot_ud);
        const double delta_down = (step2_ud - step2_dd) / (spot_ud - spot_dd);
        result.gamma =
            (delta_up - delta_down) / ((spot_uu - spot_dd) * 0.5);
        result.theta = (step2_ud - result.price) / (2.0 * dt);
    }

    return result;
}

double black_scholes_price(const OptionContract& contract) {
    validate_contract(contract);
    if (contract.style != OptionStyle::European) {
        throw std::runtime_error(
            "black_scholes_price only supports European options");
    }

    if (contract.volatility == 0.0) {
        const double forward =
            contract.spot *
            std::exp((contract.rate - contract.dividend_yield) *
                     contract.maturity_years);
        const double intrinsic =
            contract.right == OptionRight::Call
                ? std::max(forward - contract.strike, 0.0)
                : std::max(contract.strike - forward, 0.0);
        return std::exp(-contract.rate * contract.maturity_years) * intrinsic;
    }

    const double sqrt_t = std::sqrt(contract.maturity_years);
    const double sigma_t = contract.volatility * sqrt_t;
    const double d1 =
        (std::log(contract.spot / contract.strike) +
         (contract.rate - contract.dividend_yield +
          0.5 * contract.volatility * contract.volatility) *
             contract.maturity_years) /
        sigma_t;
    const double d2 = d1 - sigma_t;

    const double discounted_spot =
        contract.spot * std::exp(-contract.dividend_yield * contract.maturity_years);
    const double discounted_strike =
        contract.strike * std::exp(-contract.rate * contract.maturity_years);

    if (contract.right == OptionRight::Call) {
        return discounted_spot * normal_cdf(d1) -
               discounted_strike * normal_cdf(d2);
    }
    return discounted_strike * normal_cdf(-d2) -
           discounted_spot * normal_cdf(-d1);
}

std::string to_string(OptionStyle style) {
    switch (style) {
        case OptionStyle::European:
            return "European";
        case OptionStyle::American:
            return "American";
    }
    return "Unknown";
}

std::string to_string(OptionRight right) {
    switch (right) {
        case OptionRight::Call:
            return "Call";
        case OptionRight::Put:
            return "Put";
    }
    return "Unknown";
}

}  // namespace qt
