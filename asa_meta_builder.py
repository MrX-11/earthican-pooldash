#!/usr/bin/env python3
"""
Build /var/www/earthican/data/asa_motd_meta.json by reading POK-ARK instance docker-compose YAMLs.

Extracts env vars per instance:
- ENABLE_MOTD
- MOTD
- MOTD_DURATION
- (optional) MAP_NAME, SESSION_NAME, ASA_PORT, RCON_PORT, SERVER_VERSION

Consumed by server_monitor.py.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

# CHANGE THIS if your instances live elsewhere:
BASE_DIR = Path("/home/misterx/asa_server")
OUT_PATH = Path("/var/www/earthican/data/asa_motd_meta.json")
INSTANCE_PREFIX = "Instance_"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _extract_env_vars(compose_text: str) -> dict[str, str]:
    env: dict[str, str] = {}
    for m in re.finditer(r'^\s*-\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$', compose_text, re.M):
        k = m.group(1).strip()
        v = m.group(2).strip()
        if (len(v) >= 2) and (v[0] == v[-1]) and (v[0] in ("'", '"')):
            v = v[1:-1]
        env[k] = v
    return env


def _find_compose_file(instance_dir: Path) -> Path | None:
    candidates = sorted(instance_dir.glob("docker-compose*.y*ml"))
    if not candidates:
        return None
    for c in candidates:
        if ".bak" not in c.name:
            return c
    return candidates[0]


def main() -> int:
    if not BASE_DIR.exists():
        raise SystemExit(f"BASE_DIR not found: {BASE_DIR}")

    instances: list[dict[str, str | None]] = []
    for p in sorted(BASE_DIR.iterdir()):
        if not p.is_dir():
            continue
        if not p.name.startswith(INSTANCE_PREFIX):
            continue

        compose_path = _find_compose_file(p)
        if not compose_path:
            continue

        txt = _read_text(compose_path)
        env = _extract_env_vars(txt)

        instances.append({
            "instance_dir": p.name,
            "compose": compose_path.name,
            "instance_name": env.get("INSTANCE_NAME") or env.get("SESSION_NAME") or p.name.replace("Instance_", ""),
            "map_name": env.get("MAP_NAME"),
            "session_name": env.get("SESSION_NAME") or env.get("INSTANCE_NAME"),
            "server_version": env.get("SERVER_VERSION"),
            "enable_motd": env.get("ENABLE_MOTD"),
            "motd": env.get("MOTD"),
            "motd_duration": env.get("MOTD_DURATION"),
            "asa_port": env.get("ASA_PORT") or env.get("GAME_PORT") or env.get("PORT"),
            "rcon_port": env.get("RCON_PORT"),
        })

    payload = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "instances": instances,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, OUT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
