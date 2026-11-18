"""Operator-only Figure 4D draw-identity checks and paired prediction scoring.

No splitting, sampling, fitting or source preparation occurs here. A trusted
operator supplies the source row metadata and shared draw ledger independently
of participant predictions. Ledger consistency is not execution authenticity.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import re

TASK = "PAPER-FIND-ADD-006"
REPEATS = 100
SCORER_SHA256 = "e729def33213d40812c06193f1336e326753dbdb10bf72282fa59522217c4843"
HEX = re.compile(r"[0-9a-f]{64}\Z")
METHODS = ("author", "candidate")
FIELDS = {"Boot_rep", "Draw_occurrence", "PV_id", "Real_label", "Pred_label", "Condition"}
MAX_MEMBER_BYTES = 64 * 1024 * 1024


class DrawError(ValueError):
    """Inputs would change the declared source support or pairing."""


def require(condition, message):
    if not condition:
        raise DrawError(message)


def exact(obj, keys, name):
    require(type(obj) is dict and set(obj) == set(keys), f"unexpected {name} fields")


def literal(value, name):
    require(type(value) is str and value and value.strip() == value,
            f"invalid {name}")
    return value


def digest(value, name):
    require(type(value) is str and HEX.fullmatch(value), f"invalid {name}")
    return value


def labels(value, name, length=None):
    require(type(value) is list and value, f"{name} must be a nonempty list")
    result = tuple(literal(item, name) for item in value)
    require(len(set(result)) == len(result), f"duplicate {name}")
    require(length is None or len(result) == length, f"wrong {name} count")
    return result


def scorer_module():
    path = Path(__file__).resolve().parent.parent / "figure4d-prediction-scoring-v1" / "scorer.py"
    body = path.read_bytes()
    require(hashlib.sha256(body).hexdigest() == SCORER_SHA256,
            "prediction scorer source changed; review its dependency before use")
    spec = importlib.util.spec_from_file_location("hierarchy_prediction_scoring", path)
    module = importlib.util.module_from_spec(spec)
    # Execute the captured, verified body instead of reopening a mutable path.
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def id_list(value, name, available, unique=False):
    require(type(value) is list and value, f"{name} must be nonempty")
    for item in value:
        require(type(item) is str and item in available, f"{name}: unknown source PV")
    require(not unique or len(set(value)) == len(value), f"{name}: duplicate partition PV")
    return tuple(value)


def stratum_counts(ids, vectors):
    counts = Counter((vectors[key]["context"], vectors[key]["condition"]) for key in ids)
    return [{"context": context, "condition": condition, "count": count}
            for (context, condition), count in sorted(counts.items())]


def validate_session(source, ledger, source_sha256, scoring):
    """Check identities and support; do not certify stratification or RNG history."""
    exact(source, {"schema", "animal", "date", "context_labels", "condition_labels",
                   "preparation_receipt_sha256", "vectors"}, "source")
    require(source["schema"] == "hierarchy-figure4d-pv-metadata/v1", "unknown source schema")
    animal, date = literal(source["animal"], "animal"), literal(source["date"], "date")
    require(animal in scoring.ROSTER and date in scoring.ROSTER[animal], "unknown source session")
    contexts = labels(source["context_labels"], "context labels", 2)
    conditions = labels(source["condition_labels"], "condition labels")
    digest(source["preparation_receipt_sha256"], "preparation receipt digest")
    require(type(source["vectors"]) is list and source["vectors"], "source vectors required")
    vectors = {}
    for row in source["vectors"]:
        exact(row, {"pv_id", "context", "condition"}, "source vector")
        key = literal(row["pv_id"], "PV id")
        require(key not in vectors, "duplicate source PV identity")
        require(row["context"] in contexts and row["condition"] in conditions,
                "source vector has undeclared labels")
        vectors[key] = dict(row)
    expected_strata = {(a, b) for a in contexts for b in conditions}
    require({(v["context"], v["condition"]) for v in vectors.values()} == expected_strata,
            "declared source context/condition support absent")
    exact(ledger, {"schema", "source_sha256", "generation", "repeats"}, "ledger")
    require(ledger["schema"] == "hierarchy-figure4d-draw-ledger/v1", "unknown ledger schema")
    require(digest(ledger["source_sha256"], "source digest") == digest(source_sha256, "source digest"),
            "draw ledger belongs to another source metadata body")
    generation = ledger["generation"]
    exact(generation, {"kind", "receipt_sha256", "sample_fraction"}, "generation")
    require(generation["kind"] in {"historical_record", "regenerated_original_protocol"},
            "explicit historical versus regenerated draw provenance required")
    digest(generation["receipt_sha256"], "generation receipt digest")
    fraction = generation["sample_fraction"]
    require(type(fraction) in (int, float) and 0 < fraction <= 1 and math.isfinite(fraction),
            "sample_fraction must be explicit and in (0,1]")
    require(type(ledger["repeats"]) is list and len(ledger["repeats"]) == REPEATS,
            "all 100 repetition slots required")
    n_test = (3 * len(vectors) + 9) // 10  # ceil(0.3 * N), not rounding to nearest.
    draws, summaries = {}, []
    for row in ledger["repeats"]:
        exact(row, {"repeat", "train_partition", "test_partition", "train_draw", "test_draw"}, "repeat")
        rep = row["repeat"]
        require(type(rep) is int and 0 <= rep < REPEATS and rep not in draws,
                "unknown or duplicate repetition")
        train = id_list(row["train_partition"], "train partition", vectors, unique=True)
        test = id_list(row["test_partition"], "test partition", vectors, unique=True)
        require(len(test) == n_test and len(train) == len(vectors) - n_test,
                "partition is not the declared original 70/30 PV split size")
        require(set(train).isdisjoint(test) and set(train) | set(test) == set(vectors),
                "partitions overlap or omit source PVs")
        train_draw = id_list(row["train_draw"], "train draw", set(train))
        test_draw = id_list(row["test_draw"], "test draw", set(test))
        require(len(train_draw) == int(fraction * len(train)) and
                len(test_draw) == int(fraction * len(test)), "bootstrap sample size changed")
        require({(vectors[k]["context"], vectors[k]["condition"]) for k in train_draw} == expected_strata,
                "training draw omits source context/condition combination")
        # Keep occurrence order, even when the same source PV was sampled again.
        draws[rep] = test_draw
        summaries.append({"repeat": rep, "train_partition_count": len(train),
                          "test_partition_count": len(test), "train_draw_count": len(train_draw),
                          "test_draw_count": len(test_draw),
                          "train_partition_strata": stratum_counts(train, vectors),
                          "test_partition_strata": stratum_counts(test, vectors),
                          "train_draw_strata": stratum_counts(train_draw, vectors),
                          "test_draw_strata": stratum_counts(test_draw, vectors)})
    return {"animal": animal, "date": date, "contexts": contexts, "conditions": conditions,
            "vectors": vectors, "draws": draws, "summaries": sorted(summaries, key=lambda r: r["repeat"]),
            "generation": dict(generation), "source_sha256": source_sha256}


def integer_text(value, name):
    require(type(value) is str and re.fullmatch(r"0|[1-9][0-9]*", value), f"invalid {name}")
    return int(value)


def bound_prediction_rows(rows, validated):
    """Join every test occurrence exactly once; CSV order may differ by arm."""
    seen = set()
    for row in rows:
        exact(row, FIELDS, "prediction row")
        rep = integer_text(row["Boot_rep"], "Boot_rep")
        occurrence = integer_text(row["Draw_occurrence"], "Draw_occurrence")
        require(rep in validated["draws"] and occurrence < len(validated["draws"][rep]),
                "prediction occurrence outside declared shared draw")
        identity = (rep, occurrence)
        require(identity not in seen, "duplicate prediction occurrence")
        key = validated["draws"][rep][occurrence]
        expected = validated["vectors"][key]
        require(row["PV_id"] == key, "prediction substituted another PV at the same occurrence")
        require(row["Real_label"] == expected["context"] and row["Condition"] == expected["condition"],
                "prediction target/condition differs from independent operator metadata")
        require(row["Pred_label"] in validated["contexts"], "undeclared predicted context")
        seen.add(identity)
        yield {"Boot_rep": row["Boot_rep"], "Real_label": row["Real_label"],
               "Pred_label": row["Pred_label"], "Condition": row["Condition"]}
    require(len(seen) == sum(len(ids) for ids in validated["draws"].values()),
            "prediction export omits shared draw occurrences")


def score_session(source, ledger, source_sha256, exports, scoring=None):
    scoring = scorer_module() if scoring is None else scoring
    validated = validate_session(source, ledger, source_sha256, scoring)
    exact(exports, METHODS, "method exports")
    results = {}
    for method in METHODS:
        exact(exports[method], scoring.ARMS, "comparison arms")
        results[method] = {}
        for arm in scoring.ARMS:
            rows = bound_prediction_rows(exports[method][arm], validated)
            results[method][arm] = scoring.score_rows(
                rows, context_labels=validated["contexts"], condition_labels=validated["conditions"],
                condition_column="Condition", aggregation="global" if arm.startswith("global") else "conditional")
    return {"animal": validated["animal"], "date": validated["date"],
            "source_sha256": validated["source_sha256"], "generation": validated["generation"],
            "draw_support": validated["summaries"], "methods": results,
            "prediction_rows_bound_to_shared_occurrences": True,
            "training_execution_verified": False, "stratification_algorithm_verified": False,
            "source_preparation_verified": False, "published_metric_convention_selected": False,
            "paper_win": None, "scientific_outcome": "unknown"}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def json_body(body):
    return json.loads(body, object_pairs_hook=unique_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(DrawError("nonfinite JSON")))


def pinned_body(base, descriptor):
    exact(descriptor, {"path", "bytes", "sha256"}, "file descriptor")
    path = Path(base) / literal(descriptor["path"], "path")
    size = descriptor["bytes"]
    require(type(size) is int and 0 < size <= MAX_MEMBER_BYTES, "file size outside operator limit")
    digest(descriptor["sha256"], "file digest")
    with path.open("rb") as handle:
        body = handle.read(size + 1)
    require(len(body) == size and hashlib.sha256(body).hexdigest() == descriptor["sha256"],
            "file does not match captured bytes/hash")
    return body


def csv_rows(body):
    reader = csv.DictReader(io.StringIO(body.decode("utf-8-sig"), newline=""))
    require(reader.fieldnames is not None and len(reader.fieldnames) == len(FIELDS) and
            set(reader.fieldnames) == FIELDS, "CSV needs exactly the six identity/prediction fields")
    for row in reader:
        require(None not in row and all(value is not None for value in row.values()), "malformed CSV row")
        yield row


def score_panel(manifest, base_directory):
    exact(manifest, {"schema", "sessions"}, "panel")
    require(manifest["schema"] == "hierarchy-figure4d-paired-panel/v1", "unknown panel schema")
    scoring = scorer_module()
    expected = {(animal, date) for animal, dates in scoring.ROSTER.items() for date in dates}
    require(type(manifest["sessions"]) is list and len(manifest["sessions"]) == len(expected),
            "complete 25-session source panel required")
    results, seen, export_paths = [], set(), set()
    for session in manifest["sessions"]:
        exact(session, {"animal", "date", "source", "ledger", "exports"}, "panel session")
        identity = (literal(session["animal"], "animal"), literal(session["date"], "date"))
        require(identity in expected and identity not in seen, "unknown or duplicate panel session")
        source = json_body(pinned_body(base_directory, session["source"]))
        ledger = json_body(pinned_body(base_directory, session["ledger"]))
        require(type(source) is dict and type(ledger) is dict, "source and ledger must be objects")
        require((source.get("animal"), source.get("date")) == identity, "source session identity mismatch")
        exact(session["exports"], METHODS, "method exports")
        exports = {}
        for method in METHODS:
            exact(session["exports"][method], scoring.ARMS, "comparison arms")
            exports[method] = {}
            for arm, spec in session["exports"][method].items():
                body = pinned_body(base_directory, spec)
                identity_path = str((Path(base_directory) / spec["path"]).resolve())
                require(identity_path not in export_paths, "same prediction export reused for another method/arm/session")
                export_paths.add(identity_path)
                exports[method][arm] = csv_rows(body)
        results.append(score_session(source, ledger, session["source"]["sha256"], exports, scoring))
        seen.add(identity)
    return {"schema": "hierarchy-figure4d-paired-diagnostics/v1", "task_id": TASK,
            "sessions": results, "session_count": len(seen), "animal_count": len(scoring.ROSTER),
            "qualification": "operator_metadata_and_prediction_identity_only",
            "cross_session_aggregate": None, "biological_uncertainty": None,
            "reproduction_outcome": "unknown", "paper_win": None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.manifest.open("rb") as handle:
            body = handle.read(MAX_MEMBER_BYTES + 1)
        require(len(body) <= MAX_MEMBER_BYTES, "panel manifest exceeds operator limit")
        print(json.dumps(score_panel(json_body(body), args.manifest.resolve().parent), allow_nan=False))
    except (DrawError, ValueError, OSError, UnicodeError, csv.Error) as exc:
        parser.exit(2, f"paired_draws: {exc}\n")


if __name__ == "__main__":
    main()
