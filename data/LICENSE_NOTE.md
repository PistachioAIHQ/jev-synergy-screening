# Dataset license note

This demo uses **Bat4RCT** (Kim et al., PLOS ONE 2023):

- Paper: https://doi.org/10.1371/journal.pone.0283342
- Source: https://github.com/jennak22/Bat4RCT
- License: see upstream LICENSE (GPLv3)

Raw `rct_data.zip` is **not** vendored in this repo (large). Download with:

```bash
python -m src.prepare_demo
```

The committed file `data/demo_200.csv` is a fixed stratified 200-row slice (100 RCT / 100 non-RCT) drawn from the Bat4RCT **test** split (paper split: 80/10/10, `random_state=42`).
