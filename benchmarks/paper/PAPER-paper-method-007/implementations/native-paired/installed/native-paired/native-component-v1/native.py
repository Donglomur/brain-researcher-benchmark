"""Source-owned future UnitMatch native process. No MATLAB qualification is claimed.

The parent must authenticate stage_descriptor against the fixed original packet,
including the cohort's exact two-field removal, before calling run_native.
This adapter authenticates that approved stage, launches its own captured MATLAB
entry point, and accepts only complete, identity-joined natural-zero products.
Process/product limits are admission and monitoring controls, not OS isolation.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import selectors
import shutil
import signal
import stat
import subprocess
import time

OFFICIAL_COMMIT = "6ef0023cb4a7be0a94dabbab24bb79c084b6fb1e"
PACKET_PIN = {"bytes": 1320185, "sha256": "8f361ac6074f5306ba4cf0c07e6593ec4eaefe6d5a4e0851448a89fa73917a89"}
COHORT_PIN = {"bytes": 532569, "sha256": "7ed4a18626ca53c13d97beb12182e2240dbd6e8131dd9bdceecd696985b904f1"}
M_PIN = {"bytes": 4690, "sha256": "4c8d943744549d3e17efd589630ca917e087fc010633372208e40587240ab8dc"}
COUNTS = {"Mouse1": 534, "Mouse2": 109, "Mouse3": 96, "Mouse4": 59, "Mouse5": 466}
WAVEFORM_COUNT = 3836
LIMIT_NAMES = {
    "timeout_seconds", "terminate_grace_seconds", "max_stdout_bytes",
    "max_stderr_bytes", "max_stream_bytes", "max_product_file_bytes",
    "max_product_total_bytes", "max_product_files", "max_metadata_bytes",
    "max_total_read_bytes", "max_total_write_bytes", "min_free_bytes",
}
RECEIPT_RESERVE = 32768


class NativeFailure(RuntimeError):
    """Products and observations remain at output_root; no retry is performed."""
    def __init__(self, message, receipt):
        super().__init__(message)
        self.receipt = receipt


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _integer(value, minimum=0):
    return type(value) is int and value >= minimum


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _json_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _object_pairs(pairs):
    answer = {}
    for key, value in pairs:
        _require(key not in answer, "duplicate JSON key")
        answer[key] = value
    return answer


def _json_load(body):
    def bad_constant(value):
        raise ValueError("nonfinite JSON constant: " + value)
    return json.loads(body, object_pairs_hook=_object_pairs, parse_constant=bad_constant)


def _pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def _check_pin(value):
    _require(isinstance(value, dict) and _integer(value.get("bytes")), "invalid file pin")
    sha = value.get("sha256")
    _require(isinstance(sha, str) and len(sha) == 64 and all(c in "0123456789abcdef" for c in sha), "invalid SHA256")
    return {"bytes": value["bytes"], "sha256": sha}


def _relative(value):
    _require(isinstance(value, str) and value and "\\" not in value and "\x00" not in value, "invalid relative path")
    p = PurePosixPath(value)
    _require(not p.is_absolute() and value == p.as_posix() and all(x not in ("", ".", "..") for x in p.parts), "unsafe relative path")
    return value


def _absolute(value, exists=True):
    p = Path(value)
    _require(all(part not in (".", "..") for part in p.parts), "noncanonical absolute path")
    _require(p.is_absolute() and str(p) == str(value) and "\x00" not in str(p) and "\n" not in str(p) and "\r" not in str(p), "absolute normalized path required")
    for part in (p, *p.parents):
        if part.exists() or part.is_symlink():
            _require(not part.is_symlink(), "symlink path component")
    _require(not exists or p.exists(), "path missing")
    return p


def _file_stat(path):
    s = path.lstat()
    _require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, "ordinary single-link file required: " + str(path))
    return s


def _stable_stat(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def _open_regular(path):
    # O_NONBLOCK prevents a substituted FIFO/device from blocking admission.
    # O_NOFOLLOW binds the final component; host isolation owns ancestor races.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        s = os.fstat(fd)
        _require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, "ordinary single-link open file required: " + str(path))
        return fd, s
    except BaseException:
        os.close(fd)
        raise


def _stable_open_path(fd, path, before):
    _require(_stable_stat(os.fstat(fd)) == _stable_stat(before), "open file changed during read")
    _require(_stable_stat(_file_stat(path)) == _stable_stat(before), "file path changed during read")


def _cluster_integer(value):
    # h5py .tolist() may preserve an integral floating storage representation.
    # No rounding, truncation, boolean alias, or mutation of raw metadata.
    _require(type(value) in (int, float), "nonnumeric cluster metadata ID")
    if type(value) is float:
        _require(math.isfinite(value), "nonfinite cluster metadata ID")
    _require(value >= 0, "negative cluster metadata ID")
    integer = int(value)
    _require(value == integer, "nonintegral cluster metadata ID")
    return integer


def _census(root):
    answer = {}
    _require(root.is_dir() and not root.is_symlink(), "ordinary directory required")
    for here, dirs, files in os.walk(root, followlinks=False):
        for name in dirs:
            p = Path(here) / name
            _require(not p.is_symlink() and p.is_dir(), "nonordinary directory")
        for name in files:
            p = Path(here) / name
            answer[p.relative_to(root).as_posix()] = _file_stat(p)
    return answer


class _Budget:
    def __init__(self, limits, root):
        _require(isinstance(limits, dict) and set(limits) == LIMIT_NAMES, "exact explicit limits required")
        for key, value in limits.items():
            if key.endswith("_seconds"):
                _require(_finite(value) and value > 0, "positive finite seconds required")
            else:
                _require(_integer(value, 1), "positive integer limit required")
        _require(limits["max_stream_bytes"] <= limits["max_stdout_bytes"] + limits["max_stderr_bytes"], "incoherent stream caps")
        _require(limits["max_product_file_bytes"] <= limits["max_product_total_bytes"], "incoherent product caps")
        _require(limits["max_total_write_bytes"] > RECEIPT_RESERVE, "receipt reserve unavailable")
        self.limits, self.root = limits, root
        self.read_bytes = self.write_bytes = self.external_product_bytes = 0

    def free(self):
        _require(shutil.disk_usage(self.root).free >= self.limits["min_free_bytes"], "free-space floor")

    def read_charge(self, amount):
        _require(self.read_bytes + amount <= self.limits["max_total_read_bytes"], "read quota")
        self.read_bytes += amount

    def write_charge(self, amount, receipt=False):
        ceiling = self.limits["max_total_write_bytes"] - (0 if receipt else RECEIPT_RESERVE)
        _require(self.write_bytes + self.external_product_bytes + amount <= ceiling, "write quota")
        self.write_bytes += amount  # Charge before write/fsync, including failed writes.
        self.free()

    def read(self, path, maximum=None):
        fd, s = _open_regular(path)
        try:
            if maximum is not None:
                _require(s.st_size <= maximum, "file admission quota")
            remaining = s.st_size + 1
            self.read_charge(remaining)  # Reserve the growth-detection byte even on failure.
            chunks = []
            while remaining:
                block = os.read(fd, min(65536, remaining))
                if not block:
                    break
                chunks.append(block)
                remaining -= len(block)
            body = b"".join(chunks)
            _require(len(body) == s.st_size, "file extent changed during read")
            _stable_open_path(fd, path, s)
            return body
        finally:
            os.close(fd)

    def digest(self, path):
        fd, s = _open_regular(path)
        try:
            remaining = s.st_size + 1
            self.read_charge(remaining)
            h = hashlib.sha256()
            total = 0
            while remaining:
                block = os.read(fd, min(1048576, remaining))
                if not block:
                    break
                remaining -= len(block)
                total += len(block)
                _require(total <= s.st_size, "file grew during hash")
                h.update(block)
            _require(total == s.st_size, "file extent changed during hash")
            _stable_open_path(fd, path, s)
            return {"bytes": total, "sha256": h.hexdigest()}
        finally:
            os.close(fd)

    def write(self, path, body, receipt=False):
        self.write_charge(len(body), receipt=receipt)
        with path.open("xb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())

    def products(self, product_root):
        if not product_root.exists():
            return {}
        entries = _census(product_root)
        total = sum(s.st_size for s in entries.values())
        # Native external writes cannot be charged before MATLAB makes them.
        # This high-water observation is explicit; OS enforcement belongs to host.
        self.external_product_bytes = max(self.external_product_bytes, total)
        _require(len(entries) <= self.limits["max_product_files"], "native product count quota")
        _require(all(s.st_size <= self.limits["max_product_file_bytes"] for s in entries.values()), "native product file quota")
        _require(total <= self.limits["max_product_total_bytes"], "native product total quota")
        _require(self.write_bytes + self.external_product_bytes <= self.limits["max_total_write_bytes"] - RECEIPT_RESERVE, "native total write quota")
        self.free()
        return entries


def _validate_cohort(cohort, paths):
    _require(isinstance(cohort, dict) and cohort.get("schema") == "unitmatch_cohort_v1", "cohort schema")
    mice = cohort.get("mice")
    _require(isinstance(mice, list) and [m.get("mouse_id") for m in mice] == list(COUNTS), "five fixed mice/order")
    required = set()
    waveform_count = 0
    for mouse in mice:
        mid = mouse["mouse_id"]
        sessions, units = mouse.get("sessions"), mouse.get("units")
        _require(isinstance(sessions, list) and len(sessions) == 2, "two sessions required")
        _require(isinstance(units, list) and len(units) == COUNTS[mid], "fixed good-unit count")
        expected_units = []
        for number, session in enumerate(sessions, 1):
            _require(session.get("session") == number, "session order")
            _require("source_prepared" not in session and "prepared_sha256" not in session, "functional metadata exposed")
            data_dir = _relative(session["data_dir"])
            _require(data_dir.startswith("data/" + mid + "/"), "waveform data directory")
            meta = session.get("cluster_metadata")
            _require(isinstance(meta, dict) and set(meta) == {"cluster_id", "Good_ID", "ProbeID", "Shank", "depth"}, "cluster metadata columns")
            raw_ids = meta["cluster_id"]
            _require(isinstance(raw_ids, list), "original cluster ID list")
            ids = [_cluster_integer(value) for value in raw_ids]
            _require(len(set(ids)) == len(ids), "unique original cluster ids")
            _require(all(isinstance(v, list) and len(v) == len(ids) for v in meta.values()), "cluster column lengths")
            _require(all((type(g) is bool or _finite(g)) and g in (0, 1) for g in meta["Good_ID"]), "original Good_ID indicators")
            good = [cid for cid, flag in zip(ids, meta["Good_ID"]) if flag == 1]
            _require(session.get("good_cluster_ids") == good, "Good_ID membership/order")
            expected_units.extend({"session": number, "cluster_id": cid} for cid in good)
            required.add("public/" + data_dir + "/channel_positions.npy")
            for cid in ids:
                required.add("public/" + data_dir + "/RawWaveforms/Unit" + str(cid) + "_RawSpikes.npy")
                waveform_count += 1
        _require(units == expected_units, "original good-unit identity/order")
    _require(waveform_count == WAVEFORM_COUNT, "complete original waveform cohort")
    _require(required <= paths, "missing waveform/channel stage roles")
    actual_arrays = {p for p in paths if p.startswith("public/data/")}
    _require(actual_arrays == required, "extra data role in native stage")
    return mice


def _stage(stage_root, descriptor, budget):
    _require(isinstance(descriptor, dict) and descriptor.get("schema") == "unitmatch_native_stage_v1", "stage schema")
    _require(descriptor.get("official_commit") == OFFICIAL_COMMIT, "official source revision")
    _require(_check_pin(descriptor.get("packet_map")) == PACKET_PIN, "fixed original packet anchor")
    _require(_check_pin(descriptor.get("cohort_original")) == COHORT_PIN, "fixed original cohort anchor")
    _require(type(descriptor.get("functional_files_staged")) is int and descriptor["functional_files_staged"] == 0, "functional stage forbidden")
    rows = descriptor.get("files")
    _require(isinstance(rows, list) and rows, "complete stage file inventory")
    expected = {}
    for row in rows:
        _require(isinstance(row, dict) and "validation_mouse" not in row, "functional packet row forbidden")
        path = _relative(row.get("path"))
        _require(path not in expected, "duplicate stage path")
        parts = PurePosixPath(path).parts
        _require(not path.startswith("private/data/") and "PreparedData" not in path and "validation_mouse" not in parts, "functional path forbidden")
        _require(not path.startswith("private/") or path.startswith("private/author_source/"), "private native stage boundary")
        expected[path] = _check_pin(row)
    _require("public/cohort.json" in expected, "missing sanitized cohort")
    _require(expected["public/cohort.json"] == _check_pin(descriptor.get("cohort_sanitized")), "sanitized cohort pin join")
    entries = _census(stage_root)
    _require(set(entries) == set(expected), "stage physical inventory differs")
    for path, s in entries.items():
        _require(stat.S_IMODE(s.st_mode) == 0o444, "stage file must be 0444")
        _require(budget.digest(stage_root / path) == expected[path], "staged source/input bytes changed")
    for here, dirs, _ in os.walk(stage_root):
        _require(stat.S_IMODE(Path(here).stat().st_mode) == 0o555, "stage directory must be 0555")
    cohort_body = budget.read(stage_root / "public/cohort.json", budget.limits["max_metadata_bytes"])
    _require(_pin(cohort_body) == expected["public/cohort.json"], "cohort changed after stage validation")
    cohort = _json_load(cohort_body)
    mice = _validate_cohort(cohort, set(expected))
    _require(any(p.startswith("private/author_source/MATLAB/") and p.endswith("/UnitMatch.m") for p in expected) or
             "private/author_source/MATLAB/UnitMatch.m" in expected, "official MATLAB source missing")
    return mice, expected


def _validate_pairs(document, mouse):
    _require(isinstance(document, dict), "pair product object")
    keys = {"schema", "mouse_id", "unit_count", "row_count", "seed", "units", "session1", "cluster1", "session2", "cluster2", "probability"}
    _require(set(document) == keys and document["schema"] == "unitmatch_native_pairs_v1", "pair schema/keys")
    n, mid = len(mouse["units"]), mouse["mouse_id"]
    _require(document["mouse_id"] == mid and type(document["unit_count"]) is int and document["unit_count"] == n, "pair mouse/unit count")
    _require(type(document["row_count"]) is int and document["row_count"] == n*n, "full directed row count")
    _require(type(document["seed"]) is int and document["seed"] == 0, "seed must be zero")
    _require(document["units"] == mouse["units"], "captured original units mismatch")
    names = ("session1", "cluster1", "session2", "cluster2", "probability")
    _require(all(isinstance(document[k], list) and len(document[k]) == n*n for k in names), "pair column extent")
    lookup = {(unit["session"], unit["cluster_id"]): i for i, unit in enumerate(mouse["units"])}
    _require(len(lookup) == n, "duplicate cohort identity")
    matrix = [[None] * n for _ in range(n)]
    for s1, c1, s2, c2, probability in zip(*(document[k] for k in names)):
        _require(all(type(x) is int for x in (s1, c1, s2, c2)), "noninteger pair identity")
        _require((s1, c1) in lookup and (s2, c2) in lookup, "unknown original pair identity")
        i, j = lookup[(s1, c1)], lookup[(s2, c2)]
        _require(matrix[i][j] is None, "duplicate directed pair")
        _require(_finite(probability) and 0 <= probability <= 1, "invalid native probability")
        matrix[i][j] = probability
    _require(all(value is not None for row in matrix for value in row), "missing directed pair")
    return matrix


def _matlab_string(value):
    return "'" + str(value).replace("'", "''") + "'"


def _group_signal(process, sig):
    # The original leader can exit while descendants still hold its pipes.
    try:
        os.killpg(process.pid, sig)
    except ProcessLookupError:
        pass


def _group_exists(process):
    try:
        os.killpg(process.pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _close_group(process, grace):
    _group_signal(process, signal.SIGTERM)
    deadline = time.monotonic() + grace
    while _group_exists(process) and time.monotonic() < deadline:
        time.sleep(min(0.01, grace))
    if _group_exists(process):
        _group_signal(process, signal.SIGKILL)
        deadline = time.monotonic() + grace
        while _group_exists(process) and time.monotonic() < deadline:
            time.sleep(min(0.01, grace))
    return not _group_exists(process)


def _run_process(argv, cwd, products, budget, receipt):
    streams = {"stdout": cwd.parent / "stdout.bin", "stderr": cwd.parent / "stderr.bin"}
    handles = {}
    counts = {name: 0 for name in streams}
    hashes = {name: hashlib.sha256() for name in streams}
    process = None
    selector = None
    reason = None
    started = time.monotonic()
    stop_at = None
    complete = False
    eof = set()
    try:
        for name, path in streams.items():
            handles[name] = path.open("xb")
        selector = selectors.DefaultSelector()
        process = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True, close_fds=True)
        receipt["process_started"] = True
        receipt["pid"] = process.pid
        for name in streams:
            pipe = getattr(process, name)
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ, name)
        while selector.get_map() or process.poll() is None:
            now = time.monotonic()
            if reason is None:
                try:
                    budget.products(products)
                except Exception as exc:
                    reason = "product_monitor: " + str(exc)
                if now - started >= budget.limits["timeout_seconds"]:
                    reason = "timeout"
                if reason:
                    stop_at = now
                    _group_signal(process, signal.SIGTERM)
            if stop_at is not None and now - stop_at >= budget.limits["terminate_grace_seconds"]:
                _group_signal(process, signal.SIGKILL)
                # A grandchild may hold inherited pipes. Bounded drain failure is explicit.
                if now - stop_at >= 2 * budget.limits["terminate_grace_seconds"]:
                    break
            for key, _ in selector.select(0.05):
                name = key.data
                room = min(budget.limits["max_" + name + "_bytes"] - counts[name],
                           budget.limits["max_stream_bytes"] - sum(counts.values()))
                if room <= 0:
                    reason = reason or "stream cap exhausted before EOF"
                    stop_at = stop_at or time.monotonic()
                    _group_signal(process, signal.SIGTERM)
                    selector.unregister(key.fileobj)
                    # No extra byte is read and discarded. This stream is incomplete.
                    continue
                data = os.read(key.fileobj.fileno(), min(65536, room))
                if not data:
                    eof.add(name)
                    selector.unregister(key.fileobj)
                    continue
                budget.write_charge(len(data))
                handles[name].write(data)
                counts[name] += len(data)
                hashes[name].update(data)
        complete = eof == set(streams)
        if process.poll() is None:
            _group_signal(process, signal.SIGKILL)
        try:
            code = process.wait(timeout=budget.limits["terminate_grace_seconds"])
        except subprocess.TimeoutExpired:
            code = None
            reason = reason or "process did not reap"
        if _group_exists(process):
            reason = reason or "owned process-group members survived root exit"
            _close_group(process, budget.limits["terminate_grace_seconds"])
        receipt["owned_group_absent"] = not _group_exists(process)
        receipt["returncode"] = code
        receipt["stop_reason"] = reason
        receipt["streams_complete"] = complete
        receipt["process_natural_zero"] = code == 0 and reason is None and complete and receipt["owned_group_absent"]
    except BaseException as exc:
        # Cleanup must neither replace this exception nor turn its run into success.
        receipt["process_error"] = {"type": type(exc).__name__, "message": str(exc)}
        receipt["process_natural_zero"] = False
        receipt["natural_zero"] = False
        raise
    finally:
        finalization_errors = []

        def attempt(operation, action, stream=None):
            try:
                return True, action()
            except BaseException as exc:
                finalization_errors.append({"operation": operation, "stream": stream,
                                            "type": type(exc).__name__, "message": str(exc)})
                return False, None

        # Retire every independently owned resource even if another operation fails.
        receipt["owned_group_absent"] = process is None
        if process is not None:
            polled, status = attempt("process.poll", process.poll)
            if not polled or status is None:
                attempt("process.kill_group", lambda: _group_signal(process, signal.SIGKILL))
                attempt("process.wait", lambda: process.wait(timeout=budget.limits["terminate_grace_seconds"]))
            checked, exists = attempt("process.group_exists", lambda: _group_exists(process))
            if not checked or exists:
                attempt("process.close_group", lambda: _close_group(process, budget.limits["terminate_grace_seconds"]))
            checked, exists = attempt("process.group_exists_final", lambda: _group_exists(process))
            receipt["owned_group_absent"] = checked and not exists
        for name, handle in handles.items():
            attempt("stream.flush", handle.flush, name)
            attempt("stream.fsync", lambda handle=handle: os.fsync(handle.fileno()), name)
            attempt("stream.close", handle.close, name)
        if selector is not None:
            attempt("selector.close", selector.close)
        if process is not None:
            for name in streams:
                attempt("pipe.close", lambda name=name: getattr(process, name).close(), name)
        timed, finished = attempt("duration.monotonic", time.monotonic)
        receipt["duration_seconds"] = finished - started if timed else None
        receipt["streams"] = {name: {"path": path.name, "open_state": "opened" if name in handles else "unopened",
                                    "bytes": counts[name], "sha256": hashes[name].hexdigest()} for name, path in streams.items()}
        receipt["finalization_errors"] = finalization_errors
        receipt["stream_finalization_complete"] = not any(e["operation"].startswith("stream.") for e in finalization_errors)
        if finalization_errors or not receipt["owned_group_absent"]:
            receipt["process_natural_zero"] = False
            receipt["natural_zero"] = False


def run_native(stage_root, output_root, matlab_binary, executable_pin, stage_descriptor, limits, *, expected_source_pin):
    """Launch fixed captured MATLAB code. The caller must authenticate source lock.

    output_root must be absent. On any failure NativeFailure.receipt is returned
    as exception evidence, with all existing source, raw streams and products
    retained. There is no input baseline, provider, fake mode, or qualification
    flag. Local file integrity is checked; hostile processes/host paths require
    the parent's qualified isolation and resource enforcement.

    expected_source_pin is mandatory: the parent supplies the identity of the
    exact authenticated native.py bytes it compiled, not a later path reread.
    """
    stage = _absolute(stage_root)
    binary = _absolute(matlab_binary)
    out = _absolute(output_root, exists=False)
    _require(not out.exists() and out.parent.is_dir(), "fresh output root required")
    _require(out != stage and stage not in out.parents and out not in stage.parents, "stage/output overlap")
    source_path = _absolute(str(Path(__file__).absolute()))
    m_path = source_path.with_name("unitmatch_native_capture.m")
    expected_binary = _check_pin(executable_pin)
    expected_source = _check_pin(expected_source_pin)
    _require(_file_stat(binary).st_mode & 0o111, "executable permission required")
    out.mkdir(mode=0o700)
    budget = _Budget(limits, out)
    receipt = {"schema": "unitmatch_native_process_receipt_v1", "status": "started",
               "process_started": False, "natural_zero": False, "streams_complete": False,
               "scientifically_qualified": False, "official_commit": OFFICIAL_COMMIT,
               "source_lock_authority": "parent-authenticated fixed packet selection; adapter checks this stage",
               "original_packet": PACKET_PIN, "original_cohort": COHORT_PIN,
               "limits": dict(limits),
               "resource_enforcement": "observed logical transfers and product high-water bytes; external writes need host enforcement"}
    products = out / "products"
    try:
        source = out / "source"
        source.mkdir(mode=0o700)
        own_body = budget.read(source_path, limits["max_metadata_bytes"])
        _require(_pin(own_body) == expected_source, "compiled adapter source pin mismatch")
        m_body = budget.read(m_path, limits["max_metadata_bytes"])
        _require(_pin(m_body) == M_PIN, "fixed MATLAB entry point changed")
        descriptor_body = _json_bytes(stage_descriptor)
        _require(len(descriptor_body) <= limits["max_metadata_bytes"], "descriptor admission quota")
        budget.write(source / "native.py", own_body)
        budget.write(source / "unitmatch_native_capture.m", m_body)
        budget.write(source / "stage_descriptor.json", descriptor_body)
        receipt["source"] = {"native.py": expected_source, "unitmatch_native_capture.m": _pin(m_body),
                             "stage_descriptor.json": _pin(descriptor_body)}
        _require(budget.digest(binary) == expected_binary, "executable pin mismatch")
        receipt["executable"] = {"path": str(binary), **expected_binary}
        mice, stage_pins = _stage(stage, stage_descriptor, budget)
        receipt["stage_files"] = len(stage_pins)
        receipt["stage_bytes"] = sum(p["bytes"] for p in stage_pins.values())
        # Capture the exact cohort consumed; no original functional cohort is opened.
        sanitized_body = budget.read(stage / "public/cohort.json", limits["max_metadata_bytes"])
        _require(_pin(sanitized_body) == stage_pins["public/cohort.json"], "cohort capture mismatch")
        budget.write(source / "cohort.sanitized.json", sanitized_body)
        for path in source.iterdir():
            path.chmod(0o444)
        source.chmod(0o555)
        expression = "addpath(" + _matlab_string(source) + ");unitmatch_native_capture(" + _matlab_string(stage) + "," + _matlab_string(products) + ");"
        argv = [str(binary), "-batch", expression]
        receipt["argv"] = argv
        _require(budget.digest(binary) == expected_binary, "executable changed before invocation")
        for name, pin in receipt["source"].items():
            _require(budget.digest(source / name) == pin, "captured source changed before invocation")
        _require(budget.write_bytes + limits["max_stream_bytes"] + limits["max_product_total_bytes"] + limits["max_metadata_bytes"] + RECEIPT_RESERVE <= limits["max_total_write_bytes"], "pre-admit complete stream/product/inventory write capacity")
        _run_process(argv, source, products, budget, receipt)
        # Post-process joins run for nonzero/timeout as well, where budget allows.
        _require(budget.digest(binary) == expected_binary, "executable changed during process")
        _require(budget.digest(source_path) == _pin(own_body), "original adapter source changed")
        _require(budget.digest(m_path) == M_PIN, "original MATLAB source changed")
        for name, pin in receipt["source"].items():
            _require(budget.digest(source / name) == pin, "captured source changed")
        _require(budget.digest(source / "cohort.sanitized.json") == _pin(sanitized_body), "captured cohort changed")
        _stage(stage, stage_descriptor, budget)
        entries = budget.products(products)
        pins = {}
        for path in sorted(entries):
            pins[path] = budget.digest(products / path)
        # Preserve complete native product inventory separately from small receipt.
        inventory = {"schema": "unitmatch_native_product_inventory_v1", "files": [{"path": p, **v} for p, v in pins.items()]}
        inventory_body = _json_bytes(inventory)
        _require(len(inventory_body) <= limits["max_metadata_bytes"], "product inventory quota")
        budget.write(out / "product_inventory.json", inventory_body)
        receipt["product_inventory"] = _pin(inventory_body)
        receipt["product_count"] = len(pins)
        receipt["product_bytes"] = sum(p["bytes"] for p in pins.values())
        _require(receipt.get("process_natural_zero"), "native process not a complete natural-zero run")
        required = {"completion.json"} | {m + ".pairs.json" for m in COUNTS}
        _require(required <= set(pins), "missing complete native products")
        marker = _json_load(budget.read(products / "completion.json", limits["max_metadata_bytes"]))
        _require(marker.get("schema") == "unitmatch_native_completion_v1" and marker.get("official_commit") == OFFICIAL_COMMIT, "completion source/schema")
        _require(marker.get("mouse_ids") == list(COUNTS) and marker.get("unit_counts") == list(COUNTS.values()) and type(marker.get("seed")) is int and marker["seed"] == 0, "completion cohort/seed")
        _require(isinstance(marker.get("matlab_version"), str) and marker["matlab_version"], "MATLAB version observation missing")
        toolboxes = marker.get("toolboxes")
        if isinstance(toolboxes, dict):
            toolboxes = [toolboxes]  # MATLAB JSON singleton struct representation.
        _require(isinstance(toolboxes, list) and toolboxes and all(isinstance(t, dict) and isinstance(t.get("Name"), str) and isinstance(t.get("Version"), str) for t in toolboxes), "MATLAB ver toolbox observations missing")
        receipt["runtime_observation_product"] = "products/completion.json"
        for key in ("unitmatch_function", "parameters_function", "npy_function"):
            observed = _absolute(marker.get(key))
            _require(stage in observed.parents, "MATLAB function outside pinned stage")
            rel = observed.relative_to(stage).as_posix()
            _require(rel.startswith("private/author_source/MATLAB/") and rel in stage_pins, "MATLAB function not in locked author source")
        folds = []
        for mouse in mice:
            mid = mouse["mouse_id"]
            name = mid + ".pairs.json"
            body = budget.read(products / name, limits["max_product_file_bytes"])
            _require(_pin(body) == pins[name], "pair product changed after capture")
            matrix = _validate_pairs(_json_load(body), mouse)
            folds.append({"held_out_mouse": mid, "development_mice": [m for m in COUNTS if m != mid], "probabilities": matrix})
        _require(budget.digest(products / "completion.json") == pins["completion.json"], "completion changed after capture")
        final_entries = budget.products(products)
        _require(set(final_entries) == set(entries), "native product extent changed")
        for path in pins:
            _require(budget.digest(products / path) == pins[path], "native product changed after validation")
        submission = {"schema": "unitmatch_submission_v1", "access_view": "B",
                      "method_name": "UnitMatch v2.0 native MATLAB, seed 0, source-conditioned five-mouse demo",
                      "folds": folds}
        receipt["status"] = "accepted_native_capture"
        receipt["natural_zero"] = True
        receipt["directed_entries"] = sum(n*n for n in COUNTS.values())
        receipt["accounting"] = {"read_bytes": budget.read_bytes, "own_write_bytes_before_receipt": budget.write_bytes,
                                 "external_product_high_water_bytes": budget.external_product_bytes}
        body = _json_bytes(receipt)
        _require(len(body) <= RECEIPT_RESERVE, "success receipt reserve")
        budget.write(out / "receipt.json", body, receipt=True)
    except Exception as exc:
        receipt["status"] = "failed"
        receipt["error"] = type(exc).__name__ + ": " + str(exc)
        receipt["natural_zero"] = False  # Failed products can never be accepted native provenance.
        receipt["accounting"] = {"read_bytes": budget.read_bytes, "own_write_bytes": budget.write_bytes,
                                 "external_product_high_water_bytes": budget.external_product_bytes}
        try:
            body = _json_bytes(receipt)
            _require(len(body) <= RECEIPT_RESERVE, "failure receipt reserve")
            budget.write(out / "failure.json", body, receipt=True)
        except Exception as capture_error:
            receipt["failure_capture_error"] = type(capture_error).__name__ + ": " + str(capture_error)
        raise NativeFailure(receipt["error"], receipt) from exc
    return {"submission": submission, "receipt": receipt}
