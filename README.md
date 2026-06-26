<p align="center">
  <img src="assets/logo.svg" alt="Codex Ads 标志" width="100%">
</p>

```text
 ██████╗ ██████╗ ██████╗ ███████╗██╗  ██╗     █████╗ ██████╗ ███████╗
██╔════╝██╔═══██╗██╔══██╗██╔════╝╚██╗██╔╝    ██╔══██╗██╔══██╗██╔════╝
██║     ██║   ██║██║  ██║█████╗   ╚███╔╝     ███████║██║  ██║███████╗
██║     ██║   ██║██║  ██║██╔══╝   ██╔██╗     ██╔══██║██║  ██║╚════██║
╚██████╗╚██████╔╝██████╔╝███████╗██╔╝ ██╗    ██║  ██║██████╔╝███████║
 ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝    ╚═╝  ╚═╝╚═════╝ ╚══════╝
```

# Codex Ads

Codex Ads 是一套给 Codex 用的广告投放分析 skill。你可以把它理解成一个“广告投放副驾驶”：帮你看账户、算账、找问题、写优化方案，也能把结论整理成适合发给客户或团队看的报告。

[English README](README.en.md) · [快速启动](QUICKSTART.zh-CN.md)

## 它能干什么

- **看账户有没有跑偏**：检查 Google、Meta、YouTube、TikTok、LinkedIn、Microsoft、Apple、Amazon Ads 等平台的结构、预算、出价、转化和素材。
- **帮你判断钱花到哪了**：区分展示、点击、安装、注册、付费这些不同层级，避免被“表面转化很多”误导。
- **适合代投窄权限场景**：当 KPI、产品定位、价格或付费路径不能改时，帮投手找仍然可动的投放杠杆，尤其适合“安装很多但支付很少”“线索很多但有效很少”“CPI 很低但 ROI 很差”。
- **找出最该先改的地方**：把追踪、归因、目标、预算、广告系列结构、素材疲劳、落地页问题按优先级排出来。
- **做投放数学题**：计算 CPA、ROAS、CPI、LTV、预算分配、目标出价和 A/B 测试样本量。
- **写能落地的方案**：输出账户审计、增长计划、广告文案方向、素材 brief、竞品分析、客户汇报和 PDF 报告。
- **减少重复杂活**：支持每日巡检、异常排查、甲方回复、素材需求单、报表清洗、变更记录和周/月会汇总。
- **适合代投场景**：可以把“给甲方看的解释”和“内部实际操作清单”分开写，方便沟通预算、目标和风险。
- **默认搭配 Computer Use 看数**：如果你已经登录广告后台，它会优先只读查看真实页面和表格；不会默认改预算、暂停广告或应用建议。
- **引导式访问**：它会先告诉用户怎么打开后台、切到哪个页面、选择什么日期范围，再开始只读分析。

简单说：它不是只告诉你“数据好不好”，而是帮你回答几个关键问题：

```text
预算消耗和转化质量是否正常？
哪些环节影响了高价值转化？
下一步应该先改哪里，怎么跟客户解释？
在产品和 KPI 都不能改时，我还能动哪些投放杠杆？
```

## 安装

默认安装到 Codex：

```bash
bash install.sh
```

自定义安装目录：

```bash
bash install.sh --target=codex --skill-dir=~/custom/skills --agent-dir=~/custom/agents
```

Windows PowerShell：

```powershell
.\install.ps1
```

默认路径：

| 类型 | 路径 |
| --- | --- |
| Skills | `~/.codex/skills` |
| Agents | `~/.codex/agents` |
| 主技能 | `~/.codex/skills/ads` |

## 快速开始

优化师不需要背命令。启动 Codex 后，直接复制一句自然语言给它：

```text
只读看一下这个广告账户，帮我判断预算消耗、转化质量、目标设置和下一步优化动作。不要修改任何设置。
```

更多复制即用的话术见 [快速启动](QUICKSTART.zh-CN.md)。

深度分析前，Codex Ads 会先问几个基础问题：你投什么产品、月预算多少、核心目标是什么、现在跑哪些平台。信息越具体，它给出的判断越像真实投手，而不是泛泛建议。

如果你已经登录广告平台，可以直接说“只读看一下我的 Google Ads / Meta Ads 账户”。Codex Ads 会默认搭配 Computer Use 看真实后台数据；只有看不到后台或没有授权时，才让你导出报表或截图。

## 引导式访问

为了安全看数，建议按这个流程给 Codex Ads 访问：

```text
1. 你自己打开广告后台并登录。
2. 切到要分析的账号，不要打开付款方式、个人资料、密钥、权限管理等敏感页面。
3. 设置好日期范围，例如过去 7 天、过去 30 天或本月。
4. 如果要按甲方模板出日报/周报，打开模板，或告诉 Codex 模板的文件路径、云文档链接、文件名关键词。
5. 对 Codex 说：只读看一下这个广告账户，不要修改任何设置。
6. Codex Ads 只读取页面数据、表格、诊断、转化设置和模板结构，并给出观察、计算和建议。
```

默认安全边界：

- 只看数据，不点击“应用建议”“保存”“提交”“暂停”“启用”“删除”等会改账号的按钮。
- 不改预算、不改出价、不改转化目标、不改广告系列、不改素材。
- 不记录客户账号名、账号 ID、campaign 名、邮箱、付款信息或任何可识别客户身份的内容到仓库文件。
- 找甲方模板时，只读取模板结构和字段要求；不会私自修改、分享或发送模板。
- 报告里默认使用泛化表达；如需保留客户名或具体账号信息，必须由用户明确要求。
- 如果某个按钮可能产生修改，Codex Ads 必须先停下来问你确认。

