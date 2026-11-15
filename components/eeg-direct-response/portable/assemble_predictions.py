"""Collect a complete public response panel; no private scoring or model calls."""
from pathlib import Path
import argparse
import json
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from response_contract import complete


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--responses", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    if a.out.suffix != ".npz":
        raise ValueError("An explicit .npz destination is required")
    if a.responses.is_symlink() or a.responses.stat().st_size > 400 * 4096:
        raise ValueError("Bounded complete responses required")
    manifest = json.loads(a.manifest.read_text())
    ids = manifest["development_ids"]
    rows = a.responses.read_bytes().splitlines()
    values = complete(rows, ids)
    import numpy as np

    # A file handle prevents NumPy's implicit suffix from selecting another path.
    # Exclusive creation also rejects an existing file or final-path symlink.
    # The caller supplies a trusted parent directory; this is not a filesystem sandbox.
    with a.out.open("xb") as output:
        np.savez(output, trial_ids=np.asarray(ids, dtype="<U48"),
                 target_probability=np.asarray(values, dtype=np.float64))
        output.flush()
        os.fsync(output.fileno())
    print(json.dumps({"status": "public_complete_submission_assembled", "rows": 400,
                      "private_target_reads": 0, "scoring_performed": False}))


if __name__ == "__main__":
    main()
