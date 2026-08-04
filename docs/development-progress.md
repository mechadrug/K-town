# K-town 开发进度

> 当前路线图：`docs/design-master-plan-2026-08-04.md`（修正版主计划，Phase 0–4）
> 版本口径：v0.3-基底重构（2026-08-04）

## v0.2.1 → v0.3 基底重构（2026-08-04）

### 审计结论（承接设计主计划 §0）
原 v0.2.1 并非"功能完善"：核心缺陷是**决策结果从不执行**（`_handle_action` 零调用点）、
**数据层 4 套并存互相冲突**（tick 10 写库即崩、tick 24 日报即崩）、**前端入口 GBK 编码 500**、
**前端-后端协议失配**。模拟从未成功跨天（DB 中 day_summaries=0 行）。

### 本次完成（Phase 0 落地）
- [x] **统一持久层** `storage.py`：单一 sqlite 连接、权威 DDL、schema 版本检测自动重建，
      取代 db.py / database.py / logger.py / static_db.py 四套；main/tick/api 共享同一实例。
- [x] **接通决策→执行链**：`step()` 在 `decide()` 后调用 `_handle_action(agent, action, tick)`；
      玩家动作同样走此管线。修复其未定义变量 `tick`、缺失方法、假知识传播等 bug。
- [x] **Agent 生活节奏**：新增"傍晚广场聚集/社交"决策层，小镇有真实每日空间节律（移动可见）。
- [x] **Agent 接口补全**：`to_dict()` 含 goals/diary/personality/location_cn/role_cn；新增 `get_location_cn`。
- [x] **api.py 修复**：状态载荷收敛为 `_build_state_payload()`（消除 3 处重复）；
      `/api/history`、`/api/logs/agents` 不再 500；玩家动作支持 work/rest/add_claim/reset/talk。
- [x] **前端修复**：`index-v2.html` 由 GBK 转 UTF-8（GET / 不再 500）；`app-v2.js` 协议对齐
      （move→target）、对话接线真实 `/api/dialogue/*`、档案目标/日记真实渲染；
      `animations-v2.css` 未闭合注释修复、`style-v2.css` 补 `--bg-card`。
- [x] **清理**：删除 client/（Godot）、server/（Go）、v1 前端六件套、9 个孤儿/一次性模块、
      一次性文档脚本、NUL 损坏的 .gitignore（重写）、修复 run_server.ps1（python main.py）、
      k_town.db 移出 git 跟踪。
- [x] **冒烟测试** `test_smoke.py`：60 tick 全通过（Agent 移动、体力消耗、跨 2 天、
      日报内存+落库、知识产生、无异常）。

### 验证结果（2026-08-04）
- ✅ `python test_smoke.py` → ALL PASS OK
- ✅ `python main.py` 启动 8090；GET / 200；/api/state、/api/history/1、/api/logs/agents/1 全 200
- ✅ 服务器存活 ≥15 tick 无异常；5 地点均有居民；派系生成；知识 100+ 条

### 已知问题 / 下一步（详见设计主计划 Phase 1–4）
- 知识尚未持久化（knowledge.py 为内存态）——路线图 Phase 4.3
- narrative/town_evolution/achievements/trade_market 已实例化但冻结（待核心闭环呼吸后再取舍）
- Agent 档案 diary 暂为空（无日记写入逻辑）
- tick.py 仍为单体（1961 行），拆分在 Phase 0 之后（P2）
