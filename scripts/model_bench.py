#!/usr/bin/env python3
"""Banco di prova per modello: disponibilità, latenza, intelligenza, tool, streaming.

Va lanciato contro un'istanza FreeLLMAPI DI TEST (mai quella di produzione): per isolare ogni
modello riscrive la catena del DB con curator.py, a turni, così che ogni id instradi su un solo
provider. Solo libreria standard. Key da FREELLMAPI_API_KEY.

  sudo -E python3 model_bench.py --url http://127.0.0.1:3012 --db /path/copia/freeapi.db \
       --chain config/chain.vps.json --curator scripts/curator.py --out bench.json
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import secrets
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

KEY = os.environ.get("FREELLMAPI_API_KEY", "")

# Domande con risposta verificabile. Il controllo cerca la risposta nell'ultima riga utile.
QUIZ = [
    ("A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. "
     "How many cents does the ball cost?", r"\b5\b"),
    ("What is 17 * 23?", r"\b391\b"),
    ("How many times does the letter r appear in the words 'strawberry raspberry' combined?", r"\b6\b"),
    ("All bloops are razzies and all razzies are lazzies. Are all bloops definitely lazzies? "
     "Answer yes or no.", r"\byes\b"),
    ("In Python, what does print(sorted([3, 1, 2])[::-1][0]) print?", r"\b3\b"),
    ("What number comes next: 2, 6, 12, 20, 30, ?", r"\b42\b"),
    ("Quanti giorni ha febbraio nel 2028?", r"\b29\b"),
    ("A train leaves at 14:50 and the trip lasts 2 hours and 25 minutes. At what time does it "
     "arrive? Answer in HH:MM.", r"\b17[:.]15\b"),
]
SYSTEM = "Think as needed, then end with a last line of the form 'ANSWER: <answer>'."

# Pausa minima fra due richieste allo stesso provider (secondi), dai limiti osservati.
GAP = {"ovh": 32, "router9": 25, "mistral": 31, "electronhub": 32, "google": 7, "cohere": 4,
       "zhipu": 6, "openrouter": 4, "kilo": 3, "custom": 2}

TOOL = {"type": "function", "function": {
    "name": "get_time", "description": "Returns the current time in a city",
    "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}}


def call(base, model, messages, timeout=120, **extra):
    t0 = time.monotonic()
    r = {"ok": False, "ms": None, "routed": None, "text": "", "tools": 0, "error": None}
    try:
        req = urllib.request.Request(f"{base}/v1/chat/completions",
                                     json.dumps({"model": model, "messages": messages, **extra}).encode(),
                                     {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            d = json.loads(resp.read().decode("utf-8", "replace"))
        v = d.get("_routed_via") or {}
        m = ((d.get("choices") or [{}])[0].get("message")) or {}
        r.update(ok=True, routed=f"{v.get('platform')}/{v.get('model')}", text=m.get("content") or "",
                 tools=len(m.get("tool_calls") or []))
    except urllib.error.HTTPError as e:
        try:
            r["error"] = (json.loads(e.read().decode()).get("error") or {}).get("message", f"HTTP {e.code}")[:140]
        except Exception:
            r["error"] = f"HTTP {e.code}"
    except Exception as e:
        r["error"] = f"{type(e).__name__}: {e}"[:140]
    r["ms"] = int((time.monotonic() - t0) * 1000)
    return r


def ttft(base, model):
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(f"{base}/v1/chat/completions", json.dumps({
            "model": model, "stream": True, "max_tokens": 400,
            "messages": [{"role": "user", "content": "Count from 1 to 10."}]}).encode(),
            {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if line.startswith("data:") and '"content":"' in line and '"content":""' not in line:
                    return int((time.monotonic() - t0) * 1000)
    except Exception:
        return None
    return None


def grade(text, pattern):
    lines = [l for l in text.strip().splitlines() if l.strip()]
    tail = " ".join(l for l in lines if "ANSWER" in l.upper()) or (lines[-1] if lines else "")
    return bool(re.search(pattern, tail, re.I))


def bench_model(base, entry, pause):
    model, platform = entry["model_id"], entry["platform"]
    res = {"platform": platform, "model": model, "routed": set(), "pings": [], "quiz": [], "errors": []}

    def go(fn, *a, **k):
        out = fn(*a, **k)
        time.sleep(pause)
        return out

    for _ in range(3):
        nonce = secrets.token_hex(3).upper()
        r = go(call, base, model, [{"role": "user", "content": f"Reply with exactly: {nonce}"}],
               max_tokens=400, temperature=0, timeout=90)
        good = r["ok"] and nonce in r["text"]
        res["pings"].append({"ok": good, "ms": r["ms"]})
        if r["routed"]:
            res["routed"].add(r["routed"])
        if not good:
            res["errors"].append(r["error"] or f"risposta errata: {r['text'][:40]!r}")
    if not any(p["ok"] for p in res["pings"]):
        res["skipped_rest"] = True  # modello giù: non spreco quota sul resto
    else:
        for q, pattern in QUIZ:
            r = go(call, base, model, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": q}],
                   max_tokens=2500, temperature=0)
            res["quiz"].append(r["ok"] and grade(r["text"], pattern))
            if r["routed"]:
                res["routed"].add(r["routed"])
            if not r["ok"]:
                res["errors"].append(r["error"])
        t = go(call, base, model, [{"role": "user", "content": "What time is it in Rome? Use the tool."}],
               tools=[TOOL], max_tokens=600)
        res["tools"] = t["ok"] and t["tools"] > 0
        res["ttft_ms"] = go(ttft, base, model)
    res["routed"] = sorted(res["routed"])
    return res


def apply_chain(curator, db, entries):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({"chain": entries}, f)
    out = subprocess.run([sys.executable, curator, "apply", "--db", db, "--chain", f.name],
                         capture_output=True, text=True)
    os.unlink(f.name)
    return out.stdout.strip().splitlines()[-1] if out.stdout else out.stderr[-200:]


def canonical(db, entries):
    """Raggruppa le voci che il gateway risolverebbe sullo stesso modello (stesso display_name base)."""
    c = sqlite3.connect(db)
    out = []
    for e in entries:
        row = c.execute("SELECT display_name FROM models WHERE platform=? AND model_id=?",
                        (e["platform"], e["model_id"])).fetchone()
        name = (row[0] if row else e["model_id"]).lower()
        name = re.sub(r"\([^)]*\)", "", name)
        out.append(re.sub(r"[^a-z0-9.]+", "", name))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--chain", required=True)
    ap.add_argument("--curator", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--isolate", action="store_true", help="un modello per volta, gli altri disattivati")
    a = ap.parse_args()
    if not KEY:
        sys.exit("FREELLMAPI_API_KEY non impostata")
    entries = json.load(open(a.chain, encoding="utf-8"))["chain"]
    if a.only:
        entries = [e for e in entries if e["model_id"] in a.only.split(",")]
    if a.isolate:
        # Un modello alla volta, tutti gli altri disattivati: nessun id può finire su un altro provider.
        results = []
        for e in entries:
            apply_chain(a.curator, a.db, [e])
            ids = [e["model_id"], *e.get("alt_ids", [])]
            c = sqlite3.connect(a.db)
            c.execute(f"UPDATE models SET enabled = CASE WHEN platform=? AND model_id IN ({','.join('?' * len(ids))}) "
                      "THEN 1 ELSE 0 END", (e["platform"], *ids))
            # Solo sulla copia di test: i cooldown ereditati falserebbero la prova.
            c.execute("DELETE FROM rate_limit_cooldowns")
            c.commit()
            c.close()
            time.sleep(3)
            req = dict(e, model_id=(e.get("alt_ids") or [e["model_id"]])[0])
            r = bench_model(a.url, req, GAP.get(e["platform"], 2))
            r["model"] = e["model_id"]
            p = [x["ms"] for x in r["pings"] if x["ok"]]
            print(f"  {e['platform']:<11} {e['model_id'][:40]:<40} ping {sum(x['ok'] for x in r['pings'])}/3 "
                  f"quiz {sum(r['quiz'])}/{len(r['quiz'])} p50 {int(statistics.median(p)) if p else '-'} "
                  f"via {','.join(r['routed'])}", flush=True)
            results.append(r)
            json.dump(results, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"Scritto {a.out}")
        return
    names = canonical(a.db, entries)
    rounds, seen = [], {}
    for e, n in zip(entries, names):
        k = seen.get(n, 0)
        seen[n] = k + 1
        while len(rounds) <= k:
            rounds.append([])
        rounds[k].append(e)
    results = []
    for i, rnd in enumerate(rounds, 1):
        print(f"[turno {i}/{len(rounds)}] {len(rnd)} modelli - {apply_chain(a.curator, a.db, rnd)}", flush=True)
        time.sleep(5)
        by_platform: dict = {}
        for e in rnd:
            by_platform.setdefault(e["platform"], []).append(e)

        def run_platform(items):
            out = []
            for e in items:
                r = bench_model(a.url, e, GAP.get(e["platform"], 2))
                p = [x["ms"] for x in r["pings"] if x["ok"]]
                print(f"  {e['platform']:<11} {e['model_id'][:40]:<40} ping {sum(x['ok'] for x in r['pings'])}/3 "
                      f"quiz {sum(r['quiz'])}/{len(r['quiz'])} p50 {int(statistics.median(p)) if p else '-'}",
                      flush=True)
                out.append(r)
            return out

        with cf.ThreadPoolExecutor(len(by_platform)) as ex:
            for chunk in ex.map(run_platform, by_platform.values()):
                results.extend(chunk)
        json.dump(results, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Scritto {a.out}")


if __name__ == "__main__":
    main()
