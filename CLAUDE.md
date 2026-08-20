# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: K-town

K-town is a multi-agent town simulation game. Residents (AI agents) have independent thoughts, memories, knowledge, goals, and social relationships — they are NOT player-centric NPCs. Players can observe or join as human residents. The core loop: the environment generates events → agents perceive them → knowledge evolves → social transmission occurs → developers and players observe and adjust the world.

First deliverable (v0.1): a 2D town map, 12 agents, 5 locations, 22 event types. Agents move, observe, record knowledge, converse, and spread rumors. A player can enter and influence the town as a resident.

> **重要**：方向与路线图以 `docs/design-master-plan-2026-08-04.md` 为准。旧技术栈（Go/Godot/PostgreSQL）已废弃；本仓库实际为 Python + Web 实现（见下方"实际技术栈"）。

## Tech Stack (actual)

| Layer | Technology |
|-------|-----------|
| Client | HTML + CSS + vanilla JS（SVG 手绘地图、WebSocket 实时推送） |
| Game Server | Python 3.11 + FastAPI + Uvicorn（tick 循环、事件总线、Agent 状态机、REST + WebSocket） |
| Agent Runtime | 规则引擎（agent.py 五层决策）；LLM 仅用于关键决策（llm.py，每日限次 + 缓存，无 key 走 mock） |
| Database | SQLite（`storage.py` 单一数据访问层，WAL，权威 DDL，schema 版本检测自动重建） |
| Communication | WebSocket（实时状态同步）、HTTP（玩家动作） |

### Agent Tiers（未来扩展，当前 12 Agent 暂不启用）

1. **Cold** — 远离玩家、无关键事件。低频更新。
2. **Warm** — 活跃区域。规则/效用决策，偶尔 LLM。
3. **Hot** — 与玩家互动或关键事件中。更高 LLM 频率。

## Repository Layout

```
K-town/
  CLAUDE.md              — Claude Code 项目指南（本文件）
  AGENTS.md              — 通用 AI 编码助手指南（Codex、Copilot 等）
  README.md              — 项目介绍
  main.py                — 服务入口（python main.py，端口 8090）
  config.py / config.yaml— 配置（config.yaml 含 LLM key，已被 .gitignore 忽略）
  models.py              — dataclass 数据模型（知识/状态/事件/目标/记忆）
  world.py               — World：地点/资源/价格/天气（地点清单唯一来源）
  events.py              — EventBus + EventScheduler（每日事件日程）
  agent.py               — Agent：perceive/think/decide + populate_agents()
  knowledge.py           — 知识引擎（KnowledgeClaim 观察/传播/质疑/固化）
  storage.py             — ★唯一数据访问层（单一连接/权威 DDL/全部方法）
  tick.py                — TickEngine：advance→事件→决策→执行→结算→日报
  llm.py                 — LLM 客户端（Anthropic 兼容，mock 兜底）
  api.py                 — FastAPI 路由 + WebSocket（玩家动作统一走 tick._handle_action）
  test_smoke.py          — 冒烟测试（python test_smoke.py，验证核心闭环跨天落库）
  templates/index-v2.html + static/*-v2.* — 唯一前端
  docs/                  — 共享文档案（Git 跟踪）
    product/             — 产品设计文档（★gameplay-design-v4.md 玩法 / art-direction-v1.md 美术 / 世界观/ 五篇 / knowledge-system / agent-model）
    architecture/        — 架构文档（overview 为现状，backend-go/godot-client 为废弃方案）
    plans/               — 实施计划
    design-master-plan-2026-08-04.md — ★当前路线图（Phase 0-5 已完成；Phase 6-9 = v0.5 游戏感三件套）
    development-progress.md
    handoff.md           — AI session 交接状态
    archive/             — 过时文档归档（2026-08-20 起，只归档不删除）
  docs-local/            — 个人笔记/草稿/实验文件（Git 忽略，AI 不应修改）
```

