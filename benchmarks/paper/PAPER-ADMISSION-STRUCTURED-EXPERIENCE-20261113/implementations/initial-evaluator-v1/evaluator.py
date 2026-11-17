"""Owner-only scoring and fold preparation for the structured-experience contract.

This module neither authenticates source recordings nor executes candidate code.
Its private expected universe must never be supplied to a prediction actor.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import hmac
import itertools
import json
import math
import os
from pathlib import Path
import re
import secrets
from statistics import fmean

TASK_ID = "PAPER-ADMISSION-STRUCTURED-EXPERIENCE-20261113"
CONTRACT_SHA256 = "dfe88f71ca905acdec513203ed249480b3b2224f66fb9d4bfd71a4a2a8398aea"
CONTEXTS = ("LS", "SL", "SS")
SESSIONS = {
    "SL_only_shaping": (
        "M2_2202025_g0", "M2_2212025_g0", "M1_2182025_g0", "M1_2202025_g0",
        "M4_2252025_g0", "M4_2272025_g1", "M5_2272025_g0", "M5_3012025_g0",
    ),
    "standard_shaping": (
        "AC01_01292025_g0", "j2_05092024_g0", "AB02_08272024_g0",
        "AB02_08282024_g0", "AB04_09092024_g0",
    ),
}
PROVENANCE_FIELDS = (
    "behavior_sha256", "unit_roster_sha256", "trial_order_sha256",
    "animal_mapping_sha256", "inclusion_policy_sha256",
)
OPEN_GATES = (
    "complete_authentic_inputs", "trial_unit_authority", "all_unit_zero_event_trials",
    "code_view_rights_revision", "paper_only_identifiability", "native_reference_and_baseline",
    "production_owner_and_leakage", "scorer_uncertainty_and_tolerances", "empirical_evaluation",
)


class AdmissionError(ValueError):
    """The supplied owner artifacts violate the finite evaluation contract."""


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha256(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _identifier(value, name):
    if not isinstance(value, str) or not value or value.strip() != value:
        raise AdmissionError(f"{name} must be a nonempty, unpadded string")
    return value


def _digest(value, name):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise AdmissionError(f"{name} must be a lowercase SHA256")
    return value


def _bin(value):
    if type(value) is not int or not 0 <= value < 40:
        raise AdmissionError("bins must be integer classes 0 through 39 (booleans forbidden)")
    return value


def circular_squared_seconds(predicted_bin, true_bin):
    delta = abs(_bin(predicted_bin) - _bin(true_bin))
    return (0.5 * min(delta, 40 - delta)) ** 2


def ordered_folds(trials):
    """Ten contiguous, source-order trial folds, exactly np.array_split semantics."""
    quotient, remainder = divmod(len(trials), 10)
    if quotient == 0:
        raise AdmissionError("ten nonempty query folds are required")
    result, start = [], 0
    for fold in range(10):
        stop = start + quotient + (fold < remainder)
        result.append(trials[start:stop])
        start = stop
    return result


def _validate_shared_roster(roster):
    """Validate owner attestations structurally; hashes are not authentication proof."""
    if not isinstance(roster, dict) or roster.get("schema") != "structured_experience_owner_roster_v1":
        raise AdmissionError("unsupported owner roster schema")
    provenance = roster.get("provenance", {})
    for field in PROVENANCE_FIELDS:
        _digest(provenance.get(field), field)
    if roster.get("evidence_kind") not in ("generated_engineering_control", "owner_authenticated_source"):
        raise AdmissionError("declare the roster evidence kind explicitly")
    sessions = roster.get("sessions")
    if not isinstance(sessions, list) or len(sessions) != 13:
        raise AdmissionError("exactly thirteen sessions are required")
    seen, mice, mouse_groups = set(), defaultdict(list), {}
    for session in sessions:
        sid = _identifier(session.get("session_id"), "session_id")
        group = session.get("shaping_group")
        if group not in SESSIONS or sid not in SESSIONS[group] or sid in seen:
            raise AdmissionError("unknown, duplicate, or wrongly stratified source session")
        seen.add(sid)
        mouse = _identifier(session.get("mouse_id"), "mouse_id")
        if mouse in mouse_groups and mouse_groups[mouse] != group:
            raise AdmissionError("a mouse cannot belong to both shaping groups")
        mouse_groups[mouse] = group
        mice[mouse].append(sid)
        trials = session.get("trials")
        if not isinstance(trials, list):
            raise AdmissionError("ordered trials must be a list")
        trial_ids = set()
        for trial in trials:
            tid = _identifier(trial.get("trial_id"), "trial_id")
            if tid in trial_ids or trial.get("context") not in CONTEXTS:
                raise AdmissionError("duplicate trial or unsupported context")
            trial_ids.add(tid)
            if trial.get("has_any_retained_event") is not True:
                raise AdmissionError("all-unit-zero-event or unresolved-support trials hard-refuse")
        if {t["context"] for t in trials} != set(CONTEXTS):
            raise AdmissionError("every session requires all three contexts")
    if seen != {s for group in SESSIONS.values() for s in group}:
        raise AdmissionError("incomplete source session universe")
    for group, multiplicities in (("SL_only_shaping", [2, 2, 2, 2]), ("standard_shaping", [1, 1, 1, 2])):
        observed = sorted(len(mice[m]) for m in mice if mouse_groups[m] == group)
        if observed != multiplicities:
            raise AdmissionError("authenticated eight-mouse join/multiplicities required; never infer by prefix")
    return roster


def validate_roster(roster):
    """Shared cohort/support checks plus the explicit prospective split policy."""
    _validate_shared_roster(roster)
    if roster.get("method_route") != "prospective_pointwise_0p5s":
        raise AdmissionError("only explicit 0.5-second prospective decoding is implemented; paper-only 1s/0.5s ambiguity remains open")
    for session in roster["sessions"]:
        trials = session["trials"]
        for query in ordered_folds(trials):
            if {t["context"] for t in query} != set(CONTEXTS):
                raise AdmissionError("every query fold requires all three test contexts")
            query_ids = {t["trial_id"] for t in query}
            calibration = [t for t in trials if t["trial_id"] not in query_ids]
            if {t["context"] for t in calibration} != set(CONTEXTS):
                raise AdmissionError("every calibration fold requires all source contexts")
    return roster


def _unit_descriptions(roster):
    mice = sorted({s["mouse_id"] for s in roster["sessions"]})
    for session in roster["sessions"]:
        for fold, query in enumerate(ordered_folds(session["trials"])):
            query_ids = {t["trial_id"] for t in query}
            for source in CONTEXTS:
                yield {
                    "session_id": session["session_id"], "held_mouse_id": session["mouse_id"],
                    "fold": fold, "source_context": source,
                    "development_mouse_ids": [m for m in mice if m != session["mouse_id"]],
                    "calibration_trial_ids": [t["trial_id"] for t in session["trials"]
                                              if t["trial_id"] not in query_ids and t["context"] == source],
                    "query_trial_ids": [t["trial_id"] for t in query],
                }


def _row_descriptions(roster):
    for session in roster["sessions"]:
        for fold, query in enumerate(ordered_folds(session["trials"])):
            for source in CONTEXTS:
                for trial in query:
                    for true_bin in range(40):
                        yield {
                            "session_id": session["session_id"], "mouse_id": session["mouse_id"],
                            "shaping_group": session["shaping_group"], "fold": fold,
                            "source_context": source, "test_context": trial["context"],
                            "trial_id": trial["trial_id"], "true_bin": true_bin,
                        }


def build_expected(roster, secret, policy_sha256, development_assets_sha256):
    """Prepare an OWNER-ONLY universe before predictions; no candidate input export."""
    validate_roster(roster)
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise AdmissionError("opaque IDs require at least 32 bytes of owner secret")
    _digest(policy_sha256, "policy_sha256")
    mice = {s["mouse_id"] for s in roster["sessions"]}
    if set(development_assets_sha256) != mice:
        raise AdmissionError("one pre-calibration development asset hash per outer mouse required")
    for digest in development_assets_sha256.values():
        _digest(digest, "development_assets_sha256")
    def opaque(domain, value):
        return hmac.new(secret, domain.encode() + b"\0" + canonical_bytes(value), hashlib.sha256).hexdigest()
    units, unit_ids = [], {}
    for unit in _unit_descriptions(roster):
        uid = opaque("unit", unit)
        unit_ids[(unit["session_id"], unit["fold"], unit["source_context"])] = uid
        units.append(dict(unit, fit_unit_id=uid))
    rows = []
    for row in _row_descriptions(roster):
        uid = unit_ids[(row["session_id"], row["fold"], row["source_context"])]
        rows.append(dict(row, fit_unit_id=uid, query_id=opaque("query", row)))
    result = {
        "schema": "structured_experience_private_expected_v1", "owner_only": True,
        "task_id": TASK_ID, "contract_sha256": CONTRACT_SHA256,
        "roster": json.loads(canonical_bytes(roster)), "roster_sha256": sha256(roster),
        "policy_sha256": policy_sha256, "development_assets_sha256": dict(development_assets_sha256),
        "fit_units": units, "rows": rows,
        "runnable_benchmark": False, "scientifically_qualified": False,
        "open_gates": list(OPEN_GATES),
    }
    result["expected_sha256"] = sha256(result)
    return result


def validate_expected(expected):
    if (not isinstance(expected, dict) or expected.get("schema") != "structured_experience_private_expected_v1"
            or expected.get("owner_only") is not True or expected.get("task_id") != TASK_ID
            or expected.get("contract_sha256") != CONTRACT_SHA256):
        raise AdmissionError("unsupported or non-owner expected universe")
    content = {k: v for k, v in expected.items() if k != "expected_sha256"}
    if sha256(content) != expected.get("expected_sha256"):
        raise AdmissionError("expected-universe digest mismatch")
    if (expected.get("runnable_benchmark") is not False or expected.get("scientifically_qualified") is not False
            or expected.get("open_gates") != list(OPEN_GATES)):
        raise AdmissionError("construction artifacts cannot promote admission or qualification gates")
    roster = validate_roster(expected["roster"])
    if sha256(roster) != expected.get("roster_sha256"):
        raise AdmissionError("roster digest mismatch")
    _digest(expected.get("policy_sha256"), "policy_sha256")
    mice = {s["mouse_id"] for s in roster["sessions"]}
    assets = expected.get("development_assets_sha256", {})
    if set(assets) != mice:
        raise AdmissionError("incomplete outer-case asset freezes")
    for value in assets.values():
        _digest(value, "development asset hash")
    descriptions = list(_unit_descriptions(roster))
    units = expected.get("fit_units", [])
    if len(units) != len(descriptions):
        raise AdmissionError("incomplete fit unit plan")
    unit_ids, all_ids = {}, set()
    for unit, description in zip(units, descriptions):
        uid = _digest(unit.get("fit_unit_id"), "fit_unit_id")
        if {k: v for k, v in unit.items() if k != "fit_unit_id"} != description or uid in all_ids:
            raise AdmissionError("altered, duplicate, or leaking fit-unit plan")
        all_ids.add(uid)
        unit_ids[(unit["session_id"], unit["fold"], unit["source_context"])] = uid
    reference = {tuple(row.values()): row for row in _row_descriptions(roster)}
    rows = expected.get("rows", [])
    if len(rows) != len(reference):
        raise AdmissionError("expected rows must include every source/trial/bin exactly once")
    field_order = ("session_id", "mouse_id", "shaping_group", "fold", "source_context", "test_context", "trial_id", "true_bin")
    for row in rows:
        _bin(row.get("true_bin"))
        if type(row.get("fold")) is not int:
            raise AdmissionError("fold must be an integer")
        key = tuple(row.get(k) for k in field_order)
        if key not in reference:
            raise AdmissionError("missing, duplicate, or foreign expected target")
        reference.pop(key)
        qid = _digest(row.get("query_id"), "query_id")
        if qid in all_ids:
            raise AdmissionError("opaque identifiers must be globally unique")
        all_ids.add(qid)
        if row.get("fit_unit_id") != unit_ids[(row["session_id"], row["fold"], row["source_context"])]:
            raise AdmissionError("query assigned to the wrong isolated fit unit")
    return expected


def _prediction_map(expected, predictions):
    if not isinstance(predictions, list):
        raise AdmissionError("predictions must be a list of exact ID/class records")
    values = {}
    for row in predictions:
        if not isinstance(row, dict) or set(row) != {"query_id", "predicted_bin"}:
            raise AdmissionError("prediction records permit only query_id and predicted_bin")
        qid = _digest(row["query_id"], "query_id")
        if qid in values:
            raise AdmissionError("duplicate prediction ID")
        values[qid] = _bin(row["predicted_bin"])
    if set(values) != {row["query_id"] for row in expected["rows"]}:
        raise AdmissionError("prediction IDs do not exactly cover the private expected universe")
    return values


def score_predictions(expected, predictions):
    validate_expected(expected)
    values = _prediction_map(expected, predictions)
    trials = defaultdict(list)
    for row in expected["rows"]:
        key = (row["session_id"], row["source_context"], row["test_context"], row["trial_id"])
        trials[key].append(circular_squared_seconds(values[row["query_id"]], row["true_bin"]))
    pairs = defaultdict(list)
    for (sid, source, test, trial), losses in trials.items():
        if len(losses) != 40:
            raise AdmissionError("incomplete trial-bin universe")
        pairs[(sid, source, test)].append(fmean(losses))
    sessions, mice = [], defaultdict(list)
    for session in expected["roster"]["sessions"]:
        sid = session["session_id"]
        matrix = {source: {test: fmean(pairs[(sid, source, test)]) for test in CONTEXTS} for source in CONTEXTS}
        within = {context: matrix[context][context] for context in CONTEXTS}
        across = fmean(matrix[s][t] for s in CONTEXTS for t in CONTEXTS if s != t)
        item = {"session_id": sid, "mouse_id": session["mouse_id"], "shaping_group": session["shaping_group"],
                "context_pair_mse_seconds2": matrix, "within_context_mse_seconds2": within,
                "within_mse_seconds2": fmean(within.values()), "across_mse_seconds2": across}
        item["signed_across_minus_within_seconds2"] = across - item["within_mse_seconds2"]
        item["absolute_gap_seconds2"] = abs(item["signed_across_minus_within_seconds2"])
        sessions.append(item)
        mice[session["mouse_id"]].append(item)
    mouse_rows = []
    for mouse, records in sorted(mice.items()):
        mouse_rows.append({"mouse_id": mouse, "shaping_group": records[0]["shaping_group"],
                           "session_count": len(records),
                           "across_mse_seconds2": fmean(s["across_mse_seconds2"] for s in records),
                           "within_context_mse_seconds2": {c: fmean(s["within_context_mse_seconds2"][c] for s in records) for c in CONTEXTS}})
    return {"task_id": TASK_ID, "expected_sha256": expected["expected_sha256"],
            "evidence_kind": expected["roster"]["evidence_kind"],
            "endpoint": "mouse_macro_cross_context_circular_mse_seconds2",
            "loss": fmean(m["across_mse_seconds2"] for m in mouse_rows),
            "shaping_strata": {g: fmean(m["across_mse_seconds2"] for m in mouse_rows if m["shaping_group"] == g) for g in SESSIONS},
            "within_context_mse_seconds2": {c: fmean(m["within_context_mse_seconds2"][c] for m in mouse_rows) for c in CONTEXTS},
            "sessions": sessions, "mice": mouse_rows, "prediction_count": len(values),
            "scientifically_qualified": False, "submission_ready": False, "open_gates": list(OPEN_GATES)}


def compare_predictions(expected, candidate, baseline):
    candidate_score = score_predictions(expected, candidate)
    baseline_score = score_predictions(expected, baseline)
    differences = [{"mouse_id": c["mouse_id"], "shaping_group": c["shaping_group"],
                    "baseline_minus_candidate_seconds2": b["across_mse_seconds2"] - c["across_mse_seconds2"]}
                   for c, b in zip(candidate_score["mice"], baseline_score["mice"])]
    values = [d["baseline_minus_candidate_seconds2"] for d in differences]
    observed = fmean(values)
    signed_means = [fmean(sign * value for sign, value in zip(signs, values)) for signs in itertools.product((-1, 1), repeat=8)]
    # One ULP inclusive comparison avoids losing mathematically exact boundary ties.
    threshold = math.nextafter(abs(observed), -math.inf)
    tail_count = sum(abs(value) >= threshold for value in signed_means)
    return {"candidate": candidate_score, "baseline": baseline_score, "paired_mouse_differences": differences,
            "mean_improvement_seconds2": observed,
            "sign_symmetry_diagnostic": {"enumerations": 256, "two_sided_tail_count": tail_count,
                                         "two_sided_tail_fraction": tail_count / 256,
                                         "calibrated_p_value": False,
                                         "interpretation": "descriptive only; overlapping leave-one-mouse-out development sets do not establish independent differences"}}


def summarize_reproduction(roster, context_pair_tables, *, method_route):
    """Summarize a complete independently reconstructed 13x9 source-workflow table.

    This does not assert that table inputs arose from native/source-identical LDA.
    SciPy is loaded only for the explicitly source-defined session t-test.
    """
    if method_route != "source_concordance_0p5s":
        raise AdmissionError("paper-only bin ambiguity is unresolved; select only the explicit source-concordance diagnostic")
    _validate_shared_roster(roster)
    if set(context_pair_tables) != {s for group in SESSIONS.values() for s in group}:
        raise AdmissionError("reproduction requires all thirteen source sessions")
    gaps, summaries = defaultdict(list), []
    for session in roster["sessions"]:
        table = context_pair_tables[session["session_id"]]
        if set(table) != set(CONTEXTS) or any(set(table[s]) != set(CONTEXTS) for s in CONTEXTS):
            raise AdmissionError("every reproduction session requires the complete 3x3 context table")
        for value in (table[s][t] for s in CONTEXTS for t in CONTEXTS):
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 100:
                raise AdmissionError("circular squared errors must be finite in [0,100] seconds squared")
        within = fmean(table[c][c] for c in CONTEXTS)
        across = fmean(table[s][t] for s in CONTEXTS for t in CONTEXTS if s != t)
        signed = across - within
        gaps[session["shaping_group"]].append(abs(signed))
        summaries.append({"session_id": session["session_id"], "mouse_id": session["mouse_id"],
                          "shaping_group": session["shaping_group"], "context_pair_mse_seconds2": table,
                          "within_mse_seconds2": within, "across_mse_seconds2": across,
                          "signed_across_minus_within_seconds2": signed, "absolute_gap_seconds2": abs(signed)})
    import scipy
    from scipy.stats import ttest_ind
    result = ttest_ind(gaps["SL_only_shaping"], gaps["standard_shaping"], equal_var=True)
    finite = math.isfinite(float(result.statistic)) and math.isfinite(float(result.pvalue))
    mouse_ids = sorted({s["mouse_id"] for s in summaries})
    return {"sessions": summaries,
            "mouse_mean_absolute_gap_seconds2": {m: fmean(s["absolute_gap_seconds2"] for s in summaries if s["mouse_id"] == m) for m in mouse_ids},
            "published_session_test": {"statistic": float(result.statistic) if finite else None,
                                       "pvalue": float(result.pvalue) if finite else None,
                                       "status": "finite" if finite else "undefined_degenerate_variance",
                                       "equal_var": True, "df": 11, "group_order": list(SESSIONS),
                                       "experimental_unit": "session", "independent_animal_inference": False,
                                       "scipy_version": scipy.__version__},
            "source_workflow_verified": False, "scientifically_qualified": False,
            "method_route": method_route, "paper_comprehension_score": False,
            "published_anchors_not_expected_results": {"t_rounded": 3.2, "p_rounding_interval": [0.008715, 0.008725]}}


def _load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise AdmissionError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def invalid(value):
        raise AdmissionError(f"nonfinite JSON constant: {value}")
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs, parse_constant=invalid)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="write OWNER-ONLY expected universe (never actor input)")
    prepare.add_argument("roster"); prepare.add_argument("freeze", help="policy_sha256 and development_assets_sha256 JSON")
    prepare.add_argument("output")
    score = commands.add_parser("score")
    score.add_argument("expected"); score.add_argument("predictions"); score.add_argument("output")
    score.add_argument("--baseline")
    reproduce = commands.add_parser("reproduction")
    reproduce.add_argument("roster"); reproduce.add_argument("tables"); reproduce.add_argument("output")
    reproduce.add_argument("--route", required=True, choices=("source_concordance_0p5s",))
    args = parser.parse_args(argv)
    if args.command == "prepare":
        freeze = _load(args.freeze)
        result = build_expected(_load(args.roster), secrets.token_bytes(32), freeze["policy_sha256"], freeze["development_assets_sha256"])
    elif args.command == "score":
        expected, predictions = _load(args.expected), _load(args.predictions)
        result = compare_predictions(expected, predictions, _load(args.baseline)) if args.baseline else score_predictions(expected, predictions)
    else:
        result = summarize_reproduction(_load(args.roster), _load(args.tables), method_route=args.route)
    # Exclusive create prevents accidentally overwriting a pre-frozen owner universe.
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(result, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
