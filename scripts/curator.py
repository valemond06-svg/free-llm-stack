#!/usr/bin/env python3
"""
FreeLLMAPI curator: builds the `auto` fallback chain directly in FreeLLMAPI's SQLite DB.

Commands
  report                 show the chain the router is actually using
  apply  [--chain FILE]  apply the hand-curated chain from config/chain.json
  auto                   score every usable model and rebuild the chain
                         (gatekeeper -> anti-cannibalization -> smart positioning)

Common flags
  --db PATH      FreeLLMAPI database (default: $FREELLMAPI_DB_PATH, then the OS default)
  --dry-run      print what would change, write nothing

Why both tables: when a profile is active (the desktop app always has "Default"),
the router reads `profile_models`, not `fallback_config`. Writing only
`fallback_config` silently changes nothing. This script writes both, and turns off
`auto_include_new_models` on the active profile so catalog syncs don't re-pollute
the chain (re-run `auto` after a catalog update instead).
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CHAIN = ROOT / "config" / "chain.json"


def default_db_path():
    if os.environ.get("FREELLMAPI_DB_PATH"):
        return Path(os.environ["FREELLMAPI_DB_PATH"]).expanduser()
    candidates = [
        ROOT / "data" / "freellmapi" / "freeapi.db",  # docker bind mount from deploy/docker-compose.yml
        ROOT / "data" / "freellmapi" / "freellmapi.db",
    ]
    if sys.platform == "win32":
        candidates.append(Path(os.environ.get("APPDATA", "")) / "FreeLLMAPI" / "freeapi.db")
    elif sys.platform == "darwin":
        candidates.append(Path.home() / "Library/Application Support/FreeLLMAPI/freeapi.db")
    else:
        candidates.append(Path.home() / ".config/FreeLLMAPI/freeapi.db")
    for c in candidates:
        if c.exists():
            return c
    return candidates[-1]


def connect(db_path):
    if not db_path.exists():
        sys.exit(f"[ERROR] database not found: {db_path}\n"
                 "Start FreeLLMAPI once (it creates the DB) or pass --db / FREELLMAPI_DB_PATH.")
    conn = sqlite3.connect(db_path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


def backup(conn, db_path):
    dest = db_path.with_name(f"{db_path.name}.curator-{time.strftime('%Y%m%d-%H%M%S')}.bak")
    with sqlite3.connect(dest) as out:
        conn.backup(out)
    print(f"[backup] {dest}")


def active_profile_id(conn):
    row = conn.execute("SELECT value FROM settings WHERE key = 'active_profile_id'").fetchone()
    if not row or not str(row["value"]).strip():
        return None
    pid = int(float(row["value"]))
    return pid if conn.execute("SELECT 1 FROM profiles WHERE id = ?", (pid,)).fetchone() else None


def usable_platforms(conn):
    rows = conn.execute("""SELECT DISTINCT platform FROM api_keys
                           WHERE enabled = 1 AND status IN ('healthy', 'unknown')""").fetchall()
    return {r["platform"] for r in rows}


def find_model(conn, platform, model_id, alt_ids=()):
    """First match among model_id and its alternatives (same model under another proxy's naming)."""
    for mid in (model_id, *alt_ids):
        row = conn.execute("SELECT * FROM models WHERE platform = ? AND model_id = ? AND enabled = 1 ORDER BY id LIMIT 1",
                           (platform, mid)).fetchone()
        if row:
            return row
    return conn.execute("SELECT * FROM models WHERE platform = ? AND model_id = ? ORDER BY id LIMIT 1",
                        (platform, model_id)).fetchone()


def write_chain(conn, model_ids, disable_ids=(), dry_run=False):
    """model_ids: ordered list of models.id. Writes fallback_config and the active profile."""
    if dry_run:
        return
    for mid in disable_ids:
        conn.execute("UPDATE models SET enabled = 0 WHERE id = ?", (mid,))
    conn.execute("DELETE FROM fallback_config")
    for i, mid in enumerate(model_ids):
        prio = (i + 1) * 10
        conn.execute("UPDATE models SET enabled = 1 WHERE id = ?", (mid,))
        conn.execute("INSERT INTO fallback_config (model_db_id, priority, enabled) VALUES (?, ?, 1)", (mid, prio))
    pid = active_profile_id(conn)
    if pid is not None:
        conn.execute("UPDATE profile_models SET enabled = 0 WHERE profile_id = ?", (pid,))
        for i, mid in enumerate(model_ids):
            conn.execute("""INSERT INTO profile_models (profile_id, model_db_id, priority, enabled)
                            VALUES (?, ?, ?, 1)
                            ON CONFLICT(profile_id, model_db_id) DO UPDATE SET priority = excluded.priority, enabled = 1""",
                         (pid, mid, (i + 1) * 10))
        conn.execute("UPDATE profiles SET auto_include_new_models = 0, auto_sort = NULL WHERE id = ?", (pid,))
    conn.commit()


def current_chain(conn):
    pid = active_profile_id(conn)
    if pid is not None:
        sql = """SELECT pm.priority, m.* FROM profile_models pm JOIN models m ON m.id = pm.model_db_id
                 WHERE pm.profile_id = ? AND pm.enabled = 1 AND m.enabled = 1 ORDER BY pm.priority"""
        return pid, conn.execute(sql, (pid,)).fetchall()
    sql = """SELECT fc.priority, m.* FROM fallback_config fc JOIN models m ON m.id = fc.model_db_id
             WHERE fc.enabled = 1 AND m.enabled = 1 ORDER BY fc.priority"""
    return None, conn.execute(sql).fetchall()


def print_chain(rows, usable):
    for i, r in enumerate(rows, 1):
        flag = "" if r["platform"] in usable else "   <- NO KEY for this provider, skipped by router"
        ctx = f"{r['context_window'] // 1000}K" if r["context_window"] else "?"
        print(f"  {i:>2}. {r['display_name'][:46]:<46} {r['platform']:<11} int#{r['intelligence_rank']:<3} "
              f"ctx {ctx:<6} rpm {r['rpm_limit'] or '-':<4}{flag}")


# ---------------- commands ----------------

def cmd_report(conn, args):
    pid, rows = current_chain(conn)
    usable = usable_platforms(conn)
    print(f"Active chain ({'profile #' + str(pid) if pid else 'fallback_config'}): {len(rows)} models")
    print_chain(rows, usable)
    keys = conn.execute("SELECT platform, COUNT(*) n FROM api_keys WHERE enabled = 1 GROUP BY platform ORDER BY n DESC").fetchall()
    print("\nKeys per provider: " + ", ".join(f"{k['platform']}={k['n']}" for k in keys))


def cmd_apply(conn, args):
    chain = json.loads(Path(args.chain).read_text(encoding="utf-8"))
    usable = usable_platforms(conn)
    ids, missing = [], []
    for entry in chain["chain"]:
        m = find_model(conn, entry["platform"], entry["model_id"], entry.get("alt_ids", ()))
        if not m:
            missing.append(entry)
            continue
        if entry["platform"] not in usable:
            print(f"  [skip - no key ] {entry['platform']}/{entry['model_id']}")
            continue
        ids.append(m["id"])
        print(f"  [{len(ids):>2}] {m['display_name']} ({entry['platform']})")
    for e in missing:
        print(f"  [missing      ] {e['platform']}/{e['model_id']} - not in this install's catalog "
              "(renamed/retired, or custom endpoint not added yet)")
    if not ids:
        sys.exit("[ERROR] no chain model is usable. Add provider keys in the dashboard first.")
    if not args.dry_run:
        backup(conn, args.db)
    write_chain(conn, ids, dry_run=args.dry_run)
    print(f"\n{'Would apply' if args.dry_run else 'Applied'} {len(ids)} models.")


def reliability(conn):
    """Success rate (0-100) per (platform, model_id) over the last 14 days."""
    rows = conn.execute("""SELECT platform, model_id, COUNT(*) n, SUM(status = 'success') ok FROM requests
                           WHERE created_at > datetime('now', '-14 day') GROUP BY platform, model_id""").fetchall()
    return {(r["platform"], r["model_id"]): (100.0 * r["ok"] / r["n"], r["n"]) for r in rows}


def normalize(value, lo, hi):
    """Rank -> 0..100 score, where rank lo (best) = 100."""
    if value is None or hi == lo:
        return 50.0
    return 100.0 * (1 - (value - lo) / (hi - lo))


def cmd_auto(conn, args):
    rules = json.loads(Path(args.chain).read_text(encoding="utf-8"))["rules"]
    usable = usable_platforms(conn)
    rel = reliability(conn)
    patterns = [re.compile(p, re.I) for p in rules["non_chat_patterns"]]
    pinned = rules.get("pinned_top", [])
    pinned_keys = {(p["platform"], mid) for p in pinned for mid in (p["model_id"], *p.get("alt_ids", ()))}

    rejected, candidates = [], []
    for m in conn.execute("SELECT * FROM models").fetchall():
        key = (m["platform"], m["model_id"])
        if key in pinned_keys:
            continue
        if m["platform"] not in usable:
            continue  # no key: leave untouched, it is simply not routable
        name = f"{m['model_id']} {m['display_name']}"
        if not m["supports_tools"]:
            rejected.append((m, "no tool calling"))
        elif any(p.search(name) for p in patterns):
            rejected.append((m, "non-chat / safety / audio model"))
        elif m["intelligence_rank"] is not None and m["intelligence_rank"] > rules["max_intelligence_rank"]:
            rejected.append((m, f"intelligence rank {m['intelligence_rank']} > {rules['max_intelligence_rank']}"))
        elif any(re.search(p, name, re.I) for p in rules.get("weak_variant_patterns", [])):
            rejected.append((m, "lite/mini variant that burns the provider's shared quota"))
        else:
            candidates.append(m)

    # Anti-cannibalization: keep the best N per provider (plus one vision model if any).
    by_platform = {}
    for m in candidates:
        by_platform.setdefault(m["platform"], []).append(m)
    kept = []
    for plat, models in by_platform.items():
        models.sort(key=lambda m: m["intelligence_rank"] if m["intelligence_rank"] is not None else 999)
        keep = models[: rules["max_models_per_provider"]]
        if not any(m["supports_vision"] for m in keep):
            vision = next((m for m in models[len(keep):] if m["supports_vision"]), None)
            if vision:
                keep = keep[:-1] + [vision] if len(keep) >= rules["max_models_per_provider"] else keep + [vision]
        for m in models:
            if m in keep:
                kept.append(m)
            else:
                rejected.append((m, f"cannibalization: {plat} keeps only its top {rules['max_models_per_provider']}"))

    # Smart positioning.
    ints = [m["intelligence_rank"] for m in kept if m["intelligence_rank"] is not None]
    speeds = [m["speed_rank"] for m in kept if m["speed_rank"] is not None]
    w = rules["weights"]
    scored = []
    for m in kept:
        i_score = normalize(m["intelligence_rank"], min(ints or [0]), max(ints or [0]))
        s_score = normalize(m["speed_rank"], min(speeds or [0]), max(speeds or [0]))
        r_score, samples = rel.get((m["platform"], m["model_id"]), (None, 0))
        if samples < rules["min_samples_for_reliability"]:
            r_score = rules["default_reliability"]
        score = i_score * w["intelligence"] + r_score * w["reliability"] + s_score * w["speed"]
        ctx = m["context_window"] or 0
        score += 8 if ctx >= 1_000_000 else 5 if ctx >= 256_000 else 0
        slow = (m["rpm_limit"] is not None and m["rpm_limit"] <= rules["low_rpm"]) or s_score < rules["slow_speed_score"]
        scored.append({"m": m, "score": score, "slow": slow, "rel": r_score, "samples": samples})
    scored.sort(key=lambda x: x["score"], reverse=True)

    # Low-RPM / slow models never take the first `slow_min_position - 1` slots
    # (they would stall consecutive agent tool calls); after that, score decides.
    cut = rules["slow_min_position"] - 1
    head = [x for x in scored if not x["slow"]][:cut]
    ordered = head + [x for x in scored if x not in head]

    pinned_ids = []
    for p in pinned:
        m = find_model(conn, p["platform"], p["model_id"], p.get("alt_ids", ()))
        if m and p["platform"] in usable:
            pinned_ids.append(m["id"])

    print(f"Rejected ({len(rejected)}):")
    for m, why in sorted(rejected, key=lambda x: x[0]["platform"]):
        print(f"  - {m['display_name'][:50]:<50} {m['platform']:<11} {why}")
    print(f"\nChain ({len(pinned_ids) + len(ordered)}):")
    n = 0
    for mid in pinned_ids:
        n += 1
        m = conn.execute("SELECT display_name, platform FROM models WHERE id = ?", (mid,)).fetchone()
        print(f"  {n:>2}. {m['display_name'][:46]:<46} {m['platform']:<11} pinned")
    for x in ordered:
        n += 1
        rel_txt = f"rel {x['rel']:.0f}%" + ("" if x["samples"] >= rules["min_samples_for_reliability"] else " (default)")
        print(f"  {n:>2}. {x['m']['display_name'][:46]:<46} {x['m']['platform']:<11} score {x['score']:5.1f}  {rel_txt}"
              f"{'  [slow/low-RPM]' if x['slow'] else ''}")

    if not args.dry_run:
        backup(conn, args.db)
    write_chain(conn, pinned_ids + [x["m"]["id"] for x in ordered],
                disable_ids=[m["id"] for m, _ in rejected], dry_run=args.dry_run)
    print("\n(dry run - nothing written)" if args.dry_run else "\nChain written.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["report", "apply", "auto"])
    ap.add_argument("--db", type=Path, default=None)
    ap.add_argument("--chain", default=str(DEFAULT_CHAIN), help="chain/rules JSON (default config/chain.json)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    args.db = (args.db or default_db_path()).resolve()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(f"DB: {args.db}")
    conn = connect(args.db)
    {"report": cmd_report, "apply": cmd_apply, "auto": cmd_auto}[args.command](conn, args)
    conn.close()


if __name__ == "__main__":
    main()
