#pragma once

#include <string>
#include <vector>

namespace qt {

struct HistoryCacheResult {
    std::vector<std::string> cached_paths;
    int cache_hits{};
    int fetched{};
    int deleted_expired{};
};

class HistoryDataClient {
public:
    HistoryDataClient(std::string server_url,
                      std::string cache_dir,
                      int cache_ttl_seconds);

    // 确保每个合约都有可用的本地临时 CSV。
    // 远端服务仍是唯一数据源；本地文件只是短期缓存，方便回测内核复用 CsvReplayLoader。
    HistoryCacheResult ensure_contracts_cached(const std::vector<std::string>& contracts);

private:
    std::string server_url_;
    std::string cache_dir_;
    int cache_ttl_seconds_;
};

}  // namespace qt
