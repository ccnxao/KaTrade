cmake_minimum_required(VERSION 3.20)
project(quant_system LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(quant_core
    src/agents.cpp
    src/backtest_engine.cpp
    src/history_client.cpp
    src/strategies/factory.cpp
    src/strategies/mean_reversion.cpp
    src/strategies/trend.cpp
    src/portfolio.cpp
    src/portfolio_book.cpp
    src/pricing.cpp
    src/report_io.cpp
    src/replay_data.cpp
    src/risk.cpp
    src/runtime_config.cpp
    src/execution.cpp
    src/oms.cpp
    src/trader_engine.cpp
)

target_include_directories(quant_core PUBLIC include)

add_executable(traderd apps/traderd/main.cpp)
target_link_libraries(traderd PRIVATE quant_core)

add_executable(replay_check apps/replay_check/main.cpp)
target_link_libraries(replay_check PRIVATE quant_core)

add_executable(option_demo apps/option_demo/main.cpp)
target_link_libraries(option_demo PRIVATE quant_core)

add_executable(pricing_check apps/pricing_check/main.cpp)
target_link_libraries(pricing_check PRIVATE quant_core)
