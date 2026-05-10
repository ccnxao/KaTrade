#include <algorithm>
#include <cctype>
#include <chrono>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <memory>
#include <sstream>
#include <string>
#include <thread>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "qt/agents.hpp"
#include "qt/event_bus.hpp"
#include "qt/execution.hpp"
#include "qt/oms.hpp"
#include "qt/portfolio.hpp"
#include "qt/risk.hpp"
#include "qt/risk/risk_budget.hpp"
#include "qt/runtime_config.hpp"
#include "qt/strategy_module.hpp"
#include "qt/trader_engine.hpp"

namespace {

constexpr int DEFAULT_POLL_MS = 1000;
constexpr int DEFAULT_MAX_TICKS = 1000;
constexpr int DEFAULT_BATCH_SIZE = 1;

// ---- Minimal JSON helpers (avoid external deps) ----
std::string json_str(const std::string& json, const std::string& key) {
    auto pos = json.find("\"" + key + "\"");
    if (pos == std::string::npos) return "";
    pos = json.find(":", pos + key.size() + 2);
    if (pos == std::string::npos) return "";
    pos = json.find_first_not_of(": \t\n\r", pos);
    if (pos == std::string::npos) return "";
    if (json[pos] == '"') {
        size_t end = json.find('"', pos + 1);
        if (end == std::string::npos) return "";
        return json.substr(pos + 1, end - pos - 1);
    }
    // number
    size_t end = pos;
    while (end < json.size() && (std::isdigit(json[end]) || json[end]=='.' || json[end]=='-' || json[end]=='e' || json[end]=='E' || json[end]=='+'))
        ++end;
    return json.substr(pos, end - pos);
}

double json_num(const std::string& json, const std::string& key) {
    auto s = json_str(json, key);
    if (s.empty()) return 0.0;
    return std::stod(s);
}

std::int64_t unix_ms() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
}

std::string json_escape(const std::string& value) {
    std::string out;
    out.reserve(value.size() + 8);
    for (const char ch : value) {
        if (ch == '"') out += "\\\"";
        else if (ch == '\\') out += "\\\\";
        else if (ch == '\n') out += "\\n";
        else if (ch == '\r') out += "\\r";
        else if (ch == '\t') out += "\\t";
        else out += ch;
    }
    return out;
}

struct QualityCheck {
    std::string name;
    bool ok{true};
    std::string severity{"ok"};
    std::string message;
};

struct QualityStats {
    std::string source{"sample"};
    bool require_trade_id{true};
    std::int64_t max_tick_age_ms{30000};
    std::int64_t idle_block_ms{30000};
    std::int64_t total_ticks{};
    std::int64_t valid_ticks{};
    std::int64_t invalid_ticks{};
    std::int64_t missing_trade_ids{};
    std::int64_t duplicate_trade_ids{};
    std::int64_t out_of_order_ticks{};
    std::int64_t first_exchange_ts_ms{};
    std::int64_t last_exchange_ts_ms{};
    std::int64_t previous_exchange_ts_ms{};
    std::unordered_set<std::string> seen_trade_ids;

    void observe_trade_row(const std::string& row_json) {
        ++total_ticks;
        const auto ts = static_cast<std::int64_t>(json_num(row_json, "t"));
        const double price = json_num(row_json, "price");
        const double size = json_num(row_json, "size");
        const std::string trade_id = json_str(row_json, "trade_id");

        bool valid = true;
        if (ts <= 0 || price <= 0.0 || size <= 0.0) {
            ++invalid_ticks;
            valid = false;
        }
        if (require_trade_id && trade_id.empty()) {
            ++missing_trade_ids;
            valid = false;
        }
        if (!trade_id.empty() && !seen_trade_ids.insert(trade_id).second) {
            ++duplicate_trade_ids;
            valid = false;
        }
        if (previous_exchange_ts_ms > 0 && ts > 0 && ts < previous_exchange_ts_ms) {
            ++out_of_order_ticks;
            valid = false;
        }
        if (ts > 0) {
            previous_exchange_ts_ms = ts;
            if (first_exchange_ts_ms == 0 || ts < first_exchange_ts_ms) {
                first_exchange_ts_ms = ts;
            }
            if (ts > last_exchange_ts_ms) {
                last_exchange_ts_ms = ts;
            }
        }
        if (valid) {
            ++valid_ticks;
        }
    }

