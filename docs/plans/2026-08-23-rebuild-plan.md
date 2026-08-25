# K-town v5 重构实施计划：先做活一条七天循环

> **状态**：v5 七天纵切片已完成并通过运行时验收；后续为可选平衡调优与架构演进
> **更新日期**：2026-08-24
> **产品基线**：`docs/product/gameplay-design-v5.md`
> **配套设定/视觉**：`docs/product/world-view-v3.md`、`docs/product/art-direction-v2.md`

## 0. 目标、非目标与完成定义

### 0.1 目标

在现有 Python + FastAPI + SQLite + vanilla JS 原型上，完成一个可从首屏理解、可在七天内结束、能展示居民自主行为和次日后果的纵切片：

```text
晨间脉搏 → 选择具体请求/压力/线索 → 2-3 个有代价的行动
→ NPC 自主反应 → 关系/情绪/知识/场景变化 → 傍晚因果回信 → 次日观察
```

### 0.2 非目标

- 不新增地点、职业、复杂经济链或新的长期养成系统；
- 不把 LLM 接入日常决策；规则引擎必须在无 key 时完整运行；
- 不继续扩展失忆、玉佩、十三时、大缓变主线的首周内容；
- 不在行为闭环稳定前拆分 `tick.py`；
- 不做多玩家、排行榜、成就或世界自生成。

### 0.3 完成定义

只有同时满足以下条件才算 v5 纵切片完成：

- 新玩家 5 分钟内完成一次具体选择并看到即时反馈；
- 7 天内可以完成至少 3 个请求；每个请求至少有两种代价/后果不同的回应；
- 玩家和 NPC 的动作各只结算一次时间，所有重要结果有因果记录；
- 同一事件在不同人格上产生可解释的不同反应；
- 保存/加载后世界、Agent、请求和日志状态一致；
- 前端首屏以居民和场景为主，移动端不丢失“今日三条线”；
- 核心测试在隔离数据库上可重复运行。

## 1. 当前代码基线与风险

### 1.1 已有能力

- 12 位 Agent、5 个地点、事件总线、四维情绪、危机和重建进度已有后端基础；
- `storage.py` 是当前唯一数据访问层；
- `tick.py` 同时负责时间、NPC 决策、玩家动作、日报和结算；
- 前端已具备 SVG 地图、WebSocket、引导和部分 Phase 9 样式，但信息架构仍偏仪表盘。

### 1.2 最高风险

1. **动作重复结算**：API 和 `_handle_action` 可能重复扣 AP 或推进时间。
2. **事件不可感知**：`Agent.perceive()` 尚未形成稳定的事件 → 记忆 → 决策链。
3. **存档不完整**：Agent 实例和玩家状态不能可靠恢复，默认启动会 reset。
4. **前端显示旧模型**：四维情绪、危机、progress 接口存在，但玩家看不到或无法回应。
5. **视觉不统一**：水彩卡片、像素地图、临时粒子并存，且粒子可能随 state 更新重建。

## 2. 数据与行为契约

### 2.1 统一动作入口

新增 `ActionResolver`（可以先作为 `TickEngine` 内的明确类/模块，待稳定后再拆文件）。所有玩家、NPC、对话、请求、危机干预都必须通过它。

输入至少包含：

```python
Action(actor_id, kind, target_id=None, target_location=None, payload={})
```

输出统一为：

```python
ActionResult(
    accepted: bool,
    cost: int,
    hours: int,
    changes: list[Change],
    story_beats: list[str],
    next_observation: str | None,
    error_code: str | None,
)
```

结算规则：

- resolver 负责校验、扣除成本、推进时间、写日志和广播；调用方不能重复做其中任何一步；
- actor 必须是玩家或当前 tick 正在决策的 NPC，禁止 API 代替玩家控制任意居民；
- 目标居民必须和 actor 在同一地点，目标地点必须来自 `world.py` 的唯一清单；
- 失败动作不扣时间，除非请求明确设计为“失败也会消耗时段”；
- 夜间、资源、天气和请求截止时间由 resolver 统一校验；
- 每个 `changes` 必须有 source/action id，可在日报中追溯。

### 2.2 请求模型

在 `quests.py` 或新的 `requests.py` 中建立结构化模型：

```python
Request(
    id, requester_id, location, title, situation, deadline,
    options, requirements, visible_risks, immediate_effects,
    next_day_effects, status,
)
```

选项不是任意按钮。每个选项必须声明时间/资源成本、可能改变的居民或场景、成功与失败的可观察结果。

### 2.3 事件与因果日志

每个重要动作和 NPC 决策都记录：

- `observations`：本次决策看到的事件、知识和关系信号；
- `reason`：规则层选择该动作的原因；
- `changes`：资源、情绪、关系、知识、场景的变化；
- `next_observation`：玩家下一时段/次日应看到什么。

