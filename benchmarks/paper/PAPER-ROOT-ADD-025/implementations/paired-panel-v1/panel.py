"""Complete declared-support pairing of Park S11 decoder score records.

This operator component does not infer a source roster, aggregate source axes,
decide superiority, authenticate model predictions, or expose an agent API.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable

import numpy as np

SOURCE_COMMIT = "8b79caa5b95fadce826ea39bf6c69828991a4b28"
DECODER_SHA256 = "ac5e646fcbf6a630b11aa4be09e74e9047064749fee76043582a8f699fd24871"
SOURCE_ORDINALS = tuple(x for x in range(1, 35) if x not in (12, 14, 19, 21))
CONTEXTS = ("attn", "choice")
CLASSES = ("consistent", "inconsistent", "all")
METRICS = ("corr_S_Shat", "corr_E_Ehat", "corr_E_Shat")
FOLD_AXES = ["repeat", "fold", "metric", "PC", "time"]
MEAN_AXES = ["repeat", "metric", "PC", "time"]
HEX = re.compile(r"[0-9a-f]{64}\Z")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _fields(value: Any, names: set[str], label: str) -> None:
    _require(type(value) is dict and set(value) == names, f"invalid {label} fields")


def _text(value: Any) -> bool:
    return type(value) is str and bool(value.strip())


def _hash(value: Any) -> bool:
    return type(value) is str and HEX.fullmatch(value) is not None


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _key(value: dict[str, Any]) -> tuple[str, str, str]:
    return value["participant"], value["parcel"], value["context"]


def validate_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate a declared full S11 support; this does not verify its provenance.

    Each supplied ordinal-to-participant mapping and parcel/PC roster still
    requires independent authentication to the original source observations.
    Different contexts/participants may have different declared PC counts.
    """
    _fields(manifest, {"schema", "source_commit", "cohort", "entries"}, "manifest")
    _require(manifest["schema"] == "park_s11_paired_panel_manifest/v1"
             and manifest["source_commit"] == SOURCE_COMMIT, "wrong source manifest")
    cohort = manifest["cohort"]
    _require(type(cohort) is list and len(cohort) == 30, "S11 requires 30 source ordinals")
    for row in cohort:
        _fields(row, {"source_ordinal", "participant"}, "cohort row")
        _require(type(row["source_ordinal"]) is int and _text(row["participant"]),
                 "invalid cohort identity")
    _require(tuple(row["source_ordinal"] for row in cohort) == SOURCE_ORDINALS,
             "wrong S11 source ordinal order or membership")
    people = [row["participant"] for row in cohort]
    _require(len(set(people)) == 30, "duplicate source participant")
    entries = manifest["entries"]
    _require(type(entries) is list and len(entries) >= 60, "incomplete declared panel")
    seen = set()
    coverage = {p: set() for p in people}
    for entry in entries:
        _fields(entry, {"participant", "parcel", "context", "n_components", "design_sha256"},
                "manifest entry")
        _require(entry["participant"] in coverage and _text(entry["parcel"])
                 and entry["context"] in CONTEXTS, "unknown panel identity")
        _require(type(entry["n_components"]) is int and 1 <= entry["n_components"] <= 15,
                 "invalid original PC count")
        _require(_hash(entry["design_sha256"]), "invalid frozen design hash")
        key = _key(entry)
        _require(key not in seen, "duplicate panel identity")
        seen.add(key)
        coverage[entry["participant"]].add(entry["context"])
    _require(all(c == set(CONTEXTS) for c in coverage.values()), "missing participant/context")
    return entries


def _design(design: dict[str, Any], entry: dict[str, Any]) -> None:
    _require(type(design) is dict and _hash(design.get("design_sha256")), "invalid design")
    unsigned = {k: v for k, v in design.items() if k != "design_sha256"}
    _require(_digest(unsigned) == design["design_sha256"] == entry["design_sha256"],
             "frozen design hash mismatch")
    _require(design.get("schema") == "park_source_decoder_design/v2"
             and design.get("source_commit") == SOURCE_COMMIT, "wrong decoder design")
    for field in ("participant", "parcel", "context", "n_components"):
        _require(design.get(field) == entry[field], "design panel identity mismatch")
    _require((design.get("n_times"), design.get("n_folds"), design.get("n_repeats")) == (129, 10, 5),
             "source axis dimensions changed")
    _require(design.get("fold_unit") == "pooled_sample_row"
             and design.get("generative_selection") == "fgmu_0_all_finite",
             "source split or population changed")
    cells = design.get("cells")
    expected = [(pair, name) for pair in range(1, 7) for name in CLASSES]
    _require(type(cells) is list and len(cells) == 18, "design cell support incomplete")
    _require([(c.get("pair"), c.get("consistency")) for c in cells] == expected,
             "design cell support/order changed")
    for cell in cells:
        _require(type(cell.get("available_rows")) is int
                 and type(cell.get("matched_rows")) is int
                 and 0 <= cell["matched_rows"] <= cell["available_rows"], "invalid source row counts")
        planned = cell["matched_rows"] >= 10
        _require(cell.get("status") == ("planned" if planned else "insufficient_rows_for_10_folds"),
                 "source row availability changed")
    # Full behavior/fold replay is the existing decoder's responsibility.


