#!/usr/bin/env python3
"""agentos-kit board server — a small project-agnostic task board for agent teams.

One SQLite database + one tiny HTTP API = the "single task board" primitive of
the AgentOS pattern (see README.md): you drop cards, agents claim and complete
them in parallel, and every card leaves a receipt (summary + artifacts).

Design rules (deliberate):
  * stdlib only — nothing to install, nothing to audit
  * single writer: EVERY write goes through this process (threading.Lock +
    SQLite WAL), so any number of agents can claim concurrently with no races
  * claims are atomic and guarded: only a `backlog` card can be claimed
  * POSTs require a shared token when one is configured (`X-Board-Token`);
    the server binds 127.0.0.1 by default — expose it over a VPN (Tailscale
    etc.) only WITH a token set
  * the board assigns work; it never approves it. Merges, pushes, releases,
    and anything irreversible stay behind your own human gates.

Endpoints
  GET  /healthz                       -> {"ok": true}
  GET  /board.json?done_days=N|all    -> board state; `done` capped to N days (default 7)
  POST /api/board/card                {title, role, body?, priority?, task_ref?, source?}
  POST /api/board/claim               {card_id, agent}
  POST /api/board/complete            {card_id, summary, artifacts?}
  POST /api/board/fail                {card_id, reason}
  POST /api/board/block               {card_id, reason}   -> status=blocked
  POST /api/board/unblock             {card_id}           -> status=backlog

Configuration (env)
  AGENTOS_BOARD_DB     path to the SQLite file   (default: ./.agentos/board.sqlite3)
  AGENTOS_PORT         listen port               (default: 8791)
  AGENTOS_BIND         bind address              (default: 127.0.0.1 — don't open up casually)
  AGENTOS_BOARD_TOKEN  shared token for POSTs    (default: unset = tokenless local use)
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

DB_PATH = os.environ.get("AGENTOS_BOARD_DB") or os.path.join(os.getcwd(), ".agentos", "board.sqlite3")
PORT = int(os.environ.get("AGENTOS_PORT", "8791"))
BIND = os.environ.get("AGENTOS_BIND", "127.0.0.1")
TOKEN = os.environ.get("AGENTOS_BOARD_TOKEN", "")

LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
  id             TEXT PRIMARY KEY,
  title          TEXT NOT NULL,
  body           TEXT,
  role           TEXT DEFAULT 'any',
  priority       INTEGER DEFAULT 5,
  status         TEXT DEFAULT 'backlog',  -- backlog|claimed|done|failed|blocked
  claimed_by     TEXT, claimed_at TEXT,
  done_at        TEXT, failed_reason TEXT,
  result_summary TEXT,
  artifacts      TEXT,                    -- JSON array of strings
  source         TEXT, task_ref TEXT, created_at TEXT
);
"""

STATUSES = ("backlog", "claimed", "done", "failed", "blocked")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    with LOCK:
        c = db()
        try:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute(SCHEMA)
            c.commit()
        finally:
            c.close()


def card_public(row: sqlite3.Row) -> dict:
    d = dict(row)
    if d.get("artifacts"):
        try:
            d["artifacts"] = json.loads(d["artifacts"])
        except Exception:
            pass
    return d


def write_txn(fn):
    """Serialize every write through one lock + one connection; commit or roll back."""
    with LOCK:
        c = db()
        try:
            result = fn(c)
            c.commit()
            return result
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()


def next_id(c: sqlite3.Connection) -> str:
    row = c.execute("SELECT id FROM cards ORDER BY CAST(substr(id, 3) AS INTEGER) DESC LIMIT 1").fetchone()
    n = (int(row[0][2:]) + 1) if row else 1
    return f"B-{n:04d}"


def transition(card_id: str, expect: str | None, sets: dict) -> tuple[int, dict]:
    """Guarded state transition. 409 when the card is missing or in the wrong state."""
    def txn(c: sqlite3.Connection):
        sets_sql = ", ".join(f"{k}=?" for k in sets)
        params = list(sets.values())
        where, wparams = "id=?", [card_id]
        if expect:
            where += " AND status=?"
            wparams.append(expect)
        cur = c.execute(f"UPDATE cards SET {sets_sql} WHERE {where}", (*params, *wparams))
        if cur.rowcount == 0:
            return 409, {"ok": False, "error": f"card {card_id} not found or not in '{expect}' state"}
        row = c.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
        return 200, {"ok": True, "card": card_public(row)}
    return write_txn(txn)


# ---------------------------------------------------------------- handlers

def api_card(p: dict) -> tuple[int, dict]:
    title = (p.get("title") or "").strip()
    if not title:
        return 400, {"ok": False, "error": "title is required"}
    artifacts = p.get("artifacts") or []

    def txn(c: sqlite3.Connection):
        cid = next_id(c)
        c.execute(
            "INSERT INTO cards (id, title, body, role, priority, source, task_ref, created_at, artifacts)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (cid, title, p.get("body"), p.get("role") or "any", int(p.get("priority") or 5),
             p.get("source") or "manual", p.get("task_ref"), now_iso(),
             json.dumps(artifacts) if artifacts else None))
        row = c.execute("SELECT * FROM cards WHERE id=?", (cid,)).fetchone()
        return 201, {"ok": True, "card": card_public(row)}
    return write_txn(txn)


