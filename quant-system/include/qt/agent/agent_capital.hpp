#pragma once

#include <cstddef>
#include <string>
#include <unordered_map>
#include <vector>

namespace qt::agent {

struct AgentCapitalConfig {
    double min_capital_share{0.01};
    double max_capital_share{0.40};
    int rebalance_interval{100};
    double lookback_sharpe_window{30};
};

class CapitalAllocator {
public:
    explicit CapitalAllocator(const AgentCapitalConfig& config = {});

    void initialize(const std::vector<std::string>& agent_ids, double total_equity);
    void update_total_equity(double equity);
    double agent_capital(const std::string& agent_id) const;
    double agent_capital_share(const std::string& agent_id) const;
    bool should_rebalance(std::size_t cycle_index) const;
    void rebalance(std::size_t cycle_index, const std::vector<std::string>& agent_ids);
    void record_pnl(const std::string& agent_id, double pnl, std::int64_t timestamp_ms);
    void record_trade(const std::string& agent_id, bool winner);

private:
    AgentCapitalConfig config_;
    double total_equity_{0.0};
    std::unordered_map<std::string, double> capital_;
    std::unordered_map<std::string, double> cumulative_pnl_;
    std::unordered_map<std::string, int> trade_count_;
    std::unordered_map<std::string, int> win_count_;
    std::size_t last_rebalance_cycle_{0};
};

}  // namespace qt::agent
