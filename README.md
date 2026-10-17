# agentos-kit

**Run your AI agents as one operating system, not a pile of tabs.**

`agentos-kit` is a small, project-agnostic kit that implements the three
primitives every "agent OS" needs, distilled from running a production
7-agent goose hive:

1. **One task board** — SQLite + a tiny HTTP API (this repo's `core/`).
   You drop cards; agents claim and complete them **in parallel**; every
   card leaves a receipt (summary + artifacts).
2. **One shared-memory protocol** — a two-trigger discipline (read once
   before a task, write one structured page after) that works with any
   memory backend: an MCP memory server, a vector store, or plain
   markdown files.
3. **One daily digest** — a scheduled recipe/ cron job that folds board
   deltas, chat activity, CI runs, and costs into a single morning report.

```
          you (the owner)
             |  drop cards / read receipts / approve gates
             v
     +---------------+    claim / complete       +----------------+
     |  board server |<------ board.py CLI ------|  agent lanes   |
     | SQLite + HTTP |                           | (goose, ...)   |
     +-------+-------+                           +--------+-------+
             |  GET /board.json                          | read/write
             v                                           v
       dashboard / digest               shared memory (pluggable backend)
             ^
             |  optional: dispatch.sh hands backlog cards to idle lanes
             +-------------------- via your transport (chat mention, ...)
```

## What is in the kit

| Path | What it is |
|---|---|
| `core/board_server.py` | Task board: SQLite (WAL) + HTTP API, stdlib only, single-writer, token-auth'd |
| `core/board.py` | CLI agents (and you) use to create/claim/complete/fail/block cards |
| `core/dispatch.sh` | Optional loop that hands backlog cards to idle agents via **notify hooks** |
| `templates/` | Agent manifest, persona memory-protocol snippet, team instructions, digest recipe |
| `docs/` | Architecture, quickstart, per-project configuration, security, transport adapters |

## Quickstart (5 minutes, no infrastructure)

```bash
git clone https://github.com/yitzhakbg/agentos-kit && cd agentos-kit/core

# 1. start the board (token protects POSTs; keep it localhost or VPN-only)
export AGENTOS_BOARD_TOKEN="$(openssl rand -hex 16)"
python3 board_server.py &

# 2. drop a card
python3 board.py create --title "Draft the Q3 report" --role writer --priority 2

# 3. an agent claims it (inside its session / lane environment)
AGENTOS_BOARD_TOKEN="$AGENTOS_BOARD_TOKEN" AGENTOS_AGENT_NAME=writer \
  python3 board.py claim B-0001

# 4. ...and completes it with a receipt
python3 board.py complete B-0001 --summary "Drafted; 3 sections pending review"

# 5. look at the board
curl -s localhost:8791/board.json | python3 -m json.tool
```

Wire it into goose by adding one paragraph to each agent's persona/system
prompt (see `templates/persona-protocol.md`) and pointing your scheduler at
`templates/digest-recipe.yaml`.

## Per-project by design

Everything deployment-specific — agent roster, transport (chat mentions,
email, webhooks), memory backend, digest outputs — lives in **your project
directory** (`agents.json` + environment), never in the core. One kit on a
machine can serve many projects; each project gets its own board database
and manifest. See `docs/per-project-config.md`.

## What this deliberately does NOT do

- **No automated approval.** The board assigns work; it never merges, pushes,
  publishes, or releases on its own. Keep irreversible actions behind human gates.
- **No secrets in memory.** The memory protocol forbids storing credentials.
- **No external posting.** Nothing here posts to public platforms unprompted.
- **No lock-in.** Transport, memory, and dashboards are pluggable; SQLite and
  stdlib Python are the only hard dependencies.

## Provenance & status

The pattern was extracted from a production deployment: a 7-agent goose team
(occupying distinct chat channels, launchd-managed lanes with a self-healing
watchdog) running a real product's engineering, docs, and marketing workloads.
The board server + CLI there has served live agent traffic since 2026-10-16.
The kit you see here is the **project-agnostic rewrite** of that system;
the full spec/case study lives in `examples/`.

## Docs

- `docs/architecture.md` — components, data flow, the guarantees
- `docs/quickstart.md` — the detailed walk-through (goose + generic agents)
- `docs/per-project-config.md` — multi-project layout
- `docs/memory-protocol.md` — the two-trigger discipline and backends
- `docs/digest.md` — the daily report recipe
- `docs/security.md` — tokens, binding, arming discipline, owner gates
- `docs/buzz-adapter.md` — the relay/mention transport used in production

## License

MIT — see [LICENSE](LICENSE).