日志是玩法数据，不只是调试输出；日报从同一结构生成“因为 X，所以 Y”。

## 3. 分阶段任务

### Phase 0：冻结边界与清理入口

**目标**：让所有后续工作只围绕 v5 纵切片。

- 在主计划、README、CLAUDE、AGENTS 和 handoff 中统一引用 v5/v3/v2 文档；
- 将 v4、art-direction-v1、旧主计划中的 20 小时/失忆/随机危机等列为历史或远期参考；
- 暂停新增系统，记录未完成功能但不继续接线；
- 把 reset 从日常行动栏移入开发设置；启动 reset 改成显式配置；
- 给 smoke/progress 测试提供临时数据库路径；停止服务后才允许改写默认库；
- 为每一项调试入口标注 `development_only`，不出现在玩家首屏。

**验收**：文档引用一致；玩家首屏无 reset；测试不会触碰默认 `k_town.db`；启动模式明确显示“新游戏/继续游戏”。

### Phase 1：动作与时间基础

**目标**：消除所有双扣、免费行动和非法目标。

- 实现 `ActionResolver` 与 `ActionResult`；
- 让 `/api/player/action`、`_handle_action`、对话、trade、trigger_event、crisis 统一调用；
- 修复 API 与 `_handle_action` 双扣 AP；修复 trade/trigger_event 免费推进；统一 sleep 的扣时与换日语义；
- 校验对话同地点、移动目标合法、夜间限制、危机同一时刻只能干预一次；
- 返回成本、即时变化、后续观察点，前端只渲染 resolver 结果；
- 增加 API contract tests 和失败动作测试。

**验收**：任一动作只改变一次时钟；非法 actor/target 返回明确错误；同一 crisis 无法无限干预；日志中的 cost 与实际 AP 一致。

### Phase 2：居民感知与因果链

**目标**：让“环境 → 居民脑子 → 行为 → 学习”真实发生。

- 实现 `Agent.perceive()`，按地点、关系、天气、事件和知识筛选感知；
- `step()` 在清空事件总线前保留当前 tick 事件快照，传给所有相关 Agent；
- 新事件写入短期记忆，过期记忆压缩为摘要；
- 决策日志保存观察内容、规则命中和行动结果；
- 日报从日志生成最多 3 条“因为 X，所以 Y”叙述；
- 增加确定性剧本测试：雨天×人格、知识传播×路线选择、情绪反馈×习惯概率。

**验收**：同样的雨天输入至少让两种人格采取不同动作；传播的知识改变至少一名居民的下一次决策；行为变化可在日志和日报中解释。

### Phase 3：七天请求纵切片

**目标**：把底层动作组织成可游玩的选择。

首批只实现：

- 托林：工坊屋顶漏雨；
- 莉娜：缺干木料；
- 梅奶奶：整理镇志/居民记忆；
- 暴雨预告与旧矿道传闻；
- 工坊屋顶三阶段外观和状态；
- 傍晚“归灯集准备度”摘要。

每个请求必须有 2-3 个回应，且至少一个回应会错过另一个机会。不要用“完成一次 work”代替请求进度。

**验收**：七天内玩家能完成 3 个请求；第 2 天起至少有一个场景变化；第 7 天回顾能解释玩家选择的代价。

### Phase 4：前端生活舞台

**目标**：让玩家先看到人和处境，再看到系统。

- 默认显示全镇活动或多地点活动摘要；
- 右栏改为“今日三条线”：居民请求、镇上压力、可跟进线索；
- 底栏只显示当前地点上下文行动；
- 档案按“正在做什么 → 感受 → 原因 → 倾向 → 可回应”展示；
- 四维情绪、知识置信度和内部数值放入详情；
- 补齐 progress 面板与 crisis 交互入口；
- 事件卡展示 `story_beats` 和 `next_observation`；
- 移动端采用底部 sheet，不能隐藏今日三条线；
- reset、调试日志、原始 JSON 移入开发设置。

**验收**：新玩家不读长说明也能找到一个具体请求；每个操作按钮显示对象、时间成本和作用；桌面/移动端均可完成一次请求。

### Phase 5：视觉升级

**目标**：建立绘本水彩舞台的最小可信资产。

- 补颜色 token、纸面纹理、雨层、傍晚窗光和修缮状态；
- 稳定粒子生命周期，不在每次 state 更新时随机重建；
- 接入事件触发动画、低性能模式和 reduced-motion；
- 完成工坊雨天关键场景后再扩展其他地点；
- 清理 dead CSS 和未接入组件；
- 用真实居民姿态和职业道具替换通用圆点/状态图标。

