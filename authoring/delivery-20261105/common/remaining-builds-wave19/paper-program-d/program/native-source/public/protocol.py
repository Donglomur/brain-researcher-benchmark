"""Strict, source-scoped artifact interface; stdlib only. No scientific execution."""
import hashlib
import json
import math
import re
from pathlib import Path

REVISION = "2c15edf4e770165fc3962dcc3920c8bcaf555bed"
MAX_BYTES = 64 * 1024 * 1024
FIELDS = ("covariance", "svca2", "svca", "svca_variance", "pc_acg", "dmd")


def need(ok, message):
    if not ok:
        raise ValueError(message)


def keys(value, wanted, where):
    need(type(value) is dict and set(value) == set(wanted), where + ": exact keys")


def finite(value):
    need(type(value) in (float, int), "Finite real scalar, excluding bool")
    try:
        need(math.isfinite(value), "Finite real scalar")
    except OverflowError as exc:
        raise ValueError("Finite representable real scalar") from exc
    return value


def vector(value, length):
    need(type(value) is list and len(value) == length, "Exact vector support")
    for number in value:
        finite(number)


def matrix(value, rows, columns):
    need(type(value) is list and len(value) == rows, "Exact matrix support")
    for row in value:
        vector(row, columns)


def no_duplicate_keys(pairs):
    out = {}
    for key, value in pairs:
        need(key not in out, "Duplicate JSON key")
        out[key] = value
    return out


def decode(raw):
    need(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES, "Bounded JSON")
    def reject(token):
        raise ValueError("Nonfinite JSON token: " + token)
    return json.loads(raw, object_pairs_hook=no_duplicate_keys, parse_constant=reject)


def cohort():
    return json.loads(Path(__file__).with_name("COHORT.json").read_text())["sessions"]


def validate_design(design, sessions=None):
    """Operator supplies this only after actual shape/identity census, never a candidate."""
    sessions = cohort() if sessions is None else sessions
    keys(design, ("schema", "source_revision", "records"), "Design")
    need(design["schema"] == "critical_init_design_v1" and design["source_revision"] == REVISION,
         "Pinned scientific design")
    rows = design["records"]
    need(type(rows) is list and len(rows) == len(sessions), "Complete design roster")
    dims = ("n_fig2", "t_fig2", "ntrain_fig2", "ntest_fig2", "n_fig3", "t_fig3",
            "ntrain_fig3", "ntest_fig3", "dmd_modes")
    for row, session in zip(rows, sessions):
        keys(row, ("session_id", "input_sha256", *dims), "Design record")
        need(row["session_id"] == session["session_id"], "Exact source session order")
        need(type(row["input_sha256"]) is str and re.fullmatch("[0-9a-f]{64}", row["input_sha256"]),
             "Actual raw input SHA256 required")
        for name in dims:
            need(type(row[name]) is int and 0 < row[name] <= 10000000, "Typed finite geometry")
        need(row["ntrain_fig2"] + row["ntest_fig2"] == row["n_fig2"], "Fig2 split population")
        need(row["ntrain_fig3"] + row["ntest_fig3"] == row["n_fig3"], "Fig3 split population")
        need(row["n_fig2"] == row["n_fig3"] and row["t_fig2"] <= row["t_fig3"], "Same neurons, only Fig2 may crop time")
        if session["modality"] == "ephys":
            need(row["t_fig2"] == row["t_fig3"], "Ephys panels use identical raster duration")
        need(min(row["n_fig2"], row["ntrain_fig2"], row["ntest_fig2"]) >= 500,
             "All 500 published fit-window ranks required; no truncation fallback")
        need(min(row["ntrain_fig3"], row["ntest_fig3"]) >= session["pc_rows"], "All declared PCs required")
        need(row["t_fig2"] >= 2000 and row["t_fig3"] >= 2000, "100-lag block support")
        need(row["dmd_modes"] == min(1000, row["n_fig3"]), "Source DMD mode count")
    return design


def validate_result(value, design, design_sha256, sessions=None):
    sessions = cohort() if sessions is None else sessions
    validate_design(design, sessions)
    keys(value, ("schema", "design_sha256", "records"), "Result")
    need(value["schema"] == "critical_init_result_v1" and value["design_sha256"] == design_sha256,
         "Exact trusted design identity")
    need(type(value["records"]) is list and len(value["records"]) == len(sessions), "All session outputs required")
    for row, geometry, session in zip(value["records"], design["records"], sessions):
        keys(row, ("session_id", *FIELDS), "Result record")
        need(row["session_id"] == session["session_id"], "Unique exact ordered session support")
        for name in FIELDS[:4]:
            vector(row[name], 500)
        need(all(x >= 0 for x in row["svca2"]) and math.fsum(row["svca2"]) > 0,
             "SVCA2 nonnegative and nonzero; no undefined shape normalization")
        matrix(row["pc_acg"], session["pc_rows"], 100)
        matrix(row["dmd"], geometry["dmd_modes"], 2)
    return value


def design_pin(raw):
    return hashlib.sha256(raw).hexdigest()
