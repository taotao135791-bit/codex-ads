# UAC Quick Ops 数值决策

UAC Quick Ops 可以从用户明确提供的多日账户事实中，确定性地推导一项有边界的
tCPA、tROAS 或日预算建议。它不是效果预测器，不读取或修改 Google Ads，也不会把
经验阈值包装成平台规则。

最大单次变化、策略覆盖、多阶段计划、紧急纠错和 Numeric Replay 字段见
[数值安全策略](numeric-safety-policy.md)。

## 最短路径

源码 checkout 中可直接运行完全合成、无真实账户信息的示例：

```bash
python3 scripts/uac_experiment.py normalize \
  skills/ads-google-app/assets/UAC-QUICK-NUMERIC.example.yaml \
  --output /tmp/UAC-QUICK-NORMALIZATION.json

python3 scripts/uac_experiment.py decide \
  skills/ads-google-app/assets/UAC-QUICK-NUMERIC.example.yaml \
  --json
```

`normalize` 只做字段映射、单位转换和缺口记录，输出的是 normalization envelope，
不是决策。`decide` 接收完成 UAC 合同的结构化 YAML/JSON；在 Workspace 中，先由
Codex 补齐 envelope 中会改变结论的缺口，再使用通过校验的
`normalized/UAC-INPUT.yaml`。

该示例的安全结果是：保持 AC2.5，只把 tCPA 从 `5.0` 调到 `5.5`，日预算保持
`100`，三天或新增十个成熟事件后复查。`account_write` 和 `ledger_write` 始终为
`false`。

## 决策顺序

数值层按固定顺序执行：

1. 校验输入类型、有限数、非负数、比例和枚举；
2. 从多日事实推导成熟度、预算消耗、事件量稳定性、目标约束、价值可靠性和拆分能力；
3. 先应用测量、成熟度、近期修改和值信号硬门禁；
4. 识别一个主要约束；
5. 用账户的当前值与业务上限/下限生成有边界的候选值；
6. 应用实际生效的版本化策略，限制单次增加或降低幅度；
7. 超过上限时只建议 staged plan 的第一阶段；
8. 普通运营只选择一个数值变量；
9. 根据权限把理想建议转换成当前可执行动作或客户请求；
10. 输出一张只显示唯一执行建议的短卡片，并在 JSON 中保留计算证据。

同样版本和同样输入会得到同样结果。确定性不等于因果、增量或未来效果保证。

## 最小数值事实

### tCPA

- `goal.target_cpa`：当前 tCPA；
- `goal.maximum_acceptable_cpa`：业务可接受的成熟 CPA 上限；
- `facts.daily_budget`：当前日预算；
- `facts.daily_series[]`：至少包含多日 `spend` 和 `mature_events`；
- `facts.metrics.mature_conversions` 或等价成熟转化事实；
- `facts.metrics.mature_actual_cpa`，或足以用成熟花费/转化计算 CPA 的事实；
- `maturity` 中的观察天数、最低天数、转化延迟、近期修改天数和修改后成熟事件；
- `permissions` 中的 `bid`、`budget` 权限。

### tROAS

将 tCPA 字段替换为：

- `goal.target_roas`：当前 tROAS；
- `goal.minimum_acceptable_roas`：业务可接受的成熟 ROAS 下限；
- `facts.metrics.mature_revenue` 和成熟 ROAS/花费；
- 价值缺失、币种、Google/MMP/后端差异、退款上限、订阅续费口径和重复事件证据。

tROAS 内部使用比率：`3.0` 表示 `300%`。Normalization 同时接受 `3.0` 和
`"300%"`，并统一为 `3.0`。普通 rate 字段使用 `0..1`，也可在 normalization
入口使用百分号。tCPA、预算和收入必须使用一致币种；工具不会自动做汇率换算。

`goal.daily_budget_cap` 是预算建议的业务硬上限。缺少 CPA 上限、ROAS 下限或预算
上限时，系统返回 `null`/保持不变，而不是发明一个数字。

