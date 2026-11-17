"""Unexecuted offline census controls; no scientific imports or default launch.

The caller must explicitly supply the already qualified worker, NumPy, scipy.io
and scipy.sparse modules. These controls create only small synthetic fixtures in
a temporary directory. They never call worker.main(), host_guard(), or use its
authentic original/output paths. An external guarded entrypoint is still needed.

This implements ten named core API controls from CONTROL_DESIGN.json. Whole
runtime/package qualification, process ceilings, atomic publication in main(),
and authentic biological hierarchy recovery are outside this unit-level suite.
"""
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import zlib


CONTROL_IDS = tuple("VO-CENSUS-%02d" % n for n in range(1, 11))
CAPTURE_LIMIT = 131072
FIXTURE_FILE_LIMIT = 1048576
SIGNAL_SENTINEL = 9876543210123457


class ControlFailure(Exception):
    """Only fixed, value-free codes are allowed into the returned ledger."""
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _check(condition, code):
    if not condition:
        raise ControlFailure(code)


class _Capture(io.StringIO):
    def write(self, text):
        if self.tell() + len(text) > CAPTURE_LIMIT:
            raise ControlFailure("diagnostic_capture_budget")
        return super().write(text)


@contextmanager
def _limits(worker, **limits):
    allowed = {"MAX_NODES", "MAX_CENSUS_BYTES", "MAX_TEXT_BYTES"}
    _check(set(limits) <= allowed, "unselected_limit_mutation")
    previous = {name: getattr(worker, name) for name in limits}
    try:
        for name, value in limits.items():
            _check(isinstance(value, int) and value >= 0, "invalid_control_limit")
            setattr(worker, name, value)
        yield
    finally:
        for name, value in previous.items():
            setattr(worker, name, value)


def _rows(buffer):
    return [json.loads(line) for line in buffer.getvalue().splitlines()]


def _walk(worker, np, sparse, value, path, field_name=None):
    output = io.BytesIO()
    emitter = worker.Emitter(output, np, sparse)
    emitter.walk(value, path, field_name)
    return emitter, output, _rows(output)


def _path_key(path):
    return json.dumps(path, sort_keys=True, separators=(",", ":"))


def _by_path(rows):
    result = {_path_key(row["path"]): row for row in rows}
    _check(len(result) == len(rows), "duplicate_emitted_path")
    return result


def _reject(call, types=(RuntimeError,), reason=None):
    try:
        call()
    except types as error:
        if reason is not None:
            _check(str(error) == reason, "wrong_rejection_reason")
        return type(error).__name__
    except Exception:
        raise ControlFailure("wrong_rejection_type") from None
    raise ControlFailure("negative_fixture_accepted")


def _mat(sio, values, compressed=False):
    output = io.BytesIO()
    sio.savemat(output, values, appendmat=False, format="5",
                do_compression=compressed, oned_as="row")
    data = output.getvalue()
    _check(128 <= len(data) <= FIXTURE_FILE_LIMIT, "synthetic_fixture_size")
    return data


def _load(worker, sio, data):
    return worker.read_all_variables(io.BytesIO(data), sio)


