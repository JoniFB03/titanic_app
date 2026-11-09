"""FastAPI entry point: three pages, two engines.

GET  /              cinematic boarding screen
GET  /telegraphist  chat with the 1912 wireless operator (LLM + pandas tool)
GET  /bridge        model regatta, boarding ticket, brass gauge, passenger chart
POST /chat          {message, history} -> telegram  |  {prediction} -> joke telegram
POST /predict       boarding ticket -> survival probability + chart data
GET  /api/regatta   cross-validation results of the four contenders
GET  /api/telegraph is the wireless line (Ollama) open?
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app import chat as telegraph
from app import model
from app.data import PORTS, load_passengers

HERE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=HERE / "templates")


@asynccontextmanager
async def lifespan(_: FastAPI):
    model.get_bundle()  # load (or train) model.joblib before the first passenger boards
    warm = asyncio.create_task(telegraph.warm_up())  # wake the telegraphist without blocking startup
    yield
    warm.cancel()


app = FastAPI(title="TITANIC — The Unsinkable Experience", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")

TICKET_TITLES = ["Mr", "Mrs", "Miss", "Master", "Dr", "Rev", "Col", "Major", "Capt",
                 "Lady", "Sir", "Countess", "Don", "Mme", "Mlle", "Ms"]


# ---------------------------------------------------------------- pages

def _page(request: Request, name: str, **ctx: Any) -> HTMLResponse:
    return templates.TemplateResponse(request, name, {"page": name.removesuffix(".html"), **ctx})


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    df = load_passengers()
    return _page(request, "home.html", souls=len(df), survivors=int(df.Survived.sum()))


@app.get("/telegraphist", response_class=HTMLResponse)
def telegraphist(request: Request) -> HTMLResponse:
    suggestions = [
        "How many women were on board?",
        "Who was the oldest passenger?",
        "Which class had the most survivors?",
        "What was the most expensive fare?",
    ]
    return _page(request, "telegraphist.html", suggestions=suggestions, llm=telegraph.OLLAMA_MODEL)


@app.get("/bridge", response_class=HTMLResponse)
def bridge(request: Request) -> HTMLResponse:
    df = load_passengers()
    median_fares = {int(k): round(float(v), 2) for k, v in df.groupby("Pclass").Fare.median().items()}
    return _page(request, "bridge.html", titles=TICKET_TITLES, ports=PORTS, median_fares=median_fares,
                 regatta=model.regatta(), baseline=round(1 - float(df.Survived.mean()), 4))


# ---------------------------------------------------------------- API

class ChatIn(BaseModel):
    message: str = Field("", max_length=1000)
    history: list[dict[str, Any]] = Field(default_factory=list, max_length=40)
    prediction: dict[str, Any] | None = None


@app.post("/chat")
async def post_chat(body: ChatIn) -> dict[str, Any]:
    if body.prediction is not None:
        return await telegraph.joke(body.prediction)
    if not body.message.strip():
        raise HTTPException(422, "EMPTY TELEGRAM STOP PLEASE WRITE A MESSAGE STOP")
    return await telegraph.chat(body.message.strip(), body.history)


class PassengerIn(BaseModel):
    name: str = Field("", max_length=80)
    sex: Literal["male", "female"]
    age: float = Field(ge=0, le=100)
    pclass: Literal[1, 2, 3]
    fare: float = Field(ge=0, le=600)
    family_size: int = Field(1, ge=1, le=11)
    embarked: Literal["S", "C", "Q"]
    title: str = Field("Mr", max_length=20)


@app.post("/predict")
def post_predict(p: PassengerIn) -> dict[str, Any]:
    if p.title not in TICKET_TITLES:
        raise HTTPException(422, f"Unknown title {p.title!r}")
    return model.predict(p.model_dump())


@app.get("/api/telegraph")
async def get_telegraph_status() -> dict[str, Any]:
    return await telegraph.status()


@app.get("/api/regatta")
def get_regatta() -> dict[str, Any]:
    return model.regatta()


def run() -> None:
    """Console script `titanic-app`: start the server."""
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    print(f"\n  RMS TITANIC is boarding at http://127.0.0.1:{port}  (Ctrl+C to abandon ship)\n")
    uvicorn.run("app.main:app", host="127.0.0.1", port=port)
