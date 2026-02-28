from __future__ import annotations

import json
import os
import time
from typing import Any, Dict

from asa_rcon import query_asa_rcon

# ---- Config ----
MINECRAFT_HOST = "192.168.1.50"
MINECRAFT_PORT = 25565

ASA_META_PATH = "/var/www/earthican/data/asa_motd_meta.json"


def _safe_load_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _norm_token(s: Any) -> str:
    """
    Normalize names so we can map:
      "TheIsland" / "TheIsland_WP" / "misterXworld_TheIsland" -> "theisland"
      "Astraeos" / "Astraeos_WP" / "misterXworld_Astraeos"     -> "astraeos"
    """
    if not s:
        return ""
    s = str(s).strip().strip('"').strip("'")
    s = s.replace("_WP", "")
    # take suffix after last underscore for "misterXworld_Astraeos"
    if "_" in s:
        s = s.split("_")[-1]
    # remove spaces/punct for matching
    s = "".join(ch for ch in s.lower() if ch.isalnum())
    return s


def _load_asa_meta_map() -> Dict[str, Dict[str, Any]]:
    meta = _safe_load_json(ASA_META_PATH)
    out: Dict[str, Dict[str, Any]] = {}
    for inst in meta.get("instances", []):
        keys = [
            _norm_token(inst.get("instance_name")),
            _norm_token(inst.get("map_name")),
            _norm_token(inst.get("session_name")),
        ]
        for k in keys:
            if k:
                out[k] = inst
    return out


def query_minecraft(host: str = MINECRAFT_HOST, port: int = MINECRAFT_PORT, timeout: float = 1.5) -> Dict[str, Any]:
    """
    Minecraft Java status ping via mcstatus.
    Returns {online, players_online, players_max, version, motd, latency_ms, ...}
    """
    out: Dict[str, Any] = {"online": False, "host": host, "port": port}
    try:
        from mcstatus import JavaServer
        server = JavaServer.lookup(f"{host}:{port}", timeout=timeout)
        status = server.status()
        out.update({
            "online": True,
            "players_online": int(getattr(status.players, "online", 0) or 0),
            "players_max": int(getattr(status.players, "max", 0) or 0),
            "version": getattr(status.version, "name", None),
            "motd": getattr(getattr(status, "description", None), "to_plain", lambda: getattr(status, "description", None))(),
            "latency_ms": float(getattr(status, "latency", 0.0) or 0.0),
        })
    except Exception as e:
        out["error"] = str(e)
    return out


def query_asa(timeout: float = 2.0) -> Dict[str, Any]:
    """
    RCON-based ASA status (returns cluster summary + per-instance list).
    Augments each instance with MOTD/session_name from asa_motd_meta.json if present.
    """
    result: Dict[str, Any] = query_asa_rcon(timeout=timeout) or {}
    instances = result.get("instances") or []

    meta_map = _load_asa_meta_map()
    for row in instances:
        key = _norm_token(row.get("name")) or _norm_token(row.get("map")) or _norm_token(row.get("server_name"))
        meta = meta_map.get(key)
        if not meta:
            continue

        # Attach friendly/session naming
        row["session_name"] = meta.get("session_name") or meta.get("instance_name")

        # Attach MOTD only when enabled
        if str(meta.get("enable_motd", "")).upper() == "TRUE":
            row["motd"] = meta.get("motd")
            row["motd_duration"] = meta.get("motd_duration")
        else:
            row["motd"] = None

        # Optional: ports from YAML (useful for connect display)
        row["asa_port"] = meta.get("asa_port")
        row["rcon_port"] = meta.get("rcon_port")
        row["version"] = meta.get("server_version")

    return result
