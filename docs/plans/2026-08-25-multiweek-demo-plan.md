# K-town 四周 Demo 实施计划

> **目标**：把 v5 的七天纵切片扩展为四周可玩的 Demo，同时保持动作结算、存档、回放和前端扩展边界稳定。
> **日期**：2026-08-25
> **状态**：核心代码已落地；本文作为验收和后续扩展规则。

## 1. 设计原则

- 内容数据和模拟机制分离：章节导演负责“何时出现、产生什么故事效果”，ActionResolver 负责“能否做、花多少、如何记录”。
- 前端只依赖稳定 payload，不认识章节 effect、数据库字段或 Python 内部类。
- 每个新内容都必须有即时反馈和次日可观察后果。
- 新系统先增加隔离测试，再接入默认服务；测试不碰正在运行的 `k_town.db`。
- 扩展优先沿现有边界加数据，只有边界承载不了新语义时才拆模块。

## 2. 已落地结构

```text
campaign.py
  ChapterDefinition / CAMPAIGN_EFFECTS / CampaignDirector
       │                 │
       │                 └── 解释请求 option.effect，写 flag/score/marker/knowledge
       └── 按 current_day 解锁章节、注册请求、结算章节和最终结局

requests.py ──> ActionResolver ──> ActionResult ──> API/WS ──> 前端契约与视图
                     │                  │
                     └── AP/时间/前置/日志   └── changes/story_beats/next_observation

game_state.py <── world + agents + knowledge + requests + campaign + RNG
```

## 3. 交付切片

### Slice A：内容与导演

- [x] 第 1 周三条居民请求保留并纳入统一章节评分。
- [x] 第 2 周学校蓄水槽、旧矿道路线。
- [x] 第 3 周商路公开/保留、学校借灯/矿石灯火。
- [x] 第 4 周归灯集三种导向。
- [x] 第 29 天最终结局和章节历史。

### Slice B：后端契约

- [x] `GET /api/campaign`。
- [x] `/api/state.campaign`、`campaign_markers`、`today_threads` 章节压力。
- [x] campaign state 纳入版本化存档/恢复。
- [x] 章节分支的场景标记、知识、关系、准备度和评分变化。

### Slice C：前端扩展边界

- [x] 独立 `campaign-view-v2.js` 只渲染 campaign payload。
- [x] `state-contract-v2.js` 归一化 state/action result。
- [x] `api-client-v2.js` 集中 REST/WebSocket 边界。
- [x] `app-v2.js` 动态按钮迁移到 `data-app-action` 事件委托。
- [x] 运行时浏览器验证新前端接线（桌面、390px、reduced-motion）。

### Slice D：质量与交接

- [x] 跨周、分支、结局、存档测试。
- [x] 完整测试输出在当前解释器下复跑并清理临时数据库。
- [x] 修复 `git diff --check` 和旧文档中的“仅七天”描述。
- [x] 只 stage 相关文件，按仓库规范提交并推送。

## 4. 新章节接入协议

1. 在 `campaign.py` 添加 `ChapterDefinition`：`id/week/unlock_day/title/pressure/objective/request_ids`。
2. 在 `requests.py` 用 `chapter_id` 标记请求；选项只引用结构化 effect ID。
3. 在 `CAMPAIGN_EFFECTS` 增加 effect 定义；effect 只能操作白名单：flag、score、world marker、preparedness、requester tie、knowledge。
4. 让 `CampaignDirector.sync_for_day()` 负责解锁和播发章节事件。
5. 让 `ActionResolver._handle_request_respond()` 调用导演；不要在 API 或前端重复实现效果。
6. 扩展 `test_campaign.py`：解锁日、分支差异、终局、round-trip、至少一个次日可观察结果。
7. 前端只使用 `campaign` 的稳定字段；如果要显示新内容，先更新契约和独立 renderer。

## 5. 风险与控制

| 风险 | 控制方式 |
|---|---|
| 时间被多个入口重复扣除 | 所有动作走 `ActionResolver`；API/WS 只转换 payload |
| 新章节污染旧存档 | `CAMPAIGN_STATE_VERSION` + restore 校验；旧版本走明确迁移/拒绝 |
| 章节内容只变数字不可见 | 每个 effect 必须写 `changes/story_beats/next_observation` 或世界 marker |
| 前端新增按钮变成 inline JS | 统一 `data-app-action`，主应用只有一个 click router |
| 测试重置开发存档 | 测试构造临时路径；默认服务与测试分离 |
| tick.py 越来越难维护 | 先保持 `CampaignDirector`、`ActionResolver`、API payload 三个边界，后续再拆 tick |

## 6. 验收命令

```powershell
$env:PYTHONIOENCODING = "utf-8"
& "E:\anaconda\envs\python_class\python.exe" test_actions.py
& "E:\anaconda\envs\python_class\python.exe" test_campaign.py
& "E:\anaconda\envs\python_class\python.exe" test_phase2.py
& "E:\anaconda\envs\python_class\python.exe" test_phase3.py
& "E:\anaconda\envs\python_class\python.exe" test_smoke.py
& "E:\anaconda\envs\python_class\python.exe" test_save_restore.py
& "E:\anaconda\envs\python_class\python.exe" test_replay.py
& "E:\anaconda\envs\python_class\python.exe" test_crisis.py
& "E:\anaconda\envs\python_class\python.exe" test_emotions.py
& "E:\anaconda\envs\python_class\python.exe" test_progress.py
node --check static/app-v2.js
node --check static/api-client-v2.js
node --check static/state-contract-v2.js
node --check static/campaign-view-v2.js
```
