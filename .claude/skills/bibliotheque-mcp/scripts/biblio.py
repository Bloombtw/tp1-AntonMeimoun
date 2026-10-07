#!/usr/bin/env python3
"""Client minimal du serveur MCP `bibliotheque`, qui contourne ses pièges de lecture.

Usage :
  python biblio.py call <outil> '<json args>'   # un appel, réponse JSON brute
  python biblio.py all  <outil> '<json args>'   # toutes les pages d'un outil list_*

Le token est lu dans la variable d'environnement BIBLIO_TOKEN (ou dans ./.env).
Les appels sont espacés et une réponse « dégradée » (quota silencieux) est rejouée
après une pause, au lieu d'être prise pour une vraie réponse vide.
"""
import json
import os
import re
import sys
import time
import urllib.request

URL = os.environ.get("BIBLIO_URL", "https://ai-tools-mcp-biblio-production.up.railway.app/mcp")
MIN_GAP = 1.5      # secondes entre deux appels : en dessous, le quota se déclenche
RETRY_WAIT = 30    # le serveur se rétablit en ~30 s
MAX_RETRY = 4


def _token():
    tok = os.environ.get("BIBLIO_TOKEN")
    if not tok and os.path.exists(".env"):
        m = re.search(r"BIBLIO_TOKEN\s*[=:]\s*(\S+)", open(".env").read())
        tok = m and m.group(1)
    if not tok:
        sys.exit("BIBLIO_TOKEN introuvable (variable d'environnement ou .env)")
    return tok


_session = None
_last = 0.0


def _post(body):
    global _session
    headers = {
        "Authorization": "Bearer " + _token(),
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if _session:
        headers["mcp-session-id"] = _session
    req = urllib.request.Request(URL, json.dumps(body).encode(), headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        _session = r.headers.get("mcp-session-id") or _session
        text = r.read().decode()
    for line in text.splitlines():
        if line.startswith("data: "):
            return json.loads(line[6:])
    return json.loads(text) if text.strip() else None


def _init():
    _post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
           "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                      "clientInfo": {"name": "biblio.py", "version": "1"}}})
    _post({"jsonrpc": "2.0", "method": "notifications/initialized"})


def _degraded(tool, args, res):
    """Réponse `ok: true` mais vidée par le quota : identifiant demandé absent, total à 0."""
    if not isinstance(res, dict) or not res.get("ok"):
        return False
    if tool == "get_member_fees":
        return res.get("member_id") != args.get("member_id")
    if tool == "get_member":
        return res.get("member") is None
    if tool == "get_book":
        return res.get("book") is None
    if tool == "count_books":
        return res.get("count") == 0
    if tool == "list_missions":
        return not res.get("items")
    return False


def call(tool, args=None):
    global _last
    args = args or {}
    for attempt in range(MAX_RETRY + 1):
        wait = MIN_GAP - (time.time() - _last)
        if wait > 0:
            time.sleep(wait)
        d = _post({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                   "params": {"name": tool, "arguments": args}})
        _last = time.time()
        if "result" not in d:
            return d
        text = "".join(c.get("text", "") for c in d["result"]["content"])
        try:
            res = json.loads(text)
        except ValueError:
            return text
        if not _degraded(tool, args, res):
            return res
        print(f"[biblio] réponse dégradée ({tool}), pause {RETRY_WAIT}s", file=sys.stderr)
        time.sleep(RETRY_WAIT)
    raise RuntimeError(f"{tool}: réponses toujours dégradées après {MAX_RETRY} essais")


def all_pages(tool, args=None, limit=50):
    """Pagine jusqu'à la première page vide : `next` n'est jamais null sur ce serveur."""
    args = dict(args or {}, limit=limit)
    items, key = [], None
    while True:
        a = dict(args, **({"start_key": key} if key else {}))
        res = call(tool, a)
        page = res.get("items", []) if isinstance(res, dict) else []
        if not page:
            return items
        items += page
        key = res.get("next")
        if not key or len(page) < limit:
            return items


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("call", "all"):
        sys.exit(__doc__)
    _init()
    params = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    out = call(sys.argv[2], params) if sys.argv[1] == "call" else all_pages(sys.argv[2], params)
    print(json.dumps(out, ensure_ascii=False, indent=1))
