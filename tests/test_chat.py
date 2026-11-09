"""The Telegraphist: LINE CUT when offline, the tool loop, and the number guard (with a scripted fake model)."""

import pytest

from app import chat as telegraph


def test_line_cut_when_ollama_is_down(client):
    r = client.post("/chat", json={"message": "How many women were on board?"})
    assert r.status_code == 200
    data = r.json()
    assert data["line_cut"] is True
    assert data["reply"].startswith("LINE CUT STOP")
    assert "ollama serve" in data["reply"] and "ollama pull" in data["reply"]


def test_status_reports_offline(client):
    assert client.get("/api/telegraph").json()["online"] is False


def test_empty_message_rejected(client):
    assert client.post("/chat", json={"message": "   "}).status_code == 422


def test_joke_falls_back_to_the_archive(client):
    r = client.post("/chat", json={"prediction": {"probability": 0.12, "verdict": "sinking", "model": "X"}})
    data = r.json()
    assert "12%" in data["reply"] and data["line_cut"] is True


class FakeOllama:
    """Replays scripted assistant messages and records what was sent."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    async def __call__(self, messages, tools, think=False):
        self.calls.append({"messages": list(messages), "tools": tools})
        return self.replies.pop(0)


def tool_call(code):
    return {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "query_data", "arguments": {"code": code}}}]}


def test_tool_loop_runs_query_data(client, monkeypatch):
    fake = FakeOllama(
        tool_call('(df.Sex == "female").sum()'),
        {"role": "assistant", "content": "Heavens, 314 ladies were aboard STOP The key trembles STOP"},
    )
    monkeypatch.setattr(telegraph, "_ollama", fake)
    data = client.post("/chat", json={"message": "How many women were on board?"}).json()
    assert data["steps"] == [{"code": '(df.Sex == "female").sum()', "ok": True, "result": "314"}]
    assert "314" in data["reply"] and data["verified"] is True and data["corrected"] is False
    # the tool result was fed back to the model
    assert fake.calls[1]["messages"][-1] == {"role": "tool", "tool_name": "query_data", "content": "314"}
    assert fake.calls[0]["tools"][0]["function"]["name"] == "query_data"


def test_wrong_numbers_are_corrected(client, monkeypatch):
    fake = FakeOllama(
        tool_call('(df.Sex == "female").sum()'),
        {"role": "assistant", "content": "THREE HUNDRED AND FOURTEEN LADIES STOP"},
        {"role": "assistant", "content": "314 ladies, by Marconi STOP"},
    )
    monkeypatch.setattr(telegraph, "_ollama", fake)
    data = client.post("/chat", json={"message": "How many women?"}).json()
    assert data["reply"] == "314 ladies, by Marconi STOP"
    assert data["corrected"] is True and data["verified"] is True
    assert "TELEGRAPH CHECK FAILED" in fake.calls[2]["messages"][-1]["content"]


def test_stubborn_wrong_numbers_fall_back_to_exact_figures(client, monkeypatch):
    fake = FakeOllama(
        tool_call("df.Fare.max()"),
        {"role": "assistant", "content": "The dearest ticket cost 999 pounds STOP"},
        {"role": "assistant", "content": "Truly, 1000 pounds STOP"},
    )
    monkeypatch.setattr(telegraph, "_ollama", fake)
    data = client.post("/chat", json={"message": "Most expensive fare?"}).json()
    assert data["verified"] is False
    assert "512.3292" in data["reply"] and "999" not in data["reply"]


def test_tool_errors_are_reported_to_the_model(client, monkeypatch):
    fake = FakeOllama(
        tool_call("open('titanic.csv')"),
        {"role": "assistant", "content": "The apparatus refused STOP"},
    )
    monkeypatch.setattr(telegraph, "_ollama", fake)
    data = client.post("/chat", json={"message": "Read the file"}).json()
    assert data["steps"][0]["ok"] is False
    assert fake.calls[1]["messages"][-1]["content"].startswith("ERROR: refused")


@pytest.mark.parametrize(
    "reply, problems",
    [
        ("314 ladies STOP", 0),
        ("61.29% of children survived STOP", 0),
        ("61% survived and 39% perished STOP", 0),   # proportions and complements
        ("£512.33 STOP", 0),
        ("In 1912, class 3 STOP", 0),
        ("three hundred and fourteen ladies STOP", 1),
        ("315 ladies STOP", 1),
        ("13 percent five four STOP", 1),
    ],
)
def test_number_guard(reply, problems):
    steps = [
        {"ok": True, "result": "314"},
        {"ok": True, "result": "0.612903"},
        {"ok": True, "result": "512.3292"},
    ]
    assert len(telegraph.check_numbers(reply, steps)) == problems


def test_telegraphese():
    assert telegraph._telegraphese("Hello there.") == "Hello there STOP"
    assert telegraph._telegraphese("**Bold** figure! STOP.") == "Bold figure STOP"
    assert telegraph._telegraphese("") .endswith("STOP")
