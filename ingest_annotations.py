"""
ingest_annotations.py

Downloads POTATO user_state.json files from GCS and produces:
  annotations/annotations.csv   — one row per (annotator, item)
  annotations/summary.txt       — human-readable summary

Usage:
    python ingest_annotations.py [--gcs_prefix product-category-annotations] [--out_dir annotations/]

The script prints a rich summary to stdout, focusing on:
  - Per-annotator stats (items, gold accuracy, duration, flags)
  - Per-item agreement where items have 2+ annotations
  - All non-empty feedback responses
"""

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

GCS_BUCKET = "label-studio-magazines"
GOLD_ANSWERS = {"gold_1": "Alcohol", "gold_2": "Vehicles"}
TAXONOMY_URL = "https://storage.googleapis.com/label-studio-magazines/product_category_round1/static/taxonomy.html"


# ── helpers ──────────────────────────────────────────────────────────────────

def _extract_label(label_list: list, schema: str) -> str:
    """Extract a single label value for a given schema from POTATO's nested list format."""
    for entry in label_list:
        if isinstance(entry, list) and len(entry) >= 2:
            meta = entry[0]
            if isinstance(meta, dict) and meta.get("schema") == schema:
                val = entry[1]
                return str(val).strip() if val else ""
    return ""


def _is_gold(item_id: str) -> Optional[str]:
    """Return base gold key (e.g. 'gold_1') if item_id is a gold item, else None."""
    if item_id in GOLD_ANSWERS:
        return item_id
    if "_b" in item_id:
        base = item_id.rsplit("_b", 1)[0]
        if base in GOLD_ANSWERS:
            return base
    return None


def _duration_seconds(behav: dict) -> Optional[float]:
    """Estimate total session duration from behavioral data session_start timestamps."""
    timestamps = [
        v["session_start"]
        for v in behav.values()
        if isinstance(v, dict) and v.get("session_start")
    ]
    if len(timestamps) < 2:
        return None
    return round(max(timestamps) - min(timestamps))


# ── loading ───────────────────────────────────────────────────────────────────