**验收**：首屏截图先读到居民和天气；屋顶三阶段无需数字即可区分；动画关闭时信息仍完整；颜色无裸值。

### Phase 6：存档、测试与平衡

**目标**：让纵切片可重复、可回放、可调参。

- 建立 versioned `GameState`；保存/恢复 world、agents、inventory、AP、relationships、emotions、habits、knowledge、requests、weather、clock；
- `test_smoke.py` 使用临时数据库；补 save/load roundtrip、API contract、3 天 deterministic replay；
- 执行 7 天纵切片验收，记录每个关键选择的结果；
- 纵切片稳定后再跑 30 天游标，调情绪回归、危机压力、修缮阈值和资源供需；
- 任何平衡参数变更都要附带前后对比和回放 seed。

**验收**：同一 seed 三次运行结果一致；保存/恢复不改变第 2 天观察；长跑无异常增长、无重复扣费、无无法解释的状态跳变。

## 4. 测试策略

### 4.1 单元测试

- `ActionResolver`：成本、目标、夜间、失败回滚；
- 情绪：基础事件×人格调制、传染、习惯更新；
- 知识：传播、质疑、置信度和行为影响；
- 请求：选项成本、截止时间、状态机和次日效果；
- 存档：每个字段序列化/恢复。

### 4.2 剧本测试

固定 seed 和输入，测试以下最小剧本：

1. 雨天，敏感居民回避，稳重居民继续工作；
2. 玩家把“旧矿道塌方”告诉莉娜，她改变木料路线；
3. 玩家只修临时遮雨层，第二天工坊仍有滴漏；
4. 玩家帮助托林与莉娜共同规划，关系和修缮速度不同于独自搬料；
5. 玩家旁观三天，居民仍有自己的行动和请求结果。

### 4.3 手工验收

- 首次进入、第一次行动、傍晚因果回信、次日场景变化；
- 桌面 1440px、窄桌面 1024px、移动 390px；
- reduced-motion、无 LLM key、空数据库、保存后刷新；
- 所有失败动作都有可理解的中文反馈。

## 5. 开发纪律与注意事项

- 不以“系统已经存在”作为完成依据，必须证明玩家能看见并能回应它；
- 任何数值变化都要有 source、reason 和 next observation；
- 不让玩家直接控制任意 NPC，不给跨地点对话和免费事件；
- 不把情绪做成颜色计数器，不把知识做成静态百科；
- 新按钮先写清对象、成本、即时反馈和次日后果，再接 API；
- 先补测试和日志，再调整平衡；禁止用随机常数掩盖因果错误；
- 与用户已有修改协作，禁止用 reset/checkout 覆盖工作区；
- 不提交 `config.yaml`、默认数据库、临时日志或个人文档；
- 代码任务按边界拆小提交，文档变更放在相关代码稳定后同步；
- 每次 session 结束更新 `docs/handoff.md`，写明已完成、验证、风险和下一步。

## 6. 推荐提交顺序

1. `docs(product): establish v5 gameplay and world baseline`
2. `refactor(actions): centralize time and cost resolution`
3. `feat(agents): connect perception to causal decision logs`
4. `feat(requests): add seven-day town request slice`
5. `feat(ui): present town life stage and contextual actions`
6. `feat(art): complete watercolor stage feedback`
7. `test(save): isolate databases and verify deterministic replay`
8. `docs(plan): update handoff and progress after each phase`

每个提交只包含一个可独立验证的边界，不使用 `git add -A`、`--no-verify` 或 amend。

## 7. 当前状态与后续验收

Phase 0–6 的核心纵切片已经完成：统一动作结算、居民感知与因果日志、三条七天请求线、次日场景后果、生活舞台 UI、版本化存档和确定性回放均已接线并通过自动化与真实浏览器验证。本计划不再从 Phase 0/1 重新开工；当前四周 Demo 的扩展规则见 `docs/plans/2026-08-25-multiweek-demo-plan.md`。

完成证据：

1. 真实 Chromium 已完成完整请求流程：移动、收集、返回、交付，AP 单次扣费且请求卡/动态流同步更新；
2. 真实 Chromium 已完成活动暴风雨危机：横幅、帮忙按钮、统一动作结果、AP、进度和 Toast 同步；
3. 390px 仿真无横向溢出，今日三条线可收起，活动危机横幅完整可读，`prefers-reduced-motion` 生效；
4. 固定 seed `4242` 七天回放两次一致，三条请求完成、屋顶正式修好、暴雨和矿道路标后果出现；
5. 独立数据库重启后浏览器保留 tick、玩家位置、AP 和请求状态；自动化回归与语法检查全部通过。

后续仅保留：长期平衡调优（必须附回放结果）和稳定后再评估 `tick.py` 拆分；两者不阻塞 v5 纵切片交付。
