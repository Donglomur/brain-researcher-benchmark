"""Pure post-admission NEURAL-035 descriptive pairing; no I/O or scorer imports.

The trusted caller supplies the original deferred_grade.score result after
source/closure/target admission. Consistency checks here do not authenticate that
caller, selected biological identities, raw ranks, or the 99 surrogate draws.
"""
import copy
import math


ENVELOPE = {"candidate", "operator", "private_scoring_performed", "scientific_qualified"}
GRADE = {"schema", "primary_rank_mae", "baseline_rank_mae", "paired_context_A_minus_B",
         "surrogate_mean_minus_observed", "sessions", "mice", "required_sessions",
         "required_mice", "required_queryblocks", "no_undefined_unit_dropped",
         "scientific_success_threshold", "p_value_computed", "causal_claim",
         "source_selected_event_claim"}
SESSION = {"session_id", "mouse", "context", "queries", "rank_mae",
           "baseline_rank_mae", "surrogate_mean_minus_observed"}
QUERY = {"query_id", "rank_mae", "baseline_rank_mae", "active_cells", "flat_cells",
         "distinct_active_peak_times", "surrogate_mean_rank_mae",
         "surrogate_mean_minus_observed", "candidate_minus_baseline"}
MOUSE = {"mouse", "rank_mae", "baseline_rank_mae", "context_A_minus_B",
         "surrogate_mean_minus_observed"}
CONTEXTS = ("cxta", "cxtb")


def _need(condition, why):
    if not condition:
        raise ValueError(why)


def _keys(row, expected, why):
    _need(type(row) is dict and all(type(k) is str for k in row) and set(row) == expected, why)


def _identity(value):
    _need(type(value) is str and bool(value), "Nonempty scalar identity")
    return value


def _metric(value, lower=0.0, upper=1.0):
    _need(value is None or
          (type(value) in (int, float) and math.isfinite(value) and lower <= value <= upper),
          "Finite nonboolean metric or explicit null")
    return value


def _average(values):
    _need(bool(values), "Nonempty required reduction")
    return None if any(v is None for v in values) else math.fsum(values) / len(values)


def _difference(left, right):
    return None if left is None or right is None else left - right


def _same(actual, expected, why):
    # Metric domains/types are checked separately. No tolerance, rounding,
    # default zero, null-skipping or Boolean-as-number comparison is used.
    _need((actual is None and expected is None) or
          (actual is not None and expected is not None and actual == expected), why)


