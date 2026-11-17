#!/usr/bin/env python3
"""Write invented full-domain construction inputs, never an authentic MEG packet."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def build():
    measures = ["invented-measure-%03d" % i for i in range(246)]
    people = ["invented-person-%d" % i for i in range(4)]
    source = digest({"kind": "invented_construction_input", "version": 1})
    rows, labels, expected = [], {}, []
    for person in people:
        for label, signal in (("negative", -2.0), ("positive", 2.0)):
            oid = person + ":" + label
            values = [0.0] * 246
            values[0] = signal
            rows.append({"id": oid, "participant": person, "endpoint": "invented-endpoint", "values": values})
            expected.append({"id": oid, "participant": person})
            labels[oid] = label
    protocol = {
        "schema": "meg_nested_protocol_v1", "task_id": "PAPER-paper-method-add-010",
        "purpose": "prospective_method_evaluation", "measure_ids": measures,
        "participants": people, "participant_aliases": {p: p for p in people},
        "endpoints": [{"id": "invented-endpoint", "classes": ["negative", "positive"],
                       "region_pair": ["invented-source", "invented-target"],
                       "task_relevance": "invented", "time_window": "invented"}],
        "expected_observations": {"invented-endpoint": expected},
        "outer_folds": [{"id": "fold-" + person, "test_participants": [person],
                         "inner_validation_participants": [[other] for other in people if other != person]}
                        for person in people],
        "estimator": {"family": "balanced_l1_logistic", "normalization": "training_standardization",
                      "C": [1.0], "seed": 127, "tol": 1e-8, "max_iter": 1000},
        "selection": {"metric": "participant_mean_balanced_accuracy", "tie": "measure_then_C_order",
                      "missing_features": "refuse", "constant_features": "balanced_intercept_only",
                      "nonconvergence": "refuse"},
        "source_policy": {"source_version": "generated", "source_manifest_sha256": source,
                          "measure_domain_sha256": digest(measures), "corrected_supplement_sha256": None},
        "execution_limits": {"max_fit_calls": 2956, "max_ledger_records": 3968,
                             "max_observations": 8}}
    data = {"schema": "meg_feature_table_v1", "measure_ids": measures,
            "sampling": "label_independent_observations", "source_manifest_sha256": source,
            "observations": rows}
    return protocol, data, labels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_directory")
    args = parser.parse_args()
    destination = Path(args.output_directory)
    destination.mkdir(parents=False, exist_ok=False)
    for name, value in zip(("protocol.json", "features.json", "labels.json"), build()):
        body = (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()
        with (destination / name).open("xb") as stream:
            stream.write(body)
        if name == "protocol.json":
            print(hashlib.sha256(body).hexdigest())


if __name__ == "__main__":
    main()
