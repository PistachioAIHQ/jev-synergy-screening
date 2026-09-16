from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
WEB_DIR = ROOT / "web"

BAT4RCT_ZIP_URL = "https://github.com/jennak22/Bat4RCT/raw/main/rct_data.zip"
BAT4RCT_TXT = DATA_DIR / "rct_data" / "rct_data.txt"
DEMO_CSV = DATA_DIR / "demo_200.csv"
PREDICTIONS_CSV = RESULTS_DIR / "predictions.csv"
METRICS_JSON = RESULTS_DIR / "metrics.json"

# Paper / Bat4RCT modules.py split
SPLIT_SEED = 42
TEST_SIZE = 0.2
VAL_OF_HOLD = 0.5  # second split → 10% val / 10% test

# Demo subsample from test
DEMO_SEED = 20260916
DEMO_PER_CLASS = 100

BIOBERT_F1 = 0.9085
BIOBERT_ACC = 0.9637

JEV_URL = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = "jev-latest"

LABEL_RCT = "RCT"
LABEL_NON = "non_RCT"