def _validate(grade):
    _keys(grade, GRADE, "Exact original grade schema")
    _need(type(grade["schema"]) is str and grade["schema"] == "neural035-grade-v1",
          "Original grade version")
    for name, count in (("required_sessions", 14), ("required_mice", 7),
                        ("required_queryblocks", 28)):
        _need(type(grade[name]) is int and grade[name] == count, "Exact full support count")
    _need(grade["no_undefined_unit_dropped"] is True
          and grade["scientific_success_threshold"] is None
          and grade["p_value_computed"] is False and grade["causal_claim"] is False
          and grade["source_selected_event_claim"] is False, "Original scientific limits")
    for key in ("primary_rank_mae", "baseline_rank_mae"):
        _metric(grade[key])
    for key in ("paired_context_A_minus_B", "surrogate_mean_minus_observed"):
        _metric(grade[key], -1.0)
    _need(type(grade["sessions"]) is list and len(grade["sessions"]) == 14,
          "All fourteen session records")
    sessions = {}
    queries = {}
    grouped = {}
    total_cells = 0
    for session in grade["sessions"]:
        _keys(session, SESSION, "Exact session record")
        sid = _identity(session["session_id"])
        mouse = _identity(session["mouse"])
        context = session["context"]
        _need(type(context) is str and context in CONTEXTS and sid not in sessions,
              "Unique session and exact context")
        sessions[sid] = session
        contexts = grouped.setdefault(mouse, {})
        _need(context not in contexts, "One session per mouse/context")
        contexts[context] = session
        _need(type(session["queries"]) is list and len(session["queries"]) == 2,
              "Both original query blocks")
        cells = None
        for query in session["queries"]:
            _keys(query, QUERY, "Exact query record")
            qid = _identity(query["query_id"])
            _need(qid not in queries, "Unique query across the full cohort")
            queries[qid] = query
            active, flat, distinct = (query[k] for k in
                                      ("active_cells", "flat_cells", "distinct_active_peak_times"))
            _need(all(type(v) is int and v >= 0 for v in (active, flat, distinct)),
                  "Nonnegative nonboolean support counts")
            _need(active + flat > 0 and
                  ((active == 0 and distinct == 0) or
                   (active > 0 and 1 <= distinct <= min(active, 300))),
                  "Possible active/flat/distinct support")
            if cells is None:
                cells = active + flat
            _need(active + flat == cells, "Same full session-local cells in both queries")
            for key in ("rank_mae", "baseline_rank_mae", "surrogate_mean_rank_mae"):
                _metric(query[key])
            for key in ("surrogate_mean_minus_observed", "candidate_minus_baseline"):
                _metric(query[key], -1.0)
            metrics = [query[k] for k in ("rank_mae", "baseline_rank_mae",
                       "surrogate_mean_rank_mae", "surrogate_mean_minus_observed",
                       "candidate_minus_baseline")]
            _need(all(v is None for v in metrics) if active < 2 else
                  all(v is not None for v in metrics), "Exact activity-based definedness")
            _same(query["surrogate_mean_minus_observed"],
                  _difference(query["surrogate_mean_rank_mae"], query["rank_mae"]),
                  "Original query surrogate contrast")
            _same(query["candidate_minus_baseline"],
                  _difference(query["rank_mae"], query["baseline_rank_mae"]),
                  "Original query baseline contrast")
        total_cells += cells
        for key in ("rank_mae", "baseline_rank_mae", "surrogate_mean_minus_observed"):
            _metric(session[key], -1.0 if key == "surrogate_mean_minus_observed" else 0.0)
            _same(session[key], _average([q[key] for q in session["queries"]]),
                  "Original two-query session reduction")
    _need(len(queries) == 28 and len(grouped) == 7 and total_cells == 1012,
          "Complete 28 queries, seven mice and 1012 session-local cells")
    _need(all(set(contexts) == set(CONTEXTS) for contexts in grouped.values()),
          "Both recall contexts for each required mouse")
    _need(type(grade["mice"]) is list and len(grade["mice"]) == 7,
          "All seven original mouse records")
    mice = {}
    for record, expected_mouse in zip(grade["mice"], sorted(grouped), strict=True):
        _keys(record, MOUSE, "Exact mouse record")
        _need(_identity(record["mouse"]) == expected_mouse, "Original sorted unique mouse identities")
        mice[expected_mouse] = record
        contexts = grouped[expected_mouse]
        for key in ("rank_mae", "baseline_rank_mae", "surrogate_mean_minus_observed"):
            _metric(record[key], -1.0 if key == "surrogate_mean_minus_observed" else 0.0)
            _same(record[key], _average([contexts[c][key] for c in CONTEXTS]),
                  "Original two-context mouse reduction")
        _metric(record["context_A_minus_B"], -1.0)
        _same(record["context_A_minus_B"],
              _difference(contexts["cxta"]["rank_mae"], contexts["cxtb"]["rank_mae"]),
              "Original mouse context contrast")
    for outer, inner in (("primary_rank_mae", "rank_mae"),
                         ("baseline_rank_mae", "baseline_rank_mae"),
                         ("paired_context_A_minus_B", "context_A_minus_B"),
                         ("surrogate_mean_minus_observed", "surrogate_mean_minus_observed")):
        _same(grade[outer], _average([m[inner] for m in grade["mice"]]),
              "Original equal-seven-mouse reduction")
    return sessions, queries, mice


def _paired_values(candidate, operator):
    return {"candidate_rank_mae": candidate["rank_mae"],
            "operator_rank_mae": operator["rank_mae"],
            "operator_minus_candidate": _difference(operator["rank_mae"], candidate["rank_mae"]),
            "candidate_surrogate_mean_minus_observed": candidate["surrogate_mean_minus_observed"],
            "operator_surrogate_mean_minus_observed": operator["surrogate_mean_minus_observed"]}


