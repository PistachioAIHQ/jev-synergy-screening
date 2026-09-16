# Jev × Cohen — ADHD Abstract Triage

Viral life-sciences demo: screen **MEDLINE title + abstract** as **include vs exclude** with [TypeSafe Jev](https://docs.typesafe.ai/introduction) (System One), compared to **Abstract Triage** gold from [Cohen et al. 2006](https://doi.org/10.1197/jamia.M1929).

**Gold story = Abstract Triage (TIAB) only — not Article Triage, not MEDLINE PT, not SYNERGY.**

Optional mode: **Bat4RCT** r3_ship (MEDLINE PT RCT tagging) remains in the UI toggle.

## Why this is fair

| Claim | Detail |
|--|--|
| Gold | Cohen **Abstract Triage Status** (`I` = include; anything else = exclude) |
| Evidence | MEDLINE **title + abstract** fetched by PMID (same modality as gold) |
| Never | Article Triage / full-text labels · SYNERGY `label_included` |
| Topic | ADHD (N=851; 84 include ≈ 9.9%) |
| Eligibility | Oregon DERP ADHD pharmacologic review (population, listed drugs, design, outcomes, duration / pub-type excludes) |
| Encode | Jev Choice `include\|exclude` + atomic Nouls (**`cohen_adhd_r2_ship`**: codes 2–7 + monograph/imaging/formulation gates); combine in code; shown in Questions drawer |

Custom open data from the authors’ page — **not CC-BY**. Cite Cohen 2006 (see `data/COHEN_LICENSE_NOTE.md`).

## Headline metrics (include class)

Rule: **`cohen_adhd_r2_ship`**. H2H-100 has only **N=10** positives — **do not headline H2H 100%**; prefer full-851 F1.


### Film grid (stratified N=200, seed **20260917**)

| Acc | Prec | Rec | F1 | TP/FP/FN/TN | Mean lat | Est. $ |
|-----|------|-----|----|-------------|----------|--------|
| **92.0%** | **57.1%** | **80.0%** | **66.7%** | 16/12/4/168 | ~523 ms | ~$0.018 |

Film uses a stratified subsample so the grid is filmable; prevalence preserved (20/180). Metrics above are on that film set and labeled as such.

### Full ADHD Abstract Triage (N=851)

| Acc | Prec | Rec | F1 | TP/FP/FN/TN | Mean / p50 / p95 lat | Est. $ |
|-----|------|-----|----|-------------|----------------------|--------|
| **94.6%** | **68.6%** | **83.3%** | **75.3%** | 70/32/14/735 | ~523 / ~518 / ~593 ms | **~$0.078** |

Artifacts: `results/full/`.

### Full ADHD Abstract Triage (N=851) — re-run

See `results/full/metrics.json` after:

```bash
python -m src.run_cohen_eval --subset full --workers 8 \
  --out-csv results/full/predictions.csv --out-metrics results/full/metrics.json
```

### Fair H2H vs Anthropic (stratified N=100, seed **20260916**)

Same 100 PMIDs · same TIAB · same DERP criteria text.

| System | Acc | Prec | Rec | F1 | TP/FP/FN/TN | Mean / p50 / p95 lat | $ |
|--------|-----|------|-----|----|-------------|----------------------|---|
| **Jev** (`jev-1.13.0`) | **94.0%** | **66.7%** | **80.0%** | **72.7%** | 8/4/2/86 | 525 / 523 / 601 ms | **$0.0065** |
| Anthropic (`claude-sonnet-4-5-20250929`) | 93.0% | 60.0% | 90.0% | 72.0% | 9/6/1/84 | 1297 / 1292 / 1497 ms | $0.586 |

Artifacts: `results/h2h/`.

Anthropic protocol: structured tool `include|exclude` (JSON schema) — **no CoT essay**.

> WSS@95 from Cohen 2006 is a **historical footnote only** — not the demo headline.

## Default rule

```
include iff choice==include
  AND eligible_population>=0.5
  AND listed_adhd_drug>=0.5
  AND eligible_outcome>=0.5
  AND eligible_study_design>=0.5
  AND wrong_publication_type<0.5
  AND inadequate_study_duration<0.5
```

(`src/cohen_adhd.py`)

## Film path

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export TYPESAFE_API_KEY="$(tr -d '\n' < ~/.config/typesafe/api_key)"

python -m src.run_cohen_eval --subset film --workers 8
python -m src.serve --port 8765
# http://127.0.0.1:8765/ → Mode Cohen ADHD (default) → Start or Replay cached
```

H2H:

```bash
export ANTHROPIC_API_KEY="$(tr -d '\n' < ~/.config/anthropic/api_key)"
python -m src.run_h2h --workers 6
```

### API

`GET /api/demo?mode=cohen|bat4rct` · `/api/questions` · `POST /api/classify` · `/api/predictions` · `/api/metrics` · `/api/health`

Jev: `POST https://api.typesafe.ai/v1/systemone` · `jev-latest` · questions **map** · **$0.042/MTok** input.

## Optional: Bat4RCT

`data/demo_200.csv` · r3_ship Acc 93.5% / F1 93.12% · `results/bat4rct/`

## Citation

Cohen AM, Hersh WR, Peterson K, Yen PY. *JAMIA* 2006;13(2):206–219. doi:10.1197/jamia.M1929  
Data: https://dmice.ohsu.edu/cohenaa/systematic-drug-class-review-data.html

**Never commit API keys.**
