# The daily digest

Supervision by exception: the owner reads one page in the morning instead of
watching channels all day. `templates/digest-recipe.yaml` is a goose recipe
template; the same prompt structure ports to any scheduler (cron + a one-shot
`goose` run, CI job, etc.).

## Sources (skip what doesn't apply)

| Source | How |
|---|---|
| Board deltas | `GET /board.json?done_days=all` — done/failed/blocked/created since the digest cursor; flag backlog cards older than a week |
| Team chat | messages since the cursor from your channel(s); report what happened, not everything said |
| Ledger | git log of the project's specs/tasks since the cursor |
| CI | pipeline runs of the last 24h |
| Costs | your spend source (proxy stats, provider dashboard) |
| Upstream drift | for each vendored/tracked tool: `git fetch origin` + behind-by count + last upstream commit date — **the line that stops drift from sneaking up on you**; updates stay owner-gated |

## Output = exactly two writes

1. **Durable copy** filed to shared memory: `<prefix>/digests/YYYY-MM-DD`.
   This is how the digest itself compounds — old digests are searchable.
2. **One short post** (≤ ~12 lines) to the team's main channel: verdict line
   (`ON TRACK` / `NEEDS ATTENTION: item`), done/blocked cards, escalations
   needing the owner, the drift line.

## Cursor

`.agentos/last-digest` (ISO timestamp) defines the window exactly; the digest
run updates it. Without a cursor you get fuzzy "overnight" semantics.

## Scheduling caveat (learned the hard way)

Scheduler-based runs are best-effort — a desktop daemon that isn't up at the
fire time means a silently missed digest. If morning delivery must be
guaranteed, drive the digest from an always-on mechanism (system service /
watchdog tick) that invokes a one-shot agent run, and keep the recipe prompt
as the procedure.

## What the digest must never do

Act. A digest compiles and reports; anything it flags as needing a decision
waits for the owner. If it could auto-fix what it finds, it wouldn't be a
report — it would be a risk.