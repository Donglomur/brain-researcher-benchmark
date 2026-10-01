"""Generate grader-only v2 evidence after an independently reviewed genuine oracle run."""
import argparse
import json
from pathlib import Path
import numpy as np
p = argparse.ArgumentParser()
p.add_argument("--oracle-output", required=True, type=Path)
p.add_argument("--reference-output", required=True, type=Path)
p.add_argument("--source-receipt", required=True, type=Path)
args = p.parse_args()
receipt = json.loads(args.source_receipt.read_text())
assert receipt.get("source_sha256_by_path"), "independently verified source hashes required"
out = args.oracle_output
ids = json.loads((out / "subject_ids.json").read_text())
assert len(ids) == len(set(ids)) == 20
report = json.loads((out / "robustness.json").read_text())
import csv
networks = [r["network"] for r in csv.DictReader((out / "group_gradient.csv").open())]
payload = {"schema_version": "gradient-config-v2", "ref_ids": np.asarray(ids),
           "ref_aligned": np.load(out / "gradients_aligned.npy", allow_pickle=False),
           "ref_networks": np.asarray(networks), "ref_config_metadata": json.dumps(report["configs"]),
           "source_receipt": json.dumps(receipt)}
for conf in report["configs"]:
    payload["config_" + conf["config"]] = np.load(out / conf["gradient_path"], allow_pickle=False)
assert not args.reference_output.exists(), "refuse to overwrite existing reference"
np.savez_compressed(args.reference_output, **payload)
