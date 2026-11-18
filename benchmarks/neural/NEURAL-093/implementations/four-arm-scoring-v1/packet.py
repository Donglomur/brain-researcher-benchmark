"""Operator-only reader for the existing NEURAL-093 public packet format.

The operator supplies the expected manifest pin from the authenticated original
panel. A candidate-supplied pin is not authentication. The loader reads its six
local pinned source modules through scorer.load_sources; observation and
protected-target files are not opened. No protected mapping, fitting,
prediction, viewer, or grading is performed.
"""
import ast
import copy
import io
import zipfile

import scorer


CAP = 128 * 1024 * 1024
HEADER_CAP = 4096
FIELDS = {
    "context.npz": {"u": "float64", "u_squared": "float64"},
    "neural.npz": {"trial_index": "uint32", "unit": "uint32", "bin_id": "uint8",
                   "within_bin_seconds": "float64"},
    "wheel.npz": {"trial_index": "uint32", "bin_id": "uint8",
                  "within_bin_seconds": "float64",
                  "position_relative_to_first_trial_sample": "float64"},
    "units.npz": {"unit": "uint32", "source_qc_code": "uint8"},
    "labels.npz": {"target": "int8"},
}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def _npy(raw, expected_dtype, np):
    """Bound and parse a primitive one-dimensional NPY before creating a view."""
    need(type(raw) is bytes and 10 <= len(raw) <= CAP, "bounded NPY body")
    need(raw[:6] == b"\x93NUMPY", "NPY magic")
    version = tuple(raw[6:8])
    need(version in ((1, 0), (2, 0)), "source-compatible NPY version")
    width = 2 if version == (1, 0) else 4
    need(len(raw) >= 8 + width, "complete NPY header prefix")
    size = int.from_bytes(raw[8:8 + width], "little")
    start = 8 + width + size
    need(0 < size <= HEADER_CAP and start <= len(raw), "bounded NPY header")
    try:
        header = ast.literal_eval(raw[8 + width:start].decode("latin1"))
    except (ValueError, SyntaxError, UnicodeError, RecursionError) as exc:
        raise ValueError("invalid primitive NPY header") from exc
    need(type(header) is dict and set(header) == {"descr", "fortran_order", "shape"},
         "exact NPY header fields")
    shape = header["shape"]
    need(type(shape) is tuple and len(shape) == 1 and type(shape[0]) is int
         and 0 <= shape[0] <= CAP, "bounded one-dimensional source arrays")
    need(header["fortran_order"] is False and type(header["descr"]) is str
         and len(header["descr"]) <= 8, "primitive contiguous source dtype")
    try:
        dtype = np.dtype(header["descr"])
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid primitive source dtype") from exc
    need(dtype == np.dtype(expected_dtype) and not dtype.hasobject
         and dtype.fields is None and dtype.subdtype is None, "exact source field dtype")
    need(start + shape[0] * dtype.itemsize == len(raw), "exact NPY payload extent")
    result = np.frombuffer(raw, dtype=dtype, count=shape[0], offset=start)
    result.setflags(write=False)
    return result


