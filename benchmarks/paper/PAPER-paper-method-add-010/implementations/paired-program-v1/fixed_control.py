"""Nonlearning construction control: P(object)=0.5 for every held query.

Use only an improvement-mode engineering campaign. This is not a paper baseline,
model evaluation, neural interpretation result, or reproduction feature claim.
"""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()
context = json.loads((Path(args.input) / "CONTEXT.json").read_text())
result = {"schema": "meg-paired-program-response/v1", "context_sha256": context["context_sha256"],
          "probabilities": {identifier: 0.5 for identifier in context["queries"]},
          "source_feature_values": None}
with Path(args.output).open("x") as handle:
    json.dump(result, handle, sort_keys=True, separators=(",", ":"), allow_nan=False)
