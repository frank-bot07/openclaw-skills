#!/usr/bin/env python3
"""
Model Switchboard v3 — Backend Server
Pure Python stdlib. No external dependencies.
Manages OpenClaw model config, cron job assignments, and API keys.

Security: API keys are NEVER returned to the frontend in plaintext.
All key responses use masked form: sk-...xxxx (last 4 chars only).
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

# ─── Paths ───────────────────────────────────────────────────────────────────
HOME = Path.home()
OPENCLAW_CONFIG = HOME / ".openclaw" / "openclaw.json"
CRON_JOBS_FILE = HOME / ".openclaw" / "cron" / "jobs.json"
WORKSPACE_ENV = HOME / ".openclaw" / "workspace" / ".env"
BACKUP_DIR = HOME / ".openclaw" / "switchboard-backups"
AUTH_PROFILES = HOME / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
OPENCLAW_BIN = HOME / ".npm-global" / "lib" / "node_modules" / "openclaw" / "dist" / "index.js"
MAX_BACKUPS = 10
PORT = 7878

# ─── Provider → env key mapping ──────────────────────────────────────────────
PROVIDER_ENV_MAP = {
    "anthropic":    ["ANTHROPIC_API_KEY"],
    "openai":       ["OPENAI_API_KEY"],
    "google":       ["GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_GEMINI_API_KEY"],
    "xai":          ["XAI_API_KEY"],
    "moonshot":     ["MOONSHOT_API_KEY"],
    "minimax":      ["MINIMAX_API_KEY"],
    "openai-codex": ["OPENAI_API_KEY"],
    "mistral":      ["MISTRAL_API_KEY"],
    "cohere":       ["COHERE_API_KEY"],
    "groq":         ["GROQ_API_KEY"],
}

def provider_from_model(model_id: str) -> str:
    """Extract provider from model ID like 'anthropic/claude-opus-4-6'."""
    if "/" in model_id:
        return model_id.split("/")[0]
    return "unknown"

def mask_key(key: str) -> str:
    """Mask API key: sk-...xxxx (last 4 only)."""
    if not key or len(key) < 8:
        return "****"
    prefix = key[:3] if key.startswith("sk-") else key[:2]
    return f"{prefix}-...{key[-4:]}"

# ─── Config I/O ──────────────────────────────────────────────────────────────

def read_config() -> Dict[str, Any]:
    """Read openclaw.json safely."""
    try:
        with open(OPENCLAW_CONFIG) as f:
            return json.load(f)
    except Exception as e:
        raise RuntimeError(f"Cannot read config: {e}")

def write_config(cfg: Dict[str, Any]) -> None:
    """Write openclaw.json atomically."""
    tmp = str(OPENCLAW_CONFIG) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, str(OPENCLAW_CONFIG))

def read_cron_jobs() -> List[Dict[str, Any]]:
    """Read cron jobs from jobs.json."""
    try:
        with open(CRON_JOBS_FILE) as f:
            data = json.load(f)
        return data.get("jobs", [])
    except Exception as e:
        raise RuntimeError(f"Cannot read cron jobs: {e}")

def write_cron_jobs(jobs: List[Dict[str, Any]]) -> None:
    """Write cron jobs atomically."""
    try:
        with open(CRON_JOBS_FILE) as f:
            data = json.load(f)
    except Exception:
        data = {"version": 1}
    data["jobs"] = jobs
    tmp = str(CRON_JOBS_FILE) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, str(CRON_JOBS_FILE))

# ─── Backup ───────────────────────────────────────────────────────────────────

def create_backup(label: str = "") -> str:
    """Create a rolling backup of openclaw.json and cron/jobs.json."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"{ts}_{label}" if label else ts
    backup_path = BACKUP_DIR / name
    backup_path.mkdir()

    shutil.copy2(str(OPENCLAW_CONFIG), str(backup_path / "openclaw.json"))
    if CRON_JOBS_FILE.exists():
        shutil.copy2(str(CRON_JOBS_FILE), str(backup_path / "jobs.json"))

    # Rolling: keep only last MAX_BACKUPS
    backups = sorted(BACKUP_DIR.iterdir(), key=lambda p: p.stat().st_mtime)
    while len(backups) > MAX_BACKUPS:
        oldest = backups.pop(0)
        if oldest.is_dir():
            shutil.rmtree(str(oldest))
        else:
            oldest.unlink()

    return str(backup_path)

