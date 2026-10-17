#!/usr/bin/env python3
"""agentos-kit board CLI — thin stdlib HTTP client for the board server.

Configuration (env):
  AGENTOS_BOARD_URL    base URL of the board server (default http://127.0.0.1:8791)
  AGENTOS_BOARD_TOKEN  shared token, sent as X-Board-Token on POSTs
  AGENTOS_AGENT_NAME   who is calling (set this in each agent's launch environment)

Commands:
  create    --title T --role R [--body B] [--priority N] [--task-ref T-NNN] [--source S]
  list      [--status backlog|claimed|done|failed|blocked] [--all-done]
  show      CARD_ID
  claim     CARD_ID
  complete  CARD_ID --summary "..." [--artifact PATH]...
  fail      CARD_ID --reason "..."
  block     CARD_ID --reason "..."    (fires the optional notify hook, see below)
  unblock   CARD_ID

Optional "tiered block surfacing" hook:
  AGENTOS_BLOCK_NOTIFY_CMD is a shell COMMAND TEMPLATE evaluated on `block`
  with {card_id}, {reason}, {priority}, {agent} placeholders — e.g. a script
  that posts a note to your team chat, and additionally pings the owner when
  the card is priority 1. Unset = no hook (the card is still marked blocked).
  See docs/buzz-adapter.md for the relay/mention pattern used in production.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("AGENTOS_BOARD_URL", "http://127.0.0.1:8791")
TOKEN = os.environ.get("AGENTOS_BOARD_TOKEN", "")
AGENT = os.environ.get("AGENTOS_AGENT_NAME", "")


def _request(method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if TOKEN and method == "POST":
        req.add_header("X-Board-Token", TOKEN)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {"ok": False, "error": f"HTTP {e.code}"}
    except urllib.error.URLError as e:
        return 0, {"ok": False, "error": f"cannot reach {BASE}: {e.reason}"}


def _die(msg: str) -> None:
    print(f"board: {msg}", file=sys.stderr)
    sys.exit(1)


def _print_card(card: dict) -> None:
    who = card.get("claimed_by") or "-"
    extra = ""
    if card.get("result_summary"):
        extra = f" | {card['result_summary'][:80]}"
    elif card.get("failed_reason"):
        extra = f" | ! {card['failed_reason'][:80]}"
    print(f"{card['id']} [{card['status']:>7}] p{card.get('priority', 5)} {card.get('role', 'any'):<12} "
          f"{who:<10} {card['title']}{extra}")


def cmd_create(a) -> None:
    code, resp = _request("POST", "/api/board/card", {
        "title": a.title, "role": a.role, "body": a.body, "priority": a.priority,
        "task_ref": a.task_ref, "source": a.source,
    })
    if code >= 400:
        _die(resp.get("error", f"HTTP {code}"))
    print(f"created {resp['card']['id']}")


def cmd_list(a) -> None:
    code, resp = _request("GET", "/board.json?done_days=all" if a.all_done else "/board.json")
    if code != 200:
        _die(resp.get("error", f"HTTP {code}"))
    statuses = [a.status] if a.status else ["backlog", "claimed", "blocked", "failed"]
    if a.status == "done" or a.all_done:
        statuses = ["done"]
    for s in statuses:
        cards = resp.get(s) or []
        if cards:
            print(f"--- {s} ({len(cards)}) ---")
            for card in cards:
                _print_card(card)


def _need_card_id(a) -> str:
    if not a.card_id:
        _die("card id is required")
    return a.card_id


def cmd_show(a) -> None:
    code, resp = _request("GET", "/board.json?done_days=all")
    if code != 200:
        _die(resp.get("error", f"HTTP {code}"))
    for s in ("backlog", "claimed", "done", "failed", "blocked"):
        for card in resp.get(s) or []:
            if card["id"] == _need_card_id(a):
                print(json.dumps(card, indent=2))
                return
    _die(f"card {a.card_id} not found")


def cmd_claim(a) -> None:
    if not AGENT:
        _die("AGENTOS_AGENT_NAME is not set — who is claiming?")
    code, resp = _request("POST", "/api/board/claim", {"card_id": a.card_id, "agent": AGENT})
    if code >= 400:
        _die(resp.get("error", f"HTTP {code}"))
    print(f"claimed {a.card_id} as {AGENT}")


def cmd_complete(a) -> None:
    code, resp = _request("POST", "/api/board/complete",
                          {"card_id": a.card_id, "summary": a.summary, "artifacts": a.artifact})
    if code >= 400:
        _die(resp.get("error", f"HTTP {code}"))
    print(f"done {a.card_id} — receipt recorded")


def cmd_fail(a) -> None:
    code, resp = _request("POST", "/api/board/fail", {"card_id": a.card_id, "reason": a.reason})
    if code >= 400:
        _die(resp.get("error", f"HTTP {code}"))
    print(f"failed {a.card_id}")


def cmd_block(a) -> None:
    code, resp = _request("POST", "/api/board/block", {"card_id": a.card_id, "reason": a.reason})
    if code >= 400:
        _die(resp.get("error", f"HTTP {code}"))
    print(f"blocked {a.card_id}")
    hook = os.environ.get("AGENTOS_BLOCK_NOTIFY_CMD")
    if hook:
        card = resp.get("card", {})
        cmd = (hook.replace("{card_id}", a.card_id)
                   .replace("{reason}", a.reason)
                   .replace("{priority}", str(card.get("priority", 5)))
                   .replace("{agent}", AGENT or "unknown"))
        try:
            subprocess.run(cmd, shell=True, check=False)  # transport-specific, user-provided
        except Exception as e:
            print(f"board: notify hook failed: {e}", file=sys.stderr)


def cmd_unblock(a) -> None:
    code, resp = _request("POST", "/api/board/unblock", {"card_id": a.card_id})
    if code >= 400:
        _die(resp.get("error", f"HTTP {code}"))
    print(f"unblocked {a.card_id} (back to backlog)")


def main() -> None:
    ap = argparse.ArgumentParser(prog="board", description="agentos-kit task board CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("create"); p.add_argument("--title", required=True)
    p.add_argument("--role", default="any"); p.add_argument("--body", default="")
    p.add_argument("--priority", type=int, default=5); p.add_argument("--task-ref", default="")
    p.add_argument("--source", default="manual"); p.set_defaults(fn=cmd_create)

    p = sub.add_parser("list"); p.add_argument("--status", choices=["backlog", "claimed", "done", "failed", "blocked"])
    p.add_argument("--all-done", action="store_true"); p.set_defaults(fn=cmd_list)

    p = sub.add_parser("show"); p.add_argument("card_id"); p.set_defaults(fn=cmd_show)

    p = sub.add_parser("claim"); p.add_argument("card_id"); p.set_defaults(fn=cmd_claim)

    p = sub.add_parser("complete"); p.add_argument("card_id"); p.add_argument("--summary", required=True)
    p.add_argument("--artifact", action="append", default=[]); p.set_defaults(fn=cmd_complete)

    p = sub.add_parser("fail"); p.add_argument("card_id"); p.add_argument("--reason", required=True)
    p.set_defaults(fn=cmd_fail)

    p = sub.add_parser("block"); p.add_argument("card_id"); p.add_argument("--reason", required=True)
    p.set_defaults(fn=cmd_block)

    p = sub.add_parser("unblock"); p.add_argument("card_id"); p.set_defaults(fn=cmd_unblock)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()