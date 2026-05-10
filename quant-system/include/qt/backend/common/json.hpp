#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace qt::backend {

std::string trim(std::string_view value);
std::string json_escape(std::string_view value);
std::string json_quote(std::string_view value);
std::string json_bool(bool value);
std::string json_int(std::int64_t value);
std::string json_double(double value);
bool looks_like_json_object(std::string_view value);

std::optional<std::string> json_get_string(std::string_view object, std::string_view key);
std::optional<double> json_get_double(std::string_view object, std::string_view key);
std::optional<std::int64_t> json_get_int(std::string_view object, std::string_view key);
std::optional<bool> json_get_bool(std::string_view object, std::string_view key);
std::optional<std::string> json_get_raw_value(std::string_view object, std::string_view key);
std::vector<std::string> json_array_objects(std::string_view raw_array);
std::vector<std::string> json_array_strings(std::string_view raw_array);

}  // namespace qt::backend
