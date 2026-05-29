#!/usr/bin/env bash
# reset_participant.sh — Wipe all annotation progress for a given Prolific PID.
#
# Usage:
#   bash reset_participant.sh <PROLIFIC_PID>
#
# This deletes the participant's annotation file so they can restart the study
# from scratch with the same Prolific PID. POTATO must be restarted afterwards
# for its in-memory assignment state to be cleared.
#
# Example:
#   bash reset_participant.sh 5f3e1234abc
#   # then restart POTATO: Ctrl-C run.sh and re-run it

set -euo pipefail
cd "$(dirname "$0")"

if [ $# -ne 1 ]; then
    echo "Usage: $0 <PROLIFIC_PID>"
    exit 1
fi

PID="$1"
ANN_FILE="annotations/${PID}.json"

if [ ! -f "$ANN_FILE" ]; then
    echo "No annotation file found for PID: ${PID}"
    echo "  (looked for: ${ANN_FILE})"
    exit 0
fi

# Show a summary before deleting
echo "Participant: ${PID}"
python3 - "${ANN_FILE}" << 'EOF'
import json, sys
fpath = sys.argv[1]
with open(fpath) as f:
    data = json.load(f)
n = len(data)
gold = sum(1 for k in data if "_b" in k and k.rsplit("_b", 1)[0] in ("gold_1", "gold_2"))
print(f"  Items annotated: {n}  (gold seen: {gold})")
EOF

read -rp "Delete ${ANN_FILE}? [y/N] " confirm
if [[ "${confirm,,}" != "y" ]]; then
    echo "Aborted."
    exit 0
fi

rm "$ANN_FILE"
echo "Deleted ${ANN_FILE}."

# Also remove any session log entry for this PID
SESSION_LOG="annotations/session_log.jsonl"
if [ -f "$SESSION_LOG" ]; then
    TMPFILE=$(mktemp)
    python3 - "${SESSION_LOG}" "${PID}" > "$TMPFILE" << 'EOF'
import json, sys
log_path, pid = sys.argv[1], sys.argv[2]
kept = 0
with open(log_path) as f:
    for line in f:
        try:
            rec = json.loads(line)
        except Exception:
            print(line, end="")
            continue
        if rec.get("prolific_pid") != pid:
            print(line, end="")
            kept += 1
import sys
print(f"(removed session log entries for {pid}; {kept} other entries retained)", file=sys.stderr)
EOF
    mv "$TMPFILE" "$SESSION_LOG"
fi

echo ""
echo "IMPORTANT: Restart POTATO for its in-memory state to reset:"
echo "  Ctrl-C the current run.sh, then: bash run.sh"
