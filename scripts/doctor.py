#!/usr/bin/env python3
"""
Health check for the whole stack. Read-only: never changes anything.

  python scripts/doctor.py                       # FreeLLMAPI on :3001 (server/Docker)
  python scripts/doctor.py --url http://127.0.0.1:31415   # desktop app
  FREELLMAPI_API_KEY=freellmapi-... python scripts/doctor.py   # also tests /v1 and /mcp

Exit code 0 = everything that is configured works.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
results = []


def env_file():
    env = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def http(method, url, headers=None, body=None, timeout=20):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"content-type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # connection refused, timeout, DNS
        return None, str(e)


def check(name, ok, detail="", optional=False):
    results.append((name, ok, optional))
    mark = "OK  " if ok else ("SKIP" if optional else "FAIL")
    print(f"[{mark}] {name}" + (f" - {detail}" if detail else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.environ.get("FREELLMAPI_URL", "http://127.0.0.1:3001"))
    ap.add_argument("--bridge", default="http://127.0.0.1:3005")
    ap.add_argument("--proxy", default="http://127.0.0.1:8080")
    ap.add_argument("--chat", action="store_true", help="also send one tiny real completion through model=auto")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    env = env_file()
    key = os.environ.get("FREELLMAPI_API_KEY", "")
    base = args.url.rstrip("/")

    print(f"FreeLLMAPI: {base}")
    st, _ = http("GET", f"{base}/api/ping")
    check("FreeLLMAPI is running", st == 200, f"HTTP {st}" if st else "not reachable - is the app/container started?")

    if key:
        st, body = http("GET", f"{base}/v1/models", {"authorization": f"Bearer {key}"})
        n = len(json.loads(body).get("data", [])) if st == 200 else 0
        check("unified key works on /v1/models", st == 200, f"{n} models" if st == 200 else f"HTTP {st}: {body[:120]}")
        st, body = http("POST", f"{base}/mcp", {"authorization": f"Bearer {key}", "accept": "application/json, text/event-stream"},
                        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                         "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "doctor", "version": "1"}}})
        hint = "MCP is OFF: Keys page -> Agent compatibility -> enable MCP" if st == 403 else body[:120]
        check("MCP endpoint /mcp answers", st == 200, "" if st == 200 else f"HTTP {st}: {hint}")
        if args.chat:
            st, body = http("POST", f"{base}/v1/chat/completions", {"authorization": f"Bearer {key}"},
                            {"model": "auto", "max_tokens": 20, "messages": [{"role": "user", "content": "Reply with: pong"}]}, timeout=120)
            served = json.loads(body).get("model", "?") if st == 200 else ""
            check("real completion via model=auto", st == 200, f"served by {served}" if st == 200 else f"HTTP {st}: {body[:160]}")
    else:
        check("unified key tests", False, "set FREELLMAPI_API_KEY to test /v1 and /mcp", optional=True)

    uses_antigravity = bool(env.get("BRIDGE_API_KEY"))
    st, body = http("GET", f"{args.proxy}/health", timeout=5)
    check("Antigravity proxy", st == 200, f"HTTP {st}" if st else "not running", optional=not uses_antigravity)
    st, body = http("GET", f"{args.bridge}/health", timeout=8)
    check("antigravity-bridge -> proxy", st == 200, body[:120] if st else "not running", optional=not uses_antigravity)
    if st == 200 and env.get("BRIDGE_API_KEY"):
        st, body = http("GET", f"{args.bridge}/v1/models", {"authorization": f"Bearer {env['BRIDGE_API_KEY']}"})
        ids = [m["id"] for m in json.loads(body).get("data", [])] if st == 200 else []
        check("bridge lists Antigravity models", st == 200 and bool(ids),
              ", ".join(ids[:6]) if ids else f"HTTP {st}: {body[:120]} (no Google account added yet?)")

    failed = [r for r in results if not r[1] and not r[2]]
    print("\nAll good." if not failed else f"\n{len(failed)} check(s) failed - see docs/07-troubleshooting.md")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
