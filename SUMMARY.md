# TITANIC: The Unsinkable Experience (project summary)

## Goal

Turn the classic Titanic dataset into an absurd, epic web experience: part 1912 White Star Line
poster, part Hollywood disaster film, part video game. Under the theatre, the app shows two serious
techniques:

1. **An LLM agent with a tool.** A local model answers questions by writing pandas code. The code runs
   in a sandbox, and the model's numbers are checked against the results.
2. **A classic ML pipeline.** Four classifiers are compared with cross-validation and a hyperparameter
   search, and the winner predicts *your* survival.

## Dataset

`titanic.csv` is the Kaggle Titanic training set: **891 passengers, 12 columns**
(`PassengerId, Survived, Pclass, Name, Sex, Age, SibSp, Parch, Ticket, Fare, Cabin, Embarked`).

- **Survival:** 342 of 891 survived (**38.4%**). Guessing "everyone perished" scores 61.6%.
- **Missing values:** `Age` 177, `Cabin` 687, `Embarked` 2.
- **Derived features:**
  - **Title**, extracted from the name (Mr / Mrs / Miss / Master / Rare).
  - **FamilySize** = `SibSp + Parch + 1`.

## Architecture

```
 Browser (plain HTML / CSS / JS, Plotly)
   │   /            boarding screen
   │   /telegraphist  chat ───────── POST /chat ──► app/chat.py ──► Ollama  qwen3.5:4b
   │                                                   │  tool call
   │                                                   ▼
   │                                          app/safe_query.py  query_data(code)
   │                                          (AST-checked, read-only pandas on df)
   │   /bridge      ticket ───────── POST /predict ──► app/model.py ──► model.joblib
   │                regatta ◄─────── GET /api/regatta    (best of 4 classifiers)
   │                joke ─────────── POST /chat {prediction}
   ▼
 FastAPI app (app/main.py, Jinja2 templates, static files) served by uvicorn
```

- **Backend:** FastAPI with Pydantic validation. Templates are Jinja2, and a shared `base.html` holds the
  living background and the ship's-wheel menu.
- **LLM:**
  - Ollama's `/api/chat` with function calling. Tool rounds use thinking mode.
  - A **number guard** checks every figure in the reply against the tool results. Numbers written in
    words are rejected. A failed check gets one correction round; after that, Harold sends the exact
    figures himself.
- **Sandbox:**
  - The code is parsed with `ast.parse(mode="eval")`, so only a single expression is allowed.
  - An allow/deny AST walk blocks dunders, I/O, `eval`/`query`/`format`, `inplace=` and `:=`.
  - Evaluation uses empty `__builtins__` on a copy of `df`.
- **ML:** `ColumnTransformer` (imputation, log fare, scaling, one-hot), then `GridSearchCV` with
  stratified 5-fold CV for each model. The best model goes to `model.joblib`.
- **Frontend:**
  - No build step. Canvas draws the sky and ocean; SVG draws the ships, gauge and wheel.
  - Plotly (pinned CDN) draws the scatter chart.
  - Every animation respects `prefers-reduced-motion`, and the layout is responsive from phone to laptop.

## uv setup

- **Python 3.14** (`.python-version`). The project uses the `uv_build` backend, with the package `app/`
  at the repo root (`module-root = ""`).
- **Runtime dependencies:** `fastapi`, `uvicorn[standard]`, `jinja2`, `httpx`, `pandas`, `scikit-learn`,
  `joblib`. **Dev dependencies:** `pytest`, `httpx2`.
- **Console script:** `titanic-app = "app.main:run"`.
- **Lockfile:** `uv.lock` pins every version.
- `capture.py` declares Playwright as **inline script metadata** (PEP 723), so `uv run capture.py` gets
  it in an isolated environment and the app's dependencies stay untouched.

## Main files

