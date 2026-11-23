"""Compare two POYO submitted grids after admitting both before target access.

This is a prospective source component, not a qualified original-paper result or
evidence of independent authorship, enforced access conditions, or matched compute.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from types import ModuleType


SCORER_SHA256 = "b9911fec0d79183bd8cfccad23254674e6c15d256136a830f2d8883ee4891b64"
CONDITIONS = ("paper_data", "paper_data_author_code")


def _load_scorer():
    path = Path(__file__).resolve().parent.parent / "protected-grid-evaluator" / "evaluator.py"
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != SCORER_SHA256:
        raise ValueError("protected scorer source differs")
    module = ModuleType("poyo_protected_scorer")
    module.__file__ = str(path)
    # Execute the bytes that were authenticated, without a second source read.
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


scorer = _load_scorer()


def _pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def _difference(left, right):
    """Difference of the represented binary64 report values, without clipping."""
    return scorer.as_float(Fraction(right) - Fraction(left))


def evaluate_pair(design_body, design_pin, paper_data_body,
                  paper_data_author_code_body, target_loader):
    """Admit both full public grids, then obtain one shared private target snapshot.

    The callable trusts the owner-supplied target loader. Its returned bytes are
    reused verbatim by both unchanged scoring calls. The CLI additionally checks
    the target snapshot against an owner-supplied digest and extent.
    """
    scorer.authenticate(design_body, design_pin, "selected paired design")
    design = scorer.load_json(design_body)
    _, cases = scorer.admit_design(design)
    bodies = dict(zip(CONDITIONS, (paper_data_body, paper_data_author_code_body)))
    # No private callback is reachable until *both* complete public operands pass.
    for body in bodies.values():
        scorer.admit_predictions(scorer.load_json(body), cases)
    target_body = target_loader()
    scorer.require(type(target_body) is bytes, "shared target snapshot must be bytes")
    reports = {
        condition: scorer.evaluate(design_body, design_pin, body, lambda: target_body)
        for condition, body in bodies.items()
    }
    first, second = (reports[condition] for condition in CONDITIONS)
    session_differences = []
    for left, right in zip(first["results"], second["results"]):
        keys = ("budget_id", "session_id", "method")
        scorer.require(all(left[key] == right[key] for key in keys), "paired session alignment")
        session_differences.append({
            **{key: left[key] for key in keys},
            "r2_difference": _difference(left["r2"], right["r2"]),
            "dimension_r2_differences": [
                _difference(a, b) for a, b in zip(left["dimension_r2"], right["dimension_r2"])
            ],
        })
    summary_differences = []
    for left, right in zip(first["summaries"], second["summaries"]):
        keys = ("budget_id", "method", "group", "identity", "sessions")
        scorer.require(all(left[key] == right[key] for key in keys), "paired summary alignment")
        summary_differences.append({
            **{key: left[key] for key in keys},
            "session_macro_r2_difference": _difference(left["session_macro_r2"], right["session_macro_r2"]),
        })
    return {
        "schema": "poyo_paired_grid_comparison_v1",
        "task_id": scorer.TASK,
        "policy": scorer.POLICY,
        "support_policy": scorer.PROTECTION,
        "design_identity": _pin(design_body),
        "prediction_identities": {condition: _pin(body) for condition, body in bodies.items()},
        "target_identity": _pin(target_body),
        "scorer_sha256": SCORER_SHA256,
        "conditions": reports,
        "difference_direction": "paper_data_author_code minus paper_data",
        "difference_arithmetic": "Exact subtraction of represented binary64 report values, converted to binary64; not subtraction of unrounded rational scores.",
        "session_differences": session_differences,
        "summary_differences": summary_differences,
        "external_target_loads": 1,
        "scientific_qualification": False,
        "historical_reproduction": False,
        "input_provenance_verified": False,
        "condition_isolation_verified": False,
        "independent_authorship_verified": False,
        "matched_resource_budgets_verified": False,
        "qualification_note": "Condition names label submitted grids. Source identity and numerical comparison do not certify methods, biological membership, author-code exposure, authorship, reference competence, or resources. Reports and target identities remain evaluator-private.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("design", "paper-data", "paper-data-author-code", "targets", "output"):
        parser.add_argument("--" + name, required=True)
    for role in ("design", "targets"):
        parser.add_argument("--" + role + "-bytes", required=True, type=int)
        parser.add_argument("--" + role + "-sha256", required=True)
    args = parser.parse_args()

    def private():
        body = scorer.read_bytes(args.targets)
        scorer.authenticate(body, {"bytes": args.targets_bytes, "sha256": args.targets_sha256},
                            "shared private targets")
        return body

    result = evaluate_pair(
        scorer.read_bytes(args.design), {"bytes": args.design_bytes, "sha256": args.design_sha256},
        scorer.read_bytes(args.paper_data), scorer.read_bytes(args.paper_data_author_code), private,
    )
    body = json.dumps(result, indent=2, allow_nan=False) + "\n"
    with Path(args.output).open("x", encoding="utf8") as handle:
        handle.write(body)


if __name__ == "__main__":
    main()
