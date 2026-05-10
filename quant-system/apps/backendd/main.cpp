#include <atomic>
#include <csignal>
#include <cstdlib>
#include <iostream>
#include <string>

#include "qt/backend/http/http_server.hpp"
#include "qt/backend/common/json.hpp"
#include "qt/backend/api/route_registry.hpp"
#include "qt/backend/common/service_context.hpp"

namespace {

std::atomic_bool g_stop_requested{false};

void handle_signal(int) {
    g_stop_requested.store(true);
}

qt::backend::BackendConfig parse_args(int argc, char** argv) {
    qt::backend::BackendConfig config;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "serve" || arg == "--serve") {
            config.serve = true;
        } else if (arg == "--root" && i + 1 < argc) {
            config.root = argv[++i];
        } else if (arg == "--config" && i + 1 < argc) {
            config.config_path = argv[++i];
        } else if (arg == "--method" && i + 1 < argc) {
            config.method = argv[++i];
        } else if (arg == "--route" && i + 1 < argc) {
            config.route = argv[++i];
        } else if (arg == "--host" && i + 1 < argc) {
            config.host = argv[++i];
        } else if (arg == "--port" && i + 1 < argc) {
            config.port = std::atoi(argv[++i]);
        }
    }
    if (config.port <= 0) {
        config.port = 8791;
    }
    return config;
}

}  // namespace

int main(int argc, char** argv) {
    std::signal(SIGINT, handle_signal);
    std::signal(SIGTERM, handle_signal);

    auto config = parse_args(argc, argv);
    qt::backend::ServiceContext context(config);
    qt::backend::RouteRegistry routes;
    qt::backend::register_backend_routes(routes);

    if (config.serve) {
        qt::backend::HttpServer server(context, routes);
        return server.serve(config.host, config.port, g_stop_requested);
    }

    const auto request = qt::backend::parse_route_request(config.method, config.route);
    try {
        context.write_status("route", true, "backendd one-shot route handled");
        std::cout << routes.handle(context, request) << "\n";
        return routes.contains(request.path) ? 0 : 1;
    } catch (const std::exception& exc) {
        std::cout << "{\"ok\":false,\"service\":\"backendd\",\"error\":"
                  << qt::backend::json_quote(exc.what()) << "}\n";
        return 2;
    }
}