def download_from_gcs(gcs_prefix: str, local_dir: Path) -> list[Path]:
    local_dir.mkdir(parents=True, exist_ok=True)
    gcs_uri = f"gs://{GCS_BUCKET}/{gcs_prefix}/"
    result = subprocess.run(
        ["gsutil", "-m", "cp", "-r", gcs_uri + "*", str(local_dir)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("gsutil error:", result.stderr, file=sys.stderr)
        sys.exit(1)
    return list(local_dir.rglob("user_state.json"))


def load_user_states(local_dir: Path) -> list[dict]:
    states = []
    for fpath in sorted(local_dir.rglob("user_state.json")):
        try:
            with open(fpath) as f:
                states.append(json.load(f))
        except Exception as e:
            print(f"Warning: could not load {fpath}: {e}", file=sys.stderr)
    return states


# ── parsing ───────────────────────────────────────────────────────────────────

def parse_annotations(states: list[dict]) -> list[dict]:
    """Return flat list of annotation dicts, one per (annotator, item)."""
    rows = []
    for state in states:
        pid = state.get("user_id", "unknown")
        labels_map = state.get("instance_id_to_label_to_value", {})
        behav = state.get("instance_id_to_behavioral_data", {})
        phase_data = state.get("phase_to_page_to_label_to_value", {})
        ordering = state.get("instance_id_ordering", [])

        # Poststudy feedback
        poststudy_entries = phase_data.get("poststudy", {}).get("poststudy", [])
        feedback_interface = _extract_label(poststudy_entries, "feedback_interface")
        feedback_observations = _extract_label(poststudy_entries, "feedback_observations")

        duration = _duration_seconds(behav)

        for item_id, label_list in labels_map.items():
            category = _extract_label(label_list, "product_category")
            not_complete = _extract_label(label_list, "not_complete_ad")
            ambiguous = _extract_label(label_list, "ambiguous_category")
            comment = _extract_label(label_list, "comment")

            gold_base = _is_gold(item_id)
            gold_correct = None
            if gold_base:
                gold_correct = (category == GOLD_ANSWERS[gold_base])

            rows.append({
                "prolific_pid": pid,
                "item_id": item_id,
                "position": ordering.index(item_id) + 1 if item_id in ordering else None,
                "category": category,
                "not_complete_ad": bool(not_complete),
                "ambiguous_category": bool(ambiguous),
                "comment": comment,
                "is_gold": bool(gold_base),
                "gold_correct": gold_correct,
                "duration_seconds": duration,
                "feedback_interface": feedback_interface,
                "feedback_observations": feedback_observations,
            })
    return rows


# ── summary ───────────────────────────────────────────────────────────────────

def print_summary(rows: list[dict]) -> str:
    lines = []

    def p(s=""):
        lines.append(s)
        print(s)

    annotators = sorted({r["prolific_pid"] for r in rows})
    regular = [r for r in rows if not r["is_gold"]]
    gold = [r for r in rows if r["is_gold"]]

    p("=" * 70)
    p("ANNOTATION SUMMARY")
    p(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    p("=" * 70)
    p()

    # ── Per-annotator ──
    p(f"ANNOTATORS ({len(annotators)})")
    p("-" * 70)
    hdr = f"{'PID':<28} {'Items':>5}  {'Gold':>6}  {'Duration':>10}  Flags"
    p(hdr)
    for pid in annotators:
        pid_rows = [r for r in rows if r["prolific_pid"] == pid]
        n_regular = sum(1 for r in pid_rows if not r["is_gold"])
        gold_rows = [r for r in pid_rows if r["is_gold"]]
        gold_str = f"{sum(r['gold_correct'] for r in gold_rows)}/{len(gold_rows)}" if gold_rows else "—"
        dur = next((r["duration_seconds"] for r in pid_rows if r["duration_seconds"]), None)
        dur_str = f"{dur//60}m{dur%60:02d}s" if dur else "—"
        flags = sum(1 for r in pid_rows if r["not_complete_ad"] or r["ambiguous_category"])
        p(f"{pid:<28} {n_regular:>5}  {gold_str:>6}  {dur_str:>10}  {flags} flag(s)")
    p()

    # ── Feedback ──
    p("FEEDBACK")
    p("-" * 70)
    seen = set()
    any_feedback = False
    for pid in annotators:
        pid_rows = [r for r in rows if r["prolific_pid"] == pid]
        fi = next((r["feedback_interface"] for r in pid_rows if r["feedback_interface"]), "")
        fo = next((r["feedback_observations"] for r in pid_rows if r["feedback_observations"]), "")
        if fi or fo:
            any_feedback = True
            p(f"[{pid}]")
            if fi:
                p(f"  Interface feedback:  {fi}")
            if fo:
                p(f"  Observations:        {fo}")
    if not any_feedback:
        p("  (no feedback submitted)")
    p()

    # ── Comments on items ──
    comments = [r for r in regular if r["comment"]]
    if comments:
        p(f"ITEM COMMENTS ({len(comments)})")
        p("-" * 70)
        for r in comments:
            p(f"  [{r['prolific_pid'][:8]}] {r['item_id']}: {r['comment']}")
        p()

    # ── Flags ──
    flagged = [r for r in regular if r["not_complete_ad"] or r["ambiguous_category"]]
    if flagged:
        p(f"FLAGGED ITEMS ({len(flagged)})")
        p("-" * 70)
        by_item = defaultdict(list)
        for r in flagged:
            by_item[r["item_id"]].append(r)
        for item_id, item_rows in sorted(by_item.items()):
            flags = []
            if any(r["not_complete_ad"] for r in item_rows): flags.append("not-complete")
            if any(r["ambiguous_category"] for r in item_rows): flags.append("ambiguous")
            cats = [r["category"] for r in item_rows if r["category"]]
            p(f"  {item_id}  [{', '.join(flags)}]  labels={cats}")
        p()

    # ── Agreement on multi-annotated items ──
    item_counts = defaultdict(list)
    for r in regular:
        item_counts[r["item_id"]].append(r["category"])
    multi = {iid: cats for iid, cats in item_counts.items() if len(cats) >= 2}
    if multi:
        agree = {iid: cats for iid, cats in multi.items() if len(set(cats)) == 1}
        disagree = {iid: cats for iid, cats in multi.items() if len(set(cats)) > 1}
        p(f"AGREEMENT  ({len(multi)} items seen by 2+ annotators)")
        p(f"  Agree: {len(agree)}  |  Disagree: {len(disagree)}")
        if disagree:
            p(f"  Disagreements:")
            for iid, cats in sorted(disagree.items()):
                p(f"    {iid}: {cats}")
        p()

    # ── Category distribution ──
    cat_counts = defaultdict(int)
    for r in regular:
        if r["category"]:
            cat_counts[r["category"]] += 1
    if cat_counts:
        p("CATEGORY DISTRIBUTION (regular items only)")
        p("-" * 70)
        for cat, n in sorted(cat_counts.items(), key=lambda x: -x[1]):
            bar = "█" * n
            p(f"  {cat:<45} {n:>3}  {bar}")
        p()

    return "\n".join(lines)


# ── CSV output ────────────────────────────────────────────────────────────────

def write_csv(rows: list[dict], out_path: Path):
    import csv
    fields = [
        "prolific_pid", "item_id", "position", "category",
        "not_complete_ad", "ambiguous_category", "comment",
        "is_gold", "gold_correct", "duration_seconds",
        "feedback_interface", "feedback_observations",
    ]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"CSV written: {out_path} ({len(rows)} rows)")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gcs_prefix", default="product-category-annotations",
                        help="GCS prefix (under label-studio-magazines bucket)")
    parser.add_argument("--local_cache", default="/tmp/annotations",
                        help="Local directory to cache downloaded files")
    parser.add_argument("--no_download", action="store_true",
                        help="Skip GCS download; use existing files in --local_cache")
    parser.add_argument("--out_dir", default="annotations/",
                        help="Output directory for CSV and summary")
    args = parser.parse_args()

    local_dir = Path(args.local_cache)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)

    if not args.no_download:
        print(f"Downloading from gs://{GCS_BUCKET}/{args.gcs_prefix}/ ...")
        download_from_gcs(args.gcs_prefix, local_dir)

    states = load_user_states(local_dir)
    print(f"Loaded {len(states)} annotator state files")

    rows = parse_annotations(states)
    summary = print_summary(rows)

    csv_path = out_dir / "annotations.csv"
    write_csv(rows, csv_path)

    summary_path = out_dir / "summary.txt"
    summary_path.write_text(summary)
    print(f"Summary written: {summary_path}")


if __name__ == "__main__":
    main()
