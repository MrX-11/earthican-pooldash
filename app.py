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
    window = max(60, min(window, 60 * 60 * 24 * 90))
    max_points = max(100, min(max_points, 5000))
    return jsonify(_load_hashrate_history(window, max_points))
