"""Complete current-code DUNL raster curves; mathematical construction only.

This operator-side component does not select publication settings, train a
model, deserialize Torch/pickle objects, or qualify a scientific comparison.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import stat
import types


SCHEMA = "dunl_smoothed_raster_current_defaults_v1"
PROFILE = "dunl_current_code_defaults_30_20_11_576_v1"
RESPONSE_SAMPLES = 600
CODE_SAMPLES = 576
TAUS = (1, 10, 20, 30)
# The source requests numpy.linspace(0.025, 0.3, 20). Binary floating-point
# reduction/threshold equality parity with the author environment is NOT claimed.
THRESHOLDS = tuple(0.025 + i * ((0.3 - 0.025) / 19) for i in range(19)) + (0.3,)
ENDPOINT_BYTES = 9780
ENDPOINT_SHA256 = "ddfa29861f8d942b4dd37bac4ca8163c084e7be476bdf5ddee2e31c40b619df0"


class Refusal(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Refusal(message)


def keys(value, expected):
    require(type(value) is dict and set(value) == set(expected), "unexpected fields")


def normalized_vector(value, length):
    require(type(value) is list and len(value) == length, "complete vector required")
    require(all(type(x) in (float, int) and 0 <= x <= 1 and math.isfinite(x)
                for x in value), "finite normalized observations required")
    return value


@lru_cache(maxsize=1)
def endpoint():
    """Execute the already published endpoint's exact captured source bytes."""
    path = Path(__file__).resolve().parent.parent / "dunl-historical-events-v1" / "historical_events.py"
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_size == ENDPOINT_BYTES,
            "published endpoint missing or changed")
    with path.open("rb") as handle:
        raw = handle.read(ENDPOINT_BYTES + 1)
    require(len(raw) == ENDPOINT_BYTES and hashlib.sha256(raw).hexdigest() == ENDPOINT_SHA256,
            "published endpoint identity mismatch")
    module = types.ModuleType("dunl_published_historical_endpoint")
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def smoothing_kernel(tau):
    """Source odd-length normalized (1-exp(-t))*exp(-t/tau) kernel."""
    require(type(tau) is int and tau in TAUS, "unsupported source smoothing setting")
    count = int(2.5 * tau + 1)
    if count % 2 == 0:
        count += 1
    times = [i * (2.5 * tau) / (count - 1) for i in range(count)]
    values = [(1 - math.exp(-t)) * math.exp(-t / tau) for t in times]
    total = math.fsum(values)
    return tuple(x / total for x in values)


def smooth(values, tau):
    """Full 600-bin zero-padded source convolution, with no phase correction.

    The author flips the kernel before conv1d correlation with same padding.
    For odd kernel length L this is sum_k x[t + (L-1)/2 - k] * h[k].
    The source's reduceat step is one and therefore retains every input sample.
    """
    normalized_vector(values, RESPONSE_SAMPLES)
    kernel = smoothing_kernel(tau)
    center = len(kernel) // 2
    # Exactly-zero observations have an exactly-zero convolution; this shortcut
    # preserves the full length and is not a row or bin eligibility rule.
    if not any(values):
        return [0.0] * RESPONSE_SAMPLES
    result = []
    for t in range(RESPONSE_SAMPLES):
        result.append(math.fsum(values[t + center - k] * weight
                                for k, weight in enumerate(kernel)
                                if 0 <= t + center - k < RESPONSE_SAMPLES))
    return result