def api_claim(p: dict) -> tuple[int, dict]:
    agent = p.get("agent") or ""
    if not agent:
        return 400, {"ok": False, "error": "agent is required to claim"}
    t = now_iso()
    return transition(p.get("card_id"), "backlog",
                      {"status": "claimed", "claimed_by": agent, "claimed_at": t})


def api_complete(p: dict) -> tuple[int, dict]:
    summary = (p.get("summary") or "").strip()
    if not summary:
        return 400, {"ok": False, "error": "summary (the receipt) is required"}
    artifacts = p.get("artifacts") or []
    t = now_iso()
    ok, resp = transition(p.get("card_id"), "claimed",
                          {"status": "done", "done_at": t, "result_summary": summary,
                           "artifacts": json.dumps(artifacts) if artifacts else None})
    return ok, resp


def api_fail(p: dict) -> tuple[int, dict]:
    reason = (p.get("reason") or "").strip()
    if not reason:
        return 400, {"ok": False, "error": "reason is required"}
    return transition(p.get("card_id"), None,
                      {"status": "failed", "failed_reason": reason, "done_at": now_iso()})


def api_block(p: dict) -> tuple[int, dict]:
    reason = (p.get("reason") or "").strip()
    if not reason:
        return 400, {"ok": False, "error": "reason is required"}
    # May be blocked from backlog OR claimed (agent got stuck mid-task).
    for expect in ("claimed", "backlog"):
        ok, resp = transition(p.get("card_id"), expect, {"status": "blocked", "failed_reason": reason})
        if ok == 200:
            return ok, resp
    return 409, {"ok": False, "error": "card not in claimable state"}


def api_unblock(p: dict) -> tuple[int, dict]:
    return transition(p.get("card_id"), "blocked", {"status": "backlog", "failed_reason": None})


def board_state(done_days) -> dict:
    cutoff = None
    if done_days != "all":
        cutoff = (datetime.now(timezone.utc) - timedelta(days=int(done_days))).isoformat(timespec="seconds")
    c = db()
    try:
        rows = [dict(r) for r in c.execute("SELECT * FROM cards")]
    finally:
        c.close()
    by_status: dict[str, list] = {s: [] for s in STATUSES}
    for r in rows:
        if r["status"] == "done" and cutoff and (r.get("done_at") or "") <= cutoff:
            continue  # keep the done view short; rows stay in the DB (keep-forever retention)
        if r["status"] == "done":
            key = r.get("done_at") or ""
        else:
            key = r.get("claimed_at") or r.get("created_at") or ""
        r["artifacts"] = json.loads(r["artifacts"]) if r.get("artifacts") else []
        by_status[r["status"]].append(r)
    for s in STATUSES:
        by_status[s].sort(key=lambda c2: key_of(c2, s), reverse=True)
    return {"generated_at": now_iso(), "done_days": done_days if done_days != "all" else "all", **by_status}


def key_of(card: dict, status: str) -> str:
    return card.get("done_at") or card.get("claimed_at") or card.get("created_at") or ""


# ---------------------------------------------------------------- HTTP

ROUTES = {
    "/api/board/card": api_card,
    "/api/board/claim": api_claim,
    "/api/board/complete": api_complete,
    "/api/board/fail": api_fail,
    "/api/board/block": api_block,
    "/api/board/unblock": api_unblock,
}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")  # board UIs are local dashboards
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        u = urlparse(self.path)
        if u.path == "/healthz":
            return self._send(200, {"ok": True})
        if u.path == "/board.json":
            dd = (parse_qs(u.query).get("done_days") or ["7"])[0]
            try:
                state = "all" if dd == "all" else max(0, int(dd))
            except ValueError:
                return self._send(400, {"ok": False, "error": "done_days must be an integer or 'all'"})
            return self._send(200, board_state(state))
        self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        if TOKEN and self.headers.get("X-Board-Token") != TOKEN:
            return self._send(401, {"ok": False, "error": "missing or wrong X-Board-Token"})
        u = urlparse(self.path)
        fn = ROUTES.get(u.path)
        if not fn:
            return self._send(404, {"ok": False, "error": "unknown endpoint"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._send(400, {"ok": False, "error": "invalid JSON body"})
        code, resp = fn(payload)
        return self._send(code, resp)

    def log_message(self, fmt: str, *args) -> None:  # keep logs quiet under launchd/systemd
        pass


def main() -> None:
    init_db()
    print(f"agentos board server: db={DB_PATH} bind={BIND}:{PORT} token={'set' if TOKEN else 'UNSET'}", flush=True)
    ThreadingHTTPServer((BIND, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()