"""Operator-only primary scorer; every input/output may contain protected data."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import SupportError, score_panel


def strict_json(path, remaining):
    with open(path, "rb") as stream:
        body = stream.read(remaining + 1)
    if len(body) > remaining:
        raise ValueError("aggregate_input_byte_limit")
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result
    def invalid_constant(_):
        raise ValueError("nonfinite_json_constant")
    return json.loads(body, object_pairs_hook=object_pairs, parse_constant=invalid_constant), body


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--methods", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-input-bytes", type=int, required=True)
    parser.add_argument("--max-output-bytes", type=int, required=True)
    args = parser.parse_args(argv)
    if min(args.max_input_bytes, args.max_output_bytes) <= 0:
        parser.error("positive explicit byte ceilings required")
    try:
        remaining = args.max_input_bytes
        values, pins = [], []
        for path in (args.prepared, args.predictions, args.methods):
            value, body = strict_json(path, remaining)
            values.append(value)
            pins.append({"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()})
            remaining -= len(body)
        result = score_panel(values[0], values[1], expected_methods=values[2])
        result["prepared_support_integrity"] = {
            "implementation": "NEURAL-059/prepared-support-v2", "primary_only": True,
            "recording_byte_authentication": False, "input_pins_in_order": pins,
            "input_roles": ["protected_preparation", "captured_predictions", "prequery_methods"],
        }
        # Assemble only up to the selected ceiling; never leave a partial score.
        output = bytearray()
        for piece in json.JSONEncoder(sort_keys=True, separators=(",", ":"), allow_nan=False).iterencode(result):
            chunk = piece.encode()
            if len(output) + len(chunk) + 1 > args.max_output_bytes:
                raise ValueError("output_byte_limit")
            output.extend(chunk)
        output.extend(b"\n")
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(output)
        except BaseException:
            args.output.unlink(missing_ok=True)
            raise
        print(json.dumps({"status": "source_only_unqualified", "bytes": len(output),
                          "sha256": hashlib.sha256(output).hexdigest()}))
        return 0
    except SupportError as error:
        print(json.dumps({"error": error.code, "session_index": error.session_index,
                          "ordinal": error.ordinal}), file=sys.stderr)
        return 2
    except (ValueError, TypeError, KeyError, OverflowError, OSError) as error:
        # Avoid reflecting file paths, protected values or OS error strings.
        print(json.dumps({"error": "invalid_operand_or_output", "type": type(error).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