def _case_01(worker, np, sio, sparse, directory):
    """Hand-enumerated nested record paths; no walker-generated oracle."""
    records = np.empty((2, 2), dtype=[("signal", object), ("details", object)])
    coordinates = [(0, 0), (1, 0), (0, 1), (1, 1)]
    expected = {_path_key(["records"]): ("struct_array", [2, 2])}
    for ordinal, index in enumerate(coordinates):
        records[index]["signal"] = np.full((ordinal + 1, 2), ordinal,
                                          dtype=np.int16)
        detail = np.empty((1, 1), dtype=[("clock", object)])
        detail[0, 0]["clock"] = np.zeros((1, ordinal + 1), dtype=np.float64)
        records[index]["details"] = detail
        root = ["records", {"index": list(index)}]
        expected[_path_key(root + ["signal"])] = ("array", [ordinal + 1, 2])
        expected[_path_key(root + ["details"])] = ("struct_array", [1, 1])
        expected[_path_key(root + ["details", {"index": [0, 0]}, "clock"])] = (
            "array", [1, ordinal + 1])
    cells = np.empty((2, 3), dtype=object)
    cell_coordinates = [(0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2)]
    expected[_path_key(["cells"])] = ("cell_array", [2, 3])
    for ordinal, index in enumerate(cell_coordinates):
        cells[index] = np.zeros((ordinal, 1, 2), dtype=np.uint8)
        expected[_path_key(["cells", {"index": list(index)}])] = (
            "array", [ordinal, 1, 2])
    # Third top variable retains singleton axes; final cell is not a sample.
    singleton = np.zeros((1, 2, 1), dtype=np.float32)
    expected[_path_key(["tail"])] = ("array", [1, 2, 1])
    output = io.BytesIO()
    emitter = worker.Emitter(output, np, sparse)
    for name, value in [("records", records), ("cells", cells),
                        ("tail", singleton)]:
        emitter.walk(value, [name], name)
    observed = _by_path(_rows(output))
    _check(set(observed) == set(expected), "nested_complete_path_coverage")
    for path, (kind, shape) in expected.items():
        _check(observed[path]["kind"] == kind, "nested_container_kind")
        _check(observed[path]["shape"] == shape, "nested_dimensions")
    _check(observed[_path_key(["tail"])]["dtype"] == "float32",
           "singleton_dtype")
    _check(emitter.nodes == len(expected), "nested_node_accounting")
    return {"checks": 3, "source_path_occurrences": len(expected)}


def _case_02(worker, np, sio, sparse, directory):
    values = [
        ("empty03", np.empty((0, 3), dtype=np.float64), "array", [0, 3]),
        ("empty204", np.empty((2, 0, 4), dtype=np.int16), "array", [2, 0, 4]),
        ("empty00", np.empty((0, 0), dtype=np.uint8), "array", [0, 0]),
        ("emptycell", np.empty((0, 2), dtype=object), "cell_array", [0, 2]),
        ("emptystruct", np.empty((1, 0), dtype=[("field", object)]),
         "struct_array", [1, 0]),
        ("logical", np.array([[True, False]], dtype=np.bool_),
         "array", [1, 2]),
        ("complex", np.array([[1 + 2j, 3 - 4j]], dtype=np.complex128),
         "array", [1, 2]),
        ("nonfinite_signal", np.array([[np.nan, np.inf]], dtype=np.float64),
         "array", [1, 2]),
        ("text", np.array([["alpha", "\u03b2\n"]], dtype="U5"),
         "text_array", [1, 2]),
    ]
    for name, value, kind, shape in values:
        _, output, rows = _walk(worker, np, sparse, value, [name], name)
        _check(len(rows) == 1, "empty_leaf_unexpected_children")
        row = rows[0]
        _check(row["kind"] == kind and row["shape"] == shape,
               "empty_or_dtype_shape_loss")
        _check(row["dtype"] == str(value.dtype), "dtype_loss")
        if kind == "text_array":
            _check(row["text_values"] == ["alpha", "\u03b2\n"],
                   "private_text_loss")
            _check(row.get("custody") == "private metadata only",
                   "text_custody_missing")
        else:
            _check(row["values_disclosed"] is False, "numeric_value_disclosed")
            _check("text_values" not in row and "scalar_metadata" not in row,
                   "numeric_value_channel")
    return {"checks": len(values), "empty_records_preserved": True}