    void observe_bar(const qt::Bar& bar) {
        ++total_ticks;
        bool valid = true;
        if (bar.timestamp < 0 || bar.close <= 0.0 || bar.volume <= 0.0) {
            ++invalid_ticks;
            valid = false;
        }
        if (previous_exchange_ts_ms > 0 && bar.timestamp > 0 &&
            bar.timestamp < previous_exchange_ts_ms) {
            ++out_of_order_ticks;
            valid = false;
        }
        previous_exchange_ts_ms = bar.timestamp;
        if (first_exchange_ts_ms == 0 || bar.timestamp < first_exchange_ts_ms) {
            first_exchange_ts_ms = bar.timestamp;
        }
        if (bar.timestamp > last_exchange_ts_ms) {
            last_exchange_ts_ms = bar.timestamp;
        }
        if (valid) {
            ++valid_ticks;
        }
    }
};

// Parse a trade row into a Bar. Trade rows look like:
// {"inst_id":"BTC-USDT-SWAP","trade_id":"123","t":1778214561871,"price":79642.4,"size":68.25,"side":"sell"}
qt::Bar parse_trade_bar(const std::string& row_json, const std::string& exchange) {
    qt::Bar bar;
    bar.timestamp = static_cast<std::int64_t>(json_num(row_json, "t"));
    std::string inst = json_str(row_json, "inst_id");
    bar.instrument.symbol = inst.empty() ? "UNKNOWN" : inst;
    bar.instrument.exchange = exchange.empty() ? "OKX" : exchange;
    double px = json_num(row_json, "price");
    double sz = json_num(row_json, "size");
    bar.open = px;
    bar.high = px;
    bar.low = px;
    bar.close = px;
    bar.volume = sz;
    return bar;
}

// Check if a JSON line is a trade message
bool is_trade_msg(const std::string& line) {
    return line.find("\"trades\"") != std::string::npos;
}
bool is_ticker_msg(const std::string& line) {
    return line.find("\"tickers\"") != std::string::npos;
}

// ---- Config-driven detector construction ----
std::unique_ptr<qt::agent::MetaAgent> build_meta_agent(
    const qt::RuntimeConfig& config) {

    std::unique_ptr<qt::agent::IRegimeAgent> detector;

    if (config.regime_detector == "online_em") {
        detector = std::make_unique<qt::agent::OnlineEMRegimeAgent>(
            config.regime_hmm_states, config.regime_oem_dim);
        std::cerr << "[realtime_engine] regime detector: OnlineEM (states="
                  << config.regime_hmm_states << ", dim="
                  << config.regime_oem_dim << ")\n";
    } else if (config.regime_detector == "hmm") {
        detector = std::make_unique<qt::agent::HMMRegimeAgent>(
            config.regime_hmm_states);
        std::cerr << "[realtime_engine] regime detector: HMM (states="
                  << config.regime_hmm_states << ")\n";
    } else {
        detector = std::make_unique<qt::agent::RuleBasedRegimeAgent>(
            config.regime_rule_crisis_vol, config.regime_rule_crisis_corr,
            config.regime_rule_trending_adx, config.regime_rule_trending_ret,
            config.regime_rule_trending_vol_cap,
            config.regime_rule_mean_revert_adx, config.regime_rule_mean_revert_vol_cap);
        std::cerr << "[realtime_engine] regime detector: RuleBased\n";
    }

    return std::make_unique<qt::agent::MetaAgent>(std::move(detector));
}

// ---- JSON output ----
std::string regime_to_json(const qt::RegimeState& rs) {
    char buf[512];
    snprintf(buf, sizeof(buf),
        R"({"regime":"%s","confidence":%.4f,"mw":%.4f,"rw":%.4f,"dw":%.4f,"tp":%.4f,"rp":%.4f,"dp":%.4f,"model_version":"%s"})",
        to_string(rs.regime).c_str(),
        rs.confidence,
        rs.momentum_weight, rs.mean_revert_weight, rs.defensive_weight,
        rs.trending_prob, rs.mean_revert_prob, rs.defensive_prob,
        rs.model_version.c_str());
    return buf;
}

