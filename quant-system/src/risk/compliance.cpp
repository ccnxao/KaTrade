#include "qt/risk/compliance.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <fstream>
#include <sstream>

namespace qt::risk {

ComplianceChecker::ComplianceChecker() = default;

// ---- 限仓名单 --------------------------------------------------------

void ComplianceChecker::add_restricted(const std::string& inst_key) {
    if (std::find(restricted_instruments_.begin(),
                  restricted_instruments_.end(),
                  inst_key) == restricted_instruments_.end()) {
        restricted_instruments_.push_back(inst_key);
    }
}

void ComplianceChecker::remove_restricted(const std::string& inst_key) {
    restricted_instruments_.erase(
        std::remove(restricted_instruments_.begin(),
                    restricted_instruments_.end(), inst_key),
        restricted_instruments_.end());
}

bool ComplianceChecker::is_restricted(const std::string& inst_key) const {
    return std::find(restricted_instruments_.begin(),
                     restricted_instruments_.end(),
                     inst_key) != restricted_instruments_.end();
}

// ---- Wash Sale 检测 --------------------------------------------------

void ComplianceChecker::record_fill(const std::string& inst_key,
                                     OrderSide side,
                                     double qty,
                                     double price,
                                     double entry_price,
                                     int64_t timestamp_ms) {
    // 只记录卖出成交（潜在 wash sale 的触发端）
    // 如果卖出价低于买入价（亏损），记录以备后续检查
    if (side == OrderSide::Sell && entry_price > 0.0) {
        double loss = (price - entry_price) * qty;  // 负值 = 亏损
        wash_sale_history_.push_back(
            {inst_key, side, qty, price, loss, timestamp_ms});
    }

    // 限制历史长度
    while (wash_sale_history_.size() > 10000) {
        wash_sale_history_.pop_front();
    }
}

std::string ComplianceChecker::check_wash_sale(const std::string& inst_key,
                                                OrderSide side,
                                                int64_t timestamp_ms) const {
    // Wash sale: 卖出亏损后 30 天内重新买入同一品种
    if (side != OrderSide::Buy) return "";

    int64_t cutoff = timestamp_ms - WASH_SALE_WINDOW_MS;

    for (const auto& record : wash_sale_history_) {
        if (record.inst_key != inst_key) continue;
        if (record.timestamp_ms < cutoff) continue;

        // 找到了 30 天内的卖出记录
        if (record.side == OrderSide::Sell && record.loss < 0.0) {
            std::ostringstream oss;
            oss << "Wash sale detected: bought " << inst_key
                << " within 30 days of a loss sale (loss="
                << std::abs(record.loss) << ", sold at t="
                << record.timestamp_ms << ")";
            return oss.str();
        }
    }
    return "";
}

// ---- 仓位上限 --------------------------------------------------------

void ComplianceChecker::set_position_limit(const std::string& inst_key,
                                            double max_qty) {
    position_limits_[inst_key] = max_qty;
}

bool ComplianceChecker::exceeds_position_limit(const std::string& inst_key,
                                                double current_qty) const {
    auto it = position_limits_.find(inst_key);
    if (it == position_limits_.end()) return false;  // 无限制
    return std::abs(current_qty) > it->second;
}

// ---- 撤单率监控 ------------------------------------------------------

void ComplianceChecker::purge_stale_cancel_stats() {
    // 清理超过 24 小时未活跃的品种记录
    auto now_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    auto it = cancel_stats_.begin();
    while (it != cancel_stats_.end()) {
        if (now_ms - it->second.window_start_ms > 24 * 3600 * 1000LL)
            it = cancel_stats_.erase(it);
        else
            ++it;
    }
}

void ComplianceChecker::record_order_sent(const std::string& inst_key) {
    auto now_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    auto& stats = cancel_stats_[inst_key];

    // 每小时重置窗口
    if (stats.window_start_ms == 0 ||
        now_ms - stats.window_start_ms > EXCESSIVE_CANCEL_WINDOW_MS) {
        stats = CancelStats{};
        stats.window_start_ms = now_ms;
    }
    stats.sent++;
}

void ComplianceChecker::record_order_cancelled(const std::string& inst_key) {
    auto& stats = cancel_stats_[inst_key];
    stats.cancelled++;
}

bool ComplianceChecker::excessive_cancellations(const std::string& inst_key,
                                                  double threshold_ratio) const {
    auto it = cancel_stats_.find(inst_key);
    if (it == cancel_stats_.end()) return false;

    const auto& stats = it->second;
    if (stats.sent < 10) return false;  // 样本太小不判断

    double ratio = static_cast<double>(stats.cancelled) / stats.sent;
    return ratio > threshold_ratio;
}

// ---- 综合检查 --------------------------------------------------------

ComplianceResult ComplianceChecker::check_order(
    const std::string& inst_key,
    OrderSide side,
    double qty,
    double,
    double current_position_qty,
    int64_t timestamp_ms) const {

    ComplianceResult result;

    // 1. 限仓名单
    if (is_restricted(inst_key)) {
        result.add_violation("Instrument " + inst_key + " is on restricted list");
    }

    // 2. Wash sale
    auto ws = check_wash_sale(inst_key, side, timestamp_ms);
    if (!ws.empty()) {
        result.add_violation(ws);
    }

    // 3. 仓位上限（含新订单后）
    double new_qty = current_position_qty;
    if (side == OrderSide::Buy) new_qty += qty;
    else new_qty -= qty;
    if (exceeds_position_limit(inst_key, std::abs(new_qty))) {
        std::ostringstream oss;
        oss << "Position limit exceeded: " << inst_key
            << " would reach " << std::abs(new_qty);
        auto it = position_limits_.find(inst_key);
        if (it != position_limits_.end()) {
            oss << " (limit=" << it->second << ")";
        }
        result.add_violation(oss.str());
    }

    // 4. 撤单率
    if (excessive_cancellations(inst_key)) {
        result.add_violation("Excessive cancellation rate on " + inst_key);
    }

    return result;
}

// ---- 清理 ------------------------------------------------------------

void ComplianceChecker::purge_stale_records(int64_t before_timestamp_ms) {
    int64_t cutoff = before_timestamp_ms - WASH_SALE_WINDOW_MS;
    while (!wash_sale_history_.empty() &&
           wash_sale_history_.front().timestamp_ms < cutoff) {
        wash_sale_history_.pop_front();
    }
}

// ---- 持久化 ----------------------------------------------------------

static std::string esc_json(const std::string& s) {
    std::string out;
    out.reserve(s.size());
    for (char c : s) {
        if (c == '"') out += "\\\"";
        else if (c == '\\') out += "\\\\";
        else if (c == '\n') out += "\\n";
        else out += c;
    }
    return out;
}

bool ComplianceChecker::save(const std::string& path) const {
    std::ofstream of(path, std::ios::trunc);
    if (!of) return false;

    auto now_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();

    of << "{\n";
    of << "  \"saved_at_ms\":" << now_ms << ",\n";

    // 限仓名单
    of << "  \"restricted\":[";
    for (size_t i = 0; i < restricted_instruments_.size(); ++i) {
        if (i) of << ",";
        of << "\"" << esc_json(restricted_instruments_[i]) << "\"";
    }
    of << "],\n";

    // Wash sale 历史（只保留近 30 天）
    of << "  \"wash_sales\":[";
    bool first = true;
    int64_t cutoff = now_ms - WASH_SALE_WINDOW_MS;
    for (const auto& r : wash_sale_history_) {
        if (r.timestamp_ms < cutoff) continue;
        if (!first) of << ",";
        first = false;
        of << "{\"inst\":\"" << esc_json(r.inst_key) << "\""
           << ",\"side\":\"" << (r.side == OrderSide::Buy ? "Buy" : "Sell") << "\""
           << ",\"qty\":" << r.qty
           << ",\"price\":" << r.price
           << ",\"loss\":" << r.loss
           << ",\"ts\":" << r.timestamp_ms << "}";
    }
    of << "],\n";

    // 仓位上限
    of << "  \"position_limits\":{";
    first = true;
    for (const auto& [key, limit] : position_limits_) {
        if (!first) of << ",";
        first = false;
        of << "\"" << esc_json(key) << "\":" << limit;
    }
    of << "},\n";

    // 撤单统计
    of << "  \"cancel_stats\":{";
    first = true;
    for (const auto& [key, stats] : cancel_stats_) {
        if (now_ms - stats.window_start_ms > 24LL * 3600 * 1000) continue;
        if (!first) of << ",";
        first = false;
        of << "\"" << esc_json(key) << "\":{"
           << "\"sent\":" << stats.sent
           << ",\"cancelled\":" << stats.cancelled
           << ",\"window_start\":" << stats.window_start_ms << "}";
    }
    of << "}\n";
    of << "}\n";
    return bool(of);
}

// 前向声明
static std::string find_val_in(const std::string& s, size_t start, const std::string& key);

bool ComplianceChecker::load(const std::string& path) {
    std::ifstream in(path);
    if (!in) return false;

    std::string content((std::istreambuf_iterator<char>(in)),
                         std::istreambuf_iterator<char>());
    if (content.empty()) return false;

    // 解析 restricted 数组
    auto rpos = content.find("\"restricted\"");
    if (rpos != std::string::npos) {
        auto arr = content.find('[', rpos);
        auto end = content.find(']', arr);
        if (arr != std::string::npos && end != std::string::npos) {
            std::string arr_str = content.substr(arr + 1, end - arr - 1);
            size_t p = 0;
            while (p < arr_str.size()) {
                auto q1 = arr_str.find('"', p);
                if (q1 == std::string::npos) break;
                auto q2 = arr_str.find('"', q1 + 1);
                if (q2 == std::string::npos) break;
                restricted_instruments_.push_back(arr_str.substr(q1 + 1, q2 - q1 - 1));
                p = q2 + 1;
            }
        }
    }

    // 解析 position_limits
    auto ppos = content.find("\"position_limits\"");
    if (ppos != std::string::npos) {
        auto obj = content.find('{', ppos);
        auto end = content.find('}', obj);
        if (obj != std::string::npos && end != std::string::npos) {
            std::string obj_str = content.substr(obj + 1, end - obj - 1);
            size_t p = 0;
            while (p < obj_str.size()) {
                auto q1 = obj_str.find('"', p);
                if (q1 == std::string::npos) break;
                auto q2 = obj_str.find('"', q1 + 1);
                if (q2 == std::string::npos) break;
                std::string key = obj_str.substr(q1 + 1, q2 - q1 - 1);
                auto col = obj_str.find(':', q2 + 1);
                if (col == std::string::npos) break;
                try {
                    position_limits_[key] = std::stod(obj_str.substr(col + 1));
                } catch (...) {}
                p = col + 1;
            }
        }
    }

    // 解析 cancel_stats
    auto cpos = content.find("\"cancel_stats\"");
    if (cpos != std::string::npos) {
        auto obj = content.find('{', cpos);
        // 找匹配的 } — 简单嵌套解析
        int depth = 0;
        size_t end = obj;
        for (size_t i = obj; i < content.size(); ++i) {
            if (content[i] == '{') ++depth;
            else if (content[i] == '}') { --depth; if (depth == 0) { end = i; break; } }
        }
        if (depth == 0) {
            std::string obj_str = content.substr(obj + 1, end - obj - 1);
            // 每个 key -> { sent, cancelled, window_start }
            size_t p = 0;
            while (p < obj_str.size()) {
                auto q1 = obj_str.find('"', p);
                if (q1 == std::string::npos) break;
                auto q2 = obj_str.find('"', q1 + 1);
                if (q2 == std::string::npos) break;
                std::string key = obj_str.substr(q1 + 1, q2 - q1 - 1);
                try {
                    CancelStats st;
                    st.sent = std::stoi(find_val_in(obj_str, q2, "sent"));
                    st.cancelled = std::stoi(find_val_in(obj_str, q2, "cancelled"));
                    auto ws = find_val_in(obj_str, q2, "window_start");
                    if (!ws.empty()) st.window_start_ms = std::stoll(ws);
                    cancel_stats_[key] = st;
                } catch (...) {}
                p = obj_str.find('}', q2) + 1;
            }
        }
    }

    // 解析 wash_sales
    auto wpos = content.find("\"wash_sales\"");
    if (wpos != std::string::npos) {
        auto arr = content.find('[', wpos);
        auto end = content.find(']', arr);
        if (arr != std::string::npos && end != std::string::npos) {
            std::string arr_str = content.substr(arr + 1, end - arr - 1);
            size_t p = 0;
            while (p < arr_str.size()) {
                auto q1 = arr_str.find('{', p);
                if (q1 == std::string::npos) break;
                auto q2 = arr_str.find('}', q1);
                if (q2 == std::string::npos) break;
                std::string obj_str = arr_str.substr(q1, q2 - q1 + 1);
                try {
                    WashSaleRecord r;
                    r.inst_key = find_val_in(obj_str, 0, "inst");
                    r.side = find_val_in(obj_str, 0, "side") == "Buy" ? OrderSide::Buy : OrderSide::Sell;
                    r.qty = std::stod(find_val_in(obj_str, 0, "qty"));
                    r.price = std::stod(find_val_in(obj_str, 0, "price"));
                    r.loss = std::stod(find_val_in(obj_str, 0, "loss"));
                    auto ts = find_val_in(obj_str, 0, "ts");
                    if (!ts.empty()) r.timestamp_ms = std::stoll(ts);
                    wash_sale_history_.push_back(r);
                } catch (...) {}
                p = q2 + 1;
            }
        }
    }

    return true;
}

// 辅助: 在指定位置之后查找 key 的值
static std::string find_val_in(const std::string& s, size_t start, const std::string& key) {
    auto pos = s.find("\"" + key + "\"", start);
    if (pos == std::string::npos) return "";
    pos = s.find(':', pos + key.size() + 2);
    if (pos == std::string::npos) return "";
    pos = s.find_first_not_of(": \t\n\r", pos);
    if (pos == std::string::npos) return "";
    size_t end = pos;
    if (s[pos] == '"') {
        end = s.find('"', pos + 1);
        if (end == std::string::npos) return "";
        return s.substr(pos + 1, end - pos - 1);
    }
    while (end < s.size() && (std::isdigit(s[end]) || s[end] == '.' || s[end] == '-' || s[end] == 'e')) ++end;
    return s.substr(pos, end - pos);
}

}  // namespace qt::risk
