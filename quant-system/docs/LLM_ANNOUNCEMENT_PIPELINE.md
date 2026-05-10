# LLM 公告分析管线 — 设计方案

> 状态: 📋 方案记录，待排期实现
> 参考: 《AI量化交易：从0到1》第14课 LLM在量化中的应用

## 核心理念

LLM 作为信号增强层，分析非结构化文本（OKX 公告、X 帖子），输出结构化特征供 C++ 引擎消费。**LLM 不触碰风控/执行路径。**

## 数据源

| 来源 | 内容 | 获取方式 | 状态 |
|------|------|----------|------|
| OKX API `instruments` | 上下架状态变更 | WebSocket (已有) | ✅ 无需 LLM |
| OKX Help Center | 公告全文（原因、时间线） | 爬取 `okx.com/help/category/announcements` | ❌ 待实现 |
| @okx X/Twitter | 最快第一手公告 | X API v2 / Nitter RSS 桥接 | ❌ 待实现（付费） |

API 的 `state: "suspend"` 告知状态变化，但不含上下文——"delist 因监管压力" vs "delist 因流动性不足"对相关品种影响完全不同。Help Center 和 X 提供的就是这条信息。

## 架构

```
[OKX Help Center] ──每5min爬取──┐
[@okx X] ──X API / RSS桥接──────┤
                                │ 原始文本
                                ▼
                        ┌──────────────────┐
                        │  Kimi CLI (本地)  │
                        │  text → JSON      │
                        └────────┬─────────┘
                                 │ {"inst_id":"REN-USDT-SWAP",
                                 │  "event":"delist",
                                 │  "reason":"low_liquidity",
                                 │  "urgency":0.6, "sentiment":-0.7,
                                 │  "source_url":"..."}
                                 ▼
                        ┌──────────────────┐
                        │  共享状态文件     │
                        │  llm_events.json  │
                        └────────┬─────────┘
                                 │
                                 ▼
                        ┌──────────────────┐
                        │  C++ FeatureEngine │
                        │  + llm_event_type  │
                        │  + llm_sentiment   │
                        │  + llm_urgency     │
                        └────────┬─────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
      [Signal Agents]    [ComplianceChecker]  [RiskAgent]
      调整信号权重        自动加限制名单       提高波动率假设
```

## LLM 输出 JSON Schema

```json
{
  "events": [
    {
      "inst_id": "REN-USDT-SWAP",
      "event_type": "delist",
      "reason": "low_liquidity",
      "deadline": "2025-01-08T08:00:00Z",
      "sentiment": -0.7,
      "urgency": 0.6,
      "affected_instruments": ["REN-USDT-SWAP"],
      "summary": "OKX 将于2025年1月8日下架REN-USDT永续合约，原因为流动性不足",
      "source_url": "https://www.okx.com/help/okx-to-delist-ren-spot-pairs"
    }
  ],
  "generated_at": "2025-01-01T12:00:00Z"
}
```

## FeatureFrame 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `llm_event_active` | double (0/1) | 当前是否有针对该品种的公告事件 |
| `llm_event_type` | string→enum | delist / list / suspend / upgrade / policy |
| `llm_sentiment` | double [-1,1] | 事件情感 |
| `llm_urgency` | double [0,1] | 紧急程度（delist = 高，上新 = 中） |
| `llm_hours_to_deadline` | double | 距离截止时间的小时数 |

## 下游消费

- **ComplianceChecker**: delist 公告 → 自动 `add_restricted(inst_key)` 禁止开新仓
- **RiskAgent**: 高 urgency 事件 → 提高该品种波动率假设，收紧仓位上限
- **Signal Agents**: 负 sentiment → 倾向减仓信号；上新公告 → 观望不追高

## 实现步骤

1. **Python**: 爬取 OKX Help Center 公告列表，本地缓存文本
2. **Python**: Kimi CLI 批处理，`text → JSON`，写入 `logs/llm_events.json`
3. **C++**: `FeatureEngine::compute()` 读取 JSON，注入 FeatureFrame
4. **C++**: `ComplianceChecker` 消费 delist 事件，自动加限制
5. **扩展**: 接入 X/Twitter，达到更快的公告发现速度

## 成本

- Kimi CLI 本地运行，零 API 费用
- 调用频率: 每 5 分钟 1 次（仅在有新公告时触发 LLM）
- 延迟: 分钟级（可接受，公告事件非毫秒级交易）
