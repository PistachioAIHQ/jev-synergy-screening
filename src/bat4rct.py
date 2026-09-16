from __future__ import annotations

import zipfile
from pathlib import Path
from urllib.request import urlretrieve

import pandas as pd
from sklearn.model_selection import train_test_split

from .config import (
    BAT4RCT_TXT,
    BAT4RCT_ZIP_URL,
    DATA_DIR,
    DEMO_CSV,
    DEMO_PER_CLASS,
    DEMO_SEED,
    SPLIT_SEED,
    TEST_SIZE,
    VAL_OF_HOLD,
)


def ensure_raw_data() -> Path:
    """Download + unzip Bat4RCT if needed. Returns path to rct_data.txt."""
    alt = Path("/workspace/jev-demo/data/rct_data/rct_data.txt")
    if BAT4RCT_TXT.exists():
        return BAT4RCT_TXT
    if alt.exists():
        return alt
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DATA_DIR / "rct_data.zip"
    if not zip_path.exists():
        print(f"Downloading Bat4RCT → {zip_path} …")
        urlretrieve(BAT4RCT_ZIP_URL, zip_path)
    print(f"Unpacking {zip_path} …")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(DATA_DIR)
    if not BAT4RCT_TXT.exists():
        raise FileNotFoundError(f"Expected {BAT4RCT_TXT} after unzip")
    return BAT4RCT_TXT


def load_bat4rct(path: Path | None = None) -> pd.DataFrame:
    """Load Bat4RCT TSV with title+abstract mix (paper 'mix' mode)."""
    path = path or ensure_raw_data()
    df = pd.read_csv(
        path,
        sep="\t",
        encoding="utf-8",
        header=None,
        names=["pmid", "pubtype", "year", "title", "abstract"],
        dtype={"pmid": str, "pubtype": int, "year": "Int64", "title": str, "abstract": str},
    )
    df["title"] = df["title"].fillna("").astype(str).str.strip()
    df["abstract"] = df["abstract"].fillna("").astype(str).str.strip()
    df = df.dropna(subset=["pmid", "pubtype"])
    df = df.drop_duplicates(subset=["pmid"], keep="first")
    df["text"] = (df["title"] + " " + df["abstract"]).str.strip()
    # pubtype: 1 = RCT, 0 = non-RCT (Bat4RCT)
    df["gold"] = df["pubtype"].map({1: "RCT", 0: "non_RCT"})
    df = df[df["gold"].notna() & (df["text"].str.len() > 0)].copy()
    return df.reset_index(drop=True)


def paper_splits(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Recreate Bat4RCT 80/10/10 stratified splits (random_state=42)."""
    train, hold = train_test_split(
        df, test_size=TEST_SIZE, random_state=SPLIT_SEED, stratify=df["gold"]
    )
    val, test = train_test_split(
        hold, test_size=VAL_OF_HOLD, random_state=SPLIT_SEED, stratify=hold["gold"]
    )
    return (
        train.reset_index(drop=True),
        val.reset_index(drop=True),
        test.reset_index(drop=True),
    )


def stratified_demo(test_df: pd.DataFrame, n_per_class: int = DEMO_PER_CLASS, seed: int = DEMO_SEED) -> pd.DataFrame:
    """Fixed 100 RCT + 100 non_RCT from the test split."""
    parts = []
    for label in ("RCT", "non_RCT"):
        sub = test_df[test_df["gold"] == label]
        if len(sub) < n_per_class:
            raise ValueError(f"Need {n_per_class} {label} in test, have {len(sub)}")
        parts.append(sub.sample(n=n_per_class, random_state=seed))
    demo = pd.concat(parts, ignore_index=True)
    # shuffle for film-friendly order, still deterministic
    demo = demo.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    demo.insert(0, "demo_idx", range(len(demo)))
    return demo[["demo_idx", "pmid", "year", "title", "abstract", "text", "gold"]]


def build_demo_csv(out: Path | None = None) -> Path:
    out = out or DEMO_CSV
    df = load_bat4rct()
    _, _, test = paper_splits(df)
    demo = stratified_demo(test)
    out.parent.mkdir(parents=True, exist_ok=True)
    demo.to_csv(out, index=False)
    print(f"Wrote {out} ({len(demo)} rows: {demo['gold'].value_counts().to_dict()})")
    return out


def load_demo(path: Path | None = None) -> pd.DataFrame:
    path = path or DEMO_CSV
    if not path.exists():
        build_demo_csv(path)
    return pd.read_csv(path)
