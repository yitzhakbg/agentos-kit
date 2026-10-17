# agentos-kit

**Run your AI agents as one operating system, not a pile of tabs.**

`agentos-kit` is a small, project-agnostic kit that implements the three
primitives every "agent OS" needs, distilled from running a production
7-agent goose team:

1. **One task board** — SQLite + a tiny HTTP API (this repo's `core/`).
   You drop cards; agents claim and complete them **in parallel**; every
   card leaves a receipt (summary + artifacts).
2. **One shared-memory protocol** — a two-trigger discipline (read once
   before a task, write one structured page after) that works with any
   memory backend: an MCP memory server, a vector store, or plain
   markdown files.
3. **One daily digest** — a scheduled recipe that folds board deltas,
   chat activity, CI runs, and costs into a single morning report.

```
                you (the owner)
                   |  drop cards / read receipts / approve gates
                   v
        +-----------------+     claim / complete      +------------------+
        |   board server  |<------ board.py CLI ------|   goose agents   |
        |  SQLite + HTTP  |                           |  (persona +      |
        +--------+--------+                           |   shell tool)    |
                 |  GET /board.json                   +--------+---------+
                 v                                             | read/write
        dashboard / digest                          shared memory (pluggable:
             (scheduled goose recipe)                MCP server / store)
                 ^
                 |  optional dispatch.sh: backlog --> idle lanes
                 |        via notify hooks (Buzz mentions / webhooks / ...)
                 v
        transport-free core — buzz is one adapter, plug your own
```

## goose and Buzz — the two building blocks

**[goose](https://github.com/aaif-goose/goose)** is the open-source AI agent
that does the work. agentos-kit does **not** require any special goose
extension or plugin: a goose session talks to the board through its ordinary
shell tool (running `board.py` like any other command), reads its
instructions from a persona/system prompt that carries two small protocol
blocks (see `templates/`), and inherits its identity from three environment
variables. That's the entire integration surface.

- **Persona/system prompt** ← `templates/persona-protocol.md` (shared
  memory) + the task-board block (claim / complete / block discipline)
- **Environment** ← `AGENTOS_BOARD_URL`, `AGENTOS_BOARD_TOKEN`,
  `AGENTOS_AGENT_NAME` set in whatever launches the goose session
  (Desktop persona, `goose run`, a recipe, or a lane manager)
- **Scheduling** ← `templates/digest-recipe.yaml` registered with the goose
  scheduler: `goose schedule add --schedule-id morning-digest --cron "0 7 * * *"
  --recipe-source templates/digest-recipe.yaml`
- **Subagents/delegates** can claim cards too — just give them a different
  `AGENTOS_AGENT_NAME`

**[Buzz](https://github.com/block/buzz)** (optional) is a self-hosted
relay + chat-channel system that turns several goose agents into an
addressable team: each agent gets a cryptographic identity and lives in
channels; `@mentions` are how work reaches a lane. agentos-kit treats Buzz
as one **transport adapter** — the production deployment uses Buzz mentions
as the notify hook, and gets two extra capabilities:

- **Lane liveness** — the dispatcher can skip agents whose buzz lane is down
  (an `alive` probe in `agents.json`)
- **Tiered block notifications** — when an agent is stuck, `board.py block`
  posts a note to the agent's channel with its ambient key, and pings the
  owner live only for priority-1 cards (see `docs/buzz-adapter.md`)

**Not using Buzz?** Nothing in the core cares. The notify hook can be a
webhook, an email, a job queue — or nothing at all (you and the board are
already enough for a solo setup). The pattern is: transport is pluggable;
the board, the memory protocol, and the digest don't change.

## What is in the kit

| Path | What it is |
|---|---|
| `core/board_server.py` | Task board: SQLite (WAL) + HTTP API, stdlib only, single-writer, token-auth'd |
| `core/board.py` | CLI agents (and you) use to create/claim/complete/fail/block cards |
| `core/dispatch.sh` | Optional loop that hands backlog cards to idle agents via **notify hooks** |
| `templates/` | Agent manifest, persona memory-protocol snippet, team instructions, goose digest recipe |
| `docs/` | Architecture, quickstart, per-project configuration, security, the Buzz adapter |

## Quickstart

### With goose only (5 minutes, no infrastructure)

```bash
git clone https://github.com/yitzhakbg/agentos-kit && cd agentos-kit/core

# 1. start the board (token protects POSTs; keep it localhost or VPN-only)
export AGENTOS_BOARD_TOKEN="$(openssl rand -hex 16)"
python3 board_server.py &

# 2. drop a card
python3 board.py create --title "Draft the Q3 report" --role writer --priority 2

# 3. inside your goose session (or a recipe run), claim and work it
AGENTOS_AGENT_NAME=writer python3 board.py claim B-0001
#    ... goose does the work with its normal tools ...
AGENTOS_AGENT_NAME=writer python3 board.py complete B-0001 \
  --summary "Drafted; 3 sections pending review" --artifact report-draft.md

# 4. look at the board (this is also what the digest and dashboard read)
curl -s localhost:8791/board.json | python3 -m json.tool
```

Then make it durable:
- Add the two protocol blocks from `templates/` to the agent's persona so
  goose claims/completes cards and uses shared memory without being told each time.
- Register the digest with the goose scheduler (command above under
  *goose and Buzz*) or your system scheduler — see the caveat in
  `docs/digest.md` about schedulers vs. always-on timers.

### With goose + Buzz (the multi-agent team)

1. Run your lanes (relay adapter usually launchd/systemd-managed) so each
   goose agent is reachable by mention in its channel.
2. Point each lane at the project board: export the three env vars in the
   lane's launch environment (this is also where the agent's buzz key
   already lives — never print it into cards or memory).
3. Fill `templates/agents.example.json` with your roster and a notify hook
   per agent, e.g.:

   ```bash
   buzz messages send --channel <agent-channel> --mention <agent-key> \
     --content "📋 [Board {card_id}] {title} — claim with: board.py claim {card_id}"
   ```

   The `📋 [Board B-####]` prefix keeps automated assignments visibly
   distinct from human messages in chat history.
4. Add the dispatcher to a 10-minute timer (system timer preferred over the
   goose scheduler for always-on behavior; see docs). It is **DRY by
   default** — watch a few passes, then arm (`docs/security.md`).
5. Add the memory-protocol block to every persona identically.

A complete sanitized walk-through of a 7-agent deployment is in
`examples/production-hive/`.

## Per-project by design

Everything deployment-specific — agent roster, transport, memory backend,
digest outputs — lives in **your project directory** (`agents.json` +
environment), never in the core. One kit on a machine can serve many
projects; each project gets its own board database and manifest. See
`docs/per-project-config.md`.

## What this deliberately does NOT do

- **No automated approval.** The board assigns work; it never merges, pushes,
  publishes, or releases on its own. Keep irreversible actions behind gates
  only you control — a principle, not a feature request.
- **No secrets in memory.** The memory protocol forbids storing credentials.
- **No external posting.** Nothing here posts to public platforms unprompted.
- **No lock-in.** Transport, memory, and dashboards are pluggable; SQLite and
  stdlib Python are the only hard dependencies.

## Provenance & status

The pattern was extracted from a production deployment: a 7-agent goose team
on a Buzz relay (distinct identities, launchd-managed lanes with a
self-healing watchdog), doing real engineering, docs, and marketing work on
a shipped product. The board server + CLI there has served live agent
traffic since 2026-10-16, including the development of this very kit. The kit
is the **project-agnostic rewrite**; the full case study is sanitized under
`examples/`.

## Docs

- `docs/architecture.md` — components, data flow, the guarantees
- `docs/quickstart.md` — detailed walk-through (goose + generic agents)
- `docs/per-project-config.md` — multi-project layout
- `docs/memory-protocol.md` — the two-trigger discipline and backends
- `docs/digest.md` — the daily report recipe (and the scheduler caveat)
- `docs/security.md` — tokens, binding, arming discipline, owner gates
- `docs/buzz-adapter.md` — the relay/mention transport used in production

## License

MIT — see [LICENSE](LICENSE).