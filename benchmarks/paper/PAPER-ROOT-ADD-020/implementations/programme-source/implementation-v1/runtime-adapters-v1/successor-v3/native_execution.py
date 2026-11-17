"""Future authenticated per-phase literal MATLAB capture and exact V2 export.

No original/native execution is enabled by this source. An independently signed
operator installation must approve this additive instrumentation, immutable mount,
MATLAB image, all 56 phase keys, resource ceilings and original clock. Original
regress/STA/cosine outputs are captured; portable scientific kernels are never
called to fill missing native numerical values. Native rank and summaries absent
from an original static driver are explicitly added diagnostic instrumentation.
"""
from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import time
import warnings

import numpy as np

from .basis import basis, scientific_root
from .wire import WireLimits, encode, canonical
from .mat_source import _OwnedRelease, Limits

PUBLIC_KEY = "/opt/itbench/operator-public-key.bin"
CAPTURE_SHA256 = "709f4ef08d7fcfaa5427798628c2cba31a3b2c2d2cf95bc72a0c6d5280e6015d"
STATUS = "literal_matlab_additive_capture_not_independently_qualified"


class NativeError(ValueError):
    pass


class NativeExecutionFailure(NativeError):
    """Trusted worker must persist artifacts before propagating failed status."""
    def __init__(self, message, artifacts):
        super().__init__(message)
        self.artifacts = artifacts


def need(ok, message):
    if not ok:
        raise NativeError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _replace(text, before, after):
    need(text.count(before) == 1, "Exact reviewed instrumentation anchor missing or ambiguous")
    return text.replace(before, after)


def instrument_sources(capture, helpers):
    """Pure source transformation; no paths, arrays, MATLAB or subprocesses."""
    need(type(capture) is bytes and sha(capture) == CAPTURE_SHA256, "Frozen complete56 capture source differs")
    need(set(helpers) == {"analysis_STA.m", "STA_sub.m", "load_data.m"}, "Exact three source helpers required")
    pins = {"analysis_STA.m": "7a9b917ceb77d52d7c1347e86ff03ea61607ba7776c5f1d9adeeca235f9b8f5e",
            "STA_sub.m": "202d822bcecb459eb00e1722f8c29b0745f5c6ca58a1475f9d1cd77f767a8a30",
            "load_data.m": "9dc612d6c2e0bc8e6b125b9dcf22d4ca624e1d8fe1bc3109c88c70f5c5e3ce55"}
    for name, raw in helpers.items():
        need(type(raw) is bytes and sha(raw) == pins[name], "Original helper source differs")
    text = capture.decode("utf-8").replace("\r\n", "\n")
    text = _replace(text, "for c = 1:14", "for c = request.selection(1)")
    text = _replace(text, "for method_index = 1:2", "for method_index = request.selection(2)")
    text = _replace(text, "for mode_index = 1:2", "for mode_index = request.selection(3)")
    text = _replace(text, "addpath(fullfile(request.release_root, 'code'), '-begin');",
                    "addpath(fullfile(request.release_root, 'code'), '-begin');\naddpath(request.instrumented_helper_root, '-begin');")
    text = _replace(text, "    assert(strcmp(which(helpers{k}), fullfile(request.release_root,'code',[helpers{k} '.m'])), ...",
                    "    expected_helper = fullfile(request.release_root,'code',[helpers{k} '.m']);\n"
                    "    if any(strcmp(helpers{k},{'analysis_STA','STA_sub','load_data'}))\n"
                    "        expected_helper = fullfile(request.instrumented_helper_root,[helpers{k} '.m']);\n"
                    "    end\n    assert(strcmp(which(helpers{k}), expected_helper), ...")
    result = {"native_capture.m": text.encode()}
    original = helpers["analysis_STA.m"].decode().replace("\r\n", "\n")
    original = _replace(original, "ndim = size(param,2);", "global paper020_trace paper020_trace_rows\nndim = size(param,2);")
    tail = """
% Additive trace: the original solve/STA call and its result remain unchanged.
% rank(X) below is a NEW diagnostic, not the rank decision made by regress.
[paper020_warning,paper020_warning_id] = lastwarn;
if strcmp(method,'linear_regression')
    paper020_full_b = b(:);
    paper020_rank = rank(X);
else
    paper020_full_b = sta(:);
    paper020_rank = -1;
end
paper020_item = struct('rows',paper020_trace_rows(:),'keep',~ind_nan(:), ...
    'coefficients',sta(:),'full_b',paper020_full_b,'diagnostic_rank',paper020_rank, ...
    'finite_response',all(isfinite(resp(:))),'finite_features',all(isfinite(param(:))), ...
    'original_last_warning',paper020_warning,'original_last_warning_id',paper020_warning_id);
paper020_trace{end+1} = paper020_item;
lastwarn(paper020_warning,paper020_warning_id); % preserve original helper warning identity
"""
    original = _replace(original, "\nend\n\nend", "\nend\n" + tail + "\nend")
    result["analysis_STA.m"] = original.encode()
    original = helpers["STA_sub.m"].decode().replace("\r\n", "\n")
    original = _replace(original, "fr_raw = resp_raw(sub_stim_ind, :);",
                        "global paper020_trace_rows\npaper020_trace_rows = sub_stim_ind(:);\nfr_raw = resp_raw(sub_stim_ind, :);")
    result["STA_sub.m"] = original.encode()
    original = helpers["load_data.m"].decode().replace("\r\n", "\n")
    original = _replace(original, "params = bsxfun(@rdivide, params, sqrt(mean(params.^2)));",
                        "paper020_raw_params = params; % additive source-raw capture before unchanged normalization\n"
                        "params = bsxfun(@rdivide, params, sqrt(mean(params.^2)));")
    result["load_data.m"] = original.encode()
    before = {"native_capture.m": CAPTURE_SHA256, **pins}
    return result, {name: {"before_sha256": before[name], "after_sha256": sha(raw)} for name, raw in result.items()}


