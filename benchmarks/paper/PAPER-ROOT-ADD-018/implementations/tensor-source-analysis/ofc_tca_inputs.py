"""Portable, source-only makeTensor_TCA input transform; no MAT I/O or model fit.

Derived from ConstantinopleLab's MIT-licensed makeTensor_TCA.m at
b7b68ca8c107d8ce4a061e16da214307f175c3e5. See LICENSE.author and README.md.
Only invented inputs have exercised this module. Outputs are operator-side
intermediate tensors, not candidate inputs, reference answers, or qualification.
"""
import math

EVENTS = ("COFF", "SON", "SOFF", "Rew", "Opt")
BLOCKS = (3, 1, 2)
COHORT_SESSION_COUNTS = {"Expert": 191, "Naive": 96}


class Unsupported(ValueError):
    """A source domain/version issue; never permission to exclude a session."""


def need(condition, message):
    if not condition:
        raise Unsupported(message)


def number(value, *, nan=False):
    need(type(value) in (int, float), "primitive real number required")
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise Unsupported("number cannot be represented as binary64") from None
    need(math.isfinite(result) or (nan and math.isnan(result)), "nonfinite input")
    return result


def vector(value, label):
    need(type(value) in (list, tuple) and len(value) > 0, label + " must be nonempty vector")
    return [number(x) for x in value]


def identity(session):
    """Keep supplied animal/session/unit IDs; never derive animal from filename."""
    need(type(session) is dict, "session mapping required")
    for key in ("session_id", "animal_id", "cohort"):
        need(type(session.get(key)) is str and bool(session[key]), key + " required")
    need(session["cohort"] in COHORT_SESSION_COUNTS, "unknown cohort")
    units = session.get("SU")
    need(type(units) in (list, tuple), "SU unit sequence required")
    ids = []
    for unit in units:
        need(type(unit) is dict, "unit mapping required")
        value = unit.get("cluster_id")
        need(type(value) in (int, float) and math.isfinite(value) and value >= 0
             and value == int(value), "nonnegative integral cluster_id required")
        ids.append(value)
    need(len(set(ids)) == len(ids), "duplicate within-session cluster_id requires identity reconciliation")
    return {"session_id": session["session_id"], "animal_id": session["animal_id"],
            "cohort": session["cohort"], "cluster_ids": ids}


def round_milliseconds(value):
    """Three-decimal selection away from ties; native near-tie parity is unbound."""
    value = number(value)
    scaled = abs(value) * 1000.0
    need(math.isfinite(scaled), "axis overflow")
    fraction = scaled - math.floor(scaled)
    # MATLAB has a version-dependent roundoff-aware tie rule. Do not silently
    # emulate it with Python's ties-to-even, nor claim native bitwise parity.
    need(abs(fraction - 0.5) > 8 * math.ulp(max(1.0, scaled)),
         "axis near a rounding tie requires native version resolution")
    return math.copysign(math.floor(scaled + 0.5) / 1000.0, value)


def windows(axis):
    axis = vector(axis, "first-unit COFF axis")
    need(all(a < b for a, b in zip(axis, axis[1:])), "COFF axis must increase")
    rounded = [round_milliseconds(x) for x in axis]
    bounds = {}
    for endpoint in (-1.0, 1.0, 0.8):
        found = [i for i, x in enumerate(rounded) if x == endpoint]
        need(len(found) == 1, "source endpoint must have exactly one rounded COFF match")
        bounds[endpoint] = found[0]
    need(bounds[-1.0] < bounds[0.8] < bounds[1.0], "source windows must be ordered")
    result, offset = [], 0
    for event in EVENTS:
        right = bounds[0.8 if event in ("Rew", "Opt") else 1.0]
        indices = list(range(bounds[-1.0], right + 1))
        result.append({"event": event, "source_columns_one_based": [i + 1 for i in indices],
                       "times_s": [axis[i] for i in indices], "output_start": offset,
                       "output_stop": offset + len(indices)})
        offset += len(indices)
    return result


