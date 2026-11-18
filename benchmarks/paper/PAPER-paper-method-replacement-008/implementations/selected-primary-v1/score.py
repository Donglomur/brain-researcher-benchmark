"""BaRISTA's selected fixed-channel-mask language panel; operator use only.

No source acquisition, training, dataset selection, inference or significance
procedure is performed. The exact published-policy digest is a scope binding,
not evidence that raw support, execution or comparator competence is qualified.
"""
import hashlib
import importlib
from pathlib import Path
import sys

LEGACY = Path(__file__).resolve().parents[1] / "registered-runtime/source/classification"
DEPENDENCIES = {
    "protocol": ("public/protocol.py", "c75b683c36d2ffa3f67c7b0f0692f71492c796e73d31b02b1d126561c8644e25"),
    "io_contract": ("public/io_contract.py", "24e995c73499804d2adaed080f083b514ab94f4ba793d56aead06c989227da89"),
    "arrays": ("public/arrays.py", "d2fc53e1bc1a7da1fdb24be0e4029becae4164fdb2974955f410da7ac54a96dd"),
    "design": ("private/design.py", "6353a3dba7f1fdd258d3080e98e8655d9e3e0acde0e16e24fdb9dbe8af9c6fc1"),
    "metrics": ("private/metrics.py", "089a9be76a486ec0359efe616f143f0cbe7978e652bf01144caf1bee08bd4dbf"),
}
for name, (relative, expected) in DEPENDENCIES.items():
    path = LEGACY / relative
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError("Changed predecessor dependency: " + relative)
    if name in sys.modules and Path(getattr(sys.modules[name], "__file__", "")).resolve() != path:
        raise ValueError("Foreign preloaded module: " + name)
sys.path[:0] = [str(LEGACY / "public"), str(LEGACY / "private")]
for name in DEPENDENCIES:
    importlib.import_module(name)

from arrays import read_array
from design import ARMS, PEOPLE, SOURCE_PROTOCOL_SHA, TASK_ID, hexhash
from io_contract import capture, parse, put
from metrics import aggregate, auc, exact_summary
from protocol import digest

SCOPE_SHA256 = "bd0b8c8c17611f22bdaeb33bdad396814a8c8830b69ef6d3b5ff52824d8bc052"
TASKS = {
    "random_nonoverlap": ("sentence_onset", "speech_vs_nonspeech"),
    "chronological": ("sentence_onset_time", "speech_vs_nonspeech_time"),
}
SOURCE_MODELS = (
    "barista_channels_channels", "barista_parcels_channels", "barista_lobes_channels",
    "random_channels", "random_parcels", "random_lobes",
)
# Retains the independently supplied parcels/channels comparator from v2. Its
# competence, authenticity and information exposure still need qualification.
BASELINE_MODEL = "barista_parcels_channels"
PROVENANCE_KEYS = {
    "program_sha256", "training_config_sha256", "checkpoint_sha256",
    "exposure_audit_sha256", "execution_receipt_sha256", "baseline_artifact_sha256",
}
JSON_CAP = 32_000_000
ARRAY_CAP = 4_000_000
TOTAL_CAP = 512_000_000


def contexts():
    """All 420 selected original context slots, never a caller-picked subset."""
    return [
        {"id": f"{protocol}-sub{person}-{task}-f{fold}-s{seed}",
         "protocol": protocol, "person": person, "task": task, "fold": fold, "seed": seed}
        for protocol, tasks in TASKS.items() for person in PEOPLE for task in tasks
        for fold in ((0,) if protocol == "random_nonoverlap" else range(1, 6))
        for seed in range(1, 6)
    ]


def validate_public(public):
    keys = {"schema", "task_id", "source_protocol_sha256", "scope_contract_sha256",
            "contexts", "panel_id", "generation_commitment"}
    if (not isinstance(public, dict) or set(public) != keys
            or public["schema"] != "barista_selected_primary_panel_v1"
            or public["task_id"] != TASK_ID
            or public["source_protocol_sha256"] != SOURCE_PROTOCOL_SHA
            or public["scope_contract_sha256"] != SCOPE_SHA256
            or not hexhash(public["generation_commitment"])):
        raise ValueError("Exact selected-primary scope and source binding required")
    if public["panel_id"] != digest({k: v for k, v in public.items() if k != "panel_id"}):
        raise ValueError("Public generation fingerprint")
    rows, expected = public["contexts"], contexts()
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError("All 420 selected language contexts required")
    for row, exp in zip(rows, expected):
        if (not isinstance(row, dict) or set(row) != set(exp) | {"query_count", "query_ids_sha256"}
                or any(type(row[k]) is not type(v) or row[k] != v for k, v in exp.items())
                or type(row["query_count"]) is not int or not 1 <= row["query_count"] <= 200000
                or not hexhash(row["query_ids_sha256"])):
            raise ValueError("Complete ordered source context identity/support")
    return public