## 优化师定制

每个优化师都可以把自己的经验写进项目目录里的 `CODEX_ADS_OPTIMIZER.md`。Codex Ads 分析账户前会优先读取这个文件，把你的判断习惯、加预算规则、停投规则、素材偏好和甲方汇报口径纳入建议。

你可以直接对 Codex 说：

```text
帮我创建一个 CODEX_ADS_OPTIMIZER.md，记录我的投放判断习惯。我的风格是：先看转化目标，再看预算消耗，再看国家和素材；给甲方汇报要直接，但不要太激进。
```

## 高级命令

| 命令 | 用途 |
| --- | --- |
| `/ads audit` | 多平台完整审计 |
| `/ads google` | Google Ads 分析 |
| `/ads meta` | Meta Ads 分析 |
| `/ads youtube` | YouTube Ads 分析 |
| `/ads linkedin` | LinkedIn Ads 分析 |
| `/ads tiktok` | TikTok Ads 分析 |
| `/ads microsoft` | Microsoft Ads 分析 |
| `/ads apple` | Apple Ads 分析 |
| `/ads amazon` | Amazon Ads 分析 |
| `/ads attribution` | 跨平台归因检查 |
| `/ads tracking` | 服务端追踪检查 |
| `/ads creative` | 创意质量与疲劳评估 |
| `/ads landing` | 落地页转化评估 |
| `/ads budget` | 预算分配和出价策略 |
| `/ads levers` | 代投受限场景诊断：KPI/产品不能改时找可操作杠杆 |
| `/ads patrol` | 每日账户巡检 |
| `/ads anomaly` | 异常波动排查 |
| `/ads client-reply` | 甲方回复和解释话术 |
| `/ads creative-request` | 素材/设计/剪辑需求单 |
| `/ads clean-report` | 后台导出报表清洗和指标统一 |
| `/ads adapt-template` | 适配任意甲方日报/周报模板，生成字段映射 |
| `/ads changelog` | 优化动作变更记录 |
| `/ads meeting` | 周会/月会复盘材料 |
| `/ads plan <type>` | 按业务类型生成投放策略 |
| `/ads competitor` | 竞品广告研究 |
| `/ads math` | PPC 财务计算 |
| `/ads test` | A/B 测试设计 |
| `/ads report` | 生成 PDF 报告 |
| `/ads daily` | 导出日报 |
| `/ads creative-weekly` | 生成素材周报 |
| `/ads dna <url>` | 提取品牌 DNA |
| `/ads create` | 生成 Campaign Brief 和文案方向 |
| `/ads generate` | 生成广告图像 |
| `/ads photoshoot` | 生成产品摄影提示 |

## 使用例子

Google Ads 账户体检：

```text
/ads google
产品：移动 App
平台：Google App Campaign
目标：降低付费转化成本，同时判断是否可以扩大预算
当前问题：预算消耗不稳定，或者高价值转化成本偏高
```

代投汇报：

```text
/ads report
请输出两版：一版给甲方看，解释预算、目标和风险；一版给内部投手看，列出具体调整顺序。
```

导出日报：

```text
/ads daily
只读看一下广告后台，按甲方日报模板整理今天的数据。
模板我已经打开在浏览器里，或者我会给你文件路径/链接。
```

素材周报：

```text
/ads creative-weekly
只读看本周素材表现，按甲方素材周报模板输出。
重点看哪些素材该继续投、哪些该停、下周该补什么素材。
```

素材审查：

```text
/ads creative
请判断这些素材更容易吸引浅层用户，还是更容易吸引愿意付费的用户。
```

代投受限场景：

```text
/ads levers
我们是代投，KPI 和产品方向都不能改。现在安装很多但支付很少，
请帮我判断投放侧还能动哪些杠杆，哪些需要甲方配合，并输出给甲方的解释。
```

日常巡检：

```text
/ads patrol
只读看一下昨天的数据，帮我找今天必须处理的 3 件事：
消耗、支付/线索、CPA/ROAS、素材拒审、追踪异常和国家/版位异常都要扫一遍。
```

素材需求单：

```text
/ads creative-request
根据本周素材表现，帮我给设计/剪辑整理下周素材需求单：
每条要写清目标、平台、尺寸、角度、画面、文案、验收标准。
```

甲方回复：

```text
/ads client-reply
把这段内部判断改成给甲方看的版本，语气直接但不要甩锅，
要讲清观察、可能原因、我们会做什么、需要甲方配合什么。
```

甲方模板适配：

```text
/ads adapt-template
这个客户日报模板和其他客户不一样。请只读识别模板结构，
先生成字段映射表，标出缺失数据和计算公式，再输出可粘贴的日报草稿。
如果适合复用，请创建匿名的 client-report-map.yaml。
```

## 目录结构

```text
ads/                 主技能和参考资料
skills/              平台与工作流子技能
agents/              审计和创意 agents
scripts/             本地 Python 工具
tests/               Pytest 测试
evals/               创意评估样例
.codex-plugin/       Codex 插件元数据
```

## 本地工具

部分命令会调用 `scripts/` 下的 Python 工具。安装依赖：

```bash
pip3 install -r requirements.txt
```

图像生成通过 `ADS_IMAGE_PROVIDER` 和对应密钥配置，例如 `GOOGLE_API_KEY` 或 `OPENAI_API_KEY`。

## 测试

```bash
pip3 install -r requirements-dev.txt
pytest -q
```

## 卸载

```bash
bash uninstall.sh
```

Windows：

```powershell
.\uninstall.ps1
```

## 许可证

MIT。详见 [LICENSE](LICENSE)。
