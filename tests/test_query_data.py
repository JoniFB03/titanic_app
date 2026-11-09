"""query_data: right answers, read-only, and no way out of the sandbox."""

import json

import pytest

from app.chat import query_data  # the Telegraphist's tool, as exported by app/chat.py
from app.data import load_passengers


def ok(code):
    out = query_data(code)
    assert out["ok"], out
    json.dumps(out["result"])  # always JSON-serialisable
    return out["result"]


# ---------------------------------------------------------------- correct answers

def test_women_on_board():
    assert ok('(df.Sex == "female").sum()') == 314


def test_oldest_passenger():
    row = ok('df.loc[df.Age.idxmax(), ["Name", "Age"]]')
    assert row == {"Name": "Barkworth, Mr. Algernon Henry Wilson", "Age": 80.0}


def test_class_with_most_survivors():
    assert ok("df[df.Survived == 1].Pclass.value_counts().idxmax()") == 1
    assert ok('df.groupby("Pclass").Survived.sum()') == {"1": 136, "2": 87, "3": 119}


def test_most_expensive_fare():
    assert ok("df.Fare.max()") == pytest.approx(512.3292)


def test_rates_lambdas_and_comprehensions():
    rate = ok('df.groupby("Sex").Survived.mean()')
    assert rate["female"] == pytest.approx(0.742038, abs=1e-6)
    assert ok("df.groupby('Pclass').Age.apply(lambda s: s.median())")["1"] == 37.0
    assert ok("sorted([c for c in df.columns if c.startswith('S')])") == ["Sex", "SibSp", "Survived"]
    assert ok("pd.crosstab(df.Pclass, df.Survived).shape") == [3, 2]


def test_dataframe_results_are_truncated():
    out = ok("df.head(100)")
    assert len(out["data"]) == 25


def test_pandas_errors_are_returned_not_raised():
    out = query_data("df.NoSuchColumn.sum()")
    assert out["ok"] is False and "AttributeError" in out["error"]


# ---------------------------------------------------------------- the sandbox

@pytest.mark.parametrize(
    "code",
    [
        "import os",                                   # statements don't parse as an expression
        "__import__('os').system('echo hi')",          # dunder name
        "open('titanic.csv').read()",                  # builtins are not available
        "eval('1+1')",
        "exec('x=1')",
        "getattr(df, 'to_csv')('x.csv')",
        "df.to_csv('stolen.csv')",                     # writing files
        "df.to_string('stolen.txt')",
        "df.to_pickle('x.pkl')",
        "pd.read_csv('titanic.csv')",                  # reading files
        "pd.read_html('http://example.com')",          # network
        "pd.io",
        "df.__class__.__mro__",                        # escaping via dunders
        "df._mgr",
        "(lambda: 1).__globals__",
        "('{0._' + '_class_' + '_}').format(df)",      # str.format attribute access
        "'__class__'",
        "df.query('Age > 30')",                        # pandas mini-languages
        "df.eval('Age * 2')",
        "df.pipe(print)",
        "df.Age.fillna(0, inplace=True)",              # mutation
        "df.pop('Age')",
        "df.insert(0, 'x', 1)",
        "(x := 1)",
        "df.style",
        "",
        "df.Age.sum() + " + "1 + " * 300 + "1",           # too long
    ],
)
def test_refused(code):
    out = query_data(code)
    assert out["ok"] is False, f"should have been refused: {code!r} -> {out}"


def test_shared_dataframe_is_never_mutated():
    before = load_passengers().copy()
    for code in [
        "df.Age.fillna(0, inplace=True)",
        "df.drop(columns=['Age'])",
        "df.assign(Age=0)",
        "df.sort_values('Fare')",
        "df.Age.clip(upper=1)",
    ]:
        query_data(code)
    after = load_passengers()
    assert after.equals(before)
    assert list(after.columns) == list(before.columns)
