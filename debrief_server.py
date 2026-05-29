"""
debrief_server.py — Minimal Flask server that captures timing and end-of-task feedback.

Endpoints:
  POST /record_start  — called from intro.html when the participant begins; records start time
  POST /save_debrief  — called from exit_survey.html when participant submits debrief
  GET  /health        — liveness check

Run alongside POTATO (on port 8001):
    source myenv/bin/activate
    python debrief_server.py

Output files:
  annotations/session_log.jsonl  — one record per participant: start time, end time, duration
  annotations/debrief.jsonl      — debrief text responses (interface feedback + observations)
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # allow requests from the POTATO origin (same host, different port)

ANNOTATIONS_DIR = Path("annotations")
ANNOTATIONS_DIR.mkdir(exist_ok=True)

SESSION_LOG = ANNOTATIONS_DIR / "session_log.jsonl"
DEBRIEF_LOG = ANNOTATIONS_DIR / "debrief.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_start_times() -> dict:
    """Return {prolific_pid: started_at_iso} from session_log."""
    starts = {}
    if SESSION_LOG.exists():
        with open(SESSION_LOG) as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    pid = rec.get("prolific_pid")
                    if pid and "started_at" in rec:
                        starts[pid] = rec["started_at"]
                except Exception:
                    pass
    return starts


def _append_jsonl(path: Path, record: dict) -> None:
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


@app.post("/record_start")
def record_start():
    """Called from intro.html when the participant loads the instructions page."""
    data = request.get_json(silent=True) or {}
    pid = data.get("prolific_pid", "unknown")
    started_at = _now_iso()

    record = {
        "prolific_pid": pid,
        "started_at": started_at,
        "event": "start",
    }
    _append_jsonl(SESSION_LOG, record)
    return jsonify({"status": "ok", "started_at": started_at})


@app.post("/save_debrief")
def save_debrief():
    """Called from exit_survey.html when the participant submits the debrief form."""
    data = request.get_json(silent=True) or {}
    pid = data.get("prolific_pid", "unknown")
    submitted_at = _now_iso()

    # Compute duration if we have a start time
    starts = _load_start_times()
    duration_seconds = None
    if pid in starts:
        try:
            t0 = datetime.fromisoformat(starts[pid])
            t1 = datetime.fromisoformat(submitted_at)
            duration_seconds = round((t1 - t0).total_seconds())
        except Exception:
            pass

    # Write debrief text response
    debrief_record = {
        "prolific_pid": pid,
        "feedback_interface": data.get("feedback_interface", ""),
        "feedback_observations": data.get("feedback_observations", ""),
        "submitted_at": submitted_at,
        "duration_seconds": duration_seconds,
    }
    _append_jsonl(DEBRIEF_LOG, debrief_record)

    # Write end event to session log
    end_record = {
        "prolific_pid": pid,
        "submitted_at": submitted_at,
        "duration_seconds": duration_seconds,
        "event": "end",
    }
    _append_jsonl(SESSION_LOG, end_record)

    return jsonify({"status": "ok", "duration_seconds": duration_seconds})


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, debug=False)
