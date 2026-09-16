from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
WEB_DIR = ROOT / "web"

BAT4RCT_ZIP_URL = "https://github.com/jennak22/Bat4RCT/raw/main/rct_data.zip"
BAT4RCT_TXT = DATA_DIR / "rct_data" / "rct_data.txt"
DEMO_CSV = DATA_DIR / "demo_200.csv"  # Bat4RCT stratified 200
DONNERS_CSV = DATA_DIR / "donners_258.csv"  # SYNERGY default

# Default film path = SYNERGY Donners
PREDICTIONS_CSV = RESULTS_DIR / "predictions.csv"
METRICS_JSON = RESULTS_DIR / "metrics.json"
BAT4RCT_PREDICTIONS_CSV = RESULTS_DIR / "bat4rct" / "predictions.csv"
BAT4RCT_METRICS_JSON = RESULTS_DIR / "bat4rct" / "metrics.json"

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

# Bat4RCT labels
LABEL_RCT = "RCT"
LABEL_NON = "non_RCT"

# SYNERGY screening labels
LABEL_INCLUDE = "include"
LABEL_EXCLUDE = "exclude"

DEFAULT_MODE = "synergy"  # primary film path
