"""The Bridge's engine room: train, compare, save and use the survival models."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler
from sklearn.svm import SVC

from app.data import ROOT, TITLE_MAP, add_features, load_passengers

DEFAULT_MODEL_PATH = ROOT / "model.joblib"
NUMERIC = ["Age", "Fare", "FamilySize"]
CATEGORICAL = ["Pclass", "Sex", "Embarked", "Title"]
FEATURES = NUMERIC + CATEGORICAL
RANDOM_STATE = 42


def model_path() -> Path:
    return Path(os.environ.get("TITANIC_MODEL_PATH", DEFAULT_MODEL_PATH))


def make_preprocessor() -> ColumnTransformer:
    def scaled(*steps):
        return Pipeline([("impute", SimpleImputer(strategy="median")), *steps, ("scale", StandardScaler())])

    categorical = Pipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    return ColumnTransformer(
        [
            ("fare", scaled(("log", FunctionTransformer(np.log1p))), ["Fare"]),
            ("num", scaled(), ["Age", "FamilySize"]),
            ("cat", categorical, CATEGORICAL),
        ]
    )


@dataclass(frozen=True)
class Contender:
    name: str
    ship: str  # the name of the ship that represents it in the regatta
    estimator: Any
    grid: dict[str, list]
    fast_grid: dict[str, list]


def contenders() -> list[Contender]:
    return [
        Contender(
            "Logistic Regression", "RMS Olympic",
            LogisticRegression(max_iter=2000),
            {"clf__C": [0.03, 0.1, 0.3, 1, 3, 10]},
            {"clf__C": [1]},
        ),
        Contender(
            "Random Forest", "SS Californian",
            RandomForestClassifier(random_state=RANDOM_STATE, n_jobs=-1),
            {
                "clf__n_estimators": [300],
                "clf__max_depth": [4, 6, 8, None],
                "clf__min_samples_leaf": [1, 3, 5],
            },
            {"clf__n_estimators": [30], "clf__max_depth": [5]},
        ),
        Contender(
            "Gradient Boosting", "RMS Carpathia",
            GradientBoostingClassifier(random_state=RANDOM_STATE),
            {
                "clf__n_estimators": [100, 250],
                "clf__learning_rate": [0.03, 0.1],
                "clf__max_depth": [2, 3],
            },
            {"clf__n_estimators": [30]},
        ),
        Contender(
            "Support Vector Machine", "HMHS Britannic",
            # SVC(probability=True) is deprecated: calibrate the margins into probabilities.
            CalibratedClassifierCV(SVC(random_state=RANDOM_STATE), ensemble=False),
            {"clf__estimator__C": [0.3, 1, 3, 10], "clf__estimator__gamma": ["scale", 0.03, 0.1]},
            {"clf__estimator__C": [1]},
        ),
    ]


def training_frame() -> tuple[pd.DataFrame, pd.Series]:
    df = add_features(load_passengers())
    return df[FEATURES], df["Survived"]


def train(fast: bool = False, verbose: bool = False) -> dict[str, Any]:
    """Grid-search every contender with 5-fold CV and return the bundle to save."""
    X, y = training_frame()
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    results: list[dict[str, Any]] = []
    best_search: GridSearchCV | None = None
    best_name = ""
    for c in contenders():
        started = time.perf_counter()
        pipe = Pipeline([("prep", make_preprocessor()), ("clf", c.estimator)])
        search = GridSearchCV(
            pipe, c.fast_grid if fast else c.grid, cv=cv, scoring="accuracy", n_jobs=-1
        )
        search.fit(X, y)
        i = search.best_index_
        folds = [float(search.cv_results_[f"split{k}_test_score"][i]) for k in range(5)]
        row = {
            "name": c.name,
            "ship": c.ship,
            "accuracy": float(search.best_score_),
            "std": float(search.cv_results_["std_test_score"][i]),
            "folds": folds,
            "best_params": {k.removeprefix("clf__").removeprefix("estimator__"): _plain(v) for k, v in search.best_params_.items()},
            "candidates": len(search.cv_results_["params"]),
            "seconds": round(time.perf_counter() - started, 2),
        }
        results.append(row)
        if verbose:
            print(f"  {c.name:<24} {row['accuracy']:.4f} +/- {row['std']:.4f}  {row['best_params']}")
        if best_search is None or search.best_score_ > best_search.best_score_:
            best_search, best_name = search, c.name
    assert best_search is not None
    for row in results:
        row["winner"] = row["name"] == best_name
    return {
        "pipeline": best_search.best_estimator_,
        "best": best_name,
        "results": results,
        "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_samples": int(len(X)),
        "fast": fast,
    }


def _plain(v: Any) -> Any:
    return v.item() if isinstance(v, np.generic) else v


def save(bundle: dict[str, Any], path: Path | None = None) -> Path:
    path = path or model_path()
    joblib.dump(bundle, path)
    return path


_CACHE: dict[str, Any] = {}


def get_bundle() -> dict[str, Any]:
    """Load model.joblib (training it first if it doesn't exist). Cached per path."""
    path = model_path()
    key = str(path)
    if key not in _CACHE:
        if not path.exists():
            print(f"[bridge] No {path.name} yet - training the fleet (this takes a minute)...")
            save(train(verbose=True), path)
        bundle = joblib.load(path)
        bundle["_neighbors"] = _build_neighbors(bundle["pipeline"])
        _CACHE.clear()
        _CACHE[key] = bundle
    return _CACHE[key]


def _build_neighbors(pipeline: Pipeline) -> NearestNeighbors:
    X, _ = training_frame()
    Z = pipeline.named_steps["prep"].transform(X)
    return NearestNeighbors(n_neighbors=5).fit(Z)


# ---------------------------------------------------------------- prediction

def passenger_row(p: dict[str, Any]) -> pd.DataFrame:
    """Turn the boarding-ticket form into a one-row feature frame."""
    title = TITLE_MAP.get(p["title"], p["title"] if p["title"] in TITLE_MAP.values() else "Rare")
    return pd.DataFrame(
        [{
            "Age": float(p["age"]),
            "Fare": float(p["fare"]),
            "FamilySize": int(p["family_size"]),
            "Pclass": int(p["pclass"]),
            "Sex": p["sex"],
            "Embarked": p["embarked"],
            "Title": title,
        }]
    )[FEATURES]


@lru_cache(maxsize=1)
def chart_passengers() -> tuple[dict[str, Any], ...]:
    """All 891 passengers for the scatter. Missing ages are filled with their title's median."""
    df = add_features(load_passengers())
    age_fill = df.groupby("Title")["Age"].transform("median")
    out = []
    for r, filled in zip(df.itertuples(index=False), age_fill):
        missing = pd.isna(r.Age)
        out.append({
            "id": int(r.PassengerId),
            "name": r.Name,
            "age": round(float(filled if missing else r.Age), 1),
            "age_estimated": bool(missing),
            "fare": round(float(r.Fare), 2),
            "survived": int(r.Survived),
            "pclass": int(r.Pclass),
            "sex": r.Sex,
        })
    return tuple(out)


def predict(p: dict[str, Any], bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    bundle = bundle or get_bundle()
    pipe: Pipeline = bundle["pipeline"]
    row = passenger_row(p)
    proba = float(pipe.predict_proba(row)[0][1])

    z = pipe.named_steps["prep"].transform(row)
    dist, idx = bundle["_neighbors"].kneighbors(z, n_neighbors=5)
    manifest = load_passengers()
    neighbors = []
    for d, i in zip(dist[0], idx[0]):
        r = manifest.iloc[int(i)]
        neighbors.append({
            "id": int(r["PassengerId"]),
            "name": r["Name"],
            "survived": int(r["Survived"]),
            "pclass": int(r["Pclass"]),
            "age": None if pd.isna(r["Age"]) else float(r["Age"]),
            "fare": round(float(r["Fare"]), 2),
            "distance": round(float(d), 3),
        })

    accuracy = next(r["accuracy"] for r in bundle["results"] if r["name"] == bundle["best"])
    return {
        "probability": round(proba, 4),
        "model": bundle["best"],
        "model_accuracy": round(accuracy, 4),
        "verdict": verdict(proba),
        "chart": {
            "passengers": list(chart_passengers()),
            "you": {"age": float(p["age"]), "fare": float(p["fare"]), "name": p.get("name") or "You"},
            "neighbors": neighbors,
        },
    }


def verdict(proba: float) -> str:
    if proba < 0.30:
        return "sinking"
    if proba <= 0.70:
        return "uncertain"
    return "saved"


def regatta() -> dict[str, Any]:
    b = get_bundle()
    return {"best": b["best"], "results": b["results"], "trained_at": b["trained_at"],
            "n_samples": b["n_samples"]}
