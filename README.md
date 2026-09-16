# Jev × Bat4RCT — RCT screening demo

Viral life-sciences demo: classify MEDLINE **title + abstract** as **RCT vs non_RCT** with [TypeSafe Jev](https://docs.typesafe.ai/introduction) (System One), compare to gold labels from **Bat4RCT**, and scoreboard against the paper’s **BioBERT** baseline.

> Repo name is historical (`jev-synergy-screening`); **v1 dataset is Bat4RCT**, not SYNERGY.

## Default rule: r3_ship (NOT psych@0.5)

**CD medium Choice** + round-3 nouls (`results/round3/questions_v3.json`), combined as:

```
RCT iff choice==RCT
  OR ((rand|cluster|parallel)>=0.5 AND secondary<0.5 AND protocol<0.5)
  OR (reports_or_reanalyzes_an_rct>=0.5 AND is_review_or_meta<0.5)
  OR (experimental_allocation_implied>=0.95 AND secondary<0.5 AND protocol<0.5 AND review<0.5)
```

Implemented in `src/hybrid.py` + `src/jev_client.py`. **Psych OR at 0.5 is not shipped** (FP=2).

| Variant | Acc | F1 | TP/FP/FN/TN |
|---------|-----|----|-------------|
| CD choice-only | 87.00% | 85.23% | 75/1/25/99 |
| Hybrid R2 | 89.5% | 88.40% | 80/1/20/99 |
| **r3_ship (default)** | **93.5%** | **93.12%** | **88/1/12/99** |
| Psych@0.5 (not shipped) | 93.0% | 92.63% | 88/2/12/98 |

Δ vs hybrid R2: **+4.0 pp Acc / +4.72 pp F1**, FP unchanged (1).

## BioBERT bar (on-screen)

From Kim et al., *PLOS ONE* 2023 ([doi:10.1371/journal.pone.0283342](https://doi.org/10.1371/journal.pone.0283342)), BioBERT **title+abstract**:

| Metric | BioBERT | Jev r3_ship |
|--------|---------|-------------|
| Accuracy | **96.37%** | **93.5%** |
| F1 (RCT) | **90.85%** | **93.12%** |

Demo set: **200** abstracts, stratified **100 RCT / 100 non_RCT** from the Bat4RCT **test** split.

## Cost & time (UI)

Scoreboard shows **mean latency**, **wall time**, and **estimated $** at **$0.042 / MTok input** (output free).
- **Start (live):** uses `usage.input_tokens` from each Jev response when present.
- **Replay cached:** film cache has no live usage log; UI uses `input_tokens_est` (char/4 + question overhead) and labels it **est**.

## Film path — UI v2 (grid + questions drawer)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export TYPESAFE_API_KEY="$(tr -d '\n' < ~/.config/typesafe/api_key)"
python -m src.serve --port 8765
# open http://127.0.0.1:8765/
# → Start = live parallel r3_ship Jev
# → Replay cached = animate results/predictions.csv (no API credits)
# → Questions = full Choice/Noul map + combine rule
```

### UI v2 behavior

1. **Grid of all 200** pubs as dense blocks.
2. **Start** fires `POST /api/classify` with client-capped concurrency (default **8**).
3. After each result: **green** agree (conf ≥ 0.55), **red** disagree (conf ≥ 0.55), **amber** conf < 0.55.
4. **Click a block** → detail: title, abstract, combine pred, Choice, probs, confidence, **each noul answer**, gold, agree/disagree, tokens/cost.
5. **Questions** drawer: every Choice/Noul (instructions + criteria) + the code combine rule.
6. **Scoreboard**: Acc / F1 (with F1 gloss) / mean latency / wall time / est. cost vs BioBERT **96.37%** / **90.85%** (film settles at **93.5%** / **93.12%**).

### Amber rule

**Confidence < 0.55 → amber**, whether the prediction agrees or disagrees with gold.

### API

| Endpoint | Purpose |
|----------|---------|
| `GET /api/demo` | 200 rows from `data/demo_200.csv` |
| `GET /api/questions` | full r3 question map + combine string |
| `POST /api/classify` | r3_ship pred + answers + usage/cost |
| `GET /api/predictions` | cached CSV for **Replay cached** |
| `GET /api/metrics` | last batch metrics.json |

## What Jev returns (r3_ship)

`POST https://api.typesafe.ai/v1/systemone` · model `jev-latest` · `questions` is a **map**:

- **Choice** `label` — CD medium wording
- **Noul** R2: `has_random_allocation`, `parallel_intervention_arms`, `is_cluster_random`, `is_secondary_or_nested_only`, `is_protocol_or_single_arm`
- **Noul** R3: `reports_or_reanalyzes_an_rct`, `parent_study_was_rct`, `experimental_allocation_implied`, `is_review_or_meta`

Server applies `hybrid_combine` in `src/hybrid.py` (aggressive off; exp gate **0.95**).

## Layout

```
data/demo_200.csv
src/hybrid.py           # r3_ship combine (default)
src/jev_client.py       # System One client (round-3 questions)
src/run_eval.py         # live/dry runner → CSV + metrics
src/serve.py + web/     # UI v2 grid + questions drawer + cost/time
results/predictions.csv # r3_ship film cache (93.5% / 93.12%)
results/metrics.json
results/round3/         # ANALYSIS, questions_v3, preds_round3, summary_round3, …
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
