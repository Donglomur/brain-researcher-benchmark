"""Package an operator's existing NEURAL-048 behavior predictions before scoring.

This command neither fits nor qualifies a behavior decoder. Its canonical JSON
digest must be retained independently before candidate access or outcomes.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import tempfile


_spec = importlib.util.spec_from_file_location(
    "neural048_frozen_scorer", Path(__file__).resolve().with_name("scorer.py"))
scorer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scorer)


def write_new_comparator(path, comparator):
    """Publish one complete private file without replacing an existing path."""
    path = Path(path)
    payload = (json.dumps(comparator, indent=2, sort_keys=True,
                          allow_nan=False) + "\n").encode("utf-8")
    # A same-directory temporary file is fully written before exclusive link
    # creation. Existing files and symlinks, including broken links, are refused.
    # mkstemp creates mode0600 independently of a permissive process umask.
    fd, temporary = tempfile.mkstemp(prefix=".neural048-freeze-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", help="operator-only reference JSON")
    parser.add_argument("predictions", help="complete list of {id, behavior} probabilities")
    parser.add_argument("receipt", help="original five-field operator receipt JSON")
    parser.add_argument("--execution-manifest-sha256", required=True,
                        help="digest of separately retained operator fitting evidence")
    parser.add_argument("--output", required=True,
                        help="new private comparator path; existing paths are refused")
    args = parser.parse_args()
    try:
        comparator = scorer.freeze_behavior(
            scorer.legacy._load(args.reference), scorer.legacy._load(args.predictions),
            scorer.legacy._load(args.receipt), args.execution_manifest_sha256)
        canonical_pin = scorer.digest(comparator)
        write_new_comparator(args.output, comparator)
    except (scorer.ContractError, OSError, KeyError, TypeError, ValueError) as exc:
        parser.exit(2, f"NEURAL-048 behavior freeze rejected: {exc}\n")
    print(json.dumps({"comparator_sha256": canonical_pin,
                      "digest_kind": "canonical_json_scorer_digest"}, sort_keys=True))


if __name__ == "__main__":
    main()