def list_backups() -> List[Dict[str, Any]]:
    """List available backups."""
    if not BACKUP_DIR.exists():
        return []
    result = []
    for p in sorted(BACKUP_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.is_dir():
            files = [f.name for f in p.iterdir()]
            result.append({
                "name": p.name,
                "timestamp": p.stat().st_mtime,
                "files": files,
                "path": str(p),
            })
    return result

def restore_backup(backup_name: str) -> bool:
    """Restore a backup."""
    backup_path = BACKUP_DIR / backup_name
    if not backup_path.exists():
        return False
    # Safety: backup current state first
    create_backup("pre-restore")

    cfg_file = backup_path / "openclaw.json"
    cron_file = backup_path / "jobs.json"

    if cfg_file.exists():
        shutil.copy2(str(cfg_file), str(OPENCLAW_CONFIG))
    if cron_file.exists():
        shutil.copy2(str(cron_file), str(CRON_JOBS_FILE))
    return True

# ─── Key management ──────────────────────────────────────────────────────────

def get_env_keys() -> Dict[str, str]:
    """Get API keys from config env.vars (masked)."""
    cfg = read_config()
    vars_ = cfg.get("env", {}).get("vars", {})
    return {k: mask_key(v) for k, v in vars_.items()}

def set_env_key(key_name: str, key_value: str) -> None:
    """Set an API key in config and backup to .env."""
    cfg = read_config()
    if "env" not in cfg:
        cfg["env"] = {}
    if "vars" not in cfg["env"]:
        cfg["env"]["vars"] = {}
    cfg["env"]["vars"][key_name] = key_value
    write_config(cfg)

    # Also update .env file (upsert)
    _update_env_file(key_name, key_value)

def _update_env_file(key_name: str, key_value: str) -> None:
    """Upsert a key in workspace .env file."""
    lines = []
    updated = False
    if WORKSPACE_ENV.exists():
        with open(WORKSPACE_ENV) as f:
            for line in f:
                if line.strip().startswith(f"{key_name}="):
                    lines.append(f"{key_name}={key_value}\n")
                    updated = True
                else:
                    lines.append(line)
    if not updated:
        lines.append(f"{key_name}={key_value}\n")
    with open(WORKSPACE_ENV, "w") as f:
        f.writelines(lines)
    os.chmod(str(WORKSPACE_ENV), 0o600)

# ─── Model management ────────────────────────────────────────────────────────

def get_allowed_models() -> Dict[str, Any]:
    """Get allowed models from config."""
    cfg = read_config()
    return cfg.get("agents", {}).get("defaults", {}).get("models", {})

def get_gateway_models() -> Dict[str, Any]:
    """Get primary/fallback/imageModel config."""
    cfg = read_config()
    defaults = cfg.get("agents", {}).get("defaults", {})
    return {
        "primary": defaults.get("model", {}).get("primary", ""),
        "fallbacks": defaults.get("model", {}).get("fallbacks", []),
        "imagePrimary": defaults.get("imageModel", {}).get("primary", ""),
        "imageFallbacks": defaults.get("imageModel", {}).get("fallbacks", []),
    }

def get_auth_profiles() -> Dict[str, str]:
    """Get providers that have auth profiles (setup-token / OAuth stored by OpenClaw)."""
    profiles = {}
    try:
        if AUTH_PROFILES.exists():
            with open(AUTH_PROFILES) as f:
                data = json.load(f)
            for profile_id in data.get("profiles", {}):
                # Profile IDs like 'anthropic:frank', 'openai:chad', 'google:chad'
                if ":" in profile_id:
                    provider = profile_id.split(":")[0]
                    profiles[provider] = profile_id
    except Exception:
        pass
    return profiles

def get_key_status() -> Dict[str, Dict[str, Any]]:
    """Get provider key status."""
    cfg = read_config()
    env_vars = cfg.get("env", {}).get("vars", {})
    # Merge with process environment (config vars take priority for display)
    merged = {**os.environ, **env_vars}
    auth_profiles = get_auth_profiles()

    result = {}
    for provider, env_keys in PROVIDER_ENV_MAP.items():
        found_key = None
        found_env = None
        for ek in env_keys:
            if merged.get(ek):
                found_key = merged[ek]
                found_env = ek
                break

        # Check auth profiles (setup-token based auth from OpenClaw)
        if not found_key and provider in auth_profiles:
            found_key = "auth-profile"
            found_env = f"profile:{auth_profiles[provider]}"

        # Special case: openai-codex OAuth
        if provider == "openai-codex":
            codex_auth = HOME / ".openclaw" / "auth" / "openai-codex.json"
            if codex_auth.exists():
                found_key = "oauth"
                found_env = "OAuth"

        result[provider] = {
            "configured": bool(found_key),
            "envKey": found_env,
            "masked": mask_key(found_key) if found_key and found_key not in ("setup-token", "auth-profile", "oauth") else (found_key or None),
            "via": "env" if (found_env and not found_env.startswith("profile:")) else "profile",
        }

    return result

def add_model(model_id: str, alias: str = "") -> Dict[str, Any]:
    """Add a model to allowed models list."""
    provider = provider_from_model(model_id)
    key_status = get_key_status()
    pstatus = key_status.get(provider, {})

    if not pstatus.get("configured"):
        return {"ok": False, "error": f"No API key configured for provider '{provider}'. Add a key first."}

    cfg = read_config()
    models = cfg.get("agents", {}).get("defaults", {}).get("models", {})

    if model_id in models:
        return {"ok": False, "error": f"Model '{model_id}' already in allowed list."}

    entry: Dict[str, Any] = {}
    if alias:
        entry["alias"] = alias
    models[model_id] = entry

    cfg["agents"]["defaults"]["models"] = models
    create_backup("pre-add-model")
    write_config(cfg)
    return {"ok": True, "model": model_id}

def remove_model(model_id: str, force: bool = False) -> Dict[str, Any]:
    """Remove model — warns about dependent cron jobs."""
    jobs = read_cron_jobs()
    deps = [j for j in jobs if j.get("payload", {}).get("model") == model_id]

    cfg = read_config()
    models = cfg.get("agents", {}).get("defaults", {}).get("models", {})
    gw = get_gateway_models()

    gateway_roles = []
    if gw["primary"] == model_id:
        gateway_roles.append("primary")
    if model_id in gw["fallbacks"]:
        gateway_roles.append("fallback")
    if gw["imagePrimary"] == model_id:
        gateway_roles.append("image-primary")
    if model_id in gw["imageFallbacks"]:
        gateway_roles.append("image-fallback")

    if (deps or gateway_roles) and not force:
        return {
            "ok": False,
            "requires_force": True,
            "error": f"Model '{model_id}' has {len(deps)} cron job(s) and roles: {gateway_roles}. Use force=true to remove anyway.",
            "deps": len(deps),
            "gateway_roles": gateway_roles,
            "dep_names": [j["name"] for j in deps],
        }

    if model_id not in models:
        return {"ok": False, "error": f"Model '{model_id}' not in allowed list."}

    create_backup("pre-remove-model")
    del models[model_id]
    cfg["agents"]["defaults"]["models"] = models
    write_config(cfg)
    return {"ok": True, "model": model_id, "deps_affected": len(deps), "gateway_roles": gateway_roles}

# ─── Cron management ─────────────────────────────────────────────────────────

def list_cron_jobs_enriched() -> List[Dict[str, Any]]:
    """Return enriched cron job list with validation flags."""
    jobs = read_cron_jobs()
    allowed = get_allowed_models()
    result = []
    for j in jobs:
        model = j.get("payload", {}).get("model") or "default"
        schedule = j.get("schedule", {})
        state = j.get("state", {})

        is_flagged = False
        if model != "default" and model not in allowed:
            is_flagged = True

        result.append({
            "id": j["id"],
            "name": j["name"],
            "enabled": j.get("enabled", True),
            "model": model,
            "schedule": f"{schedule.get('kind','')} {schedule.get('expr','')} @ {schedule.get('tz','')}",
            "scheduleExpr": schedule.get("expr", ""),
            "sessionTarget": j.get("sessionTarget", ""),
            "lastStatus": state.get("lastStatus", "unknown"),
            "lastRunAgo": _format_ago(state.get("lastRunAtMs")),
            "nextRunIn": _format_in(state.get("nextRunAtMs")),
            "consecutiveErrors": state.get("consecutiveErrors", 0),
            "flagged": is_flagged,
        })
    return result

def _format_ago(ts_ms: Optional[int]) -> str:
    if not ts_ms:
        return "never"
    delta = time.time() - ts_ms / 1000
    if delta < 60:
        return f"{int(delta)}s ago"
    if delta < 3600:
        return f"{int(delta/60)}m ago"
    if delta < 86400:
        return f"{int(delta/3600)}h ago"
    return f"{int(delta/86400)}d ago"

def _format_in(ts_ms: Optional[int]) -> str:
    if not ts_ms:
        return "—"
    delta = ts_ms / 1000 - time.time()
    if delta < 0:
        return "overdue"
    if delta < 60:
        return f"in {int(delta)}s"
    if delta < 3600:
        return f"in {int(delta/60)}m"
    if delta < 86400:
        return f"in {int(delta/3600)}h"
    return f"in {int(delta/86400)}d"

def update_cron_model(job_id: str, new_model: str) -> Dict[str, Any]:
    """Update a single cron job's model."""
    if new_model != "default":
        allowed = get_allowed_models()
        if new_model not in allowed:
            return {"ok": False, "error": f"Model '{new_model}' is not in the allowed models list. Add it first."}

    jobs = read_cron_jobs()
    for j in jobs:
        if j["id"] == job_id:
            create_backup("pre-cron-update")
            if new_model == "default":
                j["payload"].pop("model", None)
            else:
                j["payload"]["model"] = new_model
            j["updatedAtMs"] = int(time.time() * 1000)
            write_cron_jobs(jobs)
            return {"ok": True, "id": job_id, "model": new_model}
    return {"ok": False, "error": f"Job '{job_id}' not found."}

def bulk_update_cron_model(from_model: str, to_model: str) -> Dict[str, Any]:
    """Reassign all cron jobs from one model to another."""
    if to_model != "default":
        allowed = get_allowed_models()
        if to_model not in allowed:
            return {"ok": False, "error": f"Target model '{to_model}' not in allowed list."}

    jobs = read_cron_jobs()
    updated = []
    for j in jobs:
        cur = j.get("payload", {}).get("model") or "default"
        if cur == from_model:
            if to_model == "default":
                j["payload"].pop("model", None)
            else:
                j["payload"]["model"] = to_model
            j["updatedAtMs"] = int(time.time() * 1000)
            updated.append(j["id"])

    if updated:
        create_backup("pre-bulk-update")
        write_cron_jobs(jobs)
    return {"ok": True, "updated": len(updated), "ids": updated}

# ─── Validation ──────────────────────────────────────────────────────────────

def validate_config() -> Dict[str, Any]:
    """Validate config: check all model refs have valid provider keys."""
    issues = []
    warnings = []

    cfg = read_config()
    allowed = get_allowed_models()
    key_status = get_key_status()
    gw = get_gateway_models()
    jobs = read_cron_jobs()

    # Check each allowed model's provider has a key
    for model_id in allowed:
        provider = provider_from_model(model_id)
        pstatus = key_status.get(provider, {})
        if not pstatus.get("configured"):
            issues.append(f"Model '{model_id}': provider '{provider}' has no API key configured.")

    # Check gateway primary
    if gw["primary"] and gw["primary"] not in allowed:
        issues.append(f"Gateway primary model '{gw['primary']}' is NOT in allowed list.")

    # Check gateway fallbacks
    for fb in gw["fallbacks"]:
        if fb not in allowed:
            issues.append(f"Gateway fallback '{fb}' is NOT in allowed list.")

    # Check cron jobs
    for j in jobs:
        model = j.get("payload", {}).get("model")
        if model and model not in allowed:
            warnings.append(f"Cron '{j['name']}': uses model '{model}' not in allowed list.")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "summary": f"{len(issues)} issue(s), {len(warnings)} warning(s)",
    }

