"""Independent typed native-quantity comparison, not a prospective grader.

No numerical reference implementation is imported. Authentic units, axes,
reference values, source identity and tolerances must be separately admitted.
Mismatch and completeness remain separate, and neither is a score callback.
"""
import hashlib
import math

from native_adapter import NativeError, checked_pin, fields, positive, require


ADMISSION_KEYS = ("schema", "job_id", "quantity_id", "actual_variant", "reference_variant",
                  "actual_source_pin", "reference_source_pin", "actual_selector_pin", "reference_selector_pin",
                  "units", "units_evidence", "support_evidence", "reference_evidence", "tolerance_evidence", "policy")


def outcome(status, *, capture_complete=False, defined=False, agreement=None, detail=None):
    return {"schema": "n079_native_quantity_outcome_v1", "status": status,
            "capture_complete": capture_complete, "comparison_defined": defined,
            "numerical_agreement": agreement, "prospective_grading_blocked": False,
            "detail": {} if detail is None else detail,
            "boundary": "Native reproduction outcome only; missing required evidence remains incomplete. Independently valid prospective grading is not suppressed by numerical mismatch."}


def _evidence(record, side, admission):
    fields(record, ("schema", "job_id", "variant", "quantity", "capture_index_pin", "observer_evidence"), "quantity evidence")
    require(record["schema"] == "n079_native_quantity_evidence_v1", "schema", "quantity evidence schema")
    checked_pin(record["capture_index_pin"]);checked_pin(record["observer_evidence"])
    require(record["job_id"] == admission["job_id"] and record["variant"] == admission[side+"_variant"], "source_join_failure", "job or original/corrected variant differs")
    q = record["quantity"]
    require(type(q) is dict and q.get("id") == admission["quantity_id"], "missing_quantity", "required named native quantity absent")
    require(q.get("status") == "captured", "missing_quantity", "native producer did not capture the required quantity")
    require(q.get("source_pin") == admission[side+"_source_pin"] and q.get("selector_pin") == admission[side+"_selector_pin"], "source_join_failure", "actual source/selector does not join independent quantity admission")
    require(q.get("units") == admission["units"] and q.get("units_evidence") == admission["units_evidence"], "units_join_failure", "native units/evidence differ")
    require(q.get("support_evidence") == admission["support_evidence"], "support_join_failure", "ordered complete axis/support evidence differs")
    checked_pin(q["pin"])
    return q


def _admission(admission):
    fields(admission, ADMISSION_KEYS, "native comparison admission")
    require(admission["schema"] == "n079_native_quantity_comparison_v1", "schema", "comparison schema")
    for key in ("actual_source_pin", "reference_source_pin", "actual_selector_pin", "reference_selector_pin", "units_evidence", "support_evidence", "reference_evidence", "tolerance_evidence"):
        checked_pin(admission[key])
    require(all(type(admission[k]) is str and admission[k] for k in ("job_id", "quantity_id", "actual_variant", "reference_variant", "units")), "schema", "nonempty independently selected quantity identities and units required")
    policy = admission["policy"]
    fields(policy, ("rule", "atol", "rtol", "nonfinite", "dtype"), "native comparison policy")
    require(policy["rule"] in ("absolute_relative", "exact_values", "exact_bytes") and policy["nonfinite"] == "undefined" and policy["dtype"] in ("same", "allow_float_precision"), "policy", "explicit supported native quantity comparison policy required")
    if policy["rule"] == "absolute_relative":
        require(all(type(policy[k]) in (int, float) and math.isfinite(policy[k]) and policy[k] >= 0 for k in ("atol", "rtol")), "policy", "finite nonnegative independent tolerances required")
    else:
        require(policy["atol"] is None and policy["rtol"] is None, "policy", "exact policy must not smuggle numeric tolerances")


def _limits(limits):
    fields(limits, ("max_elements", "block_elements", "max_live_bytes"), "native comparator limits")
    for key, value in limits.items(): positive(value, key)
    require(limits["block_elements"] <= limits["max_elements"] and limits["max_live_bytes"] >= 12*8*limits["block_elements"], "extent", "conservative twelve-buffer owned comparator reservation required")