def _case_03(worker, np, sio, sparse, directory):
    payload = b"synthetic-runtime-or-source-pin:" + bytes(range(256)) * 8
    path = directory / "pin-fixture.bin"
    path.write_bytes(payload)
    expected = hashlib.sha256(payload).hexdigest()
    actual = worker.pin(path, len(payload), expected)
    _check(actual["sha256"] == expected and actual["bytes"] == len(payload),
           "valid_pin_not_complete")
    _reject(lambda: worker.pin(path, len(payload) + 1, expected),
            reason="file extent pin mismatch")
    changed = payload[:-1] + bytes([payload[-1] ^ 1])
    path.write_bytes(changed)
    _reject(lambda: worker.pin(path, len(payload), expected),
            reason="SHA256 pin mismatch")
    _reject(lambda: worker.digest_file(path, len(payload), len(payload) - 1),
            reason="file read budget exceeded")
    bounded = worker.BoundedFile(path, 3)
    try:
        _check(bounded.read(3) == changed[:3], "bounded_reader_wrong_bytes")
        _reject(lambda: bounded.read(1), reason="MAT reader byte budget")
        _check(bounded.used == 3, "bounded_reader_overread")
    finally:
        bounded.close()
    return {"checks": 5, "late_byte_pin_checked": True,
            "runtime_main_gate_exercised": False}


def _case_04(worker, np, sio, sparse, directory):
    first = _mat(sio, {"duplicate": np.zeros((2, 2), dtype=np.int16)})
    second = _mat(sio, {"duplicate": np.ones((2, 2), dtype=np.int16)})
    duplicate = first + second[128:]
    _reject(lambda: _load(worker, sio, duplicate),
            reason="duplicate/reserved top variable")
    prefix = _mat(sio, {"early": np.zeros((2, 3), dtype=np.float64)})
    late = _mat(sio, {"late": np.arange(256, dtype=np.int32).reshape(16, 16)},
                compressed=True)
    endian = "<" if late[126:128] == b"IM" else ">"
    _check(struct.unpack(endian + "I", late[128:132])[0] == 15,
           "compressed_fixture_tag")
    corrupt = late[:136] + b"\x00\x00" + late[138:]
    errors = (ValueError, OSError, EOFError, RuntimeError, zlib.error)
    _reject(lambda: _load(worker, sio, prefix + late[128:-7]), types=errors)
    _reject(lambda: _load(worker, sio, corrupt), types=errors)
    _reject(lambda: _load(worker, sio, b"not a MATLAB stream" * 8),
            types=errors)
    return {"checks": 4, "duplicate_and_late_corruption_refused": True}


def _case_05(worker, np, sio, sparse, directory):
    shared = np.array([[1, 2, 3]], dtype=np.int16)
    equal_but_distinct = shared.copy()
    cells = np.empty((1, 3), dtype=object)
    cells[0, 0], cells[0, 1], cells[0, 2] = (
        shared, equal_but_distinct, shared)
    _, _, rows = _walk(worker, np, sparse, cells, ["records"], "records")
    by_path = _by_path(rows)
    first = ["records", {"index": [0, 0]}]
    second = ["records", {"index": [0, 1]}]
    alias = ["records", {"index": [0, 2]}]
    _check(len(rows) == 4, "alias_path_coverage")
    _check(by_path[_path_key(first)]["kind"] == "array",
           "first_reference_missing")
    _check(by_path[_path_key(second)]["kind"] == "array",
           "equal_value_wrongly_deduplicated")
    alias_row = by_path[_path_key(alias)]
    _check(alias_row["kind"] == "memory_alias", "shared_reference_unreported")
    _check(alias_row["first_path"] == first, "alias_wrong_target")
    _check(alias_row["biological_identity_inferred"] is False,
           "alias_biological_inference")
    records = np.empty((1, 2), dtype=[("cellid", object), ("signal", object)])
    for index in [(0, 0), (0, 1)]:
        records[index]["cellid"] = np.array([[7]], dtype=np.int64)
        records[index]["signal"] = np.zeros((1, 2), dtype=np.float64)
    _, _, repeated = _walk(worker, np, sparse, records, ["units"], "units")
    id_rows = [r for r in repeated if r["path"][-1] == "cellid"]
    _check(len(id_rows) == 2, "repeated_biological_id_record_lost")
    _check(all(r["scalar_metadata"]["value_decimal"] == "7" for r in id_rows),
           "repeated_id_metadata_loss")
    _check(all("animalid" not in r and "biological_count" not in r
               for r in repeated), "missing_animal_identity_invented")
    return {"checks": 3, "alias_is_reference_not_biological_identity": True}