# ─── Model health info ───────────────────────────────────────────────────────

def get_model_health() -> List[Dict[str, Any]]:
    """Per-model health: provider, key status, cron deps, gateway roles."""
    allowed = get_allowed_models()
    key_status = get_key_status()
    gw = get_gateway_models()
    jobs = read_cron_jobs()

    result = []
    for model_id, meta in allowed.items():
        provider = provider_from_model(model_id)
        pstatus = key_status.get(provider, {})

        dep_count = sum(
            1 for j in jobs
            if (j.get("payload", {}).get("model") or "default") == model_id
        )

        gateway_roles = []
        if gw["primary"] == model_id:
            gateway_roles.append("primary")
        if model_id in gw["fallbacks"]:
            gateway_roles.append("fallback")
        if gw["imagePrimary"] == model_id:
            gateway_roles.append("image-primary")
        if model_id in gw["imageFallbacks"]:
            gateway_roles.append("image-fallback")

        result.append({
            "modelId": model_id,
            "alias": meta.get("alias", ""),
            "provider": provider,
            "keyConfigured": pstatus.get("configured", False),
            "keyEnv": pstatus.get("envKey", ""),
            "cronDeps": dep_count,
            "gatewayRoles": gateway_roles,
            "canRemove": dep_count == 0 and len(gateway_roles) == 0,
        })

    return result