def _instrumentation_wire(mapping):
    return [{"name": name, **mapping[name]} for name in sorted(mapping)]


def literal_phase_keys():
    return tuple((case, mode, method) for case in basis("programme").CONFIGS
                 for mode in ("static", "time_course") for method in ("STA", "OLS_INTERCEPT"))


def _array(arrays, key, shape, dtype):
    need(key in arrays, "Native collector omitted required numerical output: " + key)
    value = arrays.pop(key)
    need(type(value) is np.ndarray and value.shape == tuple(shape) and value.dtype == np.dtype(dtype),
         "Native output shape/dtype differs: " + key)
    out = np.array(value, order="C", copy=True)
    out.flags.writeable = False
    return out


def _cosine(values, left, right):
    """Classify captured values; never recompute a scientific cosine."""
    states = np.full(values.shape, "finite", dtype="U32")
    states[~np.isfinite(values)] = "nonfinite_arithmetic"
    zero = np.all(left == 0, axis=0) | np.all(right == 0, axis=0)
    states[zero] = "zero_axis"
    states[~(np.isfinite(left).all(axis=0) & np.isfinite(right).all(axis=0))] = "nonfinite_operand"
    return basis("reproduction").CosineResult(values, np.isfinite(values), states)


def convert_native_payload(metadata, supplied_arrays, packet, phase, *, expected_instrumentation):
    """Lossless V2 assembly from native values and neutral provenance only.

    Every scientific coefficient/cosine/mean/RMS/SD/SEM is an observed MATLAB
    output. No axes(), cosine(), normalize_features(), native_summary(), or
    reproduce_case() numeric kernel is used here. Missing values cause failure.
    """
    reproduction = basis("reproduction")
    need(type(metadata) is dict and set(metadata) == {"schema", "configuration", "method", "mode", "instrumentation", "trace_groups", "source_default_dimension_compatible"}
         and metadata["schema"] == "paper020_native_phase_payload_v1", "Exact native collector metadata required")
    case, mode, method = phase["configuration"], phase["mode"], phase["method"]
    need((case, mode, method) in literal_phase_keys() and phase["family"] == "native_literal", "Original literal phase required")
    need((metadata["configuration"], metadata["mode"], metadata["method"]) == (case, mode, method)
         and metadata["instrumentation"] == _instrumentation_wire(expected_instrumentation), "Native output phase/instrumentation differs")
    need(type(packet) is dict and set(packet) == {"features", "psth", "times", "arguments"}, "Full source-owned native input required")
    args = packet["arguments"]
    need((args["configuration"], args["mode"], args["method"], args["family"]) == (case, mode, method, "native_literal"), "Input/native phase join differs")
    source_rows, dimensions = packet["features"].shape
    cells, times_count = packet["psth"].shape[1:]
    need(dimensions == 20 and packet["psth"].shape[0] == source_rows and len(args["row_ids"]) == source_rows
         and len(args["cell_ids"]) == cells and len(packet["times"]) == times_count,
         "Complete native input axes required")
    index = reproduction.validate_index_manifest(args["index_manifest"], args["stimulus_set"], source_rows)
    plan = reproduction.build_windows(packet["times"], mode)
    nw = len(plan.indices)
    need(metadata["source_default_dimension_compatible"] is True and not (mode == "time_course" and cells == 1 and nw > 1),
         "Literal singleton default-dimension summary is incompatible with exact V2 shape; no replacement summary")
    arrays = dict(supplied_arrays)
    raw = _array(arrays, "raw_features", (source_rows, 20), "float64")
    native_times = _array(arrays, "times", (times_count,), "float64")
    need(np.array_equal(raw, packet["features"], equal_nan=True) and np.array_equal(native_times, packet["times"]),
         "Native original feature/clock values differ from independently admitted packet")
    means, rms, sd0, sd1 = [_array(arrays, name, (20,), "float64") for name in ("feature_means", "feature_rms", "feature_sd_population", "feature_sd_sample")]
    transform = reproduction.FeatureTransform(_array(arrays, "feature_values", (source_rows, 20), "float64"), means, rms, sd0, sd1,
                 tuple("zero_rms" if x == 0 else "nonfinite_rms" if not np.isfinite(x) else "finite" for x in rms))
    averaged = _array(arrays, "averaged_responses", (source_rows, cells, nw), "float64")
    nan_counts = _array(arrays, "response_bin_nan_counts", (source_rows, cells, nw), "int64")
    fam_values = _array(arrays, "familiar_cosines", (nw, 1, cells), "float64")
    reps = 100 if args["stimulus_set"] == 2 else 1
    ctrl_values = _array(arrays, "control_cosines", (nw, reps, cells), "float64")
    groups = (2 + 2 * reps) * nw if args["stimulus_set"] == 2 else 3 * nw
    need(type(metadata["trace_groups"]) is int and metadata["trace_groups"] == groups,
         "Every original helper call/cell trace must be present")
    cache = {}
    consumed = set()

    def axis(group, expected_rows):
        if group in cache:
            rows, value = cache[group]
            need(rows == tuple(expected_rows), "Native helper trace reused for different source rows")
            return value
        key = f"trace/{group}/"
        rows = _array(arrays, key + "rows", (len(expected_rows),), "int64")
        need(tuple(int(x) - 1 for x in rows) == tuple(expected_rows), "Native RNG/subset/source-index selection differs; no substituted sampling")
        keep = _array(arrays, key + "keep", (len(expected_rows), cells), "bool")
        coef = _array(arrays, key + "coefficients", (20, cells), "float64")
        full_b = _array(arrays, key + "full_b", (21 if method == "OLS_INTERCEPT" else 20, cells), "float64")
        need(np.array_equal(coef, full_b[:20], equal_nan=True), "Original regress/STA coefficient trace changed")
        intercept = full_b[20].copy() if method == "OLS_INTERCEPT" else np.full(cells, np.nan)
        rank = _array(arrays, key + "diagnostic_rank", (cells,), "int64")
        need(np.all(rank >= 0) if method == "OLS_INTERCEPT" else np.all(rank == -1), "Native rank diagnostic presence differs")
        finite_inputs = _array(arrays, key + "finite_inputs", (2, cells), "bool")
        defined = np.isfinite(coef).all(axis=0)
        states = []
        for c in range(cells):
            states.append("nonfinite_response" if not finite_inputs[0, c] else "nonfinite_features" if not finite_inputs[1, c]
                          else "no_response_rows" if keep[:, c].sum() == 0 else "nonfinite_coefficients" if not defined[c]
                          else "zero_axis" if np.all(coef[:, c] == 0) else "finite")
        value = reproduction.AxisResult(method, coef, intercept, tuple(states), defined, keep,
                  keep.sum(axis=0, dtype=np.int64), rank, calculation_status=STATUS)
        consumed.add(group)
        cache[group] = (tuple(expected_rows), value)
        return value

    familiar, controls = [], []
    for w in range(nw):
        first = 2 * w if args["stimulus_set"] == 2 else 3 * w
        reference, comparison = axis(first, index.unfamiliar), axis(first + 1, index.familiar)
        fam = reproduction.PairResult("familiar", 0, index.unfamiliar, index.familiar,
              reference, comparison, _cosine(fam_values[w, 0], reference.coefficients, comparison.coefficients))
        familiar.append((fam,))
        control = []
        for rep in range(reps):
            if args["stimulus_set"] == 2:
                subset = index.subsets[rep]
                subset_set = set(subset)
                complement = tuple(i for i in index.unfamiliar if i not in subset_set)
                start = 2 * nw + 2 * (rep * nw + w)
                cmp, ref = axis(start, subset), axis(start + 1, complement)
                ref_rows, cmp_rows = complement, subset
            else:
                ref, cmp = reference, axis(first + 2, index.matched)
                ref_rows, cmp_rows = index.unfamiliar, index.matched
            control.append(reproduction.PairResult("control", rep, ref_rows, cmp_rows, ref, cmp,
                           _cosine(ctrl_values[w, rep], ref.coefficients, cmp.coefficients)))
        controls.append(tuple(control))
    need(consumed == set(range(groups)), "Native helper trace coverage differs")
    conditions = []
    for name, nested, values in (("familiar", familiar, fam_values), ("control", controls, ctrl_values)):
        prefix = "summary/" + name + "/"
        summary = reproduction.NativeSummary(
            _array(arrays, prefix + "per_cell", (nw, cells), "float64"),
            _array(arrays, prefix + "subset_non_nan_counts", (nw, cells), "int64"),
            _array(arrays, prefix + "means", (nw,), "float64"),
            _array(arrays, prefix + "sem", (nw,), "float64"),
            _array(arrays, prefix + "cell_non_nan_counts", (nw,), "int64"), True)
        # Preserve actual aggregate native cosines and derived diagnostic masks;
        # these are classifications, never a replacement cosine calculation.
        masks = np.asarray([[x.cosine.defined for x in row] for row in nested], dtype=bool)
        states = np.asarray([[x.cosine.states for x in row] for row in nested], dtype="U32")
        conditions.append(reproduction.ConditionResult(name, reproduction.CosineResult(values, masks, states), tuple(nested), summary))
    need(not arrays, "Unconsumed native numerical fields; conversion must preserve the complete declared payload")
    result = reproduction.ReproductionResult(case, args["stimulus_set"], "native_literal", method,
        tuple(args["cell_ids"]), tuple(args["row_ids"]), tuple(args["feature_ids"]), tuple(args["feature_groups"]),
        plan, transform, index, tuple(averaged[:, :, w] for w in range(nw)),
        tuple(nan_counts[:, :, w] for w in range(nw)), tuple(conditions), STATUS, False)
    record = basis("native_scoring").export_reproduction(result)
    record["provenance"]["native_additive_instrumentation"] = expected_instrumentation
    record["provenance"]["rank_semantics"] = "MATLAB rank(X) diagnostic after unchanged original regress; not regress solver rank"
    record["provenance"]["summary_semantics"] = "Captured original time summaries; static summary formulas added by reviewed collector"
    record["provenance"]["phase_workload"] = "one of the original56 literal phases; no full56 batch cache"
    basis("native_scoring").validate_record(record)
    return record


