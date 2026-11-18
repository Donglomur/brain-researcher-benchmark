"""Operator-only AJILE source preparation for the existing RF endpoint.

This is an in-memory component, not a native NetCDF reader, participant runner,
or evidence that the paper's event/day roster has been recovered.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np

_spec = importlib.util.spec_from_file_location(
    "_ajile_rf_preparation_endpoint", Path(__file__).with_name("endpoint.py")
)
endpoint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(endpoint)
require = endpoint.require
SCHEMA = "ajile-source-rf-preparation-v1"


def _numeric(value, name):
    array = np.asarray(value)
    require(array.dtype.kind in "fiu", f"{name} must be real numeric data")
    return array


def prepare_arrays(native, *, event_days, times, channel_coordinates, row_ids,
                   participant, source_sha256, kind):
    """Preserve every event while reproducing source label/split/normalization.

    ``native`` must be a single native variable in events/channels/time order,
    including its final label channel. Labels come from original time index 0,
    BEFORE selecting the inclusive [-2,+2] signal interval. Caller owns native
    extraction, byte authentication and admission; a supplied hash is not proof.
    Returned arrays and metadata are operator-private and include query truth.
    """
    require(participant in endpoint.PARTICIPANTS, "unknown source participant")
    require(kind in ("generated_control", "authentic_input"), "explicit input kind required")
    require(endpoint.valid_digest(source_sha256), "source SHA256 required")
    data = _numeric(native, "native tensor")
    require(data.ndim == 3 and data.shape[0] >= 2 and data.shape[1] >= 3
            and data.shape[2] >= 2, "expected events/channels-including-label/time")
    time = _numeric(times, "times")
    require(time.shape == (data.shape[2],) and np.isfinite(time).all()
            and np.all(time[1:] > time[:-1]), "strictly increasing finite native time grid required")
    coords = _numeric(channel_coordinates, "channel coordinates")
    require(coords.dtype.kind in "iu" and coords.shape == (data.shape[1],) and np.isfinite(coords).all()
            and len(np.unique(coords)) == len(coords), "unique integer native channel coordinates required")
    # Dataset[dict(...)] uses positional selection. The author's label index is
    # the VALUE of the final channel coordinate, not an unconditional -1.
    # Refuse alternative coordinate conventions rather than silently repairing.
    require(coords[-1] == data.shape[1] - 1, "source final channel coordinate must address the final positional channel")
    days = _numeric(event_days, "event days")
    require(days.shape == (len(data),), "one native day label per event required")
    native_ids = endpoint.row_ids(row_ids, len(data), "native row IDs")
    train_index, test_index = endpoint.source_day_indices(days)
    # The pinned loader squeezes each selected array before operating on three
    # axes. Do not silently repair its unsupported singleton event partitions.
    require(len(train_index) >= 2 and len(test_index) >= 2,
            "source squeeze requires nonsingleton training and test partitions")
    keep = np.flatnonzero((time >= -2.0) & (time <= 2.0))
    require(len(keep) >= 2, "source inclusive signal interval has insufficient samples")
    channels = data.shape[1] - 1
    if kind == "authentic_input":
        require(channels == endpoint.CHANNELS[participant], "original participant channel count required")
        require(len(keep) == 1001 and np.allclose(time[keep], np.linspace(-2, 2, 1001), rtol=0, atol=1e-10),
                "original 1001-sample 250Hz inclusive window required")
    labels_native = data[:, -1, 0]
    require(np.isfinite(labels_native).all() and np.isin(labels_native, [1, 2]).all(),
            "source label codes at native time index zero must be 1/2")
    labels = labels_native - 1.0
    # Do not inspect unused signal times or other label times: the source does
    # not use them. Do not trim trials or apply quality masks to decoder input.
    signal = data[:, :-1, :][:, :, keep]
    require(np.isfinite(signal).all(), "selected source signals must be finite")
    train, test = signal[train_index], signal[test_index]
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        ranges = np.ptp(train, axis=2)
        test_ranges = np.ptp(test, axis=2)
        lower = np.percentile(ranges, 25, axis=0, keepdims=True)
        upper = np.percentile(ranges, 75, axis=0, keepdims=True)
        width = upper - lower
        low_fence, high_fence = lower - 5.0 * width, upper + 5.0 * width
        bad_train = (ranges == 0) | (ranges < low_fence) | (ranges > high_fence)
        bad_test = (test_ranges == 0) | (test_ranges < low_fence) | (test_ranges > high_fence)
        # Source uses masked-array population statistics, not quality filtering
        # of the event roster, label vector, or RF denominator.
        full_mask = np.broadcast_to(bad_train[:, :, None], train.shape)
        masked_train = np.ma.array(train, mask=full_mask)
        mean_masked = np.ma.mean(masked_train, axis=(0, 2), keepdims=True)
        scale_masked = np.ma.std(masked_train, axis=(0, 2), keepdims=True)
        require(not np.ma.getmaskarray(mean_masked).any()
                and not np.ma.getmaskarray(scale_masked).any(), "undefined training normalization")
        mean, scale = np.asarray(mean_masked), np.asarray(scale_masked)
        require(np.isfinite(mean).all() and np.isfinite(scale).all() and np.all(scale > 0),
                "finite positive source training scale required")
        train_z = np.asarray((train - mean_masked) / scale_masked)
        test_z = np.asarray((test - mean_masked) / scale_masked)
    require(np.isfinite(ranges).all() and np.isfinite(test_ranges).all()
            and np.isfinite(low_fence).all() and np.isfinite(high_fence).all(),
            "source range calculation overflow")
    require(np.isfinite(train_z).all() and np.isfinite(test_z).all(), "standardization overflow")
    # Confirm compatibility with the endpoint's float32 boundary without
    # discarding source precision from this intermediate operator artifact.
    for name, array in (("train_z", train_z), ("test_z", test_z), ("mean", mean), ("scale", scale)):
        endpoint.float32(array, name)
    ids = np.asarray(native_ids)
    arrays = {
        "train_z": train_z, "test_z": test_z,
        "train_mean": mean.reshape(channels), "train_scale": scale.reshape(channels),
        "train_labels": labels[train_index], "test_labels": labels[test_index],
        "train_row_ids": ids[train_index], "test_row_ids": ids[test_index],
        "native_days": days.copy(), "native_row_ids": ids,
        "source_sha256": np.array(source_sha256),
        "train_quality": ~bad_train, "test_quality": ~bad_test,
        "selected_times": time[keep].copy(),
    }
    metadata = {
        "schema": SCHEMA, "kind": kind, "participant": participant,
        "source_revision": endpoint.SOURCE_REVISION, "source_sha256": source_sha256,
        "native_events": len(data), "train_events": len(train), "test_events": len(test),
        "channels": channels, "samples_per_event": len(keep),
        "train_source_indices": train_index.tolist(), "test_source_indices": test_index.tolist(),
        "selected_native_time_indices": keep.tolist(),
        "source_train_days": np.unique(days[train_index]).tolist(),
        "source_test_day": int(days[test_index][0]), "label_native_time_index": 0,
        "array_identities": {name: endpoint.array_digest(value) for name, value in arrays.items()},
        "numpy": np.__version__, "role": "operator_only_contains_query_truth",
        "historical_paper_day7_mapping": "unresolved",
        "qualification": "construction_only_no_authentic_execution_or_scientific_claim",
    }
    return arrays, metadata


def source_condition(prepared, *, dropout, repeat):
    """Source unmasked observed-channel condition; operator must isolate cases.

    Quality masks affect training normalization but the source RF experiment
    does not multiply the inference condition by observed-channel quality.
    The returned tensor is not an independently qualified participant packet.
    """
    z = endpoint.float32(prepared["test_z"], "test_z")
    require(z.ndim == 3 and min(z.shape) > 0, "expected complete test tensor")
    observed, choice_order = endpoint.observed_channels(int(z.shape[1]), dropout, repeat)
    mask = np.broadcast_to(observed[None, :, None], z.shape).astype(np.float32)
    return np.concatenate((mask, mask * z), axis=1), choice_order.tolist()
