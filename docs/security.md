# Security & discipline

The kit implements an opinionated safety posture refined in production. None
of it is fancy; all of it matters.

## Transport security

- The server binds **127.0.0.1** by default. Open it to a network only over a
  VPN mesh (Tailscale/WireGuard) and **only with a token set**
  (`AGENTOS_BOARD_TOKEN`; POSTs must carry `X-Board-Token`).
- The token is a shared secret, appropriate for a single operator / small
  trusted team. It is not multi-tenant auth; do not expose the board to
  parties you wouldn't let create cards.

## Arming discipline (the most important pattern here)

Anything that reaches out and touches agents — dispatch, notifications,
scheduled jobs — ships **DRY by default** and flips to live only after a
human has watched it behave:

1. Run in dry mode (`AGENTOS_DISPATCH_ARMED=0`, the default) and review its
   decisions for at least a couple of cycles.
2. Arm (`=1`) only by explicit owner decision, recorded somewhere durable.
3. Keep re-dispatch throttled (default: 20 min per card) so a stuck board or
   a wedged lane cannot spam agents.

## Owner gates

The board **assigns work; it never approves it.** No merge, push, release,
or external post should be triggered by a card transition. Encode this in the
team instructions ("Approval gates are human gates") and in the digest's
report-not-act contract. Automation should make the owner's decisions
faster — not make decisions.

## Secrets

- Never in shared memory (the protocol enforces it).
- Never in board card bodies — cards may be read by any lane; cards describe
  work, not credentials. Reference a secret manager handle if needed.
- Transport hooks: keys come from the environment of the hook script, never
  as literal text in `agents.json` committed anywhere shared.

## Block surfacing (tiered notifications)

`block` fires the optional `AGENTOS_BLOCK_NOTIFY_CMD` hook. Recommended
tiering: an in-channel note **always**; a live owner ping **only** for
priority-1 cards; everything else surfaces in the daily digest. Urgent
escalation is never silenced; non-urgent blocks never page the owner.

## Retention

Board rows are kept forever (SQLite, a few hundred bytes per card — years of
history is noise-free and queryable); views are capped (`?done_days=N|all`)
so dashboards stay clean without deleting history. Receipts + memory notes +
digests together form the audit trail; the board is execution state, not the
archive.