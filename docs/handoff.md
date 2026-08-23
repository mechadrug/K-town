# K-town 开发交接记录

> 交接给下一位开发者。先读 `docs/product/gameplay-design-v5.md`、`docs/product/world-view-v3.md`、`docs/product/art-direction-v2.md` 和 `docs/plans/2026-08-23-rebuild-plan.md`，再阅读本文件的现有实现记录。
> `docs/design-master-plan-2026-08-04.md`、v4 玩法、v1 美术和下方 v0.5 机制说明均为历史参考，不能覆盖 v5 的七天纵切片边界。

## 当前状态（2026-08-23 晚，Phase 0-1 完成，dry-wood 切片跑通）
- **产品目标**：让玩家作为暂住七天的新居民，通过具体请求与有限时段，看到居民自主生活和次日后果。
- **首个纵切片**：托林、莉娜、梅奶奶；广场、工坊、河谷野径；暴雨预告、旧矿道传闻、工坊屋顶三阶段和归灯集回顾。
- **代码状态**：`ActionResolver`（actions.py）已建立并接管所有玩家/NPC 动作；`bring_dry_wood` 请求端到端跑通（收集→交付→莉娜关系+6）。情绪、危机、进度等 v0.5 能力保留并有专项测试。
- **下一步范围**：Phase 2 居民感知与因果链（`Agent.perceive()` + 事件快照 + 决策日志"因为 X 所以 Y"）；随后 Phase 3 扩展托林屋顶、梅奶奶镇志两条请求线。
- **技术栈**：Python 3.11 + FastAPI + SQLite + HTML/JS(WebSocket)。**无** Go/Godot/PostgreSQL（已废弃并删除）。

## 运行方式
```powershell
cd <本仓库根目录>
.\run_server.ps1       # 前台运行；自动结束上一实例，使用 conda python_class，端口 8090
```

后台运行并等待健康检查：

```powershell
.\scripts\ensure-start-server.ps1
```

**数据安全（Phase 0 已落地）**：`test_smoke.py` / `test_actions.py` 均使用临时数据库，不再触碰默认 `k_town.db`。启动模式由 `config.yaml` 的 `server.reset_on_start` 控制（默认 `false` = 继续游戏，部分恢复）；玩家首屏已无 reset 按钮（`/api/reset` 保留为开发入口）。测试或开发需要干净世界时，临时把 `reset_on_start` 改为 `true` 再启动。

## 当前玩法一句话

K-town 是一座会自己生活的小镇。玩家以普通新居民身份暂住七天，在有限时间里决定帮助谁、相信什么、把时间留给哪里；第二天，小镇会用居民行为、关系和场景变化回应这个选择。

当前代码仍保留 20 小时/AP、十三时和失忆相关机制，但它们只是待适配的历史能力，不能成为首周教学、请求或 UI 的前置门槛。

## 当前代码的遗留机制（修改前先审计）
- **时间/AP**：`tick.advance(hours)` 已修复（hours>0 才排队）；`ActionResolver` 是唯一扣费/推进点。NPC 动作不推进时间（否则与 `run()` 循环互相喂食——已修复的回归，见 test_actions 第 10 项）。
- **动作入口**：玩家 API（`/api/player/action`）、NPC 决策、请求选项、危机干预、交易统一经 `actions.py` 的 resolver；对话仍独立在 api.py（已有同地点校验 + AP 扣减 + advance）。`trigger_event` 玩家入口已删除。
- **地图**：5 个地点与现有分层地图保留为实现资产；v5 默认应显示全镇活动或多地点摘要，不再把单地点放大视图当作唯一首屏。

## 模块地图（每个都有实际用途）
```
main.py       入口：组装依赖、创建 Storage/TickEngine/FastAPI app、启动 tick 任务与 uvicorn
config.py     配置 dataclass（server/tick/llm），config.yaml 含 LLM key（已 gitignore）
models.py     数据模型（Role/Mood/ClaimSource/ClaimScope/EventType 枚举 + dataclass）——已精简到全部被用
world.py      World：5 地点/资源/价格/天气/供需（天气唯一来源，tick%20==6 更新）
events.py     EventBus + EventScheduler（每日事件日程，仅调度被处理的类型）
agent.py      Agent：perceive/think/decide（5 层决策 + 生活节奏）+ populate_agents()
knowledge.py  知识引擎（KnowledgeClaim 观察/去重/传播/质疑/固化 + 写穿持久化 + load_from_db）
storage.py   ★唯一数据访问层（SQLite 单一连接、权威 DDL、schema 版本自动重建）
tick.py       TickEngine：回合制主循环、step（advance→事件→决策→执行→结算→日报）、
              _handle_action（玩家与 NPC 共用动作管线，含十三时/领悟/调查/修缮）、
              _night_mystery / _check_insight / _town_upgrade_check
quests.py     每日目标薄层（3 个/天，真实动作池，完成发金币）
dialogue.py   语境化对话系统（话题由性格×心情×正在做的事×关系生成）
factions.py   派系聚类（正午更新）
api.py        REST + WebSocket；_build_state_payload 统一状态；玩家动作走 _handle_action
llm.py        LLM 客户端（Anthropic 兼容，mock 兜底，每日限次+缓存）
test_smoke.py 冒烟测试
static/ + templates/index-v2.html  唯一前端（图标系统 icons.js、分层地图 town-map-v2、主逻辑 app-v2）
```

