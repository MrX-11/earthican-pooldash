#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict

SNAP_PATH = os.getenv("EARTHICAN_SNAPSHOT_PATH", "/var/www/earthican/data/pool_snapshot.json")
OUT_DIR = Path(os.getenv("EARTHICAN_MINER_HIST_DIR", "/var/www/earthican/data/miner_hist"))

def safe_name(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"[^a-zA-Z0-9._-]+", "_", s)
    return s[:200] if s else "unknown"

def load_snap() -> Dict[str, Any]:
    try:
        with open(SNAP_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def main() -> int:
    snap = load_snap()
    miners = snap.get("miners") or []
    if not isinstance(miners, list) or not miners:
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    now = int(time.time())

    for m in miners:
        try:
            username = str(m.get("username") or "").strip()
            if not username:
                continue

            total_hs = float(m.get("hashrate1m_hs") or 0.0)

            wmap: Dict[str, float] = {}
            workers = m.get("workers_list") or []
            if isinstance(workers, list):
                for w in workers:
                    wname = str(w.get("name") or "").strip()
                    if not wname:
                        continue
                    wmap[wname] = float(w.get("hashrate1m_hs") or 0.0)

            rec = {"t": now, "total_hs": total_hs, "w": wmap}
            fn = OUT_DIR / f"{safe_name(username)}.jsonl"
            with open(fn, "a", encoding="utf-8") as out:
                out.write(json.dumps(rec, separators=(",", ":")) + "\n")
        except Exception:
            continue

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
