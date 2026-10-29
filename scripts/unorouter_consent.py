#!/usr/bin/env python3
"""
UnoRouter `:free` models answer 403 `consent_required` until the account consents to the
upstream providers that serve them (they may retain prompts or train on them). The web page
is unorouter.com/consents; this does the same through its API, one account at a time.

  UNOROUTER_API_KEY=... python scripts/unorouter_consent.py              # show what is missing
  UNOROUTER_API_KEY=... python scripts/unorouter_consent.py --grant      # ask, then consent
  ... --model glm-5.3:free --model glm-5.3-flash:free   (default: both GLM 5.3 models)

This is a legal/data-processing consent given in the account owner's name: read the list first.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://unorouter.com/api/auth/provider-consents"
DEFAULT_MODELS = ["glm-5.3:free", "glm-5.3-flash:free"]


def call(method, url, key, body=None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 # urllib's default User-Agent is rejected by the site's firewall
                                 headers={"authorization": f"Bearer {key}", "content-type": "application/json",
                                          "user-agent": "Mozilla/5.0 free-llm-stack"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            status, raw = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    try:
        return status, json.loads(raw or b"{}")
    except json.JSONDecodeError:
        return status, {"success": False, "raw": raw[:200].decode("utf-8", "replace")}


def missing_providers(key, model):
    st, j = call("GET", f"{API}?model={urllib.parse.quote(model)}", key)
    if st != 200 or not j.get("success"):
        sys.exit(f"[ERROR] {model}: HTTP {st} {j}")
    data = j["data"]
    return data.get("covered", False), [p for p in data["providers"] if p.get("status") != "given"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", action="append", help="UnoRouter model id (repeatable)")
    ap.add_argument("--grant", action="store_true", help="give the consent after confirmation")
    ap.add_argument("--yes", action="store_true", help="skip the interactive confirmation")
    ap.add_argument("--locale", default="it")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    key = os.environ.get("UNOROUTER_API_KEY", "").strip()
    if not key:
        sys.exit("Set UNOROUTER_API_KEY (the key of the account to consent for).")

    for model in args.model or DEFAULT_MODELS:
        covered, todo = missing_providers(key, model)
        if covered or not todo:
            print(f"{model}: consent already given")
            continue
        print(f"{model}: consent missing for {len(todo)} provider(s)")
        for p in todo:
            print(f"  - {p['alias']:<6} {p.get('label') or '?':<6} country={p.get('country') or '?':<3} "
                  f"trains_or_retains={p.get('trains_or_retains')} unsafe={p.get('unsafe')} practice={p.get('practice')}")
        if not args.grant:
            continue
        if not args.yes and input(f"Consent for {model} to these providers? [y/N] ").strip().lower() != "y":
            print("  skipped")
            continue
        text = (f"I consent to UnoRouter routing my requests for {model} to these upstream providers: "
                + ", ".join(f"{p['alias']} ({p.get('label')}, {p.get('country') or 'unknown'})" for p in todo)
                + ". I understand they may retain prompts or use them for training.")
        st, j = call("POST", API, key, {"aliases": [], "model": model, "locale": args.locale, "text": text})
        ok = st == 200 and j.get("success") is not False
        print(f"  {'granted' if ok else 'FAILED'}: HTTP {st} {'' if ok else j}")
        covered, todo = missing_providers(key, model)
        print(f"  now covered={covered}")


if __name__ == "__main__":
    main()
