"""Pair both assistance conditions on the unchanged original contrast panel.

Trusted operator reporting only; no fitting, access enforcement or paper win.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path

DEPENDENCIES = {
    "contrast-panel-v2/panel.py": (15164, "da36249e5a538d87377be320c31ec2bbfef7b11b97083688d4791b0f81d672b9"),
    "initial-evaluator-v1/evaluator.py": (25780, "2cbfa3be223cdef714619c2db287bb77de0833c40f9c0c7e20044e6cc272e9f9"),
}
for _relative, (_size, _sha) in DEPENDENCIES.items():
    _path = Path(__file__).resolve().parents[1] / _relative
    with _path.open("rb") as _handle:
        _raw = _handle.read(_size + 1)
    if len(_raw) != _size or hashlib.sha256(_raw).hexdigest() != _sha:
        raise ValueError("accepted panel dependency changed: " + _relative)
_spec = importlib.util.spec_from_file_location(
    "decision_times_paired_panel", Path(__file__).resolve().parents[1] / "contrast-panel-v2/panel.py")
panel = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(panel)
require = panel.require
ACCESS = ("paper_data", "paper_data_author_code")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def reference_identity(references):
    """Preserve all reference operands/metadata while ignoring keyed row order.

    Call only after the original scorer has checked uniqueness and coverage.
    Equal scores alone cannot identify the same participant-level reference.
    """
    normalized = json.loads(canonical(references))
    for method in normalized:
        for mode in ("held_out", "full_data"):
            for row in method[mode]:
                row["fit_contrasts_percent"].sort()
            method[mode].sort(key=lambda r: (r["target"], r["condition"], r["participant"], r["contrast_percent"]))
    normalized.sort(key=lambda m: m["method_id"])
    return hashlib.sha256(canonical(normalized)).hexdigest()


def _difference(left, right):
    missing = [access for access, value in zip(ACCESS, (left, right)) if value is None]
    delta = None if missing else right - left
    require(delta is None or math.isfinite(delta), "paired difference overflow")
    return dict(paper_data=left, paper_data_author_code=right,
                author_code_minus_paper_data=delta,
                undefined_in=missing)


def _cells(method):
    return {(row["target"], row["condition"]): row for row in method["cells"]}


def evaluate_pair(targets, paper_data, paper_data_author_code):
    """Retain complete per-arm outcomes and all matched original result cells."""
    submissions = (paper_data, paper_data_author_code)
    for expected, submission in zip(ACCESS, submissions):
        require(isinstance(submission, dict) and submission.get("access_condition") == expected,
                "each positional arm must name its exact access condition")
    outcomes = {key for key in ("candidate", "reproduction") if key in paper_data}
    require(outcomes and outcomes == {key for key in ("candidate", "reproduction") if key in paper_data_author_code},
            "paired arms must supply the same nonempty outcome set")
    # Both use one unchanged target object. Each existing evaluator checks every
    # participant and contrast, including participants missing a held observation.
    scored = [panel.evaluate(targets, submission) for submission in submissions]
    references = [reference_identity(submission["references"]) for submission in submissions]
    require(references[0] == references[1], "paired arms must use identical complete reference operands")
    candidate, reproduction = None, None
    if "candidate" in outcomes:
        arms = [_cells(result["candidate"]) for result in scored]
        candidate = dict(method_ids={access: result["candidate"]["method_id"] for access, result in zip(ACCESS, scored)},
                         cells=[])
        for target in panel.TARGETS:
            for condition in panel.CONDITIONS:
                rows = [arm[target, condition] for arm in arms]
                candidate["cells"].append(dict(target=target, condition=condition,
                    source_rmse_ms=_difference(*(row["source_rmse_ms"] for row in rows)),
                    full_data_latency_r2=_difference(*(row["full_data_latency_r2"] for row in rows)),
                    full_data_accuracy_r2=_difference(*(row["full_data_accuracy_r2"] for row in rows))))
    if "reproduction" in outcomes:
        arms = [{method["method_id"]: _cells(method) for method in result["reproduction"]["methods"]}
                for result in scored]
        reproduction = dict(findings=[])
        for law in panel.AUTHOR_MODELS:
            metrics = ("source_rmse_ms", "full_data_latency_r2") + (("full_data_accuracy_r2",) if law == "fechner" else ())
            for target in panel.TARGETS:
                for condition in panel.CONDITIONS:
                    for metric in metrics:
                        reproduction["findings"].append(dict(model=law, target=target, condition=condition,
                            metric=metric, **_difference(*(arm[law][target, condition][metric] for arm in arms))))
    return dict(schema="decision-times-paired-panel-v1", task_id=panel.legacy.TASK,
        targets_sha256=panel.target_digest(targets), references_sha256=references[0],
        arms=dict(zip(ACCESS, scored)), candidate=candidate, reproduction=reproduction,
        difference_direction="paper_data_author_code_minus_paper_data",
        primary_metric="original_contrast_left_out_rmse_ms_panel",
        qualification="descriptive_paired_software_component_only", scientific_qualification=False,
        access_delivery_attested=False, reproduction_pass=None, paper_win=None,
        limits=["Both arm labels and matching operands are software checks, not protected access or matched-resource evidence.",
                "Authentic B/H populations, 512 Hz fixed HMP target lineage, native fitting and qualified references remain unresolved.",
                "All 18 candidate RMSE cells and 126 reproduction findings are retained; undefined companions are never dropped.",
                "Full-data R2 companions are diagnostics, not substitute improvement objectives.",
                "Strongest-comparator preselection, tolerances, joint 18-cell superiority and participant uncertainty remain unadmitted.",
                "No aggregate score, scalar reward, reproduction pass or paper win is assigned."])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", type=Path)
    parser.add_argument("paper_data", type=Path)
    parser.add_argument("paper_data_author_code", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = {key: getattr(args, key).read_bytes() for key in ("targets",) + ACCESS}
    result = evaluate_pair(*(panel.load_json(raw[key]) for key in ("targets",) + ACCESS))
    result["input_file_sha256"] = {key: hashlib.sha256(body).hexdigest() for key, body in raw.items()}
    with args.output.open("x") as handle:
        handle.write(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
