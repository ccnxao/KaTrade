CXX := c++
CXXFLAGS := -std=c++20 -Wall -Wextra -Wpedantic -Iinclude
TARGETS := traderd replay_check option_demo pricing_check

CORE_SOURCES := \
	src/agents.cpp \
	src/backtest_engine.cpp \
	src/portfolio.cpp \
	src/portfolio_book.cpp \
	src/pricing.cpp \
	src/report_io.cpp \
	src/replay_data.cpp \
	src/risk.cpp \
	src/runtime_config.cpp \
	src/execution.cpp \
	src/oms.cpp \
	src/trader_engine.cpp

TRADER_SOURCES := \
	$(CORE_SOURCES) \
	apps/traderd/main.cpp

REPLAY_CHECK_SOURCES := \
	$(CORE_SOURCES) \
	apps/replay_check/main.cpp

OPTION_DEMO_SOURCES := \
	$(CORE_SOURCES) \
	apps/option_demo/main.cpp

PRICING_CHECK_SOURCES := \
	$(CORE_SOURCES) \
	apps/pricing_check/main.cpp

all: $(TARGETS)

traderd: $(TRADER_SOURCES)
	$(CXX) $(CXXFLAGS) $(TRADER_SOURCES) -o traderd

replay_check: $(REPLAY_CHECK_SOURCES)
	$(CXX) $(CXXFLAGS) $(REPLAY_CHECK_SOURCES) -o replay_check

option_demo: $(OPTION_DEMO_SOURCES)
	$(CXX) $(CXXFLAGS) $(OPTION_DEMO_SOURCES) -o option_demo

pricing_check: $(PRICING_CHECK_SOURCES)
	$(CXX) $(CXXFLAGS) $(PRICING_CHECK_SOURCES) -o pricing_check

run: traderd
	./traderd

check: replay_check pricing_check
	./replay_check
	./pricing_check

platform:
	python3 apps/platform/server.py

clean:
	rm -f $(TARGETS)

.PHONY: all run check platform clean
