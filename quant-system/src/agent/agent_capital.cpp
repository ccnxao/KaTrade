#include "qt/agent/agent_capital.hpp"

#include <algorithm>
#include <cmath>

namespace qt::agent {

CapitalAllocator::CapitalAllocator(const AgentCapitalConfig& config)
    : config_(config) {}

void CapitalAllocator::initialize(const std::vector<std::string>& agent_ids,
                                   double total_equity) {
    total_equity_ = total_equity;
    double each = total_equity / std::max(agent_ids.size(), size_t(1));
    for (const auto& id : agent_ids) {
        capital_[id] = each;
        cumulative_pnl_[id] = 0.0;
        trade_count_[id] = 0;
        win_count_[id] = 0;
    }
}

void CapitalAllocator::update_total_equity(double equity) {
    total_equity_ = equity;
}

double CapitalAllocator::agent_capital(const std::string& agent_id) const {
    auto it = capital_.find(agent_id);
    return it != capital_.end() ? it->second : 0.0;
}

double CapitalAllocator::agent_capital_share(const std::string& agent_id) const {
    if (total_equity_ <= 0.0) return 0.0;
    return agent_capital(agent_id) / total_equity_;
}

bool CapitalAllocator::should_rebalance(std::size_t cycle_index) const {
    return cycle_index > 0 &&
           cycle_index - last_rebalance_cycle_ >=
               static_cast<std::size_t>(config_.rebalance_interval);
}

void CapitalAllocator::rebalance(std::size_t cycle_index,
                                  const std::vector<std::string>& agent_ids) {
    if (agent_ids.empty()) return;

    double total_pnl = 0.0;
    for (const auto& id : agent_ids) {
        total_pnl += cumulative_pnl_[id];
    }

    double min_share = config_.min_capital_share;
    double max_share = config_.max_capital_share;

    for (const auto& id : agent_ids) {
        double pnl_share = total_pnl > 0.0
            ? std::max(cumulative_pnl_[id], 0.0) / std::max(total_pnl, 1.0)
            : 1.0 / agent_ids.size();

        double share = min_share + (max_share - min_share) * pnl_share;
        capital_[id] = total_equity_ * std::clamp(share, min_share, max_share);
    }

    // 归一化：防止各 agent 独立 clamp 导致总分配超过总权益
    double total_allocated = 0.0;
    for (const auto& id : agent_ids) {
        total_allocated += capital_[id];
    }
    if (total_allocated > total_equity_ && total_allocated > 0.0) {
        double scale = total_equity_ / total_allocated;
        for (const auto& id : agent_ids) {
            capital_[id] *= scale;
        }
    }

    last_rebalance_cycle_ = cycle_index;
}

void CapitalAllocator::record_pnl(const std::string& agent_id,
                                   double pnl, std::int64_t) {
    cumulative_pnl_[agent_id] += pnl;
}

void CapitalAllocator::record_trade(const std::string& agent_id, bool winner) {
    trade_count_[agent_id]++;
    if (winner) win_count_[agent_id]++;
}

}  // namespace qt::agent
