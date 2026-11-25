"""ICNet Fig. 4b,d equations (3)--(5), not a qualified paper-win evaluator.

Inputs are already aligned, time x unit count arrays. Authentic preparation,
source mask recovery and baseline replay remain external prerequisites.
Variance divisor is an explicit convention, not a recovered historical default.
No response-based unit selection or sound pooling.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager, ExitStack
import hashlib
import json
import math
import os
import stat
from pathlib import Path

import numpy as np

ANIMALS = tuple(range(3, 10))
SOUNDS = ("speech_in_quiet", "speech_in_noise", "moving_ripples", "music")
ARRAY_NAMES = ("recorded_trial1", "recorded_trial2", "sampled_trial1",
               "sampled_trial2", "expected_trial1", "expected_trial2")


def _correlation(cross, ss_a, ss_b):
    if ss_a <= 0 or ss_b <= 0:
        return None
    # Separate square roots avoid an unnecessary product overflow.
    return float(cross / math.sqrt(ss_a) / math.sqrt(ss_b))


def _metrics(means, ss, cross, sse, diff_ss, n, ddof):
    reliability = _correlation(cross[0], ss[0], ss[1])
    correlations = [_correlation(cross[1], ss[0], ss[2]),
                    _correlation(cross[2], ss[1], ss[3])]
    issues = []
    correlation_explained = None
    if reliability is None or reliability == 0:
        issues.append("undefined_trial_reliability")
    elif any(x is None for x in correlations):
        issues.append("constant_sampled_prediction")
    else:
        correlation_explained = 50.0 * sum(correlations) / reliability
        if reliability < 0:
            issues.append("negative_trial_reliability")
    noise = 0.5 * diff_ss / (n - ddof)
    # Algebraically equal to .5*(Var(R1)+Var(R2)) - .5*Var(R1-R2).
    explainable = cross[0] / (n - ddof)
    mse = float(sum(sse) / (2 * n))
    variance_explained = None
    if explainable == 0:
        issues.append("zero_explainable_variance")
    else:
        variance_explained = 100.0 * (1.0 - (mse - noise) / explainable)
        if explainable < 0:
            issues.append("negative_explainable_variance")
    result = {
        "correlation_explained_percent": correlation_explained,
        "variance_explained_percent": variance_explained,
        "trial_reliability": reliability,
        "trial_prediction_correlations": correlations,
        "mean_count": float((means[0] + means[1]) / 2),
        "expected_count_mse": mse,
        "noise_variance": float(noise),
        "explainable_variance": float(explainable),
        "diagnostics": issues,
    }
    # Never serialize NaN/infinity or silently replace an undefined score by 0.
    numeric = [correlation_explained, variance_explained, reliability,
               *correlations, mse, noise, explainable]
    if any(x is not None and not math.isfinite(x) for x in numeric):
        raise ValueError("nonfinite metric; input magnitudes exceed numerical range")
    return result


def score_case(recorded_trial1, recorded_trial2, sampled_trial1,
               sampled_trial2, expected_trial1, expected_trial2, *,
               eligible_mask, unit_ids, variance_ddof, block_units=32):
    """Return flattened animal and time-only per-unit source metrics.

    Arrays must have identical time x unit shape. Masks are supplied by the
    trusted source-preparation operator and must not be estimated from these
    evaluation responses. ddof is explicit because native parity is unresolved.
    The bounded column blocks avoid loading all six full arrays as float64.
    """
    arrays = tuple(np.asarray(x) for x in (
        recorded_trial1, recorded_trial2, sampled_trial1, sampled_trial2,
        expected_trial1, expected_trial2))
    shape = arrays[0].shape
    if len(shape) != 2 or shape[0] < 2 or shape[1] < 1:
        raise ValueError("inputs must be time x unit matrices with at least two bins")
    if any(x.shape != shape or x.dtype.kind not in "iuf" for x in arrays):
        raise ValueError("all six arrays must have identical shapes and real numeric types")
    if type(variance_ddof) is not int or variance_ddof not in (0, 1):
        raise ValueError("variance_ddof must explicitly be 0 or 1")
    if type(block_units) is not int or not 1 <= block_units <= 512:
        raise ValueError("block_units must be between 1 and 512")
    mask = np.asarray(eligible_mask)
    if mask.shape != (shape[1],) or mask.dtype.kind != "b" or not mask.any():
        raise ValueError("eligible_mask must be a nonempty Boolean unit vector")
    if (len(unit_ids) != shape[1] or any(type(x) is not str or not x for x in unit_ids)
            or len(set(unit_ids)) != shape[1]):
        raise ValueError("unit_ids must uniquely identify every original column")

    # Validate excluded columns too; selection must not conceal corrupt arrays.
    for start in range(0, shape[1], block_units):
        for index, array in enumerate(arrays):
            block = np.asarray(array[:, start:start + block_units], dtype=np.float64)
            if not np.isfinite(block).all() or (block < 0).any():
                raise ValueError(f"{ARRAY_NAMES[index]} contains invalid count values")
            if index < 4 and not np.equal(block, np.floor(block)).all():
                raise ValueError(f"{ARRAY_NAMES[index]} must contain integer counts, not rates/means")
            if (block > 2**53 - 1).any():
                raise ValueError("count magnitude cannot be represented exactly in float64")

    selected = np.flatnonzero(mask)
    n_units = len(selected)
    time_bins = shape[0]
    means = np.empty((n_units, 4))
    ss = np.empty((n_units, 4))
    cross = np.empty((n_units, 3))
    sse = np.empty((n_units, 2))
    diff_ss = np.empty(n_units)
    for start in range(0, n_units, block_units):
        stop = min(start + block_units, n_units)
        columns = selected[start:stop]
        blocks = [np.asarray(x[:, columns], dtype=np.float64) for x in arrays]
        block_means = np.stack([x.mean(axis=0) for x in blocks[:4]], axis=1)
        centered = [x - block_means[:, i] for i, x in enumerate(blocks[:4])]
        means[start:stop] = block_means
        ss[start:stop] = np.stack([np.sum(x * x, axis=0) for x in centered], axis=1)
        cross[start:stop] = np.stack([
            np.sum(centered[a] * centered[b], axis=0)
            for a, b in ((0, 1), (0, 2), (1, 3))], axis=1)
        sse[start:stop] = np.stack([
            np.sum((blocks[a] - blocks[b])**2, axis=0)
            for a, b in ((0, 4), (1, 5))], axis=1)
        difference = blocks[0] - blocks[1]
        difference -= difference.mean(axis=0)
        diff_ss[start:stop] = np.sum(difference**2, axis=0)

    by_unit = [{"unit_id": unit_ids[column], "column_zero_based": int(column),
                **_metrics(means[i], ss[i], cross[i], sse[i], diff_ss[i],
                           time_bins, variance_ddof)} for i, column in enumerate(selected)]
    # Recover the flattened moments, including differences in unit means.
    # Averaging the per-unit correlations would discard this contribution.
    flat_means = means.mean(axis=0)
    offsets = means - flat_means
    flat_ss = (ss + time_bins * offsets**2).sum(axis=0)
    flat_cross = np.array([
        (cross[:, i] + time_bins * offsets[:, a] * offsets[:, b]).sum()
        for i, (a, b) in enumerate(((0, 1), (0, 2), (1, 3)))])
    flat_diff_ss = (diff_ss + time_bins * (offsets[:, 0] - offsets[:, 1])**2).sum()
    return {
        "time_bins": time_bins, "original_units": shape[1],
        "eligible_units": n_units, "variance_ddof": variance_ddof,
        "flattened": _metrics(flat_means, flat_ss, flat_cross, sse.sum(axis=0),
                              flat_diff_ss, time_bins * n_units, variance_ddof),
        "by_unit": by_unit,
    }


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha(value):
    return (type(value) is str and len(value) == 64
            and all(c in "0123456789abcdef" for c in value))


def _identity(stream):
    info = os.fstat(stream.fileno())
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


@contextmanager
def _load_array(root, entry):
    """Keep the authenticated descriptor and mapping alive through scoring."""
    if set(entry) != {"path", "sha256"} or not _sha(entry["sha256"]):
        raise ValueError("every NPY requires a relative path and SHA256")
    path = (root / entry["path"]).resolve()
    if Path(entry["path"]).is_absolute() or not path.is_relative_to(root):
        raise ValueError("array path escapes the operator input root")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("NPY must be an ordinary file")
        before = _identity(stream)
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
        if digest.hexdigest() != entry["sha256"]:
            raise ValueError("NPY SHA256 mismatch")
        stream.seek(0)
        version = np.lib.format.read_magic(stream)
        if version == (1, 0):
            shape, fortran, dtype = np.lib.format.read_array_header_1_0(stream)
        elif version in ((2, 0), (3, 0)):
            # Numeric descriptors use ASCII, common to the v2/v3 encodings.
            shape, fortran, dtype = np.lib.format.read_array_header_2_0(stream)
        else:
            raise ValueError("unsupported NPY version")
        if dtype.kind not in "iuf" or len(shape) != 2 or min(shape, default=0) <= 0:
            raise ValueError("NPY must contain a nonempty real numeric matrix")
        offset = stream.tell()
        if offset + math.prod(shape) * dtype.itemsize > before[2]:
            raise ValueError("truncated NPY payload")
        array = np.memmap(stream, mode="r", dtype=dtype, offset=offset,
                          shape=shape, order="F" if fortran else "C")
        try:
            if _identity(stream) != before:
                raise ValueError("NPY changed during authentication")
            yield array
            if _identity(stream) != before:
                raise ValueError("NPY changed during scoring")
        finally:
            array._mmap.close()


def score_panel(manifest, input_root):
    """Score exactly 28 cases; all preparation claims require external review.

    Source hashes preserve operator declarations, not source authentication.
    This API does not supply a scalar paper-win decision or a native baseline.
    """
    if manifest.get("schema") != "icnet-source-equations-input/v1":
        raise ValueError("unsupported input schema")
    ddof = manifest["variance_ddof"]
    if type(ddof) is not int or ddof not in (0, 1):
        raise ValueError("explicit variance_ddof required")
    preparation = manifest["preparation"]
    for field in ("source_mask_sha256", "alignment_protocol_sha256",
                  "prediction_freeze_sha256", "measurement_times_sha256"):
        if not _sha(preparation.get(field)):
            raise ValueError(f"missing preparation pin: {field}")
    if preparation.get("mask_origin") != "source_broadband_noise_reliability":
        raise ValueError("the mask must be sourced independently of evaluation sounds")
    if preparation.get("split") != "original_four_sounds_held_out_from_training":
        raise ValueError("trial/held-sound recalibration changes the original split")
    animals = manifest["animals"]
    if set(animals) != {str(a) for a in ANIMALS}:
        raise ValueError("original animals 3 through 9 are all required")
    eligible_total = 0
    for animal in animals.values():
        units, mask = animal["unit_ids"], animal["eligible_mask"]
        if (len(units) != 512 or len(set(units)) != 512
                or any(type(x) is not str or not x for x in units)):
            raise ValueError("512 unique original column identities required per animal")
        if len(mask) != 512 or any(type(x) is not bool for x in mask) or not any(mask):
            raise ValueError("one Boolean source mask for 512 units per animal required")
        eligible_total += sum(mask)
    if eligible_total != 3476:
        raise ValueError("Fig. 4d requires exactly 3476 source-eligible units")
    cases = manifest["cases"]
    keys = [(case["animal"], case["sound"]) for case in cases]
    expected_keys = {(animal, sound) for animal in ANIMALS for sound in SOUNDS}
    if (any(type(key[0]) is not int for key in keys) or len(keys) != 28
            or set(keys) != expected_keys):
        raise ValueError("exactly one case per original animal and sound is required")
    root = Path(input_root).resolve()
    results = []
    for case in sorted(cases, key=lambda c: (SOUNDS.index(c["sound"]), c["animal"])):
        if set(case["arrays"]) != set(ARRAY_NAMES):
            raise ValueError("both recorded, sampled and expected-count trials required")
        times = case["measurement_times_seconds"]
        if (len(times) != 2 or any(type(x) not in (int, float) or not math.isfinite(x)
                                  or x < 0 for x in times)):
            raise ValueError("two finite trial-specific measurement times required")
        with ExitStack() as stack:
            arrays = [stack.enter_context(_load_array(root, case["arrays"][key]))
                      for key in ARRAY_NAMES]
            if type(case["time_bins"]) is not int or arrays[0].shape != (case["time_bins"], 512):
                raise ValueError("prepared arrays must match declared time bins and 512 columns")
            animal = animals[str(case["animal"])]
            scores = score_case(*arrays, eligible_mask=animal["eligible_mask"],
                                unit_ids=animal["unit_ids"], variance_ddof=ddof)
        results.append({"animal": case["animal"], "sound": case["sound"],
                        "measurement_times_seconds": times, **scores})
    return {
        "schema": "icnet-source-equations-result/v1",
        "qualification": "source_equation_component_only",
        "preparation_pins": preparation,
        "variance_ddof": ddof,
        "n_animals": 7, "n_sounds": 4, "eligible_units": 3476,
        "cases": results,
        "published_text_aggregation": "textual_summaries_separate_from_defined_vectors",
        "endpoint_binding": {'definition_status': 'source_defined_fig4b_and_fig4d_vectors', 'primary_comparison': {'panel': 'Fig4d', 'observation': 'MUA channel within animal', 'reduction': 'time_only_per_unit', 'metrics': ['correlation_explained_percent', 'variance_explained_percent'], 'direction': 'higher_for_both', 'reference': 'source_single_layer_Poisson_LNP_for_same_units', 'biological_replication': 'animal; units and trials are nested'}, 'companion': {'panel': 'Fig4b', 'reduction': 'flatten_time_and_eligible_units_within_each_animal', 'metrics': ['correlation_explained_percent', 'variance_explained_percent']}, 'prediction_objects': {'equation_3': 'sampled_counts_from_each_trial_distribution', 'equations_4_5': 'expected_counts_from_each_trial_distribution'}, 'universal_scalar_required': False, 'textual_summary_reconciliation': 'separate_from_defined_vectors; not performed', 'distinct_overall_metrics': 'Figs1-3 early/late trial-average sampled-count RMSE and observed-count probability likelihood are not Fig4 metrics', 'source_uncertainty': '1000 unit bootstrap samples within each animal; no new inferential procedure implemented', 'prospective_conventions': {'variance_divisor': 'explicit variance_ddof input, common across compared models', 'undefined_metrics': 'null and diagnostics; retain units; no silent omission or clipping'}, 'accepted_definition_sha256': 'e7ec5c040d629dff023ced7d42edb1679b3c4d41636431fc441a684cbb712dd0'},
        "reproduction_evaluated": False,
        "improvement_evaluated": False,
        "native_author_baseline_reproduced": False,
        "paper_win_evaluated": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest_bytes = args.manifest.read_bytes()
    report = score_panel(json.loads(manifest_bytes), args.input_root)
    report["input_manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