def _array(array, q, limits):
    import numpy as np
    require(isinstance(array, np.ndarray) and array.dtype.kind in "biuf" and array.dtype.itemsize in (1, 2, 4, 8), "array_schema", "numeric non-object native array required")
    require(array.dtype.kind != "f" or array.dtype.itemsize in (4, 8), "array_schema", "binary32/binary64 required for floating comparison")
    require(array.size > 0 and array.size <= limits["max_elements"], "extent", "complete native quantity array extent outside admission")
    require(list(array.shape) == q.get("shape") and array.dtype.newbyteorder("<").str == q.get("dtype") and q.get("encoding") == "numeric", "support_join_failure", "array shape/dtype/encoding differs from captured native descriptor")
    digest, count = hashlib.sha256(), 0
    iterator = np.nditer(array, flags=["external_loop", "buffered"], op_flags=["readonly"],
                         op_dtypes=[array.dtype.newbyteorder("<")], casting="equiv", order="C", buffersize=limits["block_elements"])
    with iterator:
        for block in iterator:
            for start in range(0, block.size, limits["block_elements"]):
                raw = block[start:start+limits["block_elements"]].tobytes(order="C")
                digest.update(raw);count += len(raw)
    require({"bytes": count, "sha256": digest.hexdigest()} == q["pin"], "payload_join_failure", "actual numeric bytes do not match independently observed artifact")


def compare_quantity(actual, reference, actual_record, reference_record, admission, *, limits):
    """Compare all native cells; no masking, epsilon, fabricated reference or tol."""
    if actual_record is None or actual is None: return outcome("missing_quantity")
    if reference_record is None or reference is None: return outcome("missing_reference", capture_complete=True)
    if admission is None: return outcome("missing_admission", capture_complete=True)
    try:
        import numpy as np
        _limits(limits);_admission(admission)
        aq, rq = _evidence(actual_record, "actual", admission), _evidence(reference_record, "reference", admission)
        _array(actual, aq, limits);_array(reference, rq, limits)
        require(actual.shape == reference.shape, "support_join_failure", "complete native and reference coordinate shapes differ")
        policy = admission["policy"]
        same = actual.dtype.newbyteorder("<") == reference.dtype.newbyteorder("<")
        require(same or (policy["dtype"] == "allow_float_precision" and actual.dtype.kind == reference.dtype.kind == "f"), "support_join_failure", "native/reference dtype policy failed")
        if policy["rule"] == "absolute_relative":
            require(actual.dtype.kind == reference.dtype.kind == "f", "policy", "approximate numeric tolerance is only defined for floating quantities")
        nonfinite_actual = nonfinite_reference = mismatch = overflow_difference = 0
        maximum_difference = 0.0
        dtype = np.dtype("float64") if policy["rule"] == "absolute_relative" else None
        kwargs = {"op_dtypes": [dtype, dtype], "casting": "safe"} if dtype is not None else {}
        iterator = np.nditer([actual, reference], flags=["external_loop", "buffered"],
                             op_flags=[["readonly"], ["readonly"]], order="C", buffersize=limits["block_elements"], **kwargs)
        def bounded_pairs():
            with iterator:
                for outer_left, outer_right in iterator:
                    for start in range(0, outer_left.size, limits["block_elements"]):
                        yield (outer_left[start:start+limits["block_elements"]],
                               outer_right[start:start+limits["block_elements"]])
        for left, right in bounded_pairs():
                good_left, good_right = np.isfinite(left), np.isfinite(right)
                nonfinite_actual += int(np.count_nonzero(~good_left))
                nonfinite_reference += int(np.count_nonzero(~good_right))
                if not bool(np.all(good_left & good_right)): continue
                if policy["rule"] == "absolute_relative":
                    with np.errstate(all="ignore"):
                        # Keep representable nearby differences before any
                        # range scaling; true overflowing differences mismatch.
                        difference = np.abs(left-right)
                        tolerance = float(policy["atol"])+float(policy["rtol"])*np.abs(right)
                    require(bool(np.all(np.isfinite(tolerance))), "tolerance_range_failure", "independently selected tolerance overflows on actual reference support")
                    finite = np.isfinite(difference)
                    overflow_difference += int(np.count_nonzero(~finite))
                    mismatch += int(np.count_nonzero(difference > tolerance))
                    if np.any(finite): maximum_difference = max(maximum_difference, float(np.max(difference[finite])))
                else:
                    mismatch += int(np.count_nonzero(left != right))
        if nonfinite_actual or nonfinite_reference:
            return outcome("undefined_nonfinite", capture_complete=True, detail={"actual_nonfinite_count": nonfinite_actual, "reference_nonfinite_count": nonfinite_reference, "coordinates": int(actual.size), "no_coordinates_dropped": True})
        agreement = aq["pin"] == rq["pin"] if policy["rule"] == "exact_bytes" else mismatch == 0
        return outcome("match" if agreement else "mismatch", capture_complete=True, defined=True, agreement=agreement,
                       detail={"coordinates": int(actual.size), "mismatched_values": mismatch,
                               "overflow_difference_count": overflow_difference,
                               "maximum_finite_absolute_difference": maximum_difference if policy["rule"] == "absolute_relative" else None,
                               "rule": policy["rule"], "tolerance_evidence": admission["tolerance_evidence"],
                               "byte_identity": aq["pin"] == rq["pin"], "no_coordinates_dropped": True})
    except (NativeError, KeyError, TypeError, ValueError, OverflowError) as exc:
        return outcome(getattr(exc, "code", "schema_failure"), detail={"type": type(exc).__name__, "message": str(exc)})


