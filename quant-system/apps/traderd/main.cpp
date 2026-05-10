#include <algorithm>
#include <cstdlib>
#include <chrono>
#include <cstdint>
#include <ctime>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <set>
#include <sstream>
#include <string>
#include <string_view>
#include <vector>

#include "qt/agents.hpp"
#include "qt/event_bus.hpp"
#include "qt/execution.hpp"
#include "qt/oms.hpp"
#include "qt/portfolio.hpp"
#include "qt/replay_data.hpp"
#include "qt/risk.hpp"
#include "qt/risk/compliance.hpp"
#include "qt/runtime_config.hpp"
#include "qt/strategy_module.hpp"
#include "qt/trader_engine.hpp"

namespace {

struct RunMetadata {
    std::string generated_at_utc;
    std::string data_source;
    std::string dataset_id;
    std::string data_hash;
    std::string config_hash;
    std::string code_version;
    std::string execution_model_version;
    std::string sample_split;
    std::int64_t coverage_start{};
    std::int64_t coverage_end{};
    std::size_t bar_count{};
    std::size_t instrument_count{};
};

constexpr std::uint64_t FNV_OFFSET = 14695981039346656037ull;
constexpr std::uint64_t FNV_PRIME = 1099511628211ull;

std::uint64_t fnv1a_update(std::uint64_t hash, std::string_view value) {
    for (const unsigned char ch : value) {
        hash ^= static_cast<std::uint64_t>(ch);
        hash *= FNV_PRIME;
    }
    return hash;
}

std::string hex_hash(std::uint64_t hash) {
    std::ostringstream out;
    out << std::hex << std::setw(16) << std::setfill('0') << hash;
    return out.str();
}

std::string hash_file(const std::string& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input.is_open()) {
        return "missing";
    }
    std::uint64_t hash = FNV_OFFSET;
    char buffer[4096];
    while (input.read(buffer, sizeof(buffer)) || input.gcount() > 0) {
        hash = fnv1a_update(hash, std::string_view(buffer, static_cast<std::size_t>(input.gcount())));
    }
    return hex_hash(hash);
}

std::string now_utc_iso() {
    const auto now = std::chrono::system_clock::now();
    const std::time_t tt = std::chrono::system_clock::to_time_t(now);
    std::tm tm{};
    gmtime_r(&tt, &tm);
    std::ostringstream out;
    out << std::put_time(&tm, "%Y-%m-%dT%H:%M:%SZ");
    return out.str();
}

std::string json_escape(std::string_view value) {
    std::string output;
    output.reserve(value.size() + 8);
    for (const char ch : value) {
        switch (ch) {
            case '\\': output += "\\\\"; break;
            case '"': output += "\\\""; break;
            case '\n': output += "\\n"; break;
            case '\r': output += "\\r"; break;
            case '\t': output += "\\t"; break;
            default: output.push_back(ch); break;
        }
    }
    return output;
}

RunMetadata build_run_metadata(const qt::RuntimeConfig& config,
                               const std::string& config_path,
                               const std::vector<qt::Bar>& bars) {
    RunMetadata metadata;
    metadata.generated_at_utc = now_utc_iso();
    metadata.execution_model_version = "oms_sim_broker_v2";
    metadata.sample_split = "unspecified";
    metadata.config_hash = hash_file(config_path);
    metadata.code_version = std::getenv("KATRADE_CODE_VERSION") != nullptr
        ? std::getenv("KATRADE_CODE_VERSION")
        : "unknown-worktree";

    if (config.history_mode == "remote") {
        std::ostringstream source;
        source << "historyd:" << config.history_bar << ":";
        for (std::size_t i = 0; i < config.history_contracts.size(); ++i) {
            if (i) source << ",";
            source << config.history_contracts[i];
        }
        metadata.data_source = source.str();
    } else {
        metadata.data_source = config.replay_path;
    }

    std::set<std::string> instruments;
    std::uint64_t data_hash = FNV_OFFSET;
    bool has_bar = false;
    for (const auto& bar : bars) {
        has_bar = true;
        metadata.coverage_start =
            metadata.coverage_start == 0 ? bar.timestamp
                                          : std::min(metadata.coverage_start, bar.timestamp);
        metadata.coverage_end = std::max(metadata.coverage_end, bar.timestamp);
        instruments.insert(qt::instrument_key(bar.instrument));

        std::ostringstream row;
        row << bar.timestamp << '|'
            << bar.instrument.symbol << '|' << bar.instrument.exchange << '|'
            << std::setprecision(17)
            << bar.open << '|' << bar.high << '|' << bar.low << '|'
            << bar.close << '|' << bar.volume << '\n';
        data_hash = fnv1a_update(data_hash, row.str());
    }
    metadata.bar_count = bars.size();
    metadata.instrument_count = instruments.size();
    metadata.data_hash = has_bar ? hex_hash(data_hash) : "empty";
    metadata.dataset_id = "katds-" + metadata.data_hash.substr(0, 12);
    return metadata;
}

