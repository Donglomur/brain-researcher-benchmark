"""Bind original mixed readout representations to the score packet's factors.

This optional audit verifies supplied-array algebra, not fitting or historical
component identity. It preserves the separate original linear-readout audit.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import numpy as np


AUDIT_PATH = Path(__file__).with_name("audit_packet.py")
AUDIT_SHA256 = "75a2ace959cb8a6f5ff54936ee8b4a3cc5ba8e815a6cef451ff16b42da8eaa30"
MIXED = ("mixed_trial_only", "mixed_time_only", "mixed_slice12_1")
FEATURES = 182
BLOCK_BINS = 10


def original_audit():
    """Load the preserved audit; importing this module alone reads no artifacts."""
    if hashlib.sha256(AUDIT_PATH.read_bytes()).hexdigest() != AUDIT_SHA256:
        raise ValueError("original audit dependency identity differs")
    spec = importlib.util.spec_from_file_location("slice_representation_original_audit", AUDIT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_mixed_representations(packet, representations):
    """Check all 511 trials and 150 bins against the packet's 12+1 factors.

    ``packet`` must be an admitted original ``AuditPacket``; its core is the
    original ``bridge.Packet``. Inputs must remain immutable throughout this
    call and any subsequent linear-readout verification. Only the three mixed
    representation slots are checked here; no score or model fit is computed.
    """
    q = original_audit()
    core = packet.core
    q.need(packet.manifest["core_manifest_sha256"] == core.manifest_sha256
           and packet.manifest["plan_sha256"] == q.b.digest(core.plan),
           "mixed audit core/plan binding differs")
    q.need(set(MIXED) <= set(representations), "all three mixed representations required")
    shapes = {"trial_weights": (12, 511), "trial_slices": (12, FEATURES, 150),
              "time_vector": (1, 150), "preparatory_trial_neuron_slice": (511, FEATURES)}
    factors, factor_pins = {}, {}
    for name, shape in shapes.items():
        value = q.b.real(core.get("components/" + name), name, shape)
        q.need(np.all(value >= 0), "nonnegative exported factors required: " + name)
        factor_pins[name] = q.a.array_digest(value)
        factors[name] = value
    arrays = {}
    for name in MIXED:
        value = q.b.real(representations[name], name, (150, 511, FEATURES))
        q.need(value.dtype.str == "<f8", "mixed representations require little-endian float64")
        q.need(q.a.array_digest(value) == packet.manifest["representation_pins"][name],
               "mixed representation identity differs: " + name)
        arrays[name] = value

    # Follow the producer's component order and products, with bounded working
    # arrays. Preserve each product's supplied factor dtype before adding it to
    # float64, exactly as the original producer does for float32 factor exports.
    # The block is time x trial x neuron, as supplied to the readout.
    weights, slices = factors["trial_weights"], factors["trial_slices"]
    vector, matrix = factors["time_vector"][0], factors["preparatory_trial_neuron_slice"]
    with np.errstate(over="ignore", invalid="ignore"):
        for start in range(0, 150, BLOCK_BINS):
            stop = min(start + BLOCK_BINS, 150)
            trial = np.zeros((stop - start, 511, FEATURES), dtype=np.float64)
            for component in range(12):
                trial += weights[component][None, :, None] * slices[component, :, start:stop].T[:, None, :]
            time = vector[start:stop, None, None] * matrix[None, :, :]
            for name, expected in ((MIXED[0], trial), (MIXED[1], time), (MIXED[2], trial + time)):
                q.need(np.isfinite(expected).all(), "unrepresentable mixed reconstruction: " + name)
                q.need(np.allclose(arrays[name][start:stop], expected, **q.TOLERANCE),
                       "mixed factor reconstruction differs: " + name)
    return {"schema": "slicetca-mixed-factor-representation-audit-v1",
            "status": "consistent_with_supplied_factors",
            "audit_manifest_sha256": packet.manifest_sha256,
            "core_manifest_sha256": core.manifest_sha256,
            "factor_pins": factor_pins,
            "representation_pins": {name: dict(packet.manifest["representation_pins"][name]) for name in MIXED},
            "checked_shape": [150, 511, FEATURES], "trial_components": 12, "time_components": 1,
            "arithmetic_tolerance": dict(q.TOLERANCE), "fitting_reexecuted": False,
            "representation_fitting_authenticated": False, "historical_component_identity_authenticated": False,
            "scientific_admission": False}


def verify_original_linear_result(packet, bank, representations):
    """Combine factor linkage with the existing complete original readout audit."""
    linkage = verify_mixed_representations(packet, representations)
    linear = original_audit().verify_original_linear_readout(packet, bank, representations)
    return {"schema": "slicetca-linked-original-linear-result-audit-v1",
            "mixed_representation_linkage": linkage, "linear_readout": linear,
            "fit_execution_authenticated": False, "representation_fitting_authenticated": False,
            "scientific_admission": False}
