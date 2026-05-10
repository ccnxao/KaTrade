#include "qt/agent/meta_agent.hpp"

#include <algorithm>
#include <cmath>

namespace qt::agent {

// ---- MetaAgent ----
MetaAgent::MetaAgent()
    : detector_(std::make_unique<RuleBasedRegimeAgent>()) {}

MetaAgent::MetaAgent(std::unique_ptr<IRegimeAgent> detector)
    : detector_(std::move(detector)) {}

void MetaAgent::set_detector(std::unique_ptr<IRegimeAgent> detector) {
    detector_ = std::move(detector);
}

void MetaAgent::add_agent(std::unique_ptr<ISignalAgent> agent) {
    agents_.push_back(std::move(agent));
}

const IRegimeAgent* MetaAgent::detector() const noexcept {
    return detector_.get();
}
IRegimeAgent* MetaAgent::detector() noexcept {
    return detector_.get();
}

std::string_view MetaAgent::name() const noexcept {
    return "meta_agent";
}

void MetaAgent::on_bar(const Bar& bar) {
    for (auto& agent : agents_) {
        agent->on_bar(bar);
    }
}

RegimeState MetaAgent::detect_regime(const FeatureFrame& features) {
    if (!detector_) {
        return {Regime::Uncertain, 0.0, 0.33, 0.33, 0.34,
                0.33, 0.33, 0.34, "no_detector"};
    }
    return detector_->detect_regime(features);
}

void MetaAgent::record_cycle_pnl(double pnl) {
    cumulative_pnl_ += pnl;
    cycle_count_++;

    // 误判检测: 如果连续 N 个周期 PnL 符号与 regime 方向不一致，标记
    // 当前简化: 只累积
    recent_pnls_.push_back(pnl);
    if (recent_pnls_.size() > 10) {
        recent_pnls_.erase(recent_pnls_.begin());
    }
}

void MetaAgent::reset() {
    cumulative_pnl_ = 0.0;
    cycle_count_ = 0;
    recent_pnls_.clear();
    for (auto& agent : agents_) {
        agent->reset();
    }
}

}  // namespace qt::agent
