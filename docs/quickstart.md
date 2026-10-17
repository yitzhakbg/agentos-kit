# Quickstart

## 0. Requirements

- Python 3.10+ (stdlib only — no pip installs)
- One or more agents whose sessions can run a shell command (goose, Claude
  Code, cron scripts, CI jobs — anything with a shell)

## 1. Layout

Pick a project directory. The kit is per-project:

```bash
mkdir -p ~/agentos/myproject && cd ~/agentos/myproject
```

## 2. Start the board

```bash
export AGENTOS_BOARD_TOKEN="$(openssl rand -hex 16)"   # save this somewhere safe
export AGENTOS_BOARD_DB="$PWD/.agentos/board.sqlite3"
nohup python3 /path/to/agentos-kit/core/board_server.py > .agentos/server.log 2>&1 &
curl -s localhost:8791/healthz   # -> {"ok": true}
```

For a persistent deployment, wrap steps in a service unit (systemd user
service, launchd agent) — see `per-project-config.md`.

## 3. Create the agent manifest

```bash
cat > agents.json <<'EOF'
{ "agents": [
    { "name": "writer",     "notify": "bash ~/.agentos/notify-chat.sh {agent} {card_id} {title}" },
    { "name": "reviewer",   "notify": "bash ~/.agentos/notify-chat.sh {agent} {card_id} {title}" }
] }
EOF
```

The `notify` script is your transport — for a chat-based system it posts a
mention to the agent. See `buzz-adapter.md` for the production example.

## 4. Drop cards (the owner)

```bash
export AGENTOS_BOARD_TOKEN=... AGENTOS_BOARD_URL=http://127.0.0.1:8791
python3 /path/to/agentos-kit/core/board.py create \
  --title "Review the API docs for tone" --role reviewer --priority 3
```

## 5. Give each agent the protocol

Add `templates/persona-protocol.md` (adapted to your memory backend) to every
agent's persona/system prompt, plus this board block:

```text
## Task board
Cards arrive as mentions. To work a card:
  board.py claim <CARD_ID>
  ...do the work...
  board.py complete <CARD_ID> --summary "what happened" --artifact <path>
If stuck: board.py block <CARD_ID> --reason "..." and move on.
Never run irreversible actions without owner sign-off.
```

Export in the agent's launch environment: `AGENTOS_BOARD_URL`,
`AGENTOS_BOARD_TOKEN`, `AGENTOS_AGENT_NAME=<agent name from agents.json>`.

## 6. Optional: automatic dispatch

Run the dispatcher on a timer (cron every 10 min is a good start):

```bash
*/10 * * * * AGENTOS_HOME=$HOME/agentos/myproject /path/to/agentos-kit/core/dispatch.sh
```

It starts in **dry mode** — watch its output for a day, then arm with
`AGENTOS_DISPATCH_ARMED=1` in the cron env. See `security.md` for the
arming discipline.

## 7. Optional: the morning digest

Copy `templates/digest-recipe.yaml` into your goose recipes (or port the
prompt to your scheduler), set the env vars, register it at your preferred
hour (`0 7 * * *` in the example). Verify with a manual first run.