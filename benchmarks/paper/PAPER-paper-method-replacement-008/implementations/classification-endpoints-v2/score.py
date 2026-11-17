"""Complete six-endpoint BaRISTA classification comparison; no pooled task score.

Operator-only generated-software component. No neural preprocessing, fitting,
inference, source acquisition, scientific admission, or significance procedure.
"""
import hashlib
import importlib
import sys
from pathlib import Path

# Reuse the preserved primitive transport, source grid and tie-aware AUC.
# Refuse altered dependencies or a preloaded foreign generic module.
LEGACY = Path(__file__).resolve().parents[1] / "registered-runtime/source/classification"
DEPENDENCIES = {
    "protocol": ("public/protocol.py", "c75b683c36d2ffa3f67c7b0f0692f71492c796e73d31b02b1d126561c8644e25"),
    "io_contract": ("public/io_contract.py", "24e995c73499804d2adaed080f083b514ab94f4ba793d56aead06c989227da89"),
    "arrays": ("public/arrays.py", "d2fc53e1bc1a7da1fdb24be0e4029becae4164fdb2974955f410da7ac54a96dd"),
    "design": ("private/design.py", "6353a3dba7f1fdd258d3080e98e8655d9e3e0acde0e16e24fdb9dbe8af9c6fc1"),
    "metrics": ("private/metrics.py", "089a9be76a486ec0359efe616f143f0cbe7978e652bf01144caf1bee08bd4dbf"),
}
for name, (relative, expected_hash) in DEPENDENCIES.items():
    path = LEGACY / relative
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
        raise ValueError("Changed predecessor dependency: " + relative)
    if name in sys.modules and Path(getattr(sys.modules[name], "__file__", "")).resolve() != path:
        raise ValueError("Foreign preloaded module: " + name)
sys.path[:0] = [str(LEGACY / "public"), str(LEGACY / "private")]
for name in DEPENDENCIES:
    importlib.import_module(name)

from arrays import read_array
from design import ARMS, MODELS, PEOPLE, TASKS, TASK_ID, hexhash, validate_public
from io_contract import capture, parse, put
from metrics import aggregate, auc, exact_summary

JSON_CAP = 32_000_000
ARRAY_CAP = 4_000_000
TOTAL_CAP = 512_000_000
BASELINE_MODEL = "barista_parcels_channels"
PROVENANCE_KEYS = {
    "program_sha256", "training_config_sha256", "checkpoint_sha256",
    "exposure_audit_sha256", "execution_receipt_sha256", "baseline_artifact_sha256",
}


class InvalidSubmission(ValueError):
    """Candidate input failed before evaluator numerical inputs were opened."""


def outputs(public):
    """14 retained source controls plus candidate on every one of 770 contexts."""
    for arm in ARMS:
        for context in public["contexts"]:
            for model in (*MODELS, "improved"):
                yield dict(context, arm=arm, model=model)


def validate_gold(gold, public, public_body):
    """All-context independent comparator, per-context execution provenance.

    Hash syntax and support binding do not authenticate the claimed execution.
    This manifest is trusted operator input, never candidate-supplied evidence.
    """
    if (not isinstance(gold, dict) or set(gold) != {
        "schema", "panel_id", "public_sha256", "baseline_model", "contexts"
    } or gold["schema"] != "barista_endpoint_gold_v2"
            or gold["panel_id"] != public["panel_id"]
            or gold["public_sha256"] != hashlib.sha256(public_body).hexdigest()
            or gold["baseline_model"] != BASELINE_MODEL):
        raise ValueError("Exact v2 operator baseline/public binding required")
    rows = gold["contexts"]
    if not isinstance(rows, list) or len(rows) != len(public["contexts"]):
        raise ValueError("Complete 770-context trusted baseline required")
    for row, expected in zip(rows, public["contexts"]):
        if (not isinstance(row, dict) or set(row) != {
            "id", "query_ids_sha256", "labels", "trusted_parcels_channels", "provenance"
        } or any(row[k] != expected[k] for k in ("id", "query_ids_sha256"))):
            raise ValueError("Complete ordered baseline/query identity required")
        provenance = row["provenance"]
        if (not isinstance(provenance, dict) or set(provenance) != PROVENANCE_KEYS
                or any(not hexhash(provenance[k]) for k in PROVENANCE_KEYS)):
            raise ValueError("Per-context comparator provenance required")
    return rows


def admit(public, body, base):
    """Admit all 23,100 arrays before any private numerical input is opened."""
    try:
        sub = parse(body)
        if (not isinstance(sub, dict) or set(sub) != {
            "schema", "task_id", "panel_id", "predictions"
        } or sub["schema"] != "barista_endpoint_submission_v2"
                or sub["task_id"] != TASK_ID or sub["panel_id"] != public["panel_id"]):
            raise ValueError("Exact v2 task and panel required")
        expected = list(outputs(public))
        rows = sub["predictions"]
        if not isinstance(rows, list) or len(rows) != len(expected):
            raise ValueError("Complete 23,100 candidate and companion arrays required")
        total = 0
        for row, item in zip(rows, expected):
            keys = ("id", "arm", "model", "query_ids_sha256")
            if (not isinstance(row, dict) or set(row) != set(keys) | {"values"}
                    or any(row[k] != item[k] for k in keys)):
                raise ValueError("Exact ordered source prediction identity required")
            desc = row["values"]
            if (not isinstance(desc, dict) or type(desc.get("bytes")) is not int
                    or not 0 < desc["bytes"] <= ARRAY_CAP):
                raise ValueError("Per-array byte bound")
            total += desc["bytes"]
            if total > TOTAL_CAP:
                raise ValueError("Total candidate array byte bound")
            p = read_array(base, desc, shape=(item["query_count"],), cap=ARRAY_CAP)
            if p.dtype.kind != "f" or (p < 0).any() or (p > 1).any():
                raise ValueError("Complete finite class-one probabilities required")
        return rows, expected
    except (ValueError, TypeError, KeyError, OSError, OverflowError) as exc:
        raise InvalidSubmission(str(exc)) from exc