def outputs(public):
    for arm in ARMS:
        for context in public["contexts"]:
            for model in (*SOURCE_MODELS, "improved"):
                yield dict(context, arm=arm, model=model)


def admit(public, submission_body, base):
    """Admit all 5,880 artifacts before consulting the trusted gold supplier."""
    sub = parse(submission_body)
    if (not isinstance(sub, dict) or set(sub) != {"schema", "task_id", "panel_id", "predictions"}
            or sub["schema"] != "barista_selected_primary_submission_v1"
            or sub["task_id"] != TASK_ID or sub["panel_id"] != public["panel_id"]):
        raise ValueError("Exact selected-primary submission binding required")
    expected, rows = list(outputs(public)), sub["predictions"]
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError("All 5,880 selected source-control and candidate artifacts required")
    total = 0
    for row, exp in zip(rows, expected):
        keys = ("id", "arm", "model", "query_ids_sha256")
        if (not isinstance(row, dict) or set(row) != set(keys) | {"values"}
                or any(row[k] != exp[k] for k in keys)):
            raise ValueError("Exact ordered source-control/candidate/query identity required")
        desc = row["values"]
        if (not isinstance(desc, dict) or type(desc.get("bytes")) is not int
                or not 0 < desc["bytes"] <= ARRAY_CAP):
            raise ValueError("Per-array byte bound")
        total += desc["bytes"]
        if total > TOTAL_CAP:
            raise ValueError("Total candidate array byte bound")
        p = read_array(base, desc, shape=(exp["query_count"],), cap=ARRAY_CAP)
        if p.dtype.kind != "f" or (p < 0).any() or (p > 1).any():
            raise ValueError("Finite class-one probabilities required")
    return rows, expected


def validate_gold(gold, public, public_body):
    if (not isinstance(gold, dict) or set(gold) != {
            "schema", "panel_id", "public_sha256", "baseline_model", "contexts"}
            or gold["schema"] != "barista_selected_primary_gold_v1"
            or gold["panel_id"] != public["panel_id"]
            or gold["public_sha256"] != hashlib.sha256(public_body).hexdigest()
            or gold["baseline_model"] != BASELINE_MODEL):
        raise ValueError("Exact selected-primary trusted baseline binding required")
    rows = gold["contexts"]
    if not isinstance(rows, list) or len(rows) != len(public["contexts"]):
        raise ValueError("Complete 420-context independent reference required")
    for row, exp in zip(rows, public["contexts"]):
        if (not isinstance(row, dict) or set(row) != {
                "id", "query_ids_sha256", "labels", "trusted_parcels_channels", "provenance"}
                or any(row[k] != exp[k] for k in ("id", "query_ids_sha256"))):
            raise ValueError("Exact trusted reference/query identity required")
        provenance = row["provenance"]
        if (not isinstance(provenance, dict) or set(provenance) != PROVENANCE_KEYS
                or any(not hexhash(provenance[k]) for k in PROVENANCE_KEYS)):
            raise ValueError("Per-context independent reference provenance required")
    return rows


def endpoint_summaries(rows):
    # Validate the whole roster first: an extra unrelated endpoint cannot be
    # silently discarded by the per-endpoint filtering below.
    expected = contexts()
    if (len(rows) != len(expected)
            or any(any(row.get(k) != v for k, v in exp.items()) for row, exp in zip(rows, expected))):
        raise ValueError("Complete ordered selected endpoint roster required")
    result = []
    for protocol, tasks in TASKS.items():
        for task in tasks:
            selected = [r for r in rows if r["protocol"] == protocol and r["task"] == task]
            people = []
            for person in PEOPLE:
                repeated = [r for r in selected if r["person"] == person]
                people.append({"person": person, "repeat_count": len(repeated), **{
                    key: exact_summary([r[key] for r in repeated])["mean"]
                    for key in ("candidate_auc", "baseline_auc", "paired_gain")}})
            result.append({"protocol": protocol, "task": task, "source_cell_count": len(selected),
                           "person_count": len(PEOPLE), "paired_people": people, **{
                key: {"source_cell_summary": exact_summary([r[key] for r in selected]),
                      "equal_person_summary": exact_summary([r[key] for r in people])}
                for key in ("candidate_auc", "baseline_auc", "paired_gain")}})
    return result


