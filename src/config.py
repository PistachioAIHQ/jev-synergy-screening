from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
WEB_DIR = ROOT / "web"

# --- Primary: Cohen ADHD Abstract Triage ---
ADHD_CSV = DATA_DIR / "adhd_851.csv"
ADHD_FILM_CSV = DATA_DIR / "adhd_film_200.csv"  # seed 20260917 stratified
ADHD_H2H_CSV = DATA_DIR / "adhd_h2h_100.csv"  # seed 20260916 stratified
ADHD_META = DATA_DIR / "adhd_metadata.json"
PREDICTIONS_CSV = RESULTS_DIR / "predictions.csv"
METRICS_JSON = RESULTS_DIR / "metrics.json"
H2H_DIR = RESULTS_DIR / "h2h"

FILM_SEED = 20260917
H2H_SEED = 20260916
FILM_N = 200
H2H_N = 100

# Optional Bat4RCT
BAT4RCT_ZIP_URL = "https://github.com/jennak22/Bat4RCT/raw/main/rct_data.zip"
BAT4RCT_TXT = DATA_DIR / "rct_data" / "rct_data.txt"
DEMO_CSV = DATA_DIR / "demo_200.csv"
BAT4RCT_PREDICTIONS_CSV = RESULTS_DIR / "bat4rct" / "predictions.csv"
BAT4RCT_METRICS_JSON = RESULTS_DIR / "bat4rct" / "metrics.json"

# Optional / dead path: SYNERGY Donners
DONNERS_CSV = DATA_DIR / "donners_258.csv"

SPLIT_SEED = 42
TEST_SIZE = 0.2
VAL_OF_HOLD = 0.5
DEMO_SEED = 20260916
DEMO_PER_CLASS = 100

BIOBERT_F1 = 0.9085
BIOBERT_ACC = 0.9637

JEV_URL = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = "jev-latest"
INPUT_USD_PER_MTOK = 0.042
OUTPUT_USD_PER_MTOK = 0.0

ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"
ANTHROPIC_INPUT_USD_PER_MTOK = 3.0
ANTHROPIC_OUTPUT_USD_PER_MTOK = 15.0

# Claude Opus 5 (H2H second Anthropic arm; do not overwrite Sonnet predictions)
OPUS_MODEL = "claude-opus-5"
OPUS_INPUT_USD_PER_MTOK = 5.0
OPUS_OUTPUT_USD_PER_MTOK = 25.0

LABEL_RCT = "RCT"
LABEL_NON = "non_RCT"
LABEL_INCLUDE = "include"
LABEL_EXCLUDE = "exclude"

DEFAULT_MODE = "cohen"

# Aliases used by runners / metrics
BIOBERT_ACC = BIOBERT_ACC
BIOBERT_F1 = BIOBERT_F1
H2H_DIR = H2H_DIR
H2H_SEED = H2H_SEED
