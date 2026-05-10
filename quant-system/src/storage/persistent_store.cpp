#include "qt/storage/persistent_store.hpp"

#include <chrono>
#include <cstdint>
#include <mutex>
#include <cstdio>
#include <fstream>
#include <sstream>
#include <sys/stat.h>
#include <unistd.h>

namespace qt::storage {

// ---- 原子写入 --------------------------------------------------------

bool PersistentStore::atomic_write(const std::string& path,
                                    const std::string& content) {
    std::string tmp_path = path + ".tmp";

    // 1. 写入临时文件
    {
        std::ofstream out(tmp_path, std::ios::trunc);
        if (!out) return false;
        out << content;
        if (!out) return false;
        out.close();
    }

    // 2. fsync 临时文件 (R37: 防御性检查避免空指针)
    {
        FILE* fp = std::fopen(tmp_path.c_str(), "rb+");
        if (fp != nullptr) {
            fsync(fileno(fp));
            std::fclose(fp);
        }
    }

    // 3. 原子 rename
    if (std::rename(tmp_path.c_str(), path.c_str()) != 0) {
        // rename 失败，尝试清理临时文件
        std::remove(tmp_path.c_str());
        return false;
    }

    return true;
}

// ---- Schema-versioned JSONL ------------------------------------------

bool PersistentStore::append_jsonl(const std::string& path,
                                    const std::string& schema_version,
                                    const std::string& json_line) {
    std::ofstream out(path, std::ios::app);
    if (!out) return false;

    // 获取当前时间戳
    auto now_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();

    // 注入 schema 和 timestamp
    // 原始 json_line 应该是 {"key":"value",...}
    // 我们改为 {"_schema":"v1","_ts":123,...original...}
    // 简单 JSON 字符串转义：替换 \ " 和换行
    auto esc_json_str = [](const std::string& s) -> std::string {
        std::string o; o.reserve(s.size());
        for (char ch : s) {
            if (ch == '\\') o += "\\\\";
            else if (ch == '"') o += "\\\"";
            else if (ch == '\n') o += "\\n";
            else if (ch == '\r') o += "\\r";
            else if (ch == '\t') o += "\\t";
            else o += ch;
        }
        return o;
    };
    if (json_line.size() > 2 && json_line[0] == '{') {
        out << "{\"_schema\":\"" << esc_json_str(schema_version)
            << "\",\"_ts\":" << now_ms << ","
            << json_line.substr(1) << "\n";
    } else {
        out << "{\"_schema\":\"" << esc_json_str(schema_version)
            << "\",\"_ts\":" << now_ms
            << ",\"raw\":\"" << esc_json_str(json_line) << "\"}\n";
    }

    return bool(out);
}

std::vector<std::string> PersistentStore::read_jsonl(
    const std::string& path,
    const std::string& min_schema_version) {

    std::vector<std::string> result;
    std::ifstream in(path);
    if (!in) return result;

    std::string line;
    while (std::getline(in, line)) {
        if (line.empty()) continue;

        if (!min_schema_version.empty()) {
            // 提取 _schema 字段
            auto pos = line.find("\"_schema\":\"");
            if (pos != std::string::npos) {
                pos += 11;  // len("_schema":"")
                auto end = line.find('"', pos);
                if (end != std::string::npos) {
                    std::string ver = line.substr(pos, end - pos);
                    if (compare_versions(ver, min_schema_version) < 0) {
                        continue;  // 版本太旧，跳过
                    }
                }
            }
        }
        result.push_back(std::move(line));
    }

    return result;
}

PersistentStore::FileStats PersistentStore::jsonl_stats(const std::string& path) {
    FileStats stats;
    std::ifstream in(path);
    if (!in) return stats;

    // 获取文件大小
    struct stat st{};
    if (::stat(path.c_str(), &st) == 0) {
        stats.file_size_bytes = static_cast<std::size_t>(st.st_size);
    }

    std::string line;
    while (std::getline(in, line)) {
        if (line.empty()) continue;
        stats.line_count++;

        // 取第一行的 schema version
        if (stats.schema_version.empty()) {
            auto pos = line.find("\"_schema\":\"");
            if (pos != std::string::npos) {
                pos += 11;
                auto end = line.find('"', pos);
                if (end != std::string::npos) {
                    stats.schema_version = line.substr(pos, end - pos);
                }
            }
        }
    }

    stats.valid = stats.line_count > 0;
    return stats;
}

// ---- Key-Value Config -------------------------------------------------

bool PersistentStore::save_config(
    const std::string& path,
    const std::unordered_map<std::string, std::string>& kv,
    const std::string& header_comment) {

    std::ostringstream oss;
    if (!header_comment.empty()) {
        oss << "# " << header_comment << "\n";
    }
    for (const auto& [key, value] : kv) {
        oss << key << "=" << value << "\n";
    }

    return atomic_write(path, oss.str());
}

// ---- 文件校验 --------------------------------------------------------

// R38: CRC32 替代 XOR checksum
static uint32_t crc32_table[256];
static std::once_flag crc32_init_flag;
static void init_crc32() {
    for (uint32_t i = 0; i < 256; i++) {
        uint32_t crc = i;
        for (int j = 0; j < 8; j++)
            crc = (crc >> 1) ^ ((crc & 1) ? 0xEDB88320 : 0);
        crc32_table[i] = crc;
    }
}

std::string PersistentStore::checksum(const std::string& path) {
    std::call_once(crc32_init_flag, init_crc32);
    std::ifstream in(path, std::ios::binary);
    if (!in) return "";

    uint32_t crc = 0xFFFFFFFF;
    std::size_t length = 0;
    char ch;
    while (in.get(ch)) {
        crc = crc32_table[(crc ^ static_cast<unsigned char>(ch)) & 0xFF] ^ (crc >> 8);
        length++;
    }
    crc ^= 0xFFFFFFFF;

    std::ostringstream oss;
    oss << std::hex << crc << ":" << length;
    return oss.str();
}

bool PersistentStore::verify_checksum(const std::string& path,
                                       const std::string& expected) {
    return checksum(path) == expected;
}

// ---- 内部工具 --------------------------------------------------------

int PersistentStore::compare_versions(const std::string& a,
                                       const std::string& b) {
    // 简单比较: 去掉 'v' 前缀后按整数比较
    auto parse_ver = [](const std::string& v) -> int {
        std::string num = v;
        if (!num.empty() && (num[0] == 'v' || num[0] == 'V')) {
            num = num.substr(1);
        }
        try { return std::stoi(num); } catch (...) { return 0; }
    };
    return parse_ver(a) - parse_ver(b);
}

}  // namespace qt::storage