def endpoint_summaries(rows):
    """Preserve six endpoints, source pooling, and seven paired person summaries.

    SEM is descriptive sample-SD/sqrt(n), not an independent-person confidence
    interval. Fold and seed repetitions do not become independent participants.
    """
    result = []
    for protocol, tasks in TASKS.items():
        for task in tasks:
            selected = [r for r in rows if r["protocol"] == protocol and r["task"] == task]
            expected_pairs = [(person, fold, seed) for person in PEOPLE
                              for fold in ((0,) if protocol == "random_nonoverlap" else range(1, 6))
                              for seed in range(1, 6)]
            if [(r["person"], r["fold"], r["seed"]) for r in selected] != expected_pairs:
                raise ValueError("Complete paired endpoint roster required")
            summaries = {}
            person_rows = []
            for person in PEOPLE:
                repeated = [r for r in selected if r["person"] == person]
                person_rows.append({"person": person, "repeat_count": len(repeated), **{
                    key: exact_summary([r[key] for r in repeated])["mean"]
                    for key in ("candidate_auc", "baseline_auc", "paired_gain")
                }})
            for key in ("candidate_auc", "baseline_auc", "paired_gain"):
                summaries[key] = {
                    "source_cell_summary": exact_summary([r[key] for r in selected]),
                    "equal_person_summary": exact_summary([r[key] for r in person_rows]),
                }
            result.append({"protocol": protocol, "task": task,
                           "source_cell_count": len(selected), "person_count": len(PEOPLE),
                           "paired_people": person_rows, **summaries})
    return result


def grade(public_path, gold_path, submission_path):
    public_body = capture(public_path, cap=JSON_CAP)
    public = validate_public(parse(public_body))
    # The evaluator manifest and its labels/baselines are not opened until the
    # entire candidate and all retained companions have passed byte admission.
    try:
        rows, expected = admit(public, capture(submission_path, cap=JSON_CAP), Path(submission_path).parent)
    except (InvalidSubmission, OSError, ValueError) as exc:
        return {"task_id": TASK_ID, "status": "invalid_submission", "reason": str(exc),
                "private_numeric_inputs_opened": False, "paper_win_established": False}
    gold_rows = validate_gold(parse(capture(gold_path, cap=JSON_CAP)), public, public_body)
    by_id = {r["id"]: r for r in gold_rows}
    source_cells = {arm: [] for arm in ARMS}
    candidate_cells = {arm: [] for arm in ARMS}
    undefined = False
    for row, item in zip(rows, expected):
        bound = by_id[item["id"]]
        y = read_array(Path(gold_path).parent, bound["labels"], shape=(item["query_count"],), cap=ARRAY_CAP)
        p = read_array(Path(submission_path).parent, row["values"], shape=(item["query_count"],), cap=ARRAY_CAP)
        candidate = auc(y, p)
        record = {k: item[k] for k in ("id", "protocol", "person", "task", "fold", "seed", "model")}
        record.update(candidate)
        undefined |= candidate["roc_auc"] is None
        if item["model"] != "improved":
            source_cells[item["arm"]].append(record)
            continue
        baseline = read_array(Path(gold_path).parent, bound["trusted_parcels_channels"],
                              shape=(item["query_count"],), cap=ARRAY_CAP)
        trusted = auc(y, baseline)
        gain = None if candidate["roc_auc"] is None else candidate["roc_auc"] - trusted["roc_auc"]
        candidate_cells[item["arm"]].append({**record, "query_ids_sha256": item["query_ids_sha256"],
            "candidate_auc": candidate["roc_auc"], "baseline_auc": trusted["roc_auc"], "paired_gain": gain})
    companions = {arm: aggregate(source_cells[arm], [e for e in expected
                  if e["arm"] == arm and e["model"] != "improved"]) for arm in ARMS}
    return {
        "schema": "barista_endpoint_score_v2", "task_id": TASK_ID,
        "status": "undefined_required_support" if undefined else "defined",
        "panel_id": public["panel_id"], "baseline_model": BASELINE_MODEL,
        "classification_endpoints": {arm: endpoint_summaries(candidate_cells[arm]) for arm in ARMS},
        "source_companions": companions, "candidate_cells": candidate_cells,
        "source_cells": source_cells, "cross_task_primary": None,
        "reference_execution_authenticated": False, "historical_sem_parity_established": False,
        "scientific_significance_established": False, "paper_win_established": False,
        "scope": "Six original classification endpoints only; remaining original paper branches are required.",
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("public", "gold", "submission", "out"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = grade(Path(args.public), Path(args.gold), Path(args.submission))
    put(args.out, result)


if __name__ == "__main__":
    main()
