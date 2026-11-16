#!/usr/bin/env python3
"""
Smart Hybrid Router for Claude Code & FreeLLMAPI
=================================================
Intelligent multi-tier proxy between Claude Code CLI, Local LLMs (PC Fisso Vulkan, Laptop CUDA),
and FreeLLMAPI Cloud Chain (Groq, Cerebras, OpenRouter, NVIDIA, Google).

Author: Lead Agency Orchestrator (Antigravity)
Port: 127.0.0.1:31415

Tiers:
  - Tier 1 (FAST): Groq/Cerebras FreeLLMAPI (<0.5s latency, micro-tasks, commit messages, format, regex)
  - Tier 2 (LOCAL): PC Fisso Vulkan via direct cable 10.10.10.1 / Tailscale 100.83.194.37 (Qwen3.6-35B, 65k ctx)
                    or Laptop 127.0.0.1 (if GTA5 not running) -> 0 cost, 0 quota, maximum privacy.
  - Tier 3 (ELITE): FreeLLMAPI Elite Chain (Qwen 3.8 Max 1M ctx, Nemotron 550B, Gemini Flash, Claude Sonnet mapping)
                    for complex architecture, agency orchestration, multi-file refactoring, deep reasoning.
"""

import sys
import os
import json
import time
import re
import socket
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, Any, Tuple, Optional

# Configuration
ROUTER_HOST = os.environ.get("ROUTER_HOST", "127.0.0.1")
ROUTER_PORT = int(os.environ.get("ROUTER_PORT", 3012))

# PC Fisso Configuration
FISSO_CABLE_URL = os.environ.get("FISSO_CABLE_URL", "http://10.10.10.1:8080/v1")
FISSO_TAILSCALE_URL = os.environ.get("FISSO_TAILSCALE_URL", "http://100.83.194.37:8080/v1")
FISSO_API_KEY = os.environ.get("FISSO_API_KEY", "61e25408bc484a99f8141347eaa6bad2742b5cb94aa21bda564828fd3b55fc81")

# Laptop Local AI Configuration
LAPTOP_URL = os.environ.get("LAPTOP_URL", "http://127.0.0.1:8080/v1")
LAPTOP_API_KEY = os.environ.get("LAPTOP_API_KEY", "")

# FreeLLMAPI Cloud Configuration
FREELLMAPI_URL = os.environ.get("FREELLMAPI_URL", "http://100.119.96.109:3011/v1").rstrip("/")
if not FREELLMAPI_URL.endswith("/v1"):
    FREELLMAPI_URL += "/v1"
FREELLMAPI_API_KEY = os.environ.get("FREELLMAPI_API_KEY", "freellmapi-cc65ebfe697a3ec347fe49caa397e12c33d576fcae39b726")

