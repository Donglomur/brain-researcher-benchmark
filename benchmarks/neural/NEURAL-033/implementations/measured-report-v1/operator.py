"""Portable operator for the recovered NEURAL-033 activity-rank investigation.

Authenticates the complete historical public projection; does not execute a
participant program. Importing this module does not read observations or fit.
"""
import argparse
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "recovered"))
import analysis_core as core
import package_io as io
import score

VIEW = ("TASK.md", "CONTRACT.json", "identity.json", "observations.json",
        "submission.schema.json", "LICENSES.md")
EXTERNAL = frozenset(("identity.json", "observations.json", "submission.schema.json"))


def read_asset(name, source_input):
    """Data and identity-bearing schema come from the operator's directory."""
    if name not in VIEW:
        raise ValueError("Unknown public asset")
    manifest = io.strict_json(io.read_bytes(HERE / "SOURCE_INPUTS.json", 8192))
    records = [r for r in manifest["files"] if r["target"] == "public/" + name]
    if len(records) != 1:
        raise ValueError("Unique frozen asset record required")
    record = records[0]
    path = Path(source_input) / name if name in EXTERNAL else HERE / "protocol" / name
    body = io.read_bytes(path, record["bytes"])
    if io.pin(body) != {k: record[k] for k in ("bytes", "sha256")}:
        raise ValueError("Full-cohort asset identity differs: " + name)
    return body


def validate_source_join(rows, identity):
    """Recheck source identities before analysis, without deriving target values."""
    core.validate_rows(rows)
    if [r["row_id"] for r in rows] != identity["row_ids"]:
        raise ValueError("Ordered observation/identity row join differs")
    if sorted({r["mouse_id"] for r in rows}) != identity["mouse_ids"]:
        raise ValueError("Observation/identity mouse join differs")
    if len(rows) != 1936 or len(identity["mouse_ids"]) != 30:
        raise ValueError("Complete 1936-row/30-mouse source required")
    for treatment, nrows, nmice in (("control", 1143, 20), ("kir", 793, 10)):
        selected = [r for r in rows if r["treatment"] == treatment]
        if (len(selected), len({r["mouse_id"] for r in selected})) != (nrows, nmice):
            raise ValueError("Complete treatment source support required")


def prepare(source_input, output):
    """Export all six exact public files; do not compute a scientific answer."""
    captured = {name: read_asset(name, source_input) for name in VIEW}
    identity = io.strict_json(captured["identity.json"])
    if io.pin(captured["observations.json"])["sha256"] != identity["input_sha256"]:
        raise ValueError("Observation/identity digest differs")
    rows = io.strict_json(captured["observations.json"])["rows"]
    validate_source_join(rows, identity)
    output = Path(output).absolute()
    if any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError("No symbolic output path")
    output.mkdir(exist_ok=False)
    for name, body in captured.items():
        io.write_new(output / name, body)
    return {"task_id": "NEURAL-033", "status": "prepared_public_investigation",
            "files": {name: io.pin(body) for name, body in captured.items()},
            "input_rows": 1936, "input_mice": 30, "analysis_executed": False,
            "participant_mode_delivered": False}


def grade(source_input, submission):
    """Read measured outcomes only after full candidate structural admission."""
    try:
        contract = read_asset("CONTRACT.json", source_input)
        identity = io.strict_json(read_asset("identity.json", source_input))
        input_sha = identity["input_sha256"]
        contract_sha = io.pin(contract)["sha256"]
    except score.ERRORS as exc:
        return score.failure("operator_error", exc, False), 3

    def reference():
        body = read_asset("observations.json", source_input)
        if io.pin(body)["sha256"] != input_sha:
            raise ValueError("Observation/identity digest differs")
        rows = io.strict_json(body)["rows"]
        validate_source_join(rows, identity)
        return core.analyze(rows)

    try:
        body = io.read_bytes(submission, 2097152)
    except score.ERRORS as exc:
        return score.failure("invalid_submission", exc, False), 2
    return score.grade_bytes(body, identity, contract_sha, input_sha, reference)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "grade"):
        command = commands.add_parser(name)
        command.add_argument("--source-input", type=Path, required=True,
                             help="Operator directory containing pinned identity, observations and submission schema")
        command.add_argument("--output", type=Path, required=True)
        if name == "grade":
            command.add_argument("--submission", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        result = prepare(args.source_input, args.output)
        print(io.encode(result).decode(), end="")
        return 0
    if args.output.exists() or args.output.is_symlink():
        raise FileExistsError("Fresh score output required")
    result, code = grade(args.source_input, args.submission)
    io.write_new(args.output, io.encode(result))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
