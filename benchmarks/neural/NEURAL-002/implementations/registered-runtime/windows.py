"""Original fixed-window extraction from an authenticated native reader.

Reader protocol: reader(start_zero_based, stop_exclusive) returns numeric
62×(stop-start) microvolt array in the certified channel order. The qualified
native BrainVision provider and its payload authentication are explicit gates;
this API never treats a callback as an authorization or sandbox.
"""
from contract import CHANNELS, SAMPLES, RATE, require


def extract(reader, row, certificate, *, premarker=False):
    import numpy as np
    require(certificate.get("sampling_hz") == RATE, "native sample rate must be600Hz")
    names = certificate.get("channel_names")
    require(isinstance(names, list) and len(names) == CHANNELS and len(set(names)) == CHANNELS,
            "certified unique62-channel order required")
    require(certificate.get("units") == "uV", "certified native scaling required")
    require(certificate.get("source_commit") == "d2e09f610d267b8b3679997f8bc4e52fe6ca402a",
            "wrong source version")
    require(certificate.get("policy") == "raw_fixed_window_v1", "preprocessing policy")
    require(certificate.get("bad_channel_policy") == "global_zero_PO4_TP8_before_average_reference",
            "known damaged channels must use common target-independent policy")
    require("PO4" in names and "TP8" in names, "named damaged-channel audit")
    start = row["start"] - (SAMPLES if premarker else 0)
    require(type(start) is int and start >= 0, "window starts outside recording")
    x = np.array(reader(start, start + SAMPLES), dtype=np.float64, copy=True)
    require(x.shape == (CHANNELS, SAMPLES) and np.isfinite(x).all(), "invalid raw window")
    # Fixed source amendment: remove these two channels for everyone. Avoid
    # person-dependent masks and unspecified neighbor interpolation. Keep62 slots.
    removed = (names.index("PO4"), names.index("TP8"))
    good = [i for i in range(CHANNELS) if i not in removed]
    x[removed[0], :] = 0
    x[removed[1], :] = 0
    x[good, :] -= x[good, :].mean(axis=0, keepdims=True)
    require(np.isfinite(x).all(), "nonfinite referenced window")
    result = x.astype(np.float32)
    require(np.isfinite(result).all(), "float32 window overflow")
    return result
