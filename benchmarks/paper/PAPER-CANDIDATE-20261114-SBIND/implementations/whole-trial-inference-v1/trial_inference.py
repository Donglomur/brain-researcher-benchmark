"""Complete-trial inference over the existing prospective WFCI1 stream.

This is a trusted owner/participant API, not process isolation or an original
paper protocol. It never receives held behavior values. Authentic execution
and the optional PyTorch bridge require separate runtime qualification.
"""
from __future__ import annotations

from collections.abc import Sequence
import hashlib
import json
import math

import trial_preparation as trials

POLICY = "sbind-train-only-continuous-normalization-v1"
CALL_POLICY = "complete-single-trial-sequence-reset-true-at-every-trial-no-tail-drop"
LINE_LIMIT = 1024 * 1024


class InferenceError(ValueError):
    pass


def _require(value, message):
    if not value:
        raise InferenceError(message)


def _integer(value, low=0):
    _require(type(value) is int and low <= value < 2**63, "invalid bounded integer")
    return value


def _hash(value):
    _require(type(value) is str and len(value) == 64 and
             all(c in "0123456789abcdef" for c in value), "literal SHA256 required")
    return value


def _keys(value, expected):
    _require(type(value) is dict and set(value) == set(expected), "unexpected record members")


def _number(value):
    _require(type(value) in (int, float), "real numeric value required")
    try:
        result = float(value)
    except OverflowError as exc:
        raise InferenceError("numeric value outside binary64") from exc
    _require(math.isfinite(result), "nonfinite numeric value")
    return result


def _sequence(value, length):
    _require(isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
             and len(value) == length, "incorrect complete dimension")
    return value


def _field(value):
    plane = _sequence(value, 1)[0]
    return [[[_number(x) for x in _sequence(row, 128)]
             for row in _sequence(plane, 128)]]


def _encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def _decode(raw):
    def unique(rows):
        result = {}
        for key, value in rows:
            _require(key not in result, "duplicate JSON member")
            result[key] = value
        return result

    def invalid_constant(_):
        raise InferenceError("nonfinite JSON constant")

    try:
        return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise InferenceError("malformed JSON record") from exc


class _Reader:
    def __init__(self, stream, expected_bytes):
        self.stream = stream
        self.expected_bytes = _integer(expected_bytes, 1)
        self.digest = hashlib.sha256()
        self.bytes = 0

    def line(self):
        raw = self.stream.readline(LINE_LIMIT + 1)
        _require(type(raw) is bytes and 0 < len(raw) <= LINE_LIMIT and raw.endswith(b"\n"),
                 "missing, oversized, or unterminated record")
        self.bytes += len(raw)
        _require(self.bytes <= self.expected_bytes, "stream exceeds frozen extent")
        self.digest.update(raw)
        return raw, _decode(raw)

    def finish(self, expected_hash):
        _require(self.stream.read(1) == b"", "unexpected trailing stream data")
        _require(self.bytes == self.expected_bytes and self.digest.hexdigest() == expected_hash,
                 "stream identity or extent mismatch")


def _plan(census_bytes, split_bytes, *, census_sha256, split_sha256,
          representations_sha256, normalization_sha256, role, fold, max_trial_frames):
    _require(role in ("validation", "test"), "only held participant roles are supported")
    _integer(fold); _require(fold <= 4, "unknown fold")
    _integer(max_trial_frames, 1)
    _hash(representations_sha256); _hash(normalization_sha256)
    # Existing complete 248+412 trial and ten-fold checks run before any stream
    # or model is accessed. This retains the separately selected prospective split.
    protocol = trials.compile_protocol(census_bytes, split_bytes,
                                       census_sha256=census_sha256, split_sha256=split_sha256)
    assay = protocol.assays[0]
    _require(assay.assay_id == "WFCI1" and len(assay.channels) == 14,
             "this continuous bridge requires complete fourteen-channel WFCI1")
    spans = getattr(assay.folds[fold], role)
    _require(all(s.length <= max_trial_frames for s in spans),
             "a complete trial exceeds the declared memory envelope")
    header = {"schema": "sbind-normalized-fold-stream-v1", "task_id": trials.TASK,
              "policy": POLICY, "assay_id": "WFCI1", "fold": fold,
              "census_sha256": census_sha256, "split_sha256": split_sha256,
              "representations_sha256": representations_sha256,
              "normalization_sha256": normalization_sha256,
              "neural_shape": [1, 128, 128], "behavior_channels": list(assay.channels),
              "model_call_policy": CALL_POLICY, "role": role,
              "record": "header", "includes_behavior": False}
    return header, spans


