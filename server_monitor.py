from __future__ import annotations

import time
from typing import Any, Dict, List
from asa_rcon import query_asa_rcon

# ---- Config (local machine) ----
MINECRAFT_HOST = "192.168.1.50"
MINECRAFT_PORT = 25565

ASA_HOST = "127.0.0.1"
ASA_INSTANCES: List[Dict[str, Any]] = [
    {"name": "Island",      "query_port": 7779},
    {"name": "Scorched",    "query_port": 7789},
    {"name": "The Center",  "query_port": 7799},
    {"name": "Aberration",  "query_port": 7809},
    {"name": "Extinction",  "query_port": 7819},
    {"name": "Astraeos",    "query_port": 7829},
    {"name": "Ragnarok",    "query_port": 7839},
    {"name": "Valguero",    "query_port": 7849},
    {"name": "Lost Colony", "query_port": 7859},
]


def query_minecraft(host: str = MINECRAFT_HOST, port: int = MINECRAFT_PORT, timeout: float = 1.5) -> Dict[str, Any]:
    """
    Minecraft Java status ping via mcstatus.
    Returns {online, players_online, players_max, version, latency_ms, ...}
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
            "latency_ms": float(getattr(status, "latency", 0.0) or 0.0),
        })
    except Exception as e:
        out["error"] = str(e)
    return out


def query_asa(host: str = ASA_HOST, instances: List[Dict[str, Any]] = ASA_INSTANCES, timeout: float = 1.5) -> Dict[str, Any]:
    """
    ARK: Survival Ascended query via Valve/Steam A2S on per-instance query ports.
    Returns a cluster summary plus per-instance info rows.
    """
    result: Dict[str, Any] = {
        "host": host,
        "instances": [],
        "online_instances": 0,
        "total_instances": len(instances),
        "total_players": 0,
    }

    try:
        import a2s
    except Exception as e:
        result["error"] = f"a2s import failed: {e}"
        return result

    for inst in instances:
        name = str(inst.get("name", "unknown"))
        port = int(inst.get("query_port", 0))
        row: Dict[str, Any] = {"name": name, "query_port": port, "online": False}

        try:
            start = time.time()
            info = a2s.info((host, port), timeout=timeout)
            latency_ms = (time.time() - start) * 1000.0

            players = int(getattr(info, "player_count", 0) or 0)
            max_players = int(getattr(info, "max_players", 0) or 0)

            row.update({
                "online": True,
                "server_name": getattr(info, "server_name", None),
                "map": getattr(info, "map_name", None),
                "players_online": players,
                "players_max": max_players,
                "latency_ms": round(latency_ms, 1),
            })

            result["online_instances"] += 1
            result["total_players"] += players

        except Exception as e:
            row["error"] = str(e)

        result["instances"].append(row)

    return result


def query_asa(host: str = 'unused', instances=None, timeout: float = 2.0):
    # RCON-based ASA status from Nebuchadnezzar (TCP)
    return query_asa_rcon(timeout=timeout)