std::unique_ptr<qt::agent::MetaAgent> build_meta_agent(const qt::RuntimeConfig& config) {
    std::unique_ptr<qt::agent::IRegimeAgent> detector;
    if (config.regime_detector == "online_em") {
        detector = std::make_unique<qt::agent::OnlineEMRegimeAgent>(
            config.regime_hmm_states, config.regime_oem_dim);
    } else if (config.regime_detector == "hmm") {
        detector = std::make_unique<qt::agent::HMMRegimeAgent>(config.regime_hmm_states);
    } else {
        detector = std::make_unique<qt::agent::RuleBasedRegimeAgent>(
            config.regime_rule_crisis_vol, config.regime_rule_crisis_corr,
            config.regime_rule_trending_adx, config.regime_rule_trending_ret,
            config.regime_rule_trending_vol_cap,
            config.regime_rule_mean_revert_adx, config.regime_rule_mean_revert_vol_cap);
    }
    return std::make_unique<qt::agent::MetaAgent>(std::move(detector));
}

std::string regime_to_json(const qt::RegimeState& rs) {
    char buf[512];
    snprintf(buf, sizeof(buf),
        R"({"regime":"%s","confidence":%.4f,"mw":%.4f,"rw":%.4f,"dw":%.4f,"tp":%.4f,"rp":%.4f,"dp":%.4f,"model_version":"%s"})",
        qt::to_string(rs.regime).c_str(),
        rs.confidence,
        rs.momentum_weight, rs.mean_revert_weight, rs.defensive_weight,
        rs.trending_prob, rs.mean_revert_prob, rs.defensive_prob,
        rs.model_version.c_str());
    return buf;
}

void write_summary(const std::string& path,
                   const qt::CycleResult& result,
                   const RunMetadata& metadata) {
    std::ofstream of(path);
    if (!of) return;
    auto& pf = result.post_trade_portfolio;
    of << "cycles=1\n";
    of << "final_equity=" << pf.equity << "\n";
    of << "total_return=" << (pf.equity / result.initial_equity - 1.0) << "\n";
    of << "max_drawdown=0\n";
    of << "total_fills=" << result.reports.size() << "\n";
    of << "event_count=1\n";
    of << "total_commission=" << 0.0 << "\n";
    of << "total_signals=" << result.signals.size() << "\n";
    of << "dataset_id=" << metadata.dataset_id << "\n";
    of << "data_source=" << metadata.data_source << "\n";
    of << "data_hash=" << metadata.data_hash << "\n";
    of << "config_hash=" << metadata.config_hash << "\n";
    of << "code_version=" << metadata.code_version << "\n";
    of << "execution_model_version=" << metadata.execution_model_version << "\n";
    of << "sample_split=" << metadata.sample_split << "\n";
    of << "coverage_start=" << metadata.coverage_start << "\n";
    of << "coverage_end=" << metadata.coverage_end << "\n";
    of << "bar_count=" << metadata.bar_count << "\n";
    of << "instrument_count=" << metadata.instrument_count << "\n";
}