def _grade_bytes(public_body, submission_body, submission_base, gold_supplier):
    """Trusted operator internal API; CLI fixes gold_supplier to a file reader.

    The callback is not a participant extension point. It keeps private manifest
    loading after complete candidate admission and permits small software tests
    to exercise the full grid without saving megabytes of invented JSON.
    """
    if type(public_body) is not bytes or not 0 < len(public_body) <= JSON_CAP:
        raise ValueError("Public JSON byte bound")
    public = validate_public(parse(public_body))
    try:
        if type(submission_body) is not bytes or not 0 < len(submission_body) <= JSON_CAP:
            raise ValueError("Submission JSON byte bound")
        submitted, expected = admit(public, submission_body, submission_base)
    except (ValueError, TypeError, KeyError, OSError, OverflowError) as exc:
        return {"task_id": TASK_ID, "status": "invalid_submission", "reason": str(exc),
                "private_numeric_inputs_opened": False, "paper_win_established": False}
    gold, gold_base = gold_supplier()
    by_id = {r["id"]: r for r in validate_gold(gold, public, public_body)}
    source_cells = {arm: [] for arm in ARMS}
    candidate_cells = {arm: [] for arm in ARMS}
    undefined = False
    for row, exp in zip(submitted, expected):
        bound = by_id[exp["id"]]
        labels = read_array(gold_base, bound["labels"], shape=(exp["query_count"],), cap=ARRAY_CAP)
        predicted = read_array(submission_base, row["values"], shape=(exp["query_count"],), cap=ARRAY_CAP)
        scored = auc(labels, predicted)
        record = {k: exp[k] for k in ("id", "protocol", "person", "task", "fold", "seed", "model")}
        record.update(scored)
        undefined |= scored["roc_auc"] is None
        if exp["model"] != "improved":
            source_cells[exp["arm"]].append(record)
            continue
        reference = read_array(gold_base, bound["trusted_parcels_channels"],
                               shape=(exp["query_count"],), cap=ARRAY_CAP)
        trusted = auc(labels, reference)
        gain = (None if scored["roc_auc"] is None or trusted["roc_auc"] is None
                else scored["roc_auc"] - trusted["roc_auc"])
        candidate_cells[exp["arm"]].append({**record, "query_ids_sha256": exp["query_ids_sha256"],
            "candidate_auc": scored["roc_auc"], "baseline_auc": trusted["roc_auc"], "paired_gain": gain})
    companions = {arm: aggregate(source_cells[arm], [e for e in expected
                   if e["arm"] == arm and e["model"] != "improved"]) for arm in ARMS}
    return {
        "schema": "barista_selected_primary_score_v1", "task_id": TASK_ID,
        "status": "undefined_required_support" if undefined else "defined",
        "panel_id": public["panel_id"], "scope_contract_sha256": SCOPE_SHA256,
        "baseline_model": BASELINE_MODEL, "source_companions": companions,
        "classification_endpoints": {arm: endpoint_summaries(candidate_cells[arm]) for arm in ARMS},
        "source_cells": source_cells, "candidate_cells": candidate_cells,
        "cross_task_primary": None, "paper_win_established": False,
        "reference_execution_authenticated": False, "reference_competence_qualified": False,
        "historical_sem_parity_established": False, "scientific_significance_established": False,
        "readiness_promoted": False,
        "scope": "Selected channel-mask language contrast only; broader paper branches remain separate.",
    }


def grade(public_path, gold_path, submission_path):
    public_path, gold_path, submission_path = map(Path, (public_path, gold_path, submission_path))
    public_body = capture(public_path, cap=JSON_CAP)
    try:
        submission_body = capture(submission_path, cap=JSON_CAP)
    except (ValueError, OSError) as exc:
        return {"task_id": TASK_ID, "status": "invalid_submission", "reason": str(exc),
                "private_numeric_inputs_opened": False, "paper_win_established": False}
    return _grade_bytes(public_body, submission_body, submission_path.parent,
                        lambda: (parse(capture(gold_path, cap=JSON_CAP)), gold_path.parent))


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("public", "gold", "submission", "out"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    put(args.out, grade(args.public, args.gold, args.submission))


if __name__ == "__main__":
    main()
