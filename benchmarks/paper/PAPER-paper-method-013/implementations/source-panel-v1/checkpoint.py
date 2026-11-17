"""Inspect authenticated released checkpoint metadata without loading a model.

Only the root HDF5 ``model_config`` attribute is parsed as JSON. No weight array,
training configuration, Lambda payload or executable model is deserialized.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
from typing import Any


AUTHOR_REVISION = "305a4827929b2c6e82e44c5c69b2ea9d410e20a4"
AUTHOR_PATH = "Demo (full-version)/Pretrained Model/DeepCaImX_model.h5"
EXPECTED_BYTES = 7_316_832
EXPECTED_GIT_BLOB_SHA1 = "93ae42338f0e0922621a2ac833f6fa5f4df8582d"
EXPECTED_SHA256 = "608bc595d52bc135748fac1226973eb85fd09f93e414762e212eef01a02ccc5c"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _positive_integer(value: Any, name: str) -> int:
    _require(type(value) is int and value > 0, f"{name} must be a positive integer")
    return value


def _one_integer(config: dict[str, Any], key: str) -> int:
    values = config.get(key)
    _require(isinstance(values, list) and len(values) == 1, f"{key} must have one element")
    return _positive_integer(values[0], key)


def parse_config(text: str | bytes) -> dict[str, Any]:
    """JSON parsing only; serialized function values are never interpreted."""
    def unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in pairs:
            _require(key not in result, f"duplicate model_config JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise ValueError(f"nonfinite model_config JSON constant: {value}")

    result = json.loads(text, object_pairs_hook=unique_keys, parse_constant=reject_constant)
    _require(isinstance(result, dict), "model_config must be a JSON object")
    return result


def _chain(layers: list[dict[str, Any]], name: str) -> None:
    """Check serialized graph edges; do not infer ordering from list order alone."""
    for previous, current in zip(layers, layers[1:]):
        inbound = current.get("inbound_nodes")
        _require(isinstance(inbound, list) and len(inbound) == 1
                 and isinstance(inbound[0], list) and len(inbound[0]) == 1,
                 f"{name} layers must form one serial chain")
        edge = inbound[0][0]
        _require(isinstance(edge, list) and len(edge) >= 3
                 and edge[:3] == [previous["name"], 0, 0],
                 f"{name} layers must form one serial chain")


def summarize_config(model: dict[str, Any]) -> dict[str, Any]:
    """Extract inert fields and convolution-length algebra, not model behavior."""
    _require(model.get("class_name") == "Functional", "expected a Keras Functional config")
    config = model.get("config")
    _require(isinstance(config, dict), "Functional config object missing")
    layers = config.get("layers")
    _require(isinstance(layers, list) and bool(layers), "model layers missing")
    names = set()
    for layer in layers:
        _require(isinstance(layer, dict) and isinstance(layer.get("config"), dict),
                 "invalid layer configuration")
        _require(isinstance(layer.get("class_name"), str), "layer class_name missing")
        name = layer.get("name")
        _require(isinstance(name, str) and bool(name) and name not in names,
                 "layer names must be nonempty and unique")
        names.add(name)
    inputs = [layer for layer in layers if layer["class_name"] == "InputLayer"]
    _require(len(inputs) == 1, "exactly one InputLayer required")
    input_shape = inputs[0]["config"].get("batch_input_shape")
    _require(isinstance(input_shape, list) and len(input_shape) == 5 and input_shape[0] is None,
             "expected batch,time,row,column,channel input shape")
    for value in input_shape[1:]:
        _positive_integer(value, "input dimension")

    dense = [layer for layer in layers if layer["class_name"] == "Dense"]
    _require(bool(dense), "Dense chain missing")
    _chain(dense, "Dense")
    dense_units = [_positive_integer(layer["config"].get("units"), "Dense units")
                   for layer in dense]
    convs = [layer for layer in layers if layer["class_name"] == "Conv1D"]
    _require(bool(convs), "Conv1D chain missing")
    _chain(convs, "Conv1D")
    length = input_shape[1]
    conv_summary = []
    for layer in convs:
        row = layer["config"]
        kernel = _one_integer(row, "kernel_size")
        stride = _one_integer(row, "strides")
        dilation = _one_integer(row, "dilation_rate")
        _require(row.get("padding") == "valid", "only valid Conv1D padding is supported")
        _require(row.get("data_format") == "channels_last", "expected channels_last Conv1D")
        effective_kernel = dilation * (kernel - 1) + 1
        length = (length - effective_kernel) // stride + 1
        _require(length > 0, "Conv1D chain has no temporal support")
        conv_summary.append({"name": layer["name"],
                             "filters": _positive_integer(row.get("filters"), "filters"),
                             "kernel_size": kernel, "stride": stride,
                             "dilation": dilation, "padding": "valid",
                             "derived_length": length})
    outputs = config.get("output_layers")
    _require(isinstance(outputs, list) and [convs[-1]["name"], 0, 0] in outputs,
             "terminal Conv1D is not a declared model output")
    counts = Counter(layer["class_name"] for layer in layers)
    return {"model_class": "Functional", "batch_input_shape": input_shape,
            "dense_units_in_serial_chain": dense_units, "terminal_dense_units": dense_units[-1],
            "temporal_convolutions": conv_summary,
            "derived_temporal_output_length": length,
            "temporal_derivation_assumption":
                "Conv1D chain receives the declared input time length; upstream serialized operations were not executed",
            "declared_output_layers": outputs,
            "layer_class_counts": dict(sorted(counts.items())),
            "serialized_lambda_layer_count": counts["Lambda"] + counts["TFOpLambda"],
            "lambda_payloads_executed_or_decoded": False,
            "native_output_shapes_verified": False}


def inspect_checkpoint(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    _require(path.is_file() and path.stat().st_size == EXPECTED_BYTES,
             "released full checkpoint byte length mismatch")
    body = path.read_bytes()
    _require(len(body) == EXPECTED_BYTES, "checkpoint changed while reading")
    digest = hashlib.sha256(body).hexdigest()
    blob = hashlib.sha1(b"blob " + str(len(body)).encode("ascii") + b"\0" + body).hexdigest()
    _require(digest == EXPECTED_SHA256 and blob == EXPECTED_GIT_BLOB_SHA1,
             "released full checkpoint byte identity mismatch")

    # Import and HDF parsing happen only after the exact released body is captured
    # and authenticated. Keras, TensorFlow, pickle and marshal are never invoked.
    import h5py

    with h5py.File(io.BytesIO(body), "r") as checkpoint:
        _require("model_config" in checkpoint.attrs, "model_config attribute missing")
        raw = checkpoint.attrs["model_config"]
        _require(isinstance(raw, (str, bytes)), "model_config must be JSON text")
        summary = summarize_config(parse_config(raw))
    return {"schema": "deepcaimx-released-checkpoint-inspection/v1",
            "author_revision": AUTHOR_REVISION, "author_path": AUTHOR_PATH,
            "bytes": len(body), "sha256": digest, "git_blob_sha1": blob,
            "inspection_scope": "authenticated model_config JSON only; no weight arrays or model execution",
            "configuration": summary,
            "authentication_scope": "released author checkpoint identity; paper checkpoint equivalence unresolved",
            "paper_equivalence_established": False,
            "paper_architecture_comparison":
                "The paper describes N=15/P=9; released terminal Dense units and temporal metadata do not establish that architecture or its historical results."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--checkpoint", required=True)
    inspect.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        _require(not Path(args.output).exists(), "output already exists")
        result = inspect_checkpoint(args.checkpoint)
        with Path(args.output).open("x") as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write("\n")
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    main()
