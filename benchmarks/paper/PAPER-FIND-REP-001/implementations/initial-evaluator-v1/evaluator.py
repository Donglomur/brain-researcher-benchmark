"""Source-derived Fig. 2f endpoint; this is not a qualified paper grader.

The input is an explicitly prepared export of the author's putative/excl_no_response
place-field binF arrays. No pickle, native-data acquisition, or fluorescence
preprocessing occurs here. See the companion task documentation for admission holds.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
import zipfile

import numpy as np

TASK_ID = "PAPER-FIND-REP-001"
SOURCE_REVISION = "c1d1788b54c737efe24402e02762eee10da0d0d7"
CONTRACT_SHA256 = "a90c0c9a0231bfb61ffe839aa7f203df47cb0d92f54aeec5803c81fb20fc557d"
ANIMALS = tuple("Tyche-" + s for s in ("A4", "A5", "A7", "B2", "B3", "B4", "B5", "C1", "D1", "F1", "F5"))
REGIONS = ("off_diagonal", "pre_r2_indices_34_37", "pre_r1_indices_24_27", "initial", "indicator", "end")
HOLDS = (
    "Prepared binF export has not been independently checked against native vr2p/Zarr data.",
    "The 11-animal roster is fixed, but complete session ledger and archive lineage require independent native verification.",
    "Matched behavior, running-speed >5 cm/s filtering, 5-cm bins, fluorescence processing and cross-day registration require native qualification.",
    "No authentic empirical reference, frozen numeric target, tolerance or protected assessment is supplied.",
    "Fig. 2f is a scoped endpoint; full-paper longitudinal stability and state-versus-continuous-position improvement remain unresolved.",
    "Native dependency versions, complete empirical resource envelope, input rights and exposure remain admission gates.",
    "Generated controls establish engineering behavior only; unseen-animal/task generalization is not established.",
)


class ContractError(ValueError):
    """Input cannot be interpreted under the explicitly supported contract."""


def masks() -> np.ndarray:
    """Six literal Fig_2f cell-5 masks, in the source's ordering (6,46,46)."""
    result = np.zeros((6, 46, 46), dtype=bool)
    blocks = ((0, 12), (20, 26), (30, 36), (40, 46))
    for i, (start, stop) in enumerate(blocks):
        for j, (other_start, other_stop) in enumerate(blocks):
            if i != j:
                result[0, start:stop, other_start:other_stop] = True
    for index, (start, stop) in enumerate(((34, 37), (24, 27), (0, 12), (17, 20), (40, 46)), 1):
        result[index, start:stop, start:stop] = True
    return result


def population_correlations(near: np.ndarray, far: np.ndarray) -> np.ndarray:
    """Pearson r across matched cells for all near/far position pairs.

    Arrays have shape cells x 46, as the native binF record before the notebook's
    transposition. Undefined Pearson coefficients remain NaN, never zero or
    pairwise-deleted-cell estimates. Infinity and nonnumeric arrays are rejected.
    """
    arrays = []
    for name, value in (("near", near), ("far", far)):
        a = np.asarray(value)
        if a.dtype.kind not in "fiu" or a.ndim != 2 or a.shape[1] != 46 or a.shape[0] < 2:
            raise ContractError(f"{name}: expected numeric cells x 46 with at least two cells")
        a = a.astype(np.float64, copy=False)
        if np.isinf(a).any():
            raise ContractError(f"{name}: infinity is not a supported missing value")
        arrays.append(a)
    near, far = arrays
    if near.shape != far.shape:
        raise ContractError("near/far cell dimensions differ")
    with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
        return np.corrcoef(near.T, far.T)[:46, 46:]


def region_means(correlations: np.ndarray) -> np.ndarray:
    """Ordinary masked means: undefined entries propagate within each region."""
    a = np.asarray(correlations, dtype=float)
    if a.shape != (46, 46) or np.isinf(a).any():
        raise ContractError("correlations must be 46 x 46 without infinity")
    return np.array([np.mean(a[mask]) for mask in masks()])


