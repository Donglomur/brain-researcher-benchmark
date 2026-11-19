"""Constant probability engineering control, not a scientific comparator."""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()
context = json.loads((Path(args.input) / "CONTEXT.json").read_text())
if context.get("input_mode") != "generic_feature_classification_v1":
    raise ValueError("fixed Generic classification context required")
result = {"schema": "meg-generic-classification-response/v1",
          "input_mode": context["input_mode"], "context_sha256": context["context_sha256"],
          "probabilities": {identifier: 0.5 for identifier in context["queries"]}}
with open(args.output, "x") as stream:
    json.dump(result, stream, sort_keys=True, allow_nan=False)
