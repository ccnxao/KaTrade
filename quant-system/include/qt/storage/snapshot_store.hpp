#pragma once

#include <string>
#include <vector>

#include "qt/types.hpp"

namespace qt {
struct CycleResult;
}

namespace qt::storage {

class SnapshotStore {
public:
    void save_cycle_result(const CycleResult& result);
    void save_equity_point(const EquityPoint& point);
    std::vector<EquityPoint> load_equity_curve() const;

private:
    std::vector<EquityPoint> equity_curve_;
};

}  // namespace qt::storage
