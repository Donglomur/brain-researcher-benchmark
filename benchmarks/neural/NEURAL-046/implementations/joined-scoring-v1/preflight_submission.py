"""Check NEURAL-046 prediction coverage using three participant-side JSON files.

This does not grade, fit, seal an attempt, authenticate model artifacts or open
the operator's case binding or targets. The existing grader remains separate.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path


ADAPTER_SHA256 = "519299feb9e0be727e66ef77335f049062d7293d0695f3e48c1e00c27fb7529c"


def _load_adapter():
    path = Path(__file__).with_name("grade_artifacts.py")
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("linked_adapter_source")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ADAPTER_SHA256:
        raise ValueError("artifact_adapter_source_changed")
    spec = importlib.util.spec_from_file_location("_neural046_preflight_artifacts", path)
    module = importlib.util.module_from_spec(spec)
    # Execute the authenticated bytes, without reopening the source pathname.
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


adapter = _load_adapter()
scorer = adapter.load_scorer()


def validate_predictions(public, submission, sensitivity):
    """Return coverage commitments; no private input or grading callback exists.

    The primary validator's model-artifact commitment fields are retained as
    declared strings/values; this function does not authenticate their content.
    """
    public, submission, sensitivity = deepcopy((public, submission, sensitivity))
    scorer.require(type(public) is dict and public.get("task") == "NEURAL-046", "task")
    cell = scorer.shared.validate_submission(submission, public)
    expected = ({"MEN_independently_tuned"}
                if "MEN" in cell["NEURAL-046"]["models_produced"] else set())
    scorer.require(type(sensitivity) is dict and set(sensitivity) == expected,
                   "sensitivity_backfill")
    query_ids = {row["id"] for row in public["query"]}
    for predictions in sensitivity.values():
        scorer.require(type(predictions) is dict and set(predictions) == query_ids,
                       "sensitivity_case_join")
        for value in predictions.values():
            scorer.finite(value, "sensitivity_prediction")
    return {
        "schema": "neural046-participant-prediction-preflight-v1",
        "task": "NEURAL-046",
        "cell_id": public["cell_id"],
        "endpoint": public["endpoint"],
        "query_cases": len(query_ids),
        "primary_models": sorted(submission["predictions"]),
        "sensitivity_models": sorted(expected),
        "public_digest": scorer.digest(public),
        "submission_digest": scorer.digest(submission),
        "sensitivity_digest": scorer.digest(sensitivity),
        "status": "prediction_shape_and_coverage_valid",
        "grading_target_loader_invocations": 0,
        "model_artifacts_authenticated": False,
        "producer_closure_verified": False,
        "private_case_binding_verified": False,
        "scientific_qualification": False,
    }


def preflight_files(public_path, submission_path, sensitivity_path, report_path):
    """Read only the three named JSON payloads and exclusively create a report."""
    output = Path(report_path).absolute()
    adapter.plain_directory(output.parent)
    adapter.require(not output.exists() and not output.is_symlink(), "report_exists")
    objects = [adapter.strict_json(adapter.read_file(path, adapter.FILE_CAP))
               for path in (public_path, submission_path, sensitivity_path)]
    result = validate_predictions(*objects)
    adapter.exclusive_write(output, adapter.encode(result))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public", required=True)
    parser.add_argument("--submission", required=True)
    parser.add_argument("--sensitivity", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args(argv)
    preflight_files(args.public, args.submission, args.sensitivity, args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
