#include "qt/report_io.hpp"

#include <iomanip>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <type_traits>

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

void ensure_parent_directory(const std::string& path) {
    const auto parent = std::filesystem::path(path).parent_path();
    if (!parent.empty()) {
        std::filesystem::create_directories(parent);
    }
}

std::string escape_json(const std::string& value) {
    std::string escaped;
    escaped.reserve(value.size() + 8);
    for (const char ch : value) {
        switch (ch) {
            case '\\':
                escaped += "\\\\";
                break;
            case '"':
                escaped += "\\\"";
                break;
            case '\n':
                escaped += "\\n";
                break;
            default:
                escaped += ch;
                break;
        }
    }
    return escaped;
}

double parse_double(const std::string& value) {
    try {
        return std::stod(value);
    } catch (const std::exception&) {
        throw std::runtime_error("invalid numeric value: " + value);
    }
}

std::size_t parse_size(const std::string& value) {
    try {
        return static_cast<std::size_t>(std::stoull(value));
    } catch (const std::exception&) {
        throw std::runtime_error("invalid size value: " + value);
    }
}

std::string event_type_name(const Event& event) {
    return std::visit(
        [](const auto& payload) -> std::string {
            using T = std::decay_t<decltype(payload)>;
            if constexpr (std::is_same_v<T, CycleStartedEvent>) {
                return "cycle_started";
            } else if constexpr (std::is_same_v<T, RegimeDetectedEvent>) {
                return "regime_detected";
            } else if constexpr (std::is_same_v<T, RiskReviewedEvent>) {
                return "risk_reviewed";
            } else if constexpr (std::is_same_v<T, OrderSubmittedEvent>) {
                return "order_submitted";
            } else if constexpr (std::is_same_v<T, OrderFilledEvent>) {
                return "order_filled";
            } else if constexpr (std::is_same_v<T, CycleCompletedEvent>) {
                return "cycle_completed";
            }
            return "unknown";
        },
        event.payload);
}

}  // namespace

void write_event_log_jsonl(const EventBus& event_bus, const std::string& path) {
    ensure_parent_directory(path);
    std::ofstream output(path);
    if (!output.is_open()) {
        throw std::runtime_error("failed to open event log path: " + path);
    }

    for (const auto& event : event_bus.history()) {
        output << "{\"sequence\":" << event.sequence
               << ",\"type\":\"" << event_type_name(event) << "\""
               << ",\"message\":\"" << escape_json(describe_event(event)) << "\"";

        std::visit(
            [&](const auto& payload) {
                using T = std::decay_t<decltype(payload)>;
                output << ",\"cycle_index\":" << payload.cycle_index;

                if constexpr (std::is_same_v<T, CycleStartedEvent>) {
                    output << ",\"label\":\"" << escape_json(payload.label) << "\""
                           << ",\"instrument_count\":" << payload.instrument_count;
                } else if constexpr (std::is_same_v<T, RegimeDetectedEvent>) {
                    output << ",\"regime\":\"" << to_string(payload.regime.regime)
                           << "\""
                           << ",\"confidence\":" << payload.regime.confidence;
                } else if constexpr (std::is_same_v<T, RiskReviewedEvent>) {
                    output << ",\"risk_action\":\""
                           << to_string(payload.decision.action) << "\""
                           << ",\"reason\":\""
                           << escape_json(payload.decision.reason) << "\"";
                } else if constexpr (std::is_same_v<T, OrderSubmittedEvent>) {
                    output << ",\"order_id\":\""
                           << escape_json(payload.record.order_id) << "\""
                           << ",\"instrument\":\""
                           << instrument_key(payload.record.intent.instrument) << "\"";
                } else if constexpr (std::is_same_v<T, OrderFilledEvent>) {
                    output << ",\"order_id\":\""
                           << escape_json(payload.report.order_id) << "\""
                           << ",\"fill_qty\":" << payload.report.last_fill_qty
                           << ",\"status\":\""
                           << to_string(payload.report.status) << "\"";
                } else if constexpr (std::is_same_v<T, CycleCompletedEvent>) {
                    output << ",\"label\":\"" << escape_json(payload.label) << "\""
                           << ",\"submitted_orders\":" << payload.submitted_orders
                           << ",\"fill_count\":" << payload.fill_count;
                }
            },
            event.payload);

        output << "}\n";
    }
}

