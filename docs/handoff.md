# K-town 开发交接记录

> 交接给下一位开发者。先读本文件，再读 `docs/design-master-plan-2026-08-04.md`（路线图）与 `docs/product/gameplay-design-v4.md`（玩法设计）。

## 当前状态（2026-08-20，v0.5 Phase 6-8 已实现）
- **版本**：v0.5 起步——游戏感三件套（情绪闭环/危机干预/长期目标线）Phase 6-8 已实现并测试通过
- **分支**：feature/v0.2-game-ui
- **技术栈**：Python 3.11 + FastAPI + SQLite + HTML/JS(WebSocket)。**无** Go/Godot/PostgreSQL（已废弃并删除）
- **本次变更**：v4 玩法设计 + 美术方向定稿 + 仓库清理 + Phase 6-8 实现（见下方）

## 运行方式
```powershell
cd <本仓库根目录>
python main.py          # 端口 8090
python test_smoke.py    # 冒烟测试（直驱 tick，验证跨天/落库/知识/无异常）
```

## 玩法一句话
约两万八千年后的世界，大缓变后地球转速变慢，**一天 20 小时**（清醒 12h + 睡眠 8h）。小镇破破烂烂，居民各自生活、合力重建。
你是**失忆的旅行者**（古玉佩 = 封印钥匙）：每天 12 点行动力（1 AP = 过 1 小时），"休息"结束今天；每 13 天多 1 点**十三时**夜间行动力，可深夜出门见别人看不见的东西；每天一次"知识"思考，触及遗迹真相会领悟技能、想起记忆碎片。

## 核心机制（回合制）
- **时间只随玩家 AP 前进**（无闲时自动推进）：1 AP = 1 小时，`tick.advance(hours)` + `run()` 消费 `_pending_advance`
- **AP**：每日 12（`ap_max`），十三时 = 独立的 `night_ap`（每 13 天 +1，仅夜晚可用，不混入日常 AP）
- **休息** = 结束今天 → 推进到次日清晨，AP 重置为 12
- **分层地图**：5 个地点 = 5 个独立界面，当前地点像素建筑 1.7 倍放大居中，地点栏显示名称/修缮等级/在场人数

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

## 关键设计决策（改代码前务必理解）
1. **二十时世界观**：`day_length=20`, `wake_hour=5`, `waking_hours=12`；全链（agent 作息/events 日程/前端时段/地图昼夜）按 20h 对齐
2. **纯回合制**：时间只随 AP 前进；`advance()` 排队、`wait_caught_up()` 等落地；休息结束一天
3. **玩家与 NPC 共用动作管线**：`tick._handle_action(agent, action, tick)`；craft/gather 归一化为 work；玩家 AP 在 api 检查
4. **知识是主线**：每日一次"思考"（0 AP）→ `_check_insight` 触及隐藏关键词（遗迹/石碑/十三/玉佩/地球/时间…）→ 领悟技能 + 记忆碎片
5. **十三时**：`night_ap` 独立池，仅夜晚可用，夜晚行动触发 `_night_mystery`（遗迹残响 + 夜间技能）
6. **小镇重建**：居民攒钱逐级修缮建筑（Lv1→5，阈值平方增长），修缮后资源更丰
7. **数据层单一**：所有持久化走 storage.py；schema 版本不符自动重建

## 本次重构已做（2026-08-20）
**文档 + 清理**：
- **gameplay-design-v4.md**（取代 v3）：三支柱 + 游戏感三件套
- **art-direction-v1.md**：美术方向成文（水彩软化像素、地图道路/像素小人、动效接入、死 CSS 清理）
- **路线图 Phase 6-9**（v0.5a-d）：见主计划 §4b
- **仓库清理**：删 15 个根目录一次性脚本 + k_town.db + __pycache__；归档 vision/world-v0.1/report_260528 至 docs/archive/2026-08-20/（加状态横幅）；世界观五篇入库；知识固化阈值统一 0.85

**Phase 6-8 实现（已测试）**：
- **Phase 6 情绪闭环**（emotions.py）：4 维情绪 + 事件×性格偏移 + 决策渗透 + 习惯形成（近似 RL）+ 性格演化 + 关系网传染。验证：test_emotions.py 16/16
- **Phase 7 危机干预**（crisis.py）：4 危机 + 性格化反应矩阵 + 玩家四干预 + 结局分支 + NPC 自救 + NPC 交易响应。验证：test_crisis.py 20/20
- **Phase 8 长期目标线**：身世碎片收集（5 片解锁大缓变真相）+ 重建弧线进度（/api/progress）。验证：test_progress.py 8/8

## 已知问题 / 剩余工作
- **Phase 9 UI/美术重构**（art-direction-v1.md）：地图道路/像素小人/动效接入/死 CSS 清理——待实施
- **tick.py 仍是单体（约 2000 行）**：拆分属 P2 后置，等稳定后按职责拆（勿在闭环稳定前大动）
- **断点恢复补全**：Agent 状态不落库（关掉 `auto_reset` 可保留知识/日报/快照）；要做完整存档需 Agent 实例序列化
- **平衡调优**：情绪回归速率、习惯学习率、危机概率、修缮阈值（现场看效果再调）
- **前端遗留**：CSS 里 trade/achievement/settings/tutorial 套件与 icons 未用分类为"未来功能"占位（art-direction §5 已列清理清单）；情绪 4 维/危机/身世进度需前端展示（Phase 9）
- `api.py` 的 `logger` 参数名实际是 Storage 实例（历史命名，注意别混淆）

## 路线图（读这些文档）
- `docs/design-master-plan-2026-08-04.md` — 主计划（Phase 0-5 已完成 + Phase 6-9 = v0.5 游戏感三件套 + 远期 Phase 5 世界自生成）
- `docs/product/gameplay-design-v4.md` — ★权威玩法设计（取代 v3）
- `docs/product/art-direction-v1.md` — ★权威美术方向
- `docs/product/世界观/` — 世界观基底五篇（末世重建/20h/失忆旅行者）
- `docs/plans/2026-08-04-gameplay-plan.md` — v0.4 功能/实现安排（历史）
- `docs/product/world-self-generation.md` — 世界自生成设计（NPC 设计游戏资产，远期支柱，Phase 5）
- `docs/development-progress.md` — 进度记录
- `docs/archive/2026-08-20/` — 过时文档归档（vision/world-v0.1/report_260528，仅历史参考）

## 提交规范
按 CLAUDE.md：`<type>(<scope>): <English>` + 中文描述；分批 chore/refactor → feat/fix → docs；禁 `git add -A`。
