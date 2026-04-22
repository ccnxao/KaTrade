#include <cmath>
#include <iostream>
#include <string>
#include <vector>

#include "qt/pricing.hpp"

namespace {

bool expect_near(const std::string& label,
                 double actual,
                 double expected,
                 double tolerance) {
    const double error = std::abs(actual - expected);
    if (error > tolerance) {
        std::cerr << label << " failed: actual=" << actual
                  << " expected=" << expected
                  << " tolerance=" << tolerance << "\n";
        return false;
    }
    return true;
}

bool expect_true(const std::string& label, bool condition, const std::string& message) {
    if (!condition) {
        std::cerr << label << " failed: " << message << "\n";
        return false;
    }
    return true;
}

}  // namespace

int main() {
    qt::BinomialOptionPricer pricer;
    bool ok = true;

    const qt::OptionContract european_call{
        "European ATM Call",
        qt::OptionStyle::European,
        qt::OptionRight::Call,
        100.0,
        100.0,
        0.05,
        0.0,
        0.20,
        1.0,
        400,
    };

    const qt::OptionContract european_put{
        "European ATM Put",
        qt::OptionStyle::European,
        qt::OptionRight::Put,
        100.0,
        100.0,
        0.05,
        0.0,
        0.20,
        1.0,
        400,
    };

    const qt::OptionContract american_call{
        "American ATM Call",
        qt::OptionStyle::American,
        qt::OptionRight::Call,
        100.0,
        100.0,
        0.05,
        0.0,
        0.20,
        1.0,
        400,
    };

    const qt::OptionContract american_put{
        "American ATM Put",
        qt::OptionStyle::American,
        qt::OptionRight::Put,
        100.0,
        100.0,
        0.05,
        0.0,
        0.20,
        1.0,
        400,
    };

    const auto euro_call_result = pricer.price(european_call);
    const auto euro_put_result = pricer.price(european_put);
    const auto american_call_result = pricer.price(american_call);
    const auto american_put_result = pricer.price(american_put);

    const double bs_call = qt::black_scholes_price(european_call);
    const double bs_put = qt::black_scholes_price(european_put);

    ok &= expect_near("european call vs BS",
                      euro_call_result.price,
                      bs_call,
                      0.03);
    ok &= expect_near("european put vs BS",
                      euro_put_result.price,
                      bs_put,
                      0.03);
    ok &= expect_near("american call equals european call without dividends",
                      american_call_result.price,
                      euro_call_result.price,
                      0.03);
    ok &= expect_true("american put premium",
                      american_put_result.price >= euro_put_result.price,
                      "american put should not be cheaper than european put");
    ok &= expect_near("american put reference price",
                      american_put_result.price,
                      6.09,
                      0.08);
    ok &= expect_true("call delta bounds",
                      euro_call_result.delta > 0.0 && euro_call_result.delta < 1.0,
                      "call delta should be between 0 and 1");
    ok &= expect_true("put delta bounds",
                      euro_put_result.delta > -1.0 && euro_put_result.delta < 0.0,
                      "put delta should be between -1 and 0");

    if (!ok) {
        return 1;
    }

    std::cout << "pricing check passed\n";
    std::cout << "euro_call=" << euro_call_result.price
              << " euro_put=" << euro_put_result.price
              << " american_put=" << american_put_result.price << "\n";
    return 0;
}
