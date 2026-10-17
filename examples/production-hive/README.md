# Example: the reference production deployment

This kit is the project-agnostic rewrite of a system that has run in
production since October 2026, coordinating a **7-agent team** working on a
real product (a spaced-repetition platform for schools). The deployment
itself is private; this page describes its *shape* so you can compare it to
yours — with all identifying specifics (keys, IDs, paths, names) removed.

## Shape

- **7 agents**, each with a persona file, one roster-managed channel set,
  and a distinct cryptographic identity: an archivist, a strategist, an
  engineer, a marketer, a media-producer, a task-master, a scribe.
- **Transport:** self-hosted relay + channels (see `docs/buzz-adapter.md`).
  Mentions start agent sessions; the board dispatch adds the `📋 [Board
  B-####]` prefix convention so automated assignments are greppable in
  history and visibly distinct from human messages.
- **Board:** the SQLite server from `core/` (as a section of that
  deployment's dashboard service), token-auth'd, localhost-bound.
- **Dispatch:** watchdog tick every 10 min, DRY by default, one dispatch
  per agent per pass, re-dispatch throttled.
- **Memory:** a Postgres+pgvector brain (mountable over MCP on every lane),
  namespaced per project, governed by the two-trigger protocol.
- **Digest:** daily morning report (board deltas + channel activity + task
  ledger + CI runs + LLM spend + upstream-drift line).
- **Supervision:** a service-managed dashboard app polling the board and
  lane liveness; a scheduled "rollout watch" that monitors the system's own
  upgrades and recommends (never executes) repairs.

## Numbers from the first month

- Two-agent parallel card completion reached within a day of arming the
  board (the success criterion in that deployment's spec).
- Board endpoint live-serving agent traffic from day one; zero lost-update
  incidents (single-writer design).
- The most expensive lesson: schedulers that depend on a desktop daemon
  silently miss morning runs — hence the always-on watchdog pattern.

## What to copy vs. what to keep private

- Copy: the primitive shapes, the protocols, the arming discipline, the
  digest contract, the receipt culture.
- Keep private per deployment: identities, endpoints, tokens, customer data.