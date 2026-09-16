# Round-2 analysis: why cold Jev misses RCTs (Bat4RCT n=200)

## Baseline (best choice-only)
**CD medium choice instructions, choice-only** (no noul gate): Acc **87.00%** / F1 **85.23%** · TP/FP/FN/TN = **75/1/25/99**.

A short baseline was Acc 86.5% (26 FN); CD recovers one of A's FNs (PMID 32816829).

## Root cause
Bat4RCT gold is **MEDLINE Publication Type = RCT**, not “abstract clearly describes randomization.”
Cold Jev only sees title+abstract → systematic miss when:
1. Abstract omits random*/allocation language but PT is RCT
2. Abstract is secondary/nested/screening/reanalysis of a parent RCT (still PT=RCT)
3. Cluster RCT text emphasizes that *patient-level* randomization was not feasible
4. Explicit observational/retrospective/single-arm wording (PT–abstract mismatch)

Single FP (PMID 26246884) is a clear telephone-support PPD RCT — precision is already ~99%.

## FN cluster counts (CD choice-only, n=25)

| Cluster | Count | Hybrid recovered |
|---|---:|---:|
| Silent parallel-arm trial (allocation omitted; recoverable) | 4 | 4 |
| Cluster/site RCT with “not patient-randomized” disclaimer | 1 | 1 |
| Secondary / nested / screening / reanalysis mentioning parent RCT | 6 | 0 |
| Abstract reads observational / retrospective / single-arm / Phase I | 11 | 0 |
| Psychology lab “Experiment N” without random* language | 2 | 0 |
| Within-subject experimental comparison, allocation silent | 1 | 0 |
| **Total** | **25** | **5** |

## Proposed multi-question battery (atomic Choice + Noul)

See `questions_v2.json`. Fields:

1. **choice `label`** — medium RCT/non_RCT (prefer **CD wording**, not the longer R2 rewrite which lost 7 TPs)
2. **noul `has_random_allocation`** — explicit random*/randomised allocation (not “randomly selected” sampling)
3. **noul `parallel_intervention_arms`** — prospective parallel intervention vs control/comparison
4. **noul `is_cluster_random`** — site/cluster randomization
5. **noul `is_secondary_or_nested_only`** — secondary/screening/qualitative nested/reanalysis only
6. **noul `is_protocol_or_single_arm`** — protocol-only or single-arm/dose-escalation/historical-control

### Recommended combine rule (hybrid; threshold 0.5)
```
pred = RCT  if  choice == RCT
             OR (
                  (has_random_allocation >= 0.5
                   OR is_cluster_random >= 0.5
                   OR parallel_intervention_arms >= 0.5)
                  AND is_secondary_or_nested_only < 0.5
                  AND is_protocol_or_single_arm < 0.5
                )
      else non_RCT
```
Keep CD choice for the Choice question; use R2 atomic nouls only as OR-in recoveries with exclude gates.

### Aggressive variant (drops secondary exclude)
Recovers +3 more secondary/nested FNs but **adds 1 FP** (FP=2) — not preferred.

## Round-2 live results (full n=200, 0 errors)

| Variant | Acc | F1 | Prec | Rec | TP | FP | FN | TN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CD choice-only (baseline) | 87.0% | 85.23% | 98.68% | 75% | 75 | 1 | 25 | 99 |
| R2 choice-only (long instructions) | 85.0% | 82.56% | 98.61% | 71% | 71 | 1 | 29 | 99 |
| R2 native combine | 86.0% | 83.91% | 98.65% | 73% | 73 | 1 | 27 | 99 |
| **Hybrid CD choice + R2 nouls** | **89.5%** | **88.40%** | **98.77%** | **80%** | **80** | **1** | **20** | **99** |
| Aggressive (no secondary exclude) | 90.5% | 89.73% | 97.65% | 83% | 83 | 2 | 17 | 98 |

Recovered FNs (hybrid, FP unchanged): 27774458, 22139387, 24969152, 23758106, 26697137  
(all silent-parallel or cluster).

Mean latency R2 ≈ 529 ms (similar to CD).

## Recommendation
Ship **hybrid**: CD medium choice + three positive nouls + two exclude nouls. Do not replace choice with the longer R2 prompt. Remaining ~20 FN are mostly PT–abstract mismatches (observational/secondary wording) that cold abstract screening cannot and arguably should not force to RCT without hurting precision.
