#include "qt/runtime_config.hpp"

#include <fstream>
#include <stdexcept>
#include <string_view>

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
        } else if (key == "print_cycles") {
            config.print_cycles = parse_bool(value);
        } else if (key == "print_event_stream") {
            config.print_event_stream = parse_bool(value);
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

    return config;
}

}  // namespace qt
