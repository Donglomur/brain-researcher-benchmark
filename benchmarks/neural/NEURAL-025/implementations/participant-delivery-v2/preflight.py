#!/usr/bin/env python3
"""Validate a complete participant response without private evaluation inputs."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

_SOURCE = Path(__file__).with_name("delivery.py")
_DELIVERY_SHA256 = "86f647695a3ee38ee87a613ae4bd1e9bd7e19758a2cf3650c7601d76330c8bda"
if hashlib.sha256(_SOURCE.read_bytes()).hexdigest() != _DELIVERY_SHA256:
    raise ValueError("Participant delivery source identity mismatch")
_SPEC = importlib.util.spec_from_file_location("neural025_public_preflight_delivery", _SOURCE)
d = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(d)


def preflight(response: dict, packet: dict, *, expected_packet_sha256: str,
              expected_mode: str, expected_program_sha256: str | None = None) -> dict:
    """Public-input validation receipt; neither an evaluation score nor sandbox proof."""
    predictions = d.validate_response(response, packet,
                                      expected_packet_sha256=expected_packet_sha256,
                                      expected_mode=expected_mode,
                                      expected_program_sha256=expected_program_sha256)
    return {"schema": "calcium_response_preflight_v1", "task_id": d.p.TASK_ID,
            "status": "valid_complete_public_response", "mode": expected_mode,
            "packet_sha256": expected_packet_sha256,
            "response_sha256": d.p.digest(response),
            "target_field": packet["target_field"], "target_units": packet["target_units"],
            "sessions": len(predictions),
            "query_trials": sum(len(rows) for rows in predictions.values()),
            "timepoints_per_trial": len(packet["time_ms"]),
            "joints_per_timepoint": len(packet["joint_names"]),
            "private_index_checked": False, "scientific_score_computed": False,
            "process_isolation_verified": False, "scientific_qualification": False}


def _read(path: Path, limit: int) -> dict:
    with path.open("rb") as stream:
        body = d.p._read_bounded(stream, limit)
    document = json.loads(body, object_pairs_hook=d.p._unique_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(d.p.Refusal("Nonfinite JSON")))
    d.p.require(isinstance(document, dict), "Input must be a JSON object")
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--response", required=True, type=Path)
    parser.add_argument("--expected-packet-sha256", required=True)
    parser.add_argument("--mode", required=True, choices=d.MODES)
    parser.add_argument("--expected-program-sha256")
    parser.add_argument("--max-input-bytes", required=True, type=int,
                        help="Maximum bytes for each of the two input JSON files")
    parser.add_argument("--max-output-bytes", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        d.p.require(0 < args.max_input_bytes < sys.maxsize and
                    0 < args.max_output_bytes < sys.maxsize, "Byte budgets must be positive and bounded")
        packet = _read(args.packet, args.max_input_bytes)
        response = _read(args.response, args.max_input_bytes)
        result = preflight(response, packet, expected_packet_sha256=args.expected_packet_sha256,
                           expected_mode=args.mode, expected_program_sha256=args.expected_program_sha256)
        output = d.p.canonical_bytes(result) + b"\n"
        d.p.require(len(output) <= args.max_output_bytes, "Preflight receipt exceeds output budget")
        sys.stdout.buffer.write(output)
        return 0
    except (d.p.Refusal, OSError, ValueError, KeyError, TypeError, OverflowError, RecursionError) as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)[:1000]}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
