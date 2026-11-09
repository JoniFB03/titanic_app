# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A small "vibe-coded" Python app built around the classic Titanic dataset (`titanic.csv`, 891 passengers, Kaggle schema: `PassengerId, Survived, Pclass, Name, Sex, Age, SibSp, Parch, Ticket, Fare, Cabin, Embarked`). Dependencies are pandas and scikit-learn, so the intended direction is data exploration and survival modeling. The project is at an early stage: the package holds only a stub `main()`.

## Tooling

Managed with **uv** (`uv_build` backend, `src/` layout). Python **3.14** is required (`.python-version`, `requires-python >=3.14`).

```sh
uv sync                    # install deps into .venv
uv run titanic-app         # run the console script (titanic_app:main)
uv run python example.py   # run a top-level script with project deps
uv add <package>           # add a dependency (updates pyproject.toml + uv.lock)
```

No test suite, linter, or formatter is configured yet.

## Structure notes

- `src/titanic_app/__init__.py` defines `main()`, the `titanic-app` entry point. It also calls `main()` at module level, so importing the package runs it, and `uv run titanic-app` prints twice. Remove that call or guard it if this matters.
- `example.py` holds only a comment-list of steps (welcome message, greet a passenger by name, load `titanic.csv` with pandas, show the first 10 rows). It's a prompt or spec for code still to be written.
- `titanic.csv` sits at the repo root. If code opens it by a relative path, run commands from the repo root.
- `AI in Code From Chatbot to Agent.html` is a large (~1.6 MB) reference/presentation file and not part of the app. Avoid reading it unless asked.
