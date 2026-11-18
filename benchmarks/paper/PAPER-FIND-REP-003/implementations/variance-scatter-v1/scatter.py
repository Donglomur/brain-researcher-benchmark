"""Private Figure 5 supplement 2 E/F derivation, without a scientific win rule.

Reuse the complete source-panel validator. Each original held-out fit contributes
24 pairs of sample target variance and variance explained; do not replace the
scatter by a correlation, averaged trial variance or flattened score.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path

SCORER_SHA256 = "192438e3a2c6c066fc72ef0fd9f3b7d8fe2a54b1fa562d86eb95a942271b89c3"
SCHEMA = "fig5-target-variance-scatter/v1"


class ScatterError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ScatterError(message)


def _load_scorer(path):
    """Bind the already reviewed metric/support code before interpreting input."""
    body = path.read_bytes()
    require(hashlib.sha256(body).hexdigest() == SCORER_SHA256,
            "source-panel dependency changed; review and repin required")
    spec = importlib.util.spec_from_file_location("fig5_bound_source_panel", path)
    module = importlib.util.module_from_spec(spec)
    # Execute the authenticated bytes, not a second potentially changed file read.
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


_panel = _load_scorer(Path(__file__).resolve().parents[1] / "source-panel-v1" / "scorer.py")


def sample_variances(rows):
    """MATLAB var(X) default: n-1 over concatenated held-out timepoints.

    This function is deliberately independent of the VE ratio's cancelling n-1
    factors: scatter x-coordinates must retain the actual sample divisor.
    """
    require(type(rows) is list and len(rows) >= 2, "at least two variance rows required")
    _panel.matrix(rows, len(rows), "variance targets")
    result = []
    for joint in range(24):
        values = [_panel.finite(row[joint]) for row in rows]
        mean = math.fsum(values) / len(values)
        value = math.fsum((item - mean) ** 2 for item in values) / (len(values) - 1)
        require(math.isfinite(value) and value > 0,
                "constant or overflow target: source VE remains unresolved")
        result.append(value)
    return result


def evaluate(reference, candidate):
    """Derive full companion from the exact original-panel input format.

    Input is operator-private. Its scientific provenance and original-fold
    authenticity remain separate from the structural/numerical checks here.
    """
    panel = _panel.evaluate(reference, candidate)
    refs = {(item["mouse"], item["session"]): item for item in reference["sessions"]}
    sessions = []
    for scored in panel["sessions"]:
        ref = refs[(scored["mouse"], scored["session"])]
        trials = {item["trial_number"]: item["joint_angles"] for item in ref["trials"]}
        models = {item["model"]: item for item in ref["models"]}
        variances, sample_counts = [], []
        for model in range(1, 51):
            rows = [row for trial in models[model]["test_trials"] for row in trials[trial]]
            variances.append(sample_variances(rows))
            sample_counts.append(len(rows))
        # Source plot loops proximal joints then distal joints; each scatter
        # receives its 50 fit values. All 1,200 points per session are retained.
        points = []
        for joint, name in enumerate(_panel.JOINTS):
            for model in range(1, 51):
                points.append({
                    "joint_index": joint + 1, "joint_name": name,
                    "joint_group": "proximal" if joint < 7 else "distal",
                    "model": model, "heldout_timepoint_count": sample_counts[model - 1],
                    "target_sample_variance_deg2": variances[model - 1][joint],
                    "author_ve": scored["author_ve"][model - 1][joint],
                    "candidate_ve": scored["candidate_ve"][model - 1][joint],
                    "candidate_minus_author_ve": scored["candidate_minus_author_ve"][model - 1][joint],
                })
        sessions.append({
            "mouse": scored["mouse"], "session": scored["session"], "area": scored["area"],
            "source_branch": "output", "points": points,
        })
    require(len(sessions) == 10 and all(len(s["points"]) == 1200 for s in sessions),
            "complete ten-session variance/VE family required")
    return {
        "schema": SCHEMA, "task_id": _panel.TASK, "source_revision": _panel.REVISION,
        "component": "fig5_supplement2_E_F_variance_VE_derivation",
        "source_panel_sha256": SCORER_SHA256, "point_count": 12000, "sessions": sessions,
        "variance_definition": "sample variance with divisor n-1 over concatenated held-out trial timepoints",
        "metric_definition": "1-var(y-yhat)/var(y); no clipping or constant-bias penalty",
        "source_plot_order": "session, joint 1..24, source model 1..50",
        "report_visibility": "operator_private",
        "scientifically_qualified": False, "source_author_run_qualified": False,
        "published_numeric_baseline_recovered": False, "paper_win": None,
        "limits": [
            "Generated software controls do not authenticate original neural inputs, folds or author outputs.",
            "All original target/prediction bodies remain private; derived variances are also protected outcomes.",
            "Only original output-branch supplement2 E/F quantities are derived; partial, residual, lagged and posture companions remain separate.",
            "No correlation scalar, paper-win threshold, uncertainty decision or full-paper completion is introduced.",
            "Existing source-panel zero-variance rejection is preserved; the paper's zero-variance handling remains unresolved.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--reference-sha256", required=True)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--candidate-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    # Refuse existing paths before expensive input work; the final exclusive
    # creation remains authoritative if another process races this check.
    require(not args.output.exists() and not args.output.is_symlink(), "output already exists")
    ref_body, candidate_body = args.reference.read_bytes(), args.candidate.read_bytes()
    ref_sha, candidate_sha = hashlib.sha256(ref_body).hexdigest(), hashlib.sha256(candidate_body).hexdigest()
    require(ref_sha == args.reference_sha256, "operator reference hash mismatch")
    require(candidate_sha == args.candidate_sha256, "frozen candidate hash mismatch")
    report = evaluate(_panel.read_json_bytes(ref_body), _panel.read_json_bytes(candidate_body))
    report.update(reference_sha256=ref_sha, candidate_sha256=candidate_sha)
    body = (json.dumps(report, separators=(",", ":"), allow_nan=False) + "\n").encode()
    with args.output.open("xb") as handle:
        handle.write(body)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ScatterError, _panel.PanelError, KeyError, TypeError, OverflowError,
            OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"inadmissible: {error}")
