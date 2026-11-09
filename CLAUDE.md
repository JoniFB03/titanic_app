# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

"TITANIC: The Unsinkable Experience" is a FastAPI web app built on the classic Titanic dataset
(`titanic.csv`, 891 passengers, Kaggle schema). It has three pages:

- `/`: the boarding screen.
- `/telegraphist`: an LLM chat. It uses `qwen3.5:4b` via Ollama, whose only tool is `query_data(code)`.
- `/bridge`: a scikit-learn model comparison with survival prediction and a Plotly chart.

The README describes the features in full.

## Tooling

Managed with **uv** (`uv_build` backend). The package lives at `app/` in the repo root
(`[tool.uv.build-backend] module-root = ""`). Python **3.14** is required.

```sh
uv sync                       # install deps
uv run titanic-app            # start the server on :8000 (app.main:run → uvicorn)
uv run python -m app.train    # retrain the 4 models, save the winner to model.joblib (~10 s)
uv run pytest                 # tests: offline, train a fast model into a temp dir
uv add <package>              # add a dependency
```

On Windows a running `titanic-app.exe` locks the script, so `uv add` / `uv sync` fail until the server
is stopped.

## Architecture notes

- `app/safe_query.py` is the security boundary for LLM-written code. It parses the code in
  `ast.parse(mode="eval")`, walks the AST with allow/deny lists, evaluates with empty `__builtins__`, and
  uses a deep copy of `df`. Any new pandas capability must keep it read-only, with no I/O and no dunders.
  Add a refusal test for anything you open up.
- `app/chat.py`:
  - Tool rounds use `think=True`.
  - `check_numbers()` verifies every figure in the reply against the tool results. It allows rounding,
    ×100 and complements, and rejects numbers spelled in words.
  - A failed check gets one correction round, then `exact_figures_telegram()`.
  - `OLLAMA_URL` / `OLLAMA_MODEL` are read at import time. Tests set `OLLAMA_URL` to a dead port in
    `tests/conftest.py` before importing the app.
- `app/model.py`:
  - `get_bundle()` loads `model.joblib` and trains it first if it's missing. Bundles are cached per path.
  - The bundle also stores the CV results that the regatta shows.
  - `TITANIC_MODEL_PATH` overrides the path (tests use this).
- Fixed-position overlays (flood, confetti, gulls, joke popup) must go in `{% block overlays %}`, not
  inside `<main>`. The low-odds effect rotates `<main>`, which would trap fixed children.
- Frontend:
  - Plain CSS/JS. Plotly comes from jsdelivr, pinned at `plotly.js-basic-dist-min@2.35.2`.
  - `window.Titanic` (from `ambient.js`) exposes `reduced`, `toast`, `sound`, `store` and `iceberg` to
    the page scripts.
  - Every animation must have a `prefers-reduced-motion` path.
- Chat history (including jokes relayed from the Bridge) lives in `sessionStorage` under `titanic.chat`.
- `AI in Code From Chatbot to Agent.html` (~1.6 MB) is unrelated reference material. Avoid reading it
  unless asked.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- When graphify-out/graph.json exists, run `graphify query "<question>"` before your first grep, search or source-file read for a codebase question, and put this rule in every subagent prompt that explores code. Read raw files only for lines the graph or an earlier read already located. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
- A committed graphify-out/graph.json is rewritten whole on every build, so a large diff to it in a pull request is expected. Do not flag it as churn or suggest skipping the graph rebuild or its hooks.
