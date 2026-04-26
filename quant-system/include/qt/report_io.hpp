#pragma once

#include <string>

#include "qt/backtest_engine.hpp"
#include "qt/event_bus.hpp"

namespace qt {

struct GoldenMetrics {
    std::size_t cycles{};
    std::size_t event_count{};
    std::size_t total_fills{};
    double total_commission{};
    double total_return{};
    double max_drawdown{};
    double final_equity{};
    double double_tolerance{1e-6};
};

void write_event_log_jsonl(const EventBus& event_bus, const std::string& path);
void write_report_summary(const BacktestReport& report, const std::string& path);
void write_backtest_report_json(const BacktestReport& report, const std::string& path);
GoldenMetrics load_golden_metrics(const std::string& path);
bool matches_golden_metrics(const BacktestReport& report,
                            const GoldenMetrics& metrics,
                            std::string* failure_reason);

}  // namespace qt
