# UAC 数值安全策略

这份文档说明 Quick Ops 如何限制 tCPA、tROAS 和日预算的单次变化，
以及如何在不自动投放的前提下生成多阶段计划。数值策略是可校准的
heuristic，不是 Google 平台保证，也不会覆盖业务边界、测量质量、权限或人工确认。

## 安全计算顺序

普通数值建议按下列交集收口：

```text
最终推荐值 =
账户证据计算值
∩ 业务边界
∩ 最大单次变化幅度
∩ 权限边界
```

具体顺序是：先校验成熟度、转化延迟、测量和价值信号，再由账户事实计算
原始候选，收紧到 CPA/ROAS/预算业务边界，最后应用当前策略的单次幅度上限
和权限投影。任一硬门禁失败都可返回 `null`、`WAIT` 或 `NO_CHANGE`。

例如，当前 tCPA 为 `2`、业务上限为 `10`、账户证据候选为 `5`、普通单次
增加上限为 `20%` 时，第一阶段不得超过 `2.4`。业务上限较宽不等于可以
一次跳到 `5`。

## 默认策略与覆盖顺序

内置 `uac-numeric-policy-v1` 对 tCPA、tROAS 和日预算的增加与降低都使用
`20%` 默认上限。这是明确标记的 heuristic，不是所有账户的绝对值。

策略合并顺序为：

1. 安装包内的版本化默认策略；
2. 项目目录的 `policies/uac-numeric-policy.yaml` 或
   `policies/uac-signal-policy.yaml`；
3. 已初始化私有 Workspace 的同名 `policies/` 文件。

Workspace 覆盖项目，项目覆盖默认。每层覆盖都必须使用新的
`policy_version`，并用 `extends` 精确指向上一层的有效版本。例如：

```yaml
schema_version: "1.0"
policy_version: project-numeric-v2
policy_kind: uac_numeric
policy_mode: override
extends: uac-numeric-policy-v1

numeric_change_limits:
  target_cpa:
    normal_max_increase_percent: 10
```

只覆盖需要校准的字段；未声明字段继承上一层。当项目和 Workspace 都有
覆盖时，Workspace 文件的 `extends` 必须指向项目策略的版本。

## 校验与安全降级

策略文件同时受 `uac-heuristic-policy.schema.json` 和运行时合同校验。下列情况
会明确拒绝运行，不会静默忽略：

- 负数、非有限数或超过 `100%` 的比例；
- 错误的 `policy_kind`、`policy_mode` 或 `extends`；
- 重复或不合法的版本号；
- 未支持字段、类型错误、信号阈值顺序错误；
- 代理事件权重总和不是 `100%`。

缺少可选的项目/Workspace 覆盖时继续使用默认策略，因此旧 Workspace 不需要
迁移。如果安装包内的数值默认策略意外缺失，运行时会记录 degraded 警告并使用
`0%` 安全上限：保持当前值，不继续数值调整。

状态枚举、权限分类、隐私规则、人工确认、AC2.5 不能解析为 tCPA 2.5，以及价值
不可靠时禁止价值优化，仍是代码中的产品安全合同，不允许由策略文件改写。

## 操作分类

| `operation_classification` | 用途 | 幅度规则 |
| --- | --- | --- |
| `NORMAL_OPTIMIZATION` | 成熟账户的普通扩量或效率调整 | 必须遵守当前策略上限 |
| `STAGED_OPTIMIZATION` | 证据候选超过单次上限 | 只给第一阶段，后续阶段重新审核 |
| `OPERATIONAL_CORRECTION` | 已确认的误填/配置偏离 | 证据完整时可超过普通上限 |
| `EMERGENCY_INTERVENTION` | 明确严重运营事故 | 允许多变量，但禁止因果归因 |

`OPERATIONAL_CORRECTION` 不是普通扩量的快捷通道。输入必须在
`quick_ops.operational` 中同时包含：

```yaml
operation_classification: OPERATIONAL_CORRECTION
affected_variable: target_cpa
historical_approved_value: 5.0
rollback_target: 5.0
configuration_error_evidence: approved change record differs from live setting
configuration_error_confirmed: true
human_confirmation: true
```

历史批准值和回退目标必须一致，且该值仍在声明的业务边界内。少任一证据都停止精确
纠错。输出会同时保留 `numeric_safety.correction_evidence`、推荐项的
`rollback_value` / `rollback_condition` 和顶层纠错回退摘要，方便事后审计。所有纠错
依然是只读建议，不会直接写 Google Ads。

`EMERGENCY_INTERVENTION` 要求明确的紧急确认和多变量清单；还应记录可审计的事故原因。
输出强制标记 `NOT_A_VALID_EXPERIMENT` 与 `ATTRIBUTION_WILL_BE_CONFOUNDED`。
不得把该记录发布为因果学习。

