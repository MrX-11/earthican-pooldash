# earthican-pooldash

Minimal, DB-free CKPool dashboard.

- `snapshot_writer.py` parses CKPool logs and writes `data/pool_snapshot.json`
- `app.py` serves a single-page UI and `/api/snapshot`

Notes:
- `data/` is runtime output (gitignored)
- `earthican-venv/` is not tracked
