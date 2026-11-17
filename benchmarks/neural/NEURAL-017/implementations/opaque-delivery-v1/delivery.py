"""Full MC_Maze public-packet remapping and operator-only prediction restoration.

These APIs consume trusted, operator-loaded arrays, not hostile archive bytes.
They never accept evaluation targets, fit a model, or calculate a score.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re

import numpy as np


SCHEMA = "NLB017_opaque_delivery_v1"
PUBLIC_KEYS = {
    "train_counts_heldin", "train_counts_heldout", "eval_counts_heldin",
    "train_trial_ids", "eval_trial_ids", "heldin_unit_ids", "heldout_unit_ids",
    "train_condition_ids", "eval_condition_ids", "bin_left_edges_ms",
    "eval_valid_mask", "source_manifest_sha256", "panel_fingerprint",
}
PREDICTION_KEYS = {
    "expected_counts", "trial_ids", "heldout_unit_ids", "bin_left_edges_ms",
    "prediction_units", "panel_fingerprint",
}
AXIS_SIZES = {"train_trial_ids": 1721, "eval_trial_ids": 574,
              "heldin_unit_ids": 137, "heldout_unit_ids": 45}
COUNT_SHAPES = {"train_counts_heldin": (1721, 140, 137),
                "train_counts_heldout": (1721, 140, 45),
                "eval_counts_heldin": (574, 140, 137)}
GRID = np.arange(-250, 450, 5, dtype=np.float64)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def scalar(value, name):
    array = np.asarray(value)
    require(array.shape == () and array.dtype.kind == "U", name + " must be Unicode scalar")
    return str(array.item())


def sha256_text(value, name):
    value = scalar(value, name)
    require(re.fullmatch(r"[0-9a-f]{64}", value) is not None, name + " must be SHA256")
    return value


def ids(value, length, name, *, unique=True):
    array = np.asarray(value)
    require(array.shape == (length,) and array.dtype.kind == "U"
            and 0 < array.dtype.itemsize <= 1024, name + " must be bounded Unicode IDs")
    values = array.tolist()
    require(all(values) and (not unique or len(set(values)) == length),
            name + " contains empty or duplicate identities")
    return values


def _chunks(value):
    # No whole-array int64/floating temporary, including on broadcast fixtures.
    for start in range(0, len(value), 16):
        yield value[start:start + 16]


def _array_hash(value, dtype):
    result = hashlib.sha256()
    for part in _chunks(value):
        result.update(np.asarray(part, dtype=dtype).tobytes(order="C"))
    return result.hexdigest()


def fingerprint(packet):
    """Exact inherited public-only fingerprint encoding, streamed in row blocks.

    Call validate_public first for unvalidated arrays. This digest does not
    authenticate acquisition lineage; its expected value is supplied by custody.
    """
    fields = {}
    for name in sorted(PUBLIC_KEYS - {"panel_fingerprint", "source_manifest_sha256"}):
        value = np.asarray(packet[name])
        if name.endswith("_ids"):
            encoding = "utf8-json-unicode-list-v1"
            payload = json.dumps(value.tolist(), ensure_ascii=False,
                                 separators=(",", ":")).encode("utf8")
            checksum = hashlib.sha256(payload).hexdigest()
        else:
            dtype, encoding = (("u1", "uint8-c-order") if name == "eval_valid_mask"
                               else ("<f8", "little-endian-float64-c-order")
                               if name == "bin_left_edges_ms"
                               else ("<i8", "little-endian-int64-c-order"))
            checksum = _array_hash(value, dtype)
        fields[name] = {"shape": list(value.shape), "encoding": encoding, "sha256": checksum}
    return digest({"schema": "nlb-cosmoothing-public-v1",
                   "source_commit": "42f8410b88e12db136910fa2f888b025ea0aa2ae",
                   "dandiset_version": "000128/0.220113.0400", "bin_ms": 5,
                   "counts_units": "spikes_per_bin",
                   "source_manifest_sha256": scalar(packet["source_manifest_sha256"], "source manifest"),
                   "fields": fields})


def validate_public(packet, expected_fingerprint):
    """Admit the entire fixed public panel; never silently drop rows or fields."""
    require(set(packet) == PUBLIC_KEYS, "Exact public field allowlist required; targets are forbidden")
    expected_fingerprint = sha256_text(expected_fingerprint, "expected source fingerprint")
    require(sha256_text(packet["panel_fingerprint"], "panel fingerprint") == expected_fingerprint,
            "Source fingerprint differs from operator commitment")
    sha256_text(packet["source_manifest_sha256"], "source manifest")
    axes = {name: ids(packet[name], n, name) for name, n in AXIS_SIZES.items()}
    require(not set(axes["train_trial_ids"]) & set(axes["eval_trial_ids"]), "Training/query trial overlap")
    require(not set(axes["heldin_unit_ids"]) & set(axes["heldout_unit_ids"]), "Observed/withheld unit overlap")
    train_conditions = ids(packet["train_condition_ids"], 1721, "training conditions", unique=False)
    eval_conditions = ids(packet["eval_condition_ids"], 574, "query conditions", unique=False)
    require(set(eval_conditions) <= set(train_conditions), "Query condition lacks training support")
    grid = np.asarray(packet["bin_left_edges_ms"])
    require(grid.dtype.kind in "fiu" and np.array_equal(grid, GRID), "Exact 140-bin 5 ms grid required")
    mask = np.asarray(packet["eval_valid_mask"])
    require(mask.shape == (574, 140, 45) and mask.dtype == np.bool_ and mask.all(),
            "Complete fixed target support required")
    for name, shape in COUNT_SHAPES.items():
        array = np.asarray(packet[name])
        require(array.shape == shape and array.dtype.kind in "fiu", "Invalid count shape/type: " + name)
        for part in _chunks(array):
            upper = 2**53 if array.dtype.kind in "iu" else np.float64(2**53)
            require(np.isfinite(part).all() and (part >= 0).all() and (part <= upper).all()
                    and (array.dtype.kind in "iu" or (part == np.floor(part)).all()),
                    "Counts must be exact finite nonnegative integers: " + name)
    require(fingerprint(packet) == expected_fingerprint, "Public content fingerprint mismatch")
    return axes, train_conditions, eval_conditions


def _alias(secret, namespace, role, identity):
    body = canonical([SCHEMA, namespace, role, identity])
    # 128 bits, plus role prefix: fits the inherited 64-character ID boundary.
    return role + "-" + hmac.new(secret, body, hashlib.sha256).hexdigest()[:32]


def export_public(source, *, secret, expected_source_fingerprint):
    """Return (participant packet, PRIVATE binding), preserving the whole task.

    Keep the 32-byte random secret and binding outside the participant mount.
    Freeze this shared export before fitting/exposure in all compared arms.
    Neither the input nor its metadata is mutated. Count dtypes are preserved.
    """
    require(type(secret) is bytes and len(secret) == 32, "Operator secret must be exactly 32 bytes")
    axes, train_conditions, eval_conditions = validate_public(source, expected_source_fingerprint)
    namespace = scalar(source["source_manifest_sha256"], "source manifest")
    mappings = {}
    permutations = {}
    result = {}
    for name, values in axes.items():
        role = "tr" if "trial" in name else "un"
        aliases = [_alias(secret, namespace, role, value) for value in values]
        require(len(set(aliases)) == len(aliases), "Opaque identity collision")
        order = np.argsort(aliases, kind="stable")
        mappings[name] = {"source": values, "opaque_in_source_order": aliases}
        permutations[name] = order
        result[name] = np.asarray(aliases)[order]
    ti, qi = permutations["train_trial_ids"], permutations["eval_trial_ids"]
    ui, uo = permutations["heldin_unit_ids"], permutations["heldout_unit_ids"]
    bins = np.arange(140)
    for name, trials, units in (("train_counts_heldin", ti, ui),
                               ("train_counts_heldout", ti, uo),
                               ("eval_counts_heldin", qi, ui)):
        result[name] = np.asarray(source[name])[np.ix_(trials, bins, units)]
    # Conditions are explicitly permitted context, including any factor
    # structure carried in their source encoding. Retain the labels verbatim.
    result["train_condition_ids"] = np.asarray(source["train_condition_ids"])[ti].copy()
    result["eval_condition_ids"] = np.asarray(source["eval_condition_ids"])[qi].copy()
    result["bin_left_edges_ms"] = np.asarray(source["bin_left_edges_ms"]).copy()
    result["eval_valid_mask"] = np.asarray(source["eval_valid_mask"])[np.ix_(qi, bins, uo)]
    core = {"schema": SCHEMA, "source_panel_fingerprint": str(expected_source_fingerprint),
            "source_manifest_sha256": namespace, "axes": mappings,
            "condition_policy": "original permitted labels retained verbatim and permuted with their trials",
            "key_sha256": hashlib.sha256(secret).hexdigest(),
            "permutation": "lexicographic opaque ID order separately within each split/axis",
            "counts_units": "spikes_per_5ms_bin"}
    result["source_manifest_sha256"] = np.asarray(digest(core))
    result["panel_fingerprint"] = np.asarray(fingerprint(result))
    binding = {"core": core, "public_manifest_sha256": digest(core),
               "public_panel_fingerprint": result["panel_fingerprint"].item()}
    # Immutable exported arrays prevent accidental post-binding view edits.
    for array in result.values():
        array.setflags(write=False)
    return result, binding


def restore_prediction(prediction, binding, *, expected_binding_sha256):
    """Operator-only exact inverse to the inherited scorer's source axes.

    The binding's expected hash must come from the operator freeze, never from
    the participant. No target/comparator array is loaded or needed here.
    Arbitrary submitted trial/unit permutations are accepted when IDs agree.
    """
    require(digest(binding) == sha256_text(expected_binding_sha256, "binding commitment"),
            "Private binding differs from operator commitment")
    require(set(binding) == {"core", "public_manifest_sha256", "public_panel_fingerprint"},
            "Private binding fields")
    core = binding["core"]
    require(core["schema"] == SCHEMA and digest(core) == binding["public_manifest_sha256"],
            "Private mapping provenance mismatch")
    require(set(prediction) == PREDICTION_KEYS, "Exact prediction fields required")
    require(scalar(prediction["prediction_units"], "prediction units") == "expected_spikes_per_bin",
            "Predictions must be expected spikes per bin, not Hz")
    require(scalar(prediction["panel_fingerprint"], "prediction fingerprint") == binding["public_panel_fingerprint"],
            "Prediction belongs to a different delivered panel")
    grid = np.asarray(prediction["bin_left_edges_ms"])
    require(grid.dtype.kind in "fiu" and np.array_equal(grid, GRID), "Prediction bin alignment")
    submitted_trials = ids(prediction["trial_ids"], 574, "submitted trials")
    submitted_units = ids(prediction["heldout_unit_ids"], 45, "submitted units")
    orders = []
    source_ids = []
    for name, submitted, size in (("eval_trial_ids", submitted_trials, 574),
                                  ("heldout_unit_ids", submitted_units, 45)):
        mapping = core["axes"][name]
        original = ids(mapping["source"], size, "private source identities")
        opaque = ids(mapping["opaque_in_source_order"], size, "private opaque identities")
        require(set(submitted) == set(opaque), "Prediction identity set mismatch")
        index = {value: i for i, value in enumerate(submitted)}
        orders.append([index[value] for value in opaque])
        source_ids.append(np.asarray(original))
    counts = np.asarray(prediction["expected_counts"])
    require(counts.shape == (574, 140, 45) and counts.dtype.kind in "fiu",
            "Prediction must cover all 574 x 140 x 45 cells")
    require(np.isfinite(counts).all() and (counts > 0).all(), "Finite strictly positive predictions required")
    return {"expected_counts": counts[np.ix_(orders[0], np.arange(140), orders[1])],
            "trial_ids": source_ids[0], "heldout_unit_ids": source_ids[1],
            "bin_left_edges_ms": grid.copy(), "prediction_units": "expected_spikes_per_bin",
            "panel_fingerprint": core["source_panel_fingerprint"]}
