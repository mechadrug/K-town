# AGENTS.md

This file provides guidance to AI coding agents (Codex, Copilot, Cursor, etc.) when working in this repository.

## Project: K-town

A multi-agent town simulation game. Residents are independent AI agents with persistent memory, knowledge, goals, and social relationships — not player-centric NPCs. Players can observe or join as human residents.

**v0.1 target**: 2D town map, 10 agents, 3 locations, 5 event types. Agents move, observe, record knowledge, converse, spread rumors. Player can enter and influence one event.

## Tech Stack (planned)

- **Client**: Godot 2D (C# or GDScript)
- **Server**: Go — tick loop, event bus, agent state machines, WebSocket sync
- **Agent Runtime**: Rule-based (Go) for routine decisions; LLM for key decisions, dialogue, summarization
- **DB**: PostgreSQL + pgvector/Qdrant (semantic memory), Redis (cache/queue)

## Agent Tiers

1. **Cold** — far from players, low-frequency updates (schedule + summary only)
2. **Warm** — active areas, rule/utility-AI decisions, occasional LLM
3. **Hot** — interacting with players, higher LLM frequency

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
- Never commit `agentEnv.local`, `.data/`, `wiki/`, `uploads/*`, `V*.sql`
- Never amend — always create a new commit
- Never `--no-verify` / `--no-gpg-sign`
- On hook failure: fix issues, create new commit (don't amend)

## Key Principles

- Agents are the core — persistent identity, state, memory, knowledge, goals, relationships
- Knowledge is structured (`KnowledgeClaim`), not raw chat logs — evolves via observation, summarization, propagation, disputation, correction
- Developers shape via world patches (rules, events, locations), not scripted stories
- Log everything: world events, agent decisions, knowledge changes → feeds newspapers, diaries, debugging, replays
