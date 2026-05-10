#pragma once

#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

namespace qt::data {

// ---- 合约规格 --------------------------------------------------------
// 每个交易品种的标准化参数，用于:
//   - 订单数量/价格校验（tick_size, lot_size）
//   - 杠杆限制检查
//   - 最小名义金额检查
//   - 品种类型区分（现货/永续/交割/期权）
// ----------------------------------------------------------------------

struct ContractSpec {
    std::string inst_id;       // "BTC-USDT-SWAP"
    std::string base_ccy;      // "BTC"
    std::string quote_ccy;     // "USDT"
    std::string inst_type;     // "SPOT" | "SWAP" | "FUTURES" | "OPTION"
    double tick_size{0.01};    // 最小价格变动单位
    double lot_size{0.0001};   // 最小下单数量（以 base_ccy 计，合约以张计）
    double ct_val{1.0};        // 合约面值（USDT，现货为 1）
    double min_notional{5.0};  // 最小名义金额（USDT）
    double max_leverage{0.0};  // 最大杠杆（0 = 不可杠杆 / 现货）
    bool enabled{true};
};

// ---- Instrument Master ------------------------------------------------
// 合约主数据存储与查询。
// 预置 OKX 主流合约规格，支持运行时注册自定义品种。
// ----------------------------------------------------------------------

class InstrumentMaster {
public:
    InstrumentMaster();

    // ---- 查询 ----

    // 按 instrument key 查找（"BTC-USDT-SWAP.OKX"）
    const ContractSpec* lookup(const std::string& inst_key) const;

    // 按 symbol+exchange 查找
    const ContractSpec* lookup(const std::string& symbol,
                               const std::string& exchange) const;

    // 便捷查询
    double tick_size(const std::string& inst_key, double fallback = 0.01) const;
    double lot_size(const std::string& inst_key, double fallback = 0.0001) const;
    double min_notional(const std::string& inst_key, double fallback = 5.0) const;
    double max_leverage(const std::string& inst_key, double fallback = 0.0) const;

    // 品种类型判断
    bool is_spot(const std::string& inst_key) const;
    bool is_perpetual(const std::string& inst_key) const;
    bool is_derivative(const std::string& inst_key) const;

    // 从 inst_key 提取 base/quote
    std::string base_ccy(const std::string& inst_key) const;
    std::string quote_ccy(const std::string& inst_key) const;

    // ---- 注册 ----
    void register_spec(ContractSpec spec);

    // ---- 预置数据 ----
    // 返回预置 OKX 主流合约列表
    static std::vector<ContractSpec> okx_default_specs();

    // 创建预填充 OKX 数据的 master
    static InstrumentMaster okx_default();

    // ---- 列举 ----
    std::vector<std::string> all_instruments() const;
    std::vector<std::string> instruments_by_type(const std::string& inst_type) const;

private:
    // key: "BTC-USDT-SWAP.OKX" -> spec
    std::unordered_map<std::string, ContractSpec> specs_;

    // 从 inst_id ("BTC-USDT-SWAP") + exchange ("OKX") 拼 key
    static std::string make_key(const std::string& inst_id,
                                const std::string& exchange);

    // 解析 inst_id 为 components
    static void parse_inst_id(const std::string& inst_id,
                              std::string& base,
                              std::string& quote,
                              std::string& type);
};

}  // namespace qt::data
