"""Protected two-bank result validation and exact finite-suite interpretation.

This module never trains or selects a candidate/reference. A trusted protected
host supplies committed outputs and independent bank responses. No reference
is dropped after inspecting its score, and partial reproduction is not averaged.
"""
from fractions import Fraction
from .protocol import require, fraction, rational, unique, digest, outcome
from .admission import scope_inventory
from .planner import REFERENCES


def _q(value):
    return None if value is None else fraction(value)


def _pair_map(result):
    pairs = result["pair_scores"]
    result_map = {(r["truth_id"], r["detected_id"]): r for r in pairs}
    require(len(result_map) == len(pairs), "duplicate-pair-score", "bank output")
    return result_map


def _validate_witness(result, pairs):
    witness = result["assignment"]
    require(len(witness) == result["recovered"], "assignment-count", "bank result")
    require(len({x[0] for x in witness}) == len(witness)
            and len({x[1] for x in witness}) == len(witness),
            "nonbijective-unit-witness", "bank result")
    for pair in witness:
        require(tuple(pair) in pairs and pairs[tuple(pair)]["recovery_edge"],
                "invalid-recovery-witness", str(pair))
    quality = unique(result["quality"], "unit_id")
    if result["good_assigned"] is not None:
        require(sum(quality[x[1]]["good"] is True for x in witness) == result["good_assigned"],
                "assignment-secondary-objective", "good assignments")


