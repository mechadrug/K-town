# K-town 开发交接记录

> 交接给下一位开发者。先读本文件，再读 `docs/design-master-plan-2026-08-04.md`（路线图）与 `docs/product/gameplay-design-v3.md`（玩法设计）。

## 当前状态（2026-08-04，v0.4）
- **版本**：v0.4 —— 可玩的观察型小镇 + 回合制 + 二十时世界观
- **分支**：feature/v0.2-game-ui；工作树干净，全部已提交
- **技术栈**：Python 3.11 + FastAPI + SQLite + HTML/JS(WebSocket)。**无** Go/Godot/PostgreSQL（已废弃并删除）

## 运行方式
```powershell
cd C:\Users\azi\Desktop\K-town-demo-v0.1.0
python main.py          # 端口 8090
python test_smoke.py    # 冒烟测试（直驱 tick，验证跨天/落库/知识/无异常）
```

## 玩法一句话
几十万年后的世界，地球转速变慢，**一天 20 小时**（清醒 12h + 睡眠 8h）。小镇破破烂烂，居民各自生活、合力重建。
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

## 已完成（v0.4 全板块 + 两轮审计清理）
- P0 前端四问题修复、对话重设计、小镇脉搏、每日目标、知识流动视图
- P1 日记/关系后果/食物经济/事件链
- 世界观 20h + 回合制 + 十三时 + 每日领悟 + 小镇重建
- 两轮穷尽式审计清理：删死代码/死符号/防御性代码（见 commit 6b4060e / cc0875b）

## 已知问题 / 剩余工作
- **tick.py 仍是单体（约 1900 行）**：拆分属 P2 后置，等稳定后按职责拆（勿在闭环稳定前大动）
- **断点恢复补全**：Agent 状态不落库（关掉 `auto_reset` 可保留知识/日报/快照）；要做完整存档需 Agent 实例序列化
- **平衡调优**：技能成长、修缮阈值、食物经济、对话门控、每日目标池（现场看效果再调）
- **世界观伏笔深化**：20 小时之谜、遗迹发现链、古玉佩来历、观星/溯源等技能深度效果
- **前端遗留**：CSS 里 trade/achievement/settings/tutorial 套件与 icons 未用分类为"未来功能"占位，低优先可清理
- `api.py` 的 `logger` 参数名实际是 Storage 实例（历史命名，注意别混淆）

## 路线图（读这些文档）
- `docs/design-master-plan-2026-08-04.md` — 主计划（Phase 0-4 + 系统取舍 + 远期 Phase 5 世界自生成）
- `docs/product/gameplay-design-v3.md` — 权威玩法设计
- `docs/plans/2026-08-04-gameplay-plan.md` — v0.4 功能/实现安排
- `docs/product/world-view-v2.md` — 世界观（含"为什么失忆"伏笔）
- `docs/product/world-self-generation.md` — 世界自生成设计（NPC 设计游戏资产，远期支柱，2026-08-06 定稿）
- `docs/development-progress.md` — 进度记录

## 提交规范
按 CLAUDE.md：`<type>(<scope>): <English>` + 中文描述；分批 chore/refactor → feat/fix → docs；禁 `git add -A`。
