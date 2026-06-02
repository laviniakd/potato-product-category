"""
generate_examples_page.py

Reads POTATO annotation JSON files from annotations/ and builds a static
HTML page (surveyflow/examples.html) showing one representative ad image
per product category, then uploads it to GCS.

Usage (run from the potato-product-category project root on EC2):
    source myenv/bin/activate
    python generate_examples_page.py [--annotations_dir annotations/] [--upload]

Requirements:
    - annotations/*.json must be present (at least partial)
    - gsutil on PATH (for --upload)
"""

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

GCS_STATIC_URL = "https://storage.googleapis.com/label-studio-magazines/product_category_round1/static"
GCS_BUCKET_PREFIX = "gs://label-studio-magazines/product_category_round1/static"
TAXONOMY_URL = f"{GCS_STATIC_URL}/taxonomy.html"

CATEGORIES = [
    "Alcohol", "Business and Industrial", "City or Region",
    "Clothing and Accessories", "Collectables and Antiques",
    "Computer Software", "Consumer Electronics",
    "Consumer Packaged Goods and Durable Goods",
    "Cosmetic Services", "Culture and Fine Arts",
    "Debated Sensitive Social Issue", "Dieting and Weight loss",
    "Education and Careers", "Events and Performances",
    "Family and Parenting", "Finance and Insurance",
    "Fitness Activities and Sporting Goods",
    "Food and Beverage Services", "Gifts and Holiday Items",
    "Health and Medical Services", "Home and Garden Services",
    "Legal Services", "Media", "Metals", "Non-Profits",
    "Oil and Gas", "Personal/Consumer Telecom", "Pet Ownership",
    "Pharmaceuticals", "Politics", "Real Estate",
    "Religion and Spirituality", "Retail", "Sexual Health",
    "Tobacco", "Travel and Tourism", "Vehicles",
    "Weapons and Ammunition",
]


def load_annotations(ann_dir: Path) -> dict[str, list[dict]]:
    """Return {category: [item_dict, ...]} from all annotation JSON files."""
    by_cat: dict[str, list[dict]] = defaultdict(list)
    ann_files = list(ann_dir.glob("*.json"))
    ann_files = [f for f in ann_files if not f.name.startswith("_")]

    # Load the input JSONL to get image URLs
    input_jsonl = Path("data/annotations_input.jsonl")
    id_to_item: dict[str, dict] = {}
    if input_jsonl.exists():
        with open(input_jsonl) as f:
            for line in f:
                item = json.loads(line)
                id_to_item[item["id"]] = item

    for fpath in ann_files:
        try:
            with open(fpath) as f:
                data = json.load(f)
        except Exception:
            continue

        for item_id, annotation in data.items():
            if item_id.startswith("gold_"):
                continue  # skip gold items

            # Extract category label — POTATO stores it in various formats
            label = annotation.get("product_category", {})
            if isinstance(label, dict):
                label = next(iter(label.values()), "") if label else ""
            elif isinstance(label, list):
                label = label[0] if label else ""
            label = str(label).strip()
            if not label or label not in CATEGORIES:
                continue

            item = id_to_item.get(item_id, {})
            image_url = item.get("image_url", "")
            if not image_url:
                continue

            by_cat[label].append({
                "id": item_id,
                "image_url": image_url,
                "magazine": item.get("magazine", ""),
                "decade": item.get("decade", ""),
            })

    return dict(by_cat)


def build_html(by_cat: dict[str, list[dict]]) -> str:
    rows = []
    covered = sorted(by_cat.keys())
    missing = [c for c in CATEGORIES if c not in by_cat]

    for cat in CATEGORIES:
        examples = by_cat.get(cat, [])
        if not examples:
            rows.append(f"""
  <div class="cat-block missing">
    <h2>{cat}</h2>
    <p class="no-example">No annotated example available yet.</p>
  </div>""")
            continue

        # Pick up to 2 examples
        picks = examples[:2]
        imgs = ""
        for ex in picks:
            mag = str(ex.get("magazine", "")).title()
            dec = ex.get("decade", "")
            caption = f"{mag}, {dec}s" if mag and dec else ""
            imgs += f"""
      <div class="ex-img">
        <img src="{ex['image_url']}" alt="{cat}" loading="lazy" />
        <div class="caption">{caption}</div>
      </div>"""

        rows.append(f"""
  <div class="cat-block">
    <h2>{cat}</h2>
    <div class="examples">{imgs}
    </div>
  </div>""")

    covered_note = f"{len(covered)}/{len(CATEGORIES)} categories have examples"
    missing_note = (
        f"<p class='missing-note'>Missing examples: {', '.join(missing)}</p>"
        if missing else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Product Category Examples</title>
  <style>
    body {{ font-family: sans-serif; max-width: 960px; margin: 32px auto; padding: 0 16px; color: #333; }}
    h1 {{ font-size: 1.3em; border-bottom: 2px solid #ddd; padding-bottom: 8px; }}
    h2 {{ font-size: 1em; margin: 0 0 8px; color: #1e40af; }}
    .cat-block {{ border: 1px solid #e5e7eb; border-radius: 6px; padding: 12px 16px; margin-bottom: 16px; }}
    .cat-block.missing {{ background: #fafafa; border-style: dashed; }}
    .examples {{ display: flex; gap: 16px; flex-wrap: wrap; }}
    .ex-img img {{ max-height: 260px; max-width: 220px; border: 1px solid #ddd; border-radius: 4px; display: block; }}
    .caption {{ font-size: 11px; color: #888; margin-top: 4px; text-align: center; }}
    .no-example {{ font-size: 0.85em; color: #aaa; font-style: italic; }}
    .missing-note {{ font-size: 0.85em; color: #888; }}
    .meta {{ font-size: 0.85em; color: #666; margin-bottom: 24px; }}
    a {{ color: #2563eb; }}
  </style>
</head>
<body>
<h1>Product Category Examples</h1>
<p class="meta">
  {covered_note}.
  For a full category reference, see the <a href="{TAXONOMY_URL}" target="_blank">IAB taxonomy &rarr;</a>
</p>
{missing_note}
{''.join(rows)}
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotations_dir", default="annotations/")
    parser.add_argument("--upload", action="store_true",
                        help="Upload examples.html to GCS after generating")
    args = parser.parse_args()

    ann_dir = Path(args.annotations_dir)
    if not ann_dir.exists():
        print(f"Annotations directory not found: {ann_dir}")
        return

    print("Loading annotations...")
    by_cat = load_annotations(ann_dir)
    print(f"Found examples for {len(by_cat)} categories")

    html = build_html(by_cat)
    out = Path("surveyflow/examples.html")
    out.write_text(html)
    print(f"Written: {out}")

    if args.upload:
        import subprocess
        gcs_path = f"{GCS_BUCKET_PREFIX}/examples.html"
        result = subprocess.run(
            ["gsutil", "cp", str(out), gcs_path],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"Uploaded to {gcs_path}")
            print(f"Public URL: {GCS_STATIC_URL}/examples.html")
        else:
            print("Upload failed:", result.stderr)


if __name__ == "__main__":
    main()
