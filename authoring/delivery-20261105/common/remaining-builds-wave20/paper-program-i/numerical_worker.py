"""Concrete trusted primitive reference fit/query and candidate model admission.

Store ownership, allocation/deadline, lineage, Docker and complete outer/inner
loops remain with the operator controller. This module never imports a candidate
program, native reader, author source or a serialized Python object.
"""
import math
from pathlib import PurePosixPath
import re

import numpy as np

from artifacts import save_model, load_model
from reference import encoder


def _require(condition, message):
    if not condition:
        raise encoder.ReferenceError(message)


def _tokens(values):
    _require(type(values) is list and values and all(type(value) is str and
             re.fullmatch(r"[A-Za-z0-9_-]{1,96}", value) for value in values) and
             len(set(values)) == len(values), "complete unique ordered opaque cell tokens required")
    return values


def _pin(pin):
    _require(type(pin) is dict and set(pin) == {"bytes", "sha256"} and
             type(pin["bytes"]) is int and pin["bytes"] > 0 and
             type(pin["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", pin["sha256"]),
             "exact positive model bytes/SHA256 pin required")


def _model_path(path):
    _require(type(path) is str and 0 < len(path) <= 1024 and "\\" not in path,
             "bounded relative POSIX model path required")
    parts = path.split("/")
    _require(all(part not in ("", ".", "..") and
                 re.fullmatch(r"[A-Za-z0-9_.-]{1,96}", part) for part in parts) and
             parts[-1] == "MODEL.json" and not PurePosixPath(path).is_absolute(),
             "model path must name an in-store MODEL.json without traversal")


def validate_bundle(bundle_manifest, *, kind="reference", profile=None, cell_tokens=None):
    """Validate every output cell exactly once before loading any model body."""
    _require(kind in ("reference", "candidate"), "unknown bundle kind")
    _require(type(bundle_manifest) is dict and set(bundle_manifest) ==
             {"schema", "profile", "cell_tokens", "groups"} and
             bundle_manifest["schema"] == f"paper_i_{kind}_bundle_v1", "exact bundle manifest required")
    selected_profile = bundle_manifest["profile"]
    _require(selected_profile in encoder.PROFILES and
             (profile is None or selected_profile == profile), "bundle profile mismatch")
    ordered = _tokens(bundle_manifest["cell_tokens"])
    _require(cell_tokens is None or ordered == cell_tokens, "bundle complete cell axis mismatch")
    groups = bundle_manifest["groups"]
    _require(type(groups) is list and groups, "nonempty complete model groups required")
    used, paths = set(), set()
    for group in groups:
        _require(type(group) is dict and set(group) ==
                 {"model_path", "model_pin", "cell_tokens", "output_indices"}, "exact model-group ABI required")
        _model_path(group["model_path"])
        _pin(group["model_pin"])
        _require(group["model_path"] not in paths, "model path repeated in bundle")
        paths.add(group["model_path"])
        cells = _tokens(group["cell_tokens"])
        indices = group["output_indices"]
        _require(type(indices) is list and len(indices) == len(cells) and
                 all(type(index) is int and 0 <= index < len(ordered) for index in indices) and
                 len(set(indices)) == len(indices), "invalid group output-cell indices")
        _require(not used.intersection(indices) and [ordered[index] for index in indices] == cells,
                 "duplicate, reordered or misbound group cell axis")
        used.update(indices)
    _require(used == set(range(len(ordered))), "model bundle omits required output cells")
    return bundle_manifest


def fit_reference(train_manifest, input_store, output_store):
    """Fit exactly one declared reference configuration on supplied training data."""
    required = {"schema", "profile", "feature_schema", "configuration", "cell_tokens", "X", "Y", "weights"}
    _require(type(train_manifest) is dict and required <= set(train_manifest) and
             set(train_manifest) <= required | {"label_provenance", "selected_cell_indices"} and
             train_manifest["schema"] == "paper_i_reference_train_v1", "exact TRAIN reference ABI required")
    profile = train_manifest["profile"]
    _require(profile in encoder.PROFILES and type(train_manifest["feature_schema"]) is dict and
             train_manifest["feature_schema"].get("profile") == profile, "training profile/schema mismatch")
    cells = _tokens(train_manifest["cell_tokens"])
    configuration = train_manifest["configuration"]
    _require(configuration in encoder.configs(profile), "configuration absent from exact reference family")
    input_store.tick()
    output_store.tick()
    y = input_store.numeric(train_manifest["Y"])
    weights = input_store.numeric(train_manifest["weights"])
    _require(y.ndim == 2 and y.shape[1] == len(cells), "training target cell-axis binding mismatch")
    selected = train_manifest.get("selected_cell_indices")
    if selected is not None:
        _require(type(selected) is list and selected and
                 all(type(index) is int and 0 <= index < len(cells) for index in selected) and
                 len(set(selected)) == len(selected), "unique nonempty in-bounds selected cell indices required")
        y = y[:, selected]
        cells = [cells[index] for index in selected]
    model = encoder.fit(train_manifest["X"], y, weights, train_manifest["feature_schema"],
                        configuration, label_provenance=train_manifest.get("label_provenance"))
    input_store.tick()
    output_store.tick()
    manifest, model_pin = save_model(output_store, model, cells, profile)
    return {"schema": "paper_i_reference_fit_result_v1", "profile": profile,
            "model_path": "MODEL.json", "model_pin": model_pin, "model_manifest": manifest,
            "configuration_id": configuration["id"], "cell_tokens": cells,
            "logical_cell_fits": len(cells), "fit_calls": 1,
            "svd_factorizations": int(configuration["representation"] != "context_average"),
            "training_examples": y.shape[0], "operator_private": True}


def predict_reference(bundle_manifest, input_store, output_store, record):
    """Load bounded selected models and emit one complete vector for one query."""
    bundle = validate_bundle(bundle_manifest)
    profile, cells = bundle["profile"], bundle["cell_tokens"]
    result = np.empty(len(cells), dtype=np.float64)
    fallback_by_group = []
    shared_schema = None
    for group in bundle["groups"]:
        input_store.tick()
        # The owner's load_model resolves array paths relative to model_path's
        # parent using this exact Store and its existing cumulative read counter.
        model = load_model(input_store, group["model_path"], group["model_pin"],
                           profile, group["cell_tokens"])
        metadata = model["metadata"]
        _require(metadata.get("version") == encoder.MODEL_VERSION and
                 metadata.get("n_cells") == len(group["cell_tokens"]), "reference model identity/cell count mismatch")
        if shared_schema is None:
            shared_schema = metadata.get("schema")
        else:
            _require(metadata.get("schema") == shared_schema,
                     "selected cell groups disagree on complete feature schema")
        predicted, info = encoder.predict_with_info(model, record)
        _require(predicted.shape == (len(group["cell_tokens"]),) and np.isfinite(predicted).all(),
                 "nonfinite/incomplete reference group prediction")
        result[group["output_indices"]] = predicted
        fallback_by_group.append({"output_indices": group["output_indices"],
                                  "context_fallback": info["context_fallback"]})
    _require(np.isfinite(result).all(), "full reference prediction unavailable")
    input_store.tick()
    output_store.tick()
    prediction = output_store.put_numeric("PREDICTION.npy", np.ascontiguousarray(result))
    return {"schema": "paper_i_reference_prediction_v1", "profile": profile,
            "cell_tokens": cells, "prediction": prediction,
            "query_records_consumed": 1, "group_prediction_calls": len(bundle["groups"]),
            "fallback_by_group": fallback_by_group, "operator_private": True}


_PRIVATE_KEYS = {
    "label_provenance", "receipt_sha256", "source_for_destination", "permutation",
    "permutation_seed", "permutation_receipt", "shuffle_seed", "shuffle_receipt",
    "inverse_permutation", "private_index", "source_row", "physical_trial",
}


def _public_metadata(value, depth=0):
    """Check passive strict JSON; reject reserved operator-private null records."""
    _require(depth <= 64, "candidate metadata nesting exceeds admitted passive JSON depth")
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        _require(math.isfinite(value), "nonfinite candidate metadata")
        return
    if type(value) is list:
        for item in value:
            _public_metadata(item, depth + 1)
        return
    _require(type(value) is dict and all(type(key) is str for key in value),
             "candidate metadata must be passive JSON, never callable/module/object")
    for key, item in value.items():
        _require(key.lower() not in _PRIVATE_KEYS,
                 "candidate metadata contains operator-private permutation/identity material")
        _public_metadata(item, depth + 1)


def admit_candidate_model(model_path, model_pin, input_store, profile, cell_tokens):
    """Admit primitive state without executing or understanding candidate code.

    Owner Store/load_model verifies exact JSON pins, NPY headers/extent/dtype,
    finite primitive state, relative paths and cumulative budgets. No reference
    architecture is imposed on an otherwise opaque candidate model.
    """
    _model_path(model_path)
    _pin(model_pin)
    _require(profile in encoder.PROFILES, "invalid candidate model profile")
    _tokens(cell_tokens)
    input_store.tick()
    model = load_model(input_store, model_path, model_pin, profile, cell_tokens)
    _public_metadata(model["metadata"])
    _require(type(model["arrays"]) is dict, "primitive candidate array mapping required")
    for key, value in model["arrays"].items():
        _require(type(key) is str and re.fullmatch(r"[A-Za-z0-9_]{1,64}", key), "unsafe candidate numeric-state key")
        _require(isinstance(value, np.ndarray) and value.dtype.str in ("<f8", "<f4", "<i8", "|i1") and
                 value.flags.c_contiguous and np.isfinite(value).all(), "invalid/nonfinite primitive candidate numeric state")
    input_store.tick()
    return model


def admit_candidate_bundle(bundle_manifest, input_store, *, profile=None, cell_tokens=None):
    """Validate full candidate cell coverage and every primitive model group."""
    bundle = validate_bundle(bundle_manifest, kind="candidate", profile=profile, cell_tokens=cell_tokens)
    groups = []
    for group in bundle["groups"]:
        model = admit_candidate_model(group["model_path"], group["model_pin"], input_store,
                                      bundle["profile"], group["cell_tokens"])
        groups.append({"model_path": group["model_path"], "model_pin": group["model_pin"],
                       "output_indices": group["output_indices"], "cell_tokens": group["cell_tokens"],
                       "primitive_arrays": len(model["arrays"]),
                       "numeric_payload_bytes": sum(value.nbytes for value in model["arrays"].values())})
    return {"schema": "paper_i_candidate_model_admission_v1", "profile": bundle["profile"],
            "cell_tokens": bundle["cell_tokens"], "groups": groups,
            "candidate_code_executed": False,
            "qualification": "primitive artifact admission only; no predictive competence claim"}
