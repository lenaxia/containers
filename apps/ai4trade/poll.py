#!/usr/bin/env python3
"""AI-Trader heartbeat/context poller.
Prints a JSON summary and writes it to /workspace/ai4trade/last_poll.json.
Used by the scheduled participation routine. Read-only except last_poll.json.
"""
import json
import os
import datetime
import urllib.request
import urllib.error

WS = "/workspace/ai4trade"
CREDS_PATHS = [WS + "/credentials.json", os.path.expanduser("~/.config/ai4trade/credentials.json")]


def load_creds():
    for p in CREDS_PATHS:
        try:
            with open(p) as f:
                return json.load(f)
        except Exception:
            continue
    return None


def api(creds, method, path, body=None):
    url = creds.get("base_url", "https://ai4trade.ai/api").rstrip("/") + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + creds["token"])
    req.add_header("X-Claw-Token", creds["token"])
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode() or "{}"
            try:
                return json.loads(raw)
            except Exception:
                return {"_raw": raw[:400]}
    except urllib.error.HTTPError as e:
        return {"_error": "HTTP %s %s" % (e.code, e.read().decode()[:200])}
    except Exception as e:
        return {"_error": str(e)[:200]}


def main():
    creds = load_creds()
    if not creds or not creds.get("token"):
        summary = {"ok": False, "needs_action": False, "error": "credentials not found"}
        print(json.dumps(summary))
        return

    state = {}
    try:
        with open(WS + "/state.json") as f:
            state = json.load(f)
    except Exception:
        state = {}

    msgs, tasks, hb_err = [], [], None
    for _ in range(3):
        hb = api(creds, "POST", "/claw/agents/heartbeat",
                 {"agent_id": creds.get("agent_id"), "status": "alive"})
        if "_error" in hb:
            hb_err = hb["_error"]
            break
        msgs += hb.get("messages") or []
        tasks += hb.get("tasks") or []
        if not (hb.get("has_more_messages") or hb.get("has_more_tasks")):
            break

    me = api(creds, "GET", "/claw/agents/me")
    feed = api(creds, "GET", "/signals/feed?limit=15&sort=active")

    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    replied = set(state.get("replied_signal_ids", []))
    pending = []
    for m in msgs:
        d = m.get("data") or {}
        sid = d.get("signal_id")
        if m.get("type") in ("discussion_reply", "strategy_reply", "new_reply") and sid and sid not in replied:
            pending.append({
                "message_type": m.get("type"),
                "signal_id": sid,
                "reply_author": d.get("reply_author_name") or d.get("reply_author_id"),
                "title": d.get("title"),
                "content_preview": (m.get("content") or "")[:250],
            })

    summary = {
        "ok": True,
        "now_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "needs_action": bool(pending or tasks),
        "heartbeat_error": hb_err,
        "new_messages": [
            {"id": m.get("id"), "type": m.get("type"),
             "content": (m.get("content") or "")[:300], "data": m.get("data")}
            for m in msgs
        ],
        "pending_replies_needed": pending,
        "tasks": [
            {"id": t.get("id"), "type": t.get("type"), "input_data": t.get("input_data")}
            for t in tasks
        ],
        "me": ({"points": me.get("points"), "cash": me.get("cash"),
                "reputation": me.get("reputation_score")}
               if "_error" not in me else {"error": me["_error"]}),
        "feed_top": (
            [{"id": s.get("id"), "agent_id": s.get("agent_id"), "agent": s.get("agent_name"),
              "type": s.get("type"), "symbol": s.get("symbol"), "side": s.get("side"),
              "text": (s.get("title") or s.get("content") or "")[:160],
              "reply_count": s.get("reply_count")}
             for s in (feed.get("signals") or [])[:12] if isinstance(s, dict)]
            if isinstance(feed, dict) else []
        ),
        "state": {
            "last_post_date": state.get("last_post_date"),
            "joined_challenge": state.get("joined_challenge", False),
            "followed_ids": state.get("followed_ids", []),
        },
        "posted_today": state.get("last_post_date") == today,
    }

    with open(WS + "/last_poll.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
