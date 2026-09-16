# Round3 vs Hybrid (Bat4RCT n=200)

| Variant | Acc | F1 | Prec | Rec | TP | FP | FN | TN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Hybrid R2 | 89.5% | 88.40% | 98.77% | 80% | 80 | 1 | 20 | 99 |
| R3 reports alone | 92.0% | 91.40% | 98.84% | 85% | 85 | 1 | 15 | 99 |
| R3+psych@0.5 (no ship) | 93.0% | 92.63% | 97.78% | 88% | 88 | 2 | 12 | 98 |
| **R3 ship (default)** | **93.5%** | **93.12%** | **98.88%** | **88%** | **88** | **1** | **12** | **99** |

**SHIP `r3_ship` as default.** Do **not** ship psych OR at 0.5 (FP=2).

Rule:
```
RCT iff choice==RCT
  OR ((rand|cluster|parallel)>=0.5 AND secondary<0.5 AND protocol_single_arm<0.5)
  OR (reports_or_reanalyzes_an_rct>=0.5 AND is_review_or_meta<0.5)
  OR (experimental_allocation_implied>=0.95 AND secondary<0.5 AND protocol<0.5 AND review<0.5)
```

Recovered vs hybrid (8): 22093067, 22248375, 23312232, 25888270, 26863870, 28038841, 28703621, 32534135
