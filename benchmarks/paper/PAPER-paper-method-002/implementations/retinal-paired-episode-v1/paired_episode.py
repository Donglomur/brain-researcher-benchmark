"""Portable, source-only paired retinal declarations and approved logical views.

No Python dictionary, material digest or caller-provided receipt is a sandbox.
This component binds no enforcing transport or trusted event verifier and never
returns execution qualification. It performs no file, network, model or scorer
execution. candidate_view_v2 is a future trusted release operation: never pass
its evaluator-private argument to participant code. Its NumPy import is local.
"""

import hashlib
import json
import math
import re

AUTHOR_COMMIT = "5e7a86282adb9d4603b5546ac5d8dad59aec7cc0"
INPUT_BINDING_SOURCE_SHA256 = "f4bd10b4c40cef74835001937ce3dc5cb4bd16fcc061b4138696b39827a707d9"
CELL_ID = "20161028_1"
PREPROCESSING_ACCESS = "whole cropped traces/all ROI delay selection before downstream split"
SPLIT_COUNTS = {"train": 12185, "val": 3047, "test": 128}
CONDITIONS = {"A": "paper+data", "B": "paper+data+code"}
TRANSPORT_VERIFIER = None
EVENT_PROVENANCE_VERIFIER = None
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/+-]{0,191}\Z")
_DTYPES = {"|u1": 1, "|i1": 1, "<i2": 2, "<i4": 4, "<i8": 8,
           "<u2": 2, "<u4": 4, "<u8": 8, "<f4": 4, "<f8": 8}


class EpisodeContractError(ValueError):
    """Bounded field/category diagnostics, never array or target values."""

    def __init__(self, code, path):
        self.code = str(code)[:96]
        self.path = str(path)[:192]
        super().__init__(self.code + " at " + self.path)


def _need(ok, code, path):
    if not ok:
        raise EpisodeContractError(code, path)


def _keys(value, keys, path):
    _need(type(value) is dict and set(value) == set(keys), "EXACT_KEYS_REQUIRED", path)


def _hash(value, path):
    _need(type(value) is str and _HEX.fullmatch(value) is not None, "SHA256_REQUIRED", path)
    return value


def _name(value, path):
    _need(type(value) is str and _NAME.fullmatch(value) is not None and
          not value.startswith("/") and ".." not in value.split("/"), "BOUNDED_LOGICAL_NAME_REQUIRED", path)
    return value


def canonical_sha256(value):
    """Same sorted compact JSON/no-LF convention as the frozen strict scorer."""
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError, OverflowError):
        raise EpisodeContractError("FINITE_JSON_REQUIRED", "canonical") from None
    _need(len(raw) <= 2097152, "BOUNDED_METADATA_REQUIRED", "canonical")
    return hashlib.sha256(raw).hexdigest()


def _artifact(value, path):
    _keys(value, ("logical_name", "bytes", "sha256"), path)
    _name(value["logical_name"], path + ".logical_name")
    _need(type(value["bytes"]) is int and 0 < value["bytes"] <= 2**40,
          "BOUNDED_ARTIFACT_EXTENT_REQUIRED", path + ".bytes")
    _hash(value["sha256"], path + ".sha256")
    return value


def _array(value, shape, path, *, float64=False):
    _keys(value, ("logical_name", "bytes", "sha256", "shape", "dtype"), path)
    _artifact({key: value[key] for key in ("logical_name", "bytes", "sha256")}, path)
    _need(type(value["shape"]) is list and value["shape"] == shape and
          all(type(n) is int and 0 < n <= 15360 for n in shape), "EXACT_ARRAY_SHAPE_REQUIRED", path)
    dtype = value["dtype"]
    _need(type(dtype) is str and dtype in _DTYPES and (not float64 or dtype == "<f8"),
          "EXACT_NUMERIC_DTYPE_REQUIRED", path + ".dtype")
    _need(value["bytes"] == math.prod(shape) * _DTYPES[dtype], "RAW_ARRAY_EXTENT_MISMATCH", path)
    return value


