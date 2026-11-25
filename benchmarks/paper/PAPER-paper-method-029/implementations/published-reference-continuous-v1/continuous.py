"""Complete Figure 2 discrepancy reporting without a binary decision margin.

The pinned predecessor authenticates the publication and validates the original
normalized replay panel. This module adds no model execution or success policy.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import types

PREDECESSOR_SHA256 = "3e4d5d23fbd740999f60b8deaaa9689db72bc3821f07259639716b70d60263f8"
PREDECESSOR = Path(__file__).resolve().parent.parent / "published-reference-v1" / "published_reference.py"


def _load_predecessor():
    with PREDECESSOR.open("rb") as stream:
        payload = stream.read(65537)
    if len(payload) > 65536 or hashlib.sha256(payload).hexdigest() != PREDECESSOR_SHA256:
        raise ValueError("Published reference implementation identity mismatch")
    module = types.ModuleType("deeprecon_published_reference_v1")
    module.__file__ = str(PREDECESSOR)
    exec(compile(payload, str(PREDECESSOR), "exec"), module.__dict__)
    return module


reference_api = _load_predecessor()


def _root_mean_square(values):
    """Compute the declared RMS without squaring away small nonzero errors."""
    scale = max(abs(value) for value in values)
    if scale == 0:
        return 0.0
    return scale * math.sqrt(math.fsum((value / scale) ** 2 for value in values) / len(values))


def compare_continuous(reference, replay):
    """Return every pair discrepancy; do not infer provenance or a pass/fail."""
    reference_api.require(isinstance(reference, dict) and set(reference) == reference_api.EXPECTED_KEYS,
                          "Complete publication reference panel required")
    published = {key: reference_api.finite_correlation(value, "published pair mean")
                 for key, value in reference.items()}
    actual = reference_api.replay_values(replay)
    fields = ("source", "target", "roi", "method", "axis")
    rows = []
    for key in sorted(reference_api.EXPECTED_KEYS):
        error = actual[key] - published[key]
        rows.append(dict(zip(fields, key), published_mean=published[key],
                         replay_mean=actual[key], signed_error=error, absolute_error=abs(error)))
    summaries = []
    for roi, method, axis in itertools.product(reference_api.ROIS, reference_api.METHODS, reference_api.AXES):
        group = [row for row in rows if (row["roi"], row["method"], row["axis"]) == (roi, method, axis)]
        summaries.append({
            "roi": roi, "method": method, "axis": axis, "pairs": 20,
            "published_pair_mean": math.fsum(row["published_mean"] for row in group) / 20,
            "replay_pair_mean": math.fsum(row["replay_mean"] for row in group) / 20,
            "mean_signed_error": math.fsum(row["signed_error"] for row in group) / 20,
            "mean_absolute_pair_error": math.fsum(row["absolute_error"] for row in group) / 20,
            "maximum_absolute_pair_error": max(row["absolute_error"] for row in group),
            "root_mean_square_pair_error": _root_mean_square([row["signed_error"] for row in group]),
        })
    return {
        "schema": "deeprecon_published_pair_discrepancies/v1", "task_id": reference_api.TASK_ID,
        "comparison_scope": "arithmetic_published_pair_means_only", "pair_axis_values": 480,
        "summary_statistic": "observed_equal_pair_mean_not_figure_bootstrap_mean",
        "rows": rows, "summaries": summaries, "decision": "not_made",
        "reference_authentication": "not_established_by_pure_function",
        "native_replay_provenance": "not_authenticated_by_result_declarations",
        "scientific_reproduction": "not_established_by_arithmetic_comparison",
        "scientific_improvement": "not_evaluated",
        "limits": [
            "All 480 values are reported; no tolerance, pass rate, selected subset or cross-endpoint headline is supplied.",
            "The source clips normalized per-feature correlations to [-1,1] before pair averaging; this domain is retained.",
            "The publication table does not authenticate original feature ceilings, masks, fitting or candidate custody.",
            "Twenty directed pairs share five people; these summaries are not independent-subject uncertainty or the source bootstrap.",
            "Binary agreement or superiority claims require a separately justified decision rule and qualified matched execution.",
            "Paper+data and paper+data+author-code attempts require matched access and budgets; no model or SOTA result is implied.",
        ],
    }


def _strict_json(payload):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            reference_api.require(key not in result, "Duplicate replay JSON key")
            result[key] = value
        return result

    def nonfinite(_):
        raise reference_api.ReferenceError("Nonfinite replay JSON constant")

    return json.loads(payload, object_pairs_hook=unique, parse_constant=nonfinite)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("source_csv", help="Exact publisher CSV, outside Git")
    parser.add_argument("--replay", required=True, help="Complete normalized replay or compact export")
    parser.add_argument("--output", required=True, help="Fresh external JSON report")
    args = parser.parse_args(argv)
    output = Path(args.output)
    reference_api.require(not output.exists(), "Refusing to overwrite an existing output")
    reference = reference_api.load_reference(args.source_csv)
    payload = reference_api.read_bounded(args.replay, 64 * 1024 * 1024)
    report = compare_continuous(reference, _strict_json(payload))
    report["reference_authentication"] = "publisher_byte_identity_verified"
    report["reference_artifact"] = {"url": reference_api.SOURCE_URL, "sha256": reference_api.SOURCE_SHA256,
                                    "bytes": reference_api.SOURCE_BYTES, "byte_identity_verified": True}
    report["replay_sha256"] = hashlib.sha256(payload).hexdigest()
    report["reader_sha256"] = PREDECESSOR_SHA256
    encoded = json.dumps(report, indent=2, allow_nan=False) + "\n"
    with output.open("x") as stream:
        stream.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
