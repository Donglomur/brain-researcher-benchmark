"""Explicit command routing; default inspection does not open study inputs."""
import argparse
import hashlib
import json
import os
from pathlib import Path

from .contract import load_contract
from .io import ContractError, capture, decode, ordinary


def inspect_source():
    contract = load_contract()
    root = Path(__file__).parent.parent
    needed = ["preparation/stages.py", "references/stages.py", "runtime/stages.py",
              "runtime/custody.py", "owner/stages.py", "owner/worker.py"]
    missing = [name for name in needed if not (root / name).is_file()]
    return {"schema": "neural063_source_inspection_v1", "stage_count": len(contract["nodes"]),
            "entry_predicates": contract["predicates"], "external_evidence_records": len(contract["external"]),
            "cohort": {"mice": 107, "sessions": 703, "experiments": 1936, "published_roi_rows": 133066},
            "split_mice": {"fit": 73, "validation": 15, "query": 19},
            "candidate_conditions": 8, "mandatory_narrative_jobs": 8,
            "reference_fit_roster": {"primary": 28, "independent": 2, "perturbation": 5},
            "missing_source_components": missing,
            "runtime_or_scientific_qualification": "not_established_by_source_inspection",
            "actual_raw_source_bytes": None, "actual_event_count": None,
            "reference_gain": None, "scientific_execution": False}


def _keys(path, expected_sha256):
    p = ordinary(path)
    st = p.stat()
    if st.st_uid != os.geteuid() or st.st_mode & 0o077:
        raise ContractError("operator issuer keyring must be privately owned")
    body = capture(p, 65536)
    if hashlib.sha256(body).hexdigest() != expected_sha256:
        raise ContractError("operator keyring differs from explicit invocation binding")
    obj = decode(body)
    if obj.get("schema") != "neural063_operator_keyring_v1" or not isinstance(obj.get("issuers"), dict):
        raise ContractError("exact separately provisioned operator issuer keyring required")
    result = {}
    for issuer, record in obj["issuers"].items():
        if not isinstance(issuer, str) or set(record) != {"key_hex"}:
            raise ContractError("invalid issuer key entry")
        try:
            key = bytes.fromhex(record["key_hex"])
        except (TypeError, ValueError):
            raise ContractError("invalid private key encoding") from None
        if len(key) < 32:
            raise ContractError("issuer key too short")
        result[issuer] = key
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="NEURAL-063 complete-source interface; inspection never executes a study")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect", help="inspect frozen source contract without data, model or backend access")
    sub.add_parser("interfaces", help="join exact source stage inputs/outputs without opening study inputs")
    draft = sub.add_parser("draft-stage", help="compile a nonexecuting draft from explicit exact predecessor descriptors")
    draft.add_argument("--construction", required=True)
    run = sub.add_parser("execute-stage", help="future operator execution with all exact external evidence")
    run.add_argument("--request", required=True)
    run.add_argument("--keyring", required=True)
    run.add_argument("--keyring-sha256", required=True)
    guardian = sub.add_parser("_cgroup-guardian", help=argparse.SUPPRESS)
    guardian.add_argument("--context", required=True)
    guardian.add_argument("--context-bytes", type=int, required=True)
    guardian.add_argument("--key-fd", type=int, required=True)
    guardian.add_argument("--live-fd", type=int, required=True)
    guardian.add_argument("--ready-fd", type=int, required=True)
    worker = sub.add_parser("_trusted-worker", help=argparse.SUPPRESS)
    worker.add_argument("--context", required=True)
    worker.add_argument("--context-sha256", required=True)
    worker.add_argument("--context-bytes", type=int, required=True)
    worker.add_argument("--key-fd", type=int, required=True)
    worker.add_argument("--result", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            result = inspect_source()
        elif args.command == "interfaces":
            from .constructor import interface_union
            result = interface_union()
        elif args.command == "draft-stage":
            from .constructor import interface_union, compile_request
            values = decode(capture(args.construction, 4_000_000))
            expected = {"stage", "attempt", "implementation", "completions", "external_inputs",
                        "parameters", "output_root", "issuers", "external_evidence", "attempt_expires_at"}
            if not isinstance(values, dict) or set(values) != expected:
                raise ContractError("exact construction fields required")
            result = compile_request(interfaces=interface_union(), **values)
        elif args.command == "execute-stage":
            from .workflow import run_stage
            from .worker import bounded_runner
            request = decode(capture(args.request, 4_000_000))
            result = run_stage(request, _keys(args.keyring, args.keyring_sha256), worker_runner=bounded_runner)
            print(json.dumps(result, allow_nan=False))
            return 1 if result["outcome"] == "failed" else 0
        elif args.command == "_cgroup-guardian":
            from .containment import guardian_main
            return guardian_main(args)
        else:
            from .worker import worker_main
            return worker_main(args)
        print(json.dumps(result, allow_nan=False))
        return 0
    except (ContractError, OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"admitted": False, "error_type": type(exc).__name__,
                          "reason": str(exc), "scientific_success": False}, allow_nan=False))
        return 1
