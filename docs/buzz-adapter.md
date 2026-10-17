# Buzz adapter (relay + mentions transport)

This documents the transport used by the reference production deployment: a
[goose](https://github.com/aaif-goose/goose) multi-agent team running on
Buzz (self-hosted Nostr-style relay + chat channels). The pattern generalizes
to any chat system with mentions.

## Topology

- Each agent = one lane: a long-lived adapter process (relay client) that
  spawns a goose session per mention, subscribed to its channels.
- Agents share one owner identity (the human) and distinct Nostr-style keys.
- The board's `role` field matches agent names; mentions coordinate the rest.

## Mapping to the kit

| Kit concept | Buzz realization |
|---|---|
| `notify` hook | `buzz messages send --channel <agent's channel> --mention <agent pubkey> --content "📋 [Board B-####] <title> — claim with: board.py claim B-####"` |
| `alive` probe | lane-liveness check: adapter + goose-child process tree + recent-activity heuristic |
| Dispatch timer | a watchdog script on a 10-min tick (service-managed, always-on) |
| Owner gates | owner pubkey in the allowlist; irreversible actions still need the human |
| Digest post | one post to the main channel from the owner key; `buzz messages get --since <cursor>` as the digest's chat source |

## Lessons that shaped the kit

1. **Mentions delivered while a lane is down are lost** unless the adapter
   fetches unread mentions on reconnect. Dispatch-after-recovery must be a
   fresh live ping (that's why the dispatcher re-throttles rather than
   fire-and-forgets).
2. **Adapter logs don't show turn activity.** Liveness = child-process CPU
   sampling + outbox freshness, not "process exists".
3. **Identity clarity beats simplicity.** Automated dispatch (board) and
   human messages should be distinguishable in history — hence the
   `📋 [Board B-####]` prefix convention and sending from a *non-owner*
   identity where possible.
4. **Rate-limit gates are real.** Relays throttle bursts; one dispatch per
   agent per pass keeps composite automations polite.

## Tiered block surfacing (production pattern)

When an agent calls `board.py block`, the CLI hook (ambient agent key) posts
the block note to the card's role channel; a live owner ping goes out only
for priority-1 cards; everything else lands in the morning digest. Configure
via `AGENTOS_BLOCK_NOTIFY_CMD` (see `core/board.py` docstring).

## What to keep out of any public mirror

Keys, pubkeys, channel UUIDs, workspace paths, project names. The adapter
pattern is generic; instantiate it privately per deployment.