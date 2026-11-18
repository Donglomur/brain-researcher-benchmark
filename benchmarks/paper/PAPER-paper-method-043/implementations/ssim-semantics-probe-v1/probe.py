"""Diagnose NeuroPictor's grayscale SSIM call on generated inputs only.

This is an operator environment probe, never an image scorer or a scientific
admission decision. It does not select the environment used for the paper.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import inspect
import json
import math
import numbers
from pathlib import Path
import warnings


TASK_ID = "PAPER-paper-method-043"
AUTHOR_COMMIT = "b676b5be320ebb1b12919afd4cf6152e2c45db5d"
CALL_KWARGS = {
    "multichannel": True,
    "gaussian_weights": True,
    "sigma": 1.5,
    "use_sample_covariance": False,
    "data_range": 1.0,
}
MODES = ("two_dimensional_spatial", "last_axis_as_channels")
TOLERANCES = {"float32": 2e-5, "float64": 2e-10}


class ProbeError(ValueError):
    pass


def _image(value):
    if not isinstance(value, (list, tuple)) or len(value) < 11:
        raise ProbeError("generated reference needs at least 11 rows")
    width = len(value[0]) if isinstance(value[0], (list, tuple)) else 0
    if width < 11 or any(not isinstance(r, (list, tuple)) or len(r) != width for r in value):
        raise ProbeError("generated reference needs a rectangular width of at least 11")
    result = []
    for row in value:
        converted = []
        for x in row:
            if isinstance(x, bool) or not isinstance(x, (int, float)):
                raise ProbeError("reference pixels must be finite real numbers")
            x = float(x)
            if not math.isfinite(x) or not 0 <= x <= 1:
                raise ProbeError("reference pixels must be finite and in [0,1]")
            converted.append(x)
        result.append(converted)
    return result


def reference_scores(real, predicted):
    """Independent scalar Gaussian/population SSIM for two explicit hypotheses.

    Only valid interiors are computed, so no padding implementation is needed.
    Spatial mode uses both image axes and crops both by five. Channel mode
    filters/crops the first axis and averages all columns, including edge ones.
    """
    x, y = _image(real), _image(predicted)
    if len(x) != len(y) or len(x[0]) != len(y[0]):
        raise ProbeError("image shapes differ")
    h, w = len(x), len(x[0])
    kernel = [math.exp(-0.5 * (k / 1.5) ** 2) for k in range(-5, 6)]
    denominator = math.fsum(kernel)
    kernel = [z / denominator for z in kernel]

    def score(terms):
        mx = math.fsum(weight * a for weight, a, b in terms)
        my = math.fsum(weight * b for weight, a, b in terms)
        vx = math.fsum(weight * a * a for weight, a, b in terms) - mx * mx
        vy = math.fsum(weight * b * b for weight, a, b in terms) - my * my
        cov = math.fsum(weight * a * b for weight, a, b in terms) - mx * my
        return ((2 * mx * my + .01 ** 2) * (2 * cov + .03 ** 2)
                / ((mx * mx + my * my + .01 ** 2) * (vx + vy + .03 ** 2)))

    spatial, channel = [], []
    for i in range(5, h - 5):
        for j in range(w):
            channel.append(score([(a, x[i + u - 5][j], y[i + u - 5][j])
                                  for u, a in enumerate(kernel)]))
        for j in range(5, w - 5):
            spatial.append(score([(a * b, x[i + u - 5][j + v - 5], y[i + u - 5][j + v - 5])
                                  for u, a in enumerate(kernel) for v, b in enumerate(kernel)]))
    return {MODES[0]: math.fsum(spatial) / len(spatial),
            MODES[1]: math.fsum(channel) / len(channel)}


def generated_pairs():
    """Asymmetric patterns expose both filtering axis and border averaging."""
    h, w = 23, 29
    x = [[.1 + .8 * ((7 * i + 11 * j + i * j) % 31) / 30 for j in range(w)] for i in range(h)]
    y = [[.15 + .65 * ((5 * i + 3 * j * j + 2 * i * j) % 37) / 36 for j in range(w)] for i in range(h)]
    a = [[.2 + .5 * ((i + j) % 2) for j in range(w)] for i in range(h)]
    b = [[a[i][j] if 5 <= j < w - 5 else .9 - a[i][j] / 2 for j in range(w)] for i in range(h)]
    return (("asymmetric_texture", x, y), ("horizontal_edge_perturbation", a, b))


def probe_callable(ssim, *, runtime=None):
    """Observe the supplied trusted operator callable; never infer history.

    Explicit hypotheses are classified only if every probe/dtype has one
    consistent match. A version string is recorded but never selects a mode.
    """
    import numpy as np
    observations = []
    for dtype_name, tolerance in TOLERANCES.items():
        for name, x, y in generated_pairs():
            real, predicted = np.asarray(x, dtype=dtype_name), np.asarray(y, dtype=dtype_name)
            before_real, before_predicted = real.copy(), predicted.copy()
            expected = reference_scores(real.tolist(), predicted.tolist())
            row = {"fixture": name, "dtype": dtype_name, "shape": list(real.shape),
                   "absolute_tolerance": tolerance, "reference": expected}
            # If these fixtures cease to discriminate, never accept an axis.
            if abs(expected[MODES[0]] - expected[MODES[1]]) <= 20 * tolerance:
                raise ProbeError("generated fixture does not distinguish SSIM hypotheses")
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                try:
                    value = ssim(predicted, real, **dict(CALL_KWARGS))
                    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Real):
                        raise ProbeError("SSIM must return a real numeric scalar, not boolean/string/array")
                    value = float(value)
                    if not math.isfinite(value):
                        raise ProbeError("SSIM returned a nonfinite value")
                    if not np.array_equal(real, before_real) or not np.array_equal(predicted, before_predicted):
                        raise ProbeError("SSIM mutated its input")
                    matches = [mode for mode in MODES if abs(value - expected[mode]) <= tolerance]
                    row.update(status="observed", value=value, matching_hypotheses=matches)
                except Exception as exc:
                    row.update(status="rejected_or_raised", exception_type=type(exc).__name__,
                               exception_message=str(exc)[:240], matching_hypotheses=[])
                row["warnings"] = [{"category": z.category.__name__, "message": str(z.message)[:240]}
                                   for z in caught[:4]]
                row["warning_count"] = len(caught)
            observations.append(row)
    accepted = [r["matching_hypotheses"][0] for r in observations if len(r["matching_hypotheses"]) == 1]
    observed_mode = accepted[0] if len(accepted) == len(observations) and len(set(accepted)) == 1 else None
    return {
        "schema": "neuropictor-ssim-semantics-probe/v1", "task_id": TASK_ID,
        "author_commit": AUTHOR_COMMIT, "status": "generated_environment_diagnostic_only",
        "author_call_kwargs": dict(CALL_KWARGS), "observed_semantics": observed_mode,
        "all_generated_calls_classified_consistently": observed_mode is not None,
        "runtime": runtime or {}, "observations": observations,
        "historical_environment_identified": False, "native_metric_parity_verified": False,
        "paper_reproduction_established": False, "paper_improvement_established": False,
        "existing_scorer_policy_changed": False,
        "limits": ["Generated grayscale inputs only; no NSD images, fMRI, candidate outputs or model calls.",
                   "A present callable's behavior cannot identify the historical paper environment.",
                   "This does not qualify rgb2gray, resize, dtype, model-feature or full-panel parity.",
                   "Runtime declarations and source hashes bind observations, not historical authenticity."],
    }


def installed_runtime(ssim):
    """Bind the called wrapper and exposed implementation source separately.

    Decorators can copy the implementation's module/name onto wrapper code in a
    different file. Neither advertised metadata nor package version identifies
    the code file. The exposed __wrapped__ chain is bounded to 16 callables and
    unique source-file reads to 2 MiB total. Hidden closures/imports are outside
    this fingerprint's scope.
    """
    versions = {name: importlib.metadata.version(name) for name in ("numpy", "scipy", "scikit-image")}
    chain, seen = [], set()
    current = ssim
    while True:
        if id(current) in seen or len(chain) >= 16:
            raise ProbeError("cyclic or overlong exposed SSIM wrapper chain")
        chain.append(current)
        seen.add(id(current))
        if not hasattr(current, "__wrapped__"):
            break
        current = current.__wrapped__
    if inspect.unwrap(ssim) is not chain[-1]:
        raise ProbeError("SSIM wrapper chain changed during inspection")
    cache, consumed = {}, 0
    records = []
    for function in chain:
        code = getattr(function, "__code__", None)
        record = {"advertised_module": getattr(function, "__module__", None),
                  "advertised_qualname": getattr(function, "__qualname__", None),
                  "code_filename": getattr(code, "co_filename", None),
                  "code_first_line": getattr(code, "co_firstlineno", None)}
        try:
            source_path = inspect.getsourcefile(function)
        except (TypeError, OSError):
            source_path = None
        if source_path is None:
            record["source"] = {"status": "unavailable", "reason": "no inspectable Python source file"}
        else:
            path = Path(source_path).absolute()
            key = str(path)
            if key not in cache:
                try:
                    size = path.stat().st_size
                    if consumed + size > 2 * 1024 * 1024:
                        raise ProbeError("installed SSIM sources exceed total 2MiB fingerprint bound")
                    with path.open("rb") as handle:
                        payload = handle.read(size + 1)
                    consumed += len(payload)
                    if len(payload) != size:
                        raise ProbeError("installed SSIM source changed during fingerprint")
                    cache[key] = {"status": "fingerprinted", "path": key,
                                  "bytes": size, "sha256": hashlib.sha256(payload).hexdigest()}
                except OSError as exc:
                    cache[key] = {"status": "unavailable", "path": key,
                                  "reason": type(exc).__name__}
            record["source"] = cache[key]
        records.append(record)
    return {"packages": versions, "called_callable": records[0],
            "unwrapped_implementation": records[-1], "exposed_wrapped_chain": records,
            "fingerprinted_unique_source_bytes": consumed,
            "identity_scope": "currently installed exposed callable chain, not historical runtime or complete dependencies",
            "metadata_note": "advertised module/name may be copied by decorators; source paths identify the inspected code files"}


def write_report(path, report):
    content = json.dumps(report, indent=2, allow_nan=False) + "\n"
    with Path(path).open("x", encoding="utf-8") as handle:
        handle.write(content)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        from skimage.metrics import structural_similarity
        result = probe_callable(structural_similarity, runtime=installed_runtime(structural_similarity))
        write_report(args.output, result)
        return 0 if result["all_generated_calls_classified_consistently"] else 2
    except (ImportError, importlib.metadata.PackageNotFoundError, OSError, ProbeError, ValueError) as exc:
        parser.exit(2, f"SSIM environment diagnostic failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
