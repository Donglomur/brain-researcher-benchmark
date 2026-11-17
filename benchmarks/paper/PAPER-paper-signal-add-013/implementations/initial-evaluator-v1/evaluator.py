"""Owner-side CALC–CTRL map-array component; no native/qualified benchmark claim.

Semantic derivation: NeuroenergeticsLab/two_modes_of_hemodynamics,
1b22c2cb03bab0d5cf70da6a45c4d720194dc523, D_Fig2BD.ipynb Fig. 2B.
Original implementation; no upstream code is bundled. See provenance.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

import numpy as np

TASK_ID = "PAPER-paper-signal-add-013"
CONTRACT_SHA256 = "dc4aa310b2265d05b3cfa88b7f8093ebc82cbac96ca6d67628c9c83b899dcd64"
CODE_REVISION = "1b22c2cb03bab0d5cf70da6a45c4d720194dc523"
DATA_REVISION = "eef50ff140a9863c412428b0bd1a14f46f5cd342"
SUBJECT_NUMBERS = (19, 20, 21, 23, 26, 27, 28, 29, 30, 31, 32, 33, 34,
                   35, 36, 37, 38, 39, 40, 43, 44, 46, 47, 48, 49, 50,
                   51, 52, 54, 55, 58, 59, 60, 61, 63, 64, 65, 66, 67, 68)
SUBJECTS = tuple(f"sub-p{i:03d}" for i in SUBJECT_NUMBERS)
ARRAY_KEYS = {"voxel_indices", "positive_mask", "negative_mask", "bold_percent_change",
              "cmro2_control_orig", "cmro2_calc_cbv", "cmro2_calc_source_original"}
MAP_KEYS = ("bold_percent_change", "cmro2_control_orig", "cmro2_calc_cbv", "cmro2_calc_source_original")
MASK_PATHS = {
    "whole_brain": "derivatives/task-all_space-MNI152_res-2_SNR_YEO_group_mask.nii.gz",
    "positive": "results/N40_BSR_meanPLS_func_clusterBSR_res-2_calccontrol_GMmask_pos_bin.nii.gz",
    "negative": "results/N40_BSR_meanPLS_func_clusterBSR_res-2_calccontrol_GMmask_neg_bin.nii.gz",
}
HOLDS = [
    "Authentic snapshot2.0.6 maps, lineage, masks and geometry require independent verification.",
    "Native NIfTI extraction, physiological calibration and preceding notebook execution unqualified.",
    "PLS modes, bootstrap ratios and source-mask construction are not implemented by this component.",
    "Source BOLD PLS masks are exposed reproduction masks; no independent confirmatory mask claim.",
    "Spatial-autocorrelation nulls are not supplied; no voxelwise p-values or spatial significance.",
    "Participant bootstrap is prospective descriptive uncertainty, not the paper PLS bootstrap.",
    "No authentic reference execution, figure matching, independent replication or improvement established.",
    "Protected assessment, harness isolation, numeric target/tolerance and difficulty remain unqualified.",
    "CC0 data and CC BY-NC-SA4.0 upstream code terms remain distinct; public exposure retained.",
]


class ContractError(ValueError):
    """A packet fails a fixed component contract; no population/voxel dropping follows."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _require(condition, message):
    if not condition:
        raise ContractError(message)


def _digest(value, label):
    _require(isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value),
             f"{label} must be an explicit lowercase SHA-256")


def source_map_path(subject: str, key: str) -> str:
    if key == "bold_percent_change":
        return f"derivatives/{subject}/func/{subject}_task-calccontrol_space-MNI152_desc-fmriprep_BOLD_percchange.nii.gz"
    condition, lineage = {"cmro2_control_orig": ("control", "orig"),
                          "cmro2_calc_cbv": ("calc", "CBV"),
                          "cmro2_calc_source_original": ("calc", "orig" if subject in SUBJECTS[:30] else "CBV")}[key]
    return f"derivatives/{subject}/qmri/{subject}_task-{condition}_space-MNI152_desc-{lineage}_cmro2.nii.gz"


