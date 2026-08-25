# AGENTS.md

This file provides guidance to AI coding agents (Codex, Copilot, Cursor, etc.) when working in this repository.

## Project: K-town

A multi-agent town simulation game. Residents are independent AI agents with persistent memory, knowledge, goals, and social relationships — not player-centric NPCs. Players can observe or join as human residents.

**Current code state**: 12 agents, 5 locations (square/workshop/wilderness/school/mine), 22 event types, and a four-week campaign Demo. The emotion loop, crisis intervention, long-term progress, versioned save/restore, deterministic replay, and chapter effects are connected through the playable loop.

> **Current product direction (2026-08-25)**: `docs/product/gameplay-design-v6.md` is the four-week Demo baseline, extending the v5 choice-and-consequence loop. Read it with `docs/product/gameplay-design-v5.md`, `docs/product/world-view-v3.md`, `docs/product/art-direction-v2.md`, `docs/plans/2026-08-25-multiweek-demo-plan.md`, and `docs/architecture/frontend-v2.md` before changing code. The old Go/Godot/PostgreSQL plan is abandoned; the 2026-08-04 master plan and v4/v1 designs are historical implementation references.

## Tech Stack (actual)

- **Client**: HTML + CSS + vanilla JS (`templates/index-v2.html` + `static/*-v2.*`) — SVG hand-drawn map, WebSocket realtime
- **Server**: Python 3.11 + FastAPI + Uvicorn (`main.py` → port 8090) — tick loop, event bus, agent loop
- **Agent Runtime**: rule-based 5-layer decision (`agent.py:decide`); LLM only for key decisions (`llm.py`, rate-limited + cached, mock without key)
- **DB**: SQLite via `storage.py` — the ONE data access layer (WAL, authoritative DDL, schema-version rebuild)

## Runbook And Environment Notes

This repository is developed on Windows with the Conda environment `python_class`.
The validated interpreter is:

```powershell
E:\anaconda\envs\python_class\python.exe
```

Use the project launcher for a normal foreground server run:

```powershell
.\run_server.ps1
```

`run_server.ps1` stops the previous process listening on port 8090 and runs the new server with `python_class` in the current terminal. For a detached run, use `scripts/ensure-start-server.ps1` without `-Foreground`; it waits for `GET /api/state` to return HTTP 200, writes logs under `logs/`, and tracks the PID in `scripts/server.pid`.

Do not use bare `python` in this workspace. In the current machine it resolves to the Conda base interpreter (`E:\anaconda\python.exe`), which produces Windows error `0xc0000022` before the application starts. Do not assume that activating a shell changed the interpreter; verify with:

```powershell
& "E:\anaconda\envs\python_class\python.exe" -c "import sys; print(sys.executable)"
```

Install dependencies through the same interpreter:

```powershell
& "E:\anaconda\envs\python_class\python.exe" -m pip install -r requirements.txt
```

### Data And Test Safety

- `main.py` reads `server.reset_on_start` explicitly: `false` resumes the versioned save, while `true` starts a new game and clears managed tables. Do not run reset-based tests against a live server.
- Core tests, including `test_progress.py`, use isolated temporary SQLite databases. Stop any live server before running a test that intentionally targets a persistent path.
- `test_crisis.py` and `test_emotions.py` are in-memory tests. On Windows, set `$env:PYTHONIOENCODING = 'utf-8'` if the console cannot print its symbols.
- `config.yaml` is local/ignored and may contain an LLM credential. Never commit or disclose it; `LLM_API_KEY` overrides the YAML key through `config.py`.

## Current Gaps And Priorities

The four-week Demo has passed its delivery gate, including desktop/mobile/reduced-motion browser acceptance, fixed-seed replay, save/restore, and the full isolated test suite. Future work is optional:

1. Tune chapter branches, action costs, and ending thresholds only with before/after fixed-seed evidence.
2. Clarify the full-town activity layer if the single-location stage becomes a UX bottleneck.
3. Split `tick.py` only before adding another large system, after behavior remains stable.

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
  campaign.py            — chapter director and campaign effects
  game_state.py          — versioned save/restore envelope
  static/                 — frontend contract, API client, views, and map
  docs-local/            — personal notes/drafts (git ignored, AI agents should NOT modify)
```

## Development Workflow

1. **PRD first** — define goals, non-goals, core experience, risks, acceptance criteria before coding
2. **Implementation Plan** — architecture, file structure, task breakdown, data models, API, test approach, commit messages
3. **Atomic commits** — one task per commit (e.g., "add Agent schema"), not "implement entire system"
4. **Parallel sub-agents** — split by boundary (backend systems, frontend, schema, docs) and work concurrently
5. **Handoff state** — after every session, update `docs/handoff.md` with completed work, test results, risks, next step

## Documentation Structure

```
docs/
  product/
    gameplay-design-v5.md       — current gameplay baseline
    world-view-v3.md            — current seven-day world baseline
    art-direction-v2.md         — current visual/UI direction
    agent-model.md, knowledge-system.md
  architecture/
    overview.md, backend-go.md, godot-client.md, logging-and-replay.md
  plans/
    2026-08-23-rebuild-plan.md  — current implementation plan
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
