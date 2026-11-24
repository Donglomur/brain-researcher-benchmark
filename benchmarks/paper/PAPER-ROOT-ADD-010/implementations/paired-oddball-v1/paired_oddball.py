"""Compare frozen oddball predictions on identical complete declared support.

Descriptive operator utility only: no source authentication, model fitting,
uncertainty, scientific admission, or participant input delivery.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

_SCORER_PATH = Path(__file__).resolve().parents[1] / "oddball-auroc-v1" / "oddball_auroc.py"
_SPEC = importlib.util.spec_from_file_location("root010_oddball_scorer", _SCORER_PATH)
scorer = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(scorer)


def declared_support(packet):
    """Validate and canonicalize all retained metadata, including early epochs.

    Order is not identity: the scorer joins opaque trial IDs before evaluation.
    This commitment proves equality of supplied declarations, not their truth.
    """
    if not isinstance(packet, dict) or set(packet) != {
            "source_revision", "score_orientation", "times", "subjects"}:
        raise ValueError("unexpected cohort packet fields")
    if packet["source_revision"] != scorer.SOURCE_REVISION:
        raise ValueError("source revision mismatch")
    if packet["score_orientation"] != "higher_is_reference":
        raise ValueError("require higher_is_reference scores")
    times = np.asarray(packet["times"])
    if (times.shape != scorer.TIMES.shape or times.dtype.kind not in "fiu"
            or not np.allclose(times, scorer.TIMES, atol=1e-12, rtol=0)):
        raise ValueError("require the pinned code's complete 301-point time axis")
    subjects = packet["subjects"]
    if not isinstance(subjects, list) or len(subjects) != len(scorer.SUBJECTS):
        raise ValueError("require all twenty original participants")
    by_subject = {}
    for entry in subjects:
        if not isinstance(entry, dict) or set(entry) != {"subject", "trials", "branches"}:
            raise ValueError("unexpected subject fields")
        subject = entry["subject"]
        if not isinstance(subject, str) or subject not in scorer.SUBJECTS or subject in by_subject:
            raise ValueError("duplicate or unknown subject")
        if not isinstance(entry["branches"], dict) or set(entry["branches"]) != set(scorer.BRANCHES):
            raise ValueError("require both smoothing branches")
        scorer.fold_plan(subject, entry["trials"])
        by_subject[subject] = sorted(entry["trials"], key=lambda row: row["trial_id"])
    # Retain actual accepted time values: two close, but unequal, declarations
    # must not be silently treated as the exact same paired observations.
    support = {"source_revision": scorer.SOURCE_REVISION,
               "score_orientation": packet["score_orientation"],
               "times": times.astype(float).tolist(),
               "subjects": [{"subject": s, "trials": by_subject[s]}
                            for s in scorer.SUBJECTS]}
    return json.dumps(support, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()


def compare_cohorts(reference_packet, candidate_packet):
    """Score both complete packets only after exact declared-support agreement.

    Higher differences favor candidate AUROC. No time/shape/branch selection or
    global scalar is introduced; overlapping folds remain within participant.
    """
    reference_support = declared_support(reference_packet)
    candidate_support = declared_support(candidate_packet)
    if reference_support != candidate_support:
        raise ValueError("reference and candidate retained-epoch support differs")
    reference = scorer.score_cohort(reference_packet)
    candidate = scorer.score_cohort(candidate_packet)
    differences = {}
    for branch in scorer.BRANCHES:
        ref = reference["branches"][branch]
        cand = candidate["branches"][branch]
        full = (np.asarray(cand["subject_fold_shape_time_auroc"])
                - np.asarray(ref["subject_fold_shape_time_auroc"]))
        participant = full.mean(axis=1)
        differences[branch] = {
            "subject_fold_shape_time_auroc_difference": full.tolist(),
            "subject_shape_time_auroc_difference": participant.tolist(),
            "mean_shape_time_auroc_difference": participant.mean(axis=0).tolist(),
        }
    return {
        "schema": "root010-paired-oddball-comparison/v1",
        "scope": "complete_declared_support_descriptive_comparison_only",
        "research_qualified": False,
        "scientific_outcome": "unknown",
        "superiority_decision": "not_implemented_source_policy_unresolved",
        "difference_orientation": "candidate_minus_reference",
        "declared_support_sha256": hashlib.sha256(reference_support).hexdigest(),
        "reference": reference,
        "candidate": candidate,
        "paired_differences": differences,
        "limits": [
            "Matching supplied metadata does not authenticate original epochs, neural features, or source lineage.",
            "The reference is caller-supplied, not an authenticated strongest-author baseline.",
            "Source final-paper grid, normalization and smoothed-producer correspondence remain unresolved.",
            "No participant isolation, training access, execution budget or paper/code condition is verified.",
            "No selected window, uncertainty procedure, meaningful-effect threshold or scientific win is supplied.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference_packet", type=Path)
    parser.add_argument("candidate_packet", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    reference_raw = args.reference_packet.read_bytes()
    candidate_raw = args.candidate_packet.read_bytes()
    result = compare_cohorts(json.loads(reference_raw), json.loads(candidate_raw))
    result["input_sha256"] = {
        "reference": hashlib.sha256(reference_raw).hexdigest(),
        "candidate": hashlib.sha256(candidate_raw).hexdigest(),
    }
    with args.output.open("x") as handle:
        json.dump(result, handle, allow_nan=False, separators=(",", ":"))
        handle.write("\n")


if __name__ == "__main__":
    main()
