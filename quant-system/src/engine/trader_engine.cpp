#include "qt/trader_engine.hpp"

#include <algorithm>
#include <chrono>
#include <sstream>
#include <utility>

#include "qt/data/feature_store.hpp"

namespace qt {

namespace {

risk::RiskBudgetDecision skipped_budget_decision(RiskAction action,
                                                 const std::string& reason) {
    risk::RiskBudgetDecision decision;
    decision.action = action;
    decision.scale = 0.0;
    decision.reason = "基础风控已阻断，跳过风险预算：" + reason;
    return decision;
}

void apply_runtime_budget(CycleResult& result,
                          const risk::RiskBudgetDecision& budget) {
    if (budget.action == RiskAction::Halt || budget.action == RiskAction::Reject) {
        result.risk_decision.action = budget.action;
        result.risk_decision.reason = budget.reason;
        result.risk_decision.adjusted_portfolio = budget.adjusted_portfolio;
        return;
    }

    if (budget.action == RiskAction::Reduce) {
        result.risk_decision.action = RiskAction::Reduce;
        result.risk_decision.reason = result.risk_decision.reason.empty()
            ? budget.reason
            : result.risk_decision.reason + " / " + budget.reason;
        result.risk_decision.adjusted_portfolio = budget.adjusted_portfolio;
        return;
    }

    if (result.risk_decision.adjusted_portfolio.positions.empty()) {
        result.risk_decision.adjusted_portfolio = budget.adjusted_portfolio;
    }
}

void refresh_cycle_order_records(
    CycleResult& result,
    const std::vector<execution::OmsOrderRecord>& order_history) {
    const auto find_record = [&](const std::string& order_id)
        -> const execution::OmsOrderRecord* {
        for (const auto& record : order_history) {
            if (record.order_id == order_id) {
                return &record;
            }
        }
        return nullptr;
    };

    for (auto& record : result.order_records) {
        if (const auto* latest = find_record(record.order_id)) {
            record = *latest;
        }
    }

    for (const auto& report : result.reports) {
        const bool already_present = std::any_of(
            result.order_records.begin(), result.order_records.end(),
            [&](const auto& record) { return record.order_id == report.order_id; });
        if (!already_present) {
            if (const auto* latest = find_record(report.order_id)) {
                result.order_records.push_back(*latest);
            }
        }
    }
}

}  // namespace

TraderEngine::TraderEngine(
    std::unique_ptr<IMetaAgent> meta_agent,
    std::vector<std::unique_ptr<ISignalAgent>> signal_agents,
    std::unique_ptr<IPortfolioOptimizer> optimizer,
    std::unique_ptr<RiskAgent> risk_agent,
    std::unique_ptr<IExecutionAlgo> execution_algo,
    std::unique_ptr<OrderManagementSystem> order_management_system,
    double account_equity,
    EventBus* event_bus)
    : meta_agent_(std::move(meta_agent))
    , signal_agents_(std::move(signal_agents))
    , optimizer_(std::move(optimizer))
    , risk_agent_(std::move(risk_agent))
    , execution_algo_(std::move(execution_algo))
    , order_management_system_(std::move(order_management_system))
    , portfolio_book_(account_equity)
    , account_equity_(account_equity)
    , peak_equity_(account_equity)
    , event_bus_(event_bus) {}

CycleResult TraderEngine::run_cycle(const std::vector<Bar>& bars, std::string cycle_label) {
    CycleResult result;
    result.cycle_index = ++cycle_id_;
    result.cycle_label = cycle_label.empty() ? "cycle_" + std::to_string(cycle_id_) : cycle_label;
    result.initial_equity = account_equity_;

    if (event_bus_) {
        event_bus_->publish(CycleStartedEvent{result.cycle_index, result.cycle_label, bars.size()});
    }

    // Feed bars to all agents to build history
    for (const auto& bar : bars) {
        if (meta_agent_) meta_agent_->on_bar(bar);
        for (auto& agent : signal_agents_) {
            agent->on_bar(bar);
        }
    }

    result.prices = build_prices(bars);
    result.pre_trade_portfolio = portfolio_book_.snapshot();

    result.features = build_features(bars);

    // 按品种分组 bars，做 per-instrument regime 检测
    std::unordered_map<std::string, std::vector<Bar>> bars_by_instrument;
    for (const auto& bar : bars) {
        bars_by_instrument[instrument_key(bar.instrument)].push_back(bar);
    }

    if (meta_agent_) {
        auto* meta = dynamic_cast<agent::MetaAgent*>(meta_agent_.get());
        if (meta && meta->detector()) {
            auto* hmm = dynamic_cast<agent::HMMRegimeAgent*>(meta->detector());
            if (hmm) {
                hmm->fit_online(result.features);
            } else {
                auto* oem = dynamic_cast<agent::OnlineEMRegimeAgent*>(meta->detector());
                if (oem) oem->fit_online(result.features);
            }
        }
        // 全局 regime（用全部特征，向后兼容）
        result.regime = meta_agent_->detect_regime(result.features);
        if (event_bus_) {
            event_bus_->publish(RegimeDetectedEvent{result.cycle_index, result.regime});
        }
        // Per-instrument regime
        for (const auto& [inst_key, inst_bars] : bars_by_instrument) {
            auto inst_features = build_features(inst_bars);
            result.regime_by_instrument[inst_key] = meta_agent_->detect_regime(inst_features);
        }
    }

    for (auto& agent : signal_agents_) {
        auto signals = agent->generate_signals(
            result.features, result.pre_trade_portfolio, result.regime);
        for (auto& sig : signals) {
            auto kit = result.regime_by_instrument.find(instrument_key(sig.instrument));
            if (kit != result.regime_by_instrument.end()) {
                sig.confidence = kit->second.confidence;
            }
            result.signals.push_back(std::move(sig));
        }
    }

    if (optimizer_) {
        result.target_portfolio = optimizer_->optimize(
            result.signals, result.pre_trade_portfolio,
            result.features, result.regime);
    }

    if (risk_agent_) {
        qt::risk::AccountState account;
        account.equity = result.pre_trade_portfolio.equity;
        account.cash = result.pre_trade_portfolio.cash;
        account.initial_equity = account_equity_;
        peak_equity_ = std::max(peak_equity_, result.pre_trade_portfolio.equity);
        account.peak_equity = peak_equity_;

        qt::risk::MarketState market;
        auto it_vol = result.features.find("realized_vol_20d");
        market.vix = it_vol != result.features.end() ? it_vol->second : 0.15;

        result.risk_decision = risk_agent_->review(
            result.target_portfolio, result.pre_trade_portfolio, market, account);

        if (event_bus_) {
            event_bus_->publish(RiskReviewedEvent{result.cycle_index, result.risk_decision});
        }
    }

    if (risk_budget_reviewer_) {
        if (result.risk_decision.action == RiskAction::Reject ||
            result.risk_decision.action == RiskAction::Halt) {
            result.risk_budget_decision =
                skipped_budget_decision(result.risk_decision.action,
                                        result.risk_decision.reason);
        } else {
            result.risk_budget_decision = risk_budget_reviewer_(result);
            apply_runtime_budget(result, result.risk_budget_decision);
        }
    }

    if (execution_algo_ && result.risk_decision.action != RiskAction::Reject &&
        result.risk_decision.action != RiskAction::Halt) {
        ExecutionConfig exec_cfg;
        exec_cfg.default_ord_type = exec_default_ord_type_;
        const auto& portfolio_to_execute = result.risk_decision.action == RiskAction::Reduce
            ? result.risk_decision.adjusted_portfolio
            : result.target_portfolio;

        if (!portfolio_to_execute.positions.empty()) {
            result.orders = execution_algo_->plan(
                result.risk_decision, result.pre_trade_portfolio,
                result.features, exec_cfg);
            for (auto& order : result.orders) {
                const auto price_it = result.prices.find(instrument_key(order.instrument));
                const double price = price_it != result.prices.end() ? price_it->second
                                                                     : order.reference_price;
                if (order.reference_price <= 0.0 && price > 0.0) {
                    order.reference_price = price;
                }
                double agent_cap = result.pre_trade_portfolio.equity;
                if (!order.strategy_id.empty()) {
                    double cap = capital_allocator_.agent_capital(order.strategy_id);
                    if (cap > 0.0) agent_cap = cap;
                }
                if (price > 0.0 && order.quantity > 0.0 && order.quantity <= 1.0) {
                    order.quantity = order.quantity * agent_cap / price;
                }
            }
        }
    }

    if (order_management_system_) {
        if (!result.orders.empty()) {
            result.order_records = order_management_system_->submit_orders(result.orders);

            for (const auto& rec : result.order_records) {
                if (event_bus_) {
                    event_bus_->publish(OrderSubmittedEvent{
                        result.cycle_index,
                        {rec.order_id, rec.intent, rec.status, rec.filled_qty,
                         rec.remaining_qty, rec.avg_price, rec.commission}});
                }
            }
        }

        order_management_system_->on_market_snapshot(bars);
        result.reports = order_management_system_->collect_reports();
        refresh_cycle_order_records(result, order_management_system_->order_history());

        if (event_bus_) {
            for (const auto& report : result.reports) {
                if (report.last_fill_qty > 0.0) {
                    event_bus_->publish(OrderFilledEvent{result.cycle_index, report});
                }
            }
        }
    }

    portfolio_book_.apply_reports(result.reports);
    portfolio_book_.mark_to_market(result.prices);
    result.post_trade_portfolio = portfolio_book_.snapshot();
    capital_allocator_.update_total_equity(result.post_trade_portfolio.equity);

    {
        double cycle_realized_delta =
            result.post_trade_portfolio.realized_pnl - result.pre_trade_portfolio.realized_pnl;
        std::unordered_map<std::string, double> agent_notional;
        double total_notional = 0.0;
        for (const auto& report : result.reports) {
            if (report.last_fill_qty <= 0.0 || report.last_fill_price <= 0.0) continue;
            double notional = report.last_fill_qty * report.last_fill_price;
            for (const auto& rec : result.order_records) {
                if (rec.order_id == report.order_id && !rec.intent.strategy_id.empty()) {
                    agent_notional[rec.intent.strategy_id] += notional;
                    total_notional += notional;
                    break;
                }
            }
        }
        if (total_notional > 0.0) {
            for (const auto& [agent_id, notional] : agent_notional) {
                double share = notional / total_notional;
                double agent_pnl = cycle_realized_delta * share;
                auto now_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                    std::chrono::system_clock::now().time_since_epoch()).count();
                capital_allocator_.record_pnl(agent_id, agent_pnl, now_ms);
                capital_allocator_.record_trade(agent_id, agent_pnl > 0.0);
            }
        }
    }