void write_report_summary(const BacktestReport& report, const std::string& path) {
    ensure_parent_directory(path);
    std::ofstream output(path);
    if (!output.is_open()) {
        throw std::runtime_error("failed to open report summary path: " + path);
    }

    output << std::fixed << std::setprecision(8);
    output << "cycles=" << report.cycles.size() << "\n";
    output << "event_count=" << report.event_count << "\n";
    output << "total_fills=" << report.total_fills << "\n";
    output << "total_commission=" << report.total_commission << "\n";
    output << "total_return=" << report.total_return << "\n";
    output << "max_drawdown=" << report.max_drawdown << "\n";
    output << "final_equity="
           << (report.equity_curve.empty() ? 0.0 : report.equity_curve.back().equity)
           << "\n";
}

GoldenMetrics load_golden_metrics(const std::string& path) {
    std::ifstream input(path);
    if (!input.is_open()) {
        throw std::runtime_error("failed to open golden metrics file: " + path);
    }

    GoldenMetrics metrics;
    std::string line;

    while (std::getline(input, line)) {
        line = trim(line);
        if (line.empty() || line.starts_with('#')) {
            continue;
        }

        const auto delimiter = line.find('=');
        if (delimiter == std::string::npos) {
            throw std::runtime_error("invalid golden metrics line: " + line);
        }

        const std::string key = trim(line.substr(0, delimiter));
        const std::string value = trim(line.substr(delimiter + 1));

        if (key == "cycles") {
            metrics.cycles = parse_size(value);
        } else if (key == "event_count") {
            metrics.event_count = parse_size(value);
        } else if (key == "total_fills") {
            metrics.total_fills = parse_size(value);
        } else if (key == "total_commission") {
            metrics.total_commission = parse_double(value);
        } else if (key == "total_return") {
            metrics.total_return = parse_double(value);
        } else if (key == "max_drawdown") {
            metrics.max_drawdown = parse_double(value);
        } else if (key == "final_equity") {
            metrics.final_equity = parse_double(value);
        } else if (key == "double_tolerance") {
            metrics.double_tolerance = parse_double(value);
        } else {
            throw std::runtime_error("unknown golden metrics key: " + key);
        }
    }

    return metrics;
}

bool matches_golden_metrics(const BacktestReport& report,
                            const GoldenMetrics& metrics,
                            std::string* failure_reason) {
    const auto fail = [&](const std::string& reason) {
        if (failure_reason != nullptr) {
            *failure_reason = reason;
        }
        return false;
    };

    if (report.cycles.size() != metrics.cycles) {
        return fail("cycle count mismatch");
    }
    if (report.event_count != metrics.event_count) {
        return fail("event count mismatch");
    }
    if (report.total_fills != metrics.total_fills) {
        return fail("fill count mismatch");
    }

    const auto near = [&](double lhs, double rhs) {
        return std::abs(lhs - rhs) <= metrics.double_tolerance;
    };

    if (!near(report.total_commission, metrics.total_commission)) {
        return fail("total commission mismatch");
    }
    if (!near(report.total_return, metrics.total_return)) {
        return fail("total return mismatch");
    }
    if (!near(report.max_drawdown, metrics.max_drawdown)) {
        return fail("max drawdown mismatch");
    }

    const double final_equity =
        report.equity_curve.empty() ? 0.0 : report.equity_curve.back().equity;
    if (!near(final_equity, metrics.final_equity)) {
        return fail("final equity mismatch");
    }

    return true;
}

}  // namespace qt
