#!/usr/bin/env python3
"""Bind all reviewed neural definitions while preserving exact original bytes."""
import argparse
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("neural_understanding", ROOT / "src/neurobench/neural_understanding.py")
engine = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(engine)
build_outputs = engine.build_outputs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--check", action="store_true", help="Report absent/stale generated files without writing")
    operation.add_argument("--write", action="store_true", help="Write deterministic current/history/contract files")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        outputs = build_outputs(root)
        changed = [path for path, body in outputs.items() if not (root / path).is_file() or (root / path).read_bytes() != body]
        if args.check:
            if changed:
                for path in changed:
                    print("Stale neural binding: " + path.as_posix(), file=sys.stderr)
                return 1
            print("Neural definitions and preserved history are current; no execution qualification implied.")
            return 0
        for path in changed:
            destination = root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(outputs[path])
        print(f"Wrote {len(changed)} neural definition/history/contract files; registry binding remains a separate step.")
        return 0
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