# Logging Setup
LOG_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(LOG_DIR, "router.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8")
    ]
)
logger = logging.getLogger("SmartRouter")


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in separate threads for concurrency."""
    daemon_threads = True


def is_gaming_active() -> bool:
    """Check if GTA5.exe or major games are running on the laptop to avoid VRAM/GPU contention."""
    try:
        if sys.platform == "win32":
            # Quick query via tasklist
            output = os.popen('tasklist /FI "IMAGENAME eq GTA5.exe" /NH').read()
            if "GTA5.exe" in output:
                return True
            # Check other games if needed
            output_play = os.popen('tasklist /FI "IMAGENAME eq PlayGTAV.exe" /NH').read()
            if "PlayGTAV.exe" in output_play:
                return True
    except Exception as e:
        logger.debug(f"Game check error: {e}")
    return False


def check_endpoint_health(url: str, headers: Optional[Dict[str, str]] = None, timeout: float = 2.0) -> bool:
    """Quick HTTP probe to test if an LLM server is up and responsive."""
    try:
        probe_url = f"{url}/models"
        req = urllib.request.Request(probe_url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status in (200, 401)  # 200 or 401 means server is alive
    except Exception:
        return False


def get_best_local_endpoint() -> Optional[Tuple[str, str, str]]:
    """
    Returns (endpoint_url, api_key, model_name) for local AI, or None if unavailable.
    Prioritizes PC Fisso via direct cable (10.10.10.1), then Tailscale (100.83.194.37),
    then Laptop (if GTA5 not running).
    """
    gaming = is_gaming_active()
    fisso_headers = {"Authorization": f"Bearer {FISSO_API_KEY}"}

    # 1. PC Fisso via Direct Cable (Fastest, ~2ms)
    if check_endpoint_health(FISSO_CABLE_URL, fisso_headers, timeout=1.0):
        return (FISSO_CABLE_URL, FISSO_API_KEY, "local")

    # 2. PC Fisso via Tailscale
    if check_endpoint_health(FISSO_TAILSCALE_URL, fisso_headers, timeout=1.5):
        return (FISSO_TAILSCALE_URL, FISSO_API_KEY, "local")

    # 3. Laptop local AI (only if no game is running)
    if not gaming:
        laptop_headers = {"Authorization": f"Bearer {LAPTOP_API_KEY}"} if LAPTOP_API_KEY else {}
        if check_endpoint_health(LAPTOP_URL, laptop_headers, timeout=1.0):
            return (LAPTOP_URL, LAPTOP_API_KEY, "local")

    return None


def extract_prompt_text(messages: list) -> str:
    """Extract all text contents from messages list."""
    texts = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    texts.append(part.get("text", ""))
    return "\n".join(texts)


def classify_tier(body: dict) -> Tuple[str, str, str, str]:
    """
    Analyze request body and determine:
    Returns (tier_name, target_url, api_key, target_model)
    """
    model_req = str(body.get("model", "")).lower()
    messages = body.get("messages", [])
    prompt_text = extract_prompt_text(messages)
    word_count = len(prompt_text.split())
    has_tools = bool(body.get("tools"))
    gaming = is_gaming_active()

    local_backend = get_best_local_endpoint()

    # 1. Explicit model overrides
    if model_req in ("fast", "haiku", "quick", "groq"):
        return ("TIER_1_FAST", FREELLMAPI_URL, FREELLMAPI_API_KEY, "claude-haiku-4-5")

    if model_req in ("local", "fisso", "laptop", "offline", "private"):
        if local_backend:
            url, key, mod = local_backend
            return ("TIER_2_LOCAL", url, key, mod)
        else:
            logger.warning("Local backend requested but unavailable. Falling back to Tier 3 Elite.")
            return ("TIER_3_ELITE_FALLBACK", FREELLMAPI_URL, FREELLMAPI_API_KEY, "claude-sonnet-4-5")

    if model_req in ("elite", "opus", "sonnet-max", "orchestrator", "agency"):
        return ("TIER_3_ELITE", FREELLMAPI_URL, FREELLMAPI_API_KEY, "claude-sonnet-4-5")

    # 2. Intelligent Complexity Heuristics for auto / claude-*

    # Check for agency / architectural / complex markers
    architecture_keywords = [
        "architettura", "architecture", "orchestrator", "orchestrare", "scomponi",
        "refactor intero", "multi-file", "system design", "database schema",
        "security audit", "vulnerability assessment", "full stack", "pipeline",
        "concorrenza", "distributed", "benchmark completo", "graphify"
    ]
    is_architectural = any(k in prompt_text.lower() for k in architecture_keywords)

    # Check for micro-task markers
    micro_keywords = [
        "commit message", "git commit", "messaggio di commit", "regex", "formattazione",
        "correggi il typo", "formatta", "json valido", "traduci in", "spiega brevemente",
        "cosa fa questo comando", "ping", "test"
    ]
    is_micro = (word_count < 250) and any(k in prompt_text.lower() for k in micro_keywords)

    # Decision Matrix:
    # A) Micro-task (< 300 words without tools, quick response needed)
    if is_micro or (word_count < 150 and not has_tools and not is_architectural):
        return ("TIER_1_FAST", FREELLMAPI_URL, FREELLMAPI_API_KEY, "claude-haiku-4-5")

    # B) Standard coding, single-file edits, unit tests, scripts, private context
    # If local backend is available, route to local Vulkan/CUDA! (Zero tokens used, zero cost)
    if local_backend and not is_architectural and word_count < 15000:
        url, key, mod = local_backend
        return ("TIER_2_LOCAL", url, key, mod)

    # C) Complex tasks, architectural planning, multi-file reasoning, high context (>15k)
    # Route to FreeLLMAPI Elite Chain (Sonnet / Qwen Max / Nemotron / Gemini)
    return ("TIER_3_ELITE", FREELLMAPI_URL, FREELLMAPI_API_KEY, "claude-sonnet-4-5")


class SmartRouterHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        logger.debug("%s - - [%s] %s" % (self.client_address[0], self.log_date_time_string(), format % args))

    def do_GET(self):
        logger.info(f"Incoming GET: {self.path} headers: {dict(self.headers)}")
        if self.path in ("/", "/health", "/healthz"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            gaming = is_gaming_active()
            local_be = get_best_local_endpoint()
            freellm_ok = check_endpoint_health(FREELLMAPI_URL, {"Authorization": f"Bearer {FREELLMAPI_API_KEY}"})

            res = {
                "status": "ok",
                "service": "claude-free-smart-router",
                "port": ROUTER_PORT,
                "gaming_mode_active": gaming,
                "local_backend_active": bool(local_be),
                "local_backend_url": local_be[0] if local_be else None,
                "freellmapi_cloud_active": freellm_ok,
                "tiers": {
                    "tier_1_fast": "Groq Llama 3.3 / FreeLLMAPI (<0.5s)",
                    "tier_2_local": f"Local Vulkan/CUDA ({local_be[0] if local_be else 'offline'})",
                    "tier_3_elite": "FreeLLMAPI Elite (Qwen 3.8 Max, Nemotron 550B, Gemini Flash, Claude Sonnet)"
                }
            }
            self.wfile.write(json.dumps(res, indent=2).encode("utf-8"))
            return

        if self.path in ("/v1/models", "/models") or "/models" in self.path:
            # Transparent proxy to FreeLLMAPI for models listing
            target_endpoint = f"{FREELLMAPI_URL}/models"
            if "?" in self.path:
                target_endpoint += "?" + self.path.split("?", 1)[1]

            upstream_headers = {
                "Authorization": f"Bearer {FREELLMAPI_API_KEY}",
                "anthropic-version": self.headers.get("anthropic-version", "2023-06-01")
            }
            if self.headers.get("user-agent"):
                upstream_headers["user-agent"] = self.headers.get("user-agent")

            try:
                probe_req = urllib.request.Request(target_endpoint, headers=upstream_headers)
                with urllib.request.urlopen(probe_req, timeout=5.0) as upstream_res:
                    raw_data = upstream_res.read()
                    try:
                        res_json = json.loads(raw_data.decode("utf-8"))
                        if isinstance(res_json, dict) and "data" in res_json:
                            models_list = res_json["data"]
                            known_ids = {m.get("id") for m in models_list if isinstance(m, dict)}
                            for req_id in ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-opus-4-8", "local", "fast", "elite"]:
                                if req_id not in known_ids:
                                    models_list.append({
                                        "type": "model",
                                        "id": req_id,
                                        "display_name": f"{req_id} (Smart Router)",
                                        "created_at": "2026-01-01T00:00:00Z"
                                    })
                            res_json["data"] = models_list
                            raw_data = json.dumps(res_json).encode("utf-8")
                    except Exception as parse_err:
                        logger.debug(f"JSON injection pass-through: {parse_err}")

                    self.send_response(upstream_res.status)
                    for k, v in upstream_res.headers.items():
                        if k.lower() not in ("transfer-encoding", "content-length", "connection", "content-encoding", "etag"):
                            self.send_header(k, v)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(raw_data)))
                    self.end_headers()
                    self.wfile.write(raw_data)
                    self.wfile.flush()
                    return
            except Exception as e:
                logger.error(f"Error proxying models from FreeLLMAPI: {e}")
                self.send_response(502)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
                return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path in ("/v1/messages", "/messages"):
            self.handle_messages()
            return
        elif self.path in ("/v1/chat/completions", "/chat/completions"):
            self.handle_chat_completions()
            return
        else:
            self.send_response(404)
            self.end_headers()

    def handle_messages(self):
        start_time = time.time()
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length)

        try:
            body = json.loads(raw_body.decode("utf-8"))
        except Exception as e:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Invalid JSON body: {e}"}).encode("utf-8"))
            return

        tier, target_url, api_key, mapped_model = classify_tier(body)

        logger.info(f"Incoming /v1/messages -> Routing to {tier} [{mapped_model}] at {target_url}")

        body["model"] = mapped_model
        forward_data = json.dumps(body).encode("utf-8")

        target_endpoint = f"{target_url}/messages"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}" if api_key else ""
        }
        # Copy relevant anthropic headers
        for h in ("anthropic-version", "x-api-key"):
            if h in self.headers:
                headers[h] = self.headers[h]

        stream = bool(body.get("stream", False))

        try:
            req = urllib.request.Request(target_endpoint, data=forward_data, headers=headers)
            with urllib.request.urlopen(req, timeout=120) as upstream_res:
                self.send_response(upstream_res.status)
                for header_key, header_val in upstream_res.headers.items():
                    if header_key.lower() not in ("transfer-encoding", "content-length", "connection"):
                        self.send_header(header_key, header_val)

                if stream:
                    self.send_header("Transfer-Encoding", "chunked")
                    self.end_headers()

                    while True:
                        chunk = upstream_res.read(1024)
                        if not chunk:
                            break
                        # Write chunk in HTTP chunked transfer format
                        self.wfile.write(f"{len(chunk):X}\r\n".encode("ascii"))
                        self.wfile.write(chunk)
                        self.wfile.write(b"\r\n")
                        self.wfile.flush()
                    # End chunked stream
                    self.wfile.write(b"0\r\n\r\n")
                    self.wfile.flush()
                else:
                    response_data = upstream_res.read()
                    self.send_header("Content-Length", str(len(response_data)))
                    self.end_headers()
                    self.wfile.write(response_data)
                    self.wfile.flush()

                elapsed = time.time() - start_time
                logger.info(f"Request completed via {tier} in {elapsed:.2f}s (Stream={stream})")

        except urllib.error.HTTPError as e:
            err_body = e.read()
            logger.error(f"Upstream HTTP error from {tier}: {e.code} - {err_body[:200]}")
            # If local backend failed, attempt automatic fallback to FreeLLMAPI Elite
            if tier == "TIER_2_LOCAL":
                logger.info("Attempting automatic fallback from TIER_2_LOCAL to TIER_3_ELITE on FreeLLMAPI...")
                body["model"] = "claude-3-7-sonnet"
                self.fallback_to_freellmapi(body, stream)
                return

            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(err_body)

        except Exception as e:
            logger.error(f"Connection error to {target_endpoint}: {e}")
            if tier == "TIER_2_LOCAL":
                logger.info("Local backend unreachable. Falling back to TIER_3_ELITE on FreeLLMAPI...")
                body["model"] = "claude-3-7-sonnet"
                self.fallback_to_freellmapi(body, stream)
                return

            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Bad Gateway: {e}"}).encode("utf-8"))

    def fallback_to_freellmapi(self, body: dict, stream: bool):
        """Seamless fallback execution against FreeLLMAPI cloud if local model is busy or offline."""
        try:
            target_endpoint = f"{FREELLMAPI_URL}/messages"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {FREELLMAPI_API_KEY}"
            }
            forward_data = json.dumps(body).encode("utf-8")
            req = urllib.request.Request(target_endpoint, data=forward_data, headers=headers)
            with urllib.request.urlopen(req, timeout=120) as upstream_res:
                self.send_response(upstream_res.status)
                for header_key, header_val in upstream_res.headers.items():
                    if header_key.lower() not in ("transfer-encoding", "content-length", "connection"):
                        self.send_header(header_key, header_val)

                if stream:
                    self.send_header("Transfer-Encoding", "chunked")
                    self.end_headers()
                    while True:
                        chunk = upstream_res.read(1024)
                        if not chunk:
                            break
                        self.wfile.write(f"{len(chunk):X}\r\n".encode("ascii"))
                        self.wfile.write(chunk)
                        self.wfile.write(b"\r\n")
                        self.wfile.flush()
                    self.wfile.write(b"0\r\n\r\n")
                    self.wfile.flush()
                else:
                    response_data = upstream_res.read()
                    self.send_header("Content-Length", str(len(response_data)))
                    self.end_headers()
                    self.wfile.write(response_data)
                    self.wfile.flush()
                logger.info("Fallback to FreeLLMAPI succeeded.")
        except Exception as fb_err:
            logger.error(f"Fallback to FreeLLMAPI also failed: {fb_err}")
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Fallback failed: {fb_err}"}).encode("utf-8"))

    def handle_chat_completions(self):
        """Pass-through for OpenAI chat completions if requested."""
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length)
        target_endpoint = f"{FREELLMAPI_URL}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {FREELLMAPI_API_KEY}"
        }
        try:
            req = urllib.request.Request(target_endpoint, data=raw_body, headers=headers)
            with urllib.request.urlopen(req, timeout=120) as res:
                self.send_response(res.status)
                for k, v in res.headers.items():
                    if k.lower() not in ("transfer-encoding", "content-length", "connection"):
                        self.send_header(k, v)
                data = res.read()
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except Exception as e:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(str(e).encode("utf-8"))


def main():
    server_address = (ROUTER_HOST, ROUTER_PORT)
    httpd = ThreadedHTTPServer(server_address, SmartRouterHandler)
    logger.info(f"=== Claude-Free Smart Hybrid Router started on http://{ROUTER_HOST}:{ROUTER_PORT} ===")
    logger.info(f"Direct Cable Fisso: {FISSO_CABLE_URL}")
    logger.info(f"Tailscale Fisso:    {FISSO_TAILSCALE_URL}")
    logger.info(f"FreeLLMAPI Cloud:   {FREELLMAPI_URL}")
    logger.info("Ready for Claude Code traffic.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down Smart Router.")
        httpd.server_close()


if __name__ == "__main__":
    main()
