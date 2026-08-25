# K-town 开发交接记录

> 交接给下一位开发者。先读 `docs/product/gameplay-design-v6.md`、`docs/product/gameplay-design-v5.md`、`docs/product/world-view-v3.md`、`docs/product/art-direction-v2.md`、`docs/plans/2026-08-25-multiweek-demo-plan.md` 和 `docs/architecture/frontend-v2.md`，再阅读本文件的现有实现记录。
> `docs/design-master-plan-2026-08-04.md`、v4 玩法、v1 美术和下方 v0.5 机制说明均为历史参考，不能覆盖当前四周 Demo 边界。

## 当前状态（2026-08-25，四周 Demo）

- **产品目标**：让玩家作为普通新居民，在四周篇章中通过有限时间选择帮助谁、相信什么、把后果留给谁；小镇和居民会自主回应。
- **四周章节**：第 1 周雨前的七天；第 2 周河水改道；第 3 周灯火与账本；第 4 周归灯集；第 29 天结算最终结局。
- **内容架构**：`campaign.py` 负责章节解锁、请求注册、分支效果、旗标、评分和结局；`ActionResolver` 仍是唯一动作校验、扣 AP、推进时间和写日志入口。
- **存档架构**：`game_state.py` 保存/恢复章节、请求、世界标记、居民、知识、事件队列、日志和 RNG。
- **前端架构**：`state-contract-v2.js` 归一化状态，`api-client-v2.js` 集中网络边界，`campaign-view-v2.js` 独立渲染章节卡，`app-v2.js` 通过 `data-app-action` 事件委托编排动作。
- **交付状态**：代码、文档、隔离测试、存档/回放和浏览器验收均已完成；本轮变更按仓库规范提交并推送后即可交接。

## v5 历史基线（已完成，当前由上方 v6 状态继承）
- **产品目标**：让玩家作为暂住七天的新居民，通过具体请求与有限时段，看到居民自主生活和次日后果。
- **首个纵切片**：托林、莉娜、梅奶奶；广场、工坊、河谷野径；暴雨预告、旧矿道传闻、工坊屋顶三阶段和归灯集回顾。
- **代码状态**：`ActionResolver`（actions.py）统一结算玩家/NPC、请求、对话和危机；三条居民请求、暴雨/矿道传闻、屋顶三阶段、次日观察、版本化存档和确定性回放均已接线。
- **前端状态**：首屏今日三条线、当前地点行动栏、居民因果档案、请求/危机入口已接线；日报和行动结果会显示 story beats 与 next observation；地图支持稳定道路、天气层和屋顶三阶段视觉反馈。
- **完成状态**：核心代码、真实浏览器验收、固定 seed 七天回放和保存后刷新均已完成。后续只做长期平衡调优与 `tick.py` 拆分评估，不再把它们作为 v5 纵切片完成门槛。
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

**数据安全（Phase 0 已落地）**：核心测试均使用隔离临时数据库，不再触碰默认 `k_town.db`。启动模式由 `config.yaml` 的 `server.reset_on_start` 控制（默认 `false` = 继续游戏，完整存档优先恢复）；玩家首屏已无 reset 按钮（`/api/reset` 保留为开发入口）。测试或开发需要干净世界时，临时把 `reset_on_start` 改为 `true` 再启动。

## 当前玩法一句话

K-town 是一座会自己生活的小镇。v5 首先用七天纵切片验证了“玩家帮助谁、相信什么、把时间留给哪里；第二天看到小镇回应”的核心循环，v6 在此基础上扩展为四周篇章。

当前代码仍保留 20 小时/AP、十三时和失忆相关机制，但它们只是待适配的历史能力，不能成为首周教学、请求或 UI 的前置门槛。

## 当前代码的遗留机制（修改前先审计）
- **时间/AP**：`tick.advance(hours)` 已修复（hours>0 才排队）；`ActionResolver` 是唯一扣费/推进点。NPC 动作不推进时间（否则与 `run()` 循环互相喂食——已修复的回归，见 test_actions 第 10 项）。
- **动作入口**：玩家 API（`/api/player/action`）、NPC 决策、请求选项、危机干预、交易统一经 `actions.py` 的 resolver；对话仍独立在 api.py（已有同地点校验 + AP 扣减 + advance）。`trigger_event` 玩家入口已删除。
- **地图**：5 个地点与分层地图保留为实现资产；当前主舞台仍一次放大一个地点，但侧栏三条线提供全镇活动/压力摘要，后续可再做多地点同屏。

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

