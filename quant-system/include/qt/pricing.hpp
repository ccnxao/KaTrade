#pragma once

#include <cstddef>
#include <string>

namespace qt {

enum class OptionStyle { European, American };
enum class OptionRight { Call, Put };

struct OptionContract {
    std::string label;
    OptionStyle style{OptionStyle::European};
    OptionRight right{OptionRight::Call};
    double spot{};
    double strike{};
    double rate{};
    double dividend_yield{};
    double volatility{};
    double maturity_years{};
    std::size_t steps{100};
};

struct PricingResult {
    double price{};
    double delta{};
    double gamma{};
    double theta{};
    double up_factor{};
    double down_factor{};
    double risk_neutral_probability{};
};

class BinomialOptionPricer {
public:
    PricingResult price(const OptionContract& contract) const;
};

double black_scholes_price(const OptionContract& contract);
std::string to_string(OptionStyle style);
std::string to_string(OptionRight right);

}  // namespace qt
