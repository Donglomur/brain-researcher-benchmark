"""Join already-computed indexed curator labels into the owner curation export.

No sorter, model or native curation function runs here. The independently frozen
manifest and the caller's native results remain trusted evaluator-side inputs.
"""
from __future__ import annotations

from collections.abc import Mapping
import json
from numbers import Integral
from pathlib import Path

import evaluator as e


def _items(value, location):
    if isinstance(value, (str, bytes, Mapping)):
        raise e.ContractError(f"{location}: expected an iterable of explicit items")
    try:
        return iter(value)
    except TypeError as error:
        raise e.ContractError(f"{location}: expected an iterable of explicit items") from error


def _unit_key(value):
    # SpikeInterface native IDs may be integer scalars or strings. Keep their
    # types until alignment is checked, then use the existing JSON string IDs.
    if isinstance(value, Integral) and not isinstance(value, bool):
        return "integer", str(int(value))
    if isinstance(value, str):
        e._text(value, "native unit_id")
        return "string", value
    raise e.ContractError("native unit_id must be an integer or string, never a float or boolean")


def _labels(indexed_labels, native_keys, allowed, location):
    labels = {}
    for pair in _items(indexed_labels, location):
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise e.ContractError(f"{location}: expected (native unit_id, label) pairs")
        key = _unit_key(pair[0])
        if key not in native_keys or key in labels:
            raise e.ContractError(f"{location}: duplicate or foreign native unit_id")
        label = pair[1]
        if not isinstance(label, str) or label not in allowed:
            raise e.ContractError(f"{location}: unknown curation label")
        labels[key] = label
    if set(labels) != native_keys:
        raise e.ContractError(f"{location}: missing native units")
    return labels


def prepare_curation_exports(manifest, native_results, expected_manifest_sha256):
    """Prepare all four source sorters' complete indexed results for evaluator.py.

    For each sorter, pass native_unit_ids from its sorting, bombcell_labels and
    unitrefine_labels as Series.items() iterables, slay_merge_groups from the
    native merge routine, and native_artifact_sha256 matching the owner manifest.
    The tables may have different row orders. Iterators are consumed once.
    """
    e.validate_manifest(manifest, expected_manifest_sha256)
    e._keys(native_results, e.SORTERS, "native results")
    exports = {"schema_version": 1, "owner_manifest_sha256": expected_manifest_sha256,
               "sorters": {}}
    for sorter in e.SORTERS:
        result = native_results[sorter]
        e._keys(result, ("native_unit_ids", "bombcell_labels", "unitrefine_labels",
                         "slay_merge_groups", "native_artifact_sha256"), sorter)
        native = {}
        for value in _items(result["native_unit_ids"], "native_unit_ids"):
            key = _unit_key(value)
            unit_id = key[1]
            if unit_id in native:
                raise e.ContractError(f"{sorter}: duplicate or colliding native unit IDs")
            native[unit_id] = key
        owner_units = manifest["runs"][sorter]["unit_spike_counts"]
        if set(native) != set(owner_units):
            raise e.ContractError(f"{sorter}: native units differ from the frozen owner inventory")
        native_keys = set(native.values())
        bombcell = _labels(result["bombcell_labels"], native_keys, e.BOMBCELL, "bombcell_labels")
        unitrefine = _labels(result["unitrefine_labels"], native_keys, e.UNITREFINE, "unitrefine_labels")
        groups = []
        for group in _items(result["slay_merge_groups"], "slay_merge_groups"):
            converted = []
            for value in _items(group, "merge group"):
                key = _unit_key(value)
                if key not in native_keys:
                    raise e.ContractError(f"{sorter}: foreign merge unit_id")
                converted.append(key[1])
            groups.append(converted)
        exports["sorters"][sorter] = {
            "unit_rows": [{"unit_id": uid, "bombcell_label": bombcell[native[uid]],
                           "unitrefine_label": unitrefine[native[uid]]} for uid in owner_units],
            "slay_merge_groups": groups,
            "native_artifact_sha256": result["native_artifact_sha256"],
        }
    # Retain the existing complete-inventory, merge-group and artifact policies.
    # This also preserves every unresolved scientific/native-execution hold.
    e.evaluate_curation(manifest, exports, expected_manifest_sha256)
    return exports


def write_curation_exports(manifest, native_results, expected_manifest_sha256, destination):
    """Validate and serialize before creating a new JSON export; never overwrite."""
    exports = prepare_curation_exports(manifest, native_results, expected_manifest_sha256)
    payload = json.dumps(exports, indent=2, allow_nan=False) + "\n"
    with Path(destination).open("x", encoding="utf-8") as stream:
        stream.write(payload)
    return e.canonical_digest(exports)
