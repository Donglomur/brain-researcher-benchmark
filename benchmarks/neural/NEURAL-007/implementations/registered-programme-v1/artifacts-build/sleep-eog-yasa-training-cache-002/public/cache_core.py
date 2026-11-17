"""Prepared pure-array adapter for a shared fixed-YASA observation cache.

No model loading/calls, training, source reads, private targets or file loader.
Operator-owned file/lineage verification must precede these transformations.
"""
import re
import numpy as np

CLASSES = ("W", "N1", "N2", "N3", "R")
COMPONENTS = ("Fpz_EEG", "Pz_EEG", "Fpz_EEG_EOG", "Pz_EEG_EOG")
VIEWS = (*COMPONENTS, "EEG_ensemble", "EEG_EOG_ensemble", "Fpz_EEG_EOG_anchor")
FIELDS = {"epoch_id", "class_order", "component_order", "component_probabilities"}


def require(ok):
    if not ok:
        raise ValueError("invalid_shared_yasa_observation")


def canonical_ids(case_id, epochs):
    require(type(case_id) is str and re.fullmatch(r"(?:train|development)-[0-9]{3}", case_id)
            and type(epochs) is int and 1 <= epochs <= 5000)
    return np.asarray([case_id + "/" + f"{i:05d}" for i in range(epochs)])


def probability(value, epochs):
    require(isinstance(value, np.ndarray) and value.dtype == np.dtype("<f8")
            and value.shape == (epochs, 5) and np.isfinite(value).all()
            and np.all((value >= 0) & (value <= 1))
            and np.all(np.abs(value.sum(1, dtype=np.float64) - 1) <= 1e-10))


def validate_cache(cache, case_id, epochs):
    require(type(cache) is dict and set(cache) == FIELDS and all(isinstance(v, np.ndarray) for v in cache.values()))
    require(cache["epoch_id"].dtype.kind == "U" and np.array_equal(cache["epoch_id"], canonical_ids(case_id, epochs)))
    require(cache["class_order"].dtype.kind == "U" and np.array_equal(cache["class_order"], CLASSES))
    require(cache["component_order"].dtype.kind == "U" and np.array_equal(cache["component_order"], COMPONENTS))
    values = cache["component_probabilities"]
    require(values.shape == (epochs, 4, 5) and values.dtype == np.dtype("<f8"))
    for index in range(4):
        probability(values[:, index, :], epochs)
    return cache


def all_views(cache, case_id, epochs):
    validate_cache(cache, case_id, epochs)
    values = cache["component_probabilities"]
    result = {name: values[:, index, :].copy() for index, name in enumerate(COMPONENTS)}
    # Same float64 operands, order and arithmetic as the qualified reference.
    result["EEG_ensemble"] = (result["Fpz_EEG"] + result["Pz_EEG"]) / 2
    result["EEG_EOG_ensemble"] = (result["Fpz_EEG_EOG"] + result["Pz_EEG_EOG"]) / 2
    result["Fpz_EEG_EOG_anchor"] = result["Fpz_EEG_EOG"].copy()
    return result


def pack_seven_reference_streams(epoch_id, streams, class_order, case_id, epochs):
    """Convert an exact fixed-reference slice, preserving every named view.

    These identity constraints belong only to the shared tool provider. They
    must not be applied to a candidate's own final probability submission.
    """
    require(isinstance(epoch_id, np.ndarray) and epoch_id.dtype.kind == "U"
            and np.array_equal(epoch_id, canonical_ids(case_id, epochs)))
    require(tuple(class_order) == CLASSES and type(streams) is dict and set(streams) == set(VIEWS))
    for value in streams.values():
        probability(value, epochs)
    packet = {"epoch_id": epoch_id.copy(), "class_order": np.asarray(CLASSES),
              "component_order": np.asarray(COMPONENTS),
              "component_probabilities": np.stack([streams[name] for name in COMPONENTS], axis=1)}
    regenerated = all_views(packet, case_id, epochs)
    for name in VIEWS:
        require(regenerated[name].tobytes(order="C") == streams[name].tobytes(order="C"))
    return packet


def resolve_view(cache, case_id, epochs, view):
    """Full-clock response only, no arbitrary channel/model/weight parameters."""
    require(type(view) is str and view in VIEWS)
    arrays = all_views(cache, case_id, epochs)
    return {"case_id": case_id, "view": view, "epoch_id": cache["epoch_id"].copy(),
            "class_order": cache["class_order"].copy(), "probabilities": arrays[view]}


def split_qualified_development(epoch_id, streams, class_order):
    """Exact saved 2-person layout, no selection or additional YASA inference."""
    cases = (("development-001", 2780), ("development-002", 2670))
    expected = np.concatenate([canonical_ids(case_id, n) for case_id, n in cases])
    require(isinstance(epoch_id, np.ndarray) and np.array_equal(epoch_id, expected)
            and type(streams) is dict and set(streams) == set(VIEWS))
    for value in streams.values():
        probability(value, 5450)
    result, offset = {}, 0
    for case_id, n in cases:
        result[case_id] = pack_seven_reference_streams(epoch_id[offset:offset + n],
            {name: value[offset:offset + n] for name, value in streams.items()}, class_order, case_id, n)
        offset += n
    return result
