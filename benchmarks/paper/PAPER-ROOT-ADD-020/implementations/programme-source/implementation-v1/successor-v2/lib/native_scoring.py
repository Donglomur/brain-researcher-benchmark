"""Complete reproduction output custody and separate scientific/native fidelity.

Portable exports never qualify MATLAB parity. Qualified reference records must
come from a separately admitted producer, including its literal native capture.
"""
import dataclasses
import hashlib
import math
from .strict import need, digest
from .programme import ACTORS, CONFIGS, VARIANTS


def export_reproduction(result):
    """Lossless named-array view; keeps every intermediate, support mask and axis.

    Arrays are not serialized/copied by this function. Runtime must budget all
    of them and use a separately bounded operator-owned artifact transport.
    """
    import numpy as np
    from .reproduction import ReproductionResult
    need(isinstance(result, ReproductionResult), "reproduction", "Complete supplied-array result required")
    arrays, provenance = {}, {}
    def walk(value, path):
        if isinstance(value, np.ndarray):
            arrays[path] = value
            return {"array": path, "shape": list(value.shape), "dtype": value.dtype.str}
        if dataclasses.is_dataclass(value):
            answer = {}
            for field in dataclasses.fields(value):
                p = path+"/"+field.name
                part = getattr(value, field.name)
                if field.name in ("calculation_status", "literal_native_qualified"):
                    provenance[p] = part
                else:
                    answer[field.name] = walk(part, p)
            return answer
        if isinstance(value, (list, tuple)):
            return [walk(v, path+"/"+str(i)) for i, v in enumerate(value)]
        need(value is None or type(value) in (str, int, float, bool), "metadata", "Plain result metadata required")
        return value
    metadata = walk(result, "result")
    digest(metadata)
    return {"schema": "paper020_complete_reproduction_record_v1", "metadata": metadata,
            "arrays": arrays, "provenance": provenance}


def validate_record(record):
    import numpy as np
    need(type(record) is dict and set(record) == {"schema", "metadata", "arrays", "provenance"}
         and record["schema"] == "paper020_complete_reproduction_record_v1",
         "reproduction", "Complete named-array record required")
    digest(record["metadata"]); digest(record["provenance"])
    need(type(record["arrays"]) is dict and record["arrays"], "reproduction", "No omitted numerical outputs")
    declared = {}
    def inspect(value):
        if type(value) is dict:
            if set(value) == {"array", "shape", "dtype"}:
                need(value["array"] not in declared, "reproduction", "Duplicate array descriptor")
                declared[value["array"]] = value
            else:
                for v in value.values(): inspect(v)
        elif type(value) is list:
            for v in value: inspect(v)
    inspect(record["metadata"])
    need(set(declared) == set(record["arrays"]), "coverage", "Every declared intermediate is required")
    for name, a in record["arrays"].items():
        spec = declared[name]
        need(isinstance(a, np.ndarray) and a.dtype.kind in "fiubU" and not a.dtype.hasobject
             and list(a.shape) == spec["shape"] and a.dtype.str == spec["dtype"],
             "reproduction", "Exact declared array schema required")
    return record


def array_digest(array):
    import numpy as np
    a = np.ascontiguousarray(array)
    h = hashlib.sha256(digest({"dtype": a.dtype.str, "shape": list(a.shape)}).encode("ascii"))
    h.update(memoryview(a).cast("B"))
    return h.hexdigest()


def native_keys():
    return {(actor, case, mode, v[0]) for actor in ACTORS for case in CONFIGS
            for mode in ("static", "time_course") for v in VARIANTS}


