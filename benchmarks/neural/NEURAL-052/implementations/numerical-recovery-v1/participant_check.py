"""Public-only report preflight; no responses, reference analysis or candidate code.

The caller supplies the INPUTS.json SHA-256 delivered by the operator. Only that
manifest, its pinned features JSON, and submitted result/METHODS are captured.
This authenticates the schema identity; it does not qualify the complete packet
or establish correctness of any submitted estimate or prose interpretation.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re

from interface import Invalid, capture_regular, decode_json, write_json_fresh
from report_contract import SUBJECTS, build_schema, validate_report

HASH = re.compile(r"[0-9a-f]{64}\Z")
# Frozen schema identity, copied from the unchanged data_io.DESIGN_PIN.
DESIGN_PIN = {"bytes": 773647, "sha256": "3e4e7fec421ab57c61e19b66859f0434b314357de5c44dcf2957f6a5057108ec"}


def _require(condition, message):
    if not condition:
        raise Invalid(message)


def _pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def public_identity(input_dir, manifest_sha256):
    """Recover only the identity needed by the unchanged full-report contract."""
    _require(type(manifest_sha256) is str and HASH.fullmatch(manifest_sha256) is not None,
             "operator-provided INPUTS.json SHA-256 required")
    root = Path(input_dir)
    raw = capture_regular(root / "INPUTS.json", cap=1_000_000)
    _require(hashlib.sha256(raw).hexdigest() == manifest_sha256, "public manifest SHA-256 differs")
    manifest = decode_json(raw, cap=1_000_000)
    _require(type(manifest) is dict and manifest.get("schema") == "neural052_inputs_v1"
             and manifest.get("task_id") == "NEURAL-052" and manifest.get("design") == DESIGN_PIN,
             "public manifest contract identity differs")
    subjects = manifest.get("subjects")
    _require(type(subjects) is list and len(subjects) == 3
             and all(type(s) is dict for s in subjects)
             and [s.get("subject_id") for s in subjects] == list(SUBJECTS),
             "complete ordered three-person manifest required")
    desc = manifest.get("features")
    _require(type(desc) is dict and type(desc.get("file")) is str
             and desc["file"] not in ("", ".", "..")
             and "/" not in desc["file"] and "\\" not in desc["file"]
             and type(desc.get("bytes")) is int and 0 < desc["bytes"] <= 1_000_000
             and type(desc.get("sha256")) is str and HASH.fullmatch(desc["sha256"]) is not None,
             "bounded single-member feature descriptor required")
    features_raw = capture_regular(root / desc["file"], cap=1_000_000)
    _require(_pin(features_raw) == {k: desc[k] for k in ("bytes", "sha256")},
             "public feature identity differs")
    features = decode_json(features_raw, cap=1_000_000)
    _require(type(features) is dict and set(features) == {"feature_names", "concept_features"},
             "public feature fields differ")
    names, concepts = features["feature_names"], features["concept_features"]
    _require(type(names) is list and len(names) == 15
             and all(type(n) is str and n for n in names) and len(set(names)) == 15
             and names == manifest.get("feature_names"), "ordered image-feature identity differs")
    _require(type(concepts) is dict and len(concepts) == 100
             and all(type(c) is str and c and "\0" not in c for c in concepts),
             "complete 100-concept identity required")
    # Property scalars, voxel arrays and output estimates do not define schema.
    design = {"feature_names": names, "concept_features": {c: {} for c in concepts},
              "subjects": [{"subject_id": s} for s in SUBJECTS]}
    return design, {"INPUTS.json": _pin(raw), desc["file"]: _pin(features_raw)}


def check_submission(input_dir, manifest_sha256, submission, methods):
    design, identity = public_identity(input_dir, manifest_sha256)
    result_raw = capture_regular(submission, cap=4_000_000)
    result = decode_json(result_raw, cap=4_000_000)
    validate_report(result, design)
    _require(result["input_manifest_sha256"] == manifest_sha256,
             "submission refers to a different input manifest")
    methods_raw = capture_regular(methods, cap=1_048_576)
    try:
        _require(bool(methods_raw.decode("utf-8").strip()), "METHODS.md must contain nonempty UTF-8 prose")
    except UnicodeError as exc:
        raise Invalid("METHODS.md must contain nonempty UTF-8 prose") from exc
    return {"status": "valid_structure", "task_id": "NEURAL-052",
            "public_schema_identity": identity,
            "submission": _pin(result_raw), "methods": _pin(methods_raw),
            "complete_report_contract": True, "numerical_correctness_checked": False,
            "interpretation_quality_scored": False, "response_arrays_read": False,
            "scientific_qualification": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("schema", "check"))
    parser.add_argument("--input-dir", type=Path, required=True,
                        help="Public input directory containing INPUTS.json and features JSON")
    parser.add_argument("--manifest-sha256", required=True,
                        help="INPUTS.json digest independently supplied by the operator")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--submission", type=Path)
    parser.add_argument("--methods", type=Path)
    args = parser.parse_args(argv)
    if args.output.exists() or args.output.is_symlink():
        parser.error("output must be fresh")
    if args.command == "check" and (args.submission is None or args.methods is None):
        parser.error("check requires both --submission and --methods")
    try:
        if args.command == "schema":
            design, _ = public_identity(args.input_dir, args.manifest_sha256)
            result = build_schema(design)
        else:
            result = check_submission(args.input_dir, args.manifest_sha256, args.submission, args.methods)
    except (Invalid, ValueError) as exc:
        result = {"status": "preflight_rejected", "reason": str(exc),
                  "numerical_correctness_checked": False, "scientific_qualification": False}
    write_json_fresh(args.output, result, cap=4_000_000)
    return 2 if result.get("status") == "preflight_rejected" else 0


if __name__ == "__main__":
    raise SystemExit(main())
