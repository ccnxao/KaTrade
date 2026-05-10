cmake_minimum_required(VERSION 3.21)
project(KaTrade VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(BUILD_TESTS "Build unit and integration tests" ON)
option(BUILD_APPS  "Build application binaries" ON)
option(ENABLE_SANITIZERS "Enable sanitizers" OFF)

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang|AppleClang")
    add_compile_options(-Wall -Wextra -Wpedantic)
    if(ENABLE_SANITIZERS)
        add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer)
        add_link_options(-fsanitize=address,undefined)
    endif()
endif()

# R32: 只引用实际存在的源文件
add_library(qt_core INTERFACE)
target_include_directories(qt_core INTERFACE ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_features(qt_core INTERFACE cxx_std_20)

set(QT_SOURCES
    src/agent/agent_capital.cpp
    src/agent/llm_feature_agent.cpp
    src/agent/meta_agent.cpp
    src/agent/regime_agent.cpp
    src/agent/agents.cpp
    src/analysis/attribution.cpp
    src/backtest/backtest_engine.cpp
    src/data/calendar.cpp
    src/data/feature_store.cpp
    src/data/instrument_master.cpp
    src/execution/execution.cpp
    src/data/history_client.cpp
    src/execution/oms.cpp
    src/portfolio/portfolio.cpp
    src/portfolio/portfolio_book.cpp
    src/pricing/pricing.cpp
    src/data/replay_data.cpp
    src/reporting/report_io.cpp
    src/risk/risk.cpp
    src/risk/compliance.cpp
    src/risk/risk_budget.cpp
    src/risk/stress_test.cpp
    src/config/runtime_config.cpp
    src/storage/persistent_store.cpp
    src/strategies/factory.cpp
    src/strategies/mean_reversion.cpp
    src/strategies/trend.cpp
    src/engine/trader_engine.cpp
)

add_library(qt_engine STATIC ${QT_SOURCES})
target_include_directories(qt_engine PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(qt_engine PUBLIC qt_core)

if(BUILD_APPS)
    add_executable(realtime_engine apps/realtime_engine/main.cpp)
    target_link_libraries(realtime_engine PRIVATE qt_engine)

    add_executable(backendd
        apps/backendd/main.cpp
        src/backend/account/account_routes.cpp
        src/backend/account/account_read_model.cpp
        src/backend/common/json.cpp
        src/backend/order/order_maintenance.cpp
        src/backend/order/order_read_model.cpp
        src/backend/common/route_utils.cpp
        src/backend/common/service_context.cpp
        src/backend/api/route_registry.cpp
        src/backend/http/http_server.cpp
    )
    target_link_libraries(backendd PRIVATE qt_core)
endif()

if(BUILD_TESTS)
    enable_testing()

    add_executable(order_maintenance_check
        apps/order_maintenance_check/main.cpp
        src/backend/order/order_maintenance.cpp
    )
    target_link_libraries(order_maintenance_check PRIVATE qt_core)
    add_test(NAME order_maintenance_check COMMAND order_maintenance_check)

    add_executable(account_read_model_check
        apps/account_read_model_check/main.cpp
        src/backend/account/account_read_model.cpp
        src/backend/common/json.cpp
        src/backend/common/service_context.cpp
    )
    target_link_libraries(account_read_model_check PRIVATE qt_core)
    add_test(NAME account_read_model_check COMMAND account_read_model_check)

    find_package(GTest QUIET)
    if(GTest_FOUND)
        include(GoogleTest)
        add_subdirectory(tests)
    else()
        message(STATUS "GTest not found; unit tests disabled.")
    endif()
endif()
