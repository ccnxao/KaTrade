#include "qt/backend/common/service_context.hpp"

#include <chrono>
#include <fstream>
#include <iomanip>
#include <sstream>

#include "qt/backend/common/json.hpp"

namespace qt::backend {

ServiceContext::ServiceContext(BackendConfig config) : config_(std::move(config)) {
    if (config_.root.empty()) {
        config_.root = ".";
    }
    config_.root = std::filesystem::absolute(config_.root).lexically_normal();
}

std::filesystem::path ServiceContext::logs_dir() const {
    return root() / "logs";
}

std::filesystem::path ServiceContext::order_journal_path() const {
    return logs_dir() / "order_journal" / "orders.jsonl";
}

std::filesystem::path ServiceContext::execution_trace_path() const {
    return logs_dir() / "execution_trace" / "decisions.jsonl";
}

std::filesystem::path ServiceContext::execution_ledger_path() const {
    return logs_dir() / "execution_ledger" / "events.jsonl";
}

std::filesystem::path ServiceContext::okx_audit_path() const {
    return logs_dir() / "broker" / "okx_audit.jsonl";
}

std::filesystem::path ServiceContext::market_quality_path() const {
    return logs_dir() / "market_quality" / "latest.json";
}

std::filesystem::path ServiceContext::backendd_status_path() const {
    return logs_dir() / "backendd" / "status.json";
}

std::int64_t ServiceContext::now_epoch_ms() const {
    const auto now = std::chrono::system_clock::now().time_since_epoch();
    return std::chrono::duration_cast<std::chrono::milliseconds>(now).count();
}

std::string ServiceContext::now_iso() const {
    const auto now = std::chrono::system_clock::now();
    const auto t = std::chrono::system_clock::to_time_t(now);
    std::tm tm{};
#if defined(_WIN32)
    gmtime_s(&tm, &t);
#else
    gmtime_r(&t, &tm);
#endif
    std::ostringstream oss;
    oss << std::put_time(&tm, "%Y-%m-%dT%H:%M:%SZ");
    return oss.str();
}

FileSnapshot ServiceContext::file_snapshot(const std::filesystem::path& path, bool count_lines) const {
    FileSnapshot snap;
    snap.path = path.string();
    std::error_code ec;
    snap.exists = std::filesystem::exists(path, ec);
    if (!snap.exists || ec) {
        return snap;
    }
    snap.bytes = std::filesystem::file_size(path, ec);
    const auto ftime = std::filesystem::last_write_time(path, ec);
    if (!ec) {
        const auto system_time = std::chrono::time_point_cast<std::chrono::milliseconds>(
            ftime - std::filesystem::file_time_type::clock::now() + std::chrono::system_clock::now());
        snap.modified_epoch_ms = system_time.time_since_epoch().count();
        snap.age_seconds = static_cast<double>(now_epoch_ms() - snap.modified_epoch_ms) / 1000.0;
    }
    if (count_lines) {
        std::ifstream in(path);
        std::string line;
        while (std::getline(in, line)) {
            if (!line.empty()) {
                ++snap.line_count;
            }
        }
    }
    return snap;
}

std::vector<std::string> ServiceContext::read_tail_lines(const std::filesystem::path& path,
                                                         std::size_t max_lines,
                                                         std::size_t max_bytes) const {
    std::vector<std::string> rows;
    if (max_lines == 0) {
        return rows;
    }
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        return rows;
    }
    in.seekg(0, std::ios::end);
    const auto end = in.tellg();
    const auto size = end > 0 ? static_cast<std::uintmax_t>(end) : 0;
    const auto offset = size > max_bytes ? size - max_bytes : 0;
    in.seekg(static_cast<std::streamoff>(offset), std::ios::beg);
    std::string text((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    if (offset > 0) {
        const auto first_newline = text.find('\n');
        if (first_newline != std::string::npos) {
            text.erase(0, first_newline + 1);
        }
    }
    std::istringstream iss(text);
    std::string line;
    while (std::getline(iss, line)) {
        line = trim(line);
        if (!line.empty()) {
            rows.push_back(std::move(line));
        }
    }
    if (rows.size() > max_lines) {
        rows.erase(rows.begin(), rows.end() - static_cast<std::ptrdiff_t>(max_lines));
    }
    return rows;
}

std::string ServiceContext::read_text(const std::filesystem::path& path, std::size_t max_bytes) const {
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        return {};
    }
    std::string text((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    if (text.size() > max_bytes) {
        text.erase(0, text.size() - max_bytes);
    }
    return text;
}

void ServiceContext::write_status(std::string_view mode, bool ok, std::string_view message) const {
    const auto path = backendd_status_path();
    std::filesystem::create_directories(path.parent_path());
    std::ofstream out(path, std::ios::trunc);
    if (!out) {
        return;
    }
    out << "{"
        << "\"ok\":" << json_bool(ok)
        << ",\"mode\":" << json_quote(mode)
        << ",\"message\":" << json_quote(message)
        << ",\"generated_at\":" << json_quote(now_iso())
        << ",\"generated_at_ms\":" << now_epoch_ms()
        << ",\"root\":" << json_quote(root().string())
        << "}\n";
}

}  // namespace qt::backend