## 已知限制 / 后续可选工作
- **v5 验收已完成**：真实 Chromium 已覆盖完整莉娜请求流程（移动→收集→返回→交付）、活动危机横幅/帮忙/状态同步、390px 移动端危机可读性、三条线收起、reduced-motion，以及保存后重启刷新。前端危机干预补充了 REST 后的 `/api/state` 同步，确保 AP、横幅和三条线一致。
- **地图信息架构**：当前舞台一次显示一个地点；若继续打磨，应将全镇居民活动摘要更明确地放入地图层，而不是重拆地图渲染系统。
- **长期系统边界**：失忆/玉佩/十三时、随机危机池和每日目标是历史兼容能力；不要让它们重新成为 v5 首周主线。
- **`tick.py` 仍是单体**：在 v5 闭环稳定前不要大拆；`ActionResolver` 已是明确内部边界，之后再抽模块。
- **运行环境**：`run_server.ps1`/`scripts/ensure-start-server.ps1` 固定使用 Conda `python_class`；禁止用裸 `python`。`api.py` 的 `logger` 参数实际是 Storage 实例，修改时注意命名历史。调试时注意：旧服务器实例不随新实例自动退出（确保脚本杀干净再起，否则会出现 tick 漂移）。

## 最近验证（2026-08-25）
- `test_actions.py`：23/23；`test_phase2.py`、`test_phase3.py`：通过（Phase 3 含三条请求、三条线/档案 API 合约）。
- `test_smoke.py`：60 tick、跨 4 天、临时数据库 ALL PASS。
- `test_save_restore.py`：世界、居民、知识、请求、危机、事件队列、日志、RNG round-trip PASS。
- `test_replay.py`：checkpoint 恢复后 3 次确定性回放 PASS。
- `test_crisis.py`：20/20；`test_emotions.py`：16/16；`test_progress.py`：10/10。
- Python `compileall`、全部 7 个前端脚本的 `node --check` 均通过。
- API 合约：`/api/state`、`/api/today-threads` 均返回 3 条同源线程；居民详情含 profile.responses。
- 浏览器验收：1440px、1024px 均保持三条线程和四个上下文行动可见；390×844 移动仿真下 `html/body.scrollWidth = 390`，地图、顶栏和行动栏均不横溢；四个上下文行动以两列完整可见，休息/写想法按钮完整可见；今日三条线可滚动，收起按钮已验证真正隐藏列表；三条请求入口均能切换到请求详情 Tab；活动危机横幅在移动端也完整落在可视区域。
- reduced-motion：Chromium `prefers-reduced-motion: reduce` 仿真命中，动画/过渡被压缩到一次性短时长。
- 固定 seed `4242` 七天回放运行两次结果完全一致：第七天前完成莉娜/托林/梅奶奶三条请求，屋顶 `repaired`，天气 `rainy`，矿道传闻 `marked`，无异常。
- 真实浏览器请求验收：AP 按移动 1、收集 2、返回 1、交付 1 单次扣除，莉娜请求显示“已完成”，动态流显示行动结果。
- 真实浏览器危机验收：暴风雨 `0/60` 横幅可见，帮忙后 AP `12→9`、进度 `0→30`，Toast 与横幅同步。
- 真实浏览器保存后刷新：独立数据库重启后保留 tick `6`、玩家工坊位置、AP `11` 和 3 条请求。
- 回归总览：`test_actions` 23/23、`test_phase2`/`test_phase3`、`test_smoke`、`test_save_restore`、`test_replay`、`test_crisis` 20/20、`test_emotions` 16/16、`test_progress` 10/10；Python compileall、全部前端 Node 语法检查和 `git diff --check` 均通过。根目录遗留 `test_progress.db` 已移入系统临时目录，默认 `k_town.db` 未触碰。

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
