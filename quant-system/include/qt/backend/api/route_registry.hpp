#pragma once

#include <functional>
#include <map>
#include <string>
#include <unordered_map>

namespace qt::backend {

class ServiceContext;

struct Request {
    std::string method{"GET"};
    std::string path{"/api/backend/summary"};
    std::map<std::string, std::string> query;
};

using RouteHandler = std::function<std::string(ServiceContext&, const Request&)>;

class RouteRegistry {
public:
    void add(std::string path, RouteHandler handler);
    bool contains(const std::string& path) const;
    std::string handle(ServiceContext& context, const Request& request) const;

private:
    std::unordered_map<std::string, RouteHandler> handlers_;
};

Request parse_route_request(std::string method, std::string target);
void register_backend_routes(RouteRegistry& registry);

}  // namespace qt::backend