## 推导信号

以下阈值是可复现诊断启发式，不是 Google 的保证或行业定律：

- 成熟度同时检查观察天数、成熟事件量、转化延迟、近期修改冷却期和修改后事件量。
  冷却窗口仍未满足时，同时修改多个变量会阻止成熟结论；窗口和成熟量都满足后不会永久阻塞。
- 预算消耗率使用多日平均花费除以当前日预算。低于 `0.75` 标记为
  `UNDER_DELIVERING`；达到 `0.90` 且账户明确报告 budget limited 时才标记为
  `BUDGET_CONSTRAINED`。当前值已越过业务硬边界时，边界优先于普通优化；
  如果业务边界与单次幅度上限没有安全交集，则返回 `null` 并请求人工处理，
  不会假装一次性跳到边界。
- 事件量必须满足账户声明的最低日成熟事件量。默认策略中变异系数高于
  `0.50`，或零事件日超过 `20%`，会标记为量够但波动；这些是可覆盖 heuristic。
- tCPA 下，低消耗、成熟 CPA 在业务上限内且接近当前目标，才可能判断目标过紧。
  成熟 CPA 已超过业务上限时，不会为了消耗而放宽目标。
- tROAS 下，只有成熟价值、币种、去重和平台间金额对账可靠时才输出目标数字。
- 拆分可行性使用账户声明的每 Campaign 最低预算和最低成熟事件密度，返回
  `SPLIT_FEASIBLE`、`SPLIT_BORDERLINE`、`SPLIT_NOT_FEASIBLE` 或
  `INSUFFICIENT_EVIDENCE`，不伪装成流量预测。

如果推导信号与旧 `quick_ops` 手工标签冲突，有数值证据的推导结果优先用于门禁。
`quick_ops.bid_budget.recommended_target` 和 `recommended_daily_budget` 只作为旧输入提示，
不会绕过门禁；被忽略的字段会列在 `legacy_hints_ignored`。

## 候选值与唯一动作

账户证据候选值先位于当前值和业务边界之间，再受当前策略的单次变化上限约束。
系统根据 `goal.optimization_priority` 的
`scale`、`balanced` 或 `efficiency` 选择区间内的推荐位置，并按当前值约 `1%`
的步长（最小 `0.01`）量化。JSON 保留：

- `conservative_value`：更接近当前值；
- `recommended_value`：本次唯一建议；
- `aggressive_value`：最靠近业务边界的候选；
- `rollback_value` / `rollback_condition`：原值和成熟回滚门槛。

操作卡只显示 `recommended_value`。其他候选是审计上下文，不是三项并行建议。
超过单次上限时，`numeric_safety` 记录原始候选、业务有界候选、受限后候选、
实际策略版本和 staged plan。后续阶段均为 `REQUIRES_FRESH_REVIEW`，不会预先执行。

普通运营不会同时改目标和预算：

- 目标是主要约束时，预算保持当前值；
- 预算是主要约束且成熟效率仍在业务边界内时，目标保持当前值；
- Campaign 层级正在切换、并行或回退时，目标和预算都保持不变；
- Campaign 拆分不得捆绑总预算增加；需先单独完成受幅度限制的预算调整并重新取数；
- 多变量紧急处置必须由人明确确认，并标记为运营干预而非有效实验。

已确认的配置误填可分类为 `OPERATIONAL_CORRECTION`，但必须同时提供历史批准值、
一致的回退目标、配置错误证据与人工确认，且目标仍在业务边界内。只有这种情况
才可超过普通幅度上限；它仍不会自动写账户。

## 输出合同

Quick Decision schema 版本仍是 `1.0`。旧的、不含数值扩展字段的 `1.0` 输出继续
有效；一旦出现任一数值扩展字段，下面八个字段必须成组出现：

