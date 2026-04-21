CXX := c++
CXXFLAGS := -std=c++20 -Wall -Wextra -Wpedantic -Iinclude
TARGET := traderd

SOURCES := \
	src/agents.cpp \
	src/backtest_engine.cpp \
	src/portfolio.cpp \
	src/risk.cpp \
	src/execution.cpp \
	src/oms.cpp \
	src/trader_engine.cpp \
	apps/traderd/main.cpp

all: $(TARGET)

$(TARGET): $(SOURCES)
	$(CXX) $(CXXFLAGS) $(SOURCES) -o $(TARGET)

run: $(TARGET)
	./$(TARGET)

clean:
	rm -f $(TARGET)

.PHONY: all run clean
