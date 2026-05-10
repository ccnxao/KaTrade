#pragma once

#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace qt::backend {

struct BackendConfig {
    std::filesystem::path root{"."};
    std::filesystem::path config_path{"config/default.cfg"};
    std::string host{"127.0.0.1"};
    int port{8791};
    std::string method{"GET"};
    std::string route{"/api/backend/summary"};
    bool serve{false};
};

struct FileSnapshot {
    std::string path;
    bool exists{false};
    std::uintmax_t bytes{0};
    std::int64_t modified_epoch_ms{0};
    double age_seconds{-1.0};
    std::size_t line_count{0};
};

class ServiceContext {
public:
    explicit ServiceContext(BackendConfig config);

    const BackendConfig& config() const noexcept { return config_; }
    const std::filesystem::path& root() const noexcept { return config_.root; }
    std::filesystem::path logs_dir() const;
    std::filesystem::path order_journal_path() const;
    std::filesystem::path execution_trace_path() const;
    std::filesystem::path execution_ledger_path() const;
    std::filesystem::path okx_audit_path() const;
    std::filesystem::path market_quality_path() const;
    std::filesystem::path backendd_status_path() const;

    std::string now_iso() const;
    std::int64_t now_epoch_ms() const;
    FileSnapshot file_snapshot(const std::filesystem::path& path, bool count_lines = false) const;

    std::vector<std::string> read_tail_lines(const std::filesystem::path& path,
                                             std::size_t max_lines,
                                             std::size_t max_bytes = 4'000'000) const;
    std::string read_text(const std::filesystem::path& path, std::size_t max_bytes = 2'000'000) const;

    void write_status(std::string_view mode, bool ok, std::string_view message) const;

private:
    BackendConfig config_;
};

}  // namespace qt::backend
