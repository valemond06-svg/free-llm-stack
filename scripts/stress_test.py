#!/usr/bin/env python3
"""Stress test di FreeLLMAPI: prova reale di ogni modello utilizzabile, carico su `auto`, MCP.

La key arriva solo da FREELLMAPI_API_KEY. I prompt sono banali (nessun dato personale).
Scrive <out>.json e stampa un riepilogo. Fasi: models, gateway, load, mcp (--phases).

  python scripts/stress_test.py --url http://127.0.0.1:31415 --out reports/stress
  python scripts/stress_test.py --phases load --levels 5,10 --label failover --out reports/fo
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import secrets
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request

KEY = os.environ.get("FREELLMAPI_API_KEY", "")
TIMEOUT = 90
ALIASES = {"auto", "fusion", "claude-opus-4-5", "claude-sonnet-4-5", "claude-haiku-4-5"}
_pace_lock = threading.Lock()
_next_start = [0.0]
PACE = 0.7  # il gateway limita a 120 richieste/minuto


def pace() -> None:
    with _pace_lock:
        now = time.monotonic()
        wait = max(0.0, _next_start[0] - now)
        _next_start[0] = max(now, _next_start[0]) + PACE
    if wait:
        time.sleep(wait)


def scrub(text: object) -> str:
    s = re.sub(r"\s+", " ", str(text))
    s = re.sub(r"(sk|gsk|nvapi|AIza|freellmapi)[-_A-Za-z0-9]{12,}", "<key>", s)
    return s[:160]


def request(url: str, body: dict | None = None, headers: dict | None = None, timeout: int = TIMEOUT):
    h = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    h.update(headers or {})
    data = json.dumps(body).encode() if body is not None else None
    return urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=timeout)


def chat(base: str, model: str, messages: list, **extra) -> dict:
    """Una chiamata non-stream. Non solleva: l'esito è sempre nel dizionario."""
    pace()
    t0 = time.monotonic()
    out = {"model": model, "ok": False, "latency_ms": None, "routed": None, "error": None,
           "http": None, "content": "", "tool_calls": 0, "finish": None, "out_tokens": None}
    try:
        with request(f"{base}/v1/chat/completions",
                     {"model": model, "messages": messages, **extra}) as r:
            out["http"] = r.status
            d = json.loads(r.read().decode("utf-8", "replace"))
        out["latency_ms"] = int((time.monotonic() - t0) * 1000)
        v = d.get("_routed_via") or {}
        out["routed"] = f"{v.get('platform')}/{v.get('model')}"
        c = (d.get("choices") or [{}])[0]
        m = c.get("message") or {}
        out["content"] = m.get("content") or ""
        out["tool_calls"] = len(m.get("tool_calls") or [])
        out["finish"] = c.get("finish_reason")
        out["out_tokens"] = (d.get("usage") or {}).get("completion_tokens")
        out["ok"] = True
    except urllib.error.HTTPError as e:
        out["http"] = e.code
        out["latency_ms"] = int((time.monotonic() - t0) * 1000)
        try:
            b = json.loads(e.read().decode("utf-8", "replace"))
            out["error"] = scrub((b.get("error") or {}).get("message") or b)
        except Exception:
            out["error"] = f"HTTP {e.code}"
    except Exception as e:  # timeout, connessione rifiutata
        out["latency_ms"] = int((time.monotonic() - t0) * 1000)
        out["error"] = scrub(f"{type(e).__name__}: {e}")
    return out


