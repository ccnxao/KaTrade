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
    std::string history_bar{"1m"};
    std::string history_start;
    std::string history_end;
    int history_max_pages{40};

    bool print_cycles{true};
    bool print_event_stream{true};
    int metrics_drawdown_stride{1};

    int strategy_donchian_lookback{3};
    int strategy_ma_cross_fast_window{2};
    int strategy_ma_cross_slow_window{4};
    double strategy_macd_fast_alpha{0.55};
    double strategy_macd_slow_alpha{0.30};
    double strategy_macd_signal_alpha{0.45};
    double strategy_ema_slope_alpha{0.35};
    double strategy_ema_slope_min_slope{0.001};
    double strategy_keltner_alpha{0.25};
    double strategy_keltner_multiplier{1.5};
    double strategy_volume_spike_alpha{0.20};
    double strategy_volume_spike_multiplier{1.8};
    double strategy_micro_scalper_min_return{0.0004};
    double strategy_micro_scalper_min_body_ratio{0.35};
    double strategy_spread_capture_alpha{0.25};
    double strategy_spread_capture_threshold{0.55};
    double strategy_order_flow_volume_alpha{0.20};
    double strategy_order_flow_imbalance_threshold{0.45};
    double strategy_inventory_skew_neutral_band{0.04};
    int strategy_bollinger_window{4};
    double strategy_bollinger_band_width{1.2};
    int strategy_rsi_window{4};
    double strategy_rsi_oversold{35.0};
    double strategy_rsi_overbought{65.0};
    int strategy_zscore_window{8};
    double strategy_zscore_threshold{1.25};

    double initial_cash{1'000'000.0};

    // GAP-032: 组合优化器配置
    std::string optimizer_type{"simple"};      // simple | markowitz | risk_parity
    double optimizer_max_single_weight{0.35};
    double optimizer_max_gross{0.90};
    double optimizer_risk_aversion{1.0};       // Markowitz 风险厌恶系数
    double optimizer_target_vol{0.15};          // 目标年化波动率
    int optimizer_cov_lookback{60};              // 协方差估计回溯 bar 数

    double risk_max_single_weight{0.30};
    double risk_max_gross{0.80};
    double risk_max_order_notional{50'000.0};
    bool risk_kill_switch{false};
    double risk_drawdown_limit{0.20};       // 回撤熔断阈值
    double risk_vol_threshold{0.30};         // 高波动率阈值
    double risk_vol_reduction{0.50};         // 高波动率时的权重削减比例
    double risk_stress_tolerance{0.20};      // 压力测试回撤容忍度
    double risk_budget_scale{0.70};          // 风控预算失败时的缩放比例
    double risk_turnover_limit{0.50};        // 换手率上限
    double execution_min_rebalance_delta{0.02};
    double execution_max_participation_rate{0.04};
    double execution_maker_offset_bps{2.0};
    double execution_maker_fee_bps{1.0};
    double execution_max_expected_cost_bps{50.0};
    double execution_slippage_bps{3.0};
    double execution_commission_bps{1.0};
    double execution_partial_fill_prob{0.15};
    double execution_tp_ratio{0.03};       // 止盈比例 (GAP-009)
    double execution_sl_ratio{0.02};        // 止损比例 (GAP-009)
    std::string execution_default_ord_type{"limit"};  // market | limit | post_only
    int execution_pending_order_ttl_bars{1};
    bool execution_derivatives_enabled{false};
    std::string execution_derivatives_inst_type{"SWAP"};
    std::string execution_derivatives_margin_mode{"isolated"};
    std::string execution_derivatives_position_mode{"net"};
    double execution_derivatives_max_exchange_leverage{3.0};
    double execution_derivatives_max_effective_leverage{2.0};
    double execution_derivatives_max_unit_effective_leverage{1.0};
    double execution_trade_unit_base_notional_usdt{1.0};
    bool execution_trade_unit_agent_leverage_enabled{true};
    double execution_trade_unit_agent_max_step{0.5};

    // Agent 多智能体资金管理
    double agent_total_capital_ratio{0.85};
    double agent_min_capital_ratio{0.025};
    double agent_max_capital_ratio{0.30};
    int agent_capital_rebalance_cycles{100};
    int agent_performance_window{90};
    int agent_min_trades_for_review{20};
    double agent_elimination_sharpe{-0.5};
    double agent_elimination_drawdown{0.20};
    int agent_elimination_grace_cycles{200};
    bool agent_auto_activate{true};
    int agent_max_active{8};

    // Regime 检测配置
    std::string regime_detector{"rule"};     // rule | hmm | online_em
    int regime_hmm_states{3};                // 隐状态数
    int regime_oem_dim{2};                   // OnlineEM 特征维度 (1=vol, 2=vol+ADX, 3=vol+ADX+autocorr)
    double regime_rule_crisis_vol{0.30};
    double regime_rule_crisis_corr{0.80};
    double regime_rule_trending_adx{25.0};
    double regime_rule_trending_ret{0.05};
    double regime_rule_trending_vol_cap{0.30};
    double regime_rule_mean_revert_adx{20.0};
    double regime_rule_mean_revert_vol_cap{0.20};
};

RuntimeConfig load_runtime_config(const std::string& path);

}  // namespace qt
