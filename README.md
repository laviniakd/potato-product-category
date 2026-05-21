# Product Category Annotation (POTATO)

Crowd annotation of 1,040 full-page magazine ads with a 38-class product category taxonomy.
Hosted via [POTATO](https://github.com/davidjurgens/potato), deployed on EC2, workers recruited via Prolific.

## Data

1,040 images sampled from `predictions_all.csv` (ad_prob ≥ 0.90, stratified by decade × magazine).
Images are hosted publicly at `gs://label-studio-magazines/product_category_round1/`.

Each item in `data/annotations_input.jsonl`:
```json
{"id": "time-1925-01-26-x-x-2", "image_url": "https://storage.googleapis.com/...", "magazine": "time", "decade": 1920}
```

## Setup (EC2)

```bash
git clone https://github.com/YOUR_ORG/potato-product-category.git
cd potato-product-category
bash setup.sh
```

## Running

```bash
bash run.sh
```

Server starts on port 8000. Make sure the EC2 security group has port 8000 open to `0.0.0.0/0`.

## Prolific integration

Set the Prolific study URL to:
```
http://YOUR-EC2-IP:8000/?PROLIFIC_PID={{%PROLIFIC_PID%}}&STUDY_ID={{%STUDY_ID%}}&SESSION_ID={{%SESSION_ID%}}
```

POTATO reads `PROLIFIC_PID` from the URL and uses it as the worker identifier (`login_type: url_direct`).

After completing annotations, workers need to be redirected to the Prolific completion URL. See [POTATO surveyflow docs](https://potato-annotation.readthedocs.io/en/latest/crowdsourcing/) for configuring end-of-task redirects.

Recruit **≥125 workers** (150 with 20% buffer) to achieve 3 annotations per image.
Each worker sees **25 images** (`instances_per_annotator: 25` in `config.yaml`).

## Annotation parameters

| Setting | Value |
|---------|-------|
| Images | 1,040 |
| Annotations per image | 3 |
| Images per worker | 25 |
| Workers needed | ~150 |
| Categories | 38 |

## Post-collection analysis

Export POTATO's `annotations/` directory and run:

```bash
python /home/laviniad/projects/magazines/magazines/scripts/annotation_sample_creation/analyze_qualtrics_annotations.py \
    --input_csv /path/to/exported_annotations.csv \
    --manifest_csv /data/laviniad/magazines/annotation_data/prolific_product_category/manifest.csv
```

> **Note**: `analyze_qualtrics_annotations.py` expects a Qualtrics-format CSV export.
> POTATO exports JSON. A conversion script is needed — see OPEN below.

## OPEN questions

- **Prolific completion redirect**: POTATO supports end-of-task redirects via `surveyflow` config.
  Needs a `surveyflow/` directory with HTML pages and the Prolific completion URL set in config.
  See: https://potato-annotation.readthedocs.io/en/latest/crowdsourcing/
- **POTATO run command**: verify the exact invocation — either `python -m potato start config.yaml`
  or `python potato/flask_server.py start config.yaml`. `run.sh` uses the former; adjust if needed.
- **Post-collection analysis**: POTATO outputs per-annotator JSON files, not a single CSV.
  The analysis script currently expects Qualtrics CSV format and needs adaptation for POTATO output.
