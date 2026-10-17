#!/usr/bin/env bash
# agentos-kit dispatcher — hand backlog cards to agent lanes via notify hooks.
#
# Reads the board's backlog and, for each card whose role matches an agent in
# agents.json, invokes that agent's `notify` command template. This is the
# single seam between the board and ANY agent infrastructure (chat mentions,
# webhooks, a queue...). Called periodically (cron, a watchdog loop, a
# scheduler) — each invocation is one "dispatch pass".
#
# ARMING DISCIPLINE: DRY by default. AGENTOS_DISPATCH_ARMED=1 flips to live.
# Review a few dry runs before arming. See docs/security.md.
#
# Env:
#   AGENTOS_HOME                 project dir containing agents.json (default: .)
#   AGENTOS_BOARD_URL            board base URL   (default: http://127.0.0.1:8791)
#   AGENTOS_DISPATCH_ARMED       0 = dry-run only (default), 1 = live dispatch
#   AGENTOS_DISPATCH_RETRY_SECS  do not re-dispatch a still-backlog card more
#                                often than this (default: 1200 = two 10-min ticks)
#
# agents.json schema (see templates/agents.example.json):
# {
#   "agents": [
#     {
#       "name":   "engineer",
#       "roles":  ["any", "engineer"],            (optional; defaults to ["any", name])
#       "notify": "/path/to/notify-hook.sh {agent} {card_id} {title} {priority}",
#       "alive":  "optional probe command; agent is skipped unless it exits 0"
#     }
#   ]
# }
#
# State: $AGENTOS_HOME/.agentos/dispatch-state.json
set -euo pipefail

AGENTOS_HOME="${AGENTOS_HOME:-$(pwd)}"
BOARD_URL="${AGENTOS_BOARD_URL:-http://127.0.0.1:8791}"
ARMED="${AGENTOS_DISPATCH_ARMED:-0}"
RETRY_SECS="${AGENTOS_DISPATCH_RETRY_SECS:-1200}"
AGENTS_FILE="$AGENTOS_HOME/agents.json"
STATE_DIR="$AGENTOS_HOME/.agentos"
STATE_FILE="$STATE_DIR/dispatch-state.json"

[ -f "$AGENTS_FILE" ] || { echo "dispatch: no agents.json at $AGENTS_FILE" >&2; exit 1; }
mkdir -p "$STATE_DIR"

export BOARD_URL STATE_FILE ARMED RETRY_SECS

python3 - "$AGENTS_FILE" <<PYEOF
import json, os, subprocess, sys, time, urllib.request

agents_file, = sys.argv[1:2]
board_url = os.environ["BOARD_URL"]
armed = os.environ["ARMED"] == "1"
retry_secs = float(os.environ["RETRY_SECS"])
state_file = os.environ["STATE_FILE"]

try:
    cfg = json.load(open(agents_file))
except Exception as e:
    print(f"dispatch: bad agents.json: {e}", file=sys.stderr); sys.exit(1)

try:
    with urllib.request.urlopen(board_url + "/board.json", timeout=10) as r:
        board = json.load(r)
except Exception as e:
    print(f"dispatch: cannot reach board {board_url}: {e}", file=sys.stderr); sys.exit(2)

try:
    state = json.load(open(state_file))
except Exception:
    state = {}

now = time.time()
dispatched_this_pass = set()
actions = []

for card in board.get("backlog", []):
    cid = card["id"]
    role = card.get("role") or "any"
    st = state.get(cid) or {}
    # re-dispatch throttle
    if st.get("last_ts") and (now - st["last_ts"]) < retry_secs:
        continue
    # pick an eligible agent: role match, probe passes, not already used this pass
    for agent in cfg.get("agents", []):
        name = agent.get("name") or ""
        roles = agent.get("roles") or ["any", name]
        if name in dispatched_this_pass or role not in roles:
            continue
        alive = agent.get("alive")
        if alive:
            probe = subprocess.run(alive, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if probe.returncode != 0:
                continue
        actions.append((agent, card))
        dispatched_this_pass.add(name)
        break

for agent, card in actions:
    cid, title = card["id"], card.get("title") or ""
    tmpl = agent.get("notify") or ""
    cmd = (tmpl.replace("{agent}", agent["name"])
               .replace("{card_id}", cid)
               .replace("{title}", title)
               .replace("{priority}", str(card.get("priority", 5)))
               .replace("{body}", (card.get("body") or "")))
    if armed:
        rc = subprocess.run(cmd, shell=True).returncode
        if rc == 0:
            state[cid] = {"last_ts": now, "agent": agent["name"]}
            print(f"dispatched {cid} -> {agent['name']}")
        else:
            print(f"dispatch: notify hook exited {rc} for {cid} -> {agent['name']}", file=sys.stderr)
    else:
        print(f"[dry] would dispatch {cid} -> {agent['name']}: {title}")

json.dump(state, open(state_file, "w"))
if not actions:
    print("dispatch: nothing to do")
PYEOF