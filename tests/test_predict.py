"""POST /predict, the regatta, and the pages."""

import joblib
import pytest

MODEL_NAMES = {"Logistic Regression", "Random Forest", "Gradient Boosting", "Support Vector Machine"}


def test_predict_shape(client, passenger):
    r = client.post("/predict", json=passenger)
    assert r.status_code == 200
    data = r.json()
    assert 0.0 <= data["probability"] <= 1.0
    assert data["model"] in MODEL_NAMES
    assert 0.5 < data["model_accuracy"] <= 1.0

    chart = data["chart"]
    assert len(chart["passengers"]) == 891
    first = chart["passengers"][0]
    assert set(first) >= {"id", "name", "age", "fare", "survived", "pclass", "sex", "age_estimated"}
    assert all(p["age"] is not None for p in chart["passengers"])  # missing ages are filled for plotting
    assert chart["you"] == {"age": 36.0, "fare": 80.0, "name": "Ada Lovelace"}
    assert len(chart["neighbors"]) == 5
    assert {n["id"] for n in chart["neighbors"]} <= {p["id"] for p in chart["passengers"]}
    distances = [n["distance"] for n in chart["neighbors"]]
    assert distances == sorted(distances)


@pytest.mark.parametrize("p, expected", [(0.1, "sinking"), (0.29, "sinking"), (0.3, "uncertain"), (0.7, "uncertain"), (0.71, "saved")])
def test_verdict_thresholds(p, expected):
    from app.model import verdict

    assert verdict(p) == expected


def test_verdict_matches_probability(client, passenger):
    data = client.post("/predict", json=passenger).json()
    from app.model import verdict

    assert data["verdict"] == verdict(data["probability"])


def test_first_class_lady_beats_third_class_man(client, passenger):
    lady = client.post("/predict", json=passenger).json()["probability"]
    man = client.post(
        "/predict",
        json={**passenger, "name": "", "title": "Mr", "sex": "male", "age": 30, "pclass": 3, "fare": 7.25,
              "family_size": 1, "embarked": "S"},
    ).json()["probability"]
    assert lady > 0.7 > 0.3 > man


@pytest.mark.parametrize(
    "patch",
    [
        {"sex": "x"},
        {"age": -1},
        {"age": 150},
        {"pclass": 4},
        {"fare": -5},
        {"family_size": 0},
        {"embarked": "X"},
        {"title": "Emperor"},
        {"name": "x" * 81},
    ],
)
def test_predict_rejects_bad_tickets(client, passenger, patch):
    assert client.post("/predict", json={**passenger, **patch}).status_code == 422


def test_predict_requires_fields(client):
    assert client.post("/predict", json={"name": "Nobody"}).status_code == 422


def test_regatta(client):
    data = client.get("/api/regatta").json()
    names = {r["name"] for r in data["results"]}
    assert names == MODEL_NAMES
    winners = [r for r in data["results"] if r["winner"]]
    assert len(winners) == 1 and winners[0]["name"] == data["best"]
    assert winners[0]["accuracy"] == max(r["accuracy"] for r in data["results"])
    for r in data["results"]:
        assert len(r["folds"]) == 5  # 5-fold cross-validation
        assert 0.6 < r["accuracy"] < 1.0


def test_saved_bundle(model_file):
    bundle = joblib.load(model_file)
    assert set(bundle) >= {"pipeline", "best", "results"}
    assert hasattr(bundle["pipeline"], "predict_proba")


@pytest.mark.parametrize("path, text", [("/", "TITANIC"), ("/telegraphist", "The Telegraphist"), ("/bridge", "The Bridge")])
def test_pages(client, path, text):
    r = client.get(path)
    assert r.status_code == 200
    assert text.lower() in r.text.lower()
    assert 'class="helm"' in r.text  # the ship's-wheel menu links every page
    for href in ('href="/"', 'href="/telegraphist"', 'href="/bridge"'):
        assert href in r.text
