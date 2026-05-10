#pragma once

#include <map>
#include <set>
#include <string>
#include <vector>

#include "qt/backend/api/route_registry.hpp"
#include "qt/backend/common/service_context.hpp"

namespace qt::backend {

int query_int(const Request& req, const std::string& key, int fallback, int lo, int hi);
int query_int_any(const Request& req,
                  const std::vector<std::string>& keys,
                  int fallback,
                  int lo,
                  int hi);
bool query_bool_any(const Request& req, const std::vector<std::string>& keys, bool fallback);

std::string file_snapshot_json(const FileSnapshot& snap);
std::string json_object_array_from_lines(const std::vector<std::string>& rows, std::size_t limit);
std::string int_map_json(const std::map<std::string, int>& counts);
std::string double_map_json(const std::map<std::string, double>& values);
std::string string_set_json(const std::set<std::string>& values);

}  // namespace qt::backend
