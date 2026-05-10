#pragma once

#include <string>
#include <unordered_map>
#include <vector>

namespace qt::storage {

// ---- 持久化存储 (GAP-036) ---------------------------------------------
// 提供以下能力:
//   1. 原子文件写入 (write to .tmp + fsync + rename)
//   2. 带 schema version 的 JSONL 追加/读取
//   3. 简单 key-value 持久化（用于 config 等）
//   4. 数据完整性校验（行数 + checksum）
// ----------------------------------------------------------------------

class PersistentStore {
public:
    // ---- 原子写入 ----
    // 将 content 原子写入 path: 先写 .tmp，fsync，再 rename
    // 返回 true 表示写入成功
    static bool atomic_write(const std::string& path, const std::string& content);

    // ---- Schema-versioned JSONL ----
    // 追加一行 JSON（自动加 schema version header）
    // 格式: {"_schema":"v1","_ts":1234567890,...actual data...}
    static bool append_jsonl(const std::string& path,
                              const std::string& schema_version,
                              const std::string& json_line);

    // 读取所有行，返回 JSON 字符串列表
    // min_schema_version: 只返回 >= 此版本的行（空=全部）
    static std::vector<std::string> read_jsonl(
        const std::string& path,
        const std::string& min_schema_version = "");

    // 统计文件信息
    struct FileStats {
        std::size_t line_count{0};
        std::string schema_version;
        std::size_t file_size_bytes{0};
        bool valid{false};
    };
    static FileStats jsonl_stats(const std::string& path);

    // ---- Key-Value 持久化（用于 config）----
    // 原子保存 key-value 对到 .cfg 文件
    static bool save_config(const std::string& path,
                            const std::unordered_map<std::string, std::string>& kv,
                            const std::string& header_comment = "");

    // ---- 文件校验 ----
    // 计算文件的简单 checksum (XOR + 长度)
    static std::string checksum(const std::string& path);
    static bool verify_checksum(const std::string& path,
                                 const std::string& expected_checksum);

private:
    // 比较 schema version 字符串 (如 "v1" < "v2")
    static int compare_versions(const std::string& a, const std::string& b);
};

}  // namespace qt::storage
