# Jev prompt/criteria ablations (Bat4RCT demo_200)

Fixed set: `data/demo_200.csv` (n=200). Baseline to beat: Acc **87.0%** / F1 **85.2%**.

Score rubric mapping: levels `clearly not RCT` (0) / `ambiguous` (1) / `clearly RCT` (2); **pred = RCT iff score ≥ 1.5**.

| variant | Acc | F1_RCT | Prec | Rec | mean_lat_ms | coverage | notes |
|---|---:|---:|---:|---:|---:|---:|---|
| baseline | 87.0% | 85.2% | 98.7% | 75.0% | 535 | 100.0% |  |
| stronger_criteria | 82.5% | 79.0% | 98.5% | 66.0% | 520 | 100.0% |  |
| dual_gate_τ=0.5 | 83.0% | 79.8% | 98.5% | 67.0% | 535 | 100.0% | τ=0.5; choice=RCT ∧ noul_completed≥τ |
| dual_gate_τ=0.6 | 83.0% | 79.8% | 98.5% | 67.0% | 535 | 100.0% | τ=0.6; choice=RCT ∧ noul_completed≥τ |
| dual_gate_τ=0.7 | 82.5% | 79.0% | 98.5% | 66.0% | 535 | 100.0% | τ=0.7; choice=RCT ∧ noul_completed≥τ |
| dual_gate_τ=0.8 | 82.0% | 78.3% | 98.5% | 65.0% | 535 | 100.0% | τ=0.8; choice=RCT ∧ noul_completed≥τ |
| score_rubric | 82.5% | 79.0% | 98.5% | 66.0% | 510 | 100.0% | score≥1.5→RCT |
| title_only | 73.5% | 64.4% | 98.0% | 48.0% | 491 | 100.0% |  |
| title_abstract | 87.0% | 85.2% | 98.7% | 75.0% | 535 | 100.0% |  |
| conf_gate_τ=0.5 | 88.5% | 86.4% | 98.6% | 76.9% | 536 | 95.5% | τ=0.5; among conf≥τ |
| conf_gate_τ=0.6 | 88.5% | 86.4% | 98.6% | 76.9% | 536 | 95.5% | τ=0.6; among conf≥τ |
| conf_gate_τ=0.7 | 88.9% | 86.8% | 98.6% | 77.5% | 536 | 94.5% | τ=0.7; among conf≥τ |
| conf_gate_τ=0.8 | 89.3% | 87.2% | 98.6% | 78.2% | 536 | 93.5% | τ=0.8; among conf≥τ |

