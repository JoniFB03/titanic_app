"""Shared fixtures: an offline Ollama, a fast throwaway model, and a TestClient."""

import os

# Point the Telegraphist at a dead port *before* the app is imported: tests never need Ollama.
os.environ["OLLAMA_URL"] = "http://127.0.0.1:9"

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def model_file(tmp_path_factory):
    """Train a fast (tiny-grid) bundle into a temp dir so tests never touch the real model.joblib."""
    from app import model

    path = tmp_path_factory.mktemp("model") / "model.joblib"
    os.environ["TITANIC_MODEL_PATH"] = str(path)
    model.save(model.train(fast=True), path)
    yield path
    os.environ.pop("TITANIC_MODEL_PATH", None)


@pytest.fixture(scope="session")
def client(model_file):
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def passenger():
    return {
        "name": "Ada Lovelace",
        "title": "Mrs",
        "sex": "female",
        "age": 36,
        "pclass": 1,
        "fare": 80.0,
        "family_size": 2,
        "embarked": "C",
    }
