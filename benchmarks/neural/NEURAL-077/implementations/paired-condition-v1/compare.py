"""Operator-side same-trial comparison for two complete NEURAL-077 conditions.

No producer/model execution, target files, or empirical results are bundled.
The trusted caller supplies the existing hash-and-ID-checking private loader.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import stat
import tempfile
import types

CASES = ("development-001", "development-002")
ROSTER_SHA256 = "82405f12a9e8f302a27a5641241378a4f2000bef2849fece555b8843ca92d2d4"
CANONICAL_PINS = {
    "validator.py": {"bytes": 9277, "sha256": "5483d1b04e6f81d048351ca202c13a7c4183988469b88ca0274874b4714346a2"},
    "metrics.py": {"bytes": 8557, "sha256": "e053d4dbf7237b0e630a8b9f097ce4fb5bb3cd3f547e892b4aa425a736f6a99f"},
}
# These describe the current contract; a name cannot prove a producer's access.
# The tool-assisted condition is an eventual comparison endpoint, not a claim
# that its missing controller is delivered by this component.
CONDITIONS = {
    "legacy_waveform_no_tools": ("direct_observation", "numerical_waveform", 4),
    "zero_shot": ("typed_viewer", "visual_waveform", 0),
    "four_demo": ("typed_viewer", "visual_waveform", 4),
    "tool_assisted_waveform": ("tool_assisted", "numerical_waveform", 4),
    "matched_waveform_programme": ("frozen_program", "numerical_waveform", 4),
    "ordinary_feature_programme": ("frozen_program", "feature_bank", 1200),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def _valid_pin(expected, cap):
    require(type(expected) is dict and set(expected) == {"bytes", "sha256"}
            and type(expected["bytes"]) is int and 0 < expected["bytes"] <= cap
            and type(expected["sha256"]) is str and len(expected["sha256"]) == 64
            and all(c in "0123456789abcdef" for c in expected["sha256"]),
            "Exact bounded byte/SHA256 pin required")


def captured(path, expected, cap):
    """Read once and return exactly the pinned bytes, never follow final links."""
    _valid_pin(expected, cap)
    path = Path(path).absolute()
    require(all(not p.is_symlink() for p in (path, *path.parents)), "Linked input path")
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
            and before.st_size == expected["bytes"], "Exact bounded ordinary input required")
    fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        require(fields(before) == fields(os.fstat(stream.fileno())), "Input changed before capture")
        body = stream.read(cap + 1)
        require(fields(before) == fields(os.fstat(stream.fileno())) == fields(path.lstat()),
                "Input changed during capture")
    require(pin(body) == expected, "Input pin mismatch")
    return body


def canonical(directory):
    # Verify BOTH complete bodies before executing either, then execute those
    # captured bytes rather than importing a second pathname read.
    bodies = {name: captured(Path(directory) / name, expected, 65536)
              for name, expected in CANONICAL_PINS.items()}
    modules = {}
    for name, body in bodies.items():
        module = types.ModuleType("neural077_paired_" + Path(name).stem)
        module.__file__ = str(Path(directory) / name)
        exec(compile(body, module.__file__, "exec"), module.__dict__)
        modules[name] = module
    return modules["validator.py"], modules["metrics.py"]


def roster(expected_ids):
    require(type(expected_ids) is dict and set(expected_ids) == set(CASES), "Fixed two-person roster required")
    rows = {}
    for case in CASES:
        ids = list(expected_ids[case])
        require(len(ids) == 200 and all(type(x) is str and x.startswith(case + "-") for x in ids)
                and len(set(ids)) == 200 and ids == sorted(ids), "Exact sorted 200-ID person roster required")
        rows[case] = ids
    complete = [identifier for case in CASES for identifier in rows[case]]
    body = (json.dumps(complete, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode()
    require(hashlib.sha256(body).hexdigest() == ROSTER_SHA256, "Unrecognized public roster")
    return rows


def condition_record(name, receipt_pin):
    require(type(name) is str and name in CONDITIONS, "Unknown or mixed condition")
    _valid_pin(receipt_pin, 1048576)
    mode, representation, labels = CONDITIONS[name]
    return {"condition": name, "access_mode": mode, "representation": representation,
            "training_label_budget": labels, "producer_receipt_pin": dict(receipt_pin),
            "producer_provenance": "operator_authenticated_not_inferred_from_predictions"}


def paired_person(a, b, labels, person_id, epsilon):
    """Aggregate class-specific paired correctness and metric-only loss changes.

    Inputs already passed canonical validation; no per-trial targets or outputs
    are emitted. Equal class weighting preserves BA under the 40:160 imbalance.
    """
    by_class = []
    for label, name in ((1, "target"), (0, "non_target")):
        table = {"both_correct": 0, "a_only_correct": 0, "b_only_correct": 0, "neither_correct": 0}
        for pa, pb, y in zip(a, b, labels, strict=True):
            if y != label:
                continue
            ca, cb = (pa >= 0.5) == bool(y), (pb >= 0.5) == bool(y)
            key = ("both_correct" if ca and cb else "a_only_correct" if ca
                   else "b_only_correct" if cb else "neither_correct")
            table[key] += 1
        n = sum(table.values())
        require(n > 0, "Both classes required in every person")
        by_class.append({"class": name, "n": n, **table,
                         "a_minus_b_recall": (table["a_only_correct"] - table["b_only_correct"]) / n})
    loss_delta = []
    for pa, pb, y in zip(a, b, labels, strict=True):
        qa, qb = (min(max(float(v), epsilon), 1.0 - epsilon) for v in (pa, pb))
        la = -math.log(qa) if y else -math.log1p(-qa)
        lb = -math.log(qb) if y else -math.log1p(-qb)
        loss_delta.append(la - lb)
    return {"person_id": person_id, "n": len(labels), "class_specific_pairing": by_class,
            "balanced_accuracy": math.fsum(row["a_minus_b_recall"] for row in by_class) / 2,
            "log_loss": math.fsum(loss_delta) / len(labels)}


def compare_submissions(a_path, b_path, expected_ids, private_loader, reference_scores,
                        canonical_directory, *, a_pin, b_pin, a_condition, b_condition,
                        a_receipt_pin, b_receipt_pin):
    """Compare A minus B after complete public admission of both frozen NPZs.

    Call only inside the separately admitted private evaluator after both
    producers have stopped. The operator authenticates each producer receipt,
    including complete homogeneous delivery and the declared information access.
    This callable has no knowledge of provider sessions or sandbox enforcement.
    """
    ids = roster(expected_ids)
    a_metadata = condition_record(a_condition, a_receipt_pin)
    b_metadata = condition_record(b_condition, b_receipt_pin)
    require(callable(private_loader), "Trusted private loader required")
    a_body, b_body = captured(a_path, a_pin, 1048576), captured(b_path, b_pin, 1048576)
    validator, metrics = canonical(canonical_directory)
    # The canonical validator consumes private temporary snapshots of the exact
    # committed bytes. Replacing the original pathname cannot change the score.
    with tempfile.TemporaryDirectory(prefix="neural077-paired-") as tmp:
        root = Path(tmp).resolve()
        paths = [root / "a.npz", root / "b.npz"]
        for path, body in zip(paths, (a_body, b_body), strict=True):
            path.write_bytes(body)
            path.chmod(0o400)
        a = validator.validate(paths[0], ids)
        b = validator.validate(paths[1], ids)
    # No private access has occurred. Canonical scoring validates references
    # before requesting labels; original label dtype reaches canonical checks.
    cache = {}
    private_loads = 0
    def cached_loader(case):
        nonlocal private_loads
        require(case in CASES, "Unexpected private case")
        if case not in cache:
            private_loads += 1
            value = private_loader(case)
            # No coercion before canonical validation, especially float labels.
            import copy
            cache[case] = copy.deepcopy(value)
        return cache[case]
    a_score = metrics.score_candidate(a, cached_loader, reference_scores)
    require(all((row["n"], row["n_target"], row["n_non_target"]) == (200, 40, 160)
                for row in a_score["candidate"]["per_person"]), "Original complete class support required")
    b_score = metrics.score_candidate(b, cached_loader, reference_scores)
    require(private_loads == 2 and set(cache) == set(CASES), "Exactly two original private loads required")
    paired = [paired_person(a[case], b[case], cache[case], case, metrics.EPSILON) for case in CASES]
    macro_ba = math.fsum(row["balanced_accuracy"] for row in paired) / 2
    macro_loss = math.fsum(row["log_loss"] for row in paired) / 2
    for key, difference in (("participant_macro_balanced_accuracy", macro_ba),
                            ("participant_macro_log_loss", macro_loss)):
        require(math.isclose(difference, a_score["candidate"][key] - b_score["candidate"][key],
                             rel_tol=0, abs_tol=1e-12), "Paired/canonical arithmetic mismatch")
    return {"schema": "neural077_paired_condition_v1", "status": "paired_scored",
            "roster_sha256": ROSTER_SHA256, "trial_count": 400, "people": 2,
            "a": {**a_metadata, "submission_pin": dict(a_pin), "canonical_score": a_score},
            "b": {**b_metadata, "submission_pin": dict(b_pin), "canonical_score": b_score},
            "a_minus_b": {"per_person": paired, "participant_macro_balanced_accuracy": macro_ba,
                          "participant_macro_log_loss": macro_loss},
            "same_training_label_budget": a_metadata["training_label_budget"] == b_metadata["training_label_budget"],
            "same_representation": a_metadata["representation"] == b_metadata["representation"],
            "equal_information_proven": False, "condition_budgets_pooled": False,
            "primary_metric": "participant_macro_balanced_accuracy", "decision_threshold": 0.5,
            "positive_log_loss_difference_is_worse": True, "prediction_values_modified": False,
            "private_loader_invocations": private_loads, "canonical_cache_requests": 4,
            "population_confidence_interval": False, "hypothesis_test": False,
            "cohort": "two_previously_exposed_development_people", "scientific_pass_threshold": None}
