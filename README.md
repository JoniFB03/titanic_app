# TITANIC: The Unsinkable Experience

An absurd, epic and (we hope) magnificent web experience built on the classic Titanic dataset
(`titanic.csv`, 891 passengers). It's part 1912 White Star Line poster, part Hollywood disaster film and
part video game, built with **FastAPI**, **pandas**, **scikit-learn**, a local LLM through **Ollama**, and
plain HTML, CSS and JavaScript.

| Page | URL | What happens |
|---|---|---|
| Boarding | `/` | The ship emerges from the fog, the title lands letter by letter, and two brass buttons take you aboard. |
| The Telegraphist | `/telegraphist` | Wire Harold, a melodramatic 1912 Marconi operator (`qwen3.5:4b`). He answers with pandas, and the code is typed on telegraph tape. |
| The Bridge | `/bridge` | Four models race a regatta. You buy a 1912 ticket, read your survival odds on a brass gauge, and see yourself among the 891. |

A ship's-wheel menu (top right) links the pages, and a giant wave sweeps you between them.

## Quick start

```sh
uv sync                     # Python 3.14 + dependencies
uv run titanic-app          # http://127.0.0.1:8000
```

The first start trains the models if `model.joblib` doesn't exist yet (about 10 s).

For the Telegraphist you also need [Ollama](https://ollama.com) running locally:

```sh
ollama pull qwen3.5:4b
ollama serve                # usually already running as a service
```

Without Ollama the app still works. Harold replies **LINE CUT STOP** with these instructions, and the
Bridge falls back to canned jokes.

| Command | |
|---|---|
| `uv run titanic-app` | start the server (`PORT=9000 uv run titanic-app` for another port) |
| `uv run python -m app.train` | retrain and compare the fleet, then save the winner to `model.joblib` |
| `uv run pytest` | run the test suite (offline: needs neither Ollama nor `model.joblib`) |

Environment variables: `OLLAMA_URL` (default `http://localhost:11434`), `OLLAMA_MODEL` (default
`qwen3.5:4b`), `TITANIC_MODEL_PATH` (default `./model.joblib`), `PORT` (default `8000`).

## How it works

### The Telegraphist: `app/chat.py` + `app/safe_query.py`

- `POST /chat {message, history}` runs a tool-calling loop against Ollama's `/api/chat`, with at most
  5 rounds. The model's only tool is **`query_data(code)`**, which evaluates **one read-only pandas
  expression** on `df`.
- **Sandbox.** The code is parsed as a single expression, so statements and imports can't exist. The
  AST is then checked:
  - Only `df`, `pd` and a few harmless builtins are allowed.
  - Attributes starting with `_` are blocked.
  - File, network and code-evaluating methods (`to_*`, `read_*`, `eval`, `query`, `pipe`, `format`, …)
    are blocked, and so are `inplace=` and `:=`.
  - The expression is evaluated with empty `__builtins__` on a **copy** of the DataFrame.
- **Numbers are always right.** A 4B model is a fine actor but a sloppy copyist, so a guard checks
  every number in the telegram against the tool results.
  - Allowed forms: rounding, percentages, and complements such as "39% perished" for a 61% survival rate.
  - Numbers written in words are rejected.
  - If the check fails, the model gets one correction round. If it fails again, Harold sends the exact
    figures himself.
  - The rubber stamp on each telegram tells you which case happened (*figures verified*, *corrected*
    or *exact figures*).
- Tool rounds use Qwen's thinking mode because it picks much better queries. The model is warmed up
  in the background at startup.
- `POST /chat {prediction}` asks Harold for a one-telegram joke about a Bridge prediction.
- `GET /api/telegraph` reports whether the line is open, which drives the lamp on the apparatus.

### The Bridge: `app/model.py`

- **Features:** class, sex, age, fare (log), family size (`SibSp + Parch + 1`), port, and the **title**
  extracted from the name (Mr / Mrs / Miss / Master / Rare). They go through a `ColumnTransformer`
  pipeline: median or most-frequent imputation, scaling, and one-hot encoding.
- **The regatta:** logistic regression, random forest, gradient boosting and an SVM (probabilities
  calibrated with `CalibratedClassifierCV`) are each tuned with `GridSearchCV` and **stratified 5-fold
  cross-validation**. The best mean accuracy wins and is saved to `model.joblib` with every fold's
  score. Currently Gradient Boosting wins at about 84.7%. The baseline of guessing "everyone perished"
  is 61.6%.
- `POST /predict` takes `{name, title, sex, age, pclass, fare, family_size, embarked}` and returns
  `{probability, verdict, model, model_accuracy, chart: {passengers[891], you, neighbors[5]}}`. The
  neighbours are your nearest passengers in the model's own feature space.
- **Gauge effects:**
  - under 30%: the screen lists and floods
  - 30–70%: the needle trembles
  - over 70%: confetti and seagulls
- **Chart:** a Plotly scatter of age against fare on a log scale. You're a golden star linked to your
  5 nearest passengers. Survived and perished differ in colour *and* marker shape (● / ✕). The palette
  was checked for colour-blind separation and contrast on the night-sky background.
- Each prediction goes to the Telegraphist. His joke pops up on the Bridge and is waiting on the
  wireless page.

### Look and feel: `app/templates/`, `app/static/`

- **Fonts:** Cinzel Decorative and Federo (Art Nouveau headings), Cormorant Garamond (text) and Special
  Elite (telegraph tape and code), all from Google Fonts.
- **Colours:** Titanic colours as CSS tokens: black hull, white superstructure, buff funnels with black
  tops, red waterline, midnight Atlantic, gold and brass. Frames are styled as stained glass with Art
  Nouveau corners.
- **Background:** `ambient.js` draws the living background on canvas: twinkling stars, a faint aurora,
  shooting stars, a layered swell with starlight glints, a ship on the horizon with smoke from four
  funnels, and an iceberg that peeks out now and then.
- **Micro-interactions:** a foam cursor trail, buttons that rock at sea, ripples on every click, and a
  synthesised steam whistle, Morse and wave sounds (all muted by default).
- **Easter eggs:** type `iceberg` (the screen shakes), `sos` or `mgy`. Click a funnel on the home page.
- **Accessibility:** `prefers-reduced-motion` gets a calm sea, with no animation, tilt, trail or wave and
  everything visible at once. Layouts are responsive from phone to laptop.

## Project layout

```
app/
  main.py          FastAPI app, routes, request models, `titanic-app` entry point
  data.py          load titanic.csv, Title / FamilySize features
  safe_query.py    query_data(): the AST-checked, read-only pandas evaluator
  chat.py          the Telegraphist: Ollama tool loop, persona, number guard, LINE CUT
  model.py         training, regatta results, prediction, nearest passengers
  train.py         `python -m app.train`
  templates/       base.html (+ _macros.html: ship, iceberg, wheel), home, telegraphist, bridge
  static/css/      base.css, home.css, telegraphist.css, bridge.css
  static/js/       ambient.js, home.js, telegraphist.js, bridge.js
tests/             query_data sandbox, /predict, /chat (with a scripted fake model)
titanic.csv        the manifest
```
