"""Operator-only calcium input controls for one complete NEURAL-026 case.

This constructs inputs, not predictions or evidence of matched execution. The
caller retains the complete original design and runs each view in a fresh case
boundary. Complementary-fold labels must never become participant-visible.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import types

import numpy as np

PROTOCOL_SHA256 = "cb485a93af96ca7fc1c56da596a6e0ad174a3a349cd66bc938fc8de752c46621"
MODES = ("full", "context_only", "training_trial_shift")
FIELDS = {"train_x", "train_z", "train_y", "train_id", "train_target",
          "query_x", "query_z", "query_id", "query_target"}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def load_protocol():
    path = Path(__file__).resolve().parent.parent / "delivery-source/public/protocol.py"
    need(path.is_file() and not path.is_symlink(), "Ordinary pinned protocol source")
    body = path.read_bytes()
    need(len(body) == 8505 and hashlib.sha256(body).hexdigest() == PROTOCOL_SHA256,
         "Unchanged original packet, design and training-shift protocol")
    module = types.ModuleType("neural026_control_protocol")
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def identity(array):
    """C-order identity, preserving dtype/endian information and geometry."""
    need(array.flags.c_contiguous, "Captured array must be C contiguous")
    return {"shape": list(array.shape), "dtype": array.dtype.str,
            "bytes": array.nbytes,
            "sha256": hashlib.sha256(memoryview(array).cast("B")).hexdigest()}


def build_control(packet, design, case_id, mode, *, max_array_working_bytes):
    """Return one owned read-only view and private operator metadata.

    No input is inferred from a label, fitted, dropped or selected here. The
    memory allowance is a conservative declared NumPy-array envelope, not an
    OS memory cap or complete interpreter RSS measurement. Actual execution
    still requires independently admitted resources and custody.
    """
    need(mode in MODES, "One explicit input control")
    need(type(packet) is dict and set(packet) == FIELDS,
         "Exact public packet; no query angles or hidden additional fields")
    for name, value in packet.items():
        need(type(value) is np.ndarray and value.dtype.kind in "iuf"
             and not value.dtype.hasobject,
             "Ordinary primitive numerical array: " + name)
    nbytes = sum(value.nbytes for value in packet.values())
    # One independent packet capture, temporary validity masks, and the shifted
    # training-array copy fit under twice the packet extent plus fixed overhead.
    envelope = 2 * nbytes + 1024**2
    need(type(max_array_working_bytes) is int and max_array_working_bytes >= envelope,
         "Explicit sufficient array working allowance before copying")
    protocol = load_protocol()
    protocol.validate_design(design)
    matches = [case for case in design["cases"] if case["case_id"] == case_id]
    need(len(matches) == 1, "One original complete-design case")
    case = matches[0]
    captured = {name: np.array(value, copy=True, order="C")
                for name, value in packet.items()}
    protocol.validate_packet(captured)
    for side in ("train", "query"):
        need(np.array_equal(captured[side + "_id"], case[side + "_id"]),
             "Packet identity equals the frozen case's complete " + side + " support")
    source = {name: identity(captured[name]) for name in sorted(FIELDS)}
    permutation = None
    if mode == "context_only":
        captured["train_x"].fill(0)
        captured["query_x"].fill(0)
    elif mode == "training_trial_shift":
        mapping = protocol.training_shift(captured["train_target"])
        captured["train_x"] = captured["train_x"][mapping]
        permutation = mapping.tolist()
    protocol.validate_packet(captured)
    result = {name: identity(captured[name]) for name in sorted(FIELDS)}
    allowed = {"train_x", "query_x"} if mode == "context_only" else (
        {"train_x"} if mode == "training_trial_shift" else set())
    need(all(source[name] == result[name] for name in FIELDS - allowed),
         "Only selected calcium input fields may change")
    for value in captured.values():
        value.flags.writeable = False
    return captured, {
        "schema": "neural026_matched_input_control_v1", "case_id": case_id,
        "mode": mode, "source_protocol_sha256": PROTOCOL_SHA256,
        "source_arrays": source, "view_arrays": result,
        "training_row_permutation": permutation,
        "array_working_envelope_bytes": envelope,
        "support_changed": False, "query_angles_accessed": False,
        "execution_verified": False, "matched_budgets_verified": False,
        "input_isolation_verified": False, "neural_dependence_established": False,
    }
