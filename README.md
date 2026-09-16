# Jev × Bat4RCT — RCT screening demo

Viral life-sciences demo: classify MEDLINE **title + abstract** as **RCT vs non_RCT** with [TypeSafe Jev](https://docs.typesafe.ai/introduction) (System One), compare to gold labels from **Bat4RCT**, and scoreboard against the paper’s **BioBERT** baseline.

> Repo name is historical (`jev-synergy-screening`); **v1 dataset is Bat4RCT**, not SYNERGY.

## Default rule: round-2 hybrid (NOT aggressive)

**CD medium Choice** (best choice-only wording) **+** atomic nouls from `results/round2/questions_v2.json`, combined as:

```
RCT iff choice==RCT OR (
  (has_random_allocation>=0.5 OR is_cluster_random>=0.5 OR parallel_intervention_arms>=0.5)
  AND is_secondary_or_nested_only<0.5
  AND is_protocol_or_single_arm<0.5
)
```

Implemented in `src/hybrid.py` + `src/jev_client.py`. The **aggressive** variant (drops secondary exclude) is **not** used.

| Variant | Acc | F1 | TP/FP/FN/TN |
|---------|-----|----|-------------|
| CD choice-only | 87.00% | 85.23% | 75/1/25/99 |
| **Hybrid (default)** | **89.5%** | **88.40%** | **80/1/20/99** |
| Aggressive (not shipped) | 90.5% | 89.73% | 83/2/17/98 |

Round-2 win vs choice-only: **+2.5 pp Acc / +3.17 pp F1** with FP unchanged (1).

## BioBERT bar (on-screen)

From Kim et al., *PLOS ONE* 2023 ([doi:10.1371/journal.pone.0283342](https://doi.org/10.1371/journal.pone.0283342)), BioBERT **title+abstract**:

| Metric | BioBERT | Jev hybrid |
|--------|---------|------------|
| Accuracy | **96.37%** | **89.5%** |
| F1 (RCT) | **90.85%** | **88.40%** |

Demo set: **200** abstracts, stratified **100 RCT / 100 non_RCT** from the Bat4RCT **test** split (paper split 80/10/10, `random_state=42`; demo subsample seed `20260916`).

## Film path — UI v2 (grid + parallel hybrid Jev)

```bash
# 1) one-time setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# API key (never commit):
export TYPESAFE_API_KEY="$(tr -d '\n' < ~/.config/typesafe/api_key)"

# 2) ensure demo CSV exists (committed under data/demo_200.csv)
python -m src.prepare_demo   # only if regenerating

# 3) web UI
python -m src.serve --port 8765
# open http://127.0.0.1:8765/
# → Start = live parallel hybrid Jev (default 8 workers)
# → Replay cached = animate from results/predictions.csv (hybrid film cache; no API credits)
```

Optional live recompute: `python -m src.run_eval --workers 8` writes `results/predictions.csv` + `results/metrics.json`.

CLI film strip: `python -m src.cli --limit 16 --delay 0.4`

Dry-run (no API key): `python -m src.run_eval --dry-run`

### UI v2 behavior

1. **Grid of all 200** pubs as dense blocks.
2. **Start** fires `POST /api/classify` with **client-capped concurrency** (default **8**).
3. After each result:
   - **green** = agree with gold **and** confidence ≥ 0.55
   - **red** = disagree **and** confidence ≥ 0.55
   - **amber** = confidence **< 0.55** (agree *or* disagree)
4. **Click a block** → detail: title, abstract, **hybrid pred**, **Choice**, probabilities, confidence, **each noul**, gold, agree/disagree.
5. **Scoreboard**: Acc / F1 / mean latency vs BioBERT **96.37%** / **90.85%** (hybrid film cache settles at **89.5%** / **88.4%**).

### Amber rule

**Confidence < 0.55 → amber**, whether the prediction agrees or disagrees with gold.
Threshold: `AMBER_CONF = 0.55` in `web/app.js`.

### API

| Endpoint | Purpose |
|----------|---------|
| `GET /api/demo` | 200 rows from `data/demo_200.csv` |
| `POST /api/classify` | hybrid pred + full `answers` (choice, probs, confidence, each noul) |
| `GET /api/predictions` | cached CSV for **Replay cached** |
| `GET /api/metrics` | last batch metrics.json |

## What Jev returns (hybrid)

`POST https://api.typesafe.ai/v1/systemone` · model `jev-latest` · `questions` is a **map**:

- **Choice** `label` — **CD medium** wording (not the longer R2 choice rewrite)
- **Noul** `has_random_allocation`, `parallel_intervention_arms`, `is_cluster_random`
- **Noul** `is_secondary_or_nested_only`, `is_protocol_or_single_arm` (exclude gates)

Server applies the hybrid combine in `src/hybrid.py` (aggressive disabled).

## Layout

```
data/demo_200.csv
src/hybrid.py           # CD Choice + noul combine (default)
src/jev_client.py       # System One client (hybrid questions)
src/run_eval.py         # live/dry runner → CSV + metrics
src/serve.py + web/     # UI v2 grid + live parallel classify
results/predictions.csv # hybrid film cache (89.5% / 88.40%)
results/metrics.json
results/round2/         # ANALYSIS, questions_v2, preds_round2, summary_hybrid, …
```

## Auth

```bash
export TYPESAFE_API_KEY=…          # preferred
# or ~/.config/typesafe/api_key (mode 600)
```

**Never commit the API key.** `.gitignore` excludes `api_key`, `.env`, and raw Bat4RCT zip/txt.

## Cite

- Kim et al. Bat4RCT. PLOS ONE 2023. https://doi.org/10.1371/journal.pone.0283342
- Data/code: https://github.com/jennak22/Bat4RCT
- TypeSafe docs: https://docs.typesafe.ai/introduction
