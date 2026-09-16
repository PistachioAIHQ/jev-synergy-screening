# Failure analysis — Cohen ADHD r2

## Error clusters (baseline FULL N=851, pred combine)

### FP clusters by Cohen abs_reason (n=23)
| Code | Meaning | n | Pattern |
|------|---------|--:|---------|
| 5 | Wrong publication type | 8 | Drug monographs/product profiles (`Atomoxetine.`, `Dexmethylphenidate.`, OROS/Ritalin LA reviews) — `wrong_publication_type` scored only ~0.16–0.23 |
| E | Excluded (unspecified/other) | 6 | Borderline clinical trials Cohen excluded at abstract triage |
| 2 | Wrong outcome | 5 | fMRI/EEG/CSF/biomarker endpoints without clinical ADHD scales |
| 6 | Wrong study design | 3 | Formulation development; comorbid NF1 observational; methods |
| 3 | Wrong drug | 1 | Stimulant response predictors without listed-drug focus |

### FN clusters (n=30 includes missed)
- **20/30** had `choice=include` but were **vetoed by Nouls**:
  - `inadequate_study_duration` alone: 7 (acute classroom/lab studies over-penalized)
  - `out+dur`: 5; `out` alone: 4; `drug`: 2; `pop`: 1
- **10/30** had `choice=exclude` (true choice misses): acquired ADHD after brain injury; classroom reinforcer EO studies; GH/diabetes comorbidity; conduct disorder with ADHD drugs; cognitive naming-speed endpoints.

## Proposed Noul changes (implemented in questions_r2.json)
| Change | Cohen code | Rationale |
|--------|------------|-----------|
| Rewrote `wrong_publication_type` to include monographs/product profiles | 5 | Kill Atomoxetine./OROS FP cluster |
| Rewrote `eligible_outcome` — LOW for imaging/biomarker-only | 2 | Kill fMRI vermis / EEG FPs; allow classroom function |
| Rewrote `inadequate_study_duration` — only single-dose PK-only | 7 | Stop vetoing acute clinical ADHD trials |
| Rewrote `eligible_population` — allow acquired/secondary attention disorders | 4 | Recover brain-injury MPH FN |
| NEW `is_drug_monograph_or_product_profile` | 5 | Atomic FP gate |
| NEW `is_imaging_or_biomarker_only` | 2 | Atomic FP gate |
| NEW `is_formulation_dev_without_efficacy` | 6 | Atomic FP gate |
| Soften combine thresholds (pop≥0.4, out≥0.35, dur<0.85, pub<0.4) | — | Recover duration/outcome veto FNs without reopening all FPs |

## Ship vs alternatives
| Rule | H2H F1 | Film F1 | Full F1 | Verdict |
|------|-------:|--------:|--------:|---------|
| BASELINE | 72.7 | 59.1 | 67.1 | — |
| **r2_ship** | **100.0*** | **66.7** | **75.3** | **Ship** |
| choice_plus_fp_gates | 95.2 | 70.4 | 73.6 | More FPs on full |
| offline choice_not_pub_0.4 | 72.7 | 69.2 | 75.1 | Schema-light fallback |

\*H2H 100% is not a reliable claim — N=10 positives.
