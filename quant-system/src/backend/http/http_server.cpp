#include "qt/backend/http/http_server.hpp"

#include <arpa/inet.h>
#include <cerrno>
#include <cstring>
#include <iostream>
#include <netinet/in.h>
#include <sstream>
#include <sys/socket.h>
#include <unistd.h>

#include "qt/backend/common/json.hpp"

namespace qt::backend {

HttpServer::HttpServer(ServiceContext& context, RouteRegistry& routes)
    : context_(context), routes_(routes) {}

static void write_all(int fd, const std::string& payload) {
    const char* data = payload.data();
    std::size_t remaining = payload.size();
    while (remaining > 0) {
        const auto written = ::send(fd, data, remaining, 0);
        if (written <= 0) {
            return;
        }
        data += written;
        remaining -= static_cast<std::size_t>(written);
    }
}

static std::string http_response(int status, const std::string& body) {
    const char* status_text = status == 200 ? "OK" : "ERROR";
    std::ostringstream oss;
    oss << "HTTP/1.1 " << status << " " << status_text << "\r\n"
        << "Content-Type: application/json; charset=utf-8\r\n"
        << "Cache-Control: no-store\r\n"
        << "Content-Length: " << body.size() << "\r\n"
        << "Connection: close\r\n\r\n"
        << body;
    return oss.str();
}

int HttpServer::serve(const std::string& host, int port, std::atomic_bool& stop_requested) {
    const int server_fd = ::socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0) {
        std::cerr << "backendd socket failed: " << std::strerror(errno) << "\n";
        return 2;
    }
    int yes = 1;
    ::setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));

    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(static_cast<uint16_t>(port));
    if (::inet_pton(AF_INET, host.c_str(), &addr.sin_addr) != 1) {
        addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    }

    if (::bind(server_fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) < 0) {
        std::cerr << "backendd bind failed: " << std::strerror(errno) << "\n";
        ::close(server_fd);
        return 3;
    }
    if (::listen(server_fd, 64) < 0) {
        std::cerr << "backendd listen failed: " << std::strerror(errno) << "\n";
        ::close(server_fd);
        return 4;
    }

    context_.write_status("serve", true, "backendd HTTP server listening");
    std::cerr << "[backendd] listening on http://" << host << ":" << port << "\n";

    while (!stop_requested.load()) {
        sockaddr_in peer{};
        socklen_t peer_len = sizeof(peer);
        const int client_fd = ::accept(server_fd, reinterpret_cast<sockaddr*>(&peer), &peer_len);
        if (client_fd < 0) {
            if (errno == EINTR) {
                continue;
            }
            break;
        }
        char buffer[8192];
        const auto n = ::recv(client_fd, buffer, sizeof(buffer) - 1, 0);
        if (n <= 0) {
            ::close(client_fd);
            continue;
        }
        buffer[n] = '\0';
        std::istringstream request_stream{std::string(buffer)};
        std::string method;
        std::string target;
        std::string version;
        request_stream >> method >> target >> version;
        auto request = parse_route_request(method, target);
        std::string body;
        int status = 200;
        try {
            body = routes_.handle(context_, request);
            if (body.find("\"ok\":false") != std::string::npos && !routes_.contains(request.path)) {
                status = 404;
            }
        } catch (const std::exception& exc) {
            status = 500;
            body = "{\"ok\":false,\"service\":\"backendd\",\"error\":" + json_quote(exc.what()) + "}";
        }
        write_all(client_fd, http_response(status, body));
        ::close(client_fd);
    }

    context_.write_status("serve", false, "backendd HTTP server stopped");
    ::close(server_fd);
    return 0;
}

}  // namespace qt::backend