def compare_I_banks(case, response1, response2):
    """No shared edge construction: compare independently computed invariants."""
    require(response1["bank"] == "R1" and response2["bank"] == "R2", "bank-identity", "independent pair")
    require(response1["operation"] == response2["operation"] == "score_I", "profile-collapse", "I operation")
    if response1["status"] != "ok" or response2["status"] != "ok":
        return outcome("required-unscorable", result={"banks": [response1, response2]},
                       gaps=[{"id": "S10", "reason": "both complete bank outputs must be defined and qualified"}])
    a, b = response1["result"], response2["result"]
    require(a["case_id"] == b["case_id"] == case["id"], "case-mismatch", case["id"])
    require(a["profile"] == b["profile"] == "I_bijective_full", "profile-collapse", case["id"])
    for key in ("truth_count", "detected_count", "recovered", "good_assigned", "total_good",
                "duplicates", "unmatched_good"):
        require(a[key] == b[key], "bank-disagreement", key)
    require(a["truth_count"] == len(case["truth"])
            and a["detected_count"] == len(case["detected"]), "bank-support-loss", case["id"])
    require(0 <= a["recovered"] <= min(a["truth_count"], a["detected_count"]),
            "invalid-recovered-count", case["id"])
    truth_ids, detected_ids = {r["unit_id"] for r in case["truth"]}, {r["unit_id"] for r in case["detected"]}
    pa, pb = _pair_map(a), _pair_map(b)
    require(set(pa) == set(pb) == {(t, d) for t in truth_ids for d in detected_ids},
            "pair-support-loss", case["id"])
    for pair in pa:
        for key in ("match_count", "n", "m", "recovery_edge"):
            require(pa[pair][key] == pb[pair][key], "bank-disagreement", f"{pair}/{key}")
        for key in ("score", "precision", "recall", "FP", "FN"):
            require(_q(pa[pair][key]) == _q(pb[pair][key]), "bank-disagreement", f"{pair}/{key}")
        n, m, k = (pa[pair][x] for x in ("n", "m", "match_count"))
        require(0 <= k <= min(n, m), "invalid-event-match-count", str(pair))
        require(pa[pair]["recovery_edge"] == (n > 0 and m > 0 and 5 * k * (n + m) > 9 * n * m),
                "recovery-boundary", str(pair))
    incident = {d for (t, d), row in pa.items() if row["recovery_edge"]}
    require(a["duplicates"] == len(incident) - a["recovered"],
            "duplicate-objective-mismatch", case["id"])
    qa, qb = unique(a["quality"], "unit_id"), unique(b["quality"], "unit_id")
    require(set(qa) == set(qb) == detected_ids, "quality-support-loss", case["id"])
    for unit in qa:
        require(qa[unit]["good"] == qb[unit]["good"], "quality-classification-mismatch", unit)
        require(_q(qa[unit]["Q"]) == _q(qb[unit]["Q"]), "quality-Q-mismatch", unit)
        require(qa[unit]["histogram"] == qb[unit]["histogram"], "quality-CCG-mismatch", unit)
        ia, ib = qa[unit]["P_interval"], qb[unit]["P_interval"]
        if ia is None or ib is None:
            require(ia == ib, "quality-definedness-mismatch", unit)
        else:
            alo, ahi, blo, bhi = map(fraction, [ia[0], ia[1], ib[0], ib[1]])
            require(0 <= alo <= ahi <= 1 and 0 <= blo <= bhi <= 1,
                    "invalid-probability-interval", unit)
            require(max(alo, blo) <= min(ahi, bhi), "certified-interval-disjoint", unit)
            decision_a = qa[unit].get("P_lt_one_fifth", qa[unit].get("P_less_than_one_fifth"))
            decision_b = qb[unit].get("P_lt_one_fifth", qb[unit].get("P_less_than_one_fifth"))
            require(decision_a == decision_b,
                    "probability-classification-mismatch", unit)
            decision = decision_a
            require(decision is not None, "unresolved-probability-boundary", unit)
            require((ahi < Fraction(1, 5) and bhi < Fraction(1, 5)) if decision
                    else (alo >= Fraction(1, 5) and blo >= Fraction(1, 5)),
                    "uncertified-probability-decision", unit)
    require(a["total_good"] == sum(row["good"] is True for row in qa.values()),
            "good-count-mismatch", case["id"])
    _validate_witness(a, pa)
    _validate_witness(b, pb)
    # Distinct maximum-matching witnesses are expected. Both objective values
    # must agree; the witness arrays themselves need not be identical.
    ba, bb = unique(a["best_scores"], "truth_id"), unique(b["best_scores"], "truth_id")
    require(set(ba) == set(bb) == truth_ids, "best-score-support-loss", case["id"])
    for unit in ba:
        require(_q(ba[unit]["score"]) == _q(bb[unit]["score"])
                and ba[unit]["detected_id"] == bb[unit]["detected_id"],
                "best-score-mismatch", unit)
    if case["kind"] == "hybrid":
        require(a["unmatched_good"] is None, "hybrid-unlabelled-background-miscount", case["id"])
    else:
        require(a["unmatched_good"] == a["total_good"] - a["good_assigned"],
                "unmatched-good-mismatch", case["id"])
    return outcome("ok", {"case_id": case["id"], "kind": case["kind"],
                   "truth_count": a["truth_count"], "recovered": a["recovered"],
                   "duplicates": a["duplicates"], "unmatched_good": a["unmatched_good"],
                   "total_good": a["total_good"], "good_assigned": a["good_assigned"],
                   "bank_response_digests": [digest(response1), digest(response2)],
                   "full_bank_results_retained": True, "native_parity_proven": False})


def _aggregate(rows):
    grouped = {kind: [r for r in rows if r["kind"] == kind]
               for kind in ("hybrid", "synthetic", "biophysical")}
    require([len(grouped[k]) for k in grouped] == [3, 6, 2], "incomplete-suite", "3/6/2 core cases")
    def average(values):
        return sum(values, Fraction()) / len(values)
    for row in rows:
        require(type(row["truth_count"]) is int and row["truth_count"] > 0,
                "empty-truth-roster", row["case_id"])
    recoveries = {k: average([Fraction(r["recovered"], r["truth_count"]) for r in v])
                  for k, v in grouped.items()}
    duplicate = average([average([Fraction(r["duplicates"], r["truth_count"]) for r in v])
                         for v in grouped.values()])
    unmatched = average([average([Fraction(r["unmatched_good"], r["truth_count"])
                                  for r in grouped[k]]) for k in ("synthetic", "biophysical")])
    return {"h": recoveries["hybrid"], "d": recoveries["synthetic"],
            "b": recoveries["biophysical"], "r": average(list(recoveries.values())),
            "q": unmatched, "v": duplicate}