def stream(base: str, model: str, messages: list, **extra) -> dict:
    pace()
    t0 = time.monotonic()
    out = {"ok": False, "ttft_ms": None, "total_ms": None, "chunks": 0, "error": None, "text": ""}
    try:
        with request(f"{base}/v1/chat/completions",
                     {"model": model, "messages": messages, "stream": True, **extra}) as r:
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:") or line.endswith("[DONE]"):
                    continue
                try:
                    delta = (json.loads(line[5:]).get("choices") or [{}])[0].get("delta") or {}
                except ValueError:
                    continue
                piece = delta.get("content") or ""
                if piece:
                    if out["ttft_ms"] is None:
                        out["ttft_ms"] = int((time.monotonic() - t0) * 1000)
                    out["chunks"] += 1
                    out["text"] += piece
        out["total_ms"] = int((time.monotonic() - t0) * 1000)
        out["ok"] = bool(out["text"])
        if not out["ok"]:
            out["error"] = "stream vuoto"
    except urllib.error.HTTPError as e:
        out["error"] = f"HTTP {e.code}"
    except Exception as e:
        out["error"] = scrub(f"{type(e).__name__}: {e}")
    return out


def pong(base: str, model: str) -> dict:
    nonce = secrets.token_hex(3).upper()
    r = chat(base, model, [{"role": "user", "content": f"Reply with exactly this code and nothing else: {nonce}"}],
             max_tokens=400, temperature=0)
    r["correct"] = r["ok"] and nonce in r["content"]
    r["content"] = scrub(r["content"])[:80]
    return r


