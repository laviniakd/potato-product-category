"""
debrief_server.py — Minimal Flask server that captures end-of-task feedback.

Run alongside POTATO (on port 8001) in a separate screen session:
    source myenv/bin/activate
    python debrief_server.py

Responses are appended to annotations/debrief.jsonl, one JSON per line.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # allow requests from the POTATO origin (same host, different port)

OUTPUT = Path("annotations/debrief.jsonl")
OUTPUT.parent.mkdir(exist_ok=True)


@app.post("/save_debrief")
def save_debrief():
    data = request.get_json(silent=True) or {}
    record = {
        "prolific_pid": data.get("prolific_pid", "unknown"),
        "feedback_interface": data.get("feedback_interface", ""),
        "feedback_observations": data.get("feedback_observations", ""),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(OUTPUT, "a") as f:
        f.write(json.dumps(record) + "\n")
    return jsonify({"status": "ok"})


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, debug=False)
