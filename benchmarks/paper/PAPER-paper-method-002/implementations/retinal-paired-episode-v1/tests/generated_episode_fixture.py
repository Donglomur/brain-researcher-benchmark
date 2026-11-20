"""PRIVATE generated engineering declarations; never scientific run evidence.

No import of production code, files, arrays, model libraries or actual data.
Descriptors deliberately refer to synthetic declared materials; the production
validator must keep them execution-unqualified. Controls independently mutate
these declarations and exercise the real view-copy and assessment interfaces.
"""

import copy
import hashlib
import json

COMMIT = "5e7a86282adb9d4603b5546ac5d8dad59aec7cc0"
ACCESS = "whole cropped traces/all ROI delay selection before downstream split"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def artifact(name):
    return {"logical_name": "generated/" + name, "bytes": 1,
            "sha256": hashlib.sha256(("SYNTHETIC DECLARATION ONLY:" + name).encode()).hexdigest()}


def array(name, shape, dtype):
    result = artifact(name)
    size = 1
    for n in shape:
        size *= n
    result.update(shape=shape, dtype=dtype, bytes=size * (1 if dtype == "|u1" else 8))
    return result


def generated_episode(operator, author, candidate):
    """Return metadata joined to the separately generated strict-scorer operands."""
    sites = copy.deepcopy(operator["sites"])
    splits = copy.deepcopy(operator["splits"])
    identity = digest({"sites": sites, "splits": splits})
    access = {"schema": "jaxley-retinal-validation-access-v2", "mode": "targets-visible-to-both",
              "approval": artifact("validation-approval-not-authority"),
              "author_validation_checkpoints": 21, "candidate_validation_query_limit": None}
    config = {"profile": "published-code-5e7a862-retina-v1", "manifest": "generated/raw-manifest",
              "choices": {"raw_join": "explicit-keyed-pairs-no-positional-parity",
                          "site_aggregation": "recompute-author-branch-bin-mean", "contour_profile": "paper-0.6",
                          "output_scale": 40.0, "soma_radius": 5.0,
                          "training_budget": "source-iterations-rounded-to-complete-epochs",
                          "evaluation_checkpoint_epoch": 21, "rfest_profile": "fa18170-full20-tolerance20",
                          "baseline_dtype": "author-inferred-dtypes",
                          "experimental_rf": "reestimate-from-averaged-labels-prospective", "jax_platform": "cpu"},
              "training": {"iterations": 1000, "batch_size": 256, "lr": .01, "momentum": .5, "beta": .99,
                           "reduce_every": 350, "reduce_by": 10, "val_frac": .2, "test_num": 128,
                           "eval_every": 100, "seed_weights": 0, "seed_membrane": 0, "seed_tf_loader": 0,
                           "seed_tf_loop": 0, "seed_ruler": 0}}
    programme = {"author_code_commit": COMMIT, "source_snapshot": artifact("author-source-code"),
                 "configuration": config, "configuration_sha256": digest(config), "runtime": artifact("runtime"),
                 "selection": {"metric": "validation_mean_pearson", "rule": "maximum", "tie_break": "first",
                               "author_validation_checkpoints": 21}}
    views = {}
    for condition, information in (("A", "paper+data"), ("B", "paper+data+code")):
        view = {"schema": "jaxley-retinal-candidate-manifest-v2", "cell_id": "20161028_1",
                "information_condition": information, "identity_sha256": identity,
                "site_keys": [[s["field"], s["branch"], s["bin"]] for s in sites],
                "preprocessing_access": ACCESS, "validation_access_sha256": digest(access), "splits": {}}
        for name in ("train", "val", "test"):
            n = len(splits[name])
            row = {"row_ids": list(splits[name]), "images": array(name + "-images", [n, 15, 20], "|u1"),
                   "currents": array(name + "-currents", [n, 1], "<f8"),
                   "mask": array(name + "-mask", [n, 147], "<f8")}
            if name in ("train", "val"):
                row["targets"] = array(name + "-targets", [n, 147], "<f8")
            view["splits"][name] = row
        views[condition] = {"view": view, "paper": artifact("paper"), "morphology": artifact("morphology"),
                            "author_code": None if condition == "A" else
                            {"commit": COMMIT, "artifact": copy.deepcopy(programme["source_snapshot"])},
                            "additional_materials": []}
    operator_descriptor = artifact("operator-packet")
    operator_descriptor["sha256"] = digest(operator)
    return {"schema": "jaxley-paired-retinal-episode-v2", "episode_id": "generated-software-control-episode",
            "evaluated_condition": "A", "cell_id": "20161028_1", "sites": sites, "splits": splits,
            "identity_sha256": identity,
            "preprocessing": {"access": ACCESS, "whole_record_trace_preprocessing": True,
                              "all_roi_delay_selection_before_split": True, "repeated_stimulus_across_fields": True,
                              "clean_train_only_preprocessing": False, "provenance": None},
            "validation_access": access,
            "participant_budget": {"wall_seconds": 60, "cpu_threads": 1, "ram_bytes": 536870912, "write_bytes": 1048576},
            "reference_programme": programme, "conditions": views,
            "private_materials": {"observed_test_calcium": artifact("observed-test-calcium"),
                                  "full_private_binding": artifact("full-private-binding"),
                                  "operator_packet": operator_descriptor},
            "scored_packet_sha256": {"operator": digest(operator), "author": digest(author), "candidate": digest(candidate)},
            "execution_provenance": {"reference": None, "A": None, "B": None}}


def generated_provenance(episode, role):
    """Internally joined synthetic receipts still cannot authenticate any run."""
    if role not in ("reference", "A", "B"):
        raise ValueError("generated provenance role")
    context = {key: episode[key] for key in ("episode_id", "identity_sha256", "preprocessing", "validation_access",
                                            "participant_budget", "reference_programme")}
    context_sha = digest(context)
    output_key = "author" if role == "reference" else "candidate"
    return {"schema": "jaxley-retinal-run-provenance-v1", "run_id": "generated-run-" + role, "role": role,
            "episode_id": episode["episode_id"], "identity_sha256": episode["identity_sha256"],
            "context_sha256": context_sha,
            "material_manifest_sha256": context_sha if role == "reference" else digest(episode["conditions"][role]),
            "source_snapshot": copy.deepcopy(episode["reference_programme"]["source_snapshot"]) if role == "reference"
                               else artifact(role + "-candidate-source"),
            "selected_checkpoint": artifact(role + "-validation-selected-checkpoint"),
            "selected_validation_event_id": "generated-validation-event-21-" + role,
            "validation_selection_receipt": artifact(role + "-selection-receipt"),
            "output_packet_sha256": episode["scored_packet_sha256"][output_key],
            "events": artifact(role + "-event-log"), "closure": artifact(role + "-closure"),
            "transport_receipt": artifact(role + "-unverified-transport-receipt")}