def _scores(scores: dict[str, Any], design: dict[str, Any]) -> list[dict[str, Any]]:
    _fields(scores, {"schema", "design_sha256", "participant", "parcel", "context", "metric_names",
                     "fold_score_axes", "mean_fold_axes", "cells"}, "score record")
    _require(scores["schema"] == "park_source_decoder_scores/v2", "wrong score schema")
    _require(scores["design_sha256"] == design["design_sha256"]
             and _key(scores) == _key(design), "score design/identity mismatch")
    _require(scores["metric_names"] == list(METRICS) and scores["fold_score_axes"] == FOLD_AXES
             and scores["mean_fold_axes"] == MEAN_AXES, "metric identity or source axes changed")
    cells = scores["cells"]
    _require(type(cells) is list and len(cells) == 18, "score cell support incomplete")
    means = []
    for source_cell, score_cell in zip(design["cells"], cells):
        core = {"pair", "consistency", "available_rows", "matched_rows", "status", "fold_scores",
                "mean_fold_scores", "undefined_fold_correlations"}
        planned = source_cell["status"] == "planned"
        _fields(score_cell, core | ({"prediction_sha256"} if planned else set()), "score cell")
        for field in ("pair", "consistency", "available_rows", "matched_rows"):
            _require(score_cell[field] == source_cell[field], "score cell support/order changed")
        if not planned:
            _require(score_cell["status"] == "insufficient_rows_for_10_folds"
                     and all(score_cell[k] is None for k in
                             ("fold_scores", "mean_fold_scores", "undefined_fold_correlations")),
                     "unavailable source cell must remain present and unscored")
            means.append({"mean": None, "prediction_sha256": None})
            continue
        hashes = score_cell["prediction_sha256"]
        _require(type(hashes) is list and len(hashes) == 2 and all(_hash(h) for h in hashes),
                 "both prediction identities required")
        fold = np.asarray(score_cell["fold_scores"], dtype=np.float64)
        mean = np.asarray(score_cell["mean_fold_scores"], dtype=np.float64)
        _require(fold.shape == (5, 10, 3, design["n_components"], 129)
                 and mean.shape == (5, 3, design["n_components"], 129), "score shape mismatch")
        _require(not np.isinf(fold).any() and not np.isinf(mean).any(), "infinite correlation")
        _require(np.all(np.abs(fold[np.isfinite(fold)]) <= 1), "correlation outside [-1,1]")
        undefined = int(np.isnan(fold).sum())
        _require(type(score_cell["undefined_fold_correlations"]) is int
                 and score_cell["undefined_fold_correlations"] == undefined, "undefined count mismatch")
        _require(score_cell["status"] == ("scored" if undefined == 0 else "undefined_fold_correlations"),
                 "undefined score status mismatch")
        _require(np.array_equal(mean, np.mean(fold, axis=1), equal_nan=True),
                 "mean-fold score differs from full fold arithmetic")
        means.append({"mean": mean.copy(), "prediction_sha256": list(hashes)})
    return means


def compare_panel(manifest: dict[str, Any], candidate: Iterable[dict[str, Any]],
                  author: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Pair every declared design, preserving signed metrics and undefined cells.

    Inputs are ordered iterables of {design, scores} produced by the existing
    operator scorer. Both must exhaust exactly at the frozen roster boundary.
    Nothing is returned until all entries and both iterator endings validate.
    Output remains operator-owned and may contain identities and large arrays.
    """
    entries = validate_manifest(manifest)
    candidate, author = iter(candidate), iter(author)
    result = []
    for expected in entries:
        try:
            cand, ref = next(candidate), next(author)
        except StopIteration as exc:
            raise ValueError("paired panel ended before complete support") from exc
        _fields(cand, {"design", "scores"}, "candidate panel item")
        _fields(ref, {"design", "scores"}, "author panel item")
        _design(cand["design"], expected)
        _design(ref["design"], expected)
        _require(cand["design"] == ref["design"], "candidate/author designs differ")
        cm = _scores(cand["scores"], cand["design"])
        rm = _scores(ref["scores"], ref["design"])
        paired = []
        for source_cell, c, r in zip(cand["design"]["cells"], cm, rm):
            cell = {k: source_cell[k] for k in ("pair", "consistency", "available_rows", "matched_rows")}
            cell.update(candidate_prediction_sha256=c["prediction_sha256"],
                        author_prediction_sha256=r["prediction_sha256"])
            if c["mean"] is None:
                cell.update(status="insufficient_rows_for_10_folds", candidate=None, author=None,
                            candidate_minus_author=None, candidate_defined=None, author_defined=None)
            else:
                cvalid, rvalid = np.isfinite(c["mean"]), np.isfinite(r["mean"])
                difference = np.full_like(c["mean"], np.nan)
                np.subtract(c["mean"], r["mean"], out=difference, where=cvalid & rvalid)
                cell.update(status="paired_arithmetic", candidate=c["mean"], author=r["mean"],
                            candidate_minus_author=difference, candidate_defined=cvalid,
                            author_defined=rvalid)
            paired.append(cell)
        result.append({**expected, "cells": paired})
    marker = object()
    _require(next(candidate, marker) is marker and next(author, marker) is marker,
             "unexpected extra panel support")
    return {
        "schema": "park_s11_paired_panel_comparison/v1",
        "manifest_sha256": _digest(manifest), "decoder_sha256": DECODER_SHA256,
        "declared_support_complete": True, "source_support_authenticated": False,
        "metric_names": list(METRICS), "axes": MEAN_AXES, "entries": result,
        "scalar_reduction": None, "reproduction": "unknown", "paper_win": None,
        "same_task_superiority": "unknown", "qualification": "paired_arithmetic_only",
    }
