#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "qt/types.hpp"

namespace qt::execution {

class ExecutionLedger {
public:
    void record(const ExecutionReport& report);

    struct Entry {
        std::int64_t timestamp_ms;
        std::string order_id;
        std::string instrument;
        std::string side;
        double fill_qty;
        double fill_price;
        double commission;
    };
    const std::vector<Entry>& entries() const noexcept { return entries_; }

private:
    std::vector<Entry> entries_;
};

}  // namespace qt::execution