void write_status(const std::string& path,
                  const qt::CycleResult& result) {
    std::ofstream of(path);
    if (!of) return;

    of << "{\n";
    of << "  \"cycle_index\":" << result.cycle_index << ",\n";
    of << "  \"cycle_label\":\"" << result.cycle_label << "\",\n";
    of << "  \"regime\":" << regime_to_json(result.regime) << ",\n";
    of << "  \"regime_by_instrument\":{\n";
    bool first = true;
    for (const auto& [inst, rs] : result.regime_by_instrument) {
        if (!first) of << ",\n";
        of << "    \"" << inst << "\":" << regime_to_json(rs);
        first = false;
    }
    of << "\n  },\n";
    of << "  \"signals\":" << result.signals.size() << ",\n";
    of << "  \"orders\":" << result.order_records.size() << ",\n";
    of << "  \"fills\":" << result.reports.size() << ",\n";
    of << "  \"equity\":" << result.post_trade_portfolio.equity << ",\n";
    of << "  \"cash\":" << result.post_trade_portfolio.cash << "\n";
    of << "}\n";
}

std::vector<QualityCheck> quality_checks(const QualityStats& stats,
                                         std::int64_t generated_ms) {
    const std::int64_t last_age_ms =
        stats.last_exchange_ts_ms > 0
            ? std::max<std::int64_t>(0, generated_ms - stats.last_exchange_ts_ms)
            : stats.idle_block_ms + 1;
    const bool sample_source = stats.source == "sample";
    return {
        {"tick_batch", stats.total_ticks > 0, "halt",
         stats.total_ticks > 0 ? "tick batch is not empty" : "tick batch is empty"},
        {"positive_fields", stats.invalid_ticks == 0, "halt",
         stats.invalid_ticks == 0 ? "all ticks have positive price/size"
                                  : "invalid timestamp, price or size found"},
        {"trade_id", !stats.require_trade_id || stats.missing_trade_ids == 0, "halt",
         !stats.require_trade_id ? "trade id check disabled"
         : stats.missing_trade_ids == 0 ? "trade ids are present"
                                        : "missing trade ids found"},
        {"duplicates", stats.duplicate_trade_ids == 0, "warn",
         stats.duplicate_trade_ids == 0 ? "no duplicate trade ids"
                                        : "duplicate trade ids found"},
        {"timestamp_order", stats.out_of_order_ticks == 0, "warn",
         stats.out_of_order_ticks == 0 ? "timestamps are monotonic"
                                       : "out-of-order ticks found"},
        {"freshness", sample_source || last_age_ms <= stats.max_tick_age_ms, "halt",
         sample_source ? "sample source does not use freshness gate"
         : last_age_ms <= stats.max_tick_age_ms ? "ticks are fresh"
                                                : "latest tick is stale"},
        {"accepted_ticks", stats.valid_ticks > 0, "halt",
         stats.valid_ticks > 0 ? "accepted ticks are available"
                               : "no accepted ticks available"},
    };
}

void write_checks_json(std::ostream& of, const std::vector<QualityCheck>& checks) {
    of << "[";
    for (std::size_t i = 0; i < checks.size(); ++i) {
        if (i) of << ",";
        const auto& check = checks[i];
        of << "{\"name\":\"" << json_escape(check.name)
           << "\",\"ok\":" << (check.ok ? "true" : "false")
           << ",\"severity\":\"" << (check.ok ? "ok" : json_escape(check.severity))
           << "\",\"message\":\"" << json_escape(check.message) << "\"}";
    }
    of << "]";
}

void write_risk_budget_json(std::ostream& of,
                            const qt::risk::RiskBudgetDecision& budget) {
    of << "{";
    of << "\"action\":\"" << qt::to_string(budget.action) << "\""
       << ",\"reason\":\"" << json_escape(budget.reason) << "\""
       << ",\"scale\":" << budget.scale
       << ",\"checks\":[";
    for (std::size_t i = 0; i < budget.checks.size(); ++i) {
        if (i) of << ",";
        const auto& check = budget.checks[i];
        of << "{\"name\":\"" << json_escape(check.name)
           << "\",\"ok\":" << (check.passed ? "true" : "false")
           << ",\"severity\":\"" << (check.passed ? "ok" : "halt")
           << "\",\"message\":\"" << json_escape(check.detail) << "\"}";
    }
    of << "]}";
}