## 历史实现决策（用于排查现有代码，非 v5 产品承诺）
1. **二十时世界观**：`day_length=20`, `wake_hour=5`, `waking_hours=12`；全链（agent 作息/events 日程/前端时段/地图昼夜）按 20h 对齐
2. **纯回合制**：时间只随 AP 前进；`advance()` 排队、`wait_caught_up()` 等落地；休息结束一天
3. **玩家与 NPC 共用动作管线**：`tick._handle_action(agent, action, tick)`；craft/gather 归一化为 work；玩家 AP 在 api 检查
4. **知识是主线**：每日一次"思考"（0 AP）→ `_check_insight` 触及隐藏关键词（遗迹/石碑/十三/玉佩/地球/时间…）→ 领悟技能 + 记忆碎片
5. **十三时**：`night_ap` 独立池，仅夜晚可用，夜晚行动触发 `_night_mystery`（遗迹残响 + 夜间技能）
6. **小镇重建**：居民攒钱逐级修缮建筑（Lv1→5，阈值平方增长），修缮后资源更丰
7. **数据层单一**：所有持久化走 storage.py；schema 版本不符自动重建

## 历史 v0.5 重构已做（2026-08-20）
**文档 + 清理**：
- **gameplay-design-v4.md**（取代 v3）：三支柱 + 游戏感三件套
- **art-direction-v1.md**：美术方向成文（水彩软化像素、地图道路/像素小人、动效接入、死 CSS 清理）
- **路线图 Phase 6-9**（v0.5a-d）：见主计划 §4b
- **仓库清理**：删 15 个根目录一次性脚本 + k_town.db + __pycache__；归档 vision/world-v0.1/report_260528 至 docs/archive/2026-08-20/（加状态横幅）；世界观五篇入库；知识固化阈值统一 0.85

**Phase 6-8 实现（已测试）**：
- **Phase 6 情绪闭环**（emotions.py）：4 维情绪 + 事件×性格偏移 + 决策渗透 + 习惯形成（近似 RL）+ 性格演化 + 关系网传染。验证：test_emotions.py 16/16
- **Phase 7 危机干预**（crisis.py）：4 危机 + 性格化反应矩阵 + 玩家四干预 + 结局分支 + NPC 自救 + NPC 交易响应。验证：test_crisis.py 20/20
- **Phase 8 长期目标线**：身世碎片收集（5 片解锁大缓变真相）+ 重建弧线进度（/api/progress）。验证：test_progress.py 10/10

## 已知问题 / 剩余工作
- **因果链不完整（下一阶段主攻）**：`Agent.perceive()`、事件快照、短期记忆和决策原因尚未组成稳定闭环；情绪和知识不能只作为后端数值。
- **存档不完整**：Agent、AP、关系、情绪、习惯、请求、天气和时钟还不能作为一个 versioned `GameState` 可靠恢复；”继续游戏”模式是部分恢复（resolver 的 `self.requests` 每次启动重新种子，deadline 到期自动 expired）。
- **前端是旧信息架构**：目标、危机和进度入口不能代替”今日三条线”和当前地点的具体回应；四维情绪和危机详情必须转成可理解的因果信息。
- **视觉应后置于行为闭环**：已有道路、像素小人和 CSS 是可复用资产；先完成雨天工坊关键场景，不要继续堆独立粒子或页面。
- **`tick.py` 仍是单体**：在 v5 闭环稳定前不要大拆；`ActionResolver` 已是明确内部边界，之后再抽模块。
- **运行环境**：`run_server.ps1`/`scripts/ensure-start-server.ps1` 固定使用 Conda `python_class`；禁止用裸 `python`。`api.py` 的 `logger` 参数实际是 Storage 实例，修改时注意命名历史。调试时注意：旧服务器实例不随新实例自动退出（确保脚本杀干净再起，否则会出现 tick 漂移）。

## 最近验证（2026-08-23 晚，Phase 0-1）
- `test_actions.py`：23/23 通过（新：ActionResolver 契约 + dry-wood 流程 + NPC 不推进时间回归）
- `test_smoke.py`：60 tick ALL PASS（临时库）
- `test_crisis.py`：20/20、`test_emotions.py`：16/16、`test_progress.py`：10/10（后两者 Windows 控制台需 UTF-8）
- 实服验证：移动 AP 12→11 只扣一次、tick 5→6 只推进 1h；收集干木料 -2AP/+2h；异地交付拒绝零消耗；交付后请求 completed、莉娜关系 +6；前端请求卡显示 ✅ 已完成（第1天）；首屏无 reset 按钮
- `/api/state`、`/api/requests`、`/api/quests` 均返回 200

## 路线图（读这些文档）
- `docs/product/gameplay-design-v5.md` — ★当前玩法基线：七天请求、因果回信、居民自主回应
- `docs/product/world-view-v3.md` — ★当前首周世界观：归灯集、暴雨、居民关系与边界
- `docs/product/art-direction-v2.md` — ★当前美术方向：绘本水彩生活舞台
- `docs/plans/2026-08-23-rebuild-plan.md` — ★当前实施顺序、行为契约、测试策略和注意事项
- `docs/development-progress.md` — 当前设计/代码状态与下一次切片
- `docs/design-master-plan-2026-08-04.md` — 历史架构修复与 v0.5 能力来源
- `docs/product/gameplay-design-v4.md`、`docs/product/art-direction-v1.md`、`docs/product/world-self-generation.md` — 历史或远期参考，不作为当前开发入口
- `docs/archive/2026-08-20/` — 过时文档归档，仅作历史参考

## 提交规范
按 CLAUDE.md：`<type>(<scope>): <English>` + 中文描述；分批 chore/refactor → feat/fix → docs；禁 `git add -A`。
