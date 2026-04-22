#include <cmath>
#include <iomanip>
#include <iostream>
#include <vector>

#include "qt/pricing.hpp"

namespace {

void print_contract(const qt::OptionContract& contract,
                    const qt::BinomialOptionPricer& pricer) {
    const auto result = pricer.price(contract);

    std::cout << "\n=== " << contract.label << " ===\n";
    std::cout << qt::to_string(contract.style) << " "
              << qt::to_string(contract.right) << "\n";
    std::cout << "S=" << contract.spot
              << " K=" << contract.strike
              << " r=" << contract.rate
              << " q=" << contract.dividend_yield
              << " sigma=" << contract.volatility
              << " T=" << contract.maturity_years
              << " N=" << contract.steps << "\n";
    std::cout << "Binomial price=" << std::fixed << std::setprecision(6)
              << result.price << "\n";

    if (contract.style == qt::OptionStyle::European) {
        const double bs = qt::black_scholes_price(contract);
        std::cout << "Black-Scholes price=" << bs
                  << " error=" << std::abs(result.price - bs) << "\n";
    }

    std::cout << "Delta=" << result.delta
              << " Gamma=" << result.gamma
              << " Theta=" << result.theta << "\n";
    std::cout << "u=" << result.up_factor
              << " d=" << result.down_factor
              << " p=" << result.risk_neutral_probability << "\n";
}

}  // namespace

int main() {
    qt::BinomialOptionPricer pricer;

    const std::vector<qt::OptionContract> contracts = {
        {"European ATM Call",
         qt::OptionStyle::European,
         qt::OptionRight::Call,
         100.0,
         100.0,
         0.05,
         0.0,
         0.20,
         1.0,
         400},
        {"European ATM Put",
         qt::OptionStyle::European,
         qt::OptionRight::Put,
         100.0,
         100.0,
         0.05,
         0.0,
         0.20,
         1.0,
         400},
        {"American ATM Put",
         qt::OptionStyle::American,
         qt::OptionRight::Put,
         100.0,
         100.0,
         0.05,
         0.0,
         0.20,
         1.0,
         400},
    };

    for (const auto& contract : contracts) {
        print_contract(contract, pricer);
    }

    return 0;
}