# ─── HTTP Handler ─────────────────────────────────────────────────────────────

def json_response(handler, data: Any, status: int = 200) -> None:
    body = json.dumps(data).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)

def html_response(handler, html: str) -> None:
    body = html.encode()
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)

UI_FILE = Path(__file__).parent.parent / "ui" / "index.html"

class SwitchboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Quiet logging
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {self.command} {self.path} => {args[0] if args else ''}")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        try:
            if path == "/" or path == "/index.html":
                if UI_FILE.exists():
                    with open(UI_FILE) as f:
                        html_response(self, f.read())
                else:
                    json_response(self, {"error": "UI not found"}, 404)

            elif path == "/api/health":
                json_response(self, {
                    "ok": True,
                    "version": "v3",
                    "timestamp": datetime.now().isoformat(),
                    "config": str(OPENCLAW_CONFIG),
                })

            elif path == "/api/config":
                cfg = read_config()
                defaults = cfg.get("agents", {}).get("defaults", {})
                result = {
                    "primary": defaults.get("model", {}).get("primary", ""),
                    "fallbacks": defaults.get("model", {}).get("fallbacks", []),
                    "imagePrimary": defaults.get("imageModel", {}).get("primary", ""),
                    "imageFallbacks": defaults.get("imageModel", {}).get("fallbacks", []),
                    "models": get_allowed_models(),
                    "keyStatus": get_key_status(),
                    "envKeys": get_env_keys(),
                }
                json_response(self, result)

            elif path == "/api/cron":
                json_response(self, {"jobs": list_cron_jobs_enriched()})

            elif path == "/api/models":
                json_response(self, {
                    "models": get_model_health(),
                    "keyStatus": get_key_status(),
                })

            elif path == "/api/backups":
                json_response(self, {"backups": list_backups()})

            elif path == "/api/validate":
                json_response(self, validate_config())

            else:
                json_response(self, {"error": "Not found"}, 404)

        except Exception as e:
            json_response(self, {"error": str(e), "trace": traceback.format_exc()}, 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # Read body
        length = int(self.headers.get("Content-Length", 0))
        body = {}
        if length:
            try:
                body = json.loads(self.rfile.read(length))
            except Exception:
                json_response(self, {"error": "Invalid JSON body"}, 400)
                return

        try:
            if path == "/api/config/key":
                # POST { keyName, keyValue }
                key_name = body.get("keyName", "").strip()
                key_value = body.get("keyValue", "").strip()
                if not key_name or not key_value:
                    json_response(self, {"error": "keyName and keyValue required"}, 400)
                    return
                if not re.match(r'^[A-Z][A-Z0-9_]*$', key_name):
                    json_response(self, {"error": "keyName must be uppercase with underscores"}, 400)
                    return
                create_backup("pre-key-update")
                set_env_key(key_name, key_value)
                json_response(self, {"ok": True, "keyName": key_name, "masked": mask_key(key_value)})

            elif path == "/api/config/gateway":
                # POST { primary?, fallbacks?, imagePrimary?, imageFallbacks? }
                create_backup("pre-gateway-update")
                cfg = read_config()
                defaults = cfg["agents"]["defaults"]
                if "primary" in body:
                    defaults.setdefault("model", {})["primary"] = body["primary"]
                if "fallbacks" in body:
                    defaults.setdefault("model", {})["fallbacks"] = body["fallbacks"]
                if "imagePrimary" in body:
                    defaults.setdefault("imageModel", {})["primary"] = body["imagePrimary"]
                if "imageFallbacks" in body:
                    defaults.setdefault("imageModel", {})["fallbacks"] = body["imageFallbacks"]
                write_config(cfg)
                json_response(self, {"ok": True})

            elif path == "/api/cron/model":
                # POST { jobId, model }
                job_id = body.get("jobId", "").strip()
                model = body.get("model", "").strip()
                if not job_id or not model:
                    json_response(self, {"error": "jobId and model required"}, 400)
                    return
                result = update_cron_model(job_id, model)
                json_response(self, result, 200 if result["ok"] else 400)

            elif path == "/api/cron/bulk-model":
                # POST { fromModel, toModel }
                from_m = body.get("fromModel", "").strip()
                to_m = body.get("toModel", "").strip()
                if not from_m or not to_m:
                    json_response(self, {"error": "fromModel and toModel required"}, 400)
                    return
                result = bulk_update_cron_model(from_m, to_m)
                json_response(self, result)

            elif path == "/api/models/add":
                # POST { modelId, alias? }
                model_id = body.get("modelId", "").strip()
                alias = body.get("alias", "").strip()
                if not model_id:
                    json_response(self, {"error": "modelId required"}, 400)
                    return
                if not re.match(r'^[a-z0-9_\-\.]+/[a-z0-9_\-\.]+$', model_id, re.IGNORECASE):
                    json_response(self, {"error": "modelId must be 'provider/model-name' format"}, 400)
                    return
                result = add_model(model_id, alias)
                json_response(self, result, 200 if result["ok"] else 400)

            elif path == "/api/models/remove":
                # POST { modelId, force? }
                model_id = body.get("modelId", "").strip()
                force = body.get("force", False)
                if not model_id:
                    json_response(self, {"error": "modelId required"}, 400)
                    return
                result = remove_model(model_id, force)
                json_response(self, result, 200 if result["ok"] else 400)

            elif path == "/api/backup/restore":
                # POST { name }
                name = body.get("name", "").strip()
                if not name or "/" in name or ".." in name:
                    json_response(self, {"error": "Invalid backup name"}, 400)
                    return
                ok = restore_backup(name)
                json_response(self, {"ok": ok})

            elif path == "/api/backup/create":
                backup_path = create_backup("manual")
                json_response(self, {"ok": True, "path": backup_path})

            else:
                json_response(self, {"error": "Not found"}, 404)

        except Exception as e:
            json_response(self, {"error": str(e), "trace": traceback.format_exc()}, 500)


def main():
    server = HTTPServer(("localhost", PORT), SwitchboardHandler)
    print(f"╔══════════════════════════════════════════════════╗")
    print(f"║  Model Switchboard v3 — http://localhost:{PORT}  ║")
    print(f"╚══════════════════════════════════════════════════╝")
    print(f"Config: {OPENCLAW_CONFIG}")
    print(f"Cron:   {CRON_JOBS_FILE}")
    print(f"UI:     {UI_FILE}")
    print("Ready. Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutdown.")


if __name__ == "__main__":
    main()