def _archive(raw, fields, np):
    """Read only the original exporter np.savez (stored, inert) container."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = archive.infolist()
            expected = {name + ".npy" for name in fields}
            need(len(members) == len(expected)
                 and {item.filename for item in members} == expected,
                 "exact unique NPZ field allowlist")
            need(not archive.comment and all(not item.comment and not item.is_dir()
                 and item.compress_type == zipfile.ZIP_STORED and not item.flag_bits & 1
                 and item.file_size == item.compress_size and 10 <= item.file_size <= CAP
                 for item in members), "source-compatible stored unencrypted NPZ")
            need(sum(item.file_size for item in members) <= CAP, "complete NPZ byte cap")
            # No extraction, pickle, np.load, evaluation, or source code execution.
            return {name: _npy(archive.read(name + ".npy"), dtype, np)
                    for name, dtype in fields.items()}
    except (zipfile.BadZipFile, OSError, EOFError) as exc:
        raise ValueError("invalid inert NPZ container") from exc


def _validate_arrays(manifest, arrays, np):
    cases = len(manifest["case_tokens"])
    context = arrays["context.npz"]
    for value in context.values():
        need(value.shape == (cases,) and bool(np.isfinite(value).all())
             and bool(((value >= 0) & (value <= 1)).all()), "complete finite chronological context")
    need(bool(np.array_equal(context["u_squared"], np.square(context["u"])))
         and bool((np.diff(context["u"]) > 0).all()), "source u square and original row order")
    if "units.npz" in arrays:
        units = arrays["units.npz"]
        count = manifest["unit_count"]
        need(units["unit"].shape == units["source_qc_code"].shape == (count,)
             and bool(np.array_equal(units["unit"], np.arange(count, dtype=np.uint32)))
             and bool(np.isin(units["source_qc_code"], [2, 3]).all()),
             "complete dense QC2/3 unit inventory, including zero-event units")
    for name in ("neural.npz", "wheel.npz"):
        if name not in arrays:
            continue
        values = arrays[name]
        trial, bins, offset = (values[key] for key in ("trial_index", "bin_id", "within_bin_seconds"))
        need(all(a.shape == trial.shape for a in values.values()), "aligned event fields")
        need(bool((trial < cases).all()) and bool((bins < 5).all())
             and bool(np.isfinite(offset).all()) and bool((offset >= 0).all()),
             "finite native event indices and offsets")
        need(bool((trial[1:] >= trial[:-1]).all()), "original event trial order")
        same_trial = trial[1:] == trial[:-1]
        same_bin = same_trial & (bins[1:] == bins[:-1])
        need(bool((bins[1:][same_trial] >= bins[:-1][same_trial]).all())
             and bool((offset[1:][same_bin] >= offset[:-1][same_bin]).all()),
             "original event bin and within-bin order")
        # The source subtracts (absolute_onset + bin_edge); due to floating-point
        # subtraction its exclusive upper edge is not identically nominal .02.
        # Private source clocks are absent here, so do not invent/rebin an edge.
        if name == "neural.npz":
            need(bool((values["unit"] < manifest["unit_count"]).all()), "known dense unit aliases")
        else:
            position = values["position_relative_to_first_trial_sample"]
            need(bool(np.isfinite(position).all()), "finite within-trial wheel gauge")
            support = np.bincount(trial.astype(np.int64) * 5 + bins, minlength=cases * 5)
            need(support.shape == (cases * 5,) and bool((support >= 2).all()),
                 "all five original wheel bins for every case")
            first = np.r_[True, trial[1:] != trial[:-1]]
            need(bool((position[first] == 0).all()), "first observed trial wheel sample is origin")
    if "labels.npz" in arrays:
        target = arrays["labels.npz"]["target"]
        need(target.shape == (cases,) and bool(np.isin(target, [0, 1, 2]).all()),
             "only complete fitting/validation stimulus classes")


def load_packet(manifest_raw, expected_manifest, payloads, np):
    """Authenticate every public byte body before any binary decoding.

    expected_manifest is an operator-owned {bytes, sha256} from packet_plan.
    This single-packet reader does not prove the full312-packet cohort or source
    clock/coverage semantics. Use the existing planner for whole-panel joins.
    """
    sources = scorer.load_sources()
    controls, parent = sources["controls"], sources["parent_validation"]
    need(type(expected_manifest) is dict and set(expected_manifest) == {"bytes", "sha256"}
         and type(expected_manifest["bytes"]) is int
         and 0 < expected_manifest["bytes"] <= controls.MAX_MANIFEST
         and parent.digest(expected_manifest["sha256"]), "operator-selected manifest descriptor")
    need(type(manifest_raw) is bytes and len(manifest_raw) == expected_manifest["bytes"]
         and controls.pin(manifest_raw) == expected_manifest,
         "expected manifest bytes before parsing")
    manifest = controls.parse(manifest_raw, controls.MAX_MANIFEST)
    need(type(manifest) is dict, "public manifest object")
    if manifest.get("arm") in controls.ORIGINAL_ARMS:
        parent.validate_manifest(manifest)
    else:
        controls.validate_control(manifest)
    need(type(payloads) is dict and set(payloads) == set(manifest["files"]),
         "exact arm/phase payload allowlist")
    total = len(manifest_raw)
    for name, descriptor in manifest["files"].items():
        raw = payloads[name]
        need(type(raw) is bytes and len(raw) == descriptor["bytes"], "exact public payload extent")
        total += len(raw)
        need(total <= CAP, "complete packet cap without truncation")
        need(controls.pin(raw) == {key: descriptor[key] for key in ("bytes", "sha256")},
             "exact public payload hash before any decoding")
    arrays = {name: _archive(payloads[name], FIELDS[name], np) for name in manifest["files"]}
    _validate_arrays(manifest, arrays, np)
    return {"schema": "neural093_validated_public_packet_v1", "manifest": copy.deepcopy(manifest),
            "manifest_pin": dict(expected_manifest), "arrays": arrays,
            "source_clock_and_coverage_independently_verified": False,
            "whole_panel_authenticated": False, "participant_isolation_qualified": False}


def case_observation(packet, token, np):
    """Lossless numerical projection, not a rendered/native-understanding trial.

    The input must be the operator's load_packet result, not a participant object.
    Keeps native bins/offsets and all dense units. Only fitval gets a class label.
    No target-derived filtering, aggregation, new clock, or graphical resampling.
    """
    manifest = packet["manifest"]
    need(type(token) is str and token in manifest["case_tokens"], "exact public case token")
    index = manifest["case_tokens"].index(token)
    arrays = packet["arrays"]
    result = {"arm": manifest["arm"], "phase": manifest["phase"], "token": token,
              "split": manifest["case_splits"][index], "observation": copy.deepcopy(manifest["observation"]),
              "context": {name: float(value[index]) for name, value in arrays["context.npz"].items()}}
    for filename, key in (("neural.npz", "neural"), ("wheel.npz", "wheel")):
        if filename in arrays:
            family = arrays[filename]
            select = family["trial_index"] == index
            result[key] = {name: value[select] for name, value in family.items() if name != "trial_index"}
            for value in result[key].values():
                value.setflags(write=False)
    if "units.npz" in arrays:
        result["units"] = dict(arrays["units.npz"])
    if manifest["phase"] == "fitval":
        result["target"] = int(arrays["labels.npz"]["target"][index])
    return result
