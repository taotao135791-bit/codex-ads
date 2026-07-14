# Codex Ads 快速启动

Codex Ads 是一个 Codex-first 广告决策工作流。**不用背 `/ads` 命令，也不用先学 YAML**：把导出表、表格、截图或只读后台交给 Codex，再复制一句自然语言。

## 先安装稳定通道

`v1.9.2` tag 当前需要先发布；发布后推荐固定这个版本：

```bash
curl -fsSL https://raw.githubusercontent.com/taotao135791-bit/codex-ads/v1.9.2/install.sh | bash -s -- --ref=v1.9.2
```

Windows：

```powershell
irm https://raw.githubusercontent.com/taotao135791-bit/codex-ads/v1.9.2/install.ps1 -OutFile install.ps1
.\install.ps1 -Ref v1.9.2
```

`main` 是可能不稳定的滚动开发快照，不是默认稳定通道。需要回滚时，重新安装一个真实存在、已验证的旧 tag；这不会撤销广告账户操作或自动降级 ledger `1.1`，所以 schema 迁移前必须保留 `1.0` 备份。完整安装和回滚命令见 [README](README.md#安装)。

## 第一次使用

先打开 Codex，然后说：

```text
我要用 Codex Ads 做广告优化。之后请默认只读看数，不修改广告后台；如果需要日报、周报或甲方汇报，请先问我模板在哪里。
```

如果你已经打开广告后台，可以这样说：

```text
我已经登录广告后台了。请只读看一下当前账号，先告诉我你要看哪些页面，不要修改任何设置。
```

## 先记住这些边界

自然语言路径包含 Agent 推理：Codex 负责理解上下文、整理证据和追问缺口。Doctor、normalize、UAC 规则、台账校验、迁移和 replay 是本地确定性能力；它们不调用广告或模型 API，也不会修改平台。

- 不保证增长、降低 CPA 或提高 ROAS。
- 不替代产品、支付墙、SDK/埋点、MMP 或后端回传。
- 不自动登录或改账户；真实写入需要对那一项操作明确确认。
- Fixture 和公开 replay 是合成/匿名回归样例，不是真实效果证明。
- 单账户经验默认不能全局推广。数据不足时，正确建议可以是不修改账户。

## 日常常用话术

新手接项目：

```text
我刚接了一个代投项目，不知道先看哪里。请先用五个问题问我：
项目类型、甲方最终 KPI、哪些不能改、当前最头疼的现象、我现在能提供什么数据。
```

账户体检：

```text
只读看一下这个广告账户，帮我判断预算消耗、转化质量、目标设置和下一步优化动作。不要修改任何设置。
```

代投窄权限诊断：

```text
我们是代投，KPI 和产品方向都不能改。现在安装很多但支付很少，请只读判断：
投放侧还能动哪些杠杆，哪些问题需要甲方配合验证，以及我该怎么跟甲方解释。
```

每日巡检：

```text
只读看一下昨天的数据，帮我找今天必须处理的 3 件事。
重点看消耗、支付/线索、CPA/ROAS、素材拒审、追踪异常、国家/设备/版位异常。
```

Google Ads 深度分析：

```text
只读看一下当前 Google Ads 账号，重点看转化目标、广告系列结构、预算消耗、国家/设备/素材表现，并给出内部优化清单和给甲方的解释。
```

Google UAC 实验闭环：

```text
这是 Google App campaign。我只能改预算、出价目标和素材，不能改产品、支付墙、
SDK、MMP、后端事件或商店页。请先检查支付回传、学习资格和转化延迟，再判断当前
是否有优化空间。如果证据足够，只生成一个单变量实验；否则明确告诉我先补什么数据、
等待多久，以及哪些设置不要动。
```

Google UAC 日常 Quick Ops（不会默认生成完整报告或实验）：

```text
1. 我现在跑 AC2.5，直接告诉我继续、调整、并行、切换还是等待。
2. 现有 AC2.5 还健康，新素材要加入现有还是再开一个 AC2.5？
3. 支付量不多，我现在能不能进入 AC3.0？先检查 value、currency 和金额对账。
4. 支付价值回传稳定，预算也够，AC2.5 和 AC3.0 是否应该并行？
5. 我只有素材权限，不能建 campaign、改事件、预算或出价；现在能执行什么？
6. 我附上了多日成熟数据、当前 tCPA/预算和业务 CPA 上限；只给一个数值建议，另一个变量保持不变。
```

这些 AC 名称是团队内部口径，不是 tCPA 数值。Codex 会优先核对真实账户设置和项目 glossary；没有确认口径、价值信号或权限时，保持当前而不是强行切换。

想先看可复现样例，可直接使用完全合成的 [`UAC-QUICK-NUMERIC.example.yaml`](skills/ads-google-app/assets/UAC-QUICK-NUMERIC.example.yaml)；它演示保持 AC2.5、只改 tCPA、预算不动和成熟回滚门槛。

UAC 项目不需要背命令，按进度直接说下面五句话即可：

```text
1. 帮我为这个 UAC 账户初始化项目。
2. 分析本周 UAC 数据，告诉我该不该动。（同时附上数据）
3. 根据这次分析创建一个实验草案。
4. 我已在今天 <具体时间和时区> 执行了 <实际改动>，没有/还有 <其他改动>，请记录。
5. 复盘当前实验。（同时附上同口径的最新数据）
```

Codex 会把真实资料放进默认忽略的私有 workspace，内部完成字段整理、Doctor、分析和台账校验。第 3 步先只展示草案；只有你确认草案后才写入本地台账。写入台账也不等于授权修改 Google Ads，真实账户操作仍需另一次精确确认。

导出日报：

```text
按甲方日报模板整理今天的数据。我已经打开广告后台和模板了，你只读识别模板结构并生成日报，不要写回模板，不要发送给甲方。
```

适配甲方模板：

```text
这个客户日报模板和其他客户不一样。请只读识别模板结构，先生成字段映射表，
标出哪些字段能从广告后台拿、哪些需要后端/MMP/CRM，再输出可粘贴的日报草稿。
```

素材周报：

```text
看本周素材表现，按甲方素材周报模板输出：哪些继续投，哪些降预算或停，哪些角度疲劳，下周应该补什么素材。
```

素材需求单：

```text
根据本周素材表现，帮我给设计/剪辑整理下周素材需求单。
每条写清目标、平台、尺寸、角度、画面、文案、验收标准。
```

甲方沟通稿：

```text
把刚才的优化结论改成给甲方看的版本：少讲平台术语，多讲原因、风险、下一步动作和预期影响。
```

异常排查：

```text
支付/线索突然掉了。先不要建议我改预算，帮我按数据延迟、追踪、审核、消耗、国家/版位/素材结构和产品侧问题逐步排查。
```

## 只有预算、tCPA 和素材权限：9 步闭环

1. **导入**：附上导出表或粘贴数据，包含日期、campaign/OS/国家粒度、浅层到支付指标、素材、最近改动、转化延迟和对账状态。
2. **声明权限**：明确“只能改预算、tCPA、素材”，并把产品、支付墙、SDK、MMP、后端回传和商店页列为不可触碰项。
3. **Doctor**：让 Codex 运行只读 Doctor，先检查版本、依赖、输入、台账、schema 和未完成实验。
4. **分析**：运行 UAC 分析，查看测量、学习资格、权限和优化可行性。
5. **判断行动**：只在证据和成熟度通过门禁时才进入实验；否则补数据、请求客户支持、等待或不操作。
6. **创建与确认实验**：先展示一个未批准的单变量草案，不写台账；用户确认草案后才追加本地 `proposed` 记录。它不会修改 Google Ads；人工另行批准并在平台执行后才记为 `observing`，拒绝则记为 `cancelled`。
7. **等待成熟**：等待最小观察天数、成熟转化量和转化延迟，不叠加第二个变量。
8. **回填与复盘**：回填护栏、并发变化、成熟指标和规则判定，运行 `validate-ledger` 和 `review-ledger`，再决定继续、停止、回滚或延长观察。
9. **加入历史 replay**：隐私检查后才保存匿名案例。Replay 只评估工作流，不证明真实效果；下一轮使用从未出现过的新实验 ID。

## 高级：确定性检查和 schema 1.1

普通用户可以让 Codex 运行下面的工具。以下是源码 checkout 命令；一行安装的相对路径不在当前项目里，默认安装脚本在 `~/.codex/skills/ads/scripts/`。

```bash
# 创建默认忽略的私有项目；把原始摘要放进它的 input/ 后继续
python3 scripts/uac_experiment.py init-workspace my-uac-project
python3 scripts/uac_experiment.py normalize --workspace "workspaces/my-uac-project"

# 只读项目健康检查与分析；分析默认不写台账
python3 scripts/uac_experiment.py doctor --workspace "workspaces/my-uac-project"
python3 scripts/uac_experiment.py analyze --workspace "workspaces/my-uac-project"
python3 scripts/uac_experiment.py decide --workspace "workspaces/my-uac-project"

# 旧显式路径仍兼容：只映射对象型 JSON/YAML 或恰好一行 CSV
python3 scripts/uac_experiment.py normalize UAC-SUMMARY.csv --output UAC-NORMALIZED.yaml

# 匿名历史案例回放；不是因果或真实效果证明
python3 scripts/uac_experiment.py replay examples/replays/example-anonymized --json

# 台账 1.0 → 1.1：先预览，再写新文件
python3 scripts/uac_experiment.py migrate-ledger ADS-EXPERIMENTS.yaml
python3 scripts/uac_experiment.py migrate-ledger ADS-EXPERIMENTS.yaml \
  --output ADS-EXPERIMENTS.v1.1.yaml
```

Workspace normalize 总会写 draft 和 `NORMALIZATION.json`，仅在严格合同通过时才额外生成 `normalized/UAC-INPUT.yaml`；否则停止，不能分析 draft。Ledger `1.0` 仍可读，新模板使用 `1.1`，分析输出仍是 `1.0`。分析、追加、复盘和取消不会隐式迁移；只在备份和检查后才使用 `migrate-ledger --write`。

`python3 scripts/sync_skill_layout.py --check` 和 `python3 scripts/knowledge_doctor.py` 是源码仓库维护命令：前者检查 canonical router 与 legacy mirror，后者检查知识新鲜度元数据。它们不证明平台规则对某个账户正确。

## 引导式访问

使用后台前，按这个顺序来：

```text
1. 你自己打开广告后台并登录。
2. 切到正确账号。
3. 选好日期范围，比如昨天、过去 7 天、过去 30 天、本周或本月。
4. 如果要日报/周报，打开甲方模板，或给模板路径/链接/文件名关键词。
5. 告诉 Codex：只读看数，不修改任何设置。
```

Codex Ads 默认只会看：

- 概览、广告系列表、素材表、转化目标、诊断、建议、分国家/设备/网络/素材数据
- 甲方模板的结构、字段、日期格式、表格样式

默认不会做：

- 改预算、改出价、改目标、暂停/启用广告、应用建议、保存设置、发送报告
- 把真实账号名、账号 ID、campaign 名、邮箱、付款信息写进仓库文件

## 每个优化师都可以定制

每个优化师可以在项目目录放一个自己的经验文件：

```text
CODEX_ADS_OPTIMIZER.md
```

你可以这样让 Codex 创建：

```text
帮我创建一个 CODEX_ADS_OPTIMIZER.md，记录我的投放判断习惯。我的风格是：先看转化目标，再看预算消耗，再看国家和素材；给甲方汇报要直接，但不要太激进。
```

也可以让 Codex 根据你平时的话术整理：

```text
根据我下面这段优化经验，整理成 CODEX_ADS_OPTIMIZER.md，以后分析账户时先按我的规则判断。
```

开启投手风格学习：

```text
帮我在 CODEX_ADS_OPTIMIZER.md 里开启投手风格学习模式。
默认用 suggest_only：你可以根据我的纠正提出可沉淀规则，但必须先问我确认，不要自动写入。
学习到的规则要放在“从使用经验学习到的偏好”，不能覆盖我手动填写的规则，也不能保存客户信息或具体账号数据。
```

如果你想以后自动追加匿名规则，可以明确说：

```text
把 style_learning_mode 改成 auto_append_anonymized。
只能追加匿名、泛化后的投放判断习惯；不要保存客户名、账号 ID、campaign 名、素材名、具体消耗、CPA/ROAS、邮箱、手机号或带 token 的链接。
```

建立项目记忆文档：

```text
帮我为这个项目建立三份项目记忆文档：
1. 项目长期背景、KPI、甲方要求、日报格式
2. 每天操作记录、原因、复盘
3. 甲方日报/周报固定格式
先用匿名标签，不要保存真实账号 ID 或付款信息。
```

建议写进去的内容：

- 我最关注的核心指标
- 什么情况下可以加预算
- 什么情况下必须降预算或停投
- 我怎么看国家、设备、素材、转化目标
- 给甲方汇报时的语气
- 我不喜欢的建议类型
- 我的日报/周报固定格式

## 优化师配置模板

```markdown
# Codex Ads Optimizer Profile

## 我的投放风格
- 

## 优先级
1. 转化目标和追踪
2. 预算消耗和 CPA/ROAS
3. 国家、设备、网络、人群
4. 素材和落地页

## 加预算规则
- 

## 降预算/暂停规则
- 

## 素材判断
- 

## 甲方汇报口径
- 

## 我不希望 Codex 做的事
- 
```

## 常见说法

不要说：

```text
/ads google
```

可以说：

```text
只读看一下这个 Google Ads 账号，告诉我现在最影响效果的 3 个问题和下一步动作。
```

不要说：

```text
/ads report
```

可以说：

```text
按甲方模板输出一份今天的日报，模板我已经打开了，只读识别，不要写回。
```