## 多阶段计划

当业务有界候选仍超过普通单次上限时，`numeric_safety` 会保留原始候选、
受限后值和一份 `staged_plan`：

```yaml
numeric_safety:
  policy_version: uac-numeric-policy-v1
  raw_candidate: 8.0
  business_bounded_candidate: 8.0
  change_limited_candidate: 6.0
  final_recommendation: 6.0
  current_change_percent: 20.0
  capped_by_policy: true
  staged_adjustment_required: true
  operation_classification: STAGED_OPTIMIZATION
  limit_reasons: [max_single_target_change_percent]
  staged_plan:
    final_candidate: 8.0
    immediate_stage: 1
    stages_fully_enumerated: true
    remaining_stages_require_fresh_recalculation: false
    future_stages_require_fresh_review: true
    automatic_execution: false
    stages:
      - stage: 1
        target: 6.0
        immediate: true
        approval_state: PROPOSED
        automatic_execution: false
        review_after_days: 3
        minimum_mature_events: 10
      - stage: 2
        target: 7.2
        immediate: false
        approval_state: REQUIRES_FRESH_REVIEW
        automatic_execution: false
        condition:
          fresh_mature_data_required: true
          conversion_delay_mature: true
          mature_efficiency_within_business_limit: true
          delivery_improved_or_control_objective_met: true
          no_unreviewed_concurrent_change: true
      - stage: 3
        target: 8.0
        immediate: false
        approval_state: REQUIRES_FRESH_REVIEW
        automatic_execution: false
        condition:
          fresh_mature_data_required: true
          conversion_delay_mature: true
          mature_efficiency_within_business_limit: true
          delivery_improved_or_control_objective_met: true
          no_unreviewed_concurrent_change: true
```

只有第一阶段是当前建议。后续目标是待审候选；每一阶段都必须重新读取成熟数据、
等待转化延迟、重验业务边界和并发修改。`automatic_execution` 始终是 `false`。

## 什么时候不给精确值

下列任一情况会安全停止或保持当前值：

- 缺少成熟多日数据、必要业务边界或主要约束证据；
- 转化延迟未成熟，或目标/预算刚修改后的冷却条件未满足；
- 测量、去重、币种、退款口径或金额对账不可靠；
- tROAS/AC3.0 所需的价值信号不可靠；
- 业务边界和单次幅度限制之间没有安全交集；
- 当前普通操作需要同时改多个数值变量；
- Campaign 拆分计划试图同时提高总预算；拆分只能在当前总预算与业务上限内重新分配；
- 策略降级为 `0%` 变化上限；
- 权限边界不允许当前操作。

权限不足时，结构化输出可保留通过事实门禁的理想候选，但用户可执行投影和
`numeric_safety.final_recommendation` 会回到当前值，并输出客户批准或数据请求。

## 信号策略

`uac-signal-policy-v1` 只包含适合根据真实数据校准的 heuristic：

- value 金额差异、缺失、币种一致性和波动阈值；
- 事件日数、变异系数和零事件日阈值；
- Campaign 拆分的默认事件密度与边缘容量；
- 素材默认样本量、代理事件评分权重和默认成熟窗口。

默认为 `null` 的账户特定阈值不会被自动猜测；输入仍需声明该账户的标准。

## 私有 Replay 校准

真实数值 Replay 仍只能放在被 Git 忽略的
`workspaces/<project>/replays/`。如需进入数值校准，由人工在该案例的
`evaluation.yaml` 中填写完整字段：

```yaml
numeric_evaluation:
  policy_version: uac-numeric-policy-v1
  raw_candidate: 6.0
  final_recommendation: 5.5
  human_executed_value: 5.5
  direction_correct: true
  magnitude_error_percent: 0.0
  capped_by_policy: true
  staged_plan_used: true
  rollback_triggered: false
  recommendation_was_too_aggressive: false
  recommendation_was_too_conservative: false
  mature_result_available: true
```

Replay 汇总 `direction_accuracy`、`median_magnitude_error`、
`policy_cap_trigger_rate`、`too_aggressive_rate`、`too_conservative_rate`、
`rollback_rate`、`staged_plan_completion_rate` 和 `no_action_correct_rate`。

被拒绝、人工未执行、结果未成熟、执行偏离或多变量污染的案例不进入方向和幅度效果
分母。不同产品和市场应分开观察。少量账户样本不会自动改写全局策略；任何阈值修改
都必须经人工确认、更新 `policy_version` 并重新运行回归。系统不实现在线学习或策略自动修改。
