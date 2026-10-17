# Architecture

## The three primitives

An "agent OS" is, at minimum, three things no single agent provides:

1. **A task board** — a shared queue with a claim/complete lifecycle so many
   agents can work in parallel without a human shuttling work item by item.
2. **A shared memory** — a store every agent reads before and writes after
   work, so the system compounds instead of restarting each session.
3. **A digest** — a daily fold of everything that happened, so the owner can
   supervise by exception instead of watching channels all day.

`agentos-kit` implements (1) as working code and (2)+(3) as battle-tested
templates + protocols, because (1) is where engineering discipline pays and
(2)/(3) are trivially reimplementable against your own tooling.

## Board data flow

```
you ──create──▶ board server ──▶ SQLite (WAL)
                 ▲   |
   claim/complete│   └──board.json──▶ dashboard UI / digest recipe
   fail/block    │
                 │
        agent lanes (goose ACP sessions, cron jobs, CI bots, humans)
```

- **Single writer.** Every mutation goes through the board server process
  (a `threading.Lock` + WAL SQLite). Agents never touch the DB file. This
  removes the entire class of lost-update races between concurrent agents.
- **Guarded transitions.** Each status change is a guarded `UPDATE ... WHERE
  status = <expected>`; an already-claimed card cannot be double-claimed
  (the loser gets HTTP 409 and must pick another card).
- **Receipts.** `complete` requires a summary (and optional artifact paths).
  `done` cards are the audit trail; digests and memory writes are sourced
  from them. Rows are kept forever (tiny), views are capped (7-day window,
  `?done_days=all` for full history).

## Status model

`backlog → claimed → done | failed`, plus `blocked` (owner attention
required) which can come from either `backlog` or `claimed`, and `unblock`
returns it to `backlog`. There is no auto-anything: done/failed/blocked are
drivers of *reports*, never of *actions*.

## The dispatch seam

`core/dispatch.sh` is the only bridge between the board and your agent
infrastructure. It maps a card's `role` to agents in `agents.json` and runs
each agent's `notify` command template — one shell line that can be anything:
a chat mention (see `docs/buzz-adapter.md`), a webhook, an email, a job
queue. It is DRY by default and rate-limited per card, and an optional
`alive` probe skips lanes that are down.

## Memory architecture

The kit does not ship a memory server; it ships a *protocol* that outlives
any specific backend (`templates/persona-protocol.md`):

- **pluggable backends**: an MCP memory server, a vector DB, gbrain/Obsidian/
  plain markdown — anything readable and writable by all agents
- **namespacing**: one prefix per project (`<prefix>/...`), so several
  projects can share one backend without cross-talk
- **two triggers only**: read-once-per-task, write-once-per-task — the
  density that keeps retrieval trustworthy (see `docs/memory-protocol.md`)

## What is intentionally absent

- No agent runtime: bring goose, cron, CI — the kit only needs the lane to
  be able to run a shell command.
- No approval automation: irreversible actions stay behind human gates.
- No user management: the token is a shared secret, appropriate for a
  single-operator or small-trusted-team deployment.