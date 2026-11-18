"""Training-only unconditional sequence control for NEURAL-013.

This control emits the modal complete training phoneme sequence for every query.
It reads neither neural arrays nor query labels and is not a neural reference.
"""
import argparse
from collections import Counter
import hashlib
from pathlib import Path

from core import HEX, canonical, digest, need, normalize_tokens, public_queries, validate_submission
from safe_io import parse_json, read_bytes, read_json, write_json

METHOD = "modal_complete_training_phoneme_sequence_lexicographic_ties_v1"
MODEL_SCHEMA = "neural013-unconditional-sequence-prior-v1"
MODEL_FIELDS = {
    "schema", "method", "packet_id", "training_labels_sha256", "training_cases",
    "unique_training_sequences", "chosen_training_count", "tokens",
    "training_case_ids_sha256", "training_sequence_counts_sha256", "model_id",
}


def fit_prior(public, labels_body):
    """Bind the complete allowed-label file, then fit on train roles only.

    Development labels are validated as part of the supplied packet but never
    enter frequency counts, tie breaking or model selection. No trial duration
    or feature descriptor enters the prior.
    """
    public_queries(public)
    pin = public["training_labels"]
    need(type(labels_body) is bytes and len(labels_body) == pin["bytes"] and
         hashlib.sha256(labels_body).hexdigest() == pin["sha256"],
         "allowed-label file does not match public descriptor")
    labels = parse_json(labels_body)
    need(type(labels) is dict and set(labels) == {"schema", "labels"} and
         labels["schema"] == "neural013-training-labels-v1", "allowed-label schema")
    allowed = {r["case_id"]: r["role"] for r in public["cases"] if r["role"] != "query"}
    rows = labels["labels"]
    need(type(rows) is list and len(rows) == len(allowed), "complete nonquery label support")
    seen, training_ids, counts = set(), [], Counter()
    for row in rows:
        need(type(row) is dict and set(row) == {"case_id", "tokens"}, "label row fields")
        key = row["case_id"]
        need(type(key) is str and key in allowed and key not in seen,
             "duplicate, query or unknown label ID")
        seen.add(key)
        sequence = tuple(normalize_tokens(row["tokens"]))
        need(sequence, "empty source label sequence")
        if allowed[key] == "train":
            counts[sequence] += 1
            training_ids.append(key)
    need(seen == set(allowed) and training_ids, "complete labels and nonempty training support")
    chosen = min(counts, key=lambda seq: (-counts[seq], seq))
    model = {
        "schema": MODEL_SCHEMA, "method": METHOD, "packet_id": public["packet_id"],
        "training_labels_sha256": pin["sha256"], "training_cases": len(training_ids),
        "unique_training_sequences": len(counts), "chosen_training_count": counts[chosen],
        "tokens": list(chosen), "training_case_ids_sha256": digest(sorted(training_ids)),
        "training_sequence_counts_sha256": digest([
            {"tokens": list(seq), "count": counts[seq]} for seq in sorted(counts)]),
    }
    model["model_id"] = digest(model)
    return model


def predict_prior(public, model, expected_model_id):
    """Emit every query using an externally frozen model identity.

    The expected identity must be recorded after fit and before query execution.
    A hash does not establish how the fit was executed or provide OS isolation.
    """
    queries = public_queries(public)
    need(type(model) is dict and set(model) == MODEL_FIELDS, "exact prior model fields")
    need(type(expected_model_id) is str and HEX.fullmatch(expected_model_id), "frozen model ID")
    need(model["schema"] == MODEL_SCHEMA and model["method"] == METHOD and
         model["packet_id"] == public["packet_id"] and
         model["training_labels_sha256"] == public["training_labels"]["sha256"],
         "model/packet provenance join")
    need(model["model_id"] == expected_model_id and
         digest({k: v for k, v in model.items() if k != "model_id"}) == expected_model_id,
         "model changed since the externally frozen fit")
    training_ids = sorted(r["case_id"] for r in public["cases"] if r["role"] == "train")
    need(model["training_case_ids_sha256"] == digest(training_ids), "training case support changed")
    for key in ("training_cases", "unique_training_sequences", "chosen_training_count"):
        need(type(model[key]) is int and 0 < model[key] <= len(training_ids), "model count bounds")
    need(model["training_cases"] == len(training_ids), "model training count")
    need(type(model["training_sequence_counts_sha256"]) is str and
         HEX.fullmatch(model["training_sequence_counts_sha256"]), "training counts fingerprint")
    tokens = normalize_tokens(model["tokens"])
    need(tokens and tokens == model["tokens"], "canonical nonempty frozen sequence")
    submission = {
        "schema": "neural013-predictions-v1", "packet_id": public["packet_id"],
        "predictions": [{"case_id": key, "tokens": tokens.copy()} for key in sorted(queries)],
    }
    validate_submission(public, submission)
    return submission


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("fit", "predict"):
        command = sub.add_parser(action)
        command.add_argument("--public", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        if action == "fit":
            command.add_argument("--labels", type=Path, required=True)
        else:
            command.add_argument("--model", type=Path, required=True)
            command.add_argument("--expected-model-id", required=True)
    args = parser.parse_args(argv)
    public = read_json(args.public)
    # Validate public support before opening any other operand.
    public_queries(public)
    if args.action == "fit":
        result = fit_prior(public, read_bytes(args.labels, 64000000))
    else:
        result = predict_prior(public, read_json(args.model, 65536), args.expected_model_id)
    write_json(args.output, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