def summarize(result):
    """Validate two original grades and return detached originals plus description.

    Positive gain means lower candidate rank error. Direct differences of the
    original aggregates and hierarchy-reduced query differences are both exposed
    and never asserted numerically identical. No raw metric is recomputed here.
    """
    _keys(result, ENVELOPE, "Exact original deferred paired-score envelope")
    _need(result["private_scoring_performed"] is True and result["scientific_qualified"] is False,
          "Original operation performed, scientific qualification still false")
    candidate, operator = result["candidate"], result["operator"]
    cs, cq, cm = _validate(candidate)
    os, oq, om = _validate(operator)
    _need(list(cs) == list(os) and list(cq) == list(oq) and list(cm) == list(om),
          "Same complete ordered session/query/mouse identities")
    rows = []
    grouped = {}
    for sid, c in cs.items():
        o = os[sid]
        _need((c["mouse"], c["context"]) == (o["mouse"], o["context"]),
              "Same mouse/context pairing across roles")
        records = []
        for cquery, oquery in zip(c["queries"], o["queries"], strict=True):
            _need(cquery["query_id"] == oquery["query_id"], "Same session-local query placement")
            for key in ("active_cells", "flat_cells", "distinct_active_peak_times"):
                _need(cquery[key] == oquery[key], "Exact shared activity/flat/tie support")
            _same(cquery["baseline_rank_mae"], oquery["baseline_rank_mae"],
                  "Same original analytic baseline at each query")
            _same(oquery["rank_mae"], oquery["baseline_rank_mae"],
                  "Fixed operator equals original baseline at each query")
            active, distinct = cquery["active_cells"], cquery["distinct_active_peak_times"]
            status = ("undefined_fewer_than_two_active" if active < 2 else
                      "defined_all_active_peaks_tied" if distinct == 1 else
                      "defined_distinct_active_peaks")
            records.append({"query_id": cquery["query_id"], **_paired_values(cquery, oquery),
                            "active_cells": active, "flat_cells": cquery["flat_cells"],
                            "distinct_active_peak_times": distinct, "derived_status": status,
                            "baseline_rank_mae": cquery["baseline_rank_mae"]})
        row = {"session_id": sid, "mouse": c["mouse"], "context": c["context"],
               **_paired_values(c, o), "queries": records,
               "hierarchical_query_gain_mean": _average([q["operator_minus_candidate"] for q in records])}
        rows.append(row)
        grouped.setdefault(c["mouse"], {})[c["context"]] = row
    mouse_rows = []
    for mouse in sorted(grouped):
        c, o = cm[mouse], om[mouse]
        contexts = grouped[mouse]
        mouse_rows.append({"mouse": mouse, **_paired_values(c, o),
            "hierarchical_query_gain_mean": _average([contexts[k]["hierarchical_query_gain_mean"]
                                                     for k in CONTEXTS]),
            "candidate_context_A_minus_B": c["context_A_minus_B"],
            "operator_context_A_minus_B": o["context_A_minus_B"],
            "operator_minus_candidate_context_contrast": _difference(o["context_A_minus_B"],
                                                                      c["context_A_minus_B"])})
    direct = _difference(operator["primary_rank_mae"], candidate["primary_rank_mae"])
    paired = _average([m["hierarchical_query_gain_mean"] for m in mouse_rows])
    summary = {"candidate_primary_rank_mae": candidate["primary_rank_mae"],
               "operator_primary_rank_mae": operator["primary_rank_mae"],
               "operator_minus_candidate": direct, "hierarchical_query_gain_mean": paired,
               "hierarchical_minus_direct_gain": _difference(paired, direct),
               "candidate_paired_context_A_minus_B": candidate["paired_context_A_minus_B"],
               "operator_paired_context_A_minus_B": operator["paired_context_A_minus_B"],
               "operator_minus_candidate_context_contrast":
                   _difference(operator["paired_context_A_minus_B"], candidate["paired_context_A_minus_B"]),
               "candidate_surrogate_mean_minus_observed": candidate["surrogate_mean_minus_observed"],
               "operator_surrogate_mean_minus_observed": operator["surrogate_mean_minus_observed"],
               "sessions": rows, "mice": mouse_rows}
    return {"schema": "neural035-paired-descriptive-report-v1",
            "original_result": copy.deepcopy(result), "paired": summary,
            "support": {"sessions": 14, "mice": 7, "queryblocks_per_role": 28,
                        "session_local_cells": 1012},
            "gain_direction": "operator_minus_candidate; positive means lower candidate rank error",
            "reduction": "query differences, two queries per session, two contexts per mouse, seven mice equally",
            "limits": {"post_admission_consistency_only": True,
                       "identities_or_producer_authenticated_here": False,
                       "raw_ranks_or_99_surrogates_recomputed_here": False,
                       "original_primary_replaced": False, "undefined_units_dropped": False,
                       "uncertainty_computed": False, "p_value_computed": False,
                       "causal_claim": False, "source_selected_event_claim": False,
                       "scientific_qualified": False, "registration_delta": 0,
                       "qualification_delta": 0}}