def peak_indices(values, height):
    """Finite-signal find_peaks semantics with only inclusive minimum height.

    Plateaus use their midpoint rounded down; boundary plateaus are excluded.
    No distance, prominence, smoothing, or minimum event count is added here.
    """
    require(type(values) is list and len(values) >= 3, "full signal required")
    require(all(type(x) in (float, int) and -1e12 <= x <= 1e12 and math.isfinite(x)
                for x in values), "finite bounded smoothed signal required")
    require(type(height) in (float, int) and 0 <= height <= 1 and math.isfinite(height),
            "finite peak height required")
    result, i = [], 1
    while i < len(values) - 1:
        if values[i - 1] < values[i]:
            end = i
            while end + 1 < len(values) and values[end + 1] == values[i]:
                end += 1
            if end < len(values) - 1 and values[end + 1] < values[i] and values[i] >= height:
                result.append((i + end) // 2)
            i = end + 1
        else:
            i += 1
    return tuple(result)


def cropped_peaks(smoothed, height):
    require(type(smoothed) is list and len(smoothed) == RESPONSE_SAMPLES,
            "peak finding precedes the 576-bin crop")
    return frozenset(i for i in peak_indices(smoothed, height) if i < CODE_SAMPLES)


def _owner_and_rasters(owner, rasters):
    h = endpoint()
    keys(owner, ("profile", "channel_ids", "trial_ids", "target_codes"))
    require(owner["profile"] == PROFILE, "unsupported geometry")
    try:
        h._ids(owner["channel_ids"], h.CHANNELS)
        keys(owner["trial_ids"], h.SPLITS)
        keys(owner["target_codes"], h.SPLITS)
        for split, count in h.SPLITS.items():
            h._ids(owner["trial_ids"][split], count)
        require(not set(owner["trial_ids"]["train"]) & set(owner["trial_ids"]["test"]),
                "trial crosses training/test roles")
        keys(rasters, ("profile", "context_id", "channel_ids", "trial_ids", "observations"))
        require(rasters["profile"] == PROFILE and rasters["context_id"] == h.context_id(owner),
                "raster context mismatch")
        require(rasters["channel_ids"] == owner["channel_ids"] and
                rasters["trial_ids"] == owner["trial_ids"], "ordered identity mismatch")
        keys(rasters["observations"], h.SPLITS)
        result = {}
        for split, count in h.SPLITS.items():
            targets, observed = owner["target_codes"][split], rasters["observations"][split]
            require(type(targets) is list and len(targets) == count and
                    type(observed) is list and len(observed) == count, "full split required")
            rows = []
            for trial in range(count):
                require(type(targets[trial]) is list and len(targets[trial]) == 1,
                        "one complete target kernel required")
                truth = h.positive_support(targets[trial][0])
                require(type(observed[trial]) is list and len(observed[trial]) == h.CHANNELS,
                        "all eleven allocated channels required")
                for channel in range(h.CHANNELS):
                    sample = observed[trial][channel]
                    require(type(sample) is list and len(sample) == 1,
                            "one observation channel axis required")
                    rows.append((truth, normalized_vector(sample[0], RESPONSE_SAMPLES)))
            result[split] = rows
    except h.InputError as exc:
        raise Refusal(str(exc)) from exc
    return h, result


def curves(owner, rasters):
    """Compute all four-by-twenty points on both complete declared splits.

    Both inputs are selected by the operator, never inferred from candidate
    outputs. No DUNL candidate point, threshold winner, train/test pooling, F1,
    confidence interval or paper-win scalar is synthesized.
    """
    h, inputs = _owner_and_rasters(owner, rasters)
    canonical = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"),
                                        ensure_ascii=True, allow_nan=False).encode("ascii")
    result = {
        "schema": SCHEMA, "profile": PROFILE, "context_id": h.context_id(owner),
        "owner_content_sha256": hashlib.sha256(canonical(owner)).hexdigest(),
        "raster_content_sha256": hashlib.sha256(canonical(rasters)).hexdigest(),
        "endpoint_sha256": ENDPOINT_SHA256, "response_samples": RESPONSE_SAMPLES,
        "code_samples": CODE_SAMPLES, "inclusive_tolerance_bins": h.TOL_BINS,
        "row_order": "trial_major_channel_minor", "splits": {},
        "publication_settings_verified": False, "source_runtime_parity_verified": False,
        "authentic_cohort_verified": False, "scientific_qualification": False,
        "content_digest_scope": "canonical in-memory inputs; not source-file authentication",
        "independent_biological_uncertainty": "not_established",
        "selected_setting": None,
    }
    for split, inputs_for_split in inputs.items():
        tau_curves = []
        for tau in TAUS:
            signals = [(truth, smooth(values, tau)) for truth, values in inputs_for_split]
            points = []
            for index, threshold in enumerate(THRESHOLDS):
                counts = [h.row_counts(truth, cropped_peaks(signal, threshold))
                          for truth, signal in signals]
                raw_counts = json.dumps(counts, sort_keys=True, separators=(",", ":"),
                                        allow_nan=False).encode("ascii")
                points.append({"threshold_index": index, "threshold": threshold,
                               **h.aggregate(counts),
                               "ordered_row_counts_sha256": hashlib.sha256(raw_counts).hexdigest()})
            tau_curves.append({"smoothing_tau": tau, "points": points})
        result["splits"][split] = {"rows": len(inputs_for_split), "curves": tau_curves}
    return result