def validate_manifest(manifest):
    """Validate the fixed policy; assertions are owner attestations, not remote proof."""
    _require(isinstance(manifest, dict), "manifest must be an object")
    for key, expected in {
        "schema_version": 1, "task_id": TASK_ID, "contract_sha256": CONTRACT_SHA256,
        "dataset": "ds004873", "dataset_version": "2.0.6", "dataset_git_revision": DATA_REVISION,
        "official_code_revision": CODE_REVISION, "contrast": "calc-control",
        "primary_lineage": "calc_desc-CBV_vs_control_desc-orig",
        "original_sensitivity_lineage": "calc_desc-orig_first30_desc-CBV_last10_vs_control_desc-orig",
        "mask_policy": "frozen_source_PLS_BOLD_reproduction_only",
        "spatial_null_policy": "withheld_pending_geometry_preserving_null_qualification",
        "bold_units": "already_percent_change", "cmro2_units": "umol/100g/min",
    }.items():
        _require(manifest.get(key) == expected, f"wrong or missing fixed field: {key}")
    _require(manifest.get("subject_ids") == list(SUBJECTS),
             "subject_ids must be the exact ordered primary40 (not metadata75 or full-condition30)")
    grid = manifest.get("grid", {})
    _require(grid.get("space") == "MNI152" and grid.get("shape") == [91, 109, 91]
             and grid.get("voxel_size_mm") == [2, 2, 2]
             and grid.get("index_order") == "C_flat_sorted", "grid must be the declared MNI152 2mm source grid")
    _digest(grid.get("affine_sha256"), "grid affine_sha256")
    _digest(grid.get("voxel_indices_sha256"), "grid voxel_indices_sha256")
    _require(manifest.get("data_file") == "maps.npz", "data_file is fixed to maps.npz")
    _digest(manifest.get("data_sha256"), "data_sha256")
    _require(manifest.get("source_receipt_status") == "operator_attested_not_independently_authenticated",
             "source receipts cannot claim automatic authentication")
    receipts = manifest.get("map_receipts")
    _require(isinstance(receipts, list) and len(receipts) == 160, "all 40×4 map receipts required")
    expected = {(s, k) for s in SUBJECTS for k in MAP_KEYS}
    seen = set()
    for receipt in receipts:
        _require(isinstance(receipt, dict), "map receipt must be an object")
        pair = (receipt.get("subject_id"), receipt.get("map_key"))
        _require(pair in expected and pair not in seen, "unexpected or duplicate source map receipt")
        seen.add(pair)
        _require(receipt.get("path") == source_map_path(*pair), "source map lineage/path mismatch")
        _digest(receipt.get("sha256"), "source map sha256")
        _require(type(receipt.get("bytes")) is int and receipt["bytes"] > 0, "map byte count required")
        _require(receipt.get("affine_sha256") == grid["affine_sha256"], "map affine receipt mismatch")
    by_pair = {(r["subject_id"], r["map_key"]): r for r in receipts}
    for subject in SUBJECTS[30:]:
        _require(by_pair[subject, "cmro2_calc_cbv"]["sha256"] ==
                 by_pair[subject, "cmro2_calc_source_original"]["sha256"],
                 "last10 source-original convention uses the same measured CBV maps")
    mask_receipts = manifest.get("mask_receipts", {})
    _require(set(mask_receipts) == set(MASK_PATHS), "whole-brain and both signed mask receipts required")
    for key, path in MASK_PATHS.items():
        receipt = mask_receipts[key]
        _require(receipt.get("path") == path, f"wrong source {key} mask path")
        _digest(receipt.get("sha256"), f"{key} mask sha256")
        _require(receipt.get("affine_sha256") == grid["affine_sha256"], "mask affine receipt mismatch")
    _digest(manifest.get("preassessment_freeze_receipt_sha256"), "preassessment freeze receipt")
    _digest(manifest.get("physiology_and_cbv_lineage_receipt_sha256"), "physiology/CBV lineage receipt")


