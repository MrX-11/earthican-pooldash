from __future__ import annotations

import os
import time
from typing import Any, Dict, List

from rcon.source import Client

ASA_RCON_HOST = os.environ.get("ASA_RCON_HOST", "192.168.1.50")
ASA_RCON_PASSWORD = os.environ.get("ASA_RCON_PASSWORD", "")

# Based on your docker ps mapping on Nebuchadnezzar
ASA_INSTANCES: List[Dict[str, Any]] = [
    {"name": "TheIsland",      "rcon_port": 27020, "game_port": 7777},
    {"name": "ScorchedEarth",  "rcon_port": 27030, "game_port": 7787},
    {"name": "Aberration",     "rcon_port": 27040, "game_port": 7797},
    {"name": "Extinction",     "rcon_port": 27050, "game_port": 7807},
    {"name": "TheCenter",      "rcon_port": 27060, "game_port": 7817},
    {"name": "Astraeos",       "rcon_port": 27070, "game_port": 7827},
    {"name": "Ragnarok",       "rcon_port": 27080, "game_port": 7837},
    {"name": "Valguero",       "rcon_port": 27090, "game_port": 7847},
    {"name": "LostColony",     "rcon_port": 27100, "game_port": 7857},
]

def _rcon(port: int, cmd: str, timeout: float = 2.0) -> str:
    if not ASA_RCON_PASSWORD:
        raise RuntimeError("ASA_RCON_PASSWORD env var not set on berrynode")
    with Client(ASA_RCON_HOST, port, passwd=ASA_RCON_PASSWORD, timeout=timeout) as c:
        return c.run(cmd)

def _player_count_from_listplayers(resp: str) -> int:
    """
    Counts lines like: '0. PlayerName, <id>'
    Handles blank lines and no-player messages.
    """
    if not resp:
        return 0
    import re
    return len(re.findall(r"(?m)^\s*\d+\.\s+", resp))

def query_asa_rcon(timeout: float = 2.0) -> Dict[str, Any]:
    instances_out: List[Dict[str, Any]] = []
    online_instances = 0
    total_players = 0

    for inst in ASA_INSTANCES:
        row: Dict[str, Any] = {
            "name": inst["name"],
            "host": ASA_RCON_HOST,
            "game_port": inst["game_port"],
            "rcon_port": inst["rcon_port"],
            "online": False,
        }

        try:
            t0 = time.time()
            # Start with ListPlayers; if it works, server is online and we can count.
            resp = _rcon(inst["rcon_port"], "ListPlayers", timeout=timeout)
            row["online"] = True
            row["latency_ms"] = round((time.time() - t0) * 1000.0, 1)
            row["players_online"] = _player_count_from_listplayers(resp)
            row["raw_preview"] = (resp or "")[:600]  # preview for debugging UI/logs

            total_players += int(row["players_online"] or 0)
            online_instances += 1

        except Exception as e:
            row["error"] = str(e)

        instances_out.append(row)

    return {
        "host": ASA_RCON_HOST,
        "instances": instances_out,
        "online_instances": online_instances,
        "total_instances": len(instances_out),
        "total_players": total_players,
    }
