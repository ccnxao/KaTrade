#include "qt/data/instrument_master.hpp"

#include <algorithm>
#include <sstream>

namespace qt::data {

// ---- 内部工具 --------------------------------------------------------

std::string InstrumentMaster::make_key(const std::string& inst_id,
                                        const std::string& exchange) {
    return inst_id + "." + exchange;
}

void InstrumentMaster::parse_inst_id(const std::string& inst_id,
                                      std::string& base,
                                      std::string& quote,
                                      std::string& type) {
    // 格式: BASE-QUOTE-TYPE  (e.g., BTC-USDT-SWAP, ETH-USD-SPOT)
    auto dash1 = inst_id.find('-');
    if (dash1 == std::string::npos) {
        base = inst_id;
        return;
    }
    base = inst_id.substr(0, dash1);

    auto dash2 = inst_id.find('-', dash1 + 1);
    if (dash2 == std::string::npos) {
        quote = inst_id.substr(dash1 + 1);
        return;
    }
    quote = inst_id.substr(dash1 + 1, dash2 - dash1 - 1);
    type = inst_id.substr(dash2 + 1);
}

// ---- 构造函数 --------------------------------------------------------

InstrumentMaster::InstrumentMaster() = default;

// ---- 查询 ------------------------------------------------------------

const ContractSpec* InstrumentMaster::lookup(const std::string& inst_key) const {
    auto it = specs_.find(inst_key);
    return it != specs_.end() ? &it->second : nullptr;
}

const ContractSpec* InstrumentMaster::lookup(const std::string& symbol,
                                              const std::string& exchange) const {
    // 尝试几种 key 格式
    // 1. symbol 本身可能已经包含完整的 inst_id
    auto it = specs_.find(symbol + "." + exchange);
    if (it != specs_.end()) return &it->second;

    // 2. 遍历查找匹配 base+exchange 的
    for (const auto& [key, spec] : specs_) {
        if (spec.base_ccy == symbol) {
            auto dot = key.rfind('.');
            if (dot != std::string::npos && key.substr(dot + 1) == exchange) {
                return &spec;
            }
        }
    }
    return nullptr;
}

double InstrumentMaster::tick_size(const std::string& inst_key, double fallback) const {
    auto* spec = lookup(inst_key);
    return spec ? spec->tick_size : fallback;
}

double InstrumentMaster::lot_size(const std::string& inst_key, double fallback) const {
    auto* spec = lookup(inst_key);
    return spec ? spec->lot_size : fallback;
}

double InstrumentMaster::min_notional(const std::string& inst_key, double fallback) const {
    auto* spec = lookup(inst_key);
    return spec ? spec->min_notional : fallback;
}

double InstrumentMaster::max_leverage(const std::string& inst_key, double fallback) const {
    auto* spec = lookup(inst_key);
    return spec ? spec->max_leverage : fallback;
}

bool InstrumentMaster::is_spot(const std::string& inst_key) const {
    auto* spec = lookup(inst_key);
    return spec && spec->inst_type == "SPOT";
}

bool InstrumentMaster::is_perpetual(const std::string& inst_key) const {
    auto* spec = lookup(inst_key);
    return spec && spec->inst_type == "SWAP";
}

bool InstrumentMaster::is_derivative(const std::string& inst_key) const {
    auto* spec = lookup(inst_key);
    return spec && (spec->inst_type == "SWAP" || spec->inst_type == "FUTURES"
                    || spec->inst_type == "OPTION");
}

std::string InstrumentMaster::base_ccy(const std::string& inst_key) const {
    auto* spec = lookup(inst_key);
    return spec ? spec->base_ccy : "";
}

std::string InstrumentMaster::quote_ccy(const std::string& inst_key) const {
    auto* spec = lookup(inst_key);
    return spec ? spec->quote_ccy : "";
}

// ---- 注册 ------------------------------------------------------------

void InstrumentMaster::register_spec(ContractSpec spec) {
    // 同时注册 inst_id.exchange 和 base_ccy 两种 key
    // 从 inst_id 推断 exchange (默认 OKX)
    // R39: 从 inst_id 推断 exchange（默认 OKX）
    std::string exchange = "OKX";
    auto dot = spec.inst_id.rfind('.');
    if (dot != std::string::npos && dot + 1 < spec.inst_id.size()) {
        exchange = spec.inst_id.substr(dot + 1);
        // 避免 inst_id 已含 .OKX 时拼出 xxx.OKX.OKX
        if (spec.inst_id.find(exchange + ".") == std::string::npos) {
            // exchange 段不含点，合法
        } else {
            exchange = "OKX";  // 回退默认
        }
    }
    specs_[make_key(spec.inst_id, exchange)] = spec;
    // 也注册 inst_id 本身作为 key（不带交易所后缀）
    if (specs_.find(spec.inst_id) == specs_.end()) {
        specs_[spec.inst_id] = spec;
    }
}

// ---- 列举 ------------------------------------------------------------

std::vector<std::string> InstrumentMaster::all_instruments() const {
    std::vector<std::string> result;
    for (const auto& [key, spec] : specs_) {
        // 只返回带交易所后缀的 key
        if (key.find('.') != std::string::npos) {
            result.push_back(key);
        }
    }
    return result;
}

std::vector<std::string> InstrumentMaster::instruments_by_type(
    const std::string& inst_type) const {
    std::vector<std::string> result;
    for (const auto& [key, spec] : specs_) {
        if (spec.inst_type == inst_type && key.find('.') != std::string::npos) {
            result.push_back(key);
        }
    }
    return result;
}

// ---- OKX 预置数据 ----------------------------------------------------

std::vector<ContractSpec> InstrumentMaster::okx_default_specs() {
    return {
        // ---- 现货 ----
        {"BTC-USDT",    "BTC",  "USDT",  "SPOT",  0.01,  0.00001, 1.0, 10.0,   0.0, true},
        {"ETH-USDT",    "ETH",  "USDT",  "SPOT",  0.01,  0.0001,  1.0, 10.0,   0.0, true},
        {"SOL-USDT",    "SOL",  "USDT",  "SPOT",  0.01,  0.01,    1.0, 10.0,   0.0, true},
        {"BNB-USDT",    "BNB",  "USDT",  "SPOT",  0.01,  0.001,   1.0, 10.0,   0.0, true},
        {"XRP-USDT",    "XRP",  "USDT",  "SPOT",  0.0001,0.1,     1.0, 10.0,   0.0, true},
        {"DOGE-USDT",   "DOGE", "USDT",  "SPOT",  0.00001,1.0,    1.0, 10.0,   0.0, true},
        {"ADA-USDT",    "ADA",  "USDT",  "SPOT",  0.0001,0.1,     1.0, 10.0,   0.0, true},
        {"AVAX-USDT",   "AVAX", "USDT",  "SPOT",  0.001, 0.01,    1.0, 10.0,   0.0, true},

        // ---- 永续合约 (SWAP) ----
        {"BTC-USDT-SWAP",  "BTC",  "USDT",  "SWAP",  0.1,   0.001,  0.01,  1.0,  100.0, true},
        {"ETH-USDT-SWAP",  "ETH",  "USDT",  "SWAP",  0.01,  0.01,   0.01,  1.0,  100.0, true},
        {"SOL-USDT-SWAP",  "SOL",  "USDT",  "SWAP",  0.001, 0.1,    0.01,  1.0,  100.0, true},
        {"BNB-USDT-SWAP",  "BNB",  "USDT",  "SWAP",  0.01,  0.01,   0.01,  1.0,  75.0,  true},
        {"XRP-USDT-SWAP",  "XRP",  "USDT",  "SWAP",  0.0001,1.0,    0.01,  1.0,  75.0,  true},
        {"DOGE-USDT-SWAP", "DOGE", "USDT",  "SWAP",  0.00001,10.0,  0.01,  1.0,  75.0,  true},
        {"ADA-USDT-SWAP",  "ADA",  "USDT",  "SWAP",  0.0001,1.0,    0.01,  1.0,  75.0,  true},
        {"AVAX-USDT-SWAP", "AVAX", "USDT",  "SWAP",  0.001, 0.1,    0.01,  1.0,  75.0,  true},

        // ---- 常用计价货币对（反向）----
        {"ETH-BTC",       "ETH",  "BTC",   "SPOT",  0.00001,0.0001, 0.0001,10.0,  0.0, true},
        {"SOL-BTC",       "SOL",  "BTC",   "SPOT",  0.000001,0.001, 0.0001,10.0,  0.0, true},
    };
}

InstrumentMaster InstrumentMaster::okx_default() {
    InstrumentMaster master;
    for (auto& spec : okx_default_specs()) {
        master.register_spec(std::move(spec));
    }
    return master;
}

}  // namespace qt::data
