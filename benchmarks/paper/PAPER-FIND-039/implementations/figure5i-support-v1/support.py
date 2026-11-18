"""Audit complete Figure 5i split support against an operator-held reference.

This validates custody and structure only. An operator must independently
authenticate historical evidence before supplying its admitted receipt digest.
No seed, fold, biological observation, prediction or acceptance rule is generated.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

TASK_ID = "PAPER-FIND-039"
SOURCE_REVISION = "1a9dd3040c9f77662caf26a34c9452403579087a"
SCORER_SHA256 = "d33bdef4ca06fd30a774f5f9c49f5066abfd83ff291f5d9c9efac7a5b5e058da"
SCORER_BYTES = 10409
EVIDENCE_ROLES = frozenset({"original_downsampling", "original_test_partition",
                            "original_real_training", "original_spike_shuffle_training"})
SESSION_FIELDS = frozenset({"mouse_id", "session_id", "age_group", "optimal_k",
                           "source_onemap", "spatial_cell_ids",
                           "downsampled_observation_ids", "folds"})
FOLD_FIELDS = frozenset({"repeat", "test_observation_ids", "real_train_observation_ids",
                        "spike_shuffle_train_observation_ids"})


def _digest_string(value, name):
    if (type(value) is not str or len(value) != 64
            or any(c not in "0123456789abcdef" for c in value)):
        raise ValueError(f"{name}: lowercase SHA-256 required")
    return value


def _keys(value, expected, name):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError(f"{name}: exact declared fields required")


def _json_value(value):
    """Reject non-JSON container/key types before canonical serialization."""
    if value is None or type(value) in (str, bool, int, float):
        return
    if type(value) is list:
        for item in value:
            _json_value(item)
        return
    if type(value) is dict and all(type(k) is str for k in value):
        for item in value.values():
            _json_value(item)
        return
    raise ValueError("support must contain only JSON-native values and string keys")


def support_digest(support):
    """Canonical content commitment; it is not a signature or authenticity proof."""
    _json_value(support)
    try:
        body = json.dumps(support, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("support is not finite canonical JSON") from exc
    return hashlib.sha256(body).hexdigest()


def _load_scorer(path=None):
    path = (Path(path) if path is not None else
            Path(__file__).resolve().parents[1] / "figure5i-score-v1" / "score.py")
    body = path.read_bytes()
    if len(body) != SCORER_BYTES or hashlib.sha256(body).hexdigest() != SCORER_SHA256:
        raise ValueError("the pinned Figure 5i scorer dependency differs")
    # The file is maintainer source, never a participant-controlled extension.
    spec = importlib.util.spec_from_file_location("figure5i_support_scorer", path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load pinned scorer")
    scorer = importlib.util.module_from_spec(spec)
    exec(compile(body, str(path), "exec"), scorer.__dict__)
    return scorer


def _ids(value, name):
    if (type(value) is not list or not value or
            any(type(x) is not str or not x for x in value)
            or len(set(value)) != len(value)):
        raise ValueError(f"{name}: nonempty unique string IDs required")
    return value


def audit_support(reference, support, admitted_support_sha256, *, scorer_path=None):
    """Check an independently admitted complete historical-support receipt.

    `admitted_support_sha256` must originate outside participant submissions.
    Setting this argument to a participant's own digest is not admission.
    `scorer_path` is for trusted deployment layout selection; its contents must
    match the immutable source pin regardless of the supplied path.
    """
    admitted = _digest_string(admitted_support_sha256, "admitted_support_sha256")
    digest = support_digest(support)
    if digest != admitted:
        raise ValueError("support differs from the externally admitted content commitment")
    scorer = _load_scorer(scorer_path)
    references = scorer.validate_reference(reference)
    if reference["split_receipt_sha256"] != admitted:
        raise ValueError("reference does not bind the admitted split receipt")
    _keys(support, {"schema", "task_id", "source_revision", "realization",
                    "cohort_receipt_sha256", "preprocessing_receipt_sha256",
                    "realization_evidence", "sessions"}, "support")
    if (support["schema"] != "figure5i-original-split-support/v1"
            or support["task_id"] != TASK_ID
            or support["source_revision"] != SOURCE_REVISION
            or support["realization"] != "historical_original"):
        raise ValueError("original Figure 5i support identity is required; regenerated folds are distinct")
    for field in ("cohort_receipt_sha256", "preprocessing_receipt_sha256"):
        if _digest_string(support[field], field) != reference[field]:
            raise ValueError(f"{field} differs from the reference")
    evidence = support["realization_evidence"]
    _keys(evidence, EVIDENCE_ROLES, "realization_evidence")
    for role, value in evidence.items():
        _digest_string(value, role)
    if type(support["sessions"]) is not list or len(support["sessions"]) != 61:
        raise ValueError("complete 61-session original panel required")
    sessions = {}
    for session in support["sessions"]:
        _keys(session, SESSION_FIELDS, "support session")
        key = (session["mouse_id"], session["session_id"])
        if (any(type(x) is not str or not x for x in key)
                or key in sessions or key not in references):
            raise ValueError("unknown, duplicate or malformed support session")
        sessions[key] = session
    if sessions.keys() != references.keys():
        raise ValueError("support session identities differ from the reference")
    shuffled_training_rows = 0
    test_rows = 0
    different_training_folds = 0
    for key, expected in references.items():
        session = sessions[key]
        for field in SESSION_FIELDS - {"folds"}:
            # Type identity also prevents True being treated as integer 1.
            if type(session[field]) is not type(expected[field]) or session[field] != expected[field]:
                raise ValueError(f"support {field} differs from the original reference")
        if type(session["folds"]) is not list or len(session["folds"]) != 10:
            raise ValueError("ten complete original folds required per session")
        folds = {}
        for fold in session["folds"]:
            _keys(fold, FOLD_FIELDS, "support fold")
            repeat = fold["repeat"]
            if type(repeat) is not int or repeat not in range(10) or repeat in folds:
                raise ValueError("support fold IDs must be exactly integers 0..9")
            folds[repeat] = fold
        expected_folds = {fold["repeat"]: fold for fold in expected["folds"]}
        observations = set(expected["downsampled_observation_ids"])
        for repeat, original in expected_folds.items():
            fold = folds[repeat]
            test = _ids(fold["test_observation_ids"], "test_observation_ids")
            real = _ids(fold["real_train_observation_ids"], "real_train_observation_ids")
            shuffled = _ids(fold["spike_shuffle_train_observation_ids"],
                            "spike_shuffle_train_observation_ids")
            if test != original["test_observation_ids"]:
                raise ValueError("original test identities/order changed")
            if real != original["train_observation_ids"]:
                raise ValueError("original real-arm training identities/order changed")
            if len(shuffled) != int(len(observations) * 0.9):
                raise ValueError("spike-shuffle training count differs from the source rule")
            if not set(shuffled) <= observations - set(test):
                raise ValueError("spike-shuffle training includes held-out or unknown observations")
            # Separate random draws may coincide; forcing a difference would
            # alter the original protocol. Record, do not gate, this diagnostic.
            different_training_folds += int(shuffled != real)
            shuffled_training_rows += len(shuffled)
            test_rows += len(test)
    return {
        "schema": "figure5i-split-support-audit/v1", "task_id": TASK_ID,
        "support_sha256": digest, "reference_sha256": scorer.reference_digest(reference),
        "sessions": 61, "folds": 610, "young_sessions": 34, "aged_sessions": 27,
        "test_rows": test_rows, "spike_shuffle_training_rows": shuffled_training_rows,
        "folds_with_different_training_order_or_membership": different_training_folds,
        "structural_support_consistency": True,
        "historical_authenticity": "not_established_by_this_component",
        "paper_reproduction": "not_assessed", "paper_improvement": "not_assessed",
        "scientific_admission": False,
    }
