#pragma once

#include <cstdint>
#include <deque>
#include <string>
#include <unordered_map>
#include <vector>

#include "qt/types.hpp"

namespace qt::risk {

// ---- 合规检查结果 ----------------------------------------------------

struct ComplianceResult {
    bool passed{true};
    std::vector<std::string> violations;  // 违规描述列表

    void add_violation(const std::string& msg) {
        passed = false;
        violations.push_back(msg);
    }
};

// ---- 合规检查器 (GAP-035) ---------------------------------------------
// 提供以下检查:
//   1. 限仓名单 — 禁止交易特定品种
//   2. Wash sale 检测 — 30 天内卖出亏损后重新买入
//   3. 仓位上限 — 单品种持仓不超过上限
//   4. 撤单率异常 — 过高撤单率可能标记操纵行为
//   5. 交易频率 — 过高频率可能标记
// ----------------------------------------------------------------------

class ComplianceChecker {
public:
    ComplianceChecker();

    // ---- 限仓名单 ----
    void add_restricted(const std::string& inst_key);
    void remove_restricted(const std::string& inst_key);
    bool is_restricted(const std::string& inst_key) const;

    // ---- Wash Sale 检测 ----
    // 记录一笔已成交的交易（用于后续 wash sale 比对）
    void record_fill(const std::string& inst_key,
                     OrderSide side,
                     double qty,
                     double price,
                     double entry_price,  // 开仓均价（若有）
                     int64_t timestamp_ms);

    // 检查一笔新订单是否构成 wash sale
    // 返回违规描述，若无违规返回空字符串
    std::string check_wash_sale(const std::string& inst_key,
                                 OrderSide side,
                                 int64_t timestamp_ms) const;

    // ---- 仓位上限 ----
    void set_position_limit(const std::string& inst_key, double max_qty);
    bool exceeds_position_limit(const std::string& inst_key,
                                 double current_qty) const;

    // ---- 撤单率监控 ----
    void record_order_sent(const std::string& inst_key);
    void record_order_cancelled(const std::string& inst_key);
    bool excessive_cancellations(const std::string& inst_key,
                                  double threshold_ratio = 0.50) const;

    // ---- 综合检查 ----
    // 对一笔新订单执行全量合规检查
    ComplianceResult check_order(const std::string& inst_key,
                                  OrderSide side,
                                  double qty,
                                  double price,
                                  double current_position_qty,
                                  int64_t timestamp_ms) const;

    // ---- 持久化 (P1#7) ----
    // 保存合规状态到 JSON 文件，跨进程重启保留
    bool save(const std::string& path) const;
    bool load(const std::string& path);

    // ---- 清理 ----
    // 清除过期 wash sale 记录（超过 30 天）
    void purge_stale_records(int64_t before_timestamp_ms);
    // 清除过期撤单统计（超过 24 小时未活跃）
    void purge_stale_cancel_stats();

private:
    struct WashSaleRecord {
        std::string inst_key;
        OrderSide side;
        double qty;
        double price;
        double loss;        // 实现的亏损（卖出价-买入价，正=盈利，负=亏损）
        int64_t timestamp_ms;
    };

    static constexpr int64_t WASH_SALE_WINDOW_MS = 30LL * 24 * 3600 * 1000;  // 30 天
    static constexpr int64_t EXCESSIVE_CANCEL_WINDOW_MS = 3600LL * 1000;     // 1 小时

    std::vector<std::string> restricted_instruments_;
    std::deque<WashSaleRecord> wash_sale_history_;
    std::unordered_map<std::string, double> position_limits_;

    struct CancelStats {
        int sent{0};
        int cancelled{0};
        int64_t window_start_ms{0};
    };
    std::unordered_map<std::string, CancelStats> cancel_stats_;
};

}  // namespace qt::risk
