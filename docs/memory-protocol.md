# The shared-memory protocol

The most valuable — and most fragile — part of an agent team is one memory
that every agent reads before and writes after work. Fragile because free-form
multi-writer memory degenerates into noise within days. The protocol is
deliberately narrow:

## The two triggers

1. **READ once per task** (not per turn): one scoped search on the task's
   component/topic before starting work. Nothing relevant → move on. Do not
   retry with variations — that's how agents burn tokens relearning nothing.
2. **WRITE on completion or gotcha**: one structured note —
   - key: `<prefix>/<task-or-card-id>-<short-slug>`
   - tags: agent name, task id, one domain word
   - body: 3–5 lines — outcome, decisions, gotchas for the next agent

## Hard rules

- **Never store secrets.** Credentials live in secret managers; memory lives
  forever and gets read by every lane.
- **Dedupe**: search before write; update the existing page instead of
  creating a near-duplicate.
- **No free-form journaling.** If it isn't one of the two triggers, it
  doesn't belong in shared memory.

## Why the prefix matters

Namespace every page under the project prefix (`myproject/...`). That makes
one memory server safely shareable across all your projects, and makes bulk
operations ("list this project's decisions") trivial.

## Backend options

| Backend | Good fit | Notes |
|---|---|---|
| Plain markdown dir + git | smallest teams | greppable, versioned, no services; no semantic search |
| MCP memory server | goose-native teams | the agent already speaks MCP; check multi-client concurrency |
| gbrain / vector stores | larger state | Postgres+pgvector behind gbrain: multi-client safe, hybrid keyword+vector retrieval |
| Obsidian/notion-style vault | human-in-the-loop teams | humans and agents co-edit; mind write conflicts |

## Backfill (one-time)

Import the knowledge that currently lives nowhere durable — the gotchas in
people's heads, the key-decisions log, the spec index. On into the shared
store under the project prefix, idempotently, then re-run after major doc
changes. In the reference deployment this made the difference between "memory"
and "archive nobody queries".

## Anti-pattern (observed in the wild)

Auto-injecting "relevant memories" into every turn, or agents writing
observations every turn. Both feel productive and destroy precision within a
week. The two-trigger rule exists because of these.