def _case_06(worker, np, sio, sparse, directory):
    output = io.BytesIO()
    emitter = worker.Emitter(output, np, sparse)
    disallowed = ["signal", "spikes", "velocity", "Animal-ID", "animal_id",
                  "AnimalId", " animalid ", "animalid_extra", "animalidfoo"]
    for name in disallowed:
        emitter.walk(np.array([[SIGNAL_SENTINEL]], dtype=np.int64),
                     [name], name)
    emitter.walk(np.array([[SIGNAL_SENTINEL, SIGNAL_SENTINEL]], dtype=np.int64),
                 ["animalid_array"], "animalid")
    emitter.walk(np.array([[9007199254740995]], dtype=np.int64),
                 ["animalid"], "animalid")
    emitter.walk(np.array([[125.5]], dtype=np.float64), ["fs"], "fs")
    rows = _by_path(_rows(output))
    _check(len(rows) == len(disallowed) + 3, "allowlist_path_omission")
    for name in disallowed + ["animalid_array"]:
        row = rows[_path_key([name])]
        _check(row["values_disclosed"] is False, "inexact_scalar_allowlist")
        _check("scalar_metadata" not in row, "disallowed_scalar_metadata")
    _check(rows[_path_key(["animalid"])]["scalar_metadata"]["value_decimal"]
           == "9007199254740995", "integer_scalar_precision_loss")
    _check(rows[_path_key(["fs"])]["scalar_metadata"]["value_decimal"]
           == "125.5", "clock_scalar_decimal")
    _check(str(SIGNAL_SENTINEL).encode("ascii") not in output.getvalue(),
           "signal_sentinel_in_census")
    return {"checks": len(disallowed) + 3, "exact_names_only": True}


def _case_07(worker, np, sio, sparse, directory):
    for class_name in ("MatlabObject", "MatlabFunction", "MatlabOpaque"):
        wrapper = type(class_name, (np.ndarray,), {})
        value = np.arange(3, dtype=np.int16).view(wrapper)
        _reject(lambda value=value: _walk(worker, np, sparse, value,
                                         ["unsupported"], "unsupported"),
                reason="unsupported MATLAB object/function/opaque class")
    _reject(lambda: _walk(worker, np, sparse, object(), ["unexpected"]),
            reason="unsupported decoded value type")
    # Walker-contract doubles, not purported valid MAT or NumPy dimensions.
    for dimension in (float("nan"), float("inf")):
        malformed = type("MalformedShape", (np.ndarray,), {
            "shape": property(lambda self, dimension=dimension: (dimension, 2))
        })
        value = np.arange(4, dtype=np.int16).view(malformed)
        _reject(lambda value=value: _walk(worker, np, sparse, value, ["bad"]),
                types=(RuntimeError, ValueError, OverflowError))
    return {"checks": 6, "boundary_doubles_are_not_authentic_mat": True}