    if (meta_agent_) {
        double cycle_pnl = result.post_trade_portfolio.realized_pnl
                         - result.pre_trade_portfolio.realized_pnl;
        meta_agent_->record_cycle_pnl(cycle_pnl);
    }

    if (event_bus_) {
        event_bus_->publish(CycleCompletedEvent{
            result.cycle_index, result.cycle_label,
            result.signals.size(), result.order_records.size(), result.reports.size()
        });
    }

    if (capital_allocator_.should_rebalance(result.cycle_index)) {
        std::vector<std::string> candidate_ids;
        for (const auto& agent : signal_agents_) {
            candidate_ids.emplace_back(agent->name());
        }
        capital_allocator_.rebalance(result.cycle_index, candidate_ids);
    }

    return result;
}

PortfolioSnapshot TraderEngine::portfolio() const {
    return portfolio_book_.snapshot();
}

void TraderEngine::set_risk_budget_reviewer(RiskBudgetReviewer reviewer) {
    risk_budget_reviewer_ = std::move(reviewer);
}

void TraderEngine::setup_agent_capital(const agent::AgentCapitalConfig& config,
                                        const std::vector<std::string>& strategy_ids,
                                        double total_equity) {
    capital_allocator_ = agent::CapitalAllocator(config);
    capital_allocator_.initialize(strategy_ids, total_equity);
}

