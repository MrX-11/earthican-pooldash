#!/usr/bin/env python3
import json, os, re, time, tempfile
from datetime import datetime, timezone

CKPOOL_LOG = "/home/misterx/ckpool/logs/ckpool.log"
OUT_JSON   = "/var/www/earthican/data/pool_snapshot.json"

POOL_RE   = re.compile(r'^\[[^\]]+\]\s+Pool:(\{.*\})\s*$')
WORKER_RE = re.compile(r'^\[[^\]]+\]\s+Worker\s+(\S+)\s+(\{.*\})\s*$')
USER_RE   = re.compile(r'^\[[^\]]+\]\s+User\s+([^:]+):(\{.*\})\s*$')

UNIT = {"":1.0,"K":1e3,"M":1e6,"G":1e9,"T":1e12,"P":1e15,"E":1e18}

def parse_rate_to_ths(v):
    # Returns TH/s float
    if v is None:
        return None
    if isinstance(v, (int, float)):
        # assume H/s
        return float(v) / 1e12
    s = str(v).strip().strip('"')
    if s == "" or s == "0":
        return 0.0
    m = re.match(r'^([0-9]+(?:\.[0-9]+)?)\s*([KMGTPE]?)$', s, re.I)
    if not m:
        return None
    num = float(m.group(1))
    suf = m.group(2).upper()
    hs = num * UNIT.get(suf, 1.0)
    return hs / 1e12

def parse_rate_to_ghs(v):
    # Returns GH/s float (more convenient for small miners)
    ths = parse_rate_to_ths(v)
    if ths is None:
        # might already be numeric H/s in worker json
        try:
            if isinstance(v, (int, float)):
                return float(v) / 1e9
        except Exception:
            pass
        return None
    return ths * 1000.0

def tail_lines(path, max_lines=15000):
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        block = 8192
        data = b""
        while size > 0 and data.count(b"\n") <= max_lines:
            step = block if size >= block else size
            size -= step
            f.seek(size)
            data = f.read(step) + data
        lines = data.splitlines()[-max_lines:]
        return [ln.decode("utf-8", errors="replace") for ln in lines]

def atomic_write_json(path, obj):
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".snap_", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, separators=(",", ":"), ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except Exception:
            pass

def build_snapshot():
    lines = tail_lines(CKPOOL_LOG)

    runtime = None
    lastupdate = None
    counts = {}
    hashrates = {}
    shares = {}

    users = {}    # username/address -> dict
    workers = {}  # fullworkername -> dict

    # Walk from end to start; collect latest per worker/user, and latest pool blocks
    for ln in reversed(lines):
        m = POOL_RE.match(ln)
        if m:
            try:
                payload = json.loads(m.group(1))
            except Exception:
                continue

            if "runtime" in payload and "lastupdate" in payload and runtime is None:
                runtime = int(payload.get("runtime") or 0)
                lastupdate = int(payload.get("lastupdate") or 0)
                counts = {
                    "users": int(payload.get("Users", 0) or 0),
                    "workers": int(payload.get("Workers", 0) or 0),
                    "idle": int(payload.get("Idle", 0) or 0),
                    "disconnected": int(payload.get("Disconnected", 0) or 0),
                }

            if any(k.startswith("hashrate") for k in payload.keys()) and not hashrates:
                # store as GH/s for display convenience
                for k, v in payload.items():
                    if k.startswith("hashrate"):
                        hashrates[k] = parse_rate_to_ghs(v)

            if "accepted" in payload and "rejected" in payload and not shares:
                shares = {
                    "diff": payload.get("diff"),
                    "accepted": int(payload.get("accepted", 0) or 0),
                    "rejected": int(payload.get("rejected", 0) or 0),
                    "bestshare": int(payload.get("bestshare", 0) or 0),
                    "sps1m": payload.get("SPS1m"),
                    "sps5m": payload.get("SPS5m"),
                    "sps15m": payload.get("SPS15m"),
                    "sps1h": payload.get("SPS1h"),
                }
            continue

        mw = WORKER_RE.match(ln)
        if mw:
            wname = mw.group(1)
            if wname not in workers:
                try:
                    payload = json.loads(mw.group(2))
                except Exception:
                    continue
                # worker hashrate1m seems numeric H/s in your log
                ghs = None
                try:
                    ghs = float(payload.get("hashrate1m", 0.0)) / 1e9
                except Exception:
                    pass
                workers[wname] = {
                    "name": wname,
                    "hashrate1m_ghs": ghs,
                    "shares": int(payload.get("shares", 0) or 0),
                    "lastshare": int(payload.get("lastshare", 0) or 0),
                    "bestshare": float(payload.get("bestshare", 0) or 0),
                }
            continue

        mu = USER_RE.match(ln)
        if mu:
            uname = mu.group(1)
            if uname not in users:
                try:
                    payload = json.loads(mu.group(2))
                except Exception:
                    continue
                users[uname] = {
                    "username": uname,
                    "hashrate1m_ghs": parse_rate_to_ghs(payload.get("hashrate1m")),
                    "hashrate5m_ghs": parse_rate_to_ghs(payload.get("hashrate5m")),
                    "hashrate1hr_ghs": parse_rate_to_ghs(payload.get("hashrate1hr")),
                    "hashrate1d_ghs": parse_rate_to_ghs(payload.get("hashrate1d")),
                    "hashrate7d_ghs": parse_rate_to_ghs(payload.get("hashrate7d")),
                    "lastshare": int(payload.get("lastshare", 0) or 0),
                    "workers": int(payload.get("workers", 0) or 0),
                    "shares": int(payload.get("shares", 0) or 0),
                    "bestshare": float(payload.get("bestshare", 0) or 0),
                    "bestever": float(payload.get("bestever", 0) or 0),
                    "authorised": int(payload.get("authorised", 0) or 0),
                }
            continue

        if runtime is not None and hashrates and shares and users and workers:
            # We have enough for a rich snapshot
            pass

    # Attach workers to users by prefix match: "<user>.<worker>"
    miners = []
    for uname, u in users.items():
        prefix = uname + "."
        wlist = [w for k,w in workers.items() if k.startswith(prefix)]
        miners.append({**u, "workers_list": wlist})

    # Sort miners by 1m hashrate desc
    miners.sort(key=lambda x: (x.get("hashrate1m_ghs") or 0.0), reverse=True)

    now = int(time.time())
    snap = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "pool": {
            "runtime_sec": int(runtime or 0),
            "lastupdate_ts": int(lastupdate or 0),
            "lastupdate_age_sec": int(now - int(lastupdate or now)),
            "counts": counts,
            # pool hashrates in GH/s
            "hashrate_ghs": {
                "1m": hashrates.get("hashrate1m", 0.0),
                "5m": hashrates.get("hashrate5m", 0.0),
                "15m": hashrates.get("hashrate15m", 0.0),
                "1h": hashrates.get("hashrate1hr", 0.0),
                "1d": hashrates.get("hashrate1d", 0.0),
                "7d": hashrates.get("hashrate7d", 0.0),
            },
            "shares": shares,
        },
        "miners": miners,
    }
    return snap

def main():
    snap = build_snapshot()
    atomic_write_json(OUT_JSON, snap)

if __name__ == "__main__":
    main()