def _case_08(worker, np, sio, sparse, directory):
    original = {name: getattr(worker, name) for name in
                ("MAX_NODES", "MAX_CENSUS_BYTES", "MAX_TEXT_BYTES")}
    output = io.BytesIO()
    with _limits(worker, MAX_CENSUS_BYTES=1):
        emitter = worker.Emitter(output, np, sparse)
        _reject(lambda: emitter.walk(np.zeros((1, 1)), ["late"]),
                reason="complete census output budget")
        _check(output.getvalue() == b"", "output_budget_wrote_oversize_row")
    text = np.array([["ab", "cd"]], dtype="U2")
    with _limits(worker, MAX_TEXT_BYTES=4):
        _, _, rows = _walk(worker, np, sparse, text, ["text"])
        _check(len(rows) == 1, "at_limit_text_not_complete")
    with _limits(worker, MAX_TEXT_BYTES=3):
        _reject(lambda: _walk(worker, np, sparse, text, ["text"]),
                reason="complete text metadata budget")
    cells = np.empty((1, 2), dtype=object)
    cells[0, 0] = np.zeros((1, 1), dtype=np.int16)
    cells[0, 1] = np.ones((1, 1), dtype=np.int16)
    with _limits(worker, MAX_NODES=3):
        _, _, rows = _walk(worker, np, sparse, cells, ["cells"])
        _check(len(rows) == 3, "at_limit_nodes_not_complete")
    partial = io.BytesIO()
    with _limits(worker, MAX_NODES=2):
        emitter = worker.Emitter(partial, np, sparse)
        _reject(lambda: emitter.walk(cells, ["cells"]),
                reason="complete tree depth/node budget")
        rows = _rows(partial)
        _check(len(rows) == 2, "late_node_failure_prefix_accounting")
        _check(not any(r.get("accepted_complete_census") or r.get("complete")
                       for r in rows), "partial_claimed_complete")
    _check(original == {name: getattr(worker, name) for name in original},
           "control_limits_not_restored")
    return {"checks": 5, "partial_prefix_is_not_success": True,
            "main_atomic_publication_exercised": False}


def _semantic_rows(rows):
    canonical = []
    for original in rows:
        row = dict(original)
        row.pop("node", None)
        if row["kind"] in ("struct_array", "struct_scalar"):
            row["fields"] = sorted(row["fields"])
            # Structured dtype string preserves field order. Field children
            # independently preserve each field's type/shape in this fixture.
            row.pop("dtype", None)
        canonical.append(row)
    return sorted(canonical, key=lambda row: _path_key(row["path"]))


def _case_09(worker, np, sio, sparse, directory):
    def values(field_order, variable_order):
        records = np.empty((1, 2), dtype=[(name, object)
                                         for name in field_order])
        for index, length in [((0, 0), 2), ((0, 1), 5)]:
            records[index]["signal"] = np.zeros((1, length), dtype=np.int16)
            records[index]["cellid"] = np.array([[7]], dtype=np.int64)
        available = {"records": records,
                     "tail": np.zeros((0, 3), dtype=np.float32)}
        return {name: available[name] for name in variable_order}
    packets = [
        _mat(sio, values(["signal", "cellid"], ["records", "tail"])),
        _mat(sio, values(["cellid", "signal"], ["tail", "records"]))
    ]
    inventories = []
    for packet in packets:
        top, names, loaded = _load(worker, sio, packet)
        _check(set(names) == {"records", "tail"} and len(top) == 2,
               "top_variable_coverage")
        output = io.BytesIO()
        emitter = worker.Emitter(output, np, sparse)
        for name in names:
            emitter.walk(loaded[name], [name], name)
        rows = _rows(output)
        _check(len(rows) == 6, "all_record_path_coverage")
        expected_paths = {
            _path_key(["records"]), _path_key(["tail"]),
            _path_key(["records", {"index": [0, 0]}, "signal"]),
            _path_key(["records", {"index": [0, 0]}, "cellid"]),
            _path_key(["records", {"index": [0, 1]}, "signal"]),
            _path_key(["records", {"index": [0, 1]}, "cellid"]),
        }
        _check(set(_by_path(rows)) == expected_paths, "late_case_missing")
        _check(not any("animalid" in r or "biological_count" in r for r in rows),
               "published_cohort_count_invented")
        inventories.append(_semantic_rows(rows))
    _check(inventories[0] == inventories[1], "ordering_changes_semantic_census")
    return {"checks": 3, "source_order_is_not_biological_identity": True}


def _ledger_summary(ledger):
    _check(len(ledger) == len(CONTROL_IDS), "ledger_case_count")
    ids = [entry.get("id") for entry in ledger]
    _check(len(ids) == len(set(ids)) and tuple(ids) == CONTROL_IDS,
           "ledger_missing_duplicate_or_reordered_case")
    statuses = [entry.get("status") for entry in ledger]
    _check(all(status in ("pass", "fail", "error") for status in statuses),
           "ledger_skip_or_unknown_status")
    _check(all(entry.get("completed") is True for entry in ledger),
           "ledger_incomplete_case")
    counts = {status: statuses.count(status) for status in ("pass", "fail", "error")}
    return {"selected": len(CONTROL_IDS), "executed": len(ledger),
            "pass": counts["pass"], "fail": counts["fail"], "error": counts["error"],
            "skip": 0, "expected_failure": 0, "unexpected_success": 0,
            "all_selected_controls_completed": True,
            "all_passed": counts["pass"] == len(CONTROL_IDS)}


