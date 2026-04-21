#pragma once

#include <cstdint>
#include <functional>
#include <string>
#include <type_traits>
#include <utility>
#include <variant>
#include <vector>

#include "qt/types.hpp"

namespace qt {

struct CycleStartedEvent {
    std::size_t cycle_index{};
    std::string label;
    std::size_t instrument_count{};
};

struct RegimeDetectedEvent {
    std::size_t cycle_index{};
    RegimeState regime;
};

struct RiskReviewedEvent {
    std::size_t cycle_index{};
    RiskDecision decision;
};

struct OrderSubmittedEvent {
    std::size_t cycle_index{};
    OrderRecord record;
};

struct OrderFilledEvent {
    std::size_t cycle_index{};
    ExecutionReport report;
};

struct CycleCompletedEvent {
    std::size_t cycle_index{};
    std::string label;
    std::size_t signal_count{};
    std::size_t submitted_orders{};
    std::size_t fill_count{};
};

using EventPayload =
    std::variant<CycleStartedEvent,
                 RegimeDetectedEvent,
                 RiskReviewedEvent,
                 OrderSubmittedEvent,
                 OrderFilledEvent,
                 CycleCompletedEvent>;

struct Event {
    std::uint64_t sequence{};
    EventPayload payload;
};

class EventBus {
public:
    using Handler = std::function<void(const Event&)>;

    void subscribe(Handler handler) { handlers_.push_back(std::move(handler)); }

    void publish(EventPayload payload) {
        Event event{++next_sequence_, std::move(payload)};
        history_.push_back(event);
        for (const auto& handler : handlers_) {
            handler(history_.back());
        }
    }

    const std::vector<Event>& history() const noexcept { return history_; }
    void clear() {
        history_.clear();
        next_sequence_ = 0;
    }

private:
    std::uint64_t next_sequence_{0};
    std::vector<Handler> handlers_;
    std::vector<Event> history_;
};

inline std::string describe_event(const Event& event) {
    return std::visit(
        [&](const auto& payload) -> std::string {
            using T = std::decay_t<decltype(payload)>;

            if constexpr (std::is_same_v<T, CycleStartedEvent>) {
                return "cycle " + std::to_string(payload.cycle_index) + " started: " +
                       payload.label;
            } else if constexpr (std::is_same_v<T, RegimeDetectedEvent>) {
                return "cycle " + std::to_string(payload.cycle_index) +
                       " regime=" + to_string(payload.regime.regime);
            } else if constexpr (std::is_same_v<T, RiskReviewedEvent>) {
                return "cycle " + std::to_string(payload.cycle_index) +
                       " risk=" + to_string(payload.decision.action) + " (" +
                       payload.decision.reason + ")";
            } else if constexpr (std::is_same_v<T, OrderSubmittedEvent>) {
                return "cycle " + std::to_string(payload.cycle_index) +
                       " order submitted: " + payload.record.order_id + " " +
                       instrument_key(payload.record.intent.instrument);
            } else if constexpr (std::is_same_v<T, OrderFilledEvent>) {
                return "cycle " + std::to_string(payload.cycle_index) +
                       " fill: " + payload.report.order_id + " " +
                       instrument_key(payload.report.instrument);
            } else if constexpr (std::is_same_v<T, CycleCompletedEvent>) {
                return "cycle " + std::to_string(payload.cycle_index) + " completed: " +
                       payload.label;
            }

            return "unknown";
        },
        event.payload);
}

}  // namespace qt
