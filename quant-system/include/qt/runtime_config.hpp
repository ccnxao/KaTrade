#pragma once

#include <string>

namespace qt {

struct RuntimeConfig {
    std::string replay_path{"data/sample_bars.csv"};
    std::string event_log_path{"logs/events.jsonl"};
    bool print_cycles{true};
    bool print_event_stream{true};

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
