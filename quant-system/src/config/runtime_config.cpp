#include "qt/runtime_config.hpp"

#include <cstdio>
#include <fstream>
#include <stdexcept>
#include <string_view>
#include <sstream>

namespace qt {

namespace {

std::string trim(std::string value) {
    const auto is_space = [](unsigned char ch) {
        return ch == ' ' || ch == '\t' || ch == '\r' || ch == '\n';
    };

    while (!value.empty() && is_space(static_cast<unsigned char>(value.front()))) {
        value.erase(value.begin());
    }
    while (!value.empty() && is_space(static_cast<unsigned char>(value.back()))) {
        value.pop_back();
    }
    return value;
}

bool parse_bool(const std::string& value) {
    if (value == "true" || value == "1" || value == "yes") {
        return true;
    }
    if (value == "false" || value == "0" || value == "no") {
        return false;
    }
    throw std::runtime_error("invalid boolean value: " + value);
}

double parse_double(const std::string& value) {
    try {
        return std::stod(value);
    } catch (const std::exception&) {
        throw std::runtime_error("invalid numeric value: " + value);
    }
}

int parse_int(const std::string& value) {
    try {
        std::size_t consumed = 0;
        const int parsed = std::stoi(value, &consumed);
        if (consumed != value.size()) {
            throw std::runtime_error("trailing characters");
        }
        return parsed;
    } catch (const std::exception&) {
        throw std::runtime_error("invalid integer value: " + value);
    }
}

int parse_positive_int(const std::string& value, const std::string& key) {
    const int parsed = parse_int(value);
    if (parsed <= 0) {
        throw std::runtime_error(key + " must be > 0");
    }
    return parsed;
}

double parse_bounded_double(const std::string& value,
                            const std::string& key,
                            double min_value,
                            double max_value) {
    const double parsed = parse_double(value);
    if (parsed < min_value || parsed > max_value) {
        throw std::runtime_error(key + " must be between " +
                                 std::to_string(min_value) + " and " +
                                 std::to_string(max_value));
    }
    return parsed;
}

std::vector<std::string> parse_csv_list(const std::string& value) {
    std::vector<std::string> items;
    std::stringstream stream(value);
    std::string item;
    while (std::getline(stream, item, ',')) {
        item = trim(item);
        if (!item.empty()) {
            items.push_back(item);
        }
    }
    return items;
}

}  // namespace

RuntimeConfig load_runtime_config(const std::string& path) {
    std::ifstream input(path);
    if (!input.is_open()) {
        throw std::runtime_error("failed to open config file: " + path);
    }

    RuntimeConfig config;
    std::string line;
    std::size_t line_number = 0;

    while (std::getline(input, line)) {
        ++line_number;
        line = trim(line);
        if (line.empty() || line.starts_with('#')) {
            continue;
        }

        const auto delimiter = line.find('=');
        if (delimiter == std::string::npos) {
            throw std::runtime_error("invalid config line " +
                                     std::to_string(line_number));
        }

        const std::string key = trim(line.substr(0, delimiter));
        const std::string value = trim(line.substr(delimiter + 1));

        if (key == "replay_path") {
            config.replay_path = value;
        } else if (key == "event_log_path") {
            config.event_log_path = value;
        } else if (key == "report_json_path") {
            config.report_json_path = value;
        } else if (key == "strategy.enabled") {
            config.strategy_ids = parse_csv_list(value);
        } else if (key == "history.mode") {
            if (value != "local" && value != "remote") {
                throw std::runtime_error("history.mode must be local or remote");
            }
            config.history_mode = value;
        } else if (key == "history.server_url") {
            config.history_server_url = value;
        } else if (key == "history.contracts") {
            config.history_contracts = parse_csv_list(value);
        } else if (key == "history.cache_dir") {
            config.history_cache_dir = value;
        } else if (key == "history.cache_ttl_seconds") {
            config.history_cache_ttl_seconds = parse_int(value);
            if (config.history_cache_ttl_seconds < 0) {
                throw std::runtime_error("history.cache_ttl_seconds must be >= 0");
            }
        } else if (key == "history.bar") {
            config.history_bar = value.empty() ? "1m" : value;
        } else if (key == "history.start") {
            config.history_start = value;
        } else if (key == "history.end") {
            config.history_end = value;
        } else if (key == "history.max_pages") {
            config.history_max_pages = parse_positive_int(value, key);
        } else if (key == "print_cycles") {
            config.print_cycles = parse_bool(value);
        } else if (key == "print_event_stream") {
            config.print_event_stream = parse_bool(value);
        } else if (key == "metrics.drawdown_stride") {
            config.metrics_drawdown_stride = parse_positive_int(value, key);
        } else if (key == "strategy.donchian.lookback") {
            config.strategy_donchian_lookback = parse_positive_int(value, key);
        } else if (key == "strategy.ma_cross.fast_window") {
            config.strategy_ma_cross_fast_window = parse_positive_int(value, key);
        } else if (key == "strategy.ma_cross.slow_window") {
            config.strategy_ma_cross_slow_window = parse_positive_int(value, key);
        } else if (key == "strategy.macd.fast_alpha") {
            config.strategy_macd_fast_alpha = parse_bounded_double(value, key, 0.01, 1.0);
        } else if (key == "strategy.macd.slow_alpha") {
            config.strategy_macd_slow_alpha = parse_bounded_double(value, key, 0.01, 1.0);
        } else if (key == "strategy.macd.signal_alpha") {
            config.strategy_macd_signal_alpha = parse_bounded_double(value, key, 0.01, 1.0);
        } else if (key == "strategy.ema_slope.alpha") {
            config.strategy_ema_slope_alpha = parse_bounded_double(value, key, 0.01, 1.0);
        } else if (key == "strategy.ema_slope.min_slope") {
            config.strategy_ema_slope_min_slope = parse_bounded_double(value, key, 0.0001, 0.20);
        } else if (key == "strategy.keltner.alpha") {
            config.strategy_keltner_alpha = parse_bounded_double(value, key, 0.01, 1.0);
        } else if (key == "strategy.keltner.multiplier") {
            config.strategy_keltner_multiplier = parse_bounded_double(value, key, 0.1, 10.0);
        } else if (key == "strategy.volume_spike.alpha") {
            config.strategy_volume_spike_alpha = parse_bounded_double(value, key, 0.01, 1.0);
        } else if (key == "strategy.volume_spike.multiplier") {
            config.strategy_volume_spike_multiplier = parse_bounded_double(value, key, 1.0, 20.0);
        } else if (key == "strategy.micro_scalper.min_return") {
            config.strategy_micro_scalper_min_return = parse_bounded_double(value, key, 0.00005, 0.05);
        } else if (key == "strategy.micro_scalper.min_body_ratio") {
            config.strategy_micro_scalper_min_body_ratio = parse_bounded_double(value, key, 0.05, 0.95);
        } else if (key == "strategy.spread_capture.alpha") {
            config.strategy_spread_capture_alpha = parse_bounded_double(value, key, 0.01, 1.0);
        } else if (key == "strategy.spread_capture.threshold") {
            config.strategy_spread_capture_threshold = parse_bounded_double(value, key, 0.05, 5.0);
        } else if (key == "strategy.order_flow.volume_alpha") {
            config.strategy_order_flow_volume_alpha = parse_bounded_double(value, key, 0.01, 1.0);
        } else if (key == "strategy.order_flow.imbalance_threshold") {
            config.strategy_order_flow_imbalance_threshold = parse_bounded_double(value, key, 0.05, 0.95);
        } else if (key == "strategy.inventory_skew.neutral_band") {
            config.strategy_inventory_skew_neutral_band = parse_bounded_double(value, key, 0.005, 0.30);
        } else if (key == "strategy.bollinger.window") {
            config.strategy_bollinger_window = parse_positive_int(value, key);
        } else if (key == "strategy.bollinger.band_width") {
            config.strategy_bollinger_band_width = parse_bounded_double(value, key, 0.1, 10.0);
        } else if (key == "strategy.rsi.window") {
            config.strategy_rsi_window = parse_positive_int(value, key);
        } else if (key == "strategy.rsi.oversold") {
            config.strategy_rsi_oversold = parse_bounded_double(value, key, 1.0, 49.0);
        } else if (key == "strategy.rsi.overbought") {
            config.strategy_rsi_overbought = parse_bounded_double(value, key, 51.0, 99.0);
        } else if (key == "strategy.zscore.window") {
            config.strategy_zscore_window = parse_positive_int(value, key);
        } else if (key == "strategy.zscore.threshold") {
            config.strategy_zscore_threshold = parse_bounded_double(value, key, 0.1, 10.0);
        } else if (key == "initial_cash") {
            config.initial_cash = parse_double(value);
        } else if (key == "optimizer.type") {
            if (value != "simple" && value != "markowitz" && value != "risk_parity") {
                throw std::runtime_error("optimizer.type must be simple, markowitz, or risk_parity");
            }
            config.optimizer_type = value;
        } else if (key == "optimizer.max_single_weight") {
            config.optimizer_max_single_weight = parse_double(value);
        } else if (key == "optimizer.max_gross") {
            config.optimizer_max_gross = parse_double(value);
        } else if (key == "optimizer.risk_aversion") {
            config.optimizer_risk_aversion = parse_bounded_double(value, key, 0.1, 20.0);
        } else if (key == "optimizer.target_vol") {
            config.optimizer_target_vol = parse_bounded_double(value, key, 0.01, 0.50);
        } else if (key == "optimizer.cov_lookback") {
            config.optimizer_cov_lookback = parse_positive_int(value, key);
        } else if (key == "risk.max_single_weight") {
            config.risk_max_single_weight = parse_double(value);
        } else if (key == "risk.max_gross") {
            config.risk_max_gross = parse_double(value);
        } else if (key == "risk.max_order_notional") {
            config.risk_max_order_notional = parse_double(value);
        } else if (key == "risk.kill_switch") {
            config.risk_kill_switch = parse_bool(value);
        } else if (key == "risk.drawdown_limit") {
            config.risk_drawdown_limit = parse_bounded_double(value, key, 0.01, 0.50);
        } else if (key == "risk.vol_threshold") {
            config.risk_vol_threshold = parse_bounded_double(value, key, 0.05, 0.80);
        } else if (key == "risk.vol_reduction") {
            config.risk_vol_reduction = parse_bounded_double(value, key, 0.10, 0.90);
        } else if (key == "risk.stress_tolerance") {
            config.risk_stress_tolerance = parse_bounded_double(value, key, 0.01, 0.50);
        } else if (key == "risk.budget_scale") {
            config.risk_budget_scale = parse_bounded_double(value, key, 0.10, 1.0);
        } else if (key == "risk.turnover_limit") {
            config.risk_turnover_limit = parse_bounded_double(value, key, 0.01, 2.0);
        } else if (key == "execution.min_rebalance_delta") {
            config.execution_min_rebalance_delta = parse_double(value);
        } else if (key == "execution.max_participation_rate") {
            config.execution_max_participation_rate = parse_double(value);
        } else if (key == "execution.maker_offset_bps") {
            config.execution_maker_offset_bps = parse_bounded_double(value, key, 0.0, 100.0);
        } else if (key == "execution.maker_fee_bps") {
            config.execution_maker_fee_bps = parse_bounded_double(value, key, 0.0, 100.0);
        } else if (key == "execution.max_expected_cost_bps") {
            config.execution_max_expected_cost_bps = parse_bounded_double(value, key, 0.0, 500.0);
        } else if (key == "execution.slippage_bps") {
            config.execution_slippage_bps = parse_bounded_double(value, key, 0.0, 100.0);
        } else if (key == "execution.commission_bps") {
            config.execution_commission_bps = parse_bounded_double(value, key, 0.0, 50.0);
        } else if (key == "execution.tp_ratio") {
            config.execution_tp_ratio = parse_bounded_double(value, key, 0.0, 0.50);
        } else if (key == "execution.sl_ratio") {
            config.execution_sl_ratio = parse_bounded_double(value, key, 0.0, 0.50);
        } else if (key == "execution.partial_fill_prob") {
            config.execution_partial_fill_prob = parse_bounded_double(value, key, 0.0, 1.0);
        } else if (key == "execution.default_ord_type") {
            config.execution_default_ord_type = value;
        } else if (key == "execution.pending_order_ttl_bars") {
            config.execution_pending_order_ttl_bars = parse_positive_int(value, key);
        } else if (key == "execution.derivatives.enabled") {
            config.execution_derivatives_enabled = parse_bool(value);
        } else if (key == "execution.derivatives.inst_type") {
            if (value != "SWAP" && value != "FUTURES") {
                throw std::runtime_error("execution.derivatives.inst_type must be SWAP or FUTURES");
            }
            config.execution_derivatives_inst_type = value;
        } else if (key == "execution.derivatives.margin_mode") {
            if (value != "isolated" && value != "cross") {
                throw std::runtime_error("execution.derivatives.margin_mode must be isolated or cross");
            }
            config.execution_derivatives_margin_mode = value;
        } else if (key == "execution.derivatives.position_mode") {
            if (value != "net" && value != "long_short") {
                throw std::runtime_error("execution.derivatives.position_mode must be net or long_short");
            }
            config.execution_derivatives_position_mode = value;
        } else if (key == "execution.derivatives.max_exchange_leverage") {
            config.execution_derivatives_max_exchange_leverage =
                parse_bounded_double(value, key, 1.0, 20.0);
        } else if (key == "execution.derivatives.max_effective_leverage") {
            config.execution_derivatives_max_effective_leverage =
                parse_bounded_double(value, key, 0.0, 10.0);
        } else if (key == "execution.derivatives.max_unit_effective_leverage") {
            config.execution_derivatives_max_unit_effective_leverage =
                parse_bounded_double(value, key, 0.0, 10.0);
        } else if (key == "execution.trade_unit.base_notional_usdt") {
            config.execution_trade_unit_base_notional_usdt =
                parse_bounded_double(value, key, 0.1, 1000.0);
        } else if (key == "execution.trade_unit.agent_leverage_enabled") {
            config.execution_trade_unit_agent_leverage_enabled = parse_bool(value);
        } else if (key == "execution.trade_unit.agent_max_step") {
            config.execution_trade_unit_agent_max_step =
                parse_bounded_double(value, key, 0.0, 5.0);
        } else if (key == "capital.total_capital_ratio") {
            config.agent_total_capital_ratio = parse_bounded_double(value, key, 0.1, 1.0);
        } else if (key == "capital.min_capital_ratio") {
            config.agent_min_capital_ratio = parse_bounded_double(value, key, 0.01, 0.2);
        } else if (key == "capital.max_capital_ratio") {
            config.agent_max_capital_ratio = parse_bounded_double(value, key, 0.1, 0.5);
        } else if (key == "capital.rebalance_cycles") {
            config.agent_capital_rebalance_cycles = std::clamp(parse_int(value), 20, 1000);
        } else if (key == "capital.performance_window") {
            config.agent_performance_window = std::clamp(parse_int(value), 30, 500);
        } else if (key == "capital.min_trades_for_review") {
            config.agent_min_trades_for_review = std::clamp(parse_int(value), 5, 200);
        } else if (key == "capital.elimination_sharpe") {
            config.agent_elimination_sharpe = parse_double(value);
        } else if (key == "capital.elimination_drawdown") {
            config.agent_elimination_drawdown = parse_bounded_double(value, key, 0.05, 0.5);
        } else if (key == "capital.grace_cycles") {
            config.agent_elimination_grace_cycles = std::clamp(parse_int(value), 50, 1000);
        } else if (key == "capital.auto_activate") {
            config.agent_auto_activate = parse_bool(value);
        } else if (key == "capital.max_active") {
            config.agent_max_active = std::clamp(parse_int(value), 2, 18);
        } else if (key == "regime.detector") {
            config.regime_detector = value;
        } else if (key == "regime.hmm_states") {
            config.regime_hmm_states = std::clamp(parse_int(value), 2, 5);
        } else if (key == "regime.oem_dim") {
            config.regime_oem_dim = std::clamp(parse_int(value), 1, 4);
        } else if (key == "regime.rule.crisis_vol") {
            config.regime_rule_crisis_vol = parse_bounded_double(value, key, 0.10, 0.60);
        } else if (key == "regime.rule.crisis_corr") {
            config.regime_rule_crisis_corr = parse_bounded_double(value, key, 0.30, 1.00);
        } else if (key == "regime.rule.trending_adx") {
            config.regime_rule_trending_adx = parse_bounded_double(value, key, 10.0, 40.0);
        } else if (key == "regime.rule.trending_ret") {
            config.regime_rule_trending_ret = parse_bounded_double(value, key, 0.01, 0.20);
        } else if (key == "regime.rule.trending_vol_cap") {
            config.regime_rule_trending_vol_cap = parse_bounded_double(value, key, 0.10, 0.60);
        } else if (key == "regime.rule.mean_revert_adx") {
            config.regime_rule_mean_revert_adx = parse_bounded_double(value, key, 10.0, 40.0);
        } else if (key == "regime.rule.mean_revert_vol_cap") {
            config.regime_rule_mean_revert_vol_cap = parse_bounded_double(value, key, 0.10, 0.60);
        } else {
            // 跳过 C++ 不使用的 key（Python 端可能需要）
            fprintf(stderr, "[config] skipping unknown key: %s\n", key.c_str());
        }
    }

    if (config.strategy_ma_cross_fast_window >= config.strategy_ma_cross_slow_window) {
        throw std::runtime_error("strategy.ma_cross.fast_window must be less than strategy.ma_cross.slow_window");
    }
    if (config.strategy_macd_fast_alpha <= config.strategy_macd_slow_alpha) {
        throw std::runtime_error("strategy.macd.fast_alpha must be greater than strategy.macd.slow_alpha");
    }
    if (config.strategy_rsi_oversold >= config.strategy_rsi_overbought) {
        throw std::runtime_error("strategy.rsi.oversold must be less than strategy.rsi.overbought");
    }

    return config;
}

}  // namespace qt
