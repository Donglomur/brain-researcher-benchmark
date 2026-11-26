#!/usr/bin/env python3
"""Bind author Volume TSVs and saved splits without loading neural arrays."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath

TASK = "PAPER-paper-method-replacement-006"
REVISION = "d237755bbdea123c60bface0cecbb48bab6f42de"
PROFILE = "original-volume-binding-v1"
TRIALS = {"sub_1": "trial001", "sub_2": "trial006", "sub_3": "trial000",
          "sub_4": "trial000", "sub_6": "trial004", "sub_7": "trial000", "sub_10": "trial000"}
COUNTS = (1, 10, 20, 30, 40, 50, 90)
CLEAN_SHA256 = "6490851f35355a1b4283b77cd14cc4317b8bd6f38357260785c1b79cd3ab22f5"


class BindingError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise BindingError(message)


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def canonical_sha(value):
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    raw = Path(path).read_bytes()
    return json.loads(raw, object_pairs_hook=_pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(BindingError("nonfinite JSON"))), digest(raw)


def read_tsv(path, columns):
    raw = Path(path).read_bytes()
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8"), newline=""), delimiter="\t", quotechar='"'))
    require(rows and all(len(row) == columns for row in rows), f"expected exactly {columns} TSV columns")
    return rows, digest(raw)


def channel_list(value, name):
    require(isinstance(value, list) and value and
            all(isinstance(x, str) and x.strip() for x in value), f"invalid {name}")
    require(len(set(value)) == len(value), f"duplicate {name}")
    return value


def bind_splits(n_rows, saved):
    """Retain every saved index and its order; never regenerate random splits."""
    require(isinstance(saved, dict) and set(saved) == {"train", "val", "test"}, "saved split keys must be train/val/test")
    held = math.ceil(n_rows * 0.2)
    expected = {"train": n_rows - held, "val": held - math.ceil(held * 0.5), "test": math.ceil(held * 0.5)}
    seen = set()
    for split, indices in saved.items():
        require(isinstance(indices, list) and len(indices) == expected[split], "saved split sizes differ from full .8/.1/.1 recipe")
        require(all(type(i) is int and 0 <= i < n_rows for i in indices), "invalid saved row index")
        require(len(set(indices)) == len(indices) and not seen.intersection(indices), "duplicate or overlapping saved indices")
        seen.update(indices)
    require(seen == set(range(n_rows)), "saved splits omit source rows")
    return {split: list(saved[split]) for split in ("train", "val", "test")}


def bind_subject(subject, inputs, clean_channels):
    require(subject in TRIALS and isinstance(inputs, dict), "invalid downstream subject")
    manifest, manifest_sha = read_tsv(inputs["manifest_tsv"], 2)
    labels, labels_sha = read_tsv(inputs["labels_tsv"], 2)
    require(len(manifest) == len(labels), "manifest/label lengths differ; author zip would silently truncate")
    rows, seen = [], set()
    for index, ((feature, declared_subject), (label, onset)) in enumerate(zip(manifest, labels)):
        require(declared_subject == subject, "manifest mixes subjects")
        parts = PurePosixPath(feature).parts
        require("\\" not in feature and ".." not in parts and len(parts) >= 3, "invalid source feature path")
        require(parts[-3:-1] == (subject, TRIALS[subject]), "manifest feature has wrong subject/trial")
        name = parts[-1]
        require(name.endswith(".npy") and name[:-4].isdigit() and str(int(name[:-4])) == name[:-4], "unexpected author feature filename")
        row_id = "/".join(parts[-3:])
        require(row_id not in seen, "duplicate source feature identity")
        seen.add(row_id)
        require(label in ("False", "True"), "Volume label must be author Boolean text")
        try:
            seconds = float(onset)
        except ValueError as exc:
            raise BindingError("invalid word-onset seconds") from exc
        require(math.isfinite(seconds) and seconds >= 0, "invalid word-onset seconds")
        rows.append({"manifest_index": index, "row_id": row_id, "label_high_rms": int(label == "True"),
                     "word_onset_s": seconds})
    # Feature ordinal is assigned after quartile selection. It is not a transcript word index.
    require({int(row["row_id"].split("/")[-1][:-4]) for row in rows} == set(range(len(rows))),
            "feature ordinals omit part of the subject manifest")
    saved, split_sha = read_json(inputs["splits_json"])
    splits = bind_splits(len(rows), saved)
    for name, indices in splits.items():
        require({rows[i]["label_high_rms"] for i in indices} == {0, 1}, f"{name} lacks a retained RMS class")
    ordered, ordered_sha = read_json(inputs["ordered_electrodes_json"])
    require(isinstance(ordered, dict) and subject in ordered, "missing feature-channel order")
    feature_order = channel_list(ordered[subject], "feature-channel order")
    clean_channels = channel_list(clean_channels, "clean-channel list")
    require(set(feature_order).issubset(clean_channels), "feature channel outside pinned clean Laplacian source")
    require(len(feature_order) >= 90, "Table 1 needs at least 90 clean feature channels")
    selections = inputs["selection_files"]
    require(isinstance(selections, dict) and set(selections) == {str(c) for c in COUNTS}, "all Figure 3 counts and 90-electrode primary required")
    ensembles = {}
    for count in COUNTS:
        selection, selection_sha = read_json(selections[str(count)])
        require(isinstance(selection, dict) and subject in selection, "selection lacks subject")
        selected = channel_list(selection[subject], "selected channels")
        require(len(selected) == count and set(selected).issubset(feature_order), "wrong channel count or membership")
        # Native loader filters membership but keeps original feature-column order.
        indices = [i for i, channel in enumerate(feature_order) if channel in selected]
        ensembles[str(count)] = {"channels": [feature_order[i] for i in indices], "feature_indices": indices,
                                 "selection_file_sha256": selection_sha}
    return {"subject": subject, "trial": TRIALS[subject], "rows": rows, "splits": splits,
            "feature_channel_order": feature_order, "ensembles": ensembles,
            "source_files": {"manifest_sha256": manifest_sha, "labels_sha256": labels_sha,
                             "splits_sha256": split_sha, "ordered_electrodes_sha256": ordered_sha}}


def prepare(plan):
    """Operator-only metadata binding of the complete seven-subject source panel."""
    require(isinstance(plan, dict) and plan.get("source_revision") == REVISION, "wrong source revision")
    require(plan.get("endpoint") == "rms", "only original Volume endpoint is supported")
    require(isinstance(plan.get("subjects"), dict) and set(plan["subjects"]) == set(TRIALS), "complete original seven-subject panel required")
    clean, clean_sha = read_json(plan["clean_laplacian_json"])
    require(clean_sha == CLEAN_SHA256, "clean Laplacian source content pin mismatch")
    subjects = {subject: bind_subject(subject, plan["subjects"][subject], clean[subject]) for subject in TRIALS}
    result = {"task_id": TASK, "profile": PROFILE, "source_revision": REVISION, "endpoint": "rms",
              "clean_laplacian_sha256": clean_sha, "subjects": subjects,
              "scope": "operator_metadata_binding_not_authentication_of_historical_artifacts",
              "word_onset_is_neural_support": False}
    result["binding_sha256"] = canonical_sha(result)
    return result


def validate_binding(binding):
    require(isinstance(binding, dict) and binding.get("profile") == PROFILE, "wrong binding profile")
    body = dict(binding)
    wanted = body.pop("binding_sha256", None)
    require(canonical_sha(body) == wanted, "binding content changed")
    require(binding.get("task_id") == TASK and binding.get("source_revision") == REVISION and
            binding.get("endpoint") == "rms" and binding.get("clean_laplacian_sha256") == CLEAN_SHA256,
            "wrong binding identity")
    subjects = binding.get("subjects")
    require(isinstance(subjects, dict) and set(subjects) == set(TRIALS), "incomplete binding cohort")
    require(binding.get("word_onset_is_neural_support") is False, "word onset cannot be relabeled as neural support")
    for subject, data in subjects.items():
        require(data.get("subject") == subject and data.get("trial") == TRIALS[subject], "binding subject/trial differs")
        rows = data.get("rows")
        require(isinstance(rows, list) and rows, "binding rows missing")
        wanted_ids = {f"{subject}/{TRIALS[subject]}/{i}.npy" for i in range(len(rows))}
        require({r.get("row_id") for r in rows} == wanted_ids, "binding row identities differ")
        for index, row in enumerate(rows):
            require(type(row.get("manifest_index")) is int and row["manifest_index"] == index and
                    type(row.get("label_high_rms")) is int and row["label_high_rms"] in (0, 1), "invalid bound row")
            onset = row.get("word_onset_s")
            require(type(onset) in (int, float) and math.isfinite(onset) and onset >= 0, "invalid bound onset")
        splits = bind_splits(len(rows), data["splits"])
        require(all({rows[i]["label_high_rms"] for i in indices} == {0, 1} for indices in splits.values()), "bound split lacks a retained class")
        order = channel_list(data.get("feature_channel_order"), "bound feature order")
        require(len(order) >= 90 and set(data["ensembles"]) == {str(c) for c in COUNTS}, "bound electrode panel incomplete")
        for count in COUNTS:
            ensemble = data["ensembles"][str(count)]
            indices = ensemble.get("feature_indices")
            require(isinstance(indices, list) and len(indices) == count and
                    all(type(i) is int and 0 <= i < len(order) for i in indices) and
                    indices == sorted(set(indices)), "invalid bound feature indices")
            require(ensemble.get("channels") == [order[i] for i in indices], "bound feature order differs")


def bind_native(binding, native):
    """Attach native arrays to saved test order using an explicit per-run class map.

    The full original electrode grid is mandatory. This is one method's output;
    paired reproduction/improvement and comparator admission are separate work.
    Scores stay in native class-1 orientation to avoid floating-point inversion.
    """
    validate_binding(binding)
    require(isinstance(native, dict) and native.get("binding_sha256") == binding["binding_sha256"], "native binding hash mismatch")
    wanted = {f"{subject}/{count}" for subject in TRIALS for count in COUNTS}
    runs = native.get("runs")
    require(isinstance(runs, dict) and set(runs) == wanted, "native outputs must cover all 49 subject/count runs")
    records = []
    for subject in TRIALS:
        data = binding["subjects"][subject]
        for count in COUNTS:
            run = runs[f"{subject}/{count}"]
            mapping = run.get("label2idx")
            require(isinstance(mapping, dict) and set(mapping) == {"False", "True"} and
                    all(type(v) is int for v in mapping.values()) and set(mapping.values()) == {0, 1}, "explicit native Boolean class map required")
            require(run.get("channels") == data["ensembles"][str(count)]["channels"], "native channel membership/order differs")
            indices = data["splits"]["test"]
            actual_indices = run.get("manifest_indices")
            require(isinstance(actual_indices, list) and all(type(i) is int for i in actual_indices) and
                    actual_indices == indices, "native output order differs from saved test order")
            probabilities, labels = run.get("predicts"), run.get("labels")
            require(isinstance(probabilities, list) and isinstance(labels, list) and
                    len(probabilities) == len(labels) == len(indices), "native arrays omit or add test rows")
            for index, probability, label in zip(indices, probabilities, labels):
                truth = data["rows"][index]
                expected = mapping["True" if truth["label_high_rms"] else "False"]
                require(type(label) is int and label == expected, "native label does not match saved source row")
                require(type(probability) in (int, float) and math.isfinite(probability) and 0 <= probability <= 1, "invalid native probability")
                records.append({"row_id": truth["row_id"], "subject": subject, "electrode_count": count,
                                "probability_native_index1": probability, "native_high_rms_index": mapping["True"]})
    return {"profile": PROFILE, "binding_sha256": binding["binding_sha256"],
            "native_content_sha256": canonical_sha(native), "predictions": records,
            "scope": "identity_bound_native_outputs_not_scientific_reproduction_or_improvement"}


def bind_pair(binding, pairing, author, candidate):
    """Validate one operator-selected matched run pair on all original cells.

    The pairing must be independently frozen by the operator before final access.
    Digests bind declarations; they prove neither freeze timing nor model origin.
    Each export wraps the unchanged one-method native format.
    """
    def fields(value, expected, name):
        require(type(value) is dict and set(value) == set(expected), name + ": exact fields required")

    def text(value, name):
        require(type(value) is str and bool(value.strip()), name + ": nonempty string required")

    def sha(value, name):
        require(type(value) is str and len(value) == 64 and
                all(c in "0123456789abcdef" for c in value), name + ": SHA-256 required")

    validate_binding(binding)
    fields(pairing, {"schema", "binding_sha256", "protocol_sha256", "author_comparator",
                     "methods", "runs"}, "operator pairing")
    require(pairing["schema"] == "original-volume-pairing/v1", "wrong operator pairing schema")
    require(pairing["binding_sha256"] == binding["binding_sha256"], "operator pairing binding differs")
    sha(pairing["protocol_sha256"], "operator protocol")
    require(pairing["author_comparator"] == "pretrained_popt_brainbert",
            "author role requires the declared pretrained PopT+BrainBERT comparator")
    fields(pairing["methods"], {"author", "candidate"}, "operator methods")
    for role, method in pairing["methods"].items():
        fields(method, {"method_id", "implementation_sha256"}, role + " method")
        text(method["method_id"], role + " method_id")
        sha(method["implementation_sha256"], role + " implementation")
    require(pairing["methods"]["author"]["method_id"] != pairing["methods"]["candidate"]["method_id"],
            "author/candidate method IDs must differ")
    wanted = {f"{subject}/{count}" for subject in TRIALS for count in COUNTS}
    fields(pairing["runs"], wanted, "operator run panel")
    pair_ids, run_ids = set(), set()
    for cell, row in pairing["runs"].items():
        fields(row, {"pair_id", "seed", "run_ids"}, "operator run " + cell)
        text(row["pair_id"], "pair_id")
        require(row["pair_id"] not in pair_ids, "duplicate pair_id")
        pair_ids.add(row["pair_id"])
        require(type(row["seed"]) is int and row["seed"] >= 0, "declared matched seed must be nonnegative integer")
        fields(row["run_ids"], {"author", "candidate"}, "operator run IDs")
        for run_id in row["run_ids"].values():
            text(run_id, "run_id")
            require(run_id not in run_ids, "duplicate run_id")
            run_ids.add(run_id)
    pairing_sha = canonical_sha(pairing)
    exports = {"author": author, "candidate": candidate}
    for role, export in exports.items():
        fields(export, {"schema", "pairing_sha256", "protocol_sha256", "role", "method_id",
                        "implementation_sha256", "run_provenance", "native"}, role + " export")
        require(export["schema"] == "original-volume-paired-export/v1", "wrong paired export schema")
        require(export["pairing_sha256"] == pairing_sha and
                export["protocol_sha256"] == pairing["protocol_sha256"], "export pairing/protocol differs")
        require(export["role"] == role, "export role differs from operator argument")
        require(all(export[key] == pairing["methods"][role][key]
                    for key in ("method_id", "implementation_sha256")), "export method differs from operator role")
        fields(export["run_provenance"], wanted, role + " run provenance")
        for cell, row in export["run_provenance"].items():
            fields(row, {"pair_id", "seed", "run_id"}, role + " run " + cell)
            expected = pairing["runs"][cell]
            require(type(row["seed"]) is int and row == {
                "pair_id": expected["pair_id"], "seed": expected["seed"],
                "run_id": expected["run_ids"][role]}, "export matched run declaration differs")
    # Validate both complete native supports before any numeric comparison.
    bound = {role: bind_native(binding, export["native"]) for role, export in exports.items()}
    return {"pairing_sha256": pairing_sha, "binding_sha256": binding["binding_sha256"],
            "protocol_sha256": pairing["protocol_sha256"],
            "export_sha256": {role: canonical_sha(export) for role, export in exports.items()},
            "native_content_sha256": {role: row["native_content_sha256"] for role, row in bound.items()},
            "scope": "declared_matched_pair_not_freeze_or_model_authentication"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("plan")
    p.add_argument("output")
    p = sub.add_parser("bind-native")
    p.add_argument("binding")
    p.add_argument("native")
    p.add_argument("output")
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(read_json(args.plan)[0])
    else:
        result = bind_native(read_json(args.binding)[0], read_json(args.native)[0])
    Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