| File | Lines | Role |
|---|---:|---|
| `app/main.py` | 131 | FastAPI routes, request models, `titanic-app` entry point |
| `app/chat.py` | 340 | The Telegraphist: persona, Ollama tool loop, number guard, LINE CUT |
| `app/safe_query.py` | 183 | `query_data()`: the read-only pandas sandbox |
| `app/model.py` | 274 | Training, regatta results, prediction, 5 nearest passengers |
| `app/data.py` · `app/train.py` | 49 · 19 | Loading and features · `python -m app.train` |
| `app/templates/*.html` | 503 | `base`, `_macros` (SVG ship/iceberg/wheel), `home`, `telegraphist`, `bridge` |
| `app/static/css/*.css` | 995 | Tokens, stained glass, ticket, gauge, telegrams |
| `app/static/js/*.js` | 1,082 | Ocean and effects (`ambient.js`), chat, regatta, gauge, chart |
| `tests/*.py` | 372 | **75 pytest tests**: sandbox, `/predict`, `/chat` with a scripted fake model |
| `capture.py` | — | Playwright script for the 4 presentation screenshots |

## How to run

```sh
uv sync                                   # install
ollama pull qwen3.5:4b                    # once, for the Telegraphist
uv run uvicorn app.main:app               # or: uv run titanic-app
# open http://127.0.0.1:8000
uv run pytest                             # 75 tests, offline (no Ollama needed)
uv run python -m app.train                # retrain the fleet (~10 s)
uv run capture.py                         # screenshots/ (app must be running)
```

If `model.joblib` is missing, it's trained automatically at startup. Without Ollama, Harold answers
"LINE CUT STOP" with setup instructions.

## Model accuracy

Stratified 5-fold cross-validation over 891 passengers. Each model is tuned with `GridSearchCV`.

| Ship (regatta) | Model | CV accuracy | ± std | Best hyperparameters | Grid |
|---|---|---:|---:|---|---:|
| 👑 RMS Carpathia | **Gradient Boosting** | **84.74%** | 1.16 | `n_estimators=250, learning_rate=0.1, max_depth=2` | 8 |
| SS Californian | Random Forest | 84.17% | 0.84 | `n_estimators=300, max_depth=8, min_samples_leaf=5` | 12 |
| HMHS Britannic | SVM (RBF, calibrated) | 83.50% | 1.26 | `C=1, gamma=0.1` | 12 |
| RMS Olympic | Logistic Regression | 82.83% | 1.22 | `C=3` | 6 |
| — | Baseline: "everyone perished" | 61.62% | | | |

The models are within about 2 points of each other. Feature engineering (sex, class and title) does
most of the work. Example predictions: a 28-year-old man in third class (£8.05) gets **10%**, while a
36-year-old woman in first class (£80) gets **over 90%**.

## Skills used

- **Python and data:**
  - pandas feature engineering (title extraction, family size, imputation by title).
  - A safe evaluator built on Python's `ast` module.
- **Machine learning:** scikit-learn pipelines, `ColumnTransformer`, `GridSearchCV`, stratified k-fold,
  probability calibration, and nearest neighbours in the model's feature space.
- **LLM engineering:**
  - Ollama function calling and a persona system prompt.
  - Grounding the model's numbers in tool output, with a deterministic fallback.
- **Web backend:** FastAPI, Pydantic validation, Jinja2 templates, an async httpx client, and lifespan
  start-up (model loading, LLM warm-up).
- **Frontend:**
  - Plain CSS: custom properties, `color-mix`, masks, `:has()`.
  - Canvas 2D animation, hand-drawn SVG, the Web Audio API, the IntersectionObserver API, and Plotly.
  - Accessibility: reduced motion, focus styles, ARIA live regions, and a table view of the regatta.
- **Data visualisation:** colour-blind-checked survival palette (OKLab ΔE ≥ 19 under protan, deutan and
  tritan simulation; contrast ≥ 5.8 against the background), with a second marker shape (● / ✕) so
  colour isn't the only signal.
- **Quality and tooling:**
  - uv (lockfile, console script, PEP 723 inline-dependency script).
  - pytest with fixtures, parametrised sandbox-escape tests, and a fake LLM for deterministic tests.
  - Playwright for end-to-end screenshots.
- **Claude Code skills:** the **dataviz** skill guided the chart's colour choice and validation, marker
  encoding, legend and hover layer.

## Screenshots (`screenshots/`, captured by `capture.py`)

| | |
|---|---|
| `1-home.png` | Boarding screen: the ship out of the fog, gold title, sunburst, brass buttons |
| `2-telegraphist.png` | "How many women were on board?" → tape `(df.Sex == "female").sum()` → **314**, stamped *Figures verified* |
| `3-regatta.png` | The regatta: Gradient Boosting crowned at 84.7%, fireworks |
| `4-chart.png` | You (gold star) among the 891, linked to your 5 nearest passengers |
