"""Explicit external-packet entry points for the recovered NEURAL-052 source.

No default data search, candidate execution, reduced panel, or fitted-result
cache. Authentic reference/score calls require a separately scheduled native
execution; generated tests replace their input/computation boundaries.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from interface import Invalid, capture_regular, decode_json, write_json_fresh


def _design(packet_root):
    from data_io import DESIGN_PIN, checked_bytes, safe_path

    body = checked_bytes(safe_path(packet_root, "private/DESIGN.json"), DESIGN_PIN)
    return decode_json(body)


def reference(packet_root):
    """Recompute the complete frozen investigation, then validate its report."""
    from data_io import load_packet
    from encoding_core import analyze
    from report_contract import validate_report

    design = _design(packet_root)
    subjects, features, manifest_sha = load_packet(packet_root)
    report = {"task_id": "NEURAL-052", "input_manifest_sha256": manifest_sha,
              "analysis": analyze(subjects, features, draws=1000, strict=True)}
    validate_report(report, design)
    return report


def score(packet_root, submission, methods):
    """Require both participant artifacts; grade numerical reconstruction only."""
    from grade import grade_submission

    try:
        body = capture_regular(methods, cap=1_048_576)
        if not body.decode("utf-8").strip():
            raise Invalid("METHODS.md must contain nonempty UTF-8 prose")
    except (Invalid, UnicodeError) as exc:
        return {"status": "invalid_submission", "reason": str(exc),
                "primary_error": None, "full_reconstruction": False}
    result = grade_submission(submission, Path(packet_root))
    result["methods"] = {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
                         "interpretation_quality_scored": False}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("schema", "reference", "score"):
        command = subparsers.add_parser(name)
        command.add_argument("--packet-root", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        if name == "score":
            command.add_argument("--submission", type=Path, required=True)
            command.add_argument("--methods", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists() or args.output.is_symlink():
        parser.error("output must be fresh")
    if args.command == "schema":
        from report_contract import build_schema
        result = build_schema(_design(args.packet_root))
        cap = 4_000_000
    elif args.command == "reference":
        result = reference(args.packet_root)
        cap = 4_000_000
    else:
        try:
            result = score(args.packet_root, args.submission, args.methods)
        except Exception as exc:
            result = {"status": "operator_error", "reason": type(exc).__name__,
                      "primary_error": None, "full_reconstruction": False}
        cap = 262_144
    write_json_fresh(args.output, result, cap=cap)
    return 0 if args.command != "score" or result["status"] == "scored" else 2


if __name__ == "__main__":
    raise SystemExit(main())