def compare_opaque(actual_bytes, reference_bytes, actual_record, reference_record, admission, *, max_bytes):
    """Selected JSON/plot/original file byte identity; no pickle or semantic guess."""
    if actual_record is None or actual_bytes is None: return outcome("missing_quantity")
    if reference_record is None or reference_bytes is None: return outcome("missing_reference", capture_complete=True)
    if admission is None: return outcome("missing_admission", capture_complete=True)
    try:
        positive(max_bytes, "opaque comparison cap");_admission(admission)
        require(admission["policy"]["rule"] == "exact_bytes", "policy", "opaque files have no invented numeric/visual tolerance")
        aq, rq = _evidence(actual_record, "actual", admission), _evidence(reference_record, "reference", admission)
        require(type(actual_bytes) is bytes and type(reference_bytes) is bytes and max(len(actual_bytes), len(reference_bytes)) <= max_bytes, "extent", "bounded actual raw opaque bytes required")
        for raw, record in ((actual_bytes, aq), (reference_bytes, rq)):
            require({"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} == record["pin"], "payload_join_failure", "opaque source bytes differ from observed artifact")
        same = actual_bytes == reference_bytes
        return outcome("match" if same else "mismatch", capture_complete=True, defined=True, agreement=same,
                       detail={"rule": "exact_bytes", "semantic_or_figure_parity_claim": False})
    except (NativeError, KeyError, TypeError, ValueError) as exc:
        return outcome(getattr(exc, "code", "schema_failure"), detail={"type": type(exc).__name__, "message": str(exc)})


def summarize_outcomes(expected_quantity_ids, outcomes):
    require(type(expected_quantity_ids) is list and len(set(expected_quantity_ids)) == len(expected_quantity_ids) and type(outcomes) is dict, "schema", "exact unique native quantity roster required")
    require(set(outcomes) == set(expected_quantity_ids), "incomplete_comparison", "every required quantity outcome must remain present")
    for value in outcomes.values():
        require(type(value) is dict and value.get("schema") == "n079_native_quantity_outcome_v1" and value.get("prospective_grading_blocked") is False, "schema", "typed independent native comparison outcome required")
    complete = all(v["capture_complete"] and v["comparison_defined"] for v in outcomes.values())
    return {"schema": "n079_native_comparison_summary_v1", "complete_required_comparison": complete,
            "numerical_mismatch_count": sum(v["numerical_agreement"] is False for v in outcomes.values()),
            "undefined_or_missing_count": sum(not v["comparison_defined"] for v in outcomes.values()),
            "outcomes": outcomes, "prospective_grading_blocked": False,
            "whole_paper_reproduction_claim": False}
