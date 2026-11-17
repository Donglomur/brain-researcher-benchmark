"""Select the source tied-shape predictor from already computed loss grids.

No loss generation, fitting, split creation, target loading, or Spearman scoring
is performed here. See README.md for the finite, unique-minimum domain.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path

import numpy as np


class SelectionError(ValueError):
    """The supplied grid cannot establish an unambiguous source selection."""


def _require(condition, message):
    if not condition:
        raise SelectionError(message)


def _numeric(value, name):
    result = np.asarray(value)
    _require(result.dtype.kind in "iuf", f"{name} must be real numeric")
    with np.errstate(over="ignore", invalid="ignore"):
        result = np.asarray(result, dtype=np.float64)
    _require(np.isfinite(result).all(), f"{name} must be finite float64 values")
    return result


def _axis(value, name, positive=False, nonnegative=False):
    result = _numeric(value, name)
    _require(result.ndim == 1 and result.size > 0, f"{name} must be a nonempty vector")
    _require(len(np.unique(result)) == len(result), f"{name} contains duplicate coordinates")
    if positive:
        _require(np.all(result > 0), f"{name} must be positive")
    if nonnegative:
        _require(np.all(result >= 0), f"{name} must be nonnegative")
    return result


def _unique_minimum(values, context):
    minimum = float(np.min(values))
    locations = np.argwhere(values == minimum)
    _require(len(locations) == 1, f"ambiguous minimum in {context}; native myminall tie policy is unresolved")
    return tuple(int(i) for i in locations[0]), minimum


def select_tied_shape(loss, *, intper_sec, delay_sec_start, shape,
                      boundstrength, channel_ids, rates):
    """Choose each channel's shape, then that channel/rate's nuisance parameters.

    ``loss`` is [rate, width, delay, shape, boundary strength, channel]. The
    final five axes are exactly those documented in the source tie_shape.m.
    Coordinates are shared across the two rates, as asserted by that source.
    Each input must concern one source segment split; this operation never
    combines splits. Grid provenance and segment membership are operator duties.
    """
    widths = _axis(intper_sec, "intper_sec", positive=True)
    delays = _axis(delay_sec_start, "delay_sec_start")
    shapes = _axis(shape, "shape", positive=True)
    bounds = _axis(boundstrength, "boundstrength", nonnegative=True)
    rate_values = _axis(rates, "rates", positive=True)
    canonical_rates = np.array([1 / math.sqrt(3), math.sqrt(3)])
    _require(rate_values.shape == (2,) and np.array_equal(rate_values, canonical_rates),
             "rates must be the source order [1/sqrt(3), sqrt(3)]")
    _require(isinstance(channel_ids, (list, tuple)) and len(channel_ids) > 0,
             "channel_ids must be a nonempty ordered list")
    _require(all(isinstance(c, str) and c.strip() for c in channel_ids),
             "channel_ids must contain nonempty strings")
    _require(len(set(channel_ids)) == len(channel_ids), "channel_ids must be unique")
    tensor = _numeric(loss, "loss")
    expected_shape = (2, len(widths), len(delays), len(shapes), len(bounds), len(channel_ids))
    _require(tensor.shape == expected_shape,
             "loss axes must be [rate, width, delay, shape, boundary strength, channel] with complete coordinates")

    # Minimize nuisance parameters BEFORE pooling the rates. A common width
    # would change the source predictor and its absolute-time/structure contrast.
    per_rate_shape_loss = np.min(tensor, axis=(1, 2, 4))  # rate, shape, channel
    joint = np.empty((len(shapes), len(channel_ids)), dtype=float)
    for si in range(len(shapes)):
        for ci in range(len(channel_ids)):
            try:
                joint[si, ci] = math.fsum(float(v) for v in per_rate_shape_loss[:, si, ci])
            except OverflowError as exc:
                raise SelectionError("sum of rate-specific minimum losses overflows float64") from exc
            _require(math.isfinite(joint[si, ci]), "joint shape loss must be finite")

    rows = []
    for ci, channel in enumerate(channel_ids):
        (si,), shape_loss = _unique_minimum(joint[:, ci], f"shared shape for channel {channel}")
        for ri, rate in enumerate(rate_values):
            (wi, di, bi), selected_loss = _unique_minimum(
                tensor[ri, :, :, si, :, ci], f"nuisance parameters for channel {channel}, rate index {ri}")
            rows.append({
                "channel_id": channel,
                "rate_index": ri,
                "speech_rate": float(rate),
                "best_intper_sec_tiedshape": float(widths[wi]),
                "best_delay_sec_start_tiedshape": float(delays[di]),
                "best_shape_tiedshape": float(shapes[si]),
                "best_boundstrength_tiedshape": float(bounds[bi]),
                "parameter_indices_zero_based": [wi, di, si, bi],
                "selected_loss": selected_loss,
                "summed_rate_minimum_shape_loss": shape_loss,
            })
    return {
        "task_id": "PAPER-FIND-024",
        "operation": "source_tied_shape_selection_finite_unique_minima",
        "loss_axis_order": ["rate", "width", "delay", "shape", "boundary_strength", "channel"],
        "rows": rows,
        "shape_loss": joint.tolist(),
        "scope": "Loss-grid parameter selection only; no source split, loss, native parity, or paper endpoint qualification.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("loss_grid", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected-sha256", required=True,
                        help="Operator-frozen hash of the input NPZ; does not authenticate its scientific origin")
    args = parser.parse_args(argv)
    raw = args.loss_grid.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    _require(digest == args.expected_sha256, "loss-grid SHA256 mismatch")
    required = {"loss", "intper_sec", "delay_sec_start", "shape", "boundstrength", "channel_ids", "rates"}
    with np.load(io.BytesIO(raw), allow_pickle=False) as packed:
        _require(set(packed.files) == required, "NPZ must contain exactly the documented seven arrays")
        channels = packed["channel_ids"]
        _require(channels.ndim == 1 and channels.dtype.kind == "U", "channel_ids must be a Unicode vector")
        result = select_tied_shape(packed["loss"],
                                  **{key: packed[key] for key in required - {"loss", "channel_ids"}},
                                  channel_ids=channels.tolist())
    result["input_sha256"] = digest
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
