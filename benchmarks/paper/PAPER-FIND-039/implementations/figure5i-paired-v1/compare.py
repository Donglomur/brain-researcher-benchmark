"""Join complete Figure 5i predictions across source assistance and outcomes.

Operator arithmetic only. Support admission, independent candidate freezing,
matched exposure/budgets and scientific decisions remain external obligations.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path

TASK = "PAPER-FIND-039"
CONDITIONS = ("paper_data", "paper_data_author_code")
OUTCOMES = ("reproduction", "improvement")
DEPENDENCIES = {
    "figure5i-score-v1/score.py": (
        10409, "d33bdef4ca06fd30a774f5f9c49f5066abfd83ff291f5d9c9efac7a5b5e058da"),
    "figure5i-support-v1/support.py": (
        9255, "688fdd5da0689cfd7c7ec2ef79edda2e7287c39377cfb3caeedda6735ccd8965"),
}


def _load_components(root):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    # Verify both dependencies before executing either trusted component.
    bodies = {}
    for relative, (size, digest) in DEPENDENCIES.items():
        body = (root / relative).read_bytes()
        if len(body) != size or hashlib.sha256(body).hexdigest() != digest:
            raise ValueError(f"pinned component differs: {relative}")
        bodies[relative] = body
    modules = []
    for relative, body in bodies.items():
        path = root / relative
        spec = importlib.util.spec_from_file_location("paired_" + path.stem, path)
        if spec is None or spec.loader is None:
            raise ValueError(f"cannot load component: {relative}")
        module = importlib.util.module_from_spec(spec)
        exec(compile(body, str(path), "exec"), module.__dict__)
        modules.append(module)
    return (*modules, root / "figure5i-score-v1/score.py")


def _keys(value, expected, name):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError(f"{name}: exact declared fields required")


def compare_conditions(reference, support, admitted_support_sha256, candidates,
                       author, shuffle, *, components_root=None):
    """Assess all four candidate packets on one admitted original support.

    candidates[condition][outcome] is a figure5i-predictions/v1 packet, separately
    frozen upstream for that slot. Identical content is allowed: numerical
    difference is not evidence of independent freezing. The operator supplies
    the admitted support commitment outside participant submissions.
    """
    _keys(candidates, CONDITIONS, "candidate conditions")
    for condition in CONDITIONS:
        _keys(candidates[condition], OUTCOMES, f"{condition} outcomes")
    scorer, auditor, scorer_path = _load_components(components_root)
    audit = auditor.audit_support(reference, support, admitted_support_sha256,
                                  scorer_path=scorer_path)
    # The scorer recomputes every fold from predictions. Never join submitted
    # summary reports or infer a missing condition from the other candidate.
    reports = {
        condition: {
            outcome: scorer.score_panel(reference, candidates[condition][outcome], author, shuffle)
            for outcome in OUTCOMES
        }
        for condition in CONDITIONS
    }
    contrasts = {}
    for outcome in OUTCOMES:
        plain = reports[CONDITIONS[0]][outcome]
        assisted = reports[CONDITIONS[1]][outcome]
        plain_rows = {(row["mouse_id"], row["session_id"]): row for row in plain["sessions"]}
        rows = []
        for with_code in assisted["sessions"]:
            key = (with_code["mouse_id"], with_code["session_id"])
            without_code = plain_rows[key]
            left = without_code["arms"]["candidate"]
            right = with_code["arms"]["candidate"]
            rows.append({
                "mouse_id": key[0], "session_id": key[1], "age_group": with_code["age_group"],
                "fold_differences": [b - a for a, b in zip(left["fold_scores"], right["fold_scores"])],
                "session_difference": right["session_score"] - left["session_score"],
            })
        strata = {}
        for age in scorer.AGE_COUNTS:
            group = [row for row in rows if row["age_group"] == age]
            strata[age] = {
                "n_sessions": len(group), "n_mice": len({row["mouse_id"] for row in group}),
                "mean_session_difference": math.fsum(row["session_difference"] for row in group) / len(group),
            }
        contrasts[outcome] = {"sessions": rows, "age_strata": strata}
    return {
        "schema": "figure5i-paired-comparison/v1", "task_id": TASK,
        "reference_sha256": scorer.reference_digest(reference),
        "support_audit": audit,
        "candidate_packet_sha256": {
            condition: {outcome: auditor.support_digest(candidates[condition][outcome])
                        for outcome in OUTCOMES} for condition in CONDITIONS
        },
        "author_packet_sha256": auditor.support_digest(author),
        "shuffle_packet_sha256": auditor.support_digest(shuffle),
        "condition_reports": reports,
        "author_code_minus_paper_data": contrasts,
        "aggregation": "equal ten fold means, then equal session means within each age stratum",
        "interpretation": {
            "contrast": "paper_data_author_code minus paper_data; descriptive real-label score difference",
            "outcomes": "independent slots; reproduction and improvement decisions are not assessed",
            "shuffle": "mandatory shared fidelity control, never an improvement target",
            "uncertainty": "not assessed; retain mouse/session identities for a separately qualified rule",
            "exposure_and_freeze_authenticity": "not established by this component",
            "paper_reproduction": "not_assessed", "paper_improvement": "not_assessed",
            "scientific_admission": False,
        },
    }


def _unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--admitted-support-sha256", required=True,
                        help="independent operator commitment; never taken from the submission")
    parser.add_argument("--components-root", type=Path,
                        help="trusted deployment location; immutable component hashes still checked")
    args = parser.parse_args(argv)
    if args.report.resolve() == args.bundle.resolve():
        parser.error("report cannot overwrite input bundle")
    bundle = json.loads(args.bundle.read_text(), object_pairs_hook=_unique_json)
    _keys(bundle, {"schema", "task_id", "reference", "support", "candidates", "author", "shuffle"}, "bundle")
    if bundle["schema"] != "figure5i-paired-input/v1" or bundle["task_id"] != TASK:
        raise ValueError("paired bundle identity differs")
    report = compare_conditions(
        bundle["reference"], bundle["support"], args.admitted_support_sha256,
        bundle["candidates"], bundle["author"], bundle["shuffle"],
        components_root=args.components_root,
    )
    args.report.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
