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
            case '\r':
                escaped += "\\r";
                break;
            case '\t':
                escaped += "\\t";
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

void write_instrument_json(std::ostream& output, const InstrumentId& instrument) {
    output << "{\"symbol\":\"" << escape_json(instrument.symbol)
           << "\",\"exchange\":\"" << escape_json(instrument.exchange)
           << "\",\"key\":\"" << escape_json(instrument_key(instrument)) << "\"}";
}

void write_position_json(std::ostream& output, const Position& position) {
    output << "{\"instrument\":";
    write_instrument_json(output, position.instrument);
    output << ",\"quantity\":" << position.quantity
           << ",\"avg_cost\":" << position.avg_cost
           << ",\"market_price\":" << position.market_price
           << ",\"market_value\":" << position.market_value
           << ",\"weight\":" << position.weight << "}";
}

void write_portfolio_json(std::ostream& output, const PortfolioSnapshot& portfolio) {
    output << "{\"cash\":" << portfolio.cash
           << ",\"equity\":" << portfolio.equity
           << ",\"cash_weight\":" << portfolio.cash_weight
           << ",\"realized_pnl\":" << portfolio.realized_pnl
           << ",\"unrealized_pnl\":" << portfolio.unrealized_pnl
           << ",\"gross_exposure\":" << gross_exposure(portfolio)
           << ",\"positions\":[";
    for (std::size_t index = 0; index < portfolio.positions.size(); ++index) {
        if (index > 0) {
            output << ",";
        }
        write_position_json(output, portfolio.positions[index]);
    }
    output << "]}";
}

void write_target_portfolio_json(std::ostream& output, const TargetPortfolio& portfolio) {
    output << "{\"optimizer_version\":\"" << escape_json(portfolio.optimizer_version)
           << "\",\"expected_turnover\":" << portfolio.expected_turnover
           << ",\"expected_cost_bps\":" << portfolio.expected_cost_bps
           << ",\"gross_exposure\":" << gross_exposure(portfolio)
           << ",\"positions\":[";
    for (std::size_t index = 0; index < portfolio.positions.size(); ++index) {
        if (index > 0) {
            output << ",";
        }
        const auto& position = portfolio.positions[index];
        output << "{\"instrument\":";
        write_instrument_json(output, position.instrument);
        output << ",\"target_weight\":" << position.target_weight << "}";
    }
    output << "]}";
}

void write_signal_json(std::ostream& output, const Signal& signal) {
    output << "{\"strategy_id\":\"" << escape_json(signal.strategy_id)
           << "\",\"instrument\":";
    write_instrument_json(output, signal.instrument);
    output << ",\"score\":" << signal.score
           << ",\"confidence\":" << signal.confidence << "}";
}

void write_order_intent_json(std::ostream& output, const OrderIntent& intent) {
    output << "{\"instrument\":";
    write_instrument_json(output, intent.instrument);
    output << ",\"side\":\"" << to_string(intent.side)
           << "\",\"type\":\"" << (intent.type == OrderType::Market ? "Market" : "Limit")
           << "\",\"quantity\":" << intent.quantity
           << ",\"reference_price\":" << intent.reference_price
           << ",\"parent_decision_id\":\"" << escape_json(intent.parent_decision_id)
           << "\"}";
}

void write_order_record_json(std::ostream& output,
                             const execution::OmsOrderRecord& record) {
    output << "{\"order_id\":\"" << escape_json(record.order_id)
           << "\",\"intent\":";
    write_order_intent_json(output, record.intent);
    output << ",\"status\":\"" << to_string(record.status)
           << "\",\"filled_qty\":" << record.filled_qty
           << ",\"remaining_qty\":" << record.remaining_qty
           << ",\"avg_price\":" << record.avg_price
           << ",\"commission\":" << record.commission << "}";
}

void write_execution_report_json(std::ostream& output,
                                 const ExecutionReport& report) {
    output << "{\"order_id\":\"" << escape_json(report.order_id)
           << "\",\"instrument\":";
    write_instrument_json(output, report.instrument);
    output << ",\"side\":\"" << to_string(report.side)
           << "\",\"last_fill_qty\":" << report.last_fill_qty
           << ",\"last_fill_price\":" << report.last_fill_price
           << ",\"cumulative_filled_qty\":" << report.cumulative_filled_qty
           << ",\"remaining_qty\":" << report.remaining_qty
           << ",\"avg_price\":" << report.avg_price
           << ",\"commission\":" << report.commission
           << ",\"slippage_bps\":" << report.slippage_bps
           << ",\"status\":\"" << to_string(report.status)
           << "\",\"broker_status\":\"" << escape_json(report.broker_status)
           << "\"}";
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
    output << "annualized_sharpe=" << report.annualized_sharpe << "\n";
    output << "average_turnover=" << report.average_turnover << "\n";
    output << "average_cost_bps=" << report.average_cost_bps << "\n";
    output << "average_gross_exposure=" << report.average_gross_exposure << "\n";
    output << "max_gross_exposure=" << report.max_gross_exposure << "\n";
    output << "final_equity="
           << (report.equity_curve.empty() ? 0.0 : report.equity_curve.back().equity)
           << "\n";
}