def native_schema(record):
    """Response-value-free schema, supplied by the qualified operator in advance.

    Do not infer the expected schema from candidate output. The operator binds
    its independent header/index/caller-derived manifest before evaluation.
    """
    validate_record(record)
    def structural(value, path=""):
        if type(value) is dict:
            return {k: structural(v,path+"/"+k) for k,v in value.items()}
        if type(value) is list:
            return [structural(v,path+"/"+str(i)) for i,v in enumerate(value)]
        if "/states/" in path or "/column_states/" in path or path.endswith("/source_default_dimension_compatible"):
            return {"diagnostic_type":type(value).__name__}
        return value
    return {"metadata_digest":digest(structural(record["metadata"])),
            "arrays":{k:{"shape":list(a.shape),"dtype":a.dtype.str} for k,a in sorted(record["arrays"].items())}}


def native_schemas_digest(schemas):
    return digest([{"key":list(k),"schema":v} for k,v in sorted(schemas.items())])


def validate_native_bundle(bundle, expected_schemas):
    need(type(bundle) is dict and set(bundle) == native_keys(), "coverage", "All 336 reproduction records required")
    need(type(expected_schemas) is dict and set(expected_schemas) == native_keys(),
         "coverage", "Every native header-derived output schema must be independently fixed in advance")
    records = []
    for key in sorted(bundle):
        record = validate_record(bundle[key])
        need(native_schema(record) == expected_schemas[key], "coverage", "Native output differs from the complete pre-admitted schema")
        meta = record["metadata"]
        family, method = next((v[1], v[2]) for v in VARIANTS if v[0] == key[3])
        need(meta.get("configuration") == key[1] and meta.get("stimulus_set") == CONFIGS[key[1]][2]
             and meta.get("family") == family and meta.get("method") == method
             and meta.get("windows", {}).get("mode") == key[2], "identity", "Reproduction record/job mismatch")
        records.append({"key": list(key), "metadata": digest(meta),
                        "arrays": {p: array_digest(a) for p, a in sorted(record["arrays"].items())},
                        "provenance": digest(record["provenance"])})
    return digest(records)


def array_discrepancy(candidate, expected, *, strict_support=False):
    """Generic engineering reducer. Undefined states match; no masks are inferred."""
    import numpy as np
    need(candidate.shape == expected.shape and candidate.dtype == expected.dtype,
         "shape", "Identical full numerical/semantic shape and dtype required")
    if expected.dtype.kind in "biuU":
        return {"positions": int(expected.size), "defined": int(expected.size), "undefined": 0,
                "exact_equal": bool(np.array_equal(candidate, expected)), "mse": None, "maximum_absolute_error": None}
    need(expected.dtype.kind == "f", "dtype", "Float scientific arrays required")
    support = np.isfinite(expected)
    masks_equal = bool(np.array_equal(np.isnan(candidate), np.isnan(expected))
         and np.array_equal(np.isposinf(candidate), np.isposinf(expected))
         and np.array_equal(np.isneginf(candidate), np.isneginf(expected)))
    if strict_support:
        need(masks_equal, "mask", "Candidate cosine undefined states differ from the independently fixed support")
    n = int(support.sum())
    if n == 0 or not np.isfinite(candidate[support]).all():
        return {"positions": int(expected.size), "defined": n, "undefined": int(expected.size-n),
                "mask_equal": masks_equal, "mse": None, "maximum_absolute_error": None}
    with np.errstate(over="raise", invalid="raise"):
        error = candidate[support]-expected[support]
        square = error*error
    need(np.isfinite(square).all(), "arithmetic", "Nonfinite fidelity error")
    return {"positions": int(expected.size), "defined": n, "undefined": int(expected.size-n),
            "mask_equal": masks_equal, "mse": math.fsum(float(x) for x in square.flat)/n, "maximum_absolute_error": float(np.max(np.abs(error)))}


