"""Join NEURONA's six declared access/input trace cells without claiming execution.

Operator-only metadata and source trace arithmetic; no model or neural-data loader.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


_IMPLEMENTATIONS = Path(__file__).resolve().parents[1]
_PINS = {
    "initial-evaluator-v1/evaluator.py": "9d7ddf27151465693feb9346f906e3ad583194b022135a5c0cbfbfa1782b21a6",
    "source-scoring-v2/source_score.py": "c4d1d07bb20e58e4bdf6b2b36f01a87c419b5b96a9077803a15bba50dfe643ca",
}
for _relative, _expected in _PINS.items():
    if hashlib.sha256((_IMPLEMENTATIONS / _relative).read_bytes()).hexdigest() != _expected:
        raise ValueError("unchanged source-scoring dependency identity differs: " + _relative)
_spec = importlib.util.spec_from_file_location(
    "neurona_six_cell_source_score", _IMPLEMENTATIONS / "source-scoring-v2/source_score.py")
source = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = source
_spec.loader.exec_module(source)

ContractError = source.ContractError
SCHEMA = "neurona-six-cell-trace-suite/v1"
ACCESS = ("paper_data", "paper_data_author_code")
CONDITIONS = source.legacy.CONDITIONS
COMMON = ("common_inputs_sha256", "resource_budget_sha256")
DECLARATIONS = (*COMMON, "author_code_sha256", "candidate_code_sha256", "training_run_sha256")
ABLATION_DESIGN = "same_frozen_model_inference_ablations"


def require(condition, message):
    if not condition:
        raise ContractError(message)


def _exact(value, keys, label):
    require(isinstance(value, dict) and set(value) == set(keys), label + " fields differ")


def _binding(value, label):
    source.legacy._sha(value, label)
    return value


def _cell_index(suite):
    _exact(suite, ("schema", "comparison_plan_sha256", "control_design", "cells"), "suite")
    require(suite["schema"] == SCHEMA, "unsupported suite schema")
    _binding(suite["comparison_plan_sha256"], "comparison_plan_sha256")
    require(suite["control_design"] == ABLATION_DESIGN,
            "this component supports same-model inference ablations only")
    require(isinstance(suite["cells"], list) and len(suite["cells"]) == 6,
            "exactly six access/input cells required")
    cells = {}
    for cell in suite["cells"]:
        _exact(cell, ("run", "declarations"), "cell")
        run, declarations = cell["run"], cell["declarations"]
        require(isinstance(run, dict), "run must be an object")
        key = (run.get("access_condition"), run.get("neural_condition"))
        require(key[0] in ACCESS and key[1] in CONDITIONS, "unknown suite cell")
        require(key not in cells, "duplicate access/input cell")
        _exact(declarations, DECLARATIONS, "declarations")
        for name in DECLARATIONS:
            if name != "author_code_sha256":
                _binding(declarations[name], name)
        if key[0] == "paper_data":
            require(declarations["author_code_sha256"] is None,
                    "paper_data must declare no supplied author-code bundle")
        else:
            _binding(declarations["author_code_sha256"], "author_code_sha256")
        cells[key] = cell
    require(set(cells) == {(a, c) for a in ACCESS for c in CONDITIONS}, "incomplete suite")
    first = cells[(ACCESS[0], CONDITIONS[0])]["declarations"]
    for cell in cells.values():
        for name in COMMON:
            require(cell["declarations"][name] == first[name], "suite changed " + name)
    # A zero-input inference ablation is the same frozen model, not a retrained baseline.
    for access in ACCESS:
        base = cells[(access, "neural")]
        for condition in CONDITIONS:
            cell = cells[(access, condition)]
            for name in ("author_code_sha256", "candidate_code_sha256", "training_run_sha256"):
                require(cell["declarations"][name] == base["declarations"][name],
                        "within-arm ablation changed " + name)
            for name in ("checkpoint_sha256", "selection_policy", "train_hop"):
                require(cell["run"].get(name) == base["run"].get(name),
                        "within-arm ablation changed " + name)
    return cells


def _difference(left, right, *, completed=True):
    """Right minus left, only for identical nonempty included query identities."""
    same = bool(left["queries"]) and left["included_ids"] == right["included_ids"]
    comparable = same and completed
    return {
        "left_correct": left["correct"], "right_correct": right["correct"],
        "left_queries": left["queries"], "right_queries": right["queries"],
        "same_included_queries": same, "both_passes_completed": completed,
        "left_only_ids": sorted(set(left["included_ids"]) - set(right["included_ids"])),
        "right_only_ids": sorted(set(right["included_ids"]) - set(left["included_ids"])),
        "right_minus_left": right["accuracy"] - left["accuracy"] if comparable else None,
    }


def _contrasts(left, right):
    require(set(left["posthoc"]) == set(right["posthoc"]), "posthoc metric panel changed")
    return {
        "training_monitor": _difference(
            left["training_monitor"], right["training_monitor"],
            completed=left["training_monitor"]["completed"] and right["training_monitor"]["completed"]),
        "posthoc": {name: _difference(left["posthoc"][name], right["posthoc"][name])
                    for name in left["posthoc"]},
    }


def score_suite(manifest, suite, vocabulary):
    """Recompute all cells from traces; never trust caller-supplied accuracy scalars."""
    cells = _cell_index(suite)
    reports = {access: {} for access in ACCESS}
    for access in ACCESS:
        for condition in CONDITIONS:
            reports[access][condition] = source.score(manifest, cells[(access, condition)]["run"], vocabulary)
    within = {
        access: {"neural_minus_" + control: _contrasts(reports[access][control], reports[access]["neural"])
                 for control in ("no_neural", "shuffled_neural")}
        for access in ACCESS
    }
    between = {condition: _contrasts(reports["paper_data"][condition], reports["paper_data_author_code"][condition])
               for condition in CONDITIONS}
    return {
        "schema": "neurona-six-cell-trace-report/v1",
        "suite_sha256": source.digest(suite), "manifest_sha256": source.digest(manifest),
        "vocabulary_sha256": source.digest(vocabulary),
        "comparison_plan_sha256": suite["comparison_plan_sha256"],
        "engineering_fixture": manifest["engineering_fixture"],
        "control_design": ABLATION_DESIGN, "declared_cell_count": 6,
        "cells": reports,
        "declarations": {a: {c: cells[(a, c)]["declarations"].copy() for c in CONDITIONS} for a in ACCESS},
        "within_access_contrasts": within,
        "author_code_arm_minus_paper_data_arm": between,
        "execution_verified": False, "resource_equality_verified": False,
        "information_boundary_verified": False, "native_query_population_authenticated": False,
        "separately_trained_text_only_present": False, "full_benchmark_panel_complete": False,
        "reproduction_established": False, "improvement_established": False, "current_sota_established": False,
        "qualification": "six_declared_trace_cells_and_binding_consistency_only",
        "limits": [
            "Declarations and equal hashes do not authenticate delivery, model execution, consumed resources or isolation.",
            "Original baseline pipelines and separately trained text-only companion remain absent.",
            "Original native query population, publication checkpoint/scoring identity and statistical decision rules remain unresolved.",
            "No averaging across access/input conditions or significance, causal neural-contribution or superiority decision is made.",
        ],
    }


def compare_suites(manifest, reference_suite, candidate_suite, vocabulary):
    """Compare corresponding cells, preserving all source denominator changes."""
    reference_cells = _cell_index(reference_suite)
    candidate_cells = _cell_index(candidate_suite)
    require(reference_suite["comparison_plan_sha256"] == candidate_suite["comparison_plan_sha256"],
            "candidate/reference comparison plan differs")
    for key in reference_cells:
        for name in (*COMMON, "author_code_sha256"):
            require(reference_cells[key]["declarations"][name] == candidate_cells[key]["declarations"][name],
                    "candidate/reference changed " + name)
    reference = score_suite(manifest, reference_suite, vocabulary)
    candidate = score_suite(manifest, candidate_suite, vocabulary)
    paired = {a: {c: _contrasts(reference["cells"][a][c], candidate["cells"][a][c])
                  for c in CONDITIONS} for a in ACCESS}
    return {
        "schema": "neurona-six-cell-trace-comparison/v1",
        "reference": reference, "candidate": candidate,
        "candidate_minus_reference_by_cell": paired,
        "reproduction_established": False, "improvement_established": False,
        "current_sota_established": False,
        "qualification": "paired_declared_trace_diagnostics_only",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("suite", type=Path)
    parser.add_argument("vocabulary", type=Path)
    parser.add_argument("--reference-suite", type=Path)
    args = parser.parse_args()
    manifest, suite, vocabulary = (source.legacy._load(str(p)) for p in (args.manifest, args.suite, args.vocabulary))
    result = (compare_suites(manifest, source.legacy._load(str(args.reference_suite)), suite, vocabulary)
              if args.reference_suite else score_suite(manifest, suite, vocabulary))
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
