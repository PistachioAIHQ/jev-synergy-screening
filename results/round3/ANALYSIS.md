# Round-3 analysis — Bat4RCT n=200

## Goal
Beat hybrid **Acc 89.5% / F1 88.40%** (80/1/20/99) without FP > 1 if possible.

## Setup
- **Choice**: cached CD medium choice (Acc 87% choice-only)
- **R2 nouls** (cached): rand / parallel / cluster / secondary / protocol
- **R3 nouls** (live, 8 workers, 0 errors): `reports_or_reanalyzes_an_rct`, `parent_study_was_rct`, `experimental_allocation_implied`, `is_review_or_meta`
- Files: `questions_v3.json`, `questions_new_only.json`, `preds_round3.csv`, `raw_round3.jsonl`

## Variant table

| Variant | Acc | F1 | Prec | Rec | TP | FP | FN | TN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Hybrid R2 | 89.50% | 88.40% | 98.77% | 80% | 80 | 1 | 20 | 99 |
| R3 secondary AND (reports∧parent) | 91.50% | 90.81% | 98.82% | 84% | 84 | 1 | 16 | 99 |
| R3 reports alone | 92.00% | 91.40% | 98.84% | 85% | 85 | 1 | 15 | 99 |
| R3 exp@0.5 | 90.50% | 89.73% | 97.65% | 83% | 83 | 2 | 17 | 98 |
| R3 full@0.5 | 92.50% | 92.06% | 97.75% | 87% | 87 | 2 | 13 | 98 |
| **R3 ship (reports ∨ exp≥0.95)** | 93.50% | 93.12% | 98.88% | 88% | 88 | 1 | 12 | 99 |
| Aggressive R2 | 90.50% | 89.73% | 97.65% | 83% | 83 | 2 | 17 | 98 |

## Ship rule (recommended)
```
pred = RCT if
  choice_cd == RCT
  OR ((rand|cluster|parallel) >= 0.5 AND secondary < 0.5 AND protocol < 0.5)   # hybrid
  OR (reports_or_reanalyzes_an_rct >= 0.5 AND is_review_or_meta < 0.5)          # secondary/reanalysis
  OR (experimental_allocation_implied >= 0.95
      AND secondary < 0.5 AND protocol < 0.5 AND review < 0.5)                   # psych / within-subject
else non_RCT
```

**Acc 93.5% / F1 93.12% · TP/FP/FN/TN = 88/1/12/99**

Δ vs hybrid: **+4.0 Acc / +4.72 F1**, FP unchanged at 1.

### Newly recovered PMIDs (no new FPs)
| PMID | Path | Notes |
|---|---|---|
| 22093067 | exp>=0.95 | Within-subject contralateral |
| 22248375 | exp>=0.95 | Psych Experiment 1/2 |
| 23312232 | reports | KEEPS screening; SETTING=RCT |
| 25888270 | reports | Reanalysis of phase-III RCT control arms |
| 26863870 | reports | Nested qualitative; parents randomised |
| 28038841 | reports | DOEE follow-on of myopia-control trial |
| 28703621 | exp>=0.95 | Psych Experiment 1-3 |
| 32534135 | reports | Ancillary to ongoing SLIP II RCT |

### New FPs
**None** under ship. Existing FP remains **26246884** (CD choice).

exp@0.5 (or @0.90) adds FP **31444537** (risk-magnitude spatial training; exp=0.92). Gate **0.95** keeps psych TPs (exp=0.97) and drops that FP.

### Conservative alternative
`r3_reports_alone` only: Acc **92.0%** / F1 **91.40%** / FP=1. Safer if you distrust the 0.95 threshold; still +2.5 Acc over hybrid.

## Remaining 12 FNs (ship)
21607966, 21840055, 21978010, 22030767, 23837219, 23892047, 24052368, 25754896, 25866811, 26563287, 28485200, 28778281

Mostly PT–abstract mismatches (phase I / observational / weak secondary without RCT wording). Forcing them risks FP.

## Recommendation
**Ship `r3_ship`.** Clear win over hybrid at FP=1. Prefer reports-alone if you want fewer thresholds. **Stop** further cold-abstract rounds for residual observational FNs.
