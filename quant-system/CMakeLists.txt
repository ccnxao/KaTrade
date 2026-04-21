cmake_minimum_required(VERSION 3.20)
project(quant_system LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(quant_core
    src/agents.cpp
    src/portfolio.cpp
    src/risk.cpp
    src/execution.cpp
    src/trader_engine.cpp
)

target_include_directories(quant_core PUBLIC include)

add_executable(traderd apps/traderd/main.cpp)
target_link_libraries(traderd PRIVATE quant_core)
