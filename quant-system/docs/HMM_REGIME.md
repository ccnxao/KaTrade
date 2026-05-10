# 市场状态检测系统 — HMM Regime

## 架构

```
MetaAgent (确认延迟3周期 / 过渡混合5周期 / 误判恢复)
  ├─ RuleBasedRegimeAgent (硬阈值, 4特征)
  ├─ HMMRegimeAgent (高斯HMM, 1特征, 批量k-means)
  └─ OnlineEMRegimeAgent (Student-t, 多特征, 在线EM)
```

配置: `regime.detector = rule | hmm | online_em`

## OnlineEM v1

基于三篇论文:
- N'DRI et al. (2024) — Student-t 发射分布优于 Gaussian
- Cappé (2011, JCGS) — 在线 EM 算法
- Mongillo & Denève (2008) — 指数遗忘因子

### 关键设计决策

| 决策 | 理由 |
|------|------|
| Student-t ν=4 | 肥尾处理金融极端值 |
| 学习用硬分配(在线k-means) | 软EM在金融数据上不可靠，状态坍缩 |
| 推断用软Student-t发射概率 | 保留完整概率分布 |
| M-step n<0.01跳过更新 | 保护未分配状态的先验均值 |
| 方差地板1e-3 | 防止概率坍缩为100% |
| 推断不加转移先验 | 跨品种调用共享转移状态会污染 |
| 先验初始化均值(10%/22%/38%) | 打破对称性，代替随机初始化 |
| 自适应ρ∈[0.90,0.99] | 高不确定→加速遗忘 |

### 冷启动

```
0-9 tick:    Uncertain conf=10% (参数随机)
10-29 tick:  Uncertain conf=20% (初步分离)
30-49 tick:  Uncertain conf=35% (趋稳)
50+ tick:    正常输出 (oem_v1)
```

### 输出字段

- `regime`: Trending / MeanReverting / Crisis / Uncertain
- `confidence`: 主导状态置信度
- `tp/rp/dp`: T/M/D 完整概率分布
- `mw/rw/dw`: 策略资金分配权重
- `model_version`: oem_v1 / oem_cold / oem_warmup / oem_uncertain

### 配置

```ini
regime.detector=online_em
regime.hmm_states=3
regime.oem_dim=2   # 1=vol, 2=vol+ADX
```