void write_execution_runtime_json(std::ostream& of,
                                  const qt::CycleResult& result) {
    std::size_t accepted = 0;
    std::size_t blocked = 0;
    for (const auto& record : result.order_records) {
        if (record.status == qt::OrderStatus::Rejected) ++blocked;
        else ++accepted;
    }
    of << "{";
    of << "\"decisions\":" << result.order_records.size()
       << ",\"accepted\":" << accepted
       << ",\"blocked\":" << blocked
       << ",\"details\":[";
    for (std::size_t i = 0; i < result.order_records.size(); ++i) {
        if (i) of << ",";
        const auto& record = result.order_records[i];
        const bool approved = record.status != qt::OrderStatus::Rejected;
        of << "{\"trace_id\":\"" << json_escape(result.cycle_label + ":" + record.order_id)
           << "\",\"approved\":" << (approved ? "true" : "false")
           << ",\"status\":\"" << (approved ? "accepted" : "blocked")
           << "\",\"category\":\"cpp_realtime_engine\""
           << ",\"reason\":\""
           << (approved ? "C++ execution_runtime accepted order."
                        : "C++ execution_runtime blocked order.")
           << "\",\"live_order_count\":0,\"failed_checks\":[]}";
    }
    of << "]}";
}

void write_quality_report(const std::string& path,
                          const qt::CycleResult& result,
                          const QualityStats& stats) {
    std::ofstream of(path);
    if (!of) return;

    const auto generated_ms = unix_ms();
    const auto checks = quality_checks(stats, generated_ms);
    const bool blocked = std::any_of(checks.begin(), checks.end(), [](const auto& check) {
        return !check.ok && check.severity == "halt";
    });
    const auto failed = std::find_if(checks.begin(), checks.end(), [](const auto& check) {
        return !check.ok;
    });
    const std::int64_t last_age_ms =
        stats.last_exchange_ts_ms > 0
            ? std::max<std::int64_t>(0, generated_ms - stats.last_exchange_ts_ms)
            : stats.idle_block_ms + 1;
    const double coverage =
        stats.total_ticks > 0
            ? static_cast<double>(stats.valid_ticks) / static_cast<double>(stats.total_ticks)
            : 0.0;

    of << "{\n";
    of << "  \"ok\":" << (blocked ? "false" : "true") << ",\n";
    of << "  \"source\":\"" << json_escape(stats.source) << "\",\n";
    of << "  \"generated_at\":\"" << generated_ms << "\",\n";
    of << "  \"generated_at_ms\":" << generated_ms << ",\n";
    of << "  \"last_tick_age_ms\":" << last_age_ms << ",\n";
    of << "  \"last_label\":\"" << json_escape(result.cycle_label) << "\",\n";
    of << "  \"decision\":\"" << (blocked ? "block" : "allow") << "\",\n";
    of << "  \"reason\":\""
       << (failed == checks.end() ? "strategy cycle completed" : json_escape(failed->message))
       << "\",\n";
    of << "  \"regime\":" << regime_to_json(result.regime) << ",\n";
    of << "  \"regime_by_instrument\":{\n";
    bool first = true;
    for (const auto& [inst, rs] : result.regime_by_instrument) {
        if (!first) of << ",\n";
        of << "    \"" << json_escape(inst) << "\":" << regime_to_json(rs);
        first = false;
    }
    of << "\n  },\n";
    of << "  \"timeline\":{"
       << "\"decision\":\"" << (blocked ? "block" : "allow") << "\""
       << ",\"source_hash\":\"" << std::hash<std::string>{}(stats.source) << "\""
       << ",\"total_ticks\":" << stats.total_ticks
       << ",\"valid_ticks\":" << stats.valid_ticks
       << ",\"coverage_ratio\":" << coverage
       << ",\"first_exchange_ts_ms\":" << stats.first_exchange_ts_ms
       << ",\"last_exchange_ts_ms\":" << stats.last_exchange_ts_ms
       << ",\"gap_count\":0"
       << ",\"out_of_order_count\":" << stats.out_of_order_ticks
       << ",\"stale_receive_count\":0"
       << ",\"checks\":";
    write_checks_json(of, checks);
    of << ",\"instruments\":[]},\n";
    of << "  \"risk_budget\":";
    write_risk_budget_json(of, result.risk_budget_decision);
    of << ",\n  \"execution_runtime\":";
    write_execution_runtime_json(of, result);
    of << ",\n  \"summary\":{"
       << "\"total_ticks\":" << stats.total_ticks
       << ",\"accepted_ticks\":" << stats.valid_ticks
       << ",\"duplicate_ticks\":" << stats.duplicate_trade_ids
       << ",\"out_of_order_ticks\":" << stats.out_of_order_ticks
       << ",\"stale_ticks\":0"
       << ",\"invalid_ticks\":" << stats.invalid_ticks
       << "},\n";
    of << "  \"last_batch\":{"
       << "\"total_ticks\":" << stats.total_ticks
       << ",\"accepted_ticks\":" << stats.valid_ticks
       << ",\"duplicate_ticks\":" << stats.duplicate_trade_ids
       << ",\"out_of_order_ticks\":" << stats.out_of_order_ticks
       << ",\"stale_ticks\":0"
       << ",\"invalid_ticks\":" << stats.invalid_ticks
       << "},\n";
    of << "  \"checks\":";
    write_checks_json(of, checks);
    of << "\n}\n";
}

}  // namespace