def _sites_and_splits(sites, splits):
    _need(type(sites) is list and len(sites) == 147, "COMPLETE_SITE_ROSTER_REQUIRED", "sites")
    keys, rois = [], []
    for i, site in enumerate(sites):
        path = "sites[" + str(i) + "]"
        _keys(site, ("field", "branch", "bin", "raw_roi_ids"), path)
        _need(type(site["field"]) is int and 1 <= site["field"] <= 15 and
              type(site["branch"]) is int and site["branch"] >= 0 and
              type(site["bin"]) is int and 0 <= site["bin"] <= 3, "SITE_COORDINATE_REQUIRED", path)
        _need(type(site["raw_roi_ids"]) is list and 0 < len(site["raw_roi_ids"]) <= 232 and
              all(type(x) is int and x > 0 for x in site["raw_roi_ids"]), "ROI_PROVENANCE_REQUIRED", path)
        keys.append((site["field"], site["branch"], site["bin"]))
        rois.extend((site["field"], x) for x in site["raw_roi_ids"])
    _need(keys == sorted(keys) and len(set(keys)) == 147 and
          {x[0] for x in keys} == set(range(1, 16)), "EXACT_ORDERED_SITE_IDENTITY_REQUIRED", "sites")
    _need(len(rois) == len(set(rois)) == 232, "COMPLETE_UNIQUE_ROI_PROVENANCE_REQUIRED", "sites")
    _keys(splits, SPLIT_COUNTS, "splits")
    all_rows = []
    for name, count in SPLIT_COUNTS.items():
        rows = splits[name]
        _need(type(rows) is list and len(rows) == count and
              all(type(x) is int and 0 <= x < 15360 for x in rows), "EXACT_SPLIT_EXTENT_REQUIRED", "splits." + name)
        all_rows.extend(rows)
    _need(sorted(all_rows) == list(range(15360)), "COMPLETE_DISJOINT_SPLITS_REQUIRED", "splits")
    return canonical_sha256({"sites": sites, "splits": splits})


def _validation_access(value):
    _keys(value, ("schema", "mode", "approval", "author_validation_checkpoints",
                  "candidate_validation_query_limit"), "validation_access")
    _need(value["schema"] == "jaxley-retinal-validation-access-v2" and
          value["mode"] == "targets-visible-to-both", "SHARED_VALIDATION_TARGET_ACCESS_REQUIRED", "validation_access")
    _artifact(value["approval"], "validation_access.approval")
    _need(type(value["author_validation_checkpoints"]) is int and value["author_validation_checkpoints"] == 21,
          "AUTHOR_SELECTION_CADENCE_REQUIRED", "validation_access.author_validation_checkpoints")
    _need(value["candidate_validation_query_limit"] is None, "VISIBLE_LABELS_DO_NOT_ENFORCE_QUERY_LIMIT", "validation_access.candidate_validation_query_limit")