TOOL = {"type": "function", "function": {
    "name": "get_time", "description": "Returns the current time in a city",
    "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}}


def test_model(base: str, model: str, rounds: int) -> dict:
    res: dict = {"model": model, "pong": []}
    for i in range(rounds):
        if i:
            time.sleep(8)
        res["pong"].append(pong(base, model))
    res["stream"] = stream(base, model, [{"role": "user", "content": "Count from 1 to 10 separated by spaces."}],
                           max_tokens=400)
    res["stream"].pop("text", None)
    t = chat(base, model, [{"role": "user", "content": "What time is it in Rome? Use the tool."}],
             tools=[TOOL], max_tokens=400)
    res["tools"] = {"ok": t["ok"] and t["tool_calls"] > 0, "error": t["error"], "routed": t["routed"]}
    long = chat(base, model, [{"role": "user", "content": "Write 150 words about the history of bridges."}],
                max_tokens=800)
    res["long"] = {"ok": long["ok"] and len(long["content"]) > 200, "latency_ms": long["latency_ms"],
                   "chars": len(long["content"]), "out_tokens": long["out_tokens"],
                   "finish": long["finish"], "error": long["error"]}
    return res


def phase_models(base: str, models: list, rounds: int, workers: int) -> list:
    results = []
    with cf.ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(test_model, base, m, rounds): m for m in models}
        for f in cf.as_completed(futs):
            r = f.result()
            good = sum(p["correct"] for p in r["pong"])
            print(f"  {r['model']:<30} pong {good}/{len(r['pong'])}  "
                  f"tools {'si' if r['tools']['ok'] else 'no'}  "
                  f"stream {'si' if r['stream']['ok'] else 'no'}", flush=True)
            results.append(r)
    return sorted(results, key=lambda r: r["model"])


def phase_gateway(base: str, total: int = 1000, conc: int = 50) -> dict:
    """Carico solo locale, nessuna quota: /health in parallelo."""
    lat, errs = [], []

    def hit(_):
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(f"{base}/health", timeout=20) as r:
                r.read()
            lat.append((time.monotonic() - t0) * 1000)
        except Exception as e:
            errs.append(scrub(e))

    t0 = time.monotonic()
    with cf.ThreadPoolExecutor(conc) as ex:
        list(ex.map(hit, range(total)))
    return summarize_lat(lat) | {"total": total, "concurrency": conc, "errors": len(errs),
                                 "first_errors": errs[:3], "rps": int(total / (time.monotonic() - t0))}


def summarize_lat(lat: list) -> dict:
    if not lat:
        return {"p50_ms": None, "p95_ms": None, "max_ms": None}
    s = sorted(lat)
    return {"p50_ms": int(statistics.median(s)), "p95_ms": int(s[min(len(s) - 1, int(len(s) * .95))]),
            "max_ms": int(s[-1])}


def phase_load(base: str, levels: list) -> list:
    global PACE
    saved, PACE = PACE, 0.0  # qui la raffica è lo scopo
    out = []
    for n in levels:
        total = n * 2
        print(f"  concorrenza {n}: {total} richieste", flush=True)
        t0 = time.monotonic()
        with cf.ThreadPoolExecutor(n) as ex:
            rs = list(ex.map(lambda _: pong(base, "auto"), range(total)))
        ok = [r for r in rs if r["correct"]]
        routed: dict = {}
        for r in ok:
            routed[r["routed"]] = routed.get(r["routed"], 0) + 1
        errs: dict = {}
        for r in rs:
            if not r["correct"]:
                k = r["error"] or f"risposta errata: {r['content']}"
                errs[k] = errs.get(k, 0) + 1
        out.append({"concurrency": n, "total": total, "ok": len(ok),
                    "wall_s": round(time.monotonic() - t0, 1),
                    **summarize_lat([r["latency_ms"] for r in ok]), "routed": routed, "errors": errs})
        time.sleep(10)
    PACE = saved
    return out


def mcp_call(base: str, method: str, params: dict) -> tuple:
    t0 = time.monotonic()
    try:
        with request(f"{base}/mcp", {"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                     {"Accept": "application/json, text/event-stream"}, 120) as r:
            t = r.read().decode("utf-8", "replace")
        d = json.loads(t[t.find("{"):].split("\n")[0])
        ms = int((time.monotonic() - t0) * 1000)
        if "error" in d:
            return False, ms, scrub(d["error"])
        res = d.get("result") or {}
        text = " ".join(c.get("text", "") for c in res.get("content", []))
        return not res.get("isError"), ms, scrub(text)
    except Exception as e:
        return False, int((time.monotonic() - t0) * 1000), scrub(e)


def phase_mcp(base: str) -> list:
    calls = [("healthcheck", {}), ("routing_info", {}), ("quota_outlook", {}), ("provider_health", {}),
             ("ask_freellmapi", {"prompt": "Reply with exactly: MCP-OK", "model": "auto", "max_tokens": 300}),
             ("web_search", {"query": "Verona weather", "max_results": 2})]
    out = []
    for name, args in calls:
        ok, ms, text = mcp_call(base, "tools/call", {"name": name, "arguments": args})
        out.append({"tool": name, "ok": ok, "ms": ms, "text": text})
        print(f"  {name:<18} {'OK' if ok else 'KO'} {ms}ms {text[:90]}", flush=True)
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:31415")
    ap.add_argument("--out", required=True, help="prefisso del file .json")
    ap.add_argument("--phases", default="models,gateway,load,mcp")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--levels", default="1,5,10,15")
    ap.add_argument("--label", default="baseline")
    ap.add_argument("--only", default="", help="modelli separati da virgola")
    a = ap.parse_args()
    if not KEY:
        print("FREELLMAPI_API_KEY non impostata", file=sys.stderr)
        return 2
    base = a.url.rstrip("/")
    phases = a.phases.split(",")
    with request(f"{base}/v1/models") as r:
        catalog = json.loads(r.read().decode("utf-8"))["data"]
    report: dict = {"label": a.label, "started": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "catalog": [{k: m.get(k) for k in ("id", "name", "available", "unavailable_reason",
                                                       "execution_status", "context_window")} for m in catalog]}
    usable = [m["id"] for m in catalog if m.get("available")]
    if a.only:
        usable = a.only.split(",")
    if "models" in phases:
        print(f"[models] {len(usable)} modelli, {a.rounds} round", flush=True)
        report["models"] = phase_models(base, usable, a.rounds, a.workers)
    if "gateway" in phases:
        print("[gateway]", flush=True)
        report["gateway"] = phase_gateway(base)
        print(" ", report["gateway"], flush=True)
    if "load" in phases:
        print("[load]", flush=True)
        report["load"] = phase_load(base, [int(x) for x in a.levels.split(",")])
        for l in report["load"]:
            print(" ", json.dumps(l, ensure_ascii=False)[:400], flush=True)
    if "mcp" in phases:
        print("[mcp]", flush=True)
        report["mcp"] = phase_mcp(base)
    report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(f"{a.out}.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(f"Scritto {a.out}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
