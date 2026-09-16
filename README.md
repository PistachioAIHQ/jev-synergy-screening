# Jev × SYNERGY — human systematic-review screening

Viral life-sciences demo: screen **title + abstract** as **include vs exclude** with [TypeSafe Jev](https://docs.typesafe.ai/introduction) (System One), compared to **human gold labels** from [ASReview SYNERGY](https://github.com/asreview/synergy-dataset) (CC0).

**Gold story = human systematic-review screening — not MEDLINE publication type.**

Optional mode: **Bat4RCT** r3_ship (MEDLINE PT RCT tagging) remains available in the UI mode toggle.

## Review pick: Donners_2021

| | |
|--|--|
| Review | Donners et al., *Clin Pharmacokinet* 2021 — emicizumab PK / PK–PD in humans |
| Key | `Donners_2021` |
| N | **258** records · **15** included (5.8%) |
| Why | Smallest medicine SYNERGY review with clear eligibility text; fits a ~200-grid film **without** subsampling. Fallbacks considered: Nelson_2002 (N=366, thinner criteria), Meijboom_2021 (N=882 — too big). |
| Eligibility (SYNERGY metadata) | *emicizumab studies providing (1) data on humans, (2) original PK data or modeled PK data or PK/PD relationships, and (3) access to the abstract and the full text in English.* |
| DOI | [10.1007/s40262-021-01042-w](https://doi.org/10.1007/s40262-021-01042-w) |

Committed demo table: `data/donners_258.csv` (+ `data/donners_metadata.json`, `data/SYNERGY_LICENSE_NOTE.md`).

## Default rule: Choice ∩ eligibility nouls

**Choice** `include` \| `exclude` encodes Donners criteria, plus atomic **Nouls** (shown in Questions drawer). Shipped combine (one iteration after Choice-only):

```
include iff choice==include
  AND mentions_emicizumab>=0.5
  AND is_human_data>=0.5
  AND reports_pk_or_pkpd>=0.5
  AND is_secondary_without_pk<0.5
```

| Variant | Acc | F1 (include) | TP/FP/FN/TN |
|---------|-----|--------------|-------------|
| Choice-only (not shipped) | 86.82% | 39.29% | 11/30/4/213 |
| **Shipped (Choice ∧ nouls)** | **91.86%** | **48.78%** | **10/16/5/227** |

Precision/Recall (include): **38.46% / 66.67%**. Mean latency ~**517 ms**. Est. cost ~**$0.013** @ $0.042/MTok input (output free) for full N=258.

> Class is sparse (5.8% include). Acc stays high; F1 is limited by abstract-only PK cues (several gold includes barely mention PK).

Implemented in `src/synergy_screening.py` + `src/jev_client.py`.

## Film path (default = SYNERGY)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export TYPESAFE_API_KEY="$(tr -d '\n' < ~/.config/typesafe/api_key)"

# live eval → results/predictions.csv + results/metrics.json
python -m src.run_synergy_eval --workers 8

# UI
python -m src.serve --port 8765
# open http://127.0.0.1:8765/
# → Mode = SYNERGY (Donners)  [default]
# → Start = live parallel Jev
# → Replay cached = animate results/predictions.csv
# → Questions = Choice/Noul map + combine + eligibility block quote
# → Mode = Bat4RCT (MEDLINE PT) for optional r3_ship demo
```

Dry-run: `python -m src.run_synergy_eval --dry-run`

### UI behavior

1. Grid of all **258** Donners records (dense blocks).
2. **Start** → `POST /api/classify` with `mode=synergy` (concurrency selectable).
3. Green agree / red disagree / amber conf &lt; 0.55.
4. Click → title, abstract, combine pred, Choice, probs, each noul, gold, $, latency.
5. Scoreboard: Acc / F1 (include) / mean latency / wall / est. $.
6. Mode toggle → Bat4RCT optional (200 pubs, BioBERT bar, `results/bat4rct/`).

### API

| Endpoint | Purpose |
|----------|---------|
| `GET /api/demo?mode=synergy\|bat4rct` | demo rows |
| `GET /api/questions?mode=…` | question map + combine |
| `POST /api/classify` | body includes `mode` |
| `GET /api/predictions?mode=…` | film cache |
| `GET /api/metrics?mode=…` | last metrics |
| `GET /api/health` | modes + rules |

### Jev

`POST https://api.typesafe.ai/v1/systemone` · model `jev-latest` · `questions` is a **map** (Choice + Nouls). No free-text generation.

## Optional: Bat4RCT (MEDLINE PT)

Still shipped under mode **Bat4RCT**:

- Data: `data/demo_200.csv` (100 RCT / 100 non_RCT)
- Rule: r3_ship (CD Choice + round-3 nouls) — Acc **93.5%** / F1 **93.12%** vs BioBERT 96.37% / 90.85%
- Cache: `results/bat4rct/predictions.csv`
- Eval: `python -m src.run_eval --workers 8`

## Layout

```
data/donners_258.csv          # SYNERGY default (committed)
data/donners_metadata.json
data/demo_200.csv             # Bat4RCT optional
src/synergy_screening.py      # Donners questions + combine
src/jev_client.py             # classify_synergy / classify_bat4rct
src/run_synergy_eval.py       # default film runner
src/serve.py + web/           # dual-mode UI
results/predictions.csv       # SYNERGY film cache
results/bat4rct/              # optional MEDLINE PT cache
```

## Auth

```bash
export TYPESAFE_API_KEY=…          # preferred
# or ~/.config/typesafe/api_key
```

**Never commit the key.**

## Rebuilding Donners from SYNERGY (optional)

```bash
pip install 'synergy-dataset==1.2'
python -c "from synergy_dataset.base import download_raw_subset; download_raw_subset('Donners_2021')"
# then export title/abstract/label_included → data/donners_258.csv
```

Classic SYNERGY source: doi:10.34894/HE6NAQ (CC0).