def normalize(matrix, n_trials, minimum_columns):
    need(type(matrix) in (list, tuple) and len(matrix) == n_trials,
         "hmat must retain all source trials")
    need(all(type(row) in (list, tuple) for row in matrix), "hmat must be two-dimensional")
    widths = {len(row) for row in matrix}
    need(len(widths) == 1 and next(iter(widths)) >= minimum_columns,
         "hmat rectangular shape/cropped columns")
    parsed = [[number(x, nan=True) for x in row] for row in matrix]
    observed = [x for row in parsed for x in row if not math.isnan(x)]
    if not observed:
        return [[math.nan] * len(row) for row in parsed], {"observed": 0, "degenerate": True}
    try:
        mean = math.fsum(observed) / len(observed)
        scale = math.sqrt(math.fsum((x - mean) ** 2 for x in observed) / max(1, len(observed) - 1))
    except (OverflowError, ValueError):
        raise Unsupported("normalization overflow requires native numerical resolution") from None
    need(math.isfinite(mean) and math.isfinite(scale), "nonfinite normalization")
    degenerate = scale == 0.0
    need(not degenerate or all(x == observed[0] for x in observed),
         "normalization underflow for nonconstant input requires native numerical resolution")
    # Constant/single-observation matrices yield 0/0 in source, not a repaired SD.
    normalized = [[math.nan if degenerate or math.isnan(x) else (x - mean) / scale
                   for x in row] for row in parsed]
    need(all(math.isfinite(x) or math.isnan(x) for row in normalized for x in row),
         "nonfinite normalized value")
    return normalized, {"observed": len(observed), "degenerate": degenerate}


def prepare_session(session):
    """Transform one decoded session or preserve its explicit unsupported status.

    Schema: session_id, animal_id, cohort, S:{Block,vios},
    SU:[{cluster_id,xvec:{COFF:[...]},hmat:{event:[[trial,time],...]}}].
    Other fields are untouched and ignored, as in the held author function.
    The supplied identities must be externally authenticated before real use.
    """
    ident = identity(session)
    report = {**ident, "status": "unsupported", "source_exclusion": None}
    try:
        source = session.get("S")
        need(type(source) is dict, "S mapping required")
        blocks = vector(source.get("Block"), "S.Block")
        need(all(x in (1.0, 2.0, 3.0) for x in blocks), "unmapped source block")
        transitions = sum(a != b for a, b in zip(blocks, blocks[1:]))
        report.update(n_trials=len(blocks), block_transitions=transitions)
        # Literal source gate: it does NOT prove all three blocks are present.
        if len(session["SU"]) < 5 or transitions < 4:
            report.update(status="excluded_by_source", source_exclusion={
                "fewer_than_five_units": len(session["SU"]) < 5,
                "fewer_than_four_transitions": transitions < 4})
            return {"report": report, "data": None, "layout": None, "tensor_info": []}
        violations = vector(source.get("vios"), "S.vios")
        need(len(violations) == len(blocks), "Block/vios trial join")
        need(all(x in (0.0, 1.0) for x in violations), "unmapped violation indicator")
        selected = [[i for i, (b, v) in enumerate(zip(blocks, violations)) if b == block and v == 0]
                    for block in BLOCKS]
        report["selected_source_rows_one_based"] = [[i + 1 for i in rows] for rows in selected]
        # Source mean(A,'omitnan') changes its dimension for a single selected
        # trial, yielding n_units x 1 for assignment to n_units x n_time. That
        # native assignment/version branch has not been qualified.
        need(all(len(rows) != 1 for rows in selected),
             "singleton selected trial: native default-dimension/assignment branch unresolved")
        first = session["SU"][0]
        need(type(first.get("xvec")) is dict and "COFF" in first["xvec"], "COFF source axis missing")
        layout = windows(first["xvec"]["COFF"])
        width = layout[-1]["output_stop"]
        data = [[[0.0 for _ in BLOCKS] for _ in range(width)] for _ in session["SU"]]
        report["event_block_gates"] = []
        for segment in layout:
            event = segment["event"]
            columns = [i - 1 for i in segment["source_columns_one_based"]]
            normalized, norm_audit = [], []
            for unit in session["SU"]:
                need(type(unit.get("hmat")) is dict and event in unit["hmat"], "missing source event: " + event)
                values, audit = normalize(unit["hmat"][event], len(blocks), max(columns) + 1)
                normalized.append(values)
                norm_audit.append(audit)
            for block_index, rows in enumerate(selected):
                averages = []
                for values in normalized:
                    mean_row = []
                    for column in columns:
                        observed = [values[i][column] for i in rows if not math.isnan(values[i][column])]
                        mean_row.append(math.fsum(observed) / len(observed) if observed else math.nan)
                    averages.append(mean_row)
                missing = sum(math.isnan(x) for row in averages for x in row)
                assigned = missing == 0  # Literal matrix-wide `if ~isnan(avg_resp)`.
                report["event_block_gates"].append({"event": event, "block": BLOCKS[block_index],
                    "assigned": assigned, "missing_mean_entries": missing,
                    "zero_initialized_retained": not assigned, "normalization": norm_audit})
                if assigned:
                    for unit_index, row in enumerate(averages):
                        for column_index, value in enumerate(row):
                            need(math.isfinite(value), "nonfinite event/block average")
                            data[unit_index][segment["output_start"] + column_index][block_index] = value
        report["status"] = "transformed"
        info = [{"session_id": ident["session_id"], "animal_id": ident["animal_id"],
                 "cohort": ident["cohort"], "cluster_id": c, "source_unit_one_based": i + 1}
                for i, c in enumerate(ident["cluster_ids"])]
        return {"report": report, "data": data, "layout": layout, "tensor_info": info}
    except (Unsupported, OverflowError) as exc:
        report["reason"] = str(exc)
        return {"report": report, "data": None, "layout": None, "tensor_info": []}


