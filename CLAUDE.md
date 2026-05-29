# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: K-town

K-town is a multi-agent town simulation game. Residents (AI agents) have independent thoughts, memories, knowledge, goals, and social relationships — they are NOT player-centric NPCs. Players can observe or join as human residents. The core loop: the environment generates events → agents perceive them → knowledge evolves → social transmission occurs → developers and players observe and adjust the world.

First deliverable (v0.1): a 2D town map, 10 agents, 3 locations, 5 event types. Agents can move, observe, record knowledge, converse, and spread rumors. A player can enter and influence one event.

## Tech Stack (planned)

| Layer | Technology |
|-------|-----------|
| Client | Godot 2D (C# or GDScript) |
| Game Server | Go — tick loop, event bus, agent state machines, real-time sync |
| Agent Runtime | Rule-based decisions in Go; LLM calls reserved for key decisions, complex dialogue, knowledge summarization, and planning |
| Database | PostgreSQL (structured state) + pgvector or Qdrant (semantic memory) |
| Cache/Queue | Redis |
| Communication | WebSocket (real-time state sync), HTTP (player actions) |

### Agent Tiers (for scaling to 1000+ agents)

1. **Cold** — far from players, no key events. Low-frequency updates, schedule + summary only.
2. **Warm** — active areas, socializing/working/exploring. Rule/utility-AI decisions, occasional LLM.
3. **Hot** — interacting with players or in critical events. Higher LLM frequency.

## Development Workflow

This project is designed for AI-assisted development. The workflow is:

1. **Write a PRD** for each major system before coding (see `docs/report_260528_001.md` §5 for template).
2. **Write an Implementation Plan** from the PRD — include goal, architecture, file structure, task breakdown, data models, test approach, acceptance criteria, and suggested commit messages.
3. **Each task = one commit.** Split features into granular, independently committable units (e.g., "add Agent schema", not "implement entire agent system").
4. **Use sub-agents** for parallelizable work (e.g., one agent on Go server, one on Godot client, one on schema/migrations).
5. **Leave handoff state** after every session in `docs/handoff.md` — what was completed, tests passing, remaining risks, next step.

### Documentation as context cache

Every completed phase should update docs so future Claude Code sessions can resume without re-scanning the entire repo. Core docs:

```
docs/
  product/
    vision.md              — long-term vision, non-goals, core experience
    world-v0.1.md          — town, locations, resources, event types
    agent-model.md         — agent state, memory, goals, behavior strategies
    knowledge-system.md    — KnowledgeClaim, propagation, conflict, solidification
  architecture/
    overview.md            — system architecture diagram
    backend-go.md          — Go service boundaries, modules, APIs
    godot-client.md        — client scenes, sync, UI
    logging-and-replay.md  — event logs, agent decision logs, knowledge change logs, replay/debug
  plans/
    YYYY-MM-DD-feature.md  — per-feature implementation plans
  development-progress.md  — version progress tracker
  handoff.md               — AI session handoff state
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
2. 禁止提交 `agentEnv.local`、`.data/`、`wiki/`、`uploads/*`、`V*.sql`
3. 禁止 amend，永远创建新 commit
4. 禁止 `--no-verify`、`--no-gpg-sign`
5. hook 失败时修复后创建新 commit，不回退 amend

### 工作流

1. `git status` + `git diff` 分析变更
2. 按类型分组文件
3. 每组独立 add + commit
