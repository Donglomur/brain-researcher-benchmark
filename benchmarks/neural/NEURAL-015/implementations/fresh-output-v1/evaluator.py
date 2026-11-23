"""NEURAL-015 CLI with fresh output; original scientific implementation unchanged."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import types

BASE = Path(__file__).resolve().parents[1] / "initial-evaluator-v1"
SOURCE_PINS = {
    "evaluator.py": (21047, "366dff43d2624a1cbdf7651a7f0ef00f0dad6cae01480e75d600a7c969096f2a"),
    "catalog.json": (3150, "31aab0168d2f6dcf2c230a6649320d03f53f415b726991eb8f12c02d3a800942"),
}


def load_evaluator():
    """Import checked predecessor bytes, preserving its scientific functions."""
    bodies = {}
    for name, (size, expected) in SOURCE_PINS.items():
        with (BASE / name).open("rb") as stream:
            raw = stream.read(size + 1)
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("preserved evaluator source mismatch: " + name)
        bodies[name] = raw
    module = types.ModuleType("neural015_original_evaluator")
    module.__file__ = str(BASE / "evaluator.py")
    exec(compile(bodies["evaluator.py"], module.__file__, "exec"), module.__dict__)
    if module.CATALOG != json.loads(bodies["catalog.json"]):
        raise ValueError("preserved evaluator catalog changed during import")
    return module


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("query", "score", "align", "validate"))
    parser.add_argument("input", help="private reference, or alignment JSON")
    parser.add_argument("--submission")
    parser.add_argument("--output", required=True, help="Fresh JSON output file")
    args = parser.parse_args(argv)
    try:
        output = Path(args.output)
        # Existing inputs, hard links, symlinks (including dangling links), and
        # prior reports all fail before operator input bodies are read.
        if output.exists() or output.is_symlink():
            raise ValueError("output must be a fresh file")
        base = load_evaluator()
        data = base.load_json(args.input)
        if args.command == "query":
            result = base.public_query(data)
        elif args.command == "validate":
            base.validate_reference(data)
            result = {"reference_sha256": base.digest(data), "valid_construction_contract": True,
                      "admitted": False, "holds": base.HOLDS}
        elif args.command == "align":
            base.exact(data, ["movie_times", "triggers", "max_clock_residual_samples"], "alignment input")
            result = base.align_onsets(**data)
        else:
            base.require(args.submission is not None, "score requires --submission")
            result = base.evaluate(data, base.load_json(args.submission))
        serialized = json.dumps(result, indent=2, allow_nan=False) + "\n"
        # Exclusive creation also rejects a file/link introduced after preflight.
        # Alignment targets and score diagnostics are operator-private. Do not
        # let a permissive caller umask make these new files group/world readable.
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(serialized)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"NEURAL-015 input rejected: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