def _read_absolute(path, maximum):
    need(type(path) is str and path.startswith("/") and str(PurePosixPath(path)) == path
         and ".." not in PurePosixPath(path).parts, "Canonical operator-owned absolute path required")
    opened = []
    try:
        fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        opened.append(fd)
        parts = PurePosixPath(path).parts[1:]
        for part in parts[:-1]:
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            opened.append(fd)
        leaf = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0), dir_fd=fd)
        opened.append(leaf)
        before = os.fstat(leaf)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 <= before.st_size <= maximum,
             "Unsafe or oversized pinned native file")
        raw = bytearray()
        while len(raw) < before.st_size:
            value = os.read(leaf, min(65536, before.st_size - len(raw)))
            need(value, "Short pinned native file read")
            raw.extend(value)
        after = os.fstat(leaf)
        fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        need(fields(before) == fields(after), "Pinned native file changed during read")
        return bytes(raw)
    finally:
        for fd in reversed(opened):
            os.close(fd)


def _write_new(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    try:
        view = memoryview(raw)
        while view:
            n = os.write(fd, view)
            need(n > 0, "Short native request/source write")
            view = view[n:]
        os.fsync(fd)
    finally:
        os.close(fd)


def decode_native_output(raw, *, maximum_payload, maximum_metadata):
    """Fixed collector-owned flat MAT-v5 envelope; no arbitrary struct decoder."""
    need(type(raw) is bytes and len(raw) <= maximum_payload + 2 * maximum_metadata + 4096,
         "Native MAT envelope exceeds admitted extent")
    need(raw[:19] == b"MATLAB 5.0 MAT-file" and raw[126:128] in (b"IM", b"MI"), "Only the reviewed v5 collector envelope is supported")
    try:
        from scipy.io import loadmat
    except ImportError as exc:
        raise NativeError("SciPy native output decoder unavailable; no installation or fallback") from exc
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        parsed = loadmat(io.BytesIO(raw), appendmat=False, squeeze_me=False, chars_as_strings=False,
                         struct_as_record=True, verify_compressed_data_integrity=True)
    parsed = {k: v for k, v in parsed.items() if k not in ("__header__", "__version__", "__globals__")}
    need(set(parsed) == {"meta_json", "payload"} and parsed["meta_json"].dtype.kind == "U"
         and parsed["payload"].dtype == np.dtype("uint8"), "Exact collector top-level fields/dtypes required")
    text = "".join(parsed["meta_json"].ravel(order="F").tolist())
    need(len(text.encode()) <= maximum_metadata, "Native metadata limit exceeded")
    from .wire import parse
    envelope = parse(text.encode(), maximum_metadata)
    need(type(envelope) is dict and set(envelope) == {"metadata", "arrays"}, "Exact native envelope schema required")
    payload = parsed["payload"].ravel(order="F").tobytes()
    need(len(payload) <= maximum_payload, "Native raw array payload limit exceeded")
    arrays, position = {}, 0
    for entry in envelope["arrays"]:
        need(type(entry) is dict and set(entry) == {"name", "dtype", "shape", "offset", "bytes"}, "Exact native binary array descriptor required")
        name, shape, dtype = entry["name"], entry["shape"], entry["dtype"]
        need(type(name) is str and name not in arrays and dtype in ("<f8", "<i8", "|b1")
             and type(shape) is list and 1 <= len(shape) <= 3 and all(type(i) is int and i >= 0 for i in shape),
             "Unsupported/duplicate native binary array descriptor")
        count = int(np.prod(shape, dtype=object)) * np.dtype(dtype).itemsize
        need(type(entry["offset"]) is int and entry["offset"] == position and entry["bytes"] == count
             and position + count <= len(payload), "Native binary payload has gaps/overlap/truncation")
        a = np.frombuffer(payload[position:position+count], dtype=dtype).reshape(shape, order="F")
        arrays[name] = np.array(a, copy=True, order="C")
        position += count
    need(position == len(payload), "Native collector payload has undeclared trailing bytes")
    return envelope["metadata"], arrays


def _packet_digest(packet, limits):
    manifest, _ = encode(packet, WireLimits(**limits))
    return sha(manifest)


def _failure_artifacts(work, limits, instrumentation, stage, exit_code, deadline_ns):
    artifacts = {"stage": stage, "exit_code": exit_code, "instrumentation": instrumentation,
                 "scientific_success": False, "custody": "requires_external_independent_closure", "files": {}, "refusals": {}}
    for name, bound in (("capture_private.mat", limits["output_bytes"]), ("stdout.log", limits["log_bytes"]),
                        ("stderr.log", limits["log_bytes"])):
        try:
            need(time.monotonic_ns() < deadline_ns, "Original deadline prohibits further failure-artifact reads")
            artifacts["files"][name] = _read_absolute(str(work / name), bound)
        except (OSError, NativeError) as exc:
            artifacts["refusals"][name] = type(exc).__name__
    # Failure bytes require the same complete transport budget. No trimming or
    # discarding source arrays to convert a failure into a partial success.
    try:
        encode(artifacts, WireLimits(**limits["wire"]))
    except Exception as exc:
        raise NativeExecutionFailure("Native failure artifacts exceed transport; retain scratch for separately authorized recovery",
            {"stage": stage, "exit_code": exit_code, "scientific_success": False,
             "custody": "unknown_until_external_closure", "scratch_recovery_required": True}) from exc
    return artifacts


def run_native(job, packet=None):
    """Trusted isolated worker entry. No native process before signed admission.

    Public verification key has one image-pinned path and is never selected by a
    job. A failure/timeout leaves custody to the external qualified supervisor;
    this function sends no signals and never manufactures a natural-zero receipt.
    """
    need(type(job) is dict and job.get("operation") == "literal_native" and type(job.get("native_envelope")) is dict
         and job["native_envelope"].get("document", {}).get("installed") is True,
         "Independent signed native installation required before original source/process access")
    from .authority import verify_document
    public_key = _read_absolute(PUBLIC_KEY, 32)
    need(len(public_key) == 32, "Image-pinned operator public key has wrong extent")
    document = verify_document(job["native_envelope"], public_key)
    required = {"schema", "installed", "origin_ns", "deadline_ns", "phase_keys", "phase_packets", "source_root", "source_files",
                "capture", "matlab", "worker", "work_root", "limits", "matlab_version", "admission_digest",
                "instrumentation_review_sha256", "instrumentation", "expected_times", "expected_cell_ids", "role_admission_sha256"}
    need(type(document) is dict and set(document) == required and document["schema"] == "paper020_signed_native_runtime_v1",
         "Exact reviewed native deployment schema required")
    origin, deadline = document["origin_ns"], document["deadline_ns"]
    need(job.get("origin_ns") == origin and job.get("deadline_ns") == deadline, "Native signature must bind the unchanged inherited original clock")
    need(type(origin) is int and type(deadline) is int and origin <= time.monotonic_ns() < deadline,
         "Inherited original native deadline expired")
    try:
        from scipy.io import loadmat as _native_decoder_available
    except ImportError as exc:
        raise NativeError("SciPy decoder absent; native execution refused before original source or executable access") from exc
    expected_keys = [list(k) for k in literal_phase_keys()]
    need(document["phase_keys"] == expected_keys and set(document["phase_packets"]) == {"/".join(k) for k in literal_phase_keys()},
         "All original56 literal phases/packet bindings must be independently approved")
    phase = job.get("phase")
    need(type(phase) is dict and phase.get("family") == "native_literal", "Exact source-selected literal phase required")
    key = (phase.get("configuration"), phase.get("mode"), phase.get("method"))
    need(key in literal_phase_keys(), "Unknown original literal phase")
    limits = document["limits"]
    need(type(limits) is dict and set(limits) == {"wire", "source_read_bytes", "member_bytes", "output_bytes", "metadata_bytes", "log_bytes"}
         and all(type(limits[k]) is int and limits[k] > 0 for k in limits if k != "wire"), "Explicit independently approved native resource ceilings required")
    need(_packet_digest(packet, limits["wire"]) == document["phase_packets"]["/".join(key)], "Native packet differs from signed source/index/cell/time binding")
    contract = basis("programme").validate_contract(json.loads((scientific_root() / "contracts/programme.json").read_text()))
    need(set(document["source_files"]) == set(contract["source_release"]["regular_files"])
         and all(document["source_files"][k]["bytes"] == v for k, v in contract["source_release"]["regular_files"].items()),
         "Exact complete43 original source membership/size pins required")
    # Qualified mounts must be immutable and exclude candidate paths; authentic
    # file verification here is additional bounded I/O for every literal phase.
    owned = _OwnedRelease(document["source_root"], document["source_files"],
                          Limits(limits["source_read_bytes"], limits["member_bytes"], 1, 1, 1))
    source_helpers = {}
    try:
        for member in sorted(document["source_files"]):
            raw = owned.snapshot(member)
            if member in {"data and code/code/" + n for n in ("analysis_STA.m", "STA_sub.m", "load_data.m")}:
                source_helpers[PurePosixPath(member).name] = raw
        owned.verify()
    finally:
        owned.close()
    pinned = {}
    for name in ("capture", "matlab", "worker"):
        facts = document[name]
        need(type(facts) is dict and set(facts) == {"path", "bytes", "sha256"}, "Pinned native executable/source identity required")
        raw = _read_absolute(facts["path"], facts["bytes"])
        need(len(raw) == facts["bytes"] and sha(raw) == facts["sha256"], "Pinned native executable/source differs")
        pinned[name] = raw
    need(document["capture"]["sha256"] == CAPTURE_SHA256 and pinned["worker"] == Path(__file__).with_name("native_worker.m").read_bytes(),
         "Frozen capture/source-owned worker identities differ")
    instrumented, instrumentation = instrument_sources(pinned["capture"], source_helpers)
    need(instrumentation == document["instrumentation"], "Instrumentation must be independently reviewed and signed before execution")
    work = Path(document["work_root"])
    need(work.is_absolute() and not work.exists() and ".." not in work.parts, "Fresh operator-owned native work root required")
    work.mkdir(mode=0o700)
    helpers = work / "helpers"
    helpers.mkdir(mode=0o700)
    for name, raw in instrumented.items():
        _write_new(work / name if name == "native_capture.m" else helpers / name, raw)
    _write_new(work / "native_worker.m", pinned["worker"])
    request = {"future_execution_authorized": True, "admission_sha256": document["admission_digest"],
               "instrumentation_review_sha256": document["instrumentation_review_sha256"],
               "release_root": str(Path(document["source_root"]) / "data and code"), "matlab_version": document["matlab_version"],
               "expected_times": [{"values": x} for x in document["expected_times"]], "expected_cell_ids": [{"values": x} for x in document["expected_cell_ids"]],
               "role_admission_sha256": document["role_admission_sha256"], "original_clock_origin": origin / 1e9,
               "original_clock_origin_ns": str(origin), "original_clock_deadline_ns": str(deadline),
               "instrumented_helper_root": str(helpers), "selection": [list(basis("programme").CONFIGS).index(key[0]) + 1,
               1 if key[2] == "STA" else 2, 1 if key[1] == "static" else 2],
               "instrumentation": _instrumentation_wire(instrumentation), "output_byte_limit": limits["output_bytes"],
               "metadata_byte_limit": limits["metadata_bytes"]}
    _write_new(work / "request.json", canonical(request))
    # Quoting is single-argument MATLAB syntax, never a shell. Only owned paths
    # are inserted; apostrophes are MATLAB-escaped rather than shell-interpreted.
    quote = lambda x: "'" + str(x).replace("'", "''") + "'"
    expression = "addpath(" + quote(work) + ",'-begin');native_worker(" + quote(work / "request.json") + "," + quote(work / "output.mat") + ");"
    remaining = (deadline - time.monotonic_ns()) / 1e9
    need(remaining > 0, "Original deadline exceeded before native process")
    with open(work / "stdout.log", "xb") as stdout, open(work / "stderr.log", "xb") as stderr:
        before_spawn = time.monotonic_ns()
        need(origin <= before_spawn < deadline,
             "Original native deadline expired after blocking log preparation")
        process = subprocess.Popen([document["matlab"]["path"], "-batch", expression], cwd=work,
                                   stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, close_fds=True)
        try:
            remaining = (deadline - time.monotonic_ns()) / 1e9
            if remaining <= 0:
                raise subprocess.TimeoutExpired(document["matlab"]["path"],0)
            code = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as exc:
            raise NativeExecutionFailure("Original native deadline expired; external supervisor retains process custody",
                {"stage": "native_timeout", "origin_ns": origin, "deadline_ns": deadline,
                 "custody": "unknown_until_external_closure", "scratch_recovery_required": True}) from exc
    if time.monotonic_ns() >= deadline:
        raise NativeExecutionFailure("Native process exceeded original deadline; separately authorized scratch recovery required",
            {"stage": "native_deadline", "exit_code": code, "origin_ns": origin, "deadline_ns": deadline,
             "custody": "requires_external_independent_closure", "scratch_recovery_required": True})
    if code != 0:
        raise NativeExecutionFailure("Native process failed",
              _failure_artifacts(work, limits, instrumentation, "native_exit", code, deadline))
    try:
        for name in ("stdout.log", "stderr.log"):
            _read_absolute(str(work / name), limits["log_bytes"])
        raw = _read_absolute(str(work / "output.mat"), limits["output_bytes"] + 2 * limits["metadata_bytes"] + 4096)
        metadata, arrays = decode_native_output(raw, maximum_payload=limits["output_bytes"], maximum_metadata=limits["metadata_bytes"])
        record = convert_native_payload(metadata, arrays, packet, phase, expected_instrumentation=instrumentation)
        capture_raw = _read_absolute(str(work / "capture_private.mat"), limits["output_bytes"])
        record["provenance"]["native_capture_artifact_sha256"] = sha(capture_raw)
        record["provenance"]["original_clock_origin_ns"] = origin
        record["provenance"]["original_clock_deadline_ns"] = deadline
        wrapper = {"record": record, "raw_capture": capture_raw, "instrumentation": instrumentation}
        encode(wrapper, WireLimits(**limits["wire"]))
        need(time.monotonic_ns() < deadline, "Native output conversion/transport exceeded the unchanged original deadline")
        return wrapper
    except Exception as exc:
        raise NativeExecutionFailure("Native output conversion/transport failed; original capture retained",
            _failure_artifacts(work, limits, instrumentation, "native_conversion", code, deadline)) from exc
