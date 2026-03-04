from flask import Flask, jsonify, render_template, request
import time

import os, json

HIST_JSONL = os.getenv("EARTHICAN_HISTORY_JSONL", "/var/www/earthican/data/pool_hashrate_history.jsonl")

def _load_hashrate_history(window_sec: int, max_points: int):
    import time
    now = int(time.time())
    cutoff = now - max(1, int(window_sec))

    t = []
    hs = []
    try:
        with open(HIST_JSONL, "r", encoding="utf-8", errors="replace") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    obj = json.loads(ln)
                    ts = int(obj.get("t", 0) or 0)
                    if ts < cutoff:
                        continue
                    t.append(ts)
                    hs.append(float(obj.get("hs_1m", 0.0) or 0.0))
                except Exception:
                    continue
    except Exception:
        return {"t": [], "hs_1m": []}

    n = len(t)
    if n <= max_points or max_points <= 0:
        return {"t": t, "hs_1m": hs}

    stride = (n + max_points - 1) // max_points
    return {"t": t[::stride], "hs_1m": hs[::stride]}

def _load_hashrate_history_db(window_sec: int, max_points: int):
    import time
    import mysql.connector

    now = int(time.time())
    cutoff = now - max(1, int(window_sec))

    # 60s buckets (minute-aligned) from ckpool.pool_stats.hashrate
    sql = """
    SELECT
      FLOOR(UNIX_TIMESTAMP(`timestamp`)/60)*60 AS t,
      AVG(`hashrate`) AS hs
    FROM pool_stats
    WHERE `timestamp` >= FROM_UNIXTIME(%s)
    GROUP BY t
    ORDER BY t;
    """

    conn = mysql.connector.connect(
        host=os.environ["CKPOOL_DB_HOST"],
        user=os.environ["CKPOOL_DB_USER"],
        password=os.environ["CKPOOL_DB_PASS"],
        database=os.environ["CKPOOL_DB_NAME"],
    )
    try:
        cur = conn.cursor()
        cur.execute(sql, (cutoff,))
        rows = cur.fetchall()
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()

    t = [int(r[0]) for r in rows]
    hs = [float(r[1] or 0.0) for r in rows]

    n = len(t)
    if n <= max_points or max_points <= 0:
        return {"t": t, "hs_1m": hs}

    stride = (n + max_points - 1) // max_points
    return {"t": t[::stride], "hs_1m": hs[::stride]}


from server_monitor import query_minecraft, query_asa
import os
import json

app = Flask(__name__, template_folder="templates")
SNAP_PATH = os.getenv("EARTHICAN_SNAPSHOT_PATH", "/var/www/earthican/data/pool_snapshot.json")
def load_snap():
    try:
        with open(SNAP_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"ts_utc": None, "pool": {}, "miners": []}

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/snapshot")
def api_snapshot():
    return jsonify(load_snap())


@app.get("/api/server_status")
def api_server_status():
    return jsonify({
        "ts": int(time.time()),
        "minecraft": query_minecraft(),
        "ark_asa": query_asa(),
    })



@app.get("/api/hashrate_history")
def api_hashrate_history():
    window = int(request.args.get("window", "86400"))
    max_points = int(request.args.get("max_points", "600"))
    window = max(60, min(window, 60*60*24*365))
    max_points = max(100, min(max_points, 5000))
    return jsonify(_load_hashrate_history_db(window, max_points))


def _load_miner_history(username: str, window_sec: int, max_points: int, worker: str | None = None):
    import os, json, time, re
    from pathlib import Path

    base = Path(os.getenv("EARTHICAN_MINER_HIST_DIR", "/var/www/earthican/data/miner_hist"))

    def safe_name(x: str) -> str:
        x = (x or "").strip()
        x = re.sub(r"[^a-zA-Z0-9._-]+", "_", x)
        return x[:200] if x else "unknown"

    fn = base / f"{safe_name(username)}.jsonl"
    if not fn.exists():
        return {"t": [], "hs": []}

    now = int(time.time())
    cutoff = now - max(1, int(window_sec))

    t = []
    hs = []

    try:
        with fn.open("r", encoding="utf-8", errors="replace") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    obj = json.loads(ln)
                    ts = int(obj.get("t", 0) or 0)
                    if ts < cutoff:
                        continue

                    if worker:
                        w = obj.get("w") or {}
                        v = float((w.get(worker) or 0.0))
                    else:
                        v = float(obj.get("total_hs") or 0.0)

                    t.append(ts)
                    hs.append(v)
                except Exception:
                    continue
    except Exception:
        return {"t": [], "hs": []}

    n = len(t)
    if n <= max_points or max_points <= 0:
        return {"t": t, "hs": hs}

    stride = (n + max_points - 1) // max_points
    return {"t": t[::stride], "hs": hs[::stride]}


@app.get("/api/miner_history/<username>")
def api_miner_history(username):
    window = int(request.args.get("window", "86400"))
    max_points = int(request.args.get("max_points", "400"))
    worker = request.args.get("worker") or None

    # allow up to 90 days (matches pool endpoint)
    window = max(60, min(window, 60*60*24*365))
    max_points = max(60, min(max_points, 2000))

    return jsonify(_load_miner_history(username, window, max_points, worker))


@app.get("/chart/miner/<username>")
def chart_miner(username):
    # params: window (seconds), worker (full worker name or empty)
    window = int(request.args.get("window", "21600"))
    worker = request.args.get("worker", "") or ""
    window = max(3600, min(window, 60 * 60 * 24 * 365))
    return render_template("chart_miner.html", username=username, worker=worker, window=window)

@app.get("/chart/miner/<username>/all")
def chart_miner_all(username):
    window = int(request.args.get("window", "21600"))
    window = max(3600, min(window, 60 * 60 * 24 * 365))
    return render_template("chart_miner_all.html", username=username, window=window)
