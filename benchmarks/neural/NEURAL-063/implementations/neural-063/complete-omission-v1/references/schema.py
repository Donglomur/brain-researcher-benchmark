"""Shared schema constants and strict row admission, not fitting algorithms."""
from __future__ import annotations
import hashlib
import json
import math
from owner.io import ContractError, canonical

CONTEXT = ("cre_line", "targeted_structure", "imaging_depth", "image_set", "passive", "experience_level", "session_number")
CATEGORIES = ("cre_line", "targeted_structure", "image_set", "passive", "experience_level", "session_number", "previous_1", "previous_2", "previous_3")
LAMBDA_GRID = (0.0001, 0.001, 0.01, 0.1, 1.0, 10.0, 100.0)
SEEDS = (63001, 63002, 63003, 63004, 63005)
MICE = {"fit": 73, "validation": 15, "query": 19}
ROW_BASE = {"id", "mouse", "session", "experiment", "split", "previous", "context"}
ROW_SCHEMA = "neural063_rows_v2"


def finite_number(x):
    if type(x) not in (int, float):
        raise ContractError("finite scalar required")
    try:
        v = float(x)
    except (ValueError, OverflowError):
        raise ContractError("unrepresentable scalar")
    if not math.isfinite(v):
        raise ContractError("nonfinite scalar")
    return v


def encode_level(value):
    """Canonical UTF-8 tuple encoding: a scalar is a one-element tuple."""
    obj = list(value) if isinstance(value, tuple) else [value]
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def object_hash(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def admit_rows(value, split, *, view="N", require_target=None, expected_mice=None):
    if split not in MICE or view not in ("T", "N"):
        raise ContractError("fixed split/view required")
    if require_target is None:
        require_target = split != "query"
    if not isinstance(value, dict) or value.get("schema") != ROW_SCHEMA or value.get("split") != split or set(value) != {"schema", "split", "rows"}:
        raise ContractError("exact split-row wrapper required")
    rows = value["rows"]
    if not isinstance(rows, list) or not rows:
        raise ContractError("nonempty complete row list required")
    allowed = ROW_BASE | ({"history"} if view == "N" else set()) | ({"target"} if require_target else set())
    seen, session_parent, experiment_parent = set(), {}, {}
    for r in rows:
        if not isinstance(r, dict) or set(r) != allowed or r["split"] != split:
            raise ContractError("row fields/split differ from allowed information view")
        for key in ("id", "mouse", "session", "experiment"):
            if not isinstance(r[key], str) or not r[key]:
                raise ContractError("opaque nonempty row identity required")
        if r["id"] in seen:
            raise ContractError("duplicate observation")
        seen.add(r["id"])
        if session_parent.setdefault(r["session"], r["mouse"]) != r["mouse"]:
            raise ContractError("session spans mice")
        if experiment_parent.setdefault(r["experiment"], (r["mouse"], r["session"])) != (r["mouse"], r["session"]):
            raise ContractError("experiment spans hierarchy")
        c = r["context"]
        if not isinstance(c, dict) or set(c) != set(CONTEXT):
            raise ContractError("exact seven context fields required")
        for key in ("cre_line", "targeted_structure", "image_set", "experience_level"):
            if not isinstance(c[key], str) or not c[key]:
                raise ContractError("missing categorical context")
        if type(c["passive"]) is not bool or type(c["session_number"]) is not int or c["session_number"] not in range(1, 7):
            raise ContractError("typed passive/session context required")
        finite_number(c["imaging_depth"])
        prev = r["previous"]
        if not isinstance(prev, list) or len(prev) != 3:
            raise ContractError("three preceding presentations required")
        starts = []
        for item in prev:
            if not isinstance(item, dict) or set(item) != {"image", "omitted", "start_relative_seconds"}:
                raise ContractError("preceding presentation shape mismatch")
            if not isinstance(item["image"], str) or not item["image"] or type(item["omitted"]) is not bool:
                raise ContractError("typed preceding identity required")
            starts.append(finite_number(item["start_relative_seconds"]))
        if not starts[0] < starts[1] < starts[2] < 0:
            raise ContractError("strictly preceding chronological stimuli required")
        if view == "N":
            h = r["history"]
            if not isinstance(h, list) or len(h) != 12 or any(not math.isfinite(finite_number(x)) for x in h) or h[-1] != 0:
                raise ContractError("twelve finite baseline-subtracted history bins required")
        if require_target:
            y = r["target"]
            if not isinstance(y, list) or len(y) != 3:
                raise ContractError("three complete target bins required")
            for x in y: finite_number(x)
    count = MICE[split] if expected_mice is None else expected_mice
    if type(count) is not int or count <= 0 or len({r["mouse"] for r in rows}) != count:
        raise ContractError("complete fixed mouse support required")
    if [r["id"] for r in rows] != sorted(seen):
        raise ContractError("deterministic opaque event order required")
    return rows


def timing_view(rows):
    """Explicit projection; neural values are neither copied nor inspected."""
    return [{k: r[k] for k in ROW_BASE | ({"target"} if "target" in r else set())} for r in rows]


def row_numeric(row, view):
    t = [finite_number(x["start_relative_seconds"]) for x in row["previous"]]
    vals = [t[1] - t[0], t[2] - t[1], -t[2], finite_number(row["context"]["imaging_depth"])]
    if view == "N":
        vals.extend(finite_number(x) for x in row["history"][:11])
    elif view != "T":
        raise ContractError("unknown information view")
    if any(not math.isfinite(x) for x in vals):
        raise ContractError("nonfinite derived numeric feature")
    return vals


def row_categories(row):
    c = row["context"]
    return [encode_level(c[k]) for k in CATEGORIES[:6]] + [encode_level((x["image"], x["omitted"])) for x in row["previous"]]


def expected_grid_ids():
    return [f"{view}-{basis}-{lam:g}" for view in ("T", "N") for basis in ("L", "Q") for lam in LAMBDA_GRID]