def validate_arrays(arrays, manifest):
    _require(set(arrays) == ARRAY_KEYS, "NPZ must contain exactly the seven documented arrays")
    indices = np.asarray(arrays["voxel_indices"])
    _require(indices.ndim == 1 and indices.size >= 3 and indices.dtype.kind in "iu",
             "voxel_indices must be a nonempty integer vector")
    _require(np.all(indices >= 0) and np.all(indices < 91 * 109 * 91)
             and np.all(indices[1:] > indices[:-1]), "voxel indices must be sorted, unique and in-grid")
    index_hash = hashlib.sha256(indices.astype("<i8").tobytes()).hexdigest()
    _require(index_hash == manifest["grid"]["voxel_indices_sha256"], "voxel order digest mismatch")
    masks = []
    for key in ("positive_mask", "negative_mask"):
        a = np.asarray(arrays[key])
        _require(a.shape == indices.shape and a.dtype.kind == "b" and a.any(),
                 f"{key} must be a nonempty boolean vector on the frozen voxel order")
        masks.append(a)
    _require(not np.any(masks[0] & masks[1]), "positive and negative masks must be disjoint")
    for key in MAP_KEYS:
        a = np.asarray(arrays[key])
        _require(a.shape == (40, indices.size) and a.dtype.kind in "fiu", f"bad 40-person matrix: {key}")
        _require(np.isfinite(a).all(), f"{key} contains nonfinite data; no silent voxel/participant dropping")
        if key != "bold_percent_change":
            _require(np.all(a > 0), f"{key} must be positive within the fixed mask; validity hold cannot be dropped")

    _require(np.array_equal(arrays["cmro2_calc_cbv"][30:], arrays["cmro2_calc_source_original"][30:]),
             "last10 sensitivity rows must be the same measured-CBV arrays")

def load_packet(manifest_path, expected_manifest_sha256):
    """Expected digest must come from owner state frozen before candidate evaluation."""
    path = Path(manifest_path)
    _digest(expected_manifest_sha256, "externally trusted manifest digest")
    _require(sha256_file(path) == expected_manifest_sha256, "owner manifest digest mismatch")
    manifest = json.loads(path.read_text())
    validate_manifest(manifest)
    data_path = path.parent / "maps.npz"
    _require(sha256_file(data_path) == manifest["data_sha256"], "NPZ digest mismatch")
    with np.load(data_path, allow_pickle=False) as archive:
        arrays = {key: archive[key] for key in archive.files}
    validate_arrays(arrays, manifest)
    return manifest, arrays


def percent_change(task, baseline):
    """Apply the within-person source contrast before any group reduction."""
    task, baseline = np.asarray(task, dtype=float), np.asarray(baseline, dtype=float)
    _require(task.shape == baseline.shape and np.isfinite(task).all()
             and np.isfinite(baseline).all() and np.all(baseline > 0), "invalid percentage contrast")
    result = 100.0 * (task - baseline) / baseline
    _require(np.isfinite(result).all(), "nonfinite percentage contrast")
    return result