def improvement(candidate, reference, required_case_ids, gates):
    ca, re = unique(candidate, "case_id"), unique(reference, "case_id")
    require(set(ca) == set(re) == set(required_case_ids), "case-support-mismatch", "fixed full core suite")
    for name in ca:
        require(ca[name]["kind"] == re[name]["kind"] and ca[name]["truth_count"] == re[name]["truth_count"],
                "reference-support-mismatch", name)
    if not all(gates.values()):
        return outcome("required-unscorable", gaps=[{"id": k, "reason": "required scientific/resource gate not passed"}
                                                    for k, v in gates.items() if not v])
    require(set(gates) == {"source", "diagnostics", "output", "resources", "reference_competence",
                           "independent_native_parity", "isolation"}, "missing-decision-gate", "fixed gates")
    a, b = _aggregate(candidate), _aggregate(reference)
    deltas = {k: a[k] - b[k] for k in a}
    cases = {name: Fraction(ca[name]["recovered"], ca[name]["truth_count"])
             - Fraction(re[name]["recovered"], re[name]["truth_count"]) for name in ca}
    predicates = {"recovery_gain_at_least_0.02": deltas["r"] >= Fraction(1, 50),
                  "each_stratum_nondecreasing": all(deltas[k] >= 0 for k in ("h", "d", "b")),
                  "each_case_decrease_at_most_0.02": all(x >= -Fraction(1, 50) for x in cases.values()),
                  "unmatched_good_nonincreasing": deltas["q"] <= 0,
                  "aggregate_duplicates_nonincreasing": deltas["v"] <= 0}
    return outcome("ok", {"meaningful_fixed_suite_improvement": all(predicates.values()),
                           "predicates": predicates, "candidate": {k: rational(v) for k, v in a.items()},
                           "reference": {k: rational(v) for k, v in b.items()},
                           "deltas": {k: rational(v) for k, v in deltas.items()},
                           "per_case_recovery_deltas": {k: rational(v) for k, v in cases.items()},
                           "claim_scope": "descriptive comparison on historically public fixed suite",
                           "new_source_generalization": None, "SOTA_claim": None,
                           "extra_per_case_duplicate_guard": False})


def evaluate_fixed_references(candidate, reference_results, case_ids, gates_by_reference):
    require(set(reference_results) == set(REFERENCES), "reference-cherry-picking", "all four fixed methods")
    comparisons = {name: improvement(candidate, reference_results[name], case_ids, gates_by_reference[name])
                   for name in REFERENCES}
    full = all(x["status"] == "ok" for x in comparisons.values())
    primary = comparisons["Kilosort4"]
    return {"schema": "kilosort4_fixed_reference_interpretation_v1", "comparisons": comparisons,
            "primary_decision": None if primary["status"] != "ok" else primary["result"]["meaningful_fixed_suite_improvement"],
            "stronger_fixed_suite_decision": None if not full else all(
                x["result"]["meaningful_fixed_suite_improvement"] for x in comparisons.values()),
            "scientific_SOTA": None, "all_failures_and_costs_retained": True}


def reproduction(catalog, obligation_reports, profile):
    require(profile in {"R_source20", "R_paper40"}, "invalid-reproduction-profile", profile)
    reports = unique(obligation_reports, "obligation_id")
    required = scope_inventory(catalog)
    require(set(reports) <= required, "unknown-obligation", "reproduction")
    vector = []
    for key in sorted(required):
        row = reports.get(key)
        if row is None:
            vector.append({"obligation_id": key, "status": "required-unscorable", "reason": "missing complete output"})
            continue
        require(row["profile"] == profile, "reproduction-profile-mixed", key)
        require(row["status"] in {"pass", "fail", "required-unscorable"}, "invalid-obligation-status", key)
        if row["status"] in {"pass", "fail"}:
            require(row["constructor_pin"] and row["two_bank_receipt_pins"] and row["native_output_pin"]
                    and row["tolerance_contract_pin"] and row["source_lineage_receipt_pin"],
                    "unsupported-obligation-result", key)
        vector.append(row)
    undefined = any(x["status"] == "required-unscorable" for x in vector)
    return {"schema": "kilosort4_complete_reproduction_report_v1", "profile": profile,
            "coverage": vector, "whole_paper_reproduced": None if undefined else all(
                x["status"] == "pass" for x in vector),
            "partial_average_not_computed": True, "canonical_count": 1,
            "required_obligations": len(required)}