def record_discrepancy(candidate, expected):
    validate_record(candidate); validate_record(expected)
    semantic_differences = []
    def compare_metadata(a, b, path=""):
        if type(b) is dict:
            need(type(a) is dict and set(a) == set(b), "metadata", "Complete result metadata fields required")
            for k in b: compare_metadata(a[k], b[k], path+"/"+k)
        elif type(b) is list:
            need(type(a) is list and len(a) == len(b), "metadata", "Complete result metadata axes required")
            for i, (x,y) in enumerate(zip(a,b)): compare_metadata(x,y,path+"/"+str(i))
        elif a != b or type(a) is not type(b):
            if "/states/" in path or "/column_states/" in path or path.endswith("/source_default_dimension_compatible"):
                semantic_differences.append({"path":path,"candidate":a,"expected":b})
            else:
                need(False, "metadata", "Full row/window/operand/identity metadata differ: "+path)
    compare_metadata(candidate["metadata"], expected["metadata"])
    diagnostics = {p: array_discrepancy(candidate["arrays"][p], a) for p, a in expected["arrays"].items()}
    # Equal cell -> repetition -> condition -> window, with pre-established
    # source-defined support and explicit undefined counts. Missing entire
    # conditions/windows remain undefined; they are never replaced with zero.
    import numpy as np
    window_values = []
    conditions = expected["metadata"].get("conditions")
    need(type(conditions) is list and len(conditions) == 2, "coverage", "Both original conditions required")
    per_condition = []
    for ci, condition in enumerate(conditions):
        path = f"result/conditions/{ci}/cosines/values"
        a, b = candidate["arrays"][path], expected["arrays"][path]
        need(a.ndim == 3 and 0 not in a.shape, "shape", "Full window/repetition/cell axes required")
        mask_path = f"result/conditions/{ci}/cosines/defined"
        need(np.array_equal(candidate["arrays"][mask_path], expected["arrays"][mask_path])
             and np.array_equal(candidate["arrays"][mask_path], np.isfinite(a))
             and np.array_equal(expected["arrays"][mask_path], np.isfinite(b)),
             "mask", "Exact independently fixed cosine masks required")
        means = []
        for w in range(a.shape[0]):
            repetitions = []
            for rep in range(a.shape[1]):
                d = array_discrepancy(a[w, rep], b[w, rep], strict_support=True)
                if d["mse"] is not None: repetitions.append(d["mse"])
            means.append(None if not repetitions else math.fsum(repetitions)/len(repetitions))
        per_condition.append(means)
    need(len(per_condition[0]) == len(per_condition[1]), "shape", "Condition time support differs")
    for w in range(len(per_condition[0])):
        defined = [c[w] for c in per_condition if c[w] is not None]
        if defined: window_values.append(math.fsum(defined)/len(defined))
    need(window_values, "unscorable", "A required complete configuration has no defined cosine support")
    return {"cosine_mse": math.fsum(window_values)/len(window_values),
            "defined_windows": len(window_values), "total_windows": len(per_condition[0]),
            "all_intermediates": diagnostics, "tolerance_pass": None,
            "intermediate_semantic_differences": semantic_differences,
            "tolerance_status": "Requires separately qualified fixed tolerance; no scientific success inferred"}


def grade_native(bundle, independent_expected):
    """Called only after complete output validation and independent closure."""
    need(set(bundle) == native_keys(), "coverage", "All candidate/reference reproduction jobs required")
    keys = {(case, mode, v[0]) for case in CONFIGS for mode in ("static", "time_course") for v in VARIANTS}
    need(type(independent_expected) is dict and set(independent_expected) == keys,
         "coverage", "Independent qualified targets for every original variant required")
    result = {}
    for actor in ACTORS:
        detail = {(case, mode, variant): record_discrepancy(bundle[(actor, case, mode, variant)], expected)
                  for (case, mode, variant), expected in independent_expected.items()}
        scores = {}
        for mode in ("static", "time_course"):
            scores[mode] = -math.sqrt(math.fsum(detail[(c, mode, "published_geometry")]["cosine_mse"] for c in CONFIGS)/14)
        result[actor] = {"primary_negative_cosine_RMSE": scores["time_course"],
                         "static_companion_negative_cosine_RMSE": scores["static"],
                         "diagnostics": {"/".join(k): v for k, v in detail.items()}}
    return {"actors": result, "primary_contract": "benchmark_clarified_paired964_STA",
            "whole_paper_reproduction": False, "native_runtime_qualification_claim": False}