void write_backtest_report_json(const BacktestReport& report, const std::string& path) {
    ensure_parent_directory(path);
    std::ofstream output(path);
    if (!output.is_open()) {
        throw std::runtime_error("failed to open backtest report path: " + path);
    }

    output << std::fixed << std::setprecision(8);
    const double final_equity =
        report.equity_curve.empty() ? 0.0 : report.equity_curve.back().equity;

    output << "{";
    output << "\"summary\":{"
           << "\"cycles\":" << report.cycles.size()
           << ",\"event_count\":" << report.event_count
           << ",\"total_fills\":" << report.total_fills
           << ",\"total_commission\":" << report.total_commission
           << ",\"total_return\":" << report.total_return
           << ",\"max_drawdown\":" << report.max_drawdown
           << ",\"annualized_sharpe\":" << report.annualized_sharpe
           << ",\"average_turnover\":" << report.average_turnover
           << ",\"average_cost_bps\":" << report.average_cost_bps
           << ",\"average_gross_exposure\":" << report.average_gross_exposure
           << ",\"max_gross_exposure\":" << report.max_gross_exposure
           << ",\"final_equity\":" << final_equity
           << "},";

    output << "\"equity_curve\":[";
    for (std::size_t index = 0; index < report.equity_curve.size(); ++index) {
        if (index > 0) {
            output << ",";
        }
        const auto& point = report.equity_curve[index];
        output << "{\"cycle_index\":" << point.cycle_index
               << ",\"label\":\"" << escape_json(point.label)
               << "\",\"equity\":" << point.equity
               << ",\"cash\":" << point.cash
               << ",\"gross_exposure\":" << point.gross_exposure
               << ",\"realized_pnl\":" << point.realized_pnl
               << ",\"unrealized_pnl\":" << point.unrealized_pnl
               << "}";
    }
    output << "],";

    output << "\"cycles\":[";
    for (std::size_t cycle_index = 0; cycle_index < report.cycles.size(); ++cycle_index) {
        if (cycle_index > 0) {
            output << ",";
        }
        const auto& cycle = report.cycles[cycle_index];
        output << "{\"cycle_index\":" << cycle.cycle_index
               << ",\"label\":\"" << escape_json(cycle.cycle_label) << "\",";

        output << "\"features\":{";
        std::size_t feature_index = 0;
        for (const auto& [key, value] : cycle.features) {
            if (feature_index++ > 0) {
                output << ",";
            }
            output << "\"" << escape_json(key) << "\":" << value;
        }
        output << "},";

        output << "\"regime\":{"
               << "\"regime\":\"" << to_string(cycle.regime.regime)
               << "\",\"confidence\":" << cycle.regime.confidence
               << ",\"mw\":" << cycle.regime.momentum_weight
               << ",\"rw\":" << cycle.regime.mean_revert_weight
               << ",\"dw\":" << cycle.regime.defensive_weight
               << ",\"tp\":" << cycle.regime.trending_prob
               << ",\"rp\":" << cycle.regime.mean_revert_prob
               << ",\"dp\":" << cycle.regime.defensive_prob
               << ",\"model_version\":\"" << escape_json(cycle.regime.model_version)
               << "\"},";

        output << "\"signals\":[";
        for (std::size_t index = 0; index < cycle.signals.size(); ++index) {
            if (index > 0) {
                output << ",";
            }
            write_signal_json(output, cycle.signals[index]);
        }
        output << "],";

        output << "\"target_portfolio\":";
        write_target_portfolio_json(output, cycle.target_portfolio);
        output << ",\"risk_decision\":{\"action\":\""
               << to_string(cycle.risk_decision.action)
               << "\",\"reason\":\"" << escape_json(cycle.risk_decision.reason)
               << "\",\"adjusted_portfolio\":";
        write_target_portfolio_json(output, cycle.risk_decision.adjusted_portfolio);
        output << "},";

        output << "\"pre_trade_portfolio\":";
        write_portfolio_json(output, cycle.pre_trade_portfolio);
        output << ",\"post_trade_portfolio\":";
        write_portfolio_json(output, cycle.post_trade_portfolio);

        output << ",\"orders\":[";
        for (std::size_t index = 0; index < cycle.orders.size(); ++index) {
            if (index > 0) {
                output << ",";
            }
            write_order_intent_json(output, cycle.orders[index]);
        }
        output << "],\"order_records\":[";
        for (std::size_t index = 0; index < cycle.order_records.size(); ++index) {
            if (index > 0) {
                output << ",";
            }
            write_order_record_json(output, cycle.order_records[index]);
        }
        output << "],\"reports\":[";
        for (std::size_t index = 0; index < cycle.reports.size(); ++index) {
            if (index > 0) {
                output << ",";
            }
            write_execution_report_json(output, cycle.reports[index]);
        }
        output << "]}";
    }
    output << "]}";
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
