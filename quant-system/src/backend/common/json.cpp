#include "qt/backend/common/json.hpp"

#include <charconv>
#include <cmath>
#include <cstdlib>
#include <iomanip>
#include <sstream>

namespace qt::backend {

std::string trim(std::string_view value) {
    std::size_t begin = 0;
    while (begin < value.size() && static_cast<unsigned char>(value[begin]) <= ' ') {
        ++begin;
    }
    std::size_t end = value.size();
    while (end > begin && static_cast<unsigned char>(value[end - 1]) <= ' ') {
        --end;
    }
    return std::string(value.substr(begin, end - begin));
}

std::string json_escape(std::string_view value) {
    std::string out;
    out.reserve(value.size() + 8);
    for (char ch : value) {
        switch (ch) {
            case '\\': out += "\\\\"; break;
            case '"': out += "\\\""; break;
            case '\b': out += "\\b"; break;
            case '\f': out += "\\f"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
                if (static_cast<unsigned char>(ch) < 0x20) {
                    std::ostringstream oss;
                    oss << "\\u" << std::hex << std::setw(4) << std::setfill('0')
                        << static_cast<int>(static_cast<unsigned char>(ch));
                    out += oss.str();
                } else {
                    out.push_back(ch);
                }
        }
    }
    return out;
}

std::string json_quote(std::string_view value) {
    return "\"" + json_escape(value) + "\"";
}

std::string json_bool(bool value) {
    return value ? "true" : "false";
}

std::string json_int(std::int64_t value) {
    return std::to_string(value);
}

std::string json_double(double value) {
    if (!std::isfinite(value)) {
        return "0";
    }
    std::ostringstream oss;
    oss << std::setprecision(12) << value;
    return oss.str();
}

bool looks_like_json_object(std::string_view value) {
    const auto text = trim(value);
    return text.size() >= 2 && text.front() == '{' && text.back() == '}';
}

static std::size_t find_key(std::string_view object, std::string_view key) {
    const std::string needle = "\"" + std::string(key) + "\"";
    auto pos = object.find(needle);
    while (pos != std::string_view::npos) {
        auto cursor = pos + needle.size();
        while (cursor < object.size() && static_cast<unsigned char>(object[cursor]) <= ' ') {
            ++cursor;
        }
        if (cursor < object.size() && object[cursor] == ':') {
            return cursor + 1;
        }
        pos = object.find(needle, pos + 1);
    }
    return std::string_view::npos;
}

static std::optional<std::string> parse_json_string_at(std::string_view object, std::size_t pos) {
    while (pos < object.size() && static_cast<unsigned char>(object[pos]) <= ' ') {
        ++pos;
    }
    if (pos >= object.size() || object[pos] != '"') {
        return std::nullopt;
    }
    ++pos;
    std::string out;
    while (pos < object.size()) {
        const char ch = object[pos++];
        if (ch == '"') {
            return out;
        }
        if (ch == '\\' && pos < object.size()) {
            const char esc = object[pos++];
            switch (esc) {
                case '"': out.push_back('"'); break;
                case '\\': out.push_back('\\'); break;
                case '/': out.push_back('/'); break;
                case 'b': out.push_back('\b'); break;
                case 'f': out.push_back('\f'); break;
                case 'n': out.push_back('\n'); break;
                case 'r': out.push_back('\r'); break;
                case 't': out.push_back('\t'); break;
                default: out.push_back(esc); break;
            }
        } else {
            out.push_back(ch);
        }
    }
    return std::nullopt;
}

std::optional<std::string> json_get_string(std::string_view object, std::string_view key) {
    const auto pos = find_key(object, key);
    if (pos == std::string_view::npos) {
        return std::nullopt;
    }
    return parse_json_string_at(object, pos);
}

static std::string scalar_at(std::string_view object, std::size_t pos) {
    while (pos < object.size() && static_cast<unsigned char>(object[pos]) <= ' ') {
        ++pos;
    }
    const auto begin = pos;
    while (pos < object.size()) {
        const char ch = object[pos];
        if (ch == ',' || ch == '}' || ch == ']' || static_cast<unsigned char>(ch) <= ' ') {
            break;
        }
        ++pos;
    }
    return std::string(object.substr(begin, pos - begin));
}

std::optional<double> json_get_double(std::string_view object, std::string_view key) {
    const auto pos = find_key(object, key);
    if (pos == std::string_view::npos) {
        return std::nullopt;
    }
    const auto scalar = scalar_at(object, pos);
    if (scalar.empty() || scalar == "null") {
        return std::nullopt;
    }
    char* end = nullptr;
    const double value = std::strtod(scalar.c_str(), &end);
    if (end == scalar.c_str()) {
        return std::nullopt;
    }
    return value;
}

std::optional<std::int64_t> json_get_int(std::string_view object, std::string_view key) {
    const auto value = json_get_double(object, key);
    if (!value) {
        return std::nullopt;
    }
    return static_cast<std::int64_t>(*value);
}

std::optional<bool> json_get_bool(std::string_view object, std::string_view key) {
    const auto pos = find_key(object, key);
    if (pos == std::string_view::npos) {
        return std::nullopt;
    }
    const auto scalar = scalar_at(object, pos);
    if (scalar == "true") {
        return true;
    }
    if (scalar == "false") {
        return false;
    }
    return std::nullopt;
}

static std::size_t find_json_value_start(std::string_view object, std::string_view key) {
    const std::string needle = "\"" + std::string(key) + "\"";
    auto pos = object.find(needle);
    while (pos != std::string_view::npos) {
        auto cursor = pos + needle.size();
        while (cursor < object.size() && static_cast<unsigned char>(object[cursor]) <= ' ') {
            ++cursor;
        }
        if (cursor < object.size() && object[cursor] == ':') {
            ++cursor;
            while (cursor < object.size() && static_cast<unsigned char>(object[cursor]) <= ' ') {
                ++cursor;
            }
            return cursor;
        }
        pos = object.find(needle, pos + 1);
    }
    return std::string_view::npos;
}

std::optional<std::string> json_get_raw_value(std::string_view object, std::string_view key) {
    const auto start = find_json_value_start(object, key);
    if (start == std::string_view::npos || start >= object.size()) {
        return std::nullopt;
    }
    std::size_t cursor = start;
    int depth = 0;
    bool in_string = false;
    bool escaped = false;
    while (cursor < object.size()) {
        const char ch = object[cursor];
        if (in_string) {
            if (escaped) {
                escaped = false;
            } else if (ch == '\\') {
                escaped = true;
            } else if (ch == '"') {
                in_string = false;
                if (depth == 0) {
                    ++cursor;
                    break;
                }
            }
            ++cursor;
            continue;
        }
        if (ch == '"') {
            in_string = true;
            ++cursor;
            continue;
        }
        if (ch == '[' || ch == '{') {
            ++depth;
        } else if (ch == ']' || ch == '}') {
            if (depth == 0) {
                break;
            }
            --depth;
            if (depth == 0) {
                ++cursor;
                break;
            }
        } else if ((ch == ',' || static_cast<unsigned char>(ch) <= ' ') && depth == 0) {
            break;
        }
        ++cursor;
    }
    return trim(object.substr(start, cursor - start));
}

std::vector<std::string> json_array_objects(std::string_view raw_array) {
    std::vector<std::string> out;
    const auto text = trim(raw_array);
    if (text.size() < 2 || text.front() != '[' || text.back() != ']') {
        return out;
    }
    bool in_string = false;
    bool escaped = false;
    int depth = 0;
    std::size_t begin = std::string_view::npos;
    for (std::size_t i = 0; i < text.size(); ++i) {
        const char ch = text[i];
        if (in_string) {
            if (escaped) {
                escaped = false;
            } else if (ch == '\\') {
                escaped = true;
            } else if (ch == '"') {
                in_string = false;
            }
            continue;
        }
        if (ch == '"') {
            in_string = true;
            continue;
        }
        if (ch == '{') {
            if (depth == 0) {
                begin = i;
            }
            ++depth;
        } else if (ch == '}' && depth > 0) {
            --depth;
            if (depth == 0 && begin != std::string_view::npos) {
                out.emplace_back(text.substr(begin, i - begin + 1));
                begin = std::string_view::npos;
            }
        }
    }
    return out;
}

std::vector<std::string> json_array_strings(std::string_view raw_array) {
    std::vector<std::string> out;
    const auto text = trim(raw_array);
    if (text.size() < 2 || text.front() != '[' || text.back() != ']') {
        return out;
    }
    for (std::size_t i = 1; i + 1 < text.size(); ++i) {
        if (text[i] != '"') {
            continue;
        }
        std::string value;
        bool escaped = false;
        ++i;
        for (; i + 1 < text.size(); ++i) {
            const char ch = text[i];
            if (escaped) {
                value.push_back(ch);
                escaped = false;
            } else if (ch == '\\') {
                escaped = true;
            } else if (ch == '"') {
                out.push_back(value);
                break;
            } else {
                value.push_back(ch);
            }
        }
    }
    return out;
}

}  // namespace qt::backend
