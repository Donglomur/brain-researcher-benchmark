#!/usr/bin/env python3
"""Reduce the original 25-person, three-model likelihood panel.

This ports the arithmetic in FreeEnergyEEG model_validation.ipynb cell 26.
It does not compute likelihoods, authenticate fits, or score paper improvement.
See SOURCE_PINS.json and README.md for the nonstandard BIC convention.
"""

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path


MODEL_PARAMETERS = {
    "active_inference": 5,
    "model_free_rl": 2,
    "model_based_rl": 3,
}
PARTICIPANTS = tuple(range(1, 26))
SOURCE_N = 6000
FIELDS = ("participant_id", "model", "log_likelihood")
INPUT_LIMIT = 65536


def reduce_panel(records):
    """Return the literal source cohort statistic for exactly all 75 fits.

    Input likelihoods are natural-log choice-probability sums for a whole
    original 120-trial participant block. Their provenance and correct
    computation must be established separately. There is no participant BIC
    in the source reduction, and no alternative sample size is substituted.
    """
    if type(records) is not list or len(records) != 75:
        raise ValueError("Exactly 75 participant/model records are required")
    panel = {}
    for row in records:
        if type(row) is not dict or set(row) != set(FIELDS):
            raise ValueError("Each row requires exactly participant_id, model, log_likelihood")
        participant, model, ll = (row[key] for key in FIELDS)
        if type(participant) is not int or participant not in PARTICIPANTS:
            raise ValueError("Participant IDs must be the integers 1 through 25")
        if type(model) is not str or model not in MODEL_PARAMETERS:
            raise ValueError("Unknown source model")
        if type(ll) not in (int, float):
            raise ValueError("Log likelihood must be a finite nonpositive real number")
        try:
            ll = float(ll)
        except (OverflowError, ValueError) as exc:
            raise ValueError("Log likelihood is outside the finite numeric range") from exc
        if not math.isfinite(ll) or ll > 0:
            raise ValueError("Log likelihood must be a finite nonpositive real number")
        key = (participant, model)
        if key in panel:
            raise ValueError("Duplicate participant/model record")
        panel[key] = ll
    expected = {(participant, model) for participant in PARTICIPANTS for model in MODEL_PARAMETERS}
    if set(panel) != expected:
        raise ValueError("The complete original 25-person, three-model panel is required")

    models = {}
    for model, k in MODEL_PARAMETERS.items():
        try:
            total = math.fsum(panel[(participant, model)] for participant in PARTICIPANTS)
            penalty = k * math.log(SOURCE_N)
            statistic = -2 * total + penalty
        except OverflowError as exc:
            raise ValueError("Aggregate exceeds the finite numeric range") from exc
        if not math.isfinite(statistic):
            raise ValueError("Aggregate exceeds the finite numeric range")
        models[model] = {
            "participant_count": 25,
            "sum_log_likelihood_nats": total,
            "source_parameter_penalty": penalty,
            "source_k": k,
            "literal_source_statistic": statistic,
        }

    return {
        "schema_version": "freeenergy-source-statistic/v1",
        "task_id": "PAPER-FIND-037",
        "scope": "source_arithmetic_only",
        "input_likelihoods_authenticated": False,
        "published_numeric_baseline_authenticated": False,
        "source_statistic_is_standard_bic": False,
        "formula": "-2 * sum_25_participants(log_likelihood) + k * ln(6000)",
        "source_n": SOURCE_N,
        "units": "dimensionless, using natural logarithms",
        "fit_count": 75,
        "models": models,
        "active_inference_minus_comparator": {
            model: models["active_inference"]["literal_source_statistic"]
            - models[model]["literal_source_statistic"]
            for model in ("model_free_rl", "model_based_rl")
        },
    }


def read_panel(body):
    """Parse the bounded CSV transport without dropping malformed rows."""
    if type(body) is not bytes or len(body) > INPUT_LIMIT:
        raise ValueError("CSV must be at most 65536 bytes")
    reader = csv.reader(io.StringIO(body.decode("utf-8")), strict=True)
    if next(reader, None) != list(FIELDS):
        raise ValueError("CSV header must be participant_id,model,log_likelihood")
    records = []
    for fields in reader:
        if len(fields) != 3 or len(records) >= 75:
            raise ValueError("CSV requires exactly three fields in each of 75 rows")
        participant, model, ll = fields
        if participant not in {str(value) for value in PARTICIPANTS}:
            raise ValueError("CSV participant IDs must be canonical integers 1 through 25")
        records.append({"participant_id": int(participant), "model": model, "log_likelihood": float(ll)})
    return records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Complete operator-exported likelihood CSV")
    parser.add_argument("--output", required=True, type=Path, help="New JSON result file; keep numerical results outside Git")
    args = parser.parse_args(argv)
    with args.input.open("rb") as stream:
        body = stream.read(INPUT_LIMIT + 1)
    result = reduce_panel(read_panel(body))
    result["input_sha256"] = hashlib.sha256(body).hexdigest()
    output = json.dumps(result, indent=2, allow_nan=False) + "\n"
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(output)


if __name__ == "__main__":
    main()
