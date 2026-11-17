"""ABR threshold scorer with the registered animal-by-stimulus case unit.

Reuse the preserved v1 arithmetic and authentic-score refusal. The v2 reference
validator additionally rejects multiple case IDs for one animal/stimulus series;
repeated ears, runs or sessions require source-justified assembly upstream.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


_V1_PATH = Path(__file__).resolve().parents[1] / "initial-evaluator-v1" / "abr_evaluator.py"
_SPEC = importlib.util.spec_from_file_location("_abr_transfer_preserved_v1", _V1_PATH)
_v1 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_v1)

TASK_ID = _v1.TASK_ID
CONTRACT_SHA256 = _v1.CONTRACT_SHA256
TARGET_RELEASE = _v1.TARGET_RELEASE
BACKGROUNDS = _v1.BACKGROUNDS
TONES_HZ = _v1.TONES_HZ
ContractError = _v1.ContractError
animal_bootstrap = _v1.animal_bootstrap
audit_threshold_rules = _v1.audit_threshold_rules


def validate_reference(reference):
    """Validate one assembled case per animal and registered stimulus.

    IDs alone are insufficient: relabeling an ear/run/repeat with a fresh case ID
    must not change its weight. We neither average repeated annotations nor choose
    one recording. Those choices need an authenticated upstream assembly policy.
    The input remains untouched, and an ambiguity is a reference error, not a
    candidate error or a reason to calculate a complete-case score.
    """
    animals, cases = _v1.validate_reference(reference)
    series = {}
    for case_id, case in cases.items():
        key = (case["animal_id"], _v1.stimulus_key(case["stimulus"]))
        series.setdefault(key, []).append(case_id)
    collisions = [sorted(case_ids) for case_ids in series.values() if len(case_ids) > 1]
    if collisions:
        raise ContractError(
            "multiple cases for one animal-by-stimulus series; "
            "assemble repeated ears/sessions/runs with a source-justified policy "
            "before scoring; conflicting case IDs: " + repr(sorted(collisions))
        )
    return animals, cases


def evaluate(reference, predictions, baseline=None, bootstrap_replicates=2000, seed=0):
    validate_reference(reference)
    report = _v1.evaluate(reference, predictions, baseline, bootstrap_replicates, seed)
    report["implementation_version"] = "series-evaluator-v2"
    report["case_unit"] = "one assembled animal-by-stimulus series"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--baseline")
    parser.add_argument("--bootstrap-replicates", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    try:
        report = evaluate(
            _v1._load(args.reference), _v1._load(args.predictions),
            _v1._load(args.baseline) if args.baseline else None,
            args.bootstrap_replicates, args.seed,
        )
    except (ContractError, OSError, json.JSONDecodeError) as error:
        parser.exit(2, f"reference/input rejected: {error}\n")
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0 if report["submission_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
