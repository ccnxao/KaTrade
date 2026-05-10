#include <cmath>
#include <iostream>
#include <memory>
#include <span>
#include <stdexcept>
#include <string>
#include <vector>

#include "qt/execution.hpp"
#include "qt/oms.hpp"

namespace {

bool near(double lhs, double rhs, double tolerance = 1e-9) {
    return std::abs(lhs - rhs) <= tolerance;
}

void require(bool condition, const std::string& message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

qt::Bar make_bar(double close, double volume, std::int64_t timestamp = 1) {
    return qt::Bar{
        timestamp,
        {"BTC-USDT-SWAP", "OKX"},
        close,
        close,
        close,
        close,
        volume,
    };
}

qt::OrderIntent make_buy_order(double quantity) {
    return qt::OrderIntent{
        {"BTC-USDT-SWAP", "OKX"},
        qt::OrderSide::Buy,
        qt::OrderType::Limit,
        quantity,
        100.0,
        "execution_model_check",
        "test_strategy",
    };
}

std::unique_ptr<qt::execution::OrderManagementSystem> make_oms() {
    auto broker = std::make_unique<qt::execution::SimulatedBrokerGateway>(
        0.04, 3.0, 1.0, 0.0);
    return std::make_unique<qt::execution::OrderManagementSystem>(std::move(broker));
}

void check_zero_volume_does_not_fill() {
    auto oms = make_oms();
    const auto order = make_buy_order(10.0);
    const auto submitted = oms->submit_orders(std::span<const qt::OrderIntent>(&order, 1));
    require(submitted.size() == 1, "order was not submitted");

    const std::vector<qt::Bar> bars{make_bar(100.0, 0.0)};
    oms->on_market_snapshot(bars);
    const auto reports = oms->collect_reports();
    require(reports.empty(), "zero-volume bar should not create a fill report");
    require(oms->order_history().front().status == qt::OrderStatus::Submitted,
            "zero-volume order should remain submitted");
}

void check_participation_cap_and_carry_forward() {
    auto oms = make_oms();
    const auto order = make_buy_order(10.0);
    oms->submit_orders(std::span<const qt::OrderIntent>(&order, 1));

    const std::vector<qt::Bar> low_volume{make_bar(100.0, 25.0, 1)};
    oms->on_market_snapshot(low_volume);
    auto reports = oms->collect_reports();
    require(reports.size() == 1, "low-volume bar should create one partial fill");
    require(near(reports[0].last_fill_qty, 1.0),
            "participation cap should limit fill to volume * 0.04");
    require(near(reports[0].remaining_qty, 9.0),
            "remaining quantity should carry to the next cycle");
    require(reports[0].status == qt::OrderStatus::PartiallyFilled,
            "low-volume fill should be partial");

    const std::vector<qt::Bar> high_volume{make_bar(101.0, 250.0, 2)};
    oms->on_market_snapshot(high_volume);
    reports = oms->collect_reports();
    require(reports.size() == 1, "second cycle should continue the working order");
    require(near(reports[0].last_fill_qty, 9.0),
            "second cycle should fill only the carried remaining quantity");
    require(near(reports[0].remaining_qty, 0.0),
            "working order should be fully filled after enough volume");
    require(reports[0].status == qt::OrderStatus::Filled,
            "carried order should become filled");
}

void check_cancelled_order_stops_filling() {
    auto oms = make_oms();
    const auto order = make_buy_order(10.0);
    oms->submit_orders(std::span<const qt::OrderIntent>(&order, 1));

    const std::vector<qt::Bar> low_volume{make_bar(100.0, 25.0, 1)};
    oms->on_market_snapshot(low_volume);
    auto reports = oms->collect_reports();
    require(reports.size() == 1 && reports[0].status == qt::OrderStatus::PartiallyFilled,
            "setup partial fill failed");

    oms->cancel_open_orders();
    reports = oms->collect_reports();
    require(reports.size() == 1, "cancel should produce one terminal report");
    require(reports[0].status == qt::OrderStatus::Cancelled,
            "cancel report should keep terminal cancelled status");
    require(near(reports[0].remaining_qty, 0.0),
            "cancelled order should have no open remaining quantity");
    require(oms->order_history().front().status == qt::OrderStatus::Cancelled,
            "OMS history should remain cancelled after broker cancel report");

    const std::vector<qt::Bar> high_volume{make_bar(102.0, 10'000.0, 2)};
    oms->on_market_snapshot(high_volume);
    reports = oms->collect_reports();
    require(reports.empty(), "cancelled order should not fill on later snapshots");
}

}  // namespace

int main() {
    try {
        check_zero_volume_does_not_fill();
        check_participation_cap_and_carry_forward();
        check_cancelled_order_stops_filling();
        std::cout << "execution model check passed\n";
        return 0;
    } catch (const std::exception& ex) {
        std::cerr << "execution model check failed: " << ex.what() << "\n";
        return 1;
    }
}
