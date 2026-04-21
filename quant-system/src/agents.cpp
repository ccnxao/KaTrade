#include "qt/agents.hpp"

#include <algorithm>
#include <cmath>

namespace qt {

namespace {

double bar_return(const Bar& bar) {
    if (bar.open == 0.0) {
        return 0.0;
    }
    return (bar.close - bar.open) / bar.open;
}

bool is_defensive_asset(const InstrumentId& instrument) {
    return instrument.symbol == "GLD" || instrument.symbol == "IEF" ||
           instrument.symbol == "SHY";
}

double feature_or(const FeatureFrame& features,
                  const std::string& key,
                  double fallback) {
    const auto it = features.find(key);
    return it == features.end() ? fallback : it->second;
}

}  // namespace

std::string_view RuleBasedRegimeAgent::name() const noexcept {
    return "rule_based_regime";
}

RegimeState RuleBasedRegimeAgent::detect_regime(const FeatureFrame& features) {
    const double vol = feature_or(features, "market.realized_vol_20d", 0.15);
    const double corr = feature_or(features, "market.avg_corr_20d", 0.35);
    const double adx = feature_or(features, "market.adx_20d", 20.0);
    const double ret = feature_or(features, "market.ret_20d", 0.0);

    if (vol > 0.30 && corr > 0.80) {
        return {Regime::Crisis, 0.85, 0.10, 0.10, 0.80, "rule_v1"};
    }
    if (adx > 25.0 && std::abs(ret) > 0.02 && vol < 0.30) {
        return {Regime::Trending, 0.75, 0.70, 0.20, 0.10, "rule_v1"};
    }
    if (adx < 18.0 && vol < 0.20) {
        return {Regime::MeanReverting, 0.65, 0.15, 0.70, 0.15, "rule_v1"};
    }
    return {Regime::Uncertain, 0.35, 0.33, 0.33, 0.34, "rule_v1"};
}

std::string_view MomentumAgent::name() const noexcept {
    return "momentum";
}

std::vector<Signal> MomentumAgent::generate_signals(const std::vector<Bar>& bars,
                                                    const FeatureFrame&,
                                                    const PortfolioSnapshot&,
                                                    const RegimeState&) {
    std::vector<Signal> signals;
    for (const auto& bar : bars) {
        const double ret = bar_return(bar);
        if (ret <= 0.0) {
            continue;
        }
        signals.push_back(
            Signal{std::string{name()}, bar.instrument, ret * 2.5, 0.65});
    }
    return signals;
}

std::string_view MeanReversionAgent::name() const noexcept {
    return "mean_reversion";
}

std::vector<Signal> MeanReversionAgent::generate_signals(
    const std::vector<Bar>& bars,
    const FeatureFrame&,
    const PortfolioSnapshot&,
    const RegimeState&) {
    std::vector<Signal> signals;
    for (const auto& bar : bars) {
        const double ret = bar_return(bar);
        if (std::abs(ret) < 0.015) {
            continue;
        }
        signals.push_back(
            Signal{std::string{name()}, bar.instrument, -ret * 1.8, 0.55});
    }
    return signals;
}

std::string_view DefensiveAgent::name() const noexcept {
    return "defensive";
}

std::vector<Signal> DefensiveAgent::generate_signals(const std::vector<Bar>& bars,
                                                     const FeatureFrame& features,
                                                     const PortfolioSnapshot&,
                                                     const RegimeState& regime) {
    std::vector<Signal> signals;
    const double market_vol = feature_or(features, "market.realized_vol_20d", 0.15);
    const double stress_boost =
        regime.regime == Regime::Crisis ? 0.10 : std::max(0.0, market_vol - 0.18);

    for (const auto& bar : bars) {
        if (!is_defensive_asset(bar.instrument)) {
            continue;
        }
        signals.push_back(Signal{std::string{name()},
                                 bar.instrument,
                                 0.10 + stress_boost,
                                 regime.regime == Regime::Crisis ? 0.90 : 0.60});
    }
    return signals;
}

}  // namespace qt
