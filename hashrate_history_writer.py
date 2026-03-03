#!/usr/bin/env python3
import json, os, time, urllib.request

SNAP_URL = os.getenv("EARTHICAN_SNAPSHOT_URL", "http://127.0.0.1:5050/api/snapshot")
HIST_JSONL = os.getenv("EARTHICAN_HISTORY_JSONL", "/var/www/earthican/data/pool_hashrate_history.jsonl")
RETENTION_DAYS = int(os.getenv("EARTHICAN_HISTORY_RETENTION_DAYS", "30"))
MAX_MB = float(os.getenv("EARTHICAN_HISTORY_MAX_MB", "64"))

def fetch_snapshot():
    req = urllib.request.Request(SNAP_URL, headers={"Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))

def find_pool_hashrate_hs(snap: dict):
    if not isinstance(snap, dict):
        return None

    pool = snap.get("pool")
    if isinstance(pool, dict):
        hr = pool.get("hashrate_hs") or pool.get("hashrate") or {}
        if isinstance(hr, dict):
            for k in ("1m", "hashrate1m", "hashrate_1m"):
                if k in hr:
                    try: return float(hr[k])
                    except: pass
        for k in ("pool_hashrate", "hashrate1m", "hashrate"):
            if k in pool:
                try: return float(pool[k])
                except: pass

    for k in ("pool_hashrate", "hashrate1m", "hashrate"):
        if k in snap:
            try: return float(snap[k])
            except: pass

    return None

def append_point(hs: float):
    os.makedirs(os.path.dirname(HIST_JSONL), exist_ok=True)
    rec = {"t": int(time.time()), "hs_1m": float(hs)}
    with open(HIST_JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, separators=(",", ":")) + "\n")

def prune():
    if not os.path.exists(HIST_JSONL):
        return
    now = int(time.time())
    cutoff = now - int(RETENTION_DAYS * 86400)

    tmp = HIST_JSONL + ".tmp"
    with open(HIST_JSONL, "r", encoding="utf-8", errors="replace") as fin, open(tmp, "w", encoding="utf-8") as fout:
        for ln in fin:
            ln = ln.strip()
            if not ln:
                continue
            try:
                obj = json.loads(ln)
                t = int(obj.get("t", 0) or 0)
            except Exception:
                continue
            if t >= cutoff:
                fout.write(ln + "\n")
    os.replace(tmp, HIST_JSONL)

    cap = int(MAX_MB * 1024 * 1024)
    st = os.stat(HIST_JSONL)
    if cap > 0 and st.st_size > cap:
        with open(HIST_JSONL, "rb") as f:
            f.seek(max(0, st.st_size - cap))
            chunk = f.read()
        nl = chunk.find(b"\n")
        if nl != -1:
            chunk = chunk[nl+1:]
        with open(tmp, "wb") as f:
            f.write(chunk)
        os.replace(tmp, HIST_JSONL)

def main():
    snap = fetch_snapshot()
    hs = find_pool_hashrate_hs(snap)
    if hs is None:
        return
    append_point(hs)
    if int(time.time()) % 60 == 0:
        prune()

if __name__ == "__main__":
    main()