def prepare_cohort(sessions, *, cohort, expected_session_ids):
    """Preserve every source roster position; refuse tensor output on any gap.

    This checks against an externally supplied, source-ordered complete roster;
    it does not authenticate that roster or decode MAT. Expert and Naive never
    pool. The canonical source counts are 191 and 96 respectively. No animal
    identities are guessed and no session is dropped because it is unsupported.
    """
    need(cohort in COHORT_SESSION_COUNTS, "unknown cohort")
    need(type(expected_session_ids) in (list, tuple)
         and len(expected_session_ids) == COHORT_SESSION_COUNTS[cohort], "complete source cohort count required")
    need(all(type(x) is str and x for x in expected_session_ids)
         and len(set(expected_session_ids)) == len(expected_session_ids), "unique ordered session roster required")
    need(type(sessions) in (list, tuple), "explicit ordered session sequence required")
    identities = [identity(s) for s in sessions]
    need([x["session_id"] for x in identities] == list(expected_session_ids), "session coverage/order mismatch")
    need(all(x["cohort"] == cohort for x in identities), "cohort mixing refused")
    results = [prepare_session(s) for s in sessions]
    reports = [x["report"] for x in results]
    output = {"schema": "ofc_tca_input_component_v1", "cohort": cohort, "reports": reports,
              "all_source_session_ids": list(expected_session_ids), "data": None,
              "layout": None, "tensor_info": [], "status": "unsupported",
              "native_parity": False, "whole_task_complete": False}
    if any(x["status"] == "unsupported" for x in reports):
        output["reason"] = "At least one source session is unsupported; no partial tensor admitted."
        return output
    retained = [x for x in results if x["report"]["status"] == "transformed"]
    if not retained:
        output.update(status="no_source_eligible_sessions", reason="Original source gate excluded all sessions.")
        return output
    # Explicitly stronger than shape-only concatenation: differing time grids
    # need source resolution, not an implicit common time interpretation.
    if any(x["layout"] != retained[0]["layout"] for x in retained[1:]):
        output["reason"] = "Cross-session source time grids differ; no silent axis merge."
        return output
    output.update(status="transformed", layout=retained[0]["layout"],
                  data=[row for x in retained for row in x["data"]],
                  tensor_info=[row for x in retained for row in x["tensor_info"]])
    return output