def _case_10(worker, np, sio, sparse, directory):
    good = [{"id": item, "status": "pass", "completed": True}
            for item in CONTROL_IDS]
    _check(_ledger_summary(good)["all_passed"], "valid_ledger_refused")
    malformed = []
    malformed.append(good[:-1])
    duplicate = [dict(entry) for entry in good]
    duplicate[-1]["id"] = duplicate[0]["id"]
    malformed.append(duplicate)
    for state in ("skip", "expected_failure"):
        changed = [dict(entry) for entry in good]
        changed[3]["status"] = state
        malformed.append(changed)
    incomplete = [dict(entry) for entry in good]
    incomplete[-1]["completed"] = False
    malformed.append(incomplete)
    for ledger in malformed:
        _reject(lambda ledger=ledger: _ledger_summary(ledger),
                types=(ControlFailure,))
    failed = [dict(entry) for entry in good]
    failed[2]["status"] = "fail"
    summary = _ledger_summary(failed)
    _check(not summary["all_passed"] and summary["fail"] == 1,
           "failed_control_hidden")
    return {"checks": 7, "ledger_fixtures_are_not_real_results": True}


def run_controls(worker, np, sio, sparse):
    """Run only when an external owner explicitly selects this invocation.

    Return all ten case outcomes, including failures. No captured scientific
    values or arbitrary exception messages are returned. No case failure is
    converted to a skip. The caller must treat summary.all_passed == False as
    failure and retain the complete ledger. This function is not a host guard.
    """
    cases = (_case_01, _case_02, _case_03, _case_04, _case_05,
             _case_06, _case_07, _case_08, _case_09, _case_10)
    ledger = []
    with tempfile.TemporaryDirectory(prefix="vo-census-offline-controls-") as tmp:
        root = Path(tmp)
        for control_id, case in zip(CONTROL_IDS, cases):
            stdout, stderr = _Capture(), _Capture()
            entry = {"id": control_id, "status": "error", "completed": False}
            try:
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    details = case(worker, np, sio, sparse, root)
                _check(str(SIGNAL_SENTINEL) not in stdout.getvalue()
                       and str(SIGNAL_SENTINEL) not in stderr.getvalue(),
                       "signal_sentinel_in_diagnostics")
                # Unit APIs are expected to be silent; no captured prose is
                # published, even if it appears harmless.
                _check(not stdout.getvalue() and not stderr.getvalue(),
                       "unexpected_diagnostic_output")
                entry.update(status="pass", details=details)
            except ControlFailure as error:
                entry.update(status="fail", failure_code=error.code)
            except Exception as error:
                entry.update(status="error", exception_type=type(error).__name__)
            finally:
                entry["completed"] = True
                entry["stdout_characters"] = len(stdout.getvalue())
                entry["stderr_characters"] = len(stderr.getvalue())
            ledger.append(entry)
    summary = _ledger_summary(ledger)
    return {
        "schema": "vestibular-vo-offline-control-ledger-v1",
        "ledger": ledger,
        "summary": summary,
        "authentic_data_accessed": False,
        "biological_membership_verified": False,
        "benchmark_ready_claim": False,
        "scope": "Ten synthetic core API controls; no main/host/runtime wrapper.",
        "unexercised": [
            "Whole runtime/package inventory qualification and process limits",
            "Atomic publication and authentic-file stat invariance in main",
            "Complete authentic cohort, clocks, channel and pair hierarchy",
            "All prospective subcases outside these ten concrete API checks"
        ],
    }
