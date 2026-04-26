#include "qt/runtime_config.hpp"

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
        } else if (key == "print_cycles") {
            config.print_cycles = parse_bool(value);
        } else if (key == "print_event_stream") {
            config.print_event_stream = parse_bool(value);
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
        } else if (key == "initial_cash") {
            config.initial_cash = parse_double(value);
        } else if (key == "optimizer.max_single_weight") {
            config.optimizer_max_single_weight = parse_double(value);
        } else if (key == "optimizer.max_gross") {
            config.optimizer_max_gross = parse_double(value);
        } else if (key == "risk.max_single_weight") {
            config.risk_max_single_weight = parse_double(value);
        } else if (key == "risk.max_gross") {
            config.risk_max_gross = parse_double(value);
        } else if (key == "execution.min_rebalance_delta") {
            config.execution_min_rebalance_delta = parse_double(value);
        } else if (key == "execution.max_participation_rate") {
            config.execution_max_participation_rate = parse_double(value);
        } else {
            throw std::runtime_error("unknown config key: " + key);
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
