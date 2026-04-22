#pragma once

#include <string>
#include <vector>

#include "qt/backtest_engine.hpp"

namespace qt {

class CsvReplayLoader {
public:
    static std::vector<BacktestStep> load(const std::string& path);
};

}  // namespace qt
