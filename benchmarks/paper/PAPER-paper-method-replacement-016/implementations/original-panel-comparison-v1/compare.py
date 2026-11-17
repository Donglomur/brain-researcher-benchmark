"""Descriptive comparison on the original BOLDMoments panel; never a win test.

Consumes signed per-participant RSA already produced by the scientific runtime.
It does not extract features, recompute RSA, authenticate observations, or choose
an across-ROI superiority/uncertainty rule. See README.md for the input boundary.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

TASK = "PAPER-paper-method-replacement-016"
PROTOCOL_SHA256 = "59a43129bda8f20c4de74f1022609d09c3d7b8f1db275cc6b7df05057c7e9d1c"
MAX_INPUT_BYTES = 64 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(document):
    raw = json.dumps(document, allow_nan=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key: " + key)
        result[key] = value
    return result


def read_json(path, expected_sha256=None):
    with Path(path).open("rb") as handle:
        raw = handle.read(MAX_INPUT_BYTES + 1)
    require(len(raw) <= MAX_INPUT_BYTES, "input exceeds 64 MiB")
    if expected_sha256 is not None:
        require(hashlib.sha256(raw).hexdigest() == expected_sha256,
                "frozen source protocol identity mismatch")
    def reject(value):
        raise ValueError("nonfinite JSON constant: " + value)
    return json.loads(raw, object_pairs_hook=_object, parse_constant=reject)


def source_axes(protocol_path):
    """Read only the already-held, pinned public source metadata, never targets."""
    protocol = read_json(protocol_path, PROTOCOL_SHA256)
    models = protocol["models"]
    ids = [model["id"] for model in models]
    main92 = [m["id"] for m in models
              if m["type"] in ("image-in1k", "image-k400", "video-k400")]
    train51 = [m["id"] for m in models
               if m["type"] in ("image-in1k", "image-k400")]
    rois = [roi for group in protocol["roi_groups"].values() for roi in group]
    require(len(ids) == len(set(ids)) == 99 and len(main92) == 92
            and len(train51) == 51, "source 99/92/51 model memberships")
    require(len(rois) == len(set(rois)) == 17, "source 17 ROI identities")
    conditions = [("test:pca:" + model, "main") for model in ids]
    conditions += [("test:" + method + ":" + model, "figure16")
                   for method in ("srp", "none") for model in main92]
    conditions += [("train:pca:" + model, "figure17") for model in train51]
    conditions += [("test:pca:videomae_B_pretrainONLY", "figure18")]
    return {"subjects": protocol["subjects"], "stimuli": protocol["stimuli"],
            "repetitions": protocol["test_repetitions"], "rois": rois,
            "models": ids, "conditions": conditions}


def _sha(value):
    return (type(value) is str and len(value) == 64
            and all(c in "0123456789abcdef" for c in value))


def _layers(names):
    require(type(names) is list and len(names) > 0
            and all(type(x) is str and x for x in names)
            and len(names) == len(set(names)), "unique complete declared layers")


def select(layers, values):
    """Original rule: first maximum of signed ten-subject layer means.

    A missing statistic anywhere prevents selection over a convenient subset.
    Returning all original values makes undefined coverage and selection visible.
    """
    _layers(layers)
    require(type(values) is list and len(values) == len(layers), "full layer axis")
    for row in values:
        require(type(row) is list and len(row) == 10, "all ten participant values")
        require(all(v is None or (type(v) in (int, float)
                    and math.isfinite(v) and -1 <= v <= 1) for v in row),
                "signed finite RSA in [-1,1], or explicit null")
    means = [None if None in row else sum(row) / 10 for row in values]
    index = None if None in means else max(range(len(means)), key=means.__getitem__)
    return {"layers": layers, "subject_values": values, "layer_means": means,
            "selected_index": index,
            "selected_layer": None if index is None else layers[index],
            "score": None if index is None else means[index],
            "selected_subject_values": None if index is None else values[index]}


def compare(protocol_path, reference, candidate):
    """Compare one new representation against every original model per ROI.

    Reference uses all 335 source conditions, including controls. Candidate layer
    identities may differ. Input identities and hashes are declarations to bind,
    not evidence that feature/brain processing or freezing actually occurred.
    """
    axes = source_axes(protocol_path)
    require(reference["schema"] == "hundred_models_original_reference_v1",
            "reference input schema")
    require(candidate["schema"] == "hundred_models_original_candidate_v1",
            "candidate input schema")
    for document in (reference, candidate):
        support = document["test_support"]
        require(set(support) == {"subjects", "stimuli", "repetitions",
                                 "brain_rdms_sha256", "video_inputs_sha256"},
                "exact original-panel support fields")
        require(all(support[k] == axes[k] for k in ("subjects", "stimuli", "repetitions")),
                "original ten people / 102 ordered videos / ten repetitions")
        require(type(support["repetitions"]) is int, "integer repetition count")
        require(_sha(support["brain_rdms_sha256"]) and _sha(support["video_inputs_sha256"]),
                "explicit shared observation identity declarations")
        require(_sha(document["run_sha256"]), "explicit full run record digest")
    require(reference["test_support"] == candidate["test_support"],
            "candidate and reference must share original observations")
    require(_sha(candidate["freeze_sha256"]), "candidate freeze record digest")
    require(reference["origin"] in ("published_author_outputs", "reproduced_author_outputs"),
            "published and rerun reference origins remain distinct")
    train = reference["train_support"]
    require(set(train) == {"subjects", "stimuli", "repetitions", "brain_rdms_sha256",
                           "video_inputs_sha256"}, "explicit separate Figure 17 support")
    require(train["subjects"] == axes["subjects"] and type(train["repetitions"]) is int
            and train["repetitions"] == 3, "Figure 17 ten participants / three repetitions")
    require(type(train["stimuli"]) is list and len(train["stimuli"]) == 1000
            and all(type(x) is str and x for x in train["stimuli"])
            and len(set(train["stimuli"])) == 1000
            and not set(train["stimuli"]).intersection(axes["stimuli"]),
            "independently supplied 1000 training-video identities; no test substitution")
    require(_sha(train["brain_rdms_sha256"]) and _sha(train["video_inputs_sha256"]),
            "separate training observation identity declarations")
    ceilings = reference["noise_ceilings"]
    require(type(ceilings) is dict and set(ceilings) == {"test", "train"},
            "both original-panel noise ceiling profiles")
    for rows in ceilings.values():
        require([row["roi"] for row in rows] == axes["rois"], "all 17 noise ceiling ROIs")
        for row in rows:
            require(set(row) == {"roi", "lower", "upper"}, "noise ceiling fields")
            require(all(v is None or (type(v) in (int, float)
                        and math.isfinite(v) and -1 <= v <= 1)
                        for v in (row["lower"], row["upper"])),
                    "signed finite noise ceilings or explicit null")

    conditions = [condition for condition, _ in axes["conditions"]]
    catalog = reference["layer_catalog"]
    require(type(catalog) is dict and set(catalog) == set(conditions),
            "all 335 declared reference condition layer catalogs")
    for layers in catalog.values():
        _layers(layers)
    for condition in conditions:
        model = condition.split(":", 2)[2]
        if model in axes["models"]:
            require(catalog[condition] == catalog["test:pca:" + model],
                    "same source model layer catalog across companion conditions")
    # Representation layer identity cannot depend on which ROI is being scored.
    _layers(candidate["layers"])
    expected = [(condition, roi) for condition in conditions for roi in axes["rois"]]
    require([(row["condition"], row["roi"]) for row in reference["rsa"]] == expected,
            "complete ordered 335-condition by 17-ROI reference")
    require([row["roi"] for row in candidate["rsa"]] == axes["rois"],
            "all 17 candidate ROIs in original order")
    source = {}
    summaries = []
    roles = dict(axes["conditions"])
    for row in reference["rsa"]:
        require(row["layers"] == catalog[row["condition"]],
                "reference score layers match complete declared catalog")
        result = select(row["layers"], row["values"])
        source[(row["condition"], row["roi"])] = result
        summaries.append({"condition": row["condition"], "roi": row["roi"],
                          "role": roles[row["condition"]], **result})
    proposed = {}
    for row in candidate["rsa"]:
        require(row["layers"] == candidate["layers"], "all declared candidate layers")
        proposed[row["roi"]] = select(row["layers"], row["values"])

    comparisons = []
    profiles = []
    for roi in axes["rois"]:
        new = proposed[roi]
        originals = [source[("test:pca:" + model, roi)] for model in axes["models"]]
        defined = all(row["score"] is not None for row in originals)
        strongest = (max(range(99), key=lambda i: originals[i]["score"])
                     if defined else None)
        for model, old in zip(axes["models"], originals):
            available = new["score"] is not None and old["score"] is not None
            comparisons.append({"roi": roi, "reference_model": model,
                                "delta": new["score"] - old["score"] if available else None,
                                "selected_participant_deltas":
                                [a-b for a, b in zip(new["selected_subject_values"],
                                                    old["selected_subject_values"])]
                                if available else None})
        old = None if strongest is None else originals[strongest]["score"]
        profiles.append({"roi": roi, "candidate": new,
                         "strongest_reference_model": None if strongest is None else axes["models"][strongest],
                         "strongest_reference_score": old,
                         "delta_to_strongest": None if old is None or new["score"] is None
                         else new["score"] - old})
    return {"schema": "hundred_models_original_panel_comparison_v1", "task_id": TASK,
            "status": "descriptive_comparison_only", "protocol_sha256": PROTOCOL_SHA256,
            "reference_sha256": digest(reference), "candidate_sha256": digest(candidate),
            "reference_origin": reference["origin"], "test_support": reference["test_support"],
            "train_support": train, "noise_ceilings": ceilings,
            "reference_conditions": summaries, "per_reference_comparisons": comparisons,
            "roi_profile": profiles,
            "counts": {"main_models": 99, "all_source_conditions": 335,
                       "rois": 17, "participants": 10, "stimuli": 102,
                       "reference_rows": 5695, "candidate_reference_deltas": 1683},
            "inference": {"independent_units": "participants; shared stimuli and correlated layers/ROIs",
                          "participant_deltas": "descriptive after whole-cohort layer selection; not independent confirmatory estimates",
                          "interval": None, "across_roi_decision": None, "paper_win": None},
            "qualification": {"input_authenticity": False, "historical_parity": False,
                              "candidate_freeze_verified": False, "scientific_improvement": False}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = compare(args.protocol, read_json(args.reference), read_json(args.candidate))
    # Exclusive output creation protects previous results from accidental replacement.
    with Path(args.output).open("x", encoding="utf-8") as handle:
        json.dump(result, handle, allow_nan=False, separators=(",", ":"))
        handle.write("\n")


if __name__ == "__main__":
    main()