def normalize_learning(days_by_regions: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Source interpolation: drop NaN days per region, then evenly space at 0..1.

    This intentionally does not retain missing-day time gaps: the notebook
    constructs its x after deleting NaNs. Return valid counts so this behavior is
    auditable. Regions with fewer than two values are explicitly undefined.
    """
    a = np.asarray(days_by_regions, dtype=float)
    if a.ndim != 2 or a.shape[1] != 6 or np.isinf(a).any():
        raise ContractError("learning series must have shape days x 6 and no infinity")
    result = np.full((6, 1000), np.nan)
    counts = np.zeros(6, dtype=int)
    grid = np.linspace(0, 1, 1000)
    for region in range(6):
        values = a[:, region][~np.isnan(a[:, region])]
        counts[region] = len(values)
        if len(values) >= 2:
            result[region] = np.interp(grid, np.linspace(0, 1, len(values)), values)
    return result, counts


def aggregate_animals(curves: np.ndarray) -> dict[str, np.ndarray]:
    """Equal-animal mean and source population-SD SEM; no cell/bin pseudoreplication."""
    a = np.asarray(curves, dtype=float)
    if a.ndim != 3 or a.shape[1:] != (6, 1000) or a.shape[0] < 2 or np.isinf(a).any():
        raise ContractError("curves must have shape animals x 6 x 1000, at least two animals")
    # Ordinary mean/std deliberately propagate an undefined animal to the group.
    return {"mean": np.mean(a, axis=0), "source_sem_ddof0": np.std(a, axis=0, ddof=0) / np.sqrt(a.shape[0])}


def _nonempty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{name} must be a nonempty string")
    return value


def _integer(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ContractError(f"{name} must be a nonnegative integer")
    return value


def _sha256(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ContractError(f"{name} must be a lowercase SHA256")
    return value


def _pinned_path(root: Path, value: Any, expected: Any) -> tuple[Path, dict[str, Any]]:
    relative = _nonempty_string(value, "array path")
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root.resolve()):
        raise ContractError("array paths must resolve within the manifest directory")
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise ContractError(f"cannot read array: {relative}") from exc
    actual = digest.hexdigest()
    if actual != _sha256(expected, "array sha256"):
        raise ContractError(f"array SHA256 mismatch: {relative}")
    return path, {"path": relative, "sha256": actual, "bytes": path.stat().st_size}


def _validate_animal(animal: Any) -> list[dict[str, Any]]:
    if not isinstance(animal, dict):
        raise ContractError("animal entry must be an object")
    _nonempty_string(animal.get("animal_id"), "animal_id")
    count = _integer(animal.get("native_session_count"), "native_session_count")
    sessions = animal.get("sessions")
    if not isinstance(sessions, list) or len(sessions) != count or count < 2:
        raise ContractError("session ledger must cover every declared native session")
    selected = []
    still_initial_a = True
    for index, session in enumerate(sessions):
        if not isinstance(session, dict) or _integer(session.get("session_index"), "session_index") != index:
            raise ContractError("sessions must be contiguous and ordered from native index zero")
        cues = session.get("cue_sets")
        if not isinstance(cues, list) or not cues or any(not isinstance(x, str) or not x for x in cues) or len(cues) != len(set(cues)):
            raise ContractError("cue_sets must contain unique nonempty source labels")
        _nonempty_string(session.get("behavior_record"), "behavior_record")
        still_initial_a = still_initial_a and cues == ["Cue Set A"]
        if still_initial_a:
            if session.get("selection") != "putative/excl_no_response":
                raise ContractError("selected sessions require source putative/excl_no_response binF")
            selected.append(session)
    if len(selected) < 2:
        raise ContractError("normalized learning requires at least two initial pure Cue Set A sessions")
    return selected


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def evaluate_manifest(manifest_path: str | Path) -> dict[str, Any]:
    """Evaluate all eleven source animals from pinned, prepared numeric exports.

    Manifest fields are provenance claims, never evidence of native qualification.
    No admission field is promoted to scientific readiness by this function.
    """
    manifest_path = Path(manifest_path).resolve()
    raw = manifest_path.read_bytes()
    try:
        manifest = json.loads(raw, object_pairs_hook=_unique_object,
                              parse_constant=lambda value: (_ for _ in ()).throw(ContractError(f"invalid JSON number {value}")))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ContractError("manifest must be strict JSON") from exc
    if not isinstance(manifest, dict) or type(manifest.get("schema_version")) is not int or manifest.get("schema_version") != 1 or manifest.get("task_id") != TASK_ID:
        raise ContractError("wrong manifest schema or task ID")
    if manifest.get("input_kind") != "prepared_putative_placefields_binF":
        raise ContractError("input_kind must explicitly identify prepared binF exports")
    if manifest.get("evidence_kind") not in ("generated_engineering_control", "empirical_unqualified_export"):
        raise ContractError("evidence_kind must distinguish generated controls and unqualified empirical exports")
    if manifest.get("source_revision") != SOURCE_REVISION:
        raise ContractError("official source revision mismatch")
    lineage = manifest.get("lineage")
    if not isinstance(lineage, dict) or type(lineage.get("article_id")) is not int or type(lineage.get("article_version")) is not int or lineage.get("article_id") != 27273552 or lineage.get("article_version") != 1:
        raise ContractError("lineage must identify the canonical Figshare article version")
    for key in ("placefields_record", "registered_fluorescence_record", "behavior_record", "export_procedure", "rights_review"):
        _nonempty_string(lineage.get(key), f"lineage.{key}")
    animals = manifest.get("animals")
    if not isinstance(animals, list) or len(animals) != len(ANIMALS) or any(not isinstance(a, dict) for a in animals):
        raise ContractError("the complete eleven-animal Fig. 2f roster is required")
    roster = [a.get("animal_id") for a in animals]
    if any(not isinstance(x, str) for x in roster) or set(roster) != set(ANIMALS) or len(set(roster)) != len(ANIMALS):
        raise ContractError("animal roster must exactly match the pinned Set A roster")
    by_id = {a["animal_id"]: a for a in animals}
    results, curves, pins = [], [], []
    for animal_id in ANIMALS:
        animal = by_id[animal_id]
        selected = _validate_animal(animal)
        day_results, day_means = [], []
        registered_ids = None
        for session in selected:
            path, pin = _pinned_path(manifest_path.parent, session.get("arrays"), session.get("sha256"))
            try:
                with path.open("rb") as input_handle, np.load(input_handle, allow_pickle=False) as arrays:
                    if set(arrays.files) != {"near_binF", "far_binF", "cell_ids"}:
                        raise ContractError("NPZ requires exactly near_binF, far_binF, cell_ids")
                    near, far, ids = arrays["near_binF"], arrays["far_binF"], arrays["cell_ids"]
            except (OSError, ValueError, TypeError, EOFError, zipfile.BadZipFile) as exc:
                if isinstance(exc, ContractError):
                    raise
                raise ContractError(f"invalid safe numeric NPZ: {pin['path']}") from exc
            if ids.ndim != 1 or ids.dtype.kind not in "Ui" or len(ids) != len(set(ids.tolist())) or not len(ids):
                raise ContractError("cell_ids must be unique Unicode strings or signed integers")
            if ids.dtype.kind == "U" and any(not s for s in ids.tolist()):
                raise ContractError("empty cell identifiers are not permitted")
            if near.ndim != 2 or len(ids) != near.shape[0]:
                raise ContractError("cell_ids must match the cell dimension")
            if registered_ids is None:
                registered_ids = ids.copy()
            elif not np.array_equal(registered_ids, ids):
                raise ContractError("registered cell identity/order must match across selected days")
            corr = population_correlations(near, far)
            means = region_means(corr)
            day_means.append(means)
            pins.append({"animal_id": animal_id, "session_index": session["session_index"], **pin})
            day_results.append({"session_index": session["session_index"], "n_cells": len(ids),
                                "undefined_correlations": int(np.isnan(corr).sum()),
                                "correlations_near_by_far": corr, "region_means": means})
        normalized, counts = normalize_learning(np.asarray(day_means))
        curves.append(normalized)
        results.append({"animal_id": animal_id, "native_session_count_declared": animal["native_session_count"],
                        "selected_initial_a_sessions": [s["session_index"] for s in selected],
                        "valid_day_counts_by_region": counts, "days": day_results,
                        "normalized_learning_curves": normalized})
    return _json_safe({
        "schema_version": 1, "task_id": TASK_ID, "implementation": "initial-evaluator-v1",
        "endpoint": "source_derived_fig_2f_prepared_binF", "evidence_kind": manifest["evidence_kind"],
        "source_revision": SOURCE_REVISION, "canonical_contract_sha256": CONTRACT_SHA256,
        "scientifically_qualified": False, "full_contract_complete": False, "binary_reward": None,
        "native_reference_executed": False, "preserved_holds": list(HOLDS),
        "input_manifest": {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)},
        "declared_lineage_unverified": lineage, "input_pins": pins,
        "region_order": list(REGIONS), "mask_entry_counts": masks().sum(axis=(1, 2)),
        "normalized_time": np.linspace(0, 1, 1000), "animals": results,
        "group": {"n_animals": len(ANIMALS), "independent_unit": "animal", **aggregate_animals(np.asarray(curves))},
        "undefined_value_encoding": "null; NaN is never replaced with zero or omitted from group means",
    })


def _json_safe(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        if args.output.resolve() == args.manifest.resolve():
            raise ContractError("output cannot overwrite the input manifest")
        report = evaluate_manifest(args.manifest)
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, allow_nan=False)
            handle.write("\n")
    except (ContractError, OSError) as exc:
        parser.exit(2, f"error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
