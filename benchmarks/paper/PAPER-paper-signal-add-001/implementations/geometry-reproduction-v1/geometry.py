"""Reexpress the released two-class geometry example, without classifier fitting.

The empirical five-category decoder and its greedy ensemble selection are not
implemented here. See README.md for the exact source scope and numerical limits.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np


def _real_array(value, name, shape=None):
    array = np.asarray(value)
    if array.dtype.kind not in "fiu":
        raise ValueError(f"{name} must contain real numbers, not booleans or objects")
    array = array.astype(float)
    if shape is not None and array.shape != shape:
        raise ValueError(f"{name} must have shape {shape}")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must be finite")
    return array


def replay_simulation(draws):
    """Apply the source's default transform to explicitly supplied random draws.

    This consumes, but never creates, the random realization. Array indexing is
    specified in README.md; supplied draws are not claimed to be historical.
    """
    keys = {"sigma_uniform", "independent_normal", "signal_normal",
            "common_normal", "permutations"}
    if not isinstance(draws, dict) or set(draws) != keys:
        raise ValueError(f"draws must have exactly these fields: {sorted(keys)}")
    uniform = _real_array(draws["sigma_uniform"], "sigma_uniform", (2, 2))
    if np.any((uniform < 0) | (uniform >= 1)):
        raise ValueError("sigma_uniform must be in [0, 1)")
    independent = _real_array(draws["independent_normal"], "independent_normal", (2, 200, 2))
    signal = _real_array(draws["signal_normal"], "signal_normal", (2, 200))
    common = _real_array(draws["common_normal"], "common_normal", (400,))
    permutations = np.asarray(draws["permutations"])
    if permutations.shape != (2, 2, 200) or permutations.dtype.kind not in "iu":
        raise ValueError("permutations must be integer [neuron, category, trial] indices")
    if not np.all(np.sort(permutations, axis=2) == np.arange(200)):
        raise ValueError("every permutation must contain every index 0..199 once")

    # noiseCorr_genData.m treats its variable named sigma as a standard deviation.
    data = independent * (2 * uniform + 1)[:, None, :]
    data += np.array([[10.0, 0.0], [5.0, 0.0]])[:, None, :]
    # Despite the source comment mentioning tuned dimensions, this term is
    # actually added to every dimension of a trial in the implementation.
    data += (signal * np.array([2.0, 0.2])[:, None])[:, :, None]
    data = data.reshape(400, 2)
    data += (2 * common)[:, None]
    if not np.isfinite(data).all():
        raise ValueError("draws overflowed the source transform")
    scrambled = data.copy()
    for neuron in range(2):
        for category in range(2):
            rows = category * 200 + np.arange(200)
            scrambled[rows, neuron] = data[category * 200 + permutations[neuron, category], neuron]
    return {"data": data.tolist(), "labels": [0] * 200 + [1] * 200,
            "data_scrambled": scrambled.tolist()}


def geometry_from_coefficients(data, labels, beta):
    """Compute the source mode-2 geometry for an already fitted binary decoder.

    Coefficients must come from the intended source fit. This function neither
    fits a classifier nor returns prediction accuracy. Labels enforce the
    source's equal-size contiguous class layout before positional projections.
    """
    data = _real_array(data, "data")
    if data.ndim != 2 or data.shape[1] < 2 or data.shape[0] < 4 or data.shape[0] % 2:
        raise ValueError("data must be an even number of rows >=4 and >=2 neurons")
    n, p = data.shape
    labels = _real_array(labels, "labels", (n,))
    expected = np.repeat([0, 1], n // 2)
    if not np.array_equal(labels, expected):
        raise ValueError("source layout requires equal class blocks: all 0 then all 1")
    beta = _real_array(beta, "beta", (p,))
    magnitude = float(np.max(np.abs(beta)))
    if magnitude == 0:
        raise ValueError("a zero coefficient vector does not define a signal axis")
    scaled = beta / magnitude
    signal_axis = scaled / np.linalg.norm(scaled)
    # A linear hyperplane's normal is beta. This removes the source's random
    # QR construction; angles and projection SDs are invariant to its +/- sign.
    centered = data - data.mean(axis=0)
    covariance = centered.T @ centered / (n - 1)
    if not np.isfinite(covariance).all():
        raise ValueError("data overflowed covariance calculation")
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    spectral_scale = float(np.max(np.abs(eigenvalues)))
    tolerance = np.finfo(float).eps * max(n, p) * spectral_scale
    leading_gap = float(eigenvalues[-1] - eigenvalues[-2])
    unique_axis = spectral_scale > 0 and leading_gap > tolerance
    if unique_axis:
        noise_axis = eigenvectors[:, -1]
        # Fix the arbitrary eigenvector sign for deterministic serialization.
        if noise_axis[np.argmax(np.abs(noise_axis))] < 0:
            noise_axis = -noise_axis
        cosine = min(1.0, abs(float(signal_axis @ noise_axis)))
        angle = math.acos(cosine)
    else:
        noise_axis, angle = None, None

    # This is the source's inverse-eigenvalue sum, not a pseudoinverse or ridge.
    singular_values = np.linalg.svd(covariance, compute_uv=False)
    nonsingular = bool(singular_values[-1] > tolerance)
    if nonsingular:
        precision = math.sqrt(float(np.sum((eigenvectors.T @ signal_axis) ** 2 / eigenvalues)))
    else:
        precision = None
    projections = data @ signal_axis
    if not np.isfinite(projections).all():
        raise ValueError("data overflowed projection calculation")
    per_class_sd = [float(np.std(projections[:n // 2], ddof=1)),
                    float(np.std(projections[n // 2:], ddof=1))]
    if not np.isfinite(per_class_sd).all():
        raise ValueError("data overflowed projection standard deviation")
    return {
        "signal_axis": signal_axis.tolist(),
        "noise_axis": None if noise_axis is None else noise_axis.tolist(),
        "noise_axis_status": "unique" if unique_axis else "non_unique_at_numerical_tolerance",
        "angle_radians": angle,
        "angle_degrees": None if angle is None else math.degrees(angle),
        "covariance": covariance.tolist(),
        "covariance_normalization": "sample_n_minus_1_pooled_across_classes",
        "eigenvalues_ascending": eigenvalues.tolist(),
        "spectral_tolerance": tolerance,
        "projected_precision": precision,
        "precision_status": "finite" if nonsingular else "singular_at_numerical_tolerance",
        "projection_sd_by_class": per_class_sd,
        "mean_projection_sd": sum(per_class_sd) / 2,
        "rows": n,
        "neurons": p,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("replay", "geometry"))
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text())
    if args.operation == "replay":
        result = replay_simulation(payload)
    else:
        if not isinstance(payload, dict) or set(payload) != {"data", "labels", "beta"}:
            raise ValueError("geometry input requires exactly data, labels, beta")
        result = geometry_from_coefficients(**payload)
    # A final run's input cannot be silently overwritten by a requested output.
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
