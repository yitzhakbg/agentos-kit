# Per-project configuration

One kit, many projects. The core is shared; everything that varies lives in
a small project directory.

```text
~/agentos/
├── agentos-kit/            ← this kit (shared, read-only for projects)
└── myproject/              ← one project
    ├── agents.json         ← roster: names, notify hooks, liveness probes
    ├── .env                ← AGENTOS_BOARD_URL / _TOKEN / per-agent names
    ├── .agentos/
    │   ├── board.sqlite3   ← the board database (private to this project)
    │   ├── server.log
    │   ├── dispatch-state.json
    │   └── last-digest     ← digest cursor
    └── personas/           ← your agents' system prompts (one per agent)
```

## What is per-project

| Concern | Where | Notes |
|---|---|---|
| Board database | `$AGENTOS_BOARD_DB` | one SQLite file per project; cards, receipts, history |
| Agent roster | `agents.json` | who exists, how they're reached (notify hook), when they're available (`alive`) |
| Transport | `notify` command templates | chat mentions today, webhooks/queues tomorrow — the core never changes |
| Memory namespace | `<prefix>/...` in your memory backend | e.g. `myproject/decisions/...` — several projects can share one memory server |
| Digest outputs | recipe template fields | destination channel + memory prefix |
| Roles | card `role` field | free-form; the convention `any` matches every agent |

## Running several boards

Set distinct env sets per service instance: `AGENTOS_PORT` (8791, 8792, ...),
`AGENTOS_BOARD_DB`, `AGENTOS_BOARD_TOKEN`. Agents export the pair
(`AGENTOS_BOARD_URL`, `AGENTOS_BOARD_TOKEN`) for the project they're working
— a lane that serves two projects simply has both in its environment and
rules in its persona about which cards it may claim.

## Minimal (single-agent) variant

Even one agent + one human benefits: the board is the "what should I do next"
answer and the receipt trail. Drop the dispatcher and the chat transport;
`create` + `claim` + `complete` is the whole loop.

## The reference deployment (buzz-hive)

The production case study runs one project dir per deployment with a relay
transport (chat mentions as the notify hook), gbrain as the shared memory,
launchd watchdogs as the dispatcher timer, and roles exactly matching agent
names. See `examples/` for the sanitized description.