# AGENTS.md

This file provides guidance to AI coding agents (Codex, Copilot, Cursor, etc.) when working in this repository.

## Project: K-town

A multi-agent town simulation game. Residents are independent AI agents with persistent memory, knowledge, goals, and social relationships — not player-centric NPCs. Players can observe or join as human residents.

**Current state (v0.3-refactor)**: 12 agents, 5 locations (square/workshop/wilderness/school/mine), 22 event types. Agents move, work, socialize, record & spread knowledge. Player is a resident (12 AP/day) who can observe and lightly influence the town.

> **Direction**: see `docs/design-master-plan-2026-08-04.md` (the authoritative roadmap). The old Go/Godot/PostgreSQL plan is abandoned.

## Tech Stack (actual)

- **Client**: HTML + CSS + vanilla JS (`templates/index-v2.html` + `static/*-v2.*`) — SVG hand-drawn map, WebSocket realtime
- **Server**: Python 3.11 + FastAPI + Uvicorn (`main.py` → port 8090) — tick loop, event bus, agent loop
- **Agent Runtime**: rule-based 5-layer decision (`agent.py:decide`); LLM only for key decisions (`llm.py`, rate-limited + cached, mock without key)
- **DB**: SQLite via `storage.py` — the ONE data access layer (WAL, authoritative DDL, schema-version rebuild)

## Agent Tiers (future scale-up, not yet enabled)

1. **Cold** — far from players, low-frequency updates (schedule + summary only)
2. **Warm** — active areas, rule/utility-AI decisions, occasional LLM
3. **Hot** — interacting with players, higher LLM frequency

## Repository Layout

```
K-town/
  CLAUDE.md              — Claude Code project guide
  AGENTS.md              — Generic AI coding agent guide (this file)
  .gitignore             — excludes docs-local/ (personal workspace)
  README.md              — project overview
  docs/                  — shared documentation (git tracked)
    product/             — product design
    architecture/        — architecture docs
    plans/               — implementation plans
    development-progress.md
    handoff.md           — AI session handoff state
  docs-local/            — personal notes/drafts (git ignored, AI agents should NOT modify)
```

## Development Workflow

1. **PRD first** — define goals, non-goals, core experience, risks, acceptance criteria before coding
2. **Implementation Plan** — architecture, file structure, task breakdown, data models, API, test approach, commit messages
3. **Atomic commits** — one task per commit (e.g., "add Agent schema"), not "implement entire system"
4. **Parallel sub-agents** — split by boundary (Go server, Godot client, schema, docs) and work concurrently
5. **Handoff state** — after every session, update `docs/handoff.md` with completed work, test results, risks, next step

## Documentation Structure

```
docs/
  product/
    vision.md, world-v0.1.md, agent-model.md, knowledge-system.md
  architecture/
    overview.md, backend-go.md, godot-client.md, logging-and-replay.md
  plans/
    YYYY-MM-DD-feature.md
  development-progress.md
  handoff.md
```

## Git Commit Conventions

**Message format**: `<type>(<scope>): <English one-liner>` + blank line + `<Chinese description (≤100 chars)>`

**Types**: feat / fix / docs / refactor / perf / chore

**Batch order**: chore/refactor → feat/fix → docs (infrastructure first, docs last)

**Safety**:
- Never `git add -A` / `git add .` — stage only relevant files
- Never amend — always create a new commit
- Never `--no-verify` / `--no-gpg-sign`
- On hook failure: fix issues, create new commit (don't amend)

## Key Principles

- Agents are the core — persistent identity, state, memory, knowledge, goals, relationships
- Knowledge is structured (`KnowledgeClaim`), not raw chat logs — evolves via observation, summarization, propagation, disputation, correction
- Developers shape via world patches (rules, events, locations), not scripted stories
- Log everything: world events, agent decisions, knowledge changes → feeds newspapers, diaries, debugging, replays
