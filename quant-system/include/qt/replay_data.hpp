#pragma once

#include <string>
#include <vector>

#include "qt/backtest_engine.hpp"
#include "qt/runtime_config.hpp"

namespace qt {

class CsvReplayLoader {
public:
    static std::vector<BacktestStep> load(const std::string& path);
    static std::vector<BacktestStep> load_many(const std::vector<std::string>& paths);
};

class ReplayDataSource {
public:
    static std::vector<BacktestStep> load(const RuntimeConfig& config);
};

}  // namespace qt
