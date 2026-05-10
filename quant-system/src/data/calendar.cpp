#include "qt/data/calendar.hpp"

#include <algorithm>
#include <cmath>
#include <ctime>
#include <sstream>
#include <iomanip>

namespace qt::data {

// ---- 内部工具 --------------------------------------------------------

// 从 Unix 时间戳计算 UTC 日期组件
// 使用标准 <ctime> 的 gmtime 避免手动实现日历算法的复杂性
TradingCalendar::DateComponents TradingCalendar::decompose(
    int64_t utc_timestamp_ms) const {
    DateComponents dc{};
    std::time_t t = static_cast<std::time_t>(utc_timestamp_ms / 1000);
    std::tm utc{};
#if defined(_WIN32) || defined(_MSC_VER)
    gmtime_s(&utc, &t);  // R45: Windows/MSVC
#else
    gmtime_r(&t, &utc);  // POSIX
#endif
    dc.year    = utc.tm_year + 1900;
    dc.month   = utc.tm_mon + 1;
    dc.day     = utc.tm_mday;
    dc.weekday = utc.tm_wday;  // 0=Sun
    dc.hour    = utc.tm_hour;
    dc.minute  = utc.tm_min;
    dc.second  = utc.tm_sec;
    return dc;
}

bool TradingCalendar::is_leap_year(int year) {
    return (year % 4 == 0 && year % 100 != 0) || (year % 400 == 0);
}

int TradingCalendar::days_in_month(int year, int month) {
    static const int days[12] = {31,28,31,30,31,30,31,31,30,31,30,31};
    if (month == 2 && is_leap_year(year)) return 29;
    return days[month - 1];
}

// ---- 构造函数 --------------------------------------------------------

TradingCalendar::TradingCalendar() = default;

// ---- 时段检测 --------------------------------------------------------

TradingSession TradingCalendar::session(int64_t utc_timestamp_ms) const {
    auto dc = decompose(utc_timestamp_ms);

    // 周末判断
    if (dc.weekday == 0 || dc.weekday == 6) {
        return TradingSession::Weekend;
    }

    // 工作日按时段划分
    if (dc.hour < 8) {
        return TradingSession::Asia;     // 00:00-07:59 UTC = 亚洲
    } else if (dc.hour < 16) {
        return TradingSession::Europe;   // 08:00-15:59 UTC = 欧洲
    } else {
        return TradingSession::America;  // 16:00-23:59 UTC = 美洲
    }
}

const char* TradingCalendar::session_name(TradingSession session) const {
    return to_string(session);
}

bool TradingCalendar::is_weekend(int64_t utc_timestamp_ms) const {
    auto dc = decompose(utc_timestamp_ms);
    return dc.weekday == 0 || dc.weekday == 6;
}

// ---- 资金费率结算 ----------------------------------------------------

bool TradingCalendar::is_funding_settlement(int64_t utc_timestamp_ms,
                                             int threshold_seconds) const {
    // 资金费率在 UTC 00:00, 08:00, 16:00 结算
    // 将时间戳转为当天秒数
    int64_t total_seconds = utc_timestamp_ms / 1000;
    int64_t day_seconds = total_seconds % 86400;

    // 检查是否在任一结算时间点附近
    for (int64_t settlement : {0LL, 8LL * 3600, 16LL * 3600}) {
        int64_t diff = std::abs(day_seconds - settlement);
        // 处理跨天边界
        if (diff > 43200) diff = 86400 - diff;
        if (diff <= threshold_seconds) return true;
    }
    return false;
}

int64_t TradingCalendar::seconds_until_next_funding(int64_t utc_timestamp_ms) const {
    int64_t total_seconds = utc_timestamp_ms / 1000;
    int64_t day_seconds = total_seconds % 86400;

    // 找下一个结算时间
    for (int64_t settlement : {0LL, 8LL * 3600, 16LL * 3600, 24LL * 3600}) {
        if (day_seconds < settlement) {
            return settlement - day_seconds;
        }
    }
    // 今天的结算都已过，下一个是明天 00:00
    return 86400 - day_seconds;
}

int64_t TradingCalendar::last_funding_time(int64_t utc_timestamp_ms) const {
    int64_t total_seconds = utc_timestamp_ms / 1000;
    int64_t day_seconds = total_seconds % 86400;

    // 找最近一次的结算时间
    int64_t last_settlement = 16LL * 3600;  // 默认今天 16:00
    for (int64_t settlement : {16LL * 3600, 8LL * 3600, 0LL}) {
        if (day_seconds >= settlement) {
            last_settlement = settlement;
            break;
        }
    }
    // 如果今天没有（day_seconds < 0，不可能），回退到昨天 16:00
    return (total_seconds / 86400) * 86400 + last_settlement;
}

// ---- 交易日 ----------------------------------------------------------

bool TradingCalendar::is_trading_day(int64_t utc_timestamp_ms) const {
    return !is_weekend(utc_timestamp_ms);
}

int TradingCalendar::trading_days_between(int64_t from_ms, int64_t to_ms) const {
    if (from_ms >= to_ms) return 0;

    // 简单实现: 遍历每天计数（性能足以处理最多几年的跨度）
    int count = 0;
    int64_t day_ms = 86400LL * 1000;
    // 对齐到 UTC 00:00
    int64_t current = (from_ms / day_ms) * day_ms;
    int64_t end = (to_ms / day_ms) * day_ms;

    while (current <= end) {
        if (is_trading_day(current)) ++count;
        current += day_ms;
    }
    return count;
}

std::string TradingCalendar::date_string(int64_t utc_timestamp_ms) const {
    auto dc = decompose(utc_timestamp_ms);
    std::ostringstream oss;
    oss << std::setfill('0')
        << std::setw(4) << dc.year << "-"
        << std::setw(2) << dc.month << "-"
        << std::setw(2) << dc.day;
    return oss.str();
}

// ---- 周/月标记 --------------------------------------------------------

bool TradingCalendar::is_week_start(int64_t utc_timestamp_ms) const {
    auto dc = decompose(utc_timestamp_ms);
    return dc.weekday == 1;  // 周一
}

bool TradingCalendar::is_month_start(int64_t utc_timestamp_ms) const {
    auto dc = decompose(utc_timestamp_ms);
    return dc.day == 1;
}

}  // namespace qt::data
