"""Loading the passenger manifest and the feature engineering shared by the model."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "titanic.csv"

TITLE_MAP = {
    "Mr": "Mr",
    "Mrs": "Mrs",
    "Mme": "Mrs",
    "Countess": "Mrs",
    "Lady": "Mrs",
    "Dona": "Mrs",
    "Miss": "Miss",
    "Mlle": "Miss",
    "Ms": "Miss",
    "Master": "Master",
}
TITLES = ["Mr", "Mrs", "Miss", "Master", "Rare"]
PORTS = {"S": "Southampton", "C": "Cherbourg", "Q": "Queenstown"}


@lru_cache(maxsize=1)
def load_passengers() -> pd.DataFrame:
    """The raw manifest, exactly as in titanic.csv (891 rows). Cached: treat as read-only."""
    return pd.read_csv(CSV_PATH)


def extract_title(name: str) -> str:
    """'Braund, Mr. Owen Harris' -> 'Mr'. Uncommon honorifics collapse to 'Rare'."""
    try:
        raw = name.split(",", 1)[1].split(".", 1)[0].strip()
    except IndexError:
        return "Rare"
    return TITLE_MAP.get(raw, "Rare")


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with Title and FamilySize columns added."""
    out = df.copy()
    out["Title"] = out["Name"].map(extract_title)
    out["FamilySize"] = out["SibSp"].fillna(0) + out["Parch"].fillna(0) + 1
    return out