def candidate_view_v2(private_binding, information_condition, *, validation_access):
    """Explicit v2 extension: detached TRAIN and VAL targets, never TEST targets.

    The prior v1 release withheld VAL targets. This new root-selected exposure
    changes that contract explicitly and equally for A/B; 21 author checks are
    not a candidate feedback-query limit. A descriptor of approval is a logical
    binding, not authentication or permission for an untrusted caller.
    """
    _validation_access(validation_access)
    _need(information_condition in CONDITIONS.values(), "INFORMATION_CONDITION_REQUIRED", "information_condition")
    _need(type(private_binding) is dict and private_binding.get("schema") == "jaxley-original-model-binding-v1",
          "PRIVATE_ORIGINAL_BINDING_REQUIRED", "private_binding")
    identity = _sites_and_splits(private_binding["sites"], private_binding["splits"])
    _need(private_binding["identity_sha256"] == identity, "INPUT_IDENTITY_MISMATCH", "private_binding.identity_sha256")
    _need(private_binding["preprocessing_access"] == PREPROCESSING_ACCESS,
          "WHOLE_RECORD_PREPROCESSING_DISCLOSURE_REQUIRED", "private_binding.preprocessing_access")
    import numpy as np
    for key in ("noise", "currents", "labels", "mask"):
        array = private_binding[key]
        _need(type(array) is np.ndarray and array.dtype.kind in "iuf", "NUMERIC_OWNED_ARRAY_REQUIRED", "private_binding." + key)
    _need(private_binding["noise"].shape == (15360, 15, 20), "IMAGE_SUPPORT_REQUIRED", "private_binding.noise")
    _need(private_binding["currents"].ndim == 2 and private_binding["currents"].shape[0] == 15360 and
          0 < private_binding["currents"].shape[1] <= 15360, "CURRENT_SUPPORT_REQUIRED", "private_binding.currents")
    for key in ("labels", "mask"):
        _need(private_binding[key].shape == (15360, 147) and private_binding[key].dtype == np.dtype("float64"),
              "SOURCE_FLOAT64_SITE_SUPPORT_REQUIRED", "private_binding." + key)
    out = {"schema": "jaxley-retinal-candidate-input-v2", "cell_id": CELL_ID,
           "information_condition": information_condition, "identity_sha256": identity,
           "site_keys": [[s["field"], s["branch"], s["bin"]] for s in private_binding["sites"]],
           "preprocessing_access": PREPROCESSING_ACCESS,
           "validation_access_sha256": canonical_sha256(validation_access), "splits": {}}
    for name in SPLIT_COUNTS:
        rows = np.asarray(private_binding["splits"][name], dtype=np.int64)
        view = {"row_ids": rows.copy(), "images": private_binding["noise"][rows].copy(),
                "currents": private_binding["currents"][rows].copy(),
                "mask": private_binding["mask"][rows].copy()}
        if name in ("train", "val"):
            view["targets"] = private_binding["labels"][rows].copy()
        out["splits"][name] = view
    return out


def _preprocessing(value):
    _keys(value, ("access", "whole_record_trace_preprocessing", "all_roi_delay_selection_before_split",
                  "repeated_stimulus_across_fields", "clean_train_only_preprocessing", "provenance"), "preprocessing")
    _need(value["access"] == PREPROCESSING_ACCESS and value["whole_record_trace_preprocessing"] is True and
          value["all_roi_delay_selection_before_split"] is True and value["repeated_stimulus_across_fields"] is True and
          value["clean_train_only_preprocessing"] is False, "SOURCE_PREPROCESSING_LIMITATIONS_REQUIRED", "preprocessing")
    if value["provenance"] is not None:
        _artifact(value["provenance"], "preprocessing.provenance")


def _budget(value):
    _keys(value, ("wall_seconds", "cpu_threads", "ram_bytes", "write_bytes"), "participant_budget")
    limits = {"wall_seconds": 604800, "cpu_threads": 4096, "ram_bytes": 2**50, "write_bytes": 2**50}
    _need(all(type(value[key]) is int and 0 < value[key] <= limit for key, limit in limits.items()),
          "BOUNDED_SHARED_PARTICIPANT_BUDGET_REQUIRED", "participant_budget")


