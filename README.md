# Jev × Bat4RCT — RCT screening demo

Viral life-sciences demo: classify MEDLINE **title + abstract** as **RCT vs non_RCT** with [TypeSafe Jev](https://docs.typesafe.ai/introduction) (System One), compare to gold labels from **Bat4RCT**, and scoreboard against the paper’s **BioBERT** baseline.

> Repo name is historical (`jev-synergy-screening`); **v1 dataset is Bat4RCT**, not SYNERGY.

## Baseline (on-screen bar)

From Kim et al., *PLOS ONE* 2023 ([doi:10.1371/journal.pone.0283342](https://doi.org/10.1371/journal.pone.0283342)), BioBERT **title+abstract**:

| Metric | BioBERT |
|--------|---------|
| Accuracy | **96.37%** |
| F1 (RCT) | **90.85%** |

Demo set: **200** abstracts, stratified **100 RCT / 100 non_RCT** from the Bat4RCT **test** split (paper split 80/10/10, `random_state=42`; demo subsample seed `20260916`).

## Film path — UI v2 (grid + parallel Jev)

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
# → Start = live parallel Jev (default 8 workers; map-reduce wave on 200 blocks)
# → Replay cached = animate from results/predictions.csv (no API credits)
```

Optional offline cache for rehearsal: `python -m src.run_eval --workers 8` writes `results/predictions.csv` + `results/metrics.json`.

CLI film strip: `python -m src.cli --limit 16 --delay 0.4`

Dry-run (no API key): `python -m src.run_eval --dry-run`

### UI v2 behavior

1. **Grid of all 200** pubs as dense blocks (not a table / not a one-at-a-time card lane).
2. **Start** fires `POST /api/classify` with **client-capped concurrency** (default **8** workers). Blocks light up in waves (running → settle).
3. After each result:
   - **green** = agree with gold **and** confidence ≥ 0.55
   - **red** = disagree **and** confidence ≥ 0.55
   - **amber** = confidence **< 0.55** (agree *or* disagree) — low-confidence highlight
4. **Click a block** → detail panel: title, abstract, Jev Choice + probabilities + confidence (+ noul if present), gold RCT/non_RCT, agree/disagree.
5. **Persistent scoreboard**: Acc / F1 / mean latency vs BioBERT **96.37%** / **90.85%**, updating live as results arrive.

### Amber rule (documented)

**Confidence < 0.55 → amber**, whether the prediction agrees or disagrees with gold.
Green/red are reserved for confident agree/disagree (≥ 0.55). Threshold constant: `AMBER_CONF = 0.55` in `web/app.js`.

### API

| Endpoint | Purpose |
|----------|---------|
| `GET /api/demo` | 200 rows from `data/demo_200.csv` (pmid, title, abstract, gold) |
| `POST /api/classify` | body `{title, abstract, pmid}` → Jev via `src/jev_client.py` → pred, probs, confidence, noul, latency_ms |
| `GET /api/predictions` | cached CSV for **Replay cached** |
| `GET /api/metrics` | last batch metrics.json |

Server uses `ThreadingHTTPServer` so parallel `POST /api/classify` calls run concurrently; the browser caps worker count.

## What Jev returns

`POST https://api.typesafe.ai/v1/systemone` · model `jev-latest` · `questions` is a **map**:

- **Choice** `label`: `RCT` | `non_RCT` (+ criteria)
- **Noul** `is_rct_statement`: “This abstract reports a randomized controlled trial”

No rationale / free-text generation.

## Layout

```
data/demo_200.csv       # fixed 200-row demo (committed)
data/LICENSE_NOTE.md    # Bat4RCT attribution
src/bat4rct.py          # loader + paper splits + stratified 200
src/jev_client.py       # System One client
src/run_eval.py         # live/dry runner → CSV + metrics
src/cli.py              # screenable terminal demo
src/serve.py + web/     # UI v2: 200-block grid + live parallel classify
results/                # predictions.csv, metrics.json (from last live run)
```

## Live results (demo_200 batch)

Recorded in `results/metrics.json` / `results/predictions.csv` (batch eval, not required for Start):

| | Jev (live) | BioBERT (paper bar) |
|---|------------|---------------------|
| Accuracy | **87.00%** | 96.37% |
| F1 (RCT) | **85.23%** | 90.85% |
| Mean latency | **544 ms** | — |

Confusion (RCT positive): TP=75 FP=1 FN=25 TN=99. High precision, lower recall on this 200-row slice.

## Auth

```bash
export TYPESAFE_API_KEY=…          # preferred
# or
mkdir -p ~/.config/typesafe && chmod 700 ~/.config/typesafe
# put key in ~/.config/typesafe/api_key (mode 600)
```

**Never commit the API key.** `.gitignore` excludes `api_key`, `.env`, and raw Bat4RCT zip/txt.

## Cite

- Kim et al. Bat4RCT. PLOS ONE 2023. https://doi.org/10.1371/journal.pone.0283342
- Data/code: https://github.com/jennak22/Bat4RCT
- TypeSafe docs: https://docs.typesafe.ai/introduction