int main(int argc, char** argv) {
    std::ios::sync_with_stdio(false);

    // ---- Parse args ----
    std::string market_stream_path;
    std::string status_path = "logs/realtime_engine/status.json";
    std::string quality_report_path;
    std::string config_path = "config/default.cfg";  // R42
    std::string event_log_path;
    bool watch = false;
    bool watch_from_end = true;
    int poll_ms = DEFAULT_POLL_MS;
    int max_ticks = DEFAULT_MAX_TICKS;
    int batch_size = DEFAULT_BATCH_SIZE;
    int max_tick_age_ms = 30000;
    int idle_block_ms = 30000;
    bool require_trade_id = true;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--market-stream-journal" && i + 1 < argc) {
            market_stream_path = argv[++i];
        } else if (arg == "--status" && i + 1 < argc) {
            status_path = argv[++i];
        } else if (arg == "--quality-report" && i + 1 < argc) {
            quality_report_path = argv[++i];
        } else if (arg == "--event-log" && i + 1 < argc) {
            event_log_path = argv[++i];
        } else if (arg == "--config" && i + 1 < argc) {
            config_path = argv[++i];  // R42
        } else if (arg == "--watch") {
            watch = true;
        } else if (arg == "--watch-from-end" && i + 1 < argc) {
            std::string value = argv[++i];
            watch_from_end = value != "false" && value != "0";
        } else if (arg == "--poll-ms" && i + 1 < argc) {
            poll_ms = std::stoi(argv[++i]);
        } else if (arg == "--max-ticks" && i + 1 < argc) {
            max_ticks = std::stoi(argv[++i]);
        } else if (arg == "--batch-size" && i + 1 < argc) {
            batch_size = std::stoi(argv[++i]);
        } else if (arg == "--max-tick-age-ms" && i + 1 < argc) {
            max_tick_age_ms = std::stoi(argv[++i]);
        } else if (arg == "--idle-block-ms" && i + 1 < argc) {
            idle_block_ms = std::stoi(argv[++i]);
        } else if (arg == "--require-trade-id" && i + 1 < argc) {
            std::string value = argv[++i];
            require_trade_id = value != "false" && value != "0";
        }
    }
    max_ticks = std::max(1, max_ticks);
    batch_size = std::max(1, batch_size);
    max_tick_age_ms = std::max(1000, max_tick_age_ms);
    idle_block_ms = std::max(1000, idle_block_ms);

    // ---- Load config ----
    qt::RuntimeConfig config;
    try {
        config = qt::load_runtime_config(config_path);  // R42
    } catch (const std::exception& e) {
        std::cerr << "[realtime_engine] config warning: " << e.what() << "\n";
    }

    // ---- Build engine ----
    auto meta = build_meta_agent(config);

    // GAP-024: 按 config 中的 strategy_ids 动态注册所有策略
    auto signals = qt::make_signal_agents(config);

    // GAP-032: 基于配置创建组合优化器
    std::unique_ptr<qt::IPortfolioOptimizer> optimizer;
    if (config.optimizer_type == "markowitz") {
        optimizer = std::make_unique<qt::MarkowitzPortfolioOptimizer>(
            config.optimizer_max_single_weight, config.optimizer_max_gross,
            config.optimizer_risk_aversion, config.optimizer_target_vol);
        std::cerr << "[realtime_engine] optimizer: Markowitz (risk_aversion="
                  << config.optimizer_risk_aversion << ", target_vol="
                  << config.optimizer_target_vol << ")\n";
    } else if (config.optimizer_type == "risk_parity") {
        optimizer = std::make_unique<qt::RiskParityOptimizer>(
            config.optimizer_max_single_weight, config.optimizer_max_gross,
            config.optimizer_target_vol);
        std::cerr << "[realtime_engine] optimizer: Risk Parity (target_vol="
                  << config.optimizer_target_vol << ")\n";
    } else {
        optimizer = std::make_unique<qt::SimplePortfolioOptimizer>(
            config.optimizer_max_single_weight, config.optimizer_max_gross);
        std::cerr << "[realtime_engine] optimizer: Simple\n";
    }

    auto risk = std::make_unique<qt::RiskAgent>(
        config.risk_max_single_weight, config.risk_max_gross, config.risk_kill_switch);
    risk->set_thresholds(config.risk_drawdown_limit, config.risk_vol_threshold,
                         config.risk_vol_reduction, config.risk_stress_tolerance);
    auto execution = std::make_unique<qt::execution::NaiveExecutionAlgo>(
        config.execution_min_rebalance_delta);
    auto broker = std::make_unique<qt::execution::SimulatedBrokerGateway>(
        config.execution_max_participation_rate,
        config.execution_slippage_bps,
        config.execution_commission_bps,
        config.execution_partial_fill_prob);
    auto oms = std::make_unique<qt::execution::OrderManagementSystem>(std::move(broker));

    qt::EventBus bus;

    double equity = config.initial_cash > 0.0
                        ? config.initial_cash
                        : 100000.0;

    qt::TraderEngine engine(std::move(meta), std::move(signals),
                             std::move(optimizer), std::move(risk),
                             std::move(execution), std::move(oms),
                             equity, &bus);

    // 可配置执行参数 (GAP-017/018)
    engine.set_execution_params(
        config.execution_slippage_bps, config.execution_commission_bps,
        config.execution_partial_fill_prob, config.execution_default_ord_type);

    // 设置风险预算审查 (GAP-006)
    qt::risk::RiskBudgetAllocator budget_allocator;
    engine.set_risk_budget_reviewer(
        [&budget_allocator](const qt::CycleResult& cycle) -> qt::risk::RiskBudgetDecision {
            qt::risk::RiskBudgetInput input;
            input.cycle_result = &cycle;
            return budget_allocator.allocate(input);
        });

    // ---- Run ----
    if (watch && !market_stream_path.empty()) {
        std::cerr << "[realtime_engine] watch mode: " << market_stream_path << "\n";

        std::ifstream stream(market_stream_path);
        if (watch_from_end) {
            stream.seekg(0, std::ios::end);
        }
        std::streampos read_pos = stream.tellg();
        if (read_pos == std::streampos(-1)) {
            // Tail 模式下如果启动瞬间文件刚好在 EOF/异常状态，保存一个明确的
            // 读位置。后续循环会从该位置继续读新增 journal 行。
            stream.clear();
            stream.seekg(0, std::ios::end);
            read_pos = stream.tellg();
        }

        std::string line;
        std::vector<qt::Bar> batch;
        std::unordered_map<std::string, double> last_prices; // inst_key -> price
        int cycles_run = 0;
        QualityStats quality_stats;
        quality_stats.source = market_stream_path;
        quality_stats.require_trade_id = require_trade_id;
        quality_stats.max_tick_age_ms = max_tick_age_ms;
        quality_stats.idle_block_ms = idle_block_ms;

        while (true) {
            // Read new lines from the growing journal
            stream.clear();
            stream.seekg(read_pos);
            while (std::getline(stream, line)) {
                auto next_pos = stream.tellg();
                if (next_pos == std::streampos(-1)) {
                    // getline 读到文件尾附近时 tellg 可能短暂失败。清掉 EOF 后
                    // 定位到当前文件尾，避免下一轮永远卡在失效位置。
                    stream.clear();
                    stream.seekg(0, std::ios::end);
                    next_pos = stream.tellg();
                }
                read_pos = next_pos;
                if (line.empty() || line[0] != '{') continue;

                if (is_trade_msg(line)) {
                    // Parse rows array: look for "rows":[...]
                    auto rows_pos = line.find("\"rows\"");
                    if (rows_pos == std::string::npos) continue;
                    auto arr_start = line.find('[', rows_pos);
                    if (arr_start == std::string::npos) continue;

                    // Extract each row object between { and }
                    size_t pos = arr_start + 1;
                    while (pos < line.size()) {
                        pos = line.find('{', pos);
                        if (pos == std::string::npos) break;
                        size_t end = line.find('}', pos);
                        if (end == std::string::npos) break;
                        std::string row = line.substr(pos, end - pos + 1);
                        quality_stats.observe_trade_row(row);
                        auto bar = parse_trade_bar(row, "OKX");
                        if (bar.timestamp > 0 && bar.close > 0) {
                            batch.push_back(bar);
                            last_prices[instrument_key(bar.instrument)] = bar.close;
                        }
                        pos = end + 1;
                    }
                } else if (is_ticker_msg(line)) {
                    // Use ticker data to supplement last prices
                    auto rows_pos = line.find("\"rows\"");
                    if (rows_pos == std::string::npos) continue;
                    auto arr_start = line.find('[', rows_pos);
                    if (arr_start == std::string::npos) continue;
                    // Extract inst_id from top level for ticker
                    std::string inst_id = json_str(line, "inst_id");
                    if (inst_id.empty()) {
                        // fallback: look inside rows[0]
                        auto obj_start = line.find('{', arr_start + 1);
                        if (obj_start != std::string::npos) {
                            auto obj_end = line.find('}', obj_start);
                            if (obj_end != std::string::npos) {
                                inst_id = json_str(line.substr(obj_start, obj_end-obj_start+1), "inst_id");
                            }
                        }
                    }
                    if (!inst_id.empty()) {
                        double last = json_num(line, "last");
                        if (last > 0) last_prices[inst_id + ".OKX"] = last;
                    }
                }
            }
            if (!stream.eof() && !stream.good()) {
                // Journal 被轮转、截断或底层读取失败时，重开文件并从尾部继续。
                stream.close();
                stream.open(market_stream_path);
                stream.seekg(0, std::ios::end);
                read_pos = stream.tellg();
            }
            stream.clear(); // clear EOF flag so we can read new data appended later

            // Run a cycle when we have enough bars
            if (static_cast<int>(batch.size()) >= batch_size) {
                auto result = engine.run_cycle(batch, "tick_" + std::to_string(++cycles_run));
                write_status(status_path, result);
                if (!quality_report_path.empty()) {
                    write_quality_report(quality_report_path, result, quality_stats);
                }
                batch.clear();
            }

            std::this_thread::sleep_for(std::chrono::milliseconds(poll_ms));
        }
    } else {
        // Single cycle with sample data
        std::vector<qt::Bar> bars = {
            {0, {"BTC-USDT-SWAP", "OKX"}, 95000.0, 95500.0, 94500.0, 95200.0, 1500.0},
            {0, {"ETH-USDT-SWAP", "OKX"}, 3400.0, 3450.0, 3380.0, 3420.0, 8000.0},
        };
        QualityStats quality_stats;
        quality_stats.source = "sample";
        quality_stats.require_trade_id = false;
        quality_stats.max_tick_age_ms = max_tick_age_ms;
        quality_stats.idle_block_ms = idle_block_ms;
        for (const auto& bar : bars) {
            quality_stats.observe_bar(bar);
        }
        auto result = engine.run_cycle(bars, "sample");
        write_status(status_path, result);
        if (!quality_report_path.empty()) {
            write_quality_report(quality_report_path, result, quality_stats);
        }
        std::cout << regime_to_json(result.regime) << "\n";
    }

    return 0;
}
