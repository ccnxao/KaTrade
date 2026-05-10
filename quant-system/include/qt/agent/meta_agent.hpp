#pragma once

#include <memory>
#include <string>
#include <string_view>
#include <vector>

#include "qt/agent/agent.hpp"
#include "qt/types.hpp"

namespace qt::agent {

class RuleBasedRegimeAgent : public IRegimeAgent {
public:
    // 可传入 config 阈值，默认值与旧硬编码一致
    explicit RuleBasedRegimeAgent(double crisis_vol = 0.30, double crisis_corr = 0.80,
                                   double trending_adx = 25.0, double trending_ret = 0.02,
                                   double trending_vol_cap = 0.30,
                                   double mean_revert_adx = 18.0, double mean_revert_vol_cap = 0.20);
    std::string_view name() const noexcept override;
    RegimeState detect_regime(const FeatureFrame& features) override;

private:
    double crisis_vol_, crisis_corr_;
    double trending_adx_, trending_ret_, trending_vol_cap_;
    double mean_revert_adx_, mean_revert_vol_cap_;
};

class HMMRegimeAgent : public IRegimeAgent {
public:
    explicit HMMRegimeAgent(int states = 3);
    std::string_view name() const noexcept override;
    RegimeState detect_regime(const FeatureFrame& features) override;
    void fit_online(const FeatureFrame& features) override;

private:
    int states_;
    int dim_{1};
    int obs_count_{0};
    bool fitted_{false};
    std::vector<double> means_;
    std::vector<double> vars_;
    std::vector<double> trans_;
    std::vector<double> forward_;
};

class OnlineEMRegimeAgent : public IRegimeAgent {
public:
    explicit OnlineEMRegimeAgent(int states = 3, int dim = 2);
    std::string_view name() const noexcept override;
    RegimeState detect_regime(const FeatureFrame& features) override;
    void fit_online(const FeatureFrame& features) override;

private:
    std::vector<double> forward_filter(const std::vector<double>& obs);
    void online_em_step(const std::vector<double>& obs);

    int states_;
    int dim_;
    int obs_count_{0};
    int trans_count_{0};
    bool fitted_{false};
    bool fitted_this_cycle_{false};  // R08: 防止同周期双重更新
    double nu_{4.0};
    std::vector<double> means_;
    std::vector<double> vars_;
    std::vector<double> corr_;     // GAP-016: 状态间协方差相关系数
    std::vector<double> trans_;
    std::vector<double> trans_counts_;
    std::vector<double> forward_;
    std::vector<double> prev_forward_;
};

class MetaAgent : public IMetaAgent {
public:
    MetaAgent();
    explicit MetaAgent(std::unique_ptr<IRegimeAgent> detector);
    void set_detector(std::unique_ptr<IRegimeAgent> detector);
    void add_agent(std::unique_ptr<ISignalAgent> agent);
    const IRegimeAgent* detector() const noexcept;
    IRegimeAgent* detector() noexcept;  // mutable access for fit_online

    std::string_view name() const noexcept override;
    void on_bar(const Bar& bar) override;
    RegimeState detect_regime(const FeatureFrame& features) override;
    void record_cycle_pnl(double pnl) override;
    void reset() override;

    // R49: 暴露累积指标
    double cumulative_pnl() const noexcept { return cumulative_pnl_; }
    int cycle_count() const noexcept { return cycle_count_; }
    const std::vector<double>& recent_pnls() const noexcept { return recent_pnls_; }

private:
    std::unique_ptr<IRegimeAgent> detector_;
    std::vector<std::unique_ptr<ISignalAgent>> agents_;
    std::vector<double> recent_pnls_;
    double cumulative_pnl_{0.0};
    int cycle_count_{0};
};

}  // namespace qt::agent
