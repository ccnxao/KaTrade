#pragma once

#include <atomic>
#include <string>

#include "qt/backend/api/route_registry.hpp"
#include "qt/backend/common/service_context.hpp"

namespace qt::backend {

class HttpServer {
public:
    HttpServer(ServiceContext& context, RouteRegistry& routes);
    int serve(const std::string& host, int port, std::atomic_bool& stop_requested);

private:
    ServiceContext& context_;
    RouteRegistry& routes_;
};

}  // namespace qt::backend
