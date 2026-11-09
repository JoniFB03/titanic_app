"""query_data: evaluate one read-only pandas expression against the passenger DataFrame.

Safety model (defence in depth):
1. The code is parsed as a single *expression* (ast "eval" mode), so statements, imports,
   assignments, deletes and loops can't even be parsed.
2. The AST is walked: only names `df`, `pd` and a few harmless builtins are allowed, no
   attribute starting with "_", no I/O or code-evaluating methods, no `inplace=`, no walrus.
3. It is evaluated with empty __builtins__ against a *copy* of the DataFrame, so even a
   mutating method cannot change the shared data.
"""

from __future__ import annotations

import ast
import json
import math
from typing import Any

import numpy as np
import pandas as pd

from app.data import load_passengers

MAX_CODE_LEN = 600
MAX_RESULT_CHARS = 2500

SAFE_BUILTINS: dict[str, Any] = {
    "len": len,
    "sum": sum,
    "min": min,
    "max": max,
    "round": round,
    "abs": abs,
    "sorted": sorted,
    "list": list,
    "dict": dict,
    "set": set,
    "tuple": tuple,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "range": range,
    "zip": zip,
    "enumerate": enumerate,
    "True": True,
    "False": False,
    "None": None,
}

# pandas helpers that are pure computations (no I/O, no code evaluation).
SAFE_PD_ATTRS = {
    "isna", "notna", "isnull", "notnull", "cut", "qcut", "crosstab", "concat",
    "to_numeric", "Series", "DataFrame", "NA", "Grouper", "IntervalIndex",
}

BLOCKED_ATTRS = {
    # code evaluation / arbitrary callables
    "eval", "query", "pipe", "transform_func", "mro", "gi_frame", "f_globals",
    # writing anywhere
    # (all to_* except SAFE_TO_ATTRS are blocked below: to_csv, to_string(path), …)
    # mutation helpers (we evaluate on a copy anyway, but be explicit)
    "update", "insert", "pop", "drop_duplicates_inplace", "set_flags",
    # plotting spins up matplotlib; styling/printing can write to buffers
    "plot", "hist", "boxplot", "style", "info",
    # str.format can reach attributes via "{0.attr}"
    "format", "format_map",
}

# The only to_* methods allowed: they return in-memory objects and take no file path.
SAFE_TO_ATTRS = {"to_dict", "to_list", "to_frame", "to_numpy"}

ALLOWED_NAMES = {"df", "pd"} | set(SAFE_BUILTINS)


class UnsafeQuery(ValueError):
    """Raised when an expression is rejected before evaluation."""


def _check(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.NamedExpr):
            raise UnsafeQuery("assignment expressions (:=) are not allowed")
        if isinstance(node, (ast.Await, ast.Yield, ast.YieldFrom)):
            raise UnsafeQuery("async/generator constructs are not allowed")
        if isinstance(node, ast.Name):
            if node.id.startswith("_"):
                raise UnsafeQuery(f"name '{node.id}' is not allowed")
            if node.id not in ALLOWED_NAMES and not _is_bound_locally(tree, node.id):
                raise UnsafeQuery(f"name '{node.id}' is not available — use df")
        if isinstance(node, ast.Attribute):
            attr = node.attr
            if attr.startswith("_"):
                raise UnsafeQuery(f"private attribute '{attr}' is not allowed")
            if attr in BLOCKED_ATTRS or attr.startswith("read_") or (
                attr.startswith("to_") and attr not in SAFE_TO_ATTRS
            ):
                raise UnsafeQuery(f"method '{attr}' is not allowed (read-only, no files)")
            if isinstance(node.value, ast.Name) and node.value.id == "pd" and attr not in SAFE_PD_ATTRS:
                raise UnsafeQuery(f"pd.{attr} is not allowed")
        if isinstance(node, ast.keyword) and node.arg == "inplace":
            raise UnsafeQuery("inplace=... is not allowed: the manifest is read-only")
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and "__" in node.value:
            raise UnsafeQuery("strings containing '__' are not allowed")


def _is_bound_locally(tree: ast.AST, name: str) -> bool:
    """Names introduced by lambda args or comprehension targets are fine (e.g. lambda s: s.max())."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Lambda):
            args = node.args
            all_args = args.posonlyargs + args.args + args.kwonlyargs
            if args.vararg:
                all_args.append(args.vararg)
            if args.kwarg:
                all_args.append(args.kwarg)
            if any(a.arg == name for a in all_args):
                return True
        if isinstance(node, ast.comprehension):
            for t in ast.walk(node.target):
                if isinstance(t, ast.Name) and t.id == name:
                    return True
    return False


def _to_jsonable(value: Any) -> Any:
    """Turn a pandas/numpy result into something JSON-friendly and reasonably small."""
    if isinstance(value, pd.DataFrame):
        if len(value) > 25:
            value = value.head(25)
        return json.loads(value.to_json(orient="split", default_handler=str))
    if isinstance(value, pd.Series):
        if len(value) > 40:
            value = value.head(40)
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, pd.Index):
        return [_to_jsonable(v) for v in list(value[:40])]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        return None if math.isnan(value) else round(value, 6)
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v) for v in list(value)[:40]]
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in list(value.items())[:40]}
    if value is pd.NA or value is None:
        return None
    if isinstance(value, (int, str, bool)):
        return value
    return str(value)


def query_data(code: str, df: pd.DataFrame | None = None) -> dict[str, Any]:
    """Evaluate a read-only pandas expression. Always returns a dict, never raises.

    {"ok": True, "result": <json-able>, "text": <short repr>} or {"ok": False, "error": "..."}
    """
    code = (code or "").strip()
    if not code:
        return {"ok": False, "error": "empty expression"}
    if len(code) > MAX_CODE_LEN:
        return {"ok": False, "error": f"expression longer than {MAX_CODE_LEN} characters"}
    try:
        tree = ast.parse(code, mode="eval")
    except SyntaxError as exc:
        return {"ok": False, "error": f"not a single Python expression: {exc.msg}"}
    try:
        _check(tree)
    except UnsafeQuery as exc:
        return {"ok": False, "error": f"refused: {exc}"}

    frame = (load_passengers() if df is None else df).copy(deep=True)
    env = {"__builtins__": {}, "df": frame, "pd": pd, **SAFE_BUILTINS}
    try:
        value = eval(compile(tree, "<query_data>", "eval"), env, {})  # noqa: S307 — AST-vetted
    except Exception as exc:  # pandas errors become tool feedback for the model
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:400]}

    result = _to_jsonable(value)
    text = value.to_string(max_rows=25) if isinstance(value, (pd.DataFrame, pd.Series)) else repr(result)
    if len(text) > MAX_RESULT_CHARS:
        text = text[:MAX_RESULT_CHARS] + "\n…(truncated)"
    return {"ok": True, "result": result, "text": text}
