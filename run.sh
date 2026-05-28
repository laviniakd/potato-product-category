#!/usr/bin/env bash
# run.sh — Start the POTATO annotation server + debrief companion server.
#
# Must be run after setup.sh.

set -euo pipefail
cd "$(dirname "$0")"

source myenv/bin/activate

# Install flask-cors if not present (needed by debrief_server.py)
pip install -q flask-cors

PUBLIC_IP=$(curl -s http://checkip.amazonaws.com 2>/dev/null || echo "localhost")

echo "Starting debrief server on port 8001 ..."
python debrief_server.py &
DEBRIEF_PID=$!
echo "  Debrief server PID: ${DEBRIEF_PID}"
echo ""

echo "Starting POTATO on port 8000 ..."
echo ""
echo "Prolific study URL (paste into Prolific 'Study URL' field):"
echo "  http://${PUBLIC_IP}:8000/?PROLIFIC_PID={{%PROLIFIC_PID%}}&STUDY_ID={{%STUDY_ID%}}&SESSION_ID={{%SESSION_ID%}}"
echo ""
echo "Annotations will be saved to: annotations/"
echo "Debrief responses:             annotations/debrief.jsonl"
echo ""

# On exit, also kill the debrief server
trap "kill ${DEBRIEF_PID} 2>/dev/null" EXIT

python -m potato start config.yaml -p 8000
