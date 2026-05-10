CXX := c++
CXXFLAGS := -std=c++20 -Wall -Wextra -Wpedantic -Iinclude
HEADERS := $(shell find include -name '*.hpp')

# 实际存在的源文件
EXISTING_SOURCES := \
	src/agent/agent_capital.cpp \
	src/agent/llm_feature_agent.cpp \
	src/agent/meta_agent.cpp \
	src/agent/regime_agent.cpp \
	src/agent/agents.cpp \
	src/analysis/attribution.cpp \
	src/backtest/backtest_engine.cpp \
	src/data/calendar.cpp \
	src/data/feature_store.cpp \
	src/data/instrument_master.cpp \
	src/execution/execution.cpp \
	src/data/history_client.cpp \
	src/execution/oms.cpp \
	src/portfolio/portfolio.cpp \
	src/portfolio/portfolio_book.cpp \
	src/pricing/pricing.cpp \
	src/data/replay_data.cpp \
	src/reporting/report_io.cpp \
	src/risk/risk.cpp \
	src/risk/compliance.cpp \
	src/risk/risk_budget.cpp \
	src/risk/stress_test.cpp \
	src/config/runtime_config.cpp \
	src/storage/persistent_store.cpp \
	src/strategies/factory.cpp \
	src/strategies/mean_reversion.cpp \
	src/strategies/trend.cpp \
	src/engine/trader_engine.cpp

BACKENDD_SOURCES := \
	src/backend/account/account_routes.cpp \
	src/backend/account/account_read_model.cpp \
	src/backend/common/json.cpp \
	src/backend/order/order_maintenance.cpp \
	src/backend/order/order_read_model.cpp \
	src/backend/common/route_utils.cpp \
	src/backend/common/service_context.cpp \
	src/backend/api/route_registry.cpp \
	src/backend/http/http_server.cpp \
	apps/backendd/main.cpp

REALTIME_ENGINE_SOURCES := $(EXISTING_SOURCES) apps/realtime_engine/main.cpp

TRADERD_SOURCES := $(EXISTING_SOURCES) apps/traderd/main.cpp
REPLAY_CHECK_SOURCES := $(EXISTING_SOURCES) apps/replay_check/main.cpp
PRICING_CHECK_SOURCES := $(EXISTING_SOURCES) apps/pricing_check/main.cpp
OPTION_DEMO_SOURCES := $(EXISTING_SOURCES) apps/option_demo/main.cpp
EXECUTION_MODEL_CHECK_SOURCES := $(EXISTING_SOURCES) apps/execution_model_check/main.cpp
ORDER_MAINTENANCE_CHECK_SOURCES := \
	src/backend/order/order_maintenance.cpp \
	apps/order_maintenance_check/main.cpp
ACCOUNT_READ_MODEL_CHECK_SOURCES := \
	src/backend/account/account_read_model.cpp \
	src/backend/common/json.cpp \
	src/backend/common/service_context.cpp \
	apps/account_read_model_check/main.cpp

all: realtime_engine backendd

# realtime_engine — 完整编译
realtime_engine: $(REALTIME_ENGINE_SOURCES) $(HEADERS)
	$(CXX) $(CXXFLAGS) $(REALTIME_ENGINE_SOURCES) -o realtime_engine

traderd: $(TRADERD_SOURCES) $(HEADERS)
	$(CXX) $(CXXFLAGS) $(TRADERD_SOURCES) -o traderd

replay_check: $(REPLAY_CHECK_SOURCES) $(HEADERS)
	$(CXX) $(CXXFLAGS) $(REPLAY_CHECK_SOURCES) -o replay_check

pricing_check: $(PRICING_CHECK_SOURCES) $(HEADERS)
	$(CXX) $(CXXFLAGS) $(PRICING_CHECK_SOURCES) -o pricing_check

option_demo: $(OPTION_DEMO_SOURCES) $(HEADERS)
	$(CXX) $(CXXFLAGS) $(OPTION_DEMO_SOURCES) -o option_demo

execution_model_check: $(EXECUTION_MODEL_CHECK_SOURCES) $(HEADERS)
	$(CXX) $(CXXFLAGS) $(EXECUTION_MODEL_CHECK_SOURCES) -o execution_model_check

order_maintenance_check: $(ORDER_MAINTENANCE_CHECK_SOURCES) $(HEADERS)
	$(CXX) $(CXXFLAGS) $(ORDER_MAINTENANCE_CHECK_SOURCES) -o order_maintenance_check

account_read_model_check: $(ACCOUNT_READ_MODEL_CHECK_SOURCES) $(HEADERS)
	$(CXX) $(CXXFLAGS) $(ACCOUNT_READ_MODEL_CHECK_SOURCES) -o account_read_model_check

backendd: $(BACKENDD_SOURCES) $(HEADERS)
	$(CXX) $(CXXFLAGS) $(BACKENDD_SOURCES) -o backendd

check: replay_check pricing_check option_demo execution_model_check order_maintenance_check account_read_model_check backendd
	./replay_check
	./pricing_check
	./execution_model_check
	./order_maintenance_check
	./account_read_model_check
	./backendd --root . --config config/default.cfg --route /api/backend/summary >/dev/null

validate: check
	python3 -m py_compile apps/platform/server.py apps/historyd/server.py
	node --check apps/platform/static/app.js
	bash -n start.sh
	bash -n stop.sh

platform:
	python3 apps/platform/server.py

historyd:
	python3 apps/historyd/server.py

run: traderd
	./traderd

clean:
	rm -f realtime_engine backendd traderd replay_check pricing_check option_demo execution_model_check order_maintenance_check account_read_model_check

.PHONY: all check validate platform historyd run clean realtime_engine backendd execution_model_check order_maintenance_check account_read_model_check
