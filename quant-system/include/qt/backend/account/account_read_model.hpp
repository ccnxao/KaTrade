#pragma once

#include <cstdint>
#include <map>
#include <set>
#include <string>
#include <vector>

namespace qt::backend {

class ServiceContext;

struct PositionReadModel {
    std::string inst_id;
    std::string side{"flat"};
    std::string last_fill_at;
    std::string mark_source{"unmarked"};
    std::string mark_inst_id;
    std::string contract_type;
    double net_qty{0.0};
    double abs_qty{0.0};
    double avg_entry_price{0.0};
    double last_fill_price{0.0};
    double mark_price{0.0};
    double mark_notional{0.0};
    double unrealized_pnl{0.0};
    double contract_value{1.0};
    double mark_age_seconds{-1.0};
    std::int64_t mark_ts_ms{0};
    double buy_qty{0.0};
    double sell_qty{0.0};
    double notional{0.0};
    double commission{0.0};
    double realized_gross_pnl{0.0};
    double realized_net_pnl{0.0};
    double fill_count{0.0};
    double close_fill_count{0.0};
};

struct AttributionReadModel {
    std::string key;
    std::string strategy_id;
    std::string agent_id;
    std::string trading_unit_id;
    std::string trading_unit_name;
    std::string display_name;
    std::string style{"unknown"};
    std::string last_fill_at;
    double fill_count{0.0};
    double close_fill_count{0.0};
    double open_fill_count{0.0};
    double win_count{0.0};
    double loss_count{0.0};
    double filled_qty{0.0};
    double closed_qty{0.0};
    double opened_qty{0.0};
    double notional{0.0};
    double commission{0.0};
    double close_gross_pnl{0.0};
    double close_fee{0.0};
    double close_net_pnl{0.0};
    std::map<std::string, double> attribution_sources;
    std::set<std::string> strategy_ids;
};

struct RecentFillReadModel {
    std::string ts;
    std::string source_order_id;
    std::string order_id;
    std::string inst_id;
    std::string side;
    std::string strategy_id;
    std::string agent_id;
    std::string trading_unit_id;
    std::string position_effect;
    std::string attribution_source;
    double filled_qty{0.0};
    double fill_price{0.0};
    double closed_qty{0.0};
    double opened_qty{0.0};
    double close_net_pnl{0.0};
};

struct EquityCurvePoint {
    std::string label;
    std::string ts;
    std::string source;
    std::string source_order_id;
    std::string inst_id;
    std::string run_id;
    int cycle_index{0};
    std::int64_t ts_ms{0};
    double equity{0.0};
    double cash{0.0};
    double gross_exposure{0.0};
    double realized_pnl{0.0};
    double unrealized_pnl{0.0};
    double close_net_pnl{0.0};
    double cumulative_close_gross_pnl{0.0};
    double cumulative_commission{0.0};
    double cumulative_realized_net_pnl{0.0};
};

struct PortfolioReadModel {
    int order_events_scanned{0};
    int ledger_events_scanned{0};
    int fill_count{0};
    int close_fill_count{0};
    int unknown_fill_count{0};
    int marked_position_count{0};
    double total_notional{0.0};
    double total_mark_notional{0.0};
    double total_unrealized_pnl{0.0};
    double total_commission{0.0};
    double total_close_gross_pnl{0.0};
    double total_close_fee{0.0};
    double total_close_net_pnl{0.0};
    double attributed_close_net_pnl{0.0};
    double unknown_close_net_pnl{0.0};
    double reported_final_equity{0.0};
    std::map<std::string, PositionReadModel> positions;
    std::map<std::string, AttributionReadModel> by_strategy;
    std::map<std::string, AttributionReadModel> by_agent;
    std::map<std::string, AttributionReadModel> by_trading_unit;
    std::vector<RecentFillReadModel> recent_fills;
};

struct EquityCurveReadModel {
    std::string requested_session{"latest"};
    std::string resolved_session;
    std::string latest_session;
    double initial_cash{1'000'000.0};
    double report_final_equity{0.0};
    double cpp_realized_final_equity{0.0};
    double cpp_mark_to_market_equity{0.0};
    double cpp_open_unrealized_pnl{0.0};
    double cpp_gross_mark_notional{0.0};
    double cpp_cumulative_close_gross_pnl{0.0};
    double cpp_cumulative_commission{0.0};
    double cpp_cumulative_realized_net_pnl{0.0};
    int order_events_scanned{0};
    int fill_events_scanned{0};
    int marked_position_count{0};
    std::vector<EquityCurvePoint> report_points;
    std::vector<EquityCurvePoint> realized_points;
    std::vector<EquityCurvePoint> mark_to_market_points;
};

PortfolioReadModel build_portfolio_read_model(ServiceContext& ctx,
                                             int limit,
                                             int recent_limit,
                                             const std::string& session_filter = "");
EquityCurveReadModel build_equity_curve_read_model(ServiceContext& ctx,
                                                   int point_limit,
                                                   std::string requested_session,
                                                   int order_limit);

}  // namespace qt::backend