def _walk(stream, expected_bytes, header, spans):
    """Yield one validated complete trial; hashes cover exact stream bytes."""
    stream.seek(0)
    _require(stream.tell() == 0, "source must be a seekable binary stream")
    reader = _Reader(stream, expected_bytes)
    raw, observed = reader.line()
    _keys(observed, header)
    _require(observed == header and type(observed["fold"]) is int and
             type(observed["includes_behavior"]) is bool and
             all(type(n) is int for n in observed["neural_shape"]), "stream header differs from frozen plan")
    for span in spans:
        fields = []
        digest = hashlib.sha256()
        for offset in range(span.length):
            raw, record = reader.line()
            _keys(record, ("role", "source_index", "trial_id", "trial_offset", "reset", "record", "neural"))
            _require(record["role"] == header["role"] and record["record"] == "frame" and
                     record["trial_id"] == span.trial_id and
                     _integer(record["source_index"]) == span.source_start + offset and
                     _integer(record["trial_offset"]) == offset and
                     type(record["reset"]) is bool and record["reset"] == (offset == 0),
                     "frame identity/order/reset differs from complete trial support")
            fields.append(_field(record["neural"]))
            digest.update(raw)
        yield reader, span, fields, digest.hexdigest()


class _Writer:
    def __init__(self, sink, maximum_bytes):
        self.sink = sink
        self.maximum_bytes = _integer(maximum_bytes, 1)
        self.bytes = 0
        self.records = 0
        self.digest = hashlib.sha256()

    def put(self, record):
        raw = _encode(record)
        _require(self.bytes + len(raw) <= self.maximum_bytes, "output exceeds admitted byte envelope")
        cursor = 0
        while cursor < len(raw):
            count = self.sink.write(raw[cursor:])
            _require(type(count) is int and 0 < count <= len(raw) - cursor, "incomplete output write")
            self.digest.update(raw[cursor:cursor + count])
            self.bytes += count
            cursor += count
        self.records += 1


