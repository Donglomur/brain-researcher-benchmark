"""Harbor data-artifact adapter for the unchanged full PFC scorer.

Only evaluator-authored modules are imported. A submission is JSONL data,
never Python, pickle, a plugin, or a program that the verifier executes.
"""
import hashlib
import json
from pathlib import Path
import sys

SCIENCE = Path(__file__).resolve().parent / "science"
sys.path.insert(0, str(SCIENCE))
import endpoint_cli as endpoint
from conditional_kernel import FAMILIES, case_keys, need, validate_packet

PACKET_SHA256 = "8f6dc8ffff5e6ab4aa3be41dd3e9b0847c829b345142204d154124847908b21e"
PACKET_BYTES = 5368996
MAX_METRICS = 64 * 1024**2
INPUT_ERRORS = (ValueError, TypeError, KeyError, IndexError, AttributeError,
                OSError, OverflowError, RecursionError)


def verify_runtime():
    import numpy
    import scipy
    need((sys.version.split()[0], numpy.__version__, scipy.__version__) ==
         ("3.12.8", "2.2.6", "1.15.3"), "admitted scientific runtime")


def exact_reward(report, packet):
    """Only a freshly computed trusted report may enter this predicate."""
    need(type(report) is dict and report.get("schema") ==
         "PFC_FULL99_CONDITIONAL_SCORE_V1", "complete scorer report")
    need(report.get("packet_sha256") == PACKET_SHA256, "bound report packet")
    expected = case_keys(packet)
    need(len(expected) == 69 and len(packet["animals"]) == 68, "full case roster")
    need(report.get("roster") == {"recordings": 99, "units": 19186,
         "animals": 68, "families": 12, "analytic_contexts": 16,
         "gao_contexts": 4}, "complete report dimensions")
    rows = report.get("cases")
    need(type(rows) is list and len(rows) == 69, "all scored cases")
    passed = True
    for row, key in zip(rows, expected):
        need(type(row) is dict and row.get("case") == key, "ordered scored cases")
        families = row.get("moment_errors")
        need(type(families) is list and len(families) == 12, "all scored families")
        for cell, family, family_key in zip(families, packet["families"], FAMILIES):
            need(type(cell) is dict and cell.get("family") == family_key,
                 "ordered scored families")
            count = len(family["labels"]) * 8
            need(type(cell.get("cells")) is int and cell["cells"] == count,
                 "all scored coordinates")
            for field in ("counts", "mean", "variance"):
                error = cell.get(field)
                need(type(error) is dict, "complete exact error field")
                n = error.get("unequal_cells")
                maximum = error.get("max_absolute_error_exact")
                need(type(n) is int and 0 <= n <= count, "exact mismatch count")
                need(type(maximum) is list and len(maximum) == 2 and
                     all(type(x) is int for x in maximum), "exact maximum error")
                # No rounded average, numerical epsilon, or near-one threshold.
                passed = passed and n == 0 and maximum == [0, 1]
    return 1 if passed else 0


def evaluate(packet_path, candidate_path, metrics_path):
    """Validate all candidate structure before any target-dependent scoring.

    Missing/malformed output is an ordinary failed attempt. Trusted packet,
    runtime, scorer, or report failures propagate as infrastructure failures.
    """
    verify_runtime()
    packet_raw = endpoint.read(packet_path, endpoint.MAX_PACKET)
    need(len(packet_raw) == PACKET_BYTES and
         hashlib.sha256(packet_raw).hexdigest() == PACKET_SHA256,
         "exact released packet")
    packet = endpoint.decode(packet_raw)
    validate_packet(packet, expected_units=19186, expected_recordings=99)
    need(len(packet["animals"]) == 68, "complete animal roster")
    try:
        validated_cases, candidate_digest = endpoint.candidate_cases(
            candidate_path, packet, PACKET_SHA256)
        del validated_cases
    except INPUT_ERRORS as error:
        return {"reward": 0, "status": "invalid_submission",
                "reason_type": type(error).__name__}
    # This computes the unchanged reference and all continuous diagnostics.
    # The report is created exclusively in the clean verifier, not uploaded.
    completion = endpoint.score(packet_path, candidate_path, metrics_path)
    need(completion == {"cases": 69, "complete": True,
         "historical_equivalence": False, "readiness_count_delta": 0},
         "unchanged scorer completed")
    report = endpoint.decode(endpoint.read(metrics_path, MAX_METRICS))
    need(report.get("candidate_sha256") == candidate_digest,
         "candidate unchanged across validation and scoring")
    return {"reward": exact_reward(report, packet),
            "status": "complete", "cases": 69,
            "candidate_sha256": candidate_digest,
            "metrics_path": str(metrics_path)}


def main():
    # These paths are fixed by the task and clean verifier image.
    result = evaluate(Path("/input/participant-packet.json"),
                      Path("/app/output/submission.jsonl"),
                      Path("/logs/verifier/scientific-metrics.json"))
    Path("/logs/verifier/adapter-result.json").write_text(
        json.dumps(result, sort_keys=True) + "\n")
    return result


if __name__ == "__main__":
    main()
