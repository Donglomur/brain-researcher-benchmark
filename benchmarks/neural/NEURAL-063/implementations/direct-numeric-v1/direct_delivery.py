"""Paired direct numeric requests and complete response collection for NEURAL-063.

Consumes only prepared, permitted views. It never opens native source, query
targets, models or scores. Host isolation and authentic preparation are separate.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys

LEGACY = Path(__file__).resolve().parents[1] / "neural-063" / "complete-omission-v1"
sys.path.insert(0, str(LEGACY))
from owner.io import ContractError, canonical, decode
from owner.scoring import admit_predictions
from references.schema import admit_rows, timing_view

SCHEMA = "neural063_direct_numeric_pair_v1"
BASELINE = "Mean population dF/F in [-0.2,0) seconds relative to scheduled omission."
TARGET_BINS = [[0.0, 0.2], [0.2, 0.4], [0.4, 0.6]]
HISTORY_BINS = [[j / 5, (j + 1) / 5] for j in range(-12, 0)]
INSTRUCTION = (
    "Predict the three population-mean dF/F changes after this scheduled omission. "
    "Each value is the mean in its stated half-open target bin minus the stated "
    "baseline; units are dimensionless dF/F, not percent. Return one JSON object "
    "with exactly request_sha256, id, information, and values (three finite numbers "
    "in target-bin order). Copy identity fields from this request. Use only the "
    "provided observations and demonstrations; do not use tools, source lookup, "
    "other query events or outcome feedback. Opaque hierarchy IDs are grouping "
    "tokens, not predictive features."
)


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _copy(value):
    return decode(canonical(value))


def _paired(timing, neural, split):
    t = admit_rows(timing, split, view="T")
    n = admit_rows(neural, split, view="N")
    if canonical(timing_view(n)) != canonical(t):
        raise ContractError("T/N must have identical complete IDs, hierarchy, context and timing")
    return t, n


def _schedule_support(rows):
    # The producer's native-frame guard still remains mandatory. These checks
    # prevent impossible declared timings from becoming participant requests.
    for row in rows:
        starts = [x["start_relative_seconds"] for x in row["previous"]] + [0]
        if any(not .70 <= b - a <= .80 for a, b in zip(starts, starts[1:])):
            raise ContractError("prepared row violates omission preceding-cadence contract")


def build(timing, neural, *, fit_timing=None, fit_neural=None, demonstration_ids=()):
    """Return both direct conditions for every prepared query event, in order.

    Demonstrations are an explicit, ordered, fixed list of FIT event IDs. The
    supplied FIT views must contain all 73 FIT mice, and T/N use identical demos.
    The zero-shot path rejects development inputs and opens no target-bearing view.
    """
    t, n = _paired(timing, neural, "query")
    _schedule_support(t)
    if not isinstance(demonstration_ids, (list, tuple)) or any(
            not isinstance(x, str) or not x for x in demonstration_ids):
        raise ContractError("explicit ordered demonstration IDs required")
    if len(set(demonstration_ids)) != len(demonstration_ids):
        raise ContractError("duplicate demonstration ID")
    demos = {"T": [], "N": []}
    if demonstration_ids:
        if fit_timing is None or fit_neural is None:
            raise ContractError("both complete FIT views required for demonstrations")
        ft, fn = _paired(fit_timing, fit_neural, "fit")
        _schedule_support(ft)
        for key in ("id", "mouse", "session", "experiment"):
            if {r[key] for r in ft} & {r[key] for r in t}:
                raise ContractError("FIT/query identity or biological hierarchy overlap")
        for info, rows in (("T", ft), ("N", fn)):
            lookup = {r["id"]: r for r in rows}
            if any(ident not in lookup for ident in demonstration_ids):
                raise ContractError("demonstration ID missing from complete FIT views")
            demos[info] = [_copy(lookup[ident]) for ident in demonstration_ids]
    elif fit_timing is not None or fit_neural is not None:
        raise ContractError("zero-shot condition must not receive FIT targets")
    condition = "fixed_fit_demonstrations" if demonstration_ids else "zero_shot"
    requests = []
    for tr, nr in zip(t, n):
        for info, row in (("T", tr), ("N", nr)):
            request = {
                "schema": "neural063_direct_request_v1", "mode": "direct_numeric",
                "information": info, "exposure_condition": condition,
                "id": row["id"], "instruction": INSTRUCTION,
                "units": "dimensionless dF/F", "baseline": BASELINE,
                "target_bins_seconds": _copy(TARGET_BINS), "bin_closure": "[left,right)",
                "observation": _copy(row), "demonstrations": _copy(demos[info]),
            }
            if info == "N":
                request["history_bins_seconds"] = _copy(HISTORY_BINS)
            request["request_sha256"] = digest(request)
            requests.append(request)
    return {
        "schema": SCHEMA, "task": "NEURAL-063", "exposure_condition": condition,
        "demonstration_ids": list(demonstration_ids),
        "query_views_sha256": {"T": digest(timing), "N": digest(neural)},
        "demonstration_views_sha256": None if not demonstration_ids else {
            "T": digest(fit_timing), "N": digest(fit_neural)},
        "events": len(t), "query_mice": 19,
        "requests": requests,
    }


def collect(bundle, responses, *, expected_bundle_sha256):
    """Collect a trusted build() result into original scorer prediction lists.

    The SHA is supplied by the operator from the pre-response delivery artifact.
    No responses are scored and there is no partial-success return.
    """
    if digest(bundle) != expected_bundle_sha256 or bundle.get("schema") != SCHEMA:
        raise ContractError("precommitted request bundle digest/schema mismatch")
    requests = bundle["requests"]
    if not isinstance(responses, list) or len(responses) != len(requests):
        raise ContractError("one response for every paired request required")
    predictions = {"T": [], "N": []}
    expected_ids = {"T": [], "N": []}
    for request, response in zip(requests, responses):
        if not isinstance(response, dict) or set(response) != {
                "request_sha256", "id", "information", "values"}:
            raise ContractError("exact direct response fields required")
        for key in ("request_sha256", "id", "information"):
            if response[key] != request[key]:
                raise ContractError("response is out of order or bound to a different request")
        info = request["information"]
        expected_ids[info].append(request["id"])
        predictions[info].append({"id": response["id"], "values": response["values"]})
    for info in ("T", "N"):
        admit_predictions(predictions[info], expected_ids[info])
    if expected_ids["T"] != expected_ids["N"] or len(expected_ids["T"]) != bundle["events"]:
        raise ContractError("incomplete paired event support")
    return {"schema": "neural063_direct_predictions_v1", "task": "NEURAL-063",
            "mode": "direct_numeric", "exposure_condition": bundle["exposure_condition"],
            "request_bundle_sha256": expected_bundle_sha256,
            "response_sha256": digest(responses), "events": bundle["events"],
            "predictions": _copy(predictions)}


def read_json(path):
    return decode(Path(path).read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("build", "collect"))
    parser.add_argument("--timing", required=True)
    parser.add_argument("--neural", required=True)
    parser.add_argument("--fit-timing")
    parser.add_argument("--fit-neural")
    parser.add_argument("--demonstration-ids")
    parser.add_argument("--responses")
    parser.add_argument("--requests-sha256")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.operation == "build" and (args.responses or args.requests_sha256):
        parser.error("response inputs are only valid for collect")
    if args.operation == "collect" and not (args.responses and args.requests_sha256):
        parser.error("collect requires --responses and --requests-sha256")
    demo_flags = (args.fit_timing, args.fit_neural, args.demonstration_ids)
    if any(demo_flags) and not all(demo_flags):
        parser.error("demonstrations require both FIT views and an explicit ID-list file")
    demonstration_ids = read_json(args.demonstration_ids) if args.demonstration_ids else ()
    if args.demonstration_ids and (not isinstance(demonstration_ids, list) or not demonstration_ids):
        parser.error("demonstration ID list must be nonempty before FIT views may be read")
    bundle = build(read_json(args.timing), read_json(args.neural),
                   fit_timing=read_json(args.fit_timing) if args.fit_timing else None,
                   fit_neural=read_json(args.fit_neural) if args.fit_neural else None,
                   demonstration_ids=demonstration_ids)
    value = bundle if args.operation == "build" else collect(
        bundle, read_json(args.responses), expected_bundle_sha256=args.requests_sha256)
    # Exclusive creation protects a frozen delivery/response artifact from overwrite.
    with Path(args.output).open("xb") as stream:
        stream.write(canonical(value))
    print(digest(value))


if __name__ == "__main__":
    main()
