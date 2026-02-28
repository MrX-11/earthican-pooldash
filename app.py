from flask import Flask, jsonify, render_template
import time
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

