#!/usr/bin/env bash
# run.sh — Start the POTATO annotation server.
#
# Must be run after setup.sh.
# Set PROLIFIC_COMPLETION_CODE before launching if using Prolific:
#   PROLIFIC_COMPLETION_CODE=XXXXXXXX bash run.sh

set -euo pipefail
cd "$(dirname "$0")"

source myenv/bin/activate

PUBLIC_IP=$(curl -s http://checkip.amazonaws.com 2>/dev/null || echo "localhost")

echo "Starting POTATO on port 8000 ..."
echo ""
echo "Prolific study URL (paste into Prolific 'Study URL' field):"
echo "  http://${PUBLIC_IP}:8000/?PROLIFIC_PID={{%PROLIFIC_PID%}}&STUDY_ID={{%STUDY_ID%}}&SESSION_ID={{%SESSION_ID%}}"
echo ""
echo "Annotations will be saved to: annotations/"
echo ""

python -m potato start config.yaml -p 8000
