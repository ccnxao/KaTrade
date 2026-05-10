#pragma once

#include <cstdint>
#include <string>

namespace qt::ops {

struct AuditEntry {
    std::int64_t timestamp_ms{};
    std::string event_type;
    std::string source;
    std::string message;
    std::string details;
    double equity{};
};

class AuditLogger {
public:
    static AuditLogger& instance();
    void log(const AuditEntry& entry);

private:
    AuditLogger() = default;
};

}  // namespace qt::ops