> 已被删除的废弃件：`client/`（Godot）、`server/`（Go 残留）、v1 前端（index.html + style.css/app.js/town-map.js/sound.js/visualization.js）、孤儿模块（db.py / database.py / logger.py / static_db.py / knowledge_v3.py / commands.py / fix_goal.py / update_api.py / test_full.py）、根目录一次性脚本（check_cliches.py / fix_*.py / verify*.py / final_check.py / find_exact.py，2026-08-20 清理）。
>
> **仓库卫生规则**：一次性修复/验证脚本不入库（用完即删或放 docs-local/）；开发产生的临时 db/pycache 已被 .gitignore 覆盖。

## Development Workflow

This project is designed for AI-assisted development. The workflow is:

1. **Write a PRD** for each major system before coding (see `docs/archive/2026-08-20/report_260528_001.md` §5 for template — 已归档，仅作模板参考).
2. **Write an Implementation Plan** from the PRD — include goal, architecture, file structure, task breakdown, data models, test approach, acceptance criteria, and suggested commit messages.
3. **Each task = one commit.** Split features into granular, independently committable units (e.g., "add Agent schema", not "implement entire agent system").
4. **Use sub-agents** for parallelizable work (e.g., one agent on backend systems, one on frontend, one on docs/schema).
5. **Leave handoff state** after every session in `docs/handoff.md` — what was completed, tests passing, remaining risks, next step.

### Documentation as context cache

Every completed phase should update docs so future Claude Code sessions can resume without re-scanning the entire repo. Core docs:

```
docs/
  product/
    gameplay-design-v4.md  — ★权威玩法设计（三支柱 + 游戏感三件套：情绪闭环/危机干预/长期目标）
    art-direction-v1.md    — ★权威美术方向（风格锚点/地图升级/动效/死 CSS 清理）
    世界观/               — 世界观基底五篇（末世重建/20h/失忆旅行者）
    agent-model.md         — agent state, memory, goals, behavior strategies
    knowledge-system.md    — KnowledgeClaim, propagation, conflict, solidification
    world-self-generation.md — 远期支柱：NPC 按意志设计游戏资产（资产原型=可执行知识，Phase 5）
  architecture/
    overview.md            — system architecture diagram
    logging-and-replay.md  — event logs, agent decision logs, knowledge change logs, replay/debug
  plans/
    YYYY-MM-DD-feature.md  — per-feature implementation plans
  development-progress.md  — version progress tracker
  handoff.md               — AI session handoff state
  archive/                 — 过时文档归档（只归档不删除）
```

## Key Design Principles

- Agents are the core, not the player. Every agent maintains persistent identity, state, memory, knowledge, goals, and relationships.
- Knowledge is structured (`KnowledgeClaim` with subject, claim, source, confidence, scope, contradictions), not raw chat logs. Knowledge evolves through observation, summarization, propagation, disputation, and correction.
- Creation is template-based initially: items unlocked by resources + skills, organizations from shared goals + relationships, knowledge from observation + reasoning.
- Developers shape the world through patches (new locations, rule changes, events, agent model tweaks), not by scripting stories.
- Log everything from day one: world events, agent decisions, knowledge changes. These feed into town newspapers, agent diaries, developer debugging, replays, and AI context summaries.

## Git 提交规范

当用户说"提交"/"commit"时，严格按以下规则执行。

### 消息格式

```
<type>(<scope>): <English one-liner>

<中文描述(≤100字)>
```

### 分类

| type | 说明 |
|------|------|
| feat | 新功能 |
| fix | 修复 |
| docs | 文档 |
| refactor | 重构 |
| perf | 性能优化 |
| chore | 脚本/配置/工具 |

### 分批规则

不同类型变更必须分批提交。顺序：**chore/refactor → feat/fix → docs**（基础在前，文档最后）。

### 安全规则

1. 禁止 `git add -A` / `git add .`，仅暂存相关文件
2. 禁止 amend，永远创建新 commit
3. 禁止 `--no-verify`、`--no-gpg-sign`
4. hook 失败时修复后创建新 commit，不回退 amend

### 工作流

1. `git status` + `git diff` 分析变更
2. 按类型分组文件
3. 每组独立 add + commit
