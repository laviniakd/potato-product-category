#!/usr/bin/env bash
# monitor.sh — Show live annotation progress.
# Run at any time on the EC2 server:  bash monitor.sh
# For continuous updates:             watch -n 30 bash monitor.sh

cd "$(dirname "$0")"

ANNOTATIONS_DIR="annotations"

if [ ! -d "$ANNOTATIONS_DIR" ]; then
    echo "No annotations directory found. Has anyone annotated yet?"
    exit 0
fi

python3 - << 'EOF'
import json, os, glob, sys
from collections import defaultdict

ann_dir = "annotations"
files = glob.glob(os.path.join(ann_dir, "*.json"))
# Exclude POTATO's internal state files
files = [f for f in files if not os.path.basename(f).startswith("_")]

if not files:
    print("No annotation files found yet.")
    sys.exit(0)

total_items = 0
total_gold_correct = 0
total_gold_seen = 0
annotator_rows = []

GOLD_ANSWERS = {"gold_1": "Alcohol", "gold_2": "Vehicles"}

for fpath in sorted(files):
    try:
        with open(fpath) as f:
            data = json.load(f)
    except Exception:
        continue

    username = os.path.splitext(os.path.basename(fpath))[0]
    n_items = 0
    gold_correct = 0
    gold_seen = 0

    for item_id, annotation in data.items():
        n_items += 1
        # Check gold items (id like gold_1_b3, gold_2_b12, etc.)
        base = item_id.rsplit("_b", 1)[0] if "_b" in item_id else item_id
        if base in GOLD_ANSWERS:
            gold_seen += 1
            label = annotation.get("product_category", {})
            # POTATO stores labels in various formats; try to extract the value
            if isinstance(label, dict):
                label = list(label.values())[0] if label else ""
            elif isinstance(label, list):
                label = label[0] if label else ""
            if label == GOLD_ANSWERS[base]:
                gold_correct += 1

    total_items += n_items
    total_gold_seen += gold_seen
    total_gold_correct += gold_correct
    acc = f"{gold_correct}/{gold_seen}" if gold_seen else "—"
    annotator_rows.append((username, n_items, acc))

print(f"{'Annotator':<30} {'Items':>6}  {'Gold':>6}")
print("-" * 46)
for user, n, acc in sorted(annotator_rows, key=lambda r: -r[1]):
    print(f"{user:<30} {n:>6}  {acc:>6}")
print("-" * 46)
print(f"{'TOTAL':<30} {total_items:>6}  {total_gold_correct}/{total_gold_seen}")
print()
print(f"Annotators active: {len(annotator_rows)}")

# Timing summary from session_log.jsonl
import json as _json, os as _os
log_path = os.path.join(ann_dir, "session_log.jsonl")
if os.path.exists(log_path):
    durations = []
    with open(log_path) as f:
        for line in f:
            try:
                rec = _json.loads(line)
                d = rec.get("duration_seconds")
                if d is not None:
                    durations.append(d)
            except Exception:
                pass
    if durations:
        avg = sum(durations) / len(durations)
        mn, mx = min(durations), max(durations)
        print()
        print(f"Completion times (n={len(durations)}): "
              f"avg {avg/60:.1f}m  min {mn/60:.1f}m  max {mx/60:.1f}m")
EOF