def pearson(x, y):
    """Descriptive spatial correlation; undefined values are explicit JSON null."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    x, y = x - x.mean(), y - y.mean()
    denom = float(np.linalg.norm(x) * np.linalg.norm(y))
    return None if denom == 0 else float(np.clip(np.dot(x, y) / denom, -1, 1))


def _region_summary(bold, metabolism):
    # Figure2B stores these two noncommuting reductions separately.
    b_group, m_group = np.median(bold, axis=0), np.median(metabolism, axis=0)
    b_subject, m_subject = np.median(bold, axis=1), np.median(metabolism, axis=1)
    nonzero = (b_group != 0) & (m_group != 0)
    n_nonzero = int(nonzero.sum())
    n_opposed = int(((b_group[nonzero] > 0) != (m_group[nonzero] > 0)).sum())
    return {
        "voxel_count": int(bold.shape[1]),
        "source_spatial_median_of_voxelwise_subject_medians": {
            "bold_percent": float(np.median(b_group)), "cmro2_percent": float(np.median(m_group))},
        "participant_spatial_medians": {"bold_percent": b_subject.tolist(), "cmro2_percent": m_subject.tolist()},
        "median_of_participant_spatial_medians": {
            "bold_percent": float(np.median(b_subject)), "cmro2_percent": float(np.median(m_subject))},
        "spatial_pearson_descriptive": pearson(b_group, m_group),
        "group_voxel_signs": {"nonzero_pair_count": n_nonzero,
            "zero_pair_count": int(nonzero.size - n_nonzero), "opposed_count": n_opposed,
            "opposed_fraction_nonzero": n_opposed / n_nonzero if n_nonzero else None},
    }


def _bootstrap(bold, metabolism, indices):
    # One resample uses the same subjects for both modalities and every voxel.
    estimates = np.empty((len(indices), 2))
    for i, sample in enumerate(indices):
        estimates[i] = (np.median(np.median(bold[sample], axis=0)),
                        np.median(np.median(metabolism[sample], axis=0)))
    interval = np.quantile(estimates, [0.025, 0.975], axis=0, method="linear")
    return {"bold_percent": interval[:, 0].tolist(), "cmro2_percent": interval[:, 1].tolist()}


def evaluate_packet(manifest, arrays, *, bootstrap_replicates=2000, seed=0):
    """Compute a complete fixed contrast component, never a benchmark reward."""
    validate_manifest(manifest)
    validate_arrays(arrays, manifest)
    _require(type(bootstrap_replicates) is int and 1 <= bootstrap_replicates <= 10000,
             "bootstrap_replicates must be 1..10000 (engineering bound, not qualification)")
    _require(type(seed) is int and seed >= 0, "seed must be a nonnegative integer")
    bold = np.asarray(arrays["bold_percent_change"], dtype=float)
    baseline = arrays["cmro2_control_orig"]
    corrected = percent_change(arrays["cmro2_calc_cbv"], baseline)
    original = percent_change(arrays["cmro2_calc_source_original"], baseline)
    resamples = np.random.default_rng(seed).integers(0, 40, size=(bootstrap_replicates, 40))
    outputs = {}
    for lineage, metabolism in (("primary_cbv", corrected), ("source_original_convention_sensitivity", original)):
        outputs[lineage] = {}
        for region in ("positive", "negative"):
            mask = arrays[region + "_mask"]
            summary = _region_summary(bold[:, mask], metabolism[:, mask])
            summary["prospective_paired_subject_bootstrap_percentile_95"] = _bootstrap(
                bold[:, mask], metabolism[:, mask], resamples)
            outputs[lineage][region] = summary
    return {
        "task_id": TASK_ID, "component": "fixed_calc_control_map_contrast",
        "status": "owner_packet_component_computed_not_scientifically_qualified",
        "subject_ids": list(SUBJECTS), "n_primary": 40, "n_full_condition": 30,
        "n_additional_control_calc": 10, "metadata_rows_not_sample_size": 75,
        "contrast": "calc-control", "outputs": outputs,
        "bootstrap": {"replicates": bootstrap_replicates, "seed": seed,
                      "unit": "paired_subject_entire_spatial_field", "quantile_method": "linear"},
        "spatial_null_pvalue": None, "reward": None, "research_qualified": False,
        "full_contract_complete": False, "holds": HOLDS,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bootstrap-replicates", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    manifest, arrays = load_packet(args.manifest, args.expected_manifest_sha256)
    result = evaluate_packet(manifest, arrays, bootstrap_replicates=args.bootstrap_replicates, seed=args.seed)
    result["owner_manifest_sha256"] = args.expected_manifest_sha256
    result["data_sha256"] = manifest["data_sha256"]
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
