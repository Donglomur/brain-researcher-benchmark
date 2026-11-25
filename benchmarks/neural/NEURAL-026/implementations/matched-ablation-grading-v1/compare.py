"""Operator-only descriptive grading of three complete matched NEURAL-026 arms.

All submission commitments are captured before the first protected target read.
The unchanged measured-target arithmetic grades each arm against the same design
and trusted loader. Candidate execution, input views and budgets remain external
requirements; this component cannot establish neural dependence or causality.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
from pathlib import Path
import re

import numpy as np

HERE = Path(__file__).resolve().parent
SCORE_SHA256 = "45d39f3c6d66b7838c3aa725596eeb293517ed51cacf4b9738f79de27af3a5ea"
MODES = ("full", "context_only", "training_trial_shift")


def need(value, message):
    if not value:
        raise ValueError(message)


def load_scorer():
    path = HERE.parent / "understanding-metrics-v1/score.py"
    need(path.is_file() and not path.is_symlink(), "Ordinary measured-target scorer source")
    body = path.read_bytes()
    need(hashlib.sha256(body).hexdigest() == SCORE_SHA256,
         "Pinned measured-target scorer with paired admission support")
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(
        "neural026_paired_score", loader=None))
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def _contrast(full, control, mice, areas):
    need([(r["mouse"], r["area"]) for r in full["biological_effects"]]
         == [(m, a) for m in mice for a in areas]
         == [(r["mouse"], r["area"]) for r in control["biological_effects"]],
         "Complete matched biological row order")
    cells = []
    with np.errstate(over="raise", under="raise", invalid="raise", divide="raise"):
        for first, second in zip(full["biological_effects"], control["biological_effects"], strict=True):
            sst = np.asarray(first["pooled_target_joint_sst"], dtype=np.float64)
            need(first["query_samples"] == second["query_samples"]
                 and np.array_equal(sst, second["pooled_target_joint_sst"])
                 and sst.shape == (24,) and np.isfinite(sst).all() and (sst > 0).all(),
                 "Same positive pooled target variance and sample counts in every arm")
            # The common nuisance SSE cancels algebraically. Subtracting two
            # large nuisance-based gains would lose a smaller real difference.
            delta = ((np.asarray(second["candidate_joint_sse"], dtype=np.float64)
                      - np.asarray(first["candidate_joint_sse"], dtype=np.float64)) / sst)
            need(delta.shape == (24,) and np.isfinite(delta).all(), "All 24 finite signed joint differences")
            cells.append({"mouse": first["mouse"], "area": first["area"],
                          "full_minus_control_joint_incremental_ev": delta.tolist()})
        per_mouse = [{"mouse": mouse, "full_minus_control_incremental_ev": float(np.mean([
            row["full_minus_control_joint_incremental_ev"] for row in cells if row["mouse"] == mouse]))}
            for mouse in mice]
        value = float(np.mean([row["full_minus_control_incremental_ev"] for row in per_mouse]))
        need(np.isfinite(value), "Finite equal-mouse paired difference")
    return {"direction": "higher", "value": value, "biological_effects": cells,
            "per_mouse": per_mouse, "independent_mice": 5,
            "inference": "descriptive signed difference; no threshold, interval or significance"}


def evaluate(submissions, design, trusted_private_loader):
    """Use one operator design/loader for full, context-only and shifted panels.

    The trusted loader has the same obligations as the measured-target scorer:
    return independently frozen targets and reference arrays for every call.
    Use the CLI to enforce one external design and private binding by hash.
    """
    need(type(submissions) is dict and set(submissions) == set(MODES),
         "Exactly the three explicit matched input conditions")
    scorer = load_scorer()
    api = scorer.backend()
    admitted = {mode: scorer.admit_submission(submissions[mode], design, api) for mode in MODES}
    grades = {mode: scorer.evaluate(submissions[mode], design, trusted_private_loader,
                                   expected_admission=admitted[mode]) for mode in MODES}
    contrasts = {mode: _contrast(grades["full"], grades[mode], api.p.MICE, api.p.AREAS)
                 for mode in MODES[1:]}
    return {"schema": "neural026_matched_ablation_grade_v1", "modes": list(MODES),
            "complete_cases_per_mode": 50, "independent_mice": 5,
            "primary_per_mode": "equal_mouse_area_joint_fixed_nuisance_incremental_EV",
            "grades": grades, "full_minus_control": contrasts,
            "submission_commitments": {
                mode: {"schema": admitted[mode][0], "prediction_keys": sorted(admitted[mode][1]),
                       "cases": admitted[mode][2]} for mode in MODES},
            "same_operator_design_and_loader": True,
            "all_mode_admission_before_protected_read": True,
            "matched_candidate_execution_verified": False, "matched_input_views_verified": False,
            "matched_budgets_verified": False, "neural_dependence_established": False,
            "scientific_qualification": False, "binary_pass": None,
            "limits": [
                "Same candidate, initialization, fitting and selection budget, and actual input controls require external verification.",
                "Training-only shifts are one diagnostic and may alter distributions; contrasts do not establish causality.",
                "Five mice are biological units; folds, joints and input conditions do not increase that number.",
                "A changed candidate after initial admission is refused, not retried or replaced.",
            ]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("full", "context-only", "training-trial-shift", "design", "private-root", "binding", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--design-sha256", required=True)
    parser.add_argument("--binding-sha256", required=True)
    args = parser.parse_args(argv)
    scorer = load_scorer()
    api = scorer.backend()
    api.io.fresh_output(args.output)
    design = scorer.metadata_pin(args.design, args.design_sha256, api)
    binding = scorer.metadata_pin(args.binding, args.binding_sha256, api)
    need(type(binding) is dict and binding.get("schema") == "neural026_private_binding_v1"
         and type(binding.get("cases")) is dict and set(binding["cases"]) == set(api.p.case_ids()),
         "One complete independently pinned target/reference binding")

    def loader(cid):
        values = []
        for role, expected in (("target", {"trial_id", "y"}), ("reference", {"trial_id", *api.p.ARMS})):
            row = binding["cases"][cid][role]
            need(type(row) is dict and {"file", "bytes", "sha256"} <= set(row)
                 and type(row["bytes"]) is int and 0 < row["bytes"] <= scorer.FILE_CAP
                 and type(row["sha256"]) is str and re.fullmatch("[0-9a-f]{64}", row["sha256"]),
                 "Typed independently committed target/reference identity")
            raw = api.io.capture(scorer.flat_path(args.private_root, row["file"]), scorer.FILE_CAP)
            need(api.io.identity(raw) == {k: row[k] for k in ("bytes", "sha256")},
                 "Same pinned private bytes across all input conditions")
            values.append(api.io.arrays(raw, expected, scorer.FILE_CAP))
        return values

    grade = evaluate({mode: getattr(args, mode) for mode in MODES}, design, loader)
    grade["operator_design_sha256"] = args.design_sha256
    grade["operator_binding_sha256"] = args.binding_sha256
    api.common.save_json(args.output, grade)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