def predict_held_wfci1(census_bytes, split_bytes, *, census_sha256, split_sha256,
                      representations_sha256, normalization_sha256, role, fold,
                      stream, stream_sha256, stream_bytes, max_trial_frames,
                      infer_trial, sink, max_output_bytes):
    """Run one complete held role, one reset model call per complete trial.

    `infer_trial(fields, x_init=True, behavior_width=14)` returns a dict with
    exactly `neural` and `behavior`: complete sequences of 1x128x128 fields and
    fourteen continuous values, respectively. No targets, owner state or masks
    are passed. Every output keeps its source index; this code adds no lag or mask.

    The first pass checks all identities, values, extent and hash before a model
    call or output write. The second pass checks each exact trial-byte digest
    before calling the model, then rechecks the full stream. A failed operation
    may leave partial outputs and model state; only a returned receipt is success.
    The trusted owner must stage/discard partial sinks and enforce process/file
    isolation. No claim is made that a callback actually follows x_init/causality.
    """
    _hash(stream_sha256)
    _integer(stream_bytes, 1); _integer(max_output_bytes, 1)
    _require(callable(infer_trial), "an explicit inference callback is required")
    _require(stream is not sink, "input and output objects must differ")
    header, spans = _plan(census_bytes, split_bytes, census_sha256=census_sha256,
                         split_sha256=split_sha256, representations_sha256=representations_sha256,
                         normalization_sha256=normalization_sha256, role=role,
                         fold=fold, max_trial_frames=max_trial_frames)
    trial_hashes = []
    for reader, span, fields, digest in _walk(stream, stream_bytes, header, spans):
        trial_hashes.append(digest)
    reader.finish(stream_sha256)
    # Release the final validation trial before allocating the second pass.
    del fields
    writer = _Writer(sink, max_output_bytes)
    writer.put({"schema": "sbind-prospective-wfci1-predictions-v1", "task_id": trials.TASK,
                "assay_id": "WFCI1", "fold": fold, "role": role,
                "input_sha256": stream_sha256, "census_sha256": census_sha256,
                "split_sha256": split_sha256, "normalization_sha256": normalization_sha256,
                "representations_sha256": representations_sha256,
                "behavior_channels": header["behavior_channels"], "model_call_policy": CALL_POLICY,
                "record": "header", "historical_reproduction_qualified": False})
    count = 0
    for expected_hash, (reader, span, fields, digest) in zip(
            trial_hashes, _walk(stream, stream_bytes, header, spans)):
        _require(digest == expected_hash, "source changed between validation and inference")
        prediction = infer_trial(fields, x_init=True, behavior_width=14)
        _keys(prediction, ("neural", "behavior"))
        y = _sequence(prediction["neural"], span.length)
        z = _sequence(prediction["behavior"], span.length)
        # Validate the complete trial before writing any of its predictions.
        for field, behavior in zip(y, z):
            _field(field)
            tuple(_number(v) for v in _sequence(behavior, 14))
        for offset in range(span.length):
            writer.put({"record": "prediction", "role": role, "trial_id": span.trial_id,
                        "source_index": span.source_start + offset, "trial_offset": offset,
                        "neural": _field(y[offset]),
                        "behavior": [_number(v) for v in z[offset]]})
            count += 1
    reader.finish(stream_sha256)
    _require(count == sum(s.length for s in spans), "incomplete prediction support")
    return {"schema": "sbind-prospective-wfci1-inference-receipt-v1", "task_id": trials.TASK,
            "assay_id": "WFCI1", "fold": fold, "role": role,
            "input_sha256": stream_sha256, "input_bytes": stream_bytes,
            "output_sha256": writer.digest.hexdigest(), "output_bytes": writer.bytes,
            "output_records": writer.records, "trials": len(spans), "frames": count,
            "model_calls": len(spans), "reset_true_calls": len(spans),
            "historical_reproduction_qualified": False, "runtime_isolation_qualified": False}


class TorchSBINDPredictor:
    """Optional native bridge, NOT exercised or runtime-qualified by source tests.

    Construct only inside a separately admitted environment with a trusted model
    and explicit device/dtype. No checkpoints are loaded. The owner must freeze
    architecture, weights and native precision and verify prediction causality.
    """
    def __init__(self, model, *, device, dtype):
        import torch
        _require(dtype in (torch.float32, torch.float64), "explicit float32/float64 dtype required")
        _require(isinstance(model, torch.nn.Module), "a trusted torch model is required")
        _require(getattr(model, "Cz_observation_model", None) == "gaussian",
                 "this bridge supports continuous WFCI1 behavior only")
        for stage_name in ("stage_1", "stage_2"):
            stage = getattr(model, stage_name, None)
            _require(stage is None or getattr(stage, "step_ahead_prediction", None) is None,
                     "multi-step shortening is not supported by the complete-frame bridge")
        self.torch = torch
        self.model = model.to(device=device, dtype=dtype)
        self.device, self.dtype = device, dtype

    def __call__(self, fields, *, x_init, behavior_width):
        _require(x_init is True and behavior_width == 14, "wrong full-trial call contract")
        torch = self.torch
        tensor = torch.tensor([fields], device=self.device, dtype=self.dtype)
        _require(tuple(tensor.shape) == (1, len(fields), 1, 128, 128) and
                 bool(torch.isfinite(tensor).all().item()), "invalid native input conversion")
        self.model.eval()
        with torch.no_grad():
            output = self.model(tensor, x_init=True)
        _require(type(output) is dict and "y" in output and "z" in output,
                 "model did not return both prediction modalities")
        expected = {"y": {(1, len(fields), 1, 128, 128)},
                    "z": {(1, len(fields), 14), (1, len(fields), 14, 1),
                          (1, len(fields), 14, 1, 1)}}
        for key, shapes in expected.items():
            value = output[key]
            _require(isinstance(value, torch.Tensor) and value.is_floating_point() and
                     tuple(value.shape) in shapes and
                     bool(torch.isfinite(value).all().item()), "invalid native output dimensions or values")
        return {"neural": output["y"].detach().cpu().tolist()[0],
                "behavior": output["z"].detach().cpu().reshape(1, len(fields), 14).tolist()[0]}
