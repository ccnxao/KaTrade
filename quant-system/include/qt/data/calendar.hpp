#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace qt::data {

// ---- 交易时段类型 ----------------------------------------------------
// 加密货币 24/7 交易，但按全球主要交易时段划分便于策略感知
enum class TradingSession {
    Asia,       // 亚洲时段 (00:00-08:00 UTC)
    Europe,     // 欧洲时段 (08:00-16:00 UTC)
    America,    // 美洲时段 (16:00-24:00 UTC)
    Weekend,    // 周末 (周六/周日 UTC)
    Unknown
};

// ---- 交易日历 --------------------------------------------------------
// 提供:
//   - 当前交易时段判断
//   - 资金费率结算时间检测
//   - 周末/节假日判断
//   - 交易日计数（用于回测/报告）
//
// 加密货币没有传统意义上的休市，但以下时间点有特殊意义:
//   - 资金费率结算: 每天 00:00, 08:00, 16:00 UTC
//   - 期权/交割合约到期: 每周五 08:00 UTC
//   - 周末低流动性时段
// ----------------------------------------------------------------------

class TradingCalendar {
public:
    TradingCalendar();

    // ---- 时段检测 ----

    // 根据 UTC 时间戳判断当前交易时段
    TradingSession session(int64_t utc_timestamp_ms) const;
    const char* session_name(TradingSession session) const;

    // 是否在周末 (UTC 周六/周日)
    bool is_weekend(int64_t utc_timestamp_ms) const;

    // ---- 资金费率 ----

    // 检查是否在资金费率结算时刻前后 (threshold_seconds 内的结算时间)
    bool is_funding_settlement(int64_t utc_timestamp_ms, int threshold_seconds = 30) const;

    // 距下一次资金费率结算的秒数
    int64_t seconds_until_next_funding(int64_t utc_timestamp_ms) const;

    // 资金费率结算时间点 (返回最近一次 <= timestamp 的结算时刻)
    int64_t last_funding_time(int64_t utc_timestamp_ms) const;

    // ---- 交易日 ----

    // 是否为有效交易日 (非周末)
    bool is_trading_day(int64_t utc_timestamp_ms) const;

    // 两个时间戳之间的交易日数
    int trading_days_between(int64_t from_ms, int64_t to_ms) const;

    // 给定 UTC 时间戳的日期字符串 (YYYY-MM-DD)
    std::string date_string(int64_t utc_timestamp_ms) const;

    // ---- 周/月标记 ----

    // 是否为一周的第一天 (周一 UTC)
    bool is_week_start(int64_t utc_timestamp_ms) const;
    // 是否为一个月的第一天
    bool is_month_start(int64_t utc_timestamp_ms) const;

private:
    // 资金费率结算时刻 (UTC 秒): 00:00, 08:00, 16:00
    static constexpr int64_t FUNDING_INTERVAL_SEC = 8 * 3600;  // 8 小时
    static constexpr int64_t FUNDING_OFFSET_SEC = 0;            // 00:00 UTC

    // 将 ms 时间戳分解为 UTC 日期组件
    struct DateComponents {
        int year;
        int month;   // 1-12
        int day;     // 1-31
        int weekday; // 0=Sun, 1=Mon, ..., 6=Sat
        int hour;
        int minute;
        int second;
    };
    DateComponents decompose(int64_t utc_timestamp_ms) const;

    // 判断是否为闰年
    static bool is_leap_year(int year);

    // 某年某月的天数
    static int days_in_month(int year, int month);
};

// 便捷函数
inline const char* to_string(TradingSession session) {
    switch (session) {
        case TradingSession::Asia:    return "Asia";
        case TradingSession::Europe:  return "Europe";
        case TradingSession::America: return "America";
        case TradingSession::Weekend: return "Weekend";
        case TradingSession::Unknown: return "Unknown";
    }
    return "Unknown";
}

}  // namespace qt::data
