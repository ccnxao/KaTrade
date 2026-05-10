#include "qt/history_client.hpp"

#include <algorithm>
#include <cerrno>
#include <chrono>
#include <cctype>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string_view>
#include <utility>

#include <netdb.h>
#include <sys/socket.h>
#include <unistd.h>

namespace qt {

namespace {

namespace fs = std::filesystem;

struct ParsedUrl {
    std::string host;
    std::string port{"80"};
    std::string base_path;
};

std::string trim_right_slash(std::string value) {
    while (!value.empty() && value.back() == '/') {
        value.pop_back();
    }
    return value;
}

ParsedUrl parse_http_url(const std::string& url) {
    constexpr std::string_view prefix = "http://";
    if (!url.starts_with(prefix)) {
        throw std::runtime_error("history.server_url currently supports http:// only: " + url);
    }

    const auto without_scheme = url.substr(prefix.size());
    const auto path_pos = without_scheme.find('/');
    const auto host_port = without_scheme.substr(0, path_pos);
    ParsedUrl parsed;
    parsed.base_path = path_pos == std::string::npos ? "" : without_scheme.substr(path_pos);

    const auto colon = host_port.rfind(':');
    if (colon == std::string::npos) {
        parsed.host = host_port;
    } else {
        parsed.host = host_port.substr(0, colon);
        parsed.port = host_port.substr(colon + 1);
    }
    if (parsed.host.empty()) {
        throw std::runtime_error("invalid history.server_url: " + url);
    }
    return parsed;
}

std::string sanitize_component(const std::string& value) {
    std::string out;
    out.reserve(value.size());
    for (const unsigned char ch : value) {
        if (std::isalnum(ch) || ch == '-' || ch == '_') {
            out.push_back(static_cast<char>(ch));
        } else {
            out.push_back('_');
        }
    }
    return out.empty() ? "default" : out;
}

std::string url_encode(const std::string& value) {
    std::ostringstream out;
    out << std::uppercase << std::hex;
    for (const unsigned char ch : value) {
        if (std::isalnum(ch) || ch == '-' || ch == '_' || ch == '.' || ch == '~') {
            out << static_cast<char>(ch);
        } else {
            out << '%' << std::setw(2) << std::setfill('0') << static_cast<int>(ch);
        }
    }
    return out.str();
}

fs::path cache_root(const std::string& cache_dir, const std::string& server_url) {
    return fs::path(cache_dir) / sanitize_component(trim_right_slash(server_url));
}

fs::path cache_path_for_contract(const std::string& cache_dir,
                                 const std::string& server_url,
                                 const std::string& contract,
                                 const std::string& cache_scope) {
    return cache_root(cache_dir, server_url) /
           (sanitize_component(contract + "_" + cache_scope) + ".csv");
}

bool is_cache_fresh(const fs::path& path, int ttl_seconds) {
    if (!fs::exists(path) || ttl_seconds <= 0) {
        return false;
    }
    const auto now = fs::file_time_type::clock::now();
    const auto last_used = fs::last_write_time(path);
    return now - last_used <= std::chrono::seconds(ttl_seconds);
}

void touch_cache_file(const fs::path& path) {
    fs::last_write_time(path, fs::file_time_type::clock::now());
}

int cleanup_expired_cache(const fs::path& root, int ttl_seconds) {
    if (!fs::exists(root)) {
        return 0;
    }
    int deleted = 0;
    const auto now = fs::file_time_type::clock::now();
    for (const auto& entry : fs::directory_iterator(root)) {
        if (!entry.is_regular_file() || entry.path().extension() != ".csv") {
            continue;
        }
        const bool expired =
            ttl_seconds <= 0 ||
            now - fs::last_write_time(entry.path()) > std::chrono::seconds(ttl_seconds);
        if (expired) {
            fs::remove(entry.path());
            ++deleted;
        }
    }
    return deleted;
}

void send_all(int socket_fd, std::string_view bytes) {
    const char* data = bytes.data();
    std::size_t remaining = bytes.size();
    while (remaining > 0) {
        const auto sent = ::send(socket_fd, data, remaining, 0);
        if (sent < 0) {
            throw std::runtime_error("history http send failed: " + std::string(std::strerror(errno)));
        }
        data += sent;
        remaining -= static_cast<std::size_t>(sent);
    }
}

std::string http_get(const std::string& server_url, const std::string& target) {
    const ParsedUrl url = parse_http_url(server_url);

    addrinfo hints{};
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;

    addrinfo* results = nullptr;
    const int gai = ::getaddrinfo(url.host.c_str(), url.port.c_str(), &hints, &results);
    if (gai != 0) {
        throw std::runtime_error("history http DNS failed: " + std::string(::gai_strerror(gai)));
    }

    int socket_fd = -1;
    for (addrinfo* item = results; item != nullptr; item = item->ai_next) {
        socket_fd = ::socket(item->ai_family, item->ai_socktype, item->ai_protocol);
        if (socket_fd < 0) {
            continue;
        }
        if (::connect(socket_fd, item->ai_addr, item->ai_addrlen) == 0) {
            break;
        }
        ::close(socket_fd);
        socket_fd = -1;
    }
    ::freeaddrinfo(results);
    if (socket_fd < 0) {
        throw std::runtime_error("history http connect failed: " + server_url);
    }

    const std::string path =
        (url.base_path.empty() ? "" : trim_right_slash(url.base_path)) + target;
    const std::string request =
        "GET " + path + " HTTP/1.0\r\n"
        "Host: " + url.host + "\r\n"
        "User-Agent: KaTradeHistoryClient/0.1\r\n"
        "Connection: close\r\n\r\n";
    send_all(socket_fd, request);

    std::string response;
    char buffer[4096];
    while (true) {
        const auto received = ::recv(socket_fd, buffer, sizeof(buffer), 0);
        if (received < 0) {
            ::close(socket_fd);
            throw std::runtime_error("history http recv failed: " + std::string(std::strerror(errno)));
        }
        if (received == 0) {
            break;
        }
        response.append(buffer, static_cast<std::size_t>(received));
    }
    ::close(socket_fd);

    const auto header_end = response.find("\r\n\r\n");
    if (header_end == std::string::npos) {
        throw std::runtime_error("history http response missing headers");
    }
    const auto status_end = response.find("\r\n");
    const std::string status = response.substr(0, status_end);
    if (status.find(" 200 ") == std::string::npos) {
        const std::string body = response.substr(header_end + 4);
        throw std::runtime_error("history http request failed: " + status + " " + body);
    }
    return response.substr(header_end + 4);
}

void write_text_atomic(const fs::path& path, const std::string& content) {
    fs::create_directories(path.parent_path());
    const fs::path temp = path.string() + ".tmp";
    {
        std::ofstream output(temp, std::ios::binary);
        if (!output.is_open()) {
            throw std::runtime_error("failed to open cache temp file: " + temp.string());
        }
        output << content;
    }
    fs::rename(temp, path);
    touch_cache_file(path);
}

bool csv_has_data_rows(const std::string& csv) {
    const auto first_newline = csv.find('\n');
    return first_newline != std::string::npos && first_newline + 1 < csv.size();
}

}  // namespace

HistoryDataClient::HistoryDataClient(std::string server_url,
                                     std::string cache_dir,
                                     int cache_ttl_seconds,
                                     std::string bar,
                                     std::string start,
                                     std::string end,
                                     int max_pages)
    : server_url_(trim_right_slash(std::move(server_url))),
      cache_dir_(std::move(cache_dir)),
      cache_ttl_seconds_(cache_ttl_seconds),
      bar_(std::move(bar)),
      start_(std::move(start)),
      end_(std::move(end)),
      max_pages_(max_pages) {}

HistoryCacheResult HistoryDataClient::ensure_contracts_cached(
    const std::vector<std::string>& contracts) {
    if (contracts.empty()) {
        throw std::runtime_error("history.contracts is required when history.mode=remote");
    }

    HistoryCacheResult result;
    const fs::path root = cache_root(cache_dir_, server_url_);
    fs::create_directories(root);
    result.deleted_expired = cleanup_expired_cache(root, cache_ttl_seconds_);

    std::string query_suffix;
    std::string cache_scope = bar_.empty() ? "default" : bar_;
    if (!bar_.empty()) {
        query_suffix += "&bar=" + url_encode(bar_);
    }
    if (!start_.empty()) {
        query_suffix += "&start=" + url_encode(start_);
        cache_scope += "_start_" + start_;
    }
    if (!end_.empty()) {
        query_suffix += "&end=" + url_encode(end_);
        cache_scope += "_end_" + end_;
    }
    if (max_pages_ > 0) {
        query_suffix += "&max_pages=" + std::to_string(max_pages_);
        cache_scope += "_pages_" + std::to_string(max_pages_);
    }

    for (const auto& contract : contracts) {
        const fs::path path = cache_path_for_contract(cache_dir_, server_url_, contract, cache_scope);
        if (is_cache_fresh(path, cache_ttl_seconds_)) {
            touch_cache_file(path);
            result.cached_paths.push_back(path.string());
            ++result.cache_hits;
            continue;
        }

        const std::string target = "/api/bars.csv?contract=" + url_encode(contract) + query_suffix;
        const std::string csv = http_get(server_url_, target);
        if (!csv_has_data_rows(csv)) {
            throw std::runtime_error("history server returned no rows for contract: " + contract);
        }
        write_text_atomic(path, csv);
        result.cached_paths.push_back(path.string());
        ++result.fetched;
    }
    return result;
}

}  // namespace qt
