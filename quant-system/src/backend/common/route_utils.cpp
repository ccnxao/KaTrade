#include "qt/backend/common/route_utils.hpp"

#include <algorithm>
#include <cctype>
#include <sstream>

#include "qt/backend/common/json.hpp"

namespace qt::backend {

int query_int(const Request& req, const std::string& key, int fallback, int lo, int hi) {
    auto it = req.query.find(key);
    if (it == req.query.end()) {
        return fallback;
    }
    try {
        return std::clamp(std::stoi(it->second), lo, hi);
    } catch (...) {
        return fallback;
    }
}

int query_int_any(const Request& req,
                  const std::vector<std::string>& keys,
                  int fallback,
                  int lo,
                  int hi) {
    for (const auto& key : keys) {
        if (req.query.find(key) == req.query.end()) {
            continue;
        }
        return query_int(req, key, fallback, lo, hi);
    }
    return fallback;
}

static bool parse_bool_text(std::string value, bool fallback) {
    value = std::string(trim(value));
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    if (value == "1" || value == "true" || value == "yes" || value == "on") {
        return true;
    }
    if (value == "0" || value == "false" || value == "no" || value == "off") {
        return false;
    }
    return fallback;
}

bool query_bool_any(const Request& req, const std::vector<std::string>& keys, bool fallback) {
    for (const auto& key : keys) {
        const auto it = req.query.find(key);
        if (it != req.query.end()) {
            return parse_bool_text(it->second, fallback);
        }
    }
    return fallback;
}

std::string file_snapshot_json(const FileSnapshot& snap) {
    return "{"
           "\"path\":" + json_quote(snap.path) + ","
           "\"exists\":" + json_bool(snap.exists) + ","
           "\"bytes\":" + std::to_string(snap.bytes) + ","
           "\"modified_epoch_ms\":" + std::to_string(snap.modified_epoch_ms) + ","
           "\"age_seconds\":" + json_double(snap.age_seconds) + ","
           "\"line_count\":" + std::to_string(snap.line_count) +
           "}";
}

std::string json_object_array_from_lines(const std::vector<std::string>& rows, std::size_t limit) {
    std::ostringstream oss;
    oss << "[";
    bool first = true;
    const std::size_t begin = rows.size() > limit ? rows.size() - limit : 0;
    for (std::size_t i = begin; i < rows.size(); ++i) {
        if (!looks_like_json_object(rows[i])) {
            continue;
        }
        if (!first) {
            oss << ",";
        }
        first = false;
        oss << rows[i];
    }
    oss << "]";
    return oss.str();
}

std::string int_map_json(const std::map<std::string, int>& counts) {
    std::ostringstream oss;
    oss << "{";
    bool first = true;
    for (const auto& [key, value] : counts) {
        if (!first) {
            oss << ",";
        }
        first = false;
        oss << json_quote(key) << ":" << value;
    }
    oss << "}";
    return oss.str();
}

std::string double_map_json(const std::map<std::string, double>& values) {
    std::ostringstream oss;
    oss << "{";
    bool first = true;
    for (const auto& [key, value] : values) {
        if (!first) {
            oss << ",";
        }
        first = false;
        oss << json_quote(key) << ":" << json_double(value);
    }
    oss << "}";
    return oss.str();
}

std::string string_set_json(const std::set<std::string>& values) {
    std::ostringstream oss;
    oss << "[";
    bool first = true;
    for (const auto& value : values) {
        if (!first) {
            oss << ",";
        }
        first = false;
        oss << json_quote(value);
    }
    oss << "]";
    return oss.str();
}

}  // namespace qt::backend
