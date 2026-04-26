#pragma once

#include <string>
#include <vector>

namespace qt {

struct RuntimeConfig {
    std::string replay_path{"data/sample_bars.csv"};
    std::string event_log_path{"logs/events.jsonl"};
    std::string report_json_path{"logs/last_report.json"};
    std::vector<std::string> strategy_ids;

    // history.mode=local 时沿用 replay_path。
    // history.mode=remote 时通过 history.server_url 按合约拉取 CSV，并只在本机短期缓存。
    std::string history_mode{"local"};
    std::string history_server_url{"http://127.0.0.1:8790"};
    std::vector<std::string> history_contracts;
    std::string history_cache_dir{"logs/cache/history"};
    int history_cache_ttl_seconds{1800};

    bool print_cycles{true};
    bool print_event_stream{true};

    int strategy_donchian_lookback{3};
    int strategy_ma_cross_fast_window{2};
    int strategy_ma_cross_slow_window{4};
    double strategy_macd_fast_alpha{0.55};
    double strategy_macd_slow_alpha{0.30};
    double strategy_macd_signal_alpha{0.45};
    int strategy_bollinger_window{4};
    double strategy_bollinger_band_width{1.2};
    int strategy_rsi_window{4};
    double strategy_rsi_oversold{35.0};
    double strategy_rsi_overbought{65.0};

    double initial_cash{1'000'000.0};
    double optimizer_max_single_weight{0.35};
    double optimizer_max_gross{0.90};
    double risk_max_single_weight{0.30};
    double risk_max_gross{0.80};
    double execution_min_rebalance_delta{0.02};
    double execution_max_participation_rate{0.04};
};

RuntimeConfig load_runtime_config(const std::string& path);

}  // namespace qt