| 字段 | 含义 |
| --- | --- |
| `constraint_analysis` | 一个主要约束及各信号状态 |
| `target_recommendation` | tCPA/tROAS 候选、唯一建议、复查门槛和回滚条件 |
| `budget_recommendation` | 日预算候选、唯一建议、复查门槛和回滚条件 |
| `split_feasibility` | 拆分后的事件密度与预算可行性 |
| `derived_signals` | 成熟度、消耗、事件、目标、价值、候选事件和素材质量信号 |
| `calculation_evidence` | 计算所使用的证据及其类型 |
| `heuristics_used` | 本次实际使用的启发式标签 |
| `legacy_hints_ignored` | 被安全忽略的旧推荐值字段 |

每条 calculation evidence 明确属于：

- `ACCOUNT_EVIDENCE`：用户提供或由其事实直接计算的账户证据；
- `BUSINESS_CONSTRAINT`：用户声明的 CPA/ROAS/预算边界；
- `PLATFORM_GUIDANCE`：仅用于风险控制的平台指导；
- `HEURISTIC`：公开标记的确定性经验规则；
- `INSUFFICIENT_EVIDENCE`：阻止数值建议的缺口。

这些类型不能互相冒充，账户证据也不能自动升格成全局规则。

## 权限语义

`target_recommendation.recommended_value` 或
`budget_recommendation.recommended_value` 表示通过事实门禁的理想建议；
`execution` 表示当前权限下是否可立即准备该动作。兼容字段 `bid_decision` 和
`budget_decision` 只展示当前可执行投影：

- 有权限：保留唯一建议，并标记 `executable_now: true`；
- 需客户批准/数据：保持当前值，生成精确客户请求；
- 只读或平台受限：保持当前值，不把不可执行建议写成“现在执行”；
- 所有情况：真实账户写入仍需逐项人工确认。

数值决策不会创建实验、写实验台账或直接修改账户。若要验证因果，必须另行进入
Experiment 模式并满足单变量、基线、成熟度、护栏、成功/失败和回滚合同。

## 私有 Replay 校准

真实数值回放继续只放在被 Git 忽略的 `workspaces/<project>/replays/`。可选的
`evaluation.yaml.numeric_evaluation` 用十二个完整字段记录策略版本、原始/最终值、
人工执行值、方向、幅度、cap、staged plan、回退、激进/保守和成熟结果。旧五/六文件
Replay 仍可读取；不含该字段时不进入新的数值校准分母。

新增汇总包括方向准确率、幅度误差中位数、策略截断率、过激/过保守率、回退率、
阶段计划完成率和正确 no-action 率。人工未执行、结果未成熟、执行偏离或被污染样本不会进入
执行后方向/幅度效果分母。Replay 不会自动修改策略；策略变更必须人工确认并升级版本。

Replay 只用于同一账户上下文中的小样本校准，不是因果证明，也不能把不同账户混在
一起推出统一调整比例。没有私有真实样本时，这些指标应保持空分母，而不是用公开
合成 fixture 冒充效果证据。

## 不输出数值的情况

以下任一情况都可以安全返回 `null`、`WAIT` 或 `NO_CHANGE`：

- 多日成熟数据或业务边界缺失；
- 转化延迟未成熟，或近期修改尚未冷却；
- 测量、币种、价值、去重或金额对账不可靠；
- AC3.0 所需价值信号不可靠；
- 当前结果没有证明目标或预算是主要约束；
- 拆分后预算或成熟事件不足；
- 建议会与另一个普通变量或层级变化同时发生；
- 权限不足，且没有可安全执行的替代动作。

这不是“没有给建议”，而是明确保护账户免受伪精确和不可归因修改。

## 隐私与公开示例

`UAC-QUICK-NUMERIC.example.yaml` 是完全合成 fixture。公开示例不得包含真实客户名、
账户 ID、Campaign ID、邮箱、主机路径、访问令牌、原始导出片段或可反推真实业务的
组合数据。真实数据应放在被 Git 忽略的私有 Workspace 中。