void write_report(const std::string& path,
                  const qt::CycleResult& result,
                  const RunMetadata& metadata) {
    std::ofstream of(path);
    if (!of) return;
    auto& pf = result.post_trade_portfolio;

    of << "{\n";
    of << "  \"metadata\": {\n";
    of << "    \"generated_at_utc\":\"" << json_escape(metadata.generated_at_utc) << "\",\n";
    of << "    \"data_source\":\"" << json_escape(metadata.data_source) << "\",\n";
    of << "    \"dataset_id\":\"" << json_escape(metadata.dataset_id) << "\",\n";
    of << "    \"data_hash\":\"" << json_escape(metadata.data_hash) << "\",\n";
    of << "    \"config_hash\":\"" << json_escape(metadata.config_hash) << "\",\n";
    of << "    \"code_version\":\"" << json_escape(metadata.code_version) << "\",\n";
    of << "    \"execution_model_version\":\""
       << json_escape(metadata.execution_model_version) << "\",\n";
    of << "    \"sample_split\":\"" << json_escape(metadata.sample_split) << "\",\n";
    of << "    \"coverage_start\":" << metadata.coverage_start << ",\n";
    of << "    \"coverage_end\":" << metadata.coverage_end << ",\n";
    of << "    \"bar_count\":" << metadata.bar_count << ",\n";
    of << "    \"instrument_count\":" << metadata.instrument_count << "\n";
    of << "  },\n";
    of << "  \"summary\": {\n";
    of << "    \"final_equity\":" << pf.equity << ",\n";
    of << "    \"total_fills\":" << result.reports.size() << ",\n";
    of << "    \"total_signals\":" << result.signals.size() << "\n";
    of << "  },\n";
    of << "  \"equity_curve\": [\n";
    of << "    {\"label\":\"" << result.cycle_label << "\",\"equity\":" << pf.equity
       << ",\"cash\":" << pf.cash << ",\"gross\":0}\n";
    of << "  ],\n";
    of << "  \"cycles\": [{\n";
    of << "    \"cycle_index\":1,\n";
    of << "    \"label\":\"" << result.cycle_label << "\",\n";
    of << "    \"regime\":" << regime_to_json(result.regime) << ",\n";
    of << "    \"features\":{},\n";

    // Signals
    of << "    \"signals\":[";
    for (size_t i = 0; i < result.signals.size(); ++i) {
        if (i) of << ",";
        auto& s = result.signals[i];
        of << "{\"strategy_id\":\"" << s.strategy_id << "\""
           << ",\"score\":" << s.score
           << ",\"confidence\":" << s.confidence << "}";
    }
    of << "],\n";

    // Target portfolio
    of << "    \"target_portfolio\":{\"positions\":[";
    for (size_t i = 0; i < result.target_portfolio.positions.size(); ++i) {
        if (i) of << ",";
        auto& tp = result.target_portfolio.positions[i];
        of << "{\"instrument\":{\"symbol\":\"" << tp.instrument.symbol << "\",\"exchange\":\"" << tp.instrument.exchange << "\"}"
           << ",\"target_weight\":" << tp.target_weight
           << ",\"strategy_id\":\"" << tp.strategy_id << "\"}";
    }
    of << "]},\n";

    // Risk decision
    of << "    \"risk_decision\":{\"action\":\"" << qt::to_string(result.risk_decision.action)
       << "\",\"reason\":\"" << result.risk_decision.reason
       << "\",\"adjusted_portfolio\":";

    auto& adj = result.risk_decision.adjusted_portfolio;
    of << "{\"positions\":[";
    for (size_t i = 0; i < adj.positions.size(); ++i) {
        if (i) of << ",";
        auto& ap = adj.positions[i];
        of << "{\"instrument\":{\"symbol\":\"" << ap.instrument.symbol << "\",\"exchange\":\"OKX\"}"
           << ",\"target_weight\":" << ap.target_weight << "}";
    }
    of << "]}},\n";

    // Pre/post portfolios
    of << "    \"pre_trade_portfolio\":{\"positions\":[],\"cash\":" << pf.cash
       << ",\"equity\":" << pf.equity << ",\"realized_pnl\":0,\"unrealized_pnl\":0},\n";
    of << "    \"post_trade_portfolio\":{\"positions\":[";
    for (size_t i = 0; i < pf.positions.size(); ++i) {
        if (i) of << ",";
        auto& p = pf.positions[i];
        of << "{\"instrument\":{\"symbol\":\"" << p.instrument.symbol << "\",\"exchange\":\"OKX\"}"
           << ",\"quantity\":" << p.quantity
           << ",\"avg_cost\":" << p.avg_cost
           << ",\"market_price\":" << p.market_price
           << ",\"market_value\":" << p.market_value
           << ",\"weight\":" << p.weight << "}";
    }
    of << "],\"cash\":" << pf.cash
       << ",\"equity\":" << pf.equity
       << ",\"realized_pnl\":" << pf.realized_pnl
       << ",\"unrealized_pnl\":" << pf.unrealized_pnl << "},\n";

    // Orders (from OMS)
    of << "    \"orders\":[";
    const auto& ord_hist = result.order_records;
    for (size_t i = 0; i < ord_hist.size(); ++i) {
        if (i) of << ",";
        auto& o = ord_hist[i];
        auto& intent = o.intent;
        of << "{\"order_id\":\"" << o.order_id << "\""
           << ",\"instrument\":{\"symbol\":\"" << intent.instrument.symbol << "\",\"exchange\":\"OKX\"}"
           << ",\"side\":\"" << qt::to_string(intent.side) << "\""
           << ",\"quantity\":" << intent.quantity
           << ",\"reference_price\":" << intent.reference_price
           << ",\"status\":\"" << qt::to_string(o.status) << "\""
           << ",\"strategy_id\":\"" << intent.strategy_id << "\"}";
    }
    of << "],\n";

    // Reports (fills)
    of << "    \"reports\":[";
    for (size_t i = 0; i < result.reports.size(); ++i) {
        if (i) of << ",";
        auto& r = result.reports[i];
        of << "{\"order_id\":\"" << r.order_id << "\""
           << ",\"instrument\":{\"symbol\":\"" << r.instrument.symbol << "\",\"exchange\":\"OKX\"}"
           << ",\"side\":\"" << qt::to_string(r.side) << "\""
           << ",\"last_fill_qty\":" << r.last_fill_qty
           << ",\"last_fill_price\":" << r.last_fill_price
           << ",\"cumulative_filled_qty\":" << r.cumulative_filled_qty
           << ",\"remaining_qty\":" << r.remaining_qty
           << ",\"avg_price\":" << r.avg_price
           << ",\"commission\":" << r.commission << "}";
    }
    of << "],\n";

    of << "    \"order_records\":[],\n";
    of << "    \"risk_budget_decision\":{}\n";
    of << "  }]\n";
    of << "}\n";
}

}  // namespace