def _programme(value):
    _keys(value, ("author_code_commit", "source_snapshot", "configuration", "configuration_sha256",
                  "runtime", "selection"), "reference_programme")
    _need(value["author_code_commit"] == AUTHOR_COMMIT, "EXACT_AUTHOR_COMMIT_REQUIRED", "reference_programme")
    _artifact(value["source_snapshot"], "reference_programme.source_snapshot")
    _artifact(value["runtime"], "reference_programme.runtime")
    cfg = value["configuration"]
    _keys(cfg, ("profile", "manifest", "choices", "training"), "reference_programme.configuration")
    _need(cfg["profile"] == "published-code-5e7a862-retina-v1", "SOURCE_PROGRAMME_PROFILE_REQUIRED", "reference_programme.configuration.profile")
    _name(cfg["manifest"], "reference_programme.configuration.manifest")
    choices = cfg["choices"]
    _keys(choices, ("raw_join", "site_aggregation", "contour_profile", "output_scale", "soma_radius", "training_budget",
                    "evaluation_checkpoint_epoch", "rfest_profile", "baseline_dtype", "experimental_rf", "jax_platform"), "reference_programme.configuration.choices")
    required = {"raw_join": "explicit-keyed-pairs-no-positional-parity", "site_aggregation": "recompute-author-branch-bin-mean",
                "training_budget": "source-iterations-rounded-to-complete-epochs", "experimental_rf": "reestimate-from-averaged-labels-prospective"}
    _need(all(choices[k] == v for k, v in required.items()), "SOURCE_PROGRAMME_CHOICE_REQUIRED", "reference_programme.configuration.choices")
    allowed = {"contour_profile": ("paper-0.6", "author-results-0.5", "author-assembly-0.4"), "output_scale": (40.0, 60.0),
               "soma_radius": (5.0, 7.5), "rfest_profile": ("fa18170-full20-tolerance20", "fa18170-max20-tolerance10"),
               "baseline_dtype": ("author-inferred-dtypes", "explicit-float64-adapter"), "jax_platform": ("cpu", "gpu")}
    _need(all(choices[k] in v for k, v in allowed.items()) and
          type(choices["evaluation_checkpoint_epoch"]) is int and choices["evaluation_checkpoint_epoch"] >= 0,
          "EXPLICIT_SOURCE_VARIANT_REQUIRED", "reference_programme.configuration.choices")
    training = cfg["training"]
    _keys(training, ("iterations", "batch_size", "lr", "momentum", "beta", "reduce_every", "reduce_by", "val_frac", "test_num",
                     "eval_every", "seed_weights", "seed_membrane", "seed_tf_loader", "seed_tf_loop", "seed_ruler"), "reference_programme.configuration.training")
    _need(all(type(training[k]) is int and 0 < training[k] <= 2**31 for k in
              ("iterations", "batch_size", "reduce_every", "reduce_by", "test_num", "eval_every")),
          "BOUNDED_SOURCE_TRAINING_BUDGET_REQUIRED", "reference_programme.configuration.training")
    _need(all(type(training[k]) is int and 0 <= training[k] < 2**31 for k in
              ("seed_weights", "seed_membrane", "seed_tf_loader", "seed_tf_loop", "seed_ruler")),
          "SOURCE_SEED_REQUIRED", "reference_programme.configuration.training")
    _need(all(type(training[k]) is float and training[k] == v for k, v in
              {"lr": .01, "momentum": .5, "beta": .99, "val_frac": .2}.items()) and
          training["reduce_by"] == 10 and training["reduce_every"] == 350 and training["test_num"] == 128 and
          training["seed_membrane"] + training["seed_ruler"] == 0,
          "EXACT_FRESH_SOURCE_SPLIT_PROGRAMME_REQUIRED", "reference_programme.configuration.training")
    _need(training["iterations"] == 1000 and training["batch_size"] == 256 and training["eval_every"] == 100,
          "EXACT_REFERENCE_FIT_DEFAULTS_REQUIRED", "reference_programme.configuration.training")
    _need(value["configuration_sha256"] == canonical_sha256(cfg), "PROGRAMME_CONFIGURATION_DIGEST_MISMATCH", "reference_programme.configuration_sha256")
    # Frozen retina_model.train: ceil complete batches/epochs, every eval_every
    # batches plus one unconditional epoch-end evaluation. This is a declaration
    # consistency check; it is not evidence that these evaluations occurred.
    batches = (SPLIT_COUNTS["train"] + training["batch_size"] - 1) // training["batch_size"]
    epochs = (training["iterations"] + batches - 1) // batches
    evaluations = epochs * (batches // training["eval_every"] + 1)
    _need(batches == 48 and epochs == 21 and evaluations == 21 and batches * epochs == 1008 and
          SPLIT_COUNTS["train"] % training["batch_size"] == 153,
          "AUTHOR_VALIDATION_CHECK_COUNT_MISMATCH", "reference_programme.configuration.training")
    _need(choices["evaluation_checkpoint_epoch"] <= epochs, "CHECKPOINT_EPOCH_NOT_PRODUCED", "reference_programme.configuration.choices")
    _keys(value["selection"], ("metric", "rule", "tie_break", "author_validation_checkpoints"), "reference_programme.selection")
    _need(value["selection"] == {"metric": "validation_mean_pearson", "rule": "maximum", "tie_break": "first", "author_validation_checkpoints": 21},
          "SOURCE_VALIDATION_SELECTION_REQUIRED", "reference_programme.selection")


def _manifest(value, condition, episode):
    path = "conditions." + condition
    _keys(value, ("view", "paper", "morphology", "author_code", "additional_materials"), path)
    _artifact(value["paper"], path + ".paper")
    _artifact(value["morphology"], path + ".morphology")
    _need(value["additional_materials"] == [], "UNDECLARED_MATERIALS_FORBIDDEN", path + ".additional_materials")
    if condition == "A":
        _need(value["author_code"] is None, "AUTHOR_CODE_FORBIDDEN_IN_A", path + ".author_code")
    else:
        _keys(value["author_code"], ("commit", "artifact"), path + ".author_code")
        _need(value["author_code"]["commit"] == AUTHOR_COMMIT, "EXACT_AUTHOR_COMMIT_REQUIRED", path + ".author_code.commit")
        _artifact(value["author_code"]["artifact"], path + ".author_code.artifact")
        _need(value["author_code"]["artifact"] == episode["reference_programme"]["source_snapshot"],
              "PINNED_AUTHOR_SOURCE_ARTIFACT_MISMATCH", path + ".author_code.artifact")
    view = value["view"]
    _keys(view, ("schema", "cell_id", "information_condition", "identity_sha256", "site_keys", "preprocessing_access",
                 "validation_access_sha256", "splits"), path + ".view")
    _need(view["schema"] == "jaxley-retinal-candidate-manifest-v2" and view["cell_id"] == CELL_ID and
          view["information_condition"] == CONDITIONS[condition] and view["identity_sha256"] == episode["identity_sha256"] and
          view["site_keys"] == [[s["field"], s["branch"], s["bin"]] for s in episode["sites"]] and
          view["preprocessing_access"] == PREPROCESSING_ACCESS and
          view["validation_access_sha256"] == canonical_sha256(episode["validation_access"]),
          "PAIRED_VIEW_IDENTITY_MISMATCH", path + ".view")
    _keys(view["splits"], SPLIT_COUNTS, path + ".view.splits")
    n_currents = None
    for split, count in SPLIT_COUNTS.items():
        row = view["splits"][split]
        spath = path + ".view.splits." + split
        keys = ("row_ids", "images", "currents", "mask", "targets") if split in ("train", "val") else ("row_ids", "images", "currents", "mask")
        _keys(row, keys, spath)
        _need(row["row_ids"] == episode["splits"][split], "EXACT_SPLIT_ORDER_REQUIRED", spath + ".row_ids")
        _array(row["images"], [count, 15, 20], spath + ".images")
        current_shape = row["currents"].get("shape") if type(row["currents"]) is dict else None
        _need(type(current_shape) is list and len(current_shape) == 2, "CURRENT_SHAPE_REQUIRED", spath + ".currents")
        _array(row["currents"], [count, current_shape[1]], spath + ".currents")
        if n_currents is None:
            n_currents = current_shape[1]
        _need(current_shape[1] == n_currents, "SHARED_CURRENT_AXIS_REQUIRED", spath + ".currents")
        _array(row["mask"], [count, 147], spath + ".mask", float64=True)
        if split in ("train", "val"):
            _array(row["targets"], [count, 147], spath + ".targets", float64=True)
    return value


def _public_artifacts(condition):
    result = [condition["paper"], condition["morphology"]]
    if condition["author_code"] is not None:
        result.append(condition["author_code"]["artifact"])
    for split in condition["view"]["splits"].values():
        result.extend(value for key, value in split.items() if key != "row_ids")
    return result


def _provenance(value, role, episode, context_sha256, manifests):
    if value is None:
        return False
    path = "execution_provenance." + role
    _keys(value, ("schema", "run_id", "role", "episode_id", "identity_sha256", "context_sha256", "material_manifest_sha256",
                  "source_snapshot", "selected_checkpoint", "selected_validation_event_id", "validation_selection_receipt",
                  "output_packet_sha256", "events", "closure", "transport_receipt"), path)
    _need(value["schema"] == "jaxley-retinal-run-provenance-v1" and value["role"] == role and
          value["episode_id"] == episode["episode_id"] and value["identity_sha256"] == episode["identity_sha256"] and
          value["context_sha256"] == context_sha256, "RUN_PROVENANCE_IDENTITY_MISMATCH", path)
    _name(value["run_id"], path + ".run_id")
    _name(value["selected_validation_event_id"], path + ".selected_validation_event_id")
    expected_manifest = context_sha256 if role == "reference" else manifests[role]
    _need(value["material_manifest_sha256"] == expected_manifest, "RUN_MATERIAL_MANIFEST_MISMATCH", path)
    for key in ("source_snapshot", "selected_checkpoint", "validation_selection_receipt", "events", "closure", "transport_receipt"):
        _artifact(value[key], path + "." + key)
    _hash(value["output_packet_sha256"], path + ".output_packet_sha256")
    if role == "reference":
        _need(value["source_snapshot"] == episode["reference_programme"]["source_snapshot"] and
              value["output_packet_sha256"] == episode["scored_packet_sha256"]["author"], "FRESH_REFERENCE_BINDING_MISMATCH", path)
    elif role == episode["evaluated_condition"]:
        _need(value["output_packet_sha256"] == episode["scored_packet_sha256"]["candidate"], "CANDIDATE_OUTPUT_BINDING_MISMATCH", path)
    return True


def validate_pair(episode, *, trusted_operator_evidence=None):
    """Validate declarations; never upgrade them to verified execution evidence.

    The trusted_operator_evidence parameter is reserved for a future explicit
    supported verifier, not a dictionary-based authority shortcut. It is neither
    imported, executed nor trusted in this version.
    """
    _keys(episode, ("schema", "episode_id", "evaluated_condition", "cell_id", "sites", "splits", "identity_sha256",
                    "preprocessing", "validation_access", "participant_budget", "reference_programme", "conditions", "private_materials",
                    "scored_packet_sha256", "execution_provenance"), "episode")
    _need(episode["schema"] == "jaxley-paired-retinal-episode-v2" and episode["cell_id"] == CELL_ID and
          episode["evaluated_condition"] in CONDITIONS, "EXACT_EPISODE_SCOPE_REQUIRED", "episode")
    _name(episode["episode_id"], "episode_id")
    identity = _sites_and_splits(episode["sites"], episode["splits"])
    _need(episode["identity_sha256"] == identity, "INPUT_IDENTITY_MISMATCH", "identity_sha256")
    _preprocessing(episode["preprocessing"])
    _validation_access(episode["validation_access"])
    _budget(episode["participant_budget"])
    _programme(episode["reference_programme"])
    _keys(episode["conditions"], CONDITIONS, "conditions")
    for condition in CONDITIONS:
        _manifest(episode["conditions"][condition], condition, episode)
    a, b = episode["conditions"]["A"], episode["conditions"]["B"]
    _need(a["paper"] == b["paper"] and a["morphology"] == b["morphology"] and
          a["view"]["splits"] == b["view"]["splits"], "PAIRED_DATA_OR_VALIDATION_EXPOSURE_MISMATCH", "conditions")
    _keys(episode["private_materials"], ("observed_test_calcium", "full_private_binding", "operator_packet"), "private_materials")
    for role, value in episode["private_materials"].items():
        _artifact(value, "private_materials." + role)
    private_hashes = {x["sha256"] for x in episode["private_materials"].values()}
    private_names = {x["logical_name"] for x in episode["private_materials"].values()}
    for condition in CONDITIONS:
        artifacts = _public_artifacts(episode["conditions"][condition])
        _need(all(x["sha256"] not in private_hashes and x["logical_name"] not in private_names for x in artifacts),
              "PRIVATE_TEST_OR_BINDING_MATERIAL_FORBIDDEN", "conditions." + condition)
        if condition == "A":
            source = episode["reference_programme"]["source_snapshot"]
            _need(all(x["sha256"] != source["sha256"] and x["logical_name"] != source["logical_name"] for x in artifacts),
                  "AUTHOR_SOURCE_PAYLOAD_FORBIDDEN_IN_A", "conditions.A")
        names = [x["logical_name"] for x in artifacts]
        _need(len(names) == len(set(names)), "DISTINCT_PUBLIC_MATERIAL_NAMES_REQUIRED", "conditions." + condition)
    _keys(episode["scored_packet_sha256"], ("operator", "author", "candidate"), "scored_packet_sha256")
    for role, value in episode["scored_packet_sha256"].items():
        _hash(value, "scored_packet_sha256." + role)
    _need(episode["scored_packet_sha256"]["operator"] == episode["private_materials"]["operator_packet"]["sha256"],
          "PRIVATE_SCORER_PACKET_MISMATCH", "scored_packet_sha256.operator")
    context = {k: episode[k] for k in ("episode_id", "identity_sha256", "preprocessing", "validation_access", "participant_budget", "reference_programme")}
    context_sha = canonical_sha256(context)
    manifests = {key: canonical_sha256(value) for key, value in episode["conditions"].items()}
    _keys(episode["execution_provenance"], ("reference", "A", "B"), "execution_provenance")
    declared = {role: _provenance(value, role, episode, context_sha, manifests)
                for role, value in episode["execution_provenance"].items()}
    reasons = ["ENFORCING_TRANSPORT_UNBOUND", "TRUSTED_EVENT_PROVENANCE_VERIFIER_UNBOUND",
               "VALIDATION_APPROVAL_RECEIPT_NOT_AUTHENTICATED_BY_THIS_COMPONENT",
               "SOURCE_SPLIT_AND_PREPROCESSING_PROVENANCE_NOT_EXECUTED_OR_AUTHENTICATED"]
    reasons.extend("MISSING_RUN_PROVENANCE_" + role.upper() for role, present in declared.items() if not present)
    if trusted_operator_evidence is not None:
        reasons.append("CALLER_SUPPLIED_OPERATOR_EVIDENCE_CANNOT_QUALIFY_UNBOUND_TRANSPORT")
    return {"schema": "jaxley-paired-retinal-episode-validation-v1", "status": "UNQUALIFIED",
            "contract_valid": True, "qualification": False, "execution_qualified": False,
            "qualification_reasons": reasons, "episode_sha256": canonical_sha256(episode),
            "identity_sha256": identity, "evaluated_condition": episode["evaluated_condition"],
            "scored_packet_sha256": dict(episode["scored_packet_sha256"]),
            "shared_data_manifest_sha256": canonical_sha256(a["view"]["splits"]),
            "condition_manifest_sha256": manifests, "execution_context_sha256": context_sha,
            "shared_participant_budget_sha256": canonical_sha256(episode["participant_budget"]),
            "declared_run_provenance_present": declared, "source_split_recomputed": False,
            "mask_privacy_claim": False, "structural_mask_rule": "row_id//1024+1 == site.field",
            "declared_observed_test_calcium_public": False, "declared_validation_targets_visible_to_both": True,
            "candidate_validation_query_limit": None, "author_validation_checkpoints": 21,
            "dataset_scope": "one cell; field-by-frame holdout with repeated stimulus frames across fields",
            "clean_train_only_preprocessing": False, "reference_or_candidate_executed": False}