FeatureFrame TraderEngine::build_features(const std::vector<Bar>& bars) {
    feature_engine_.feed_bars(bars);
    auto frame = feature_engine_.compute();

    // FeatureEngine::compute() 已按品种分组计算 vol/adx/ret/corr
    // 同时写入 bare key 和 market.* 前缀，供不同消费者使用
    for (const auto& bare_key : {"realized_vol_20d", "ret_20d", "adx_20d", "avg_corr_20d"}) {
        auto it = frame.find(bare_key);
        if (it != frame.end()) {
            frame[std::string("market.") + bare_key] = it->second;
        }
    }

    // GAP-032: 协方差矩阵估计（供 Markowitz / Risk Parity 优化器使用）
    auto cov_map = feature_engine_.compute_covariance_map(60);
    for (const auto& entry : cov_map) {
        frame[entry.first] = entry.second;
    }

    // GAP-033: 交易日历信息
    if (!bars.empty()) {
        int64_t ts = bars.back().timestamp > 0
            ? bars.back().timestamp
            : static_cast<int64_t>(
                std::chrono::duration_cast<std::chrono::milliseconds>(
                    std::chrono::system_clock::now().time_since_epoch()).count());
        auto session = calendar_.session(ts);
        frame["session.is_weekend"] = calendar_.is_weekend(ts) ? 1.0 : 0.0;
        frame["session.is_funding"] = calendar_.is_funding_settlement(ts, 300) ? 1.0 : 0.0;
        frame["session.until_funding_s"] = static_cast<double>(
            calendar_.seconds_until_next_funding(ts));
        // 时段编码: Asia=0, Europe=1, America=2, Weekend=3
        frame["session.type"] = static_cast<double>(static_cast<int>(session));
        frame["session.is_month_start"] = calendar_.is_month_start(ts) ? 1.0 : 0.0;
        frame["session.is_week_start"] = calendar_.is_week_start(ts) ? 1.0 : 0.0;
    }

    return frame;
}

PriceMap TraderEngine::build_prices(const std::vector<Bar>& bars) const {
    PriceMap prices;
    for (const auto& bar : bars) {
        prices[instrument_key(bar.instrument)] = bar.close;
    }
    return prices;
}

}  // namespace qt