int main(int argc, char** argv) {
    std::ios::sync_with_stdio(false);

    std::string config_path = "config/default.cfg";
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--config" && i + 1 < argc) {
            config_path = argv[++i];
        }
    }

    // Load config
    qt::RuntimeConfig config;
    try {
        config = qt::load_runtime_config(config_path);
    } catch (const std::exception& e) {
        std::cerr << "[traderd] config: " << e.what() << "\n";
    }

    // Build engine
    auto meta = build_meta_agent(config);
    auto signals = qt::make_signal_agents(config);

    std::unique_ptr<qt::IPortfolioOptimizer> optimizer;
    if (config.optimizer_type == "markowitz") {
        optimizer = std::make_unique<qt::MarkowitzPortfolioOptimizer>(
            config.optimizer_max_single_weight, config.optimizer_max_gross,
            config.optimizer_risk_aversion, config.optimizer_target_vol);
    } else if (config.optimizer_type == "risk_parity") {
        optimizer = std::make_unique<qt::RiskParityOptimizer>(
            config.optimizer_max_single_weight, config.optimizer_max_gross,
            config.optimizer_target_vol);
    } else {
        optimizer = std::make_unique<qt::SimplePortfolioOptimizer>(
            config.optimizer_max_single_weight, config.optimizer_max_gross);
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
    double equity = config.initial_cash > 0.0 ? config.initial_cash : 100000.0;

    qt::TraderEngine engine(std::move(meta), std::move(signals),
                             std::move(optimizer), std::move(risk),
                             std::move(execution), std::move(oms),
                             equity, &bus);

    engine.set_execution_params(
        config.execution_slippage_bps, config.execution_commission_bps,
        config.execution_partial_fill_prob, config.execution_default_ord_type);

    // Multiple bars for BTC-USDT-SWAP to feed lookback-dependent strategies
    // 合规持久化 (P1#7): 加载上次保存的状态
    qt::risk::ComplianceChecker compliance;
    compliance.load("logs/compliance_state.json");

    // 从 historyd 拉取真实行情数据（或从 replay CSV 回放）
    std::vector<qt::Bar> all_bars;
    try {
        auto steps = qt::ReplayDataSource::load(config);
        for (const auto& step : steps) {
            for (const auto& bar : step.bars) {
                all_bars.push_back(bar);
            }
        }
        std::cerr << "[traderd] loaded " << all_bars.size() << " bars from "
                  << steps.size() << " steps\n";
    } catch (const std::exception& e) {
        std::cerr << "[traderd] data load failed: " << e.what() << "\n";
        return 1;
    }

    if (all_bars.empty()) {
        std::cerr << "[traderd] no bars loaded\n";
        return 1;
    }

    // 按小时分批（每小时 ~60 根 1m bar），每批跑一个 cycle
    // 单根 bar 策略无法产生信号（lookback 不足），需要足够 bar 数
    std::sort(all_bars.begin(), all_bars.end(), [](const qt::Bar& a, const qt::Bar& b) {
        return a.timestamp < b.timestamp;
    });

    constexpr std::int64_t BATCH_MS = 3600 * 1000;  // 1 小时
    qt::CycleResult result;
    std::int64_t batch_start = -1;
    std::vector<qt::Bar> batch;
    for (const auto& bar : all_bars) {
        if (batch_start < 0) batch_start = bar.timestamp;
        if (bar.timestamp - batch_start >= BATCH_MS && !batch.empty()) {
            result = engine.run_cycle(batch, std::to_string(batch_start));
            batch.clear();
            batch_start = bar.timestamp;
        }
        batch.push_back(bar);
    }
    if (!batch.empty()) {
        result = engine.run_cycle(batch, std::to_string(batch_start));
    }

    std::cerr << "[traderd] final cycle: regime=" << qt::to_string(result.regime.regime)
              << " equity=" << result.post_trade_portfolio.equity
              << " signals=" << result.signals.size() << "\n";

    const auto metadata = build_run_metadata(config, config_path, all_bars);

    // 保存合规状态到磁盘，跨进程重启保留 (P1#7)
    compliance.save("logs/compliance_state.json");

    // Write outputs to config-specified paths
    std::string report_path = config.report_json_path.empty() ? "logs/last_report.json" : config.report_json_path;
    std::string summary_path = "logs/last_run_summary.txt";
    write_summary(summary_path, result, metadata);
    write_report(report_path, result, metadata);

    // Output legacy format
    auto& pf = result.post_trade_portfolio;
    std::cout << "- " << result.cycle_label
              << " equity=" << pf.equity
              << " cash=" << pf.cash
              << " gross=" << gross_exposure(pf)
              << "\n";
    std::cout << "regime=" << qt::to_string(result.regime.regime)
              << " equity=" << pf.equity
              << " fills=" << result.reports.size()
              << " signals=" << result.signals.size()
              << " orders=" << result.order_records.size() << "\n";

    return 0;
}
