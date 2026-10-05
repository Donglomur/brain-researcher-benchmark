"""Build the held-out bank only from a retained real-data oracle execution.

Run in the pinned image. Both input checksums and source/score arithmetic are
validated before writing; independent preprocessing validation is a separate gate.
"""
import argparse
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from prediction_contract import validate_predictions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-output", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("/app/data"))
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.data_dir / "data_manifest.json").read_text())
    hashes = {}
    for record in manifest["files"]:
        path = args.data_dir / record["path"]
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        assert path.stat().st_size == record["size_bytes"] and digest == record["sha256"]
        hashes[record["path"]] = digest
    folds = validate_predictions(args.oracle_output, args.data_dir / "subj1/labels.txt",
                                 hashes["subj1/labels.txt"])
    result = json.loads((args.oracle_output / "decoding_results.json").read_text())
    metadata = json.loads((args.oracle_output / "run_metadata.json").read_text())
    assert metadata["pipeline_id"] == "runwise-clean-loro-v2"
    assert metadata["source_sha256"] == hashes
    with (args.oracle_output / "predictions.csv").open(newline="") as stream:
        rows = sorted(csv.DictReader(stream), key=lambda row: int(row["volume_id"]))
    # The bank retains full-precision counts, not the rounded public CSV scores.
    folds = {run: float(np.mean([row["predicted_label"] == row["true_label"] for row in rows
                               if int(row["held_out_run"]) == run])) for run in sorted(folds)}
    stats = {key: result[key] for key in ("n_samples", "n_voxels", "n_categories", "n_runs", "chance")}
    stats.update(pipeline_id=metadata["pipeline_id"], source_sha256=hashes,
                 loro_accuracy=float(np.mean(list(folds.values()))),
                 package_versions={name: importlib.metadata.version(name) for name in
                                   ("numpy", "scipy", "pandas", "nibabel", "nilearn", "scikit-learn")},
                 prediction_sha256=hashlib.sha256((args.oracle_output / "predictions.csv").read_bytes()).hexdigest())
    np.savez_compressed(args.destination,
                        ref_run_ids=np.array([str(run) for run in sorted(folds)]),
                        ref_fold_acc=np.array([folds[run] for run in sorted(folds)]),
                        ref_volume_ids=np.array([int(row["volume_id"]) for row in rows]),
                        ref_prediction_runs=np.array([int(row["held_out_run"]) for row in rows]),
                        ref_true_labels=np.array([row["true_label"] for row in rows]),
                        ref_predicted_labels=np.array([row["predicted_label"] for row in rows]),
                        ref_stats=np.array(json.dumps(stats, sort_keys=True)))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
