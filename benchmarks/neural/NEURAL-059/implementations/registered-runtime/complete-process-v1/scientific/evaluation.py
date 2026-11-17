"""Independent protected evaluation from captured per-case operands only.

No reference implementation or submitted aggregate is imported. The literal
roster is the public projection in the accepted ROSTER.json; asset paths are
neither followed nor inspected. All arithmetic remains source_only_unqualified.
"""
import copy
import hashlib
import json
import math
from .diagnostics import HashRNG, PREFIX

STATUS = "source_only_unqualified"
CONDITIONS = ("SH", "SHN", "SBH", "SBHN")
METRICS = ("log_loss", "brier", "balanced_accuracy", "auc")
CLIP = 1e-12
ROSTER = (('0802ced5-33a3-405e-8336-b65ebc5cb07c', 'ZFM-02373', 'mainenlab'), ('09394481-8dd2-4d5c-9327-f2753ede92d7', 'ibl_witten_26', 'wittenlab'), ('0cbeae00-e229-4b7d-bdcc-1b0569d7e0c3', 'CSHL055', 'churchlandlab'), ('12dc8b34-b18e-4cdd-90a9-da134a9be79c', 'CSHL053', 'churchlandlab'), ('16693458-0801-4d35-a3f1-9115c7e5acfd', 'KS014', 'cortexlab'), ('19e66dc9-bf9f-430b-9d6a-acfa85de6fb7', 'UCLA006', 'churchlandlab_ucla'), ('28338153-4113-485b-835b-91cb96d984f2', 'NR_0028', 'steinmetzlab'), ('29a6def1-fc5c-4eea-ac48-47e9b053dcb5', 'NR_0028', 'steinmetzlab'), ('2d9bfc10-59fb-424a-b699-7c42f86c7871', 'NR_0024', 'steinmetzlab'), ('3bcb81b4-d9ca-4fc9-a1cd-353a966239ca', 'NR_0024', 'steinmetzlab'), ('5569f363-0934-464e-9a5b-77c8e67791a1', 'NYU-30', 'angelakilab'), ('56956777-dca5-468c-87cb-78150432cc57', 'NYU-11', 'angelakilab'), ('5c0c560e-9e1f-45e9-b66e-e4ee7855be84', 'NR_0028', 'steinmetzlab'), ('5ec72172-3901-4771-8777-6e9490ca51fc', 'NYU-30', 'angelakilab'), ('6713a4a7-faed-4df2-acab-ee4e63326f8d', 'NYU-11', 'angelakilab'), ('6f6d2c8e-28be-49f4-ae4d-06be2d3148c1', 'ZFM-02370', 'mainenlab'), ('77e6dc6a-66ed-433c-b1a2-778c914f523c', 'NYU-30', 'angelakilab'), ('7cc74598-9c1b-436b-84fa-0bf89f31adf6', 'NR_0024', 'steinmetzlab'), ('810b1e07-009e-4ebe-930a-915e4cd8ece4', 'CSHL053', 'churchlandlab'), ('8c025071-c4f3-426c-9aed-f149e8f75b7b', 'NYU-65', 'angelakilab'), ('934dd7a4-fbdc-459c-8830-04fe9033bc28', 'ZM_3003', 'mainenlab'), ('b9c205c3-feac-485b-a89d-afc96d9cb280', 'KS014', 'cortexlab'), ('c958919c-2e75-435d-845d-5b62190b520e', 'NR_0028', 'steinmetzlab'), ('d0c91c3c-8cbb-4929-8657-31f18bffc294', 'ZFM-02370', 'mainenlab'), ('dc21e80d-97d7-44ca-a729-a8e3f9b14305', 'ibl_witten_26', 'wittenlab'), ('e1931de1-cf7b-49af-af33-2ade15e8abe7', 'KS014', 'cortexlab'), ('f4eb56a4-8bf8-4bbc-a8f3-6e6535134bad', 'NR_0024', 'steinmetzlab'), ('f56194bc-8215-4ae8-bc6a-89781ad8e050', 'NR_0028', 'steinmetzlab'), ('fe1fd79f-b051-411f-a0a9-2530a02cc78d', 'ZM_3003', 'mainenlab'))
ANIMAL_ORDER = tuple(dict.fromkeys(r[1] for r in ROSTER))
LAB_ORDER = tuple(dict.fromkeys(r[2] for r in ROSTER))


def _token(value):
    """Typed exact JSON equality: True, 1 and 1.0 are distinct identities."""
    return json.dumps(value, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False)


def _equal(a, b):
    try:
        return _token(a) == _token(b)
    except (TypeError, ValueError):
        return False


def _safe(value):
    """Preserve nonfinite failures as typed evidence, never JSON NaN scores."""
    if isinstance(value, float) and not math.isfinite(value):
        return {"unavailable_numeric": repr(value)}
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    return value


def _digest(value):
    return hashlib.sha256(_token(value).encode("utf-8")).hexdigest()


def _probability(p):
    return type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1


def trial_score(y, p):
    """Actual one-observation arithmetic; invalid operands are hard failures."""
    if type(y) is not int or y not in (0, 1):
        raise ValueError("truth_not_binary_integer")
    if not _probability(p):
        raise ValueError("probability_not_finite_in_unit_interval")
    clipped = min(1 - CLIP, max(CLIP, p))
    predicted = int(p >= .5)
    return {"y": y, "raw_probability": p, "predicted_left": predicted,
            "clipped_for_log_loss": clipped != p,
            "log_loss": -math.log(clipped) if y else -math.log1p(-clipped),
            "brier": (p - y) ** 2,
            "confusion": "TP" if y and predicted else "FN" if y else "FP" if predicted else "TN"}


def metrics_from_pairs(pairs):
    """Compute pooled metrics, including exact-tie rank AUC, from (y,p)."""
    observations = [trial_score(y, p) for y, p in pairs]
    n = len(observations)
    counts = {name: sum(row["confusion"] == name for row in observations)
              for name in ("TN", "FP", "FN", "TP")}
    left, right = counts["TP"] + counts["FN"], counts["TN"] + counts["FP"]
    scores = {metric: None for metric in METRICS}
    reasons = {}
    if n:
        scores["log_loss"] = math.fsum(row["log_loss"] for row in observations) / n
        scores["brier"] = math.fsum(row["brier"] for row in observations) / n
    else:
        reasons.update({metric: "empty_support" for metric in METRICS})
    if left and right:
        scores["balanced_accuracy"] = (counts["TP"] / left + counts["TN"] / right) / 2
        ordered = sorted(observations, key=lambda row: row["raw_probability"])
        preceding_negative = numerator_twice = i = 0
        while i < n:
            j = i + 1
            while j < n and ordered[j]["raw_probability"] == ordered[i]["raw_probability"]:
                j += 1
            positive = sum(row["y"] for row in ordered[i:j])
            negative = j - i - positive
            numerator_twice += positive * (2 * preceding_negative + negative)
            preceding_negative += negative
            i = j
        scores["auc"] = numerator_twice / (2 * left * right)
    elif n:
        reasons.update({metric: "one_class_support" for metric in ("balanced_accuracy", "auc")})
    return {"scores": scores, "metric_reasons": reasons, "n": n,
            "class_counts": {"right": right, "left": left}, "confusion": counts,
            "clipping_count": sum(row["clipped_for_log_loss"] for row in observations)}


def _draws(animal_order):
    for replicate in range(1999):
        rng = HashRNG([PREFIX, "animal-bootstrap", replicate])
        yield tuple(rng.randbelow(len(animal_order)) for _ in animal_order)


def _spread(animal_values, animal_order, draws):
    result = {"status": STATUS, "label": "conditional resampling spread; coverage unqualified",
              "replicates": 1999, "animal_order": list(animal_order),
              "percentile_method": "linear interpolation h=(1999-1)*q",
              "lower_0.025": None, "upper_0.975": None,
              "conditions": "fixed fitted predictions; animal exchangeability unestablished; no refitting or test-null"}
    check = HashRNG([PREFIX, "animal-bootstrap", 0])
    if [check.randbelow(13) for _ in range(13)] != [5, 11, 3, 0, 1, 7, 3, 7, 8, 10, 3, 11, 5]:
        return dict(result, reason="independent_frozen_rng_vector_failed")
    if tuple(animal_order) != ANIMAL_ORDER or set(animal_values) != set(animal_order):
        return dict(result, reason="incomplete_or_wrong_frozen_animal_support")
    values = [animal_values[a] for a in animal_order]
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
        return dict(result, reason="nonfinite_or_unavailable_animal_value")
    samples = sorted(math.fsum(values[i] for i in draw) / 13 for draw in draws)
    if len(samples) != 1999:
        raise ValueError("incomplete_bootstrap_draw_support")
    def percentile(q):
        h = (len(samples) - 1) * q
        lo = math.floor(h)
        return samples[lo] + (h - lo) * (samples[math.ceil(h)] - samples[lo])
    return dict(result, **{"lower_0.025": percentile(.025), "upper_0.975": percentile(.975)},
                reason=None, independent_check="source-only independent frozen RNG vector; see controls")


def conditional_spread(animal_values, animal_order):
    """The complete 1999-draw conditional spread, with exact frozen animal order."""
    return _spread(animal_values, animal_order, _draws(animal_order))


def _roster_members(roster_members):
    found = tuple((m.get("eid", m.get("session_id")),
                   m.get("subject", m.get("subject_id")), m.get("lab")) for m in roster_members)
    if found != ROSTER:
        raise ValueError("frozen_29_session_13_animal_7_lab_roster_mismatch")
    return found


def reference_slots(roster_members):
    """Stream all 61,132 prospective fit identities; this executes zero fits."""
    roster = _roster_members(roster_members)
    panels = [("identity", None, CONDITIONS)]
    panels.extend(("D-label", r, CONDITIONS) for r in range(20))
    panels.extend(("D-neural", r, ("SHN", "SBHN")) for r in range(20))
    for tag, replicate, conditions in panels:
        for eid, subject, lab in roster:
            for condition in conditions:
                for family in ("L", "H"):
                    grid = ([{"lambda": v} for v in (.001, .1, 10.)] if family == "L" else
                            [{"max_leaf_nodes": leaves, "max_iter": iterations,
                              "l2_regularization": penalty}
                             for leaves in (7, 15, 31) for iterations in (100, 300) for penalty in (1., 10.)])
                    for index, config in enumerate(grid + [None]):
                        identity = {"session_id": eid, "subject_id": subject, "lab": lab,
                                    "condition": condition, "family": family,
                                    "diagnostic_tag": tag, "replicate": replicate,
                                    "stage": "grid" if config is not None else "refit",
                                    "grid_index": index if config is not None else None,
                                    "config": config, "status": "declared_not_executed"}
                        identity["slot_id"] = _digest(identity)
                        yield identity


def prior_slots(roster_members):
    """58 estimates, reused by exact identity across conditions and diagnostics."""
    for eid, subject, lab in _roster_members(roster_members):
        for split in ("train", "train+val"):
            identity = {"session_id": eid, "subject_id": subject, "lab": lab,
                        "fitting_support": split, "status": "declared_not_executed"}
            yield dict(identity, prior_id=_digest(identity))


def build_prediction(prepared, case, method, condition, p, *, status="ok", error=None):
    """Operator capture convenience only; score_panel independently rejoins it."""
    commitments = [c for c in method["commitments"]
                   if c["session_id"] == prepared["session_id"] and c["condition"] == condition]
    if len(commitments) != 1:
        raise ValueError("prediction_requires_one_precommitted_cell")
    committed = commitments[0]
    row = {k: copy.deepcopy(prepared[k]) for k in ("session_id", "subject_id", "lab", "source_identity", "unit_ids")}
    row.update({k: copy.deepcopy(case[k]) for k in ("case_id", "ordinal", "split", "prior_case_id")})
    row.update({k: copy.deepcopy(method[k]) for k in ("method_id", "arm", "method_source_identity")})
    row.update({k: copy.deepcopy(committed[k]) for k in ("config_identity", "parameter_identity")})
    row.update(condition=condition, p=p, status=status)
    if error is not None:
        row["error"] = copy.deepcopy(error)
    return row


def _null_scores(reason):
    return {"scores": {metric: None for metric in METRICS},
            "metric_reasons": {metric: reason for metric in METRICS}}


def _method_key(method):
    return method["method_id"], method["arm"]


def _valid_identity(value):
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, dict):
        try:
            return bool(value) and bool(_token(value))
        except (TypeError, ValueError):
            return False
    return False


def _preparation(prepared_sessions):
    """Validate protected support against the literal full roster, retaining holds."""
    expected = {eid: (subject, lab) for eid, subject, lab in ROSTER}
    groups, global_failures = {}, []
    for session in prepared_sessions:
        eid = session.get("session_id")
        if not isinstance(eid, str) or eid not in expected:
            global_failures.append({"reason": "unexpected_prepared_session", "session": _safe(session)})
        else:
            groups.setdefault(eid, []).append(session)
    sessions = {}
    for eid, subject, lab in ROSTER:
        candidates = groups.get(eid, [])
        failures = []
        if len(candidates) != 1:
            failures.append({"reason": "missing_prepared_session" if not candidates else "duplicate_prepared_session"})
            sessions[eid] = {"prepared": None, "cases": [], "failures": failures, "support_identity": None}
            continue
        session = candidates[0]
        for field, expected_value in (("subject_id", subject), ("lab", lab), ("status", STATUS)):
            if not _equal(session.get(field), expected_value):
                failures.append({"reason": "prepared_axis_mismatch", "field": field,
                                 "observed": _safe(session.get(field)), "expected": expected_value})
        if session.get("structural_holds", []):
            failures.append({"reason": "preparation_structural_holds", "original": _safe(session["structural_holds"])})
        if not _valid_identity(session.get("source_identity")):
            failures.append({"reason": "missing_or_invalid_source_identity"})
        units = session.get("unit_ids")
        if not isinstance(units, list) or not units or any(not isinstance(u, str) or not u for u in units) or len(set(units)) != len(units):
            failures.append({"reason": "invalid_prepared_unit_axis"})
        cases, seen_ids, seen_ordinals = [], set(), set()
        for case in session.get("cases", []):
            valid = True
            cid, ordinal, split = case.get("case_id"), case.get("ordinal"), case.get("split")
            if not isinstance(cid, str) or not cid or cid in seen_ids:
                failures.append({"reason": "invalid_or_duplicate_case_id", "case": _safe(case)})
                valid = False
            if type(ordinal) is not int or ordinal < 0 or ordinal in seen_ordinals:
                failures.append({"reason": "invalid_or_duplicate_original_ordinal", "case_id": cid})
                valid = False
            if split not in ("train", "val", "test"):
                failures.append({"reason": "invalid_case_split", "case_id": cid})
                valid = False
            if "prior_case_id" not in case or not (case["prior_case_id"] is None or isinstance(case["prior_case_id"], str)):
                failures.append({"reason": "invalid_predecessor_identity", "case_id": cid})
                valid = False
            if type(case.get("y")) is not int or case["y"] not in (0, 1):
                failures.append({"reason": "invalid_protected_truth", "case_id": cid})
                valid = False
            if "unit_ids" in case and not _equal(case["unit_ids"], units):
                failures.append({"reason": "prepared_case_unit_mismatch", "case_id": cid})
                valid = False
            if isinstance(cid, str):
                seen_ids.add(cid)
            if type(ordinal) is int:
                seen_ordinals.add(ordinal)
            if valid and split == "test":
                cases.append(case)
        cases.sort(key=lambda c: c["ordinal"])
        if not cases:
            failures.append({"reason": "empty_held_support"})
        support = {k: session.get(k) for k in ("session_id", "subject_id", "lab", "source_identity", "unit_ids")}
        support["cases"] = [{k: c[k] for k in ("case_id", "ordinal", "split", "prior_case_id", "y")} for c in cases]
        try:
            support_identity = _digest(support)
        except (TypeError, ValueError):
            support_identity = None
            failures.append({"reason": "noncanonical_support_identity"})
        sessions[eid] = {"prepared": session, "cases": cases, "failures": failures,
                         "support_identity": support_identity}
    return sessions, global_failures


def score_panel(prepared_sessions, predictions, *, expected_methods):
    """Complete per-trial/session/animal scores and predeclared paired contrasts.

    expected_methods are method/arm records with typed method_source_identity and
    pre-query commitments for every session/condition. Predictions are protected
    captured row records, not summaries; missing/extra/mismatched axes stay held.
    All full-population summaries require every required case and all 13 animals.
    """
    sessions, global_failures = _preparation(prepared_sessions)
    methods, method_keys = [], set()
    for method in expected_methods:
        if not isinstance(method.get("method_id"), str) or not method["method_id"]:
            raise ValueError("expected_method_id_required")
        kind, arm = method.get("kind"), method.get("arm")
        if kind not in ("actor", "reference", "prior") or arm not in (("F", "I") if kind == "actor" else ("R",)):
            raise ValueError("expected_method_kind_arm_axis")
        if not _valid_identity(method.get("method_source_identity")):
            raise ValueError("expected_method_source_identity_required")
        key = _method_key(method)
        if key in method_keys:
            raise ValueError("duplicate_expected_method_arm")
        methods.append(method)
        method_keys.add(key)
    if not methods:
        raise ValueError("expected_methods_empty")
    groups = {}
    for index, row in enumerate(predictions):
        key = (row.get("method_id"), row.get("arm"))
        eid, condition = row.get("session_id"), row.get("condition")
        if any(not isinstance(v, str) for v in (*key, eid, condition)) or key not in method_keys or eid not in sessions or condition not in CONDITIONS:
            global_failures.append({"reason": "unexpected_prediction_axis", "input_index": index, "original": _safe(row)})
        else:
            groups.setdefault((key, eid, condition), []).append((index, row))
    output = {"status": STATUS, "scientific_qualification": False,
              "roster": [{"session_id": e, "subject_id": s, "lab": l} for e, s, l in ROSTER],
              "animal_order": list(ANIMAL_ORDER), "lab_order": list(LAB_ORDER),
              "global_failures": global_failures, "methods": [], "contrasts": []}
    lookup = {}
    for method in methods:
        key = _method_key(method)
        commitments, commitment_failures = {}, []
        for commitment in method.get("commitments", []):
            cell = (commitment.get("session_id"), commitment.get("condition"))
            if any(not isinstance(v, str) for v in cell) or cell[0] not in sessions or cell[1] not in CONDITIONS:
                commitment_failures.append({"reason": "unexpected_commitment_axis", "original": _safe(commitment)})
            else:
                commitments.setdefault(cell, []).append(commitment)
        method_result = {k: copy.deepcopy(method[k]) for k in ("method_id", "kind", "arm", "method_source_identity")}
        method_result["conditions"] = []
        for condition in CONDITIONS:
            condition_result = {"condition": condition, "sessions": [], "animals": []}
            accepted_by_session = {}
            for eid, subject, lab in ROSTER:
                prepared = sessions[eid]
                failures = copy.deepcopy(prepared["failures"] + commitment_failures)
                if global_failures:
                    failures.append({"reason": "panel_global_axis_failures"})
                declarations = commitments.get((eid, condition), [])
                commitment = declarations[0] if len(declarations) == 1 else None
                if commitment is None:
                    failures.append({"reason": "missing_commitment" if not declarations else "duplicate_commitment",
                                     "originals": _safe(declarations)})
                elif commitment.get("status", "ok") != "ok":
                    failures.append({"reason": "failed_commitment", "original": _safe(commitment)})
                elif any(not _valid_identity(commitment.get(k)) for k in ("config_identity", "parameter_identity")):
                    failures.append({"reason": "invalid_committed_model_identity", "original": _safe(commitment)})
                if method["kind"] == "prior":
                    reused = [commitments.get((eid, c), []) for c in CONDITIONS]
                    if any(len(rows) != 1 for rows in reused) or any(
                        not _equal(reused[0][0].get(field), rows[0].get(field))
                        for rows in reused if len(rows) == 1 for field in ("config_identity", "parameter_identity")):
                        failures.append({"reason": "prior_fitting_identity_not_shared"})
                expected_cases = {c["case_id"]: c for c in prepared["cases"]}
                rows_by_case = {}
                for index, row in groups.get((key, eid, condition), []):
                    cid = row.get("case_id")
                    if not isinstance(cid, str) or cid not in expected_cases:
                        failures.append({"reason": "unexpected_held_case", "input_index": index, "original": _safe(row)})
                    else:
                        rows_by_case.setdefault(cid, []).append((index, row))
                trial_rows, valid_pairs = [], []
                session = prepared["prepared"]
                for case in prepared["cases"]:
                    cid = case["case_id"]
                    received = rows_by_case.get(cid, [])
                    errors = []
                    row = received[0][1] if len(received) == 1 else None
                    if row is None:
                        errors.append("missing_prediction" if not received else "duplicate_prediction")
                    else:
                        expected_axes = {k: session.get(k) for k in ("session_id", "subject_id", "lab", "source_identity", "unit_ids")}
                        expected_axes.update({k: case[k] for k in ("case_id", "ordinal", "split", "prior_case_id")})
                        expected_axes.update({k: method[k] for k in ("method_id", "arm", "method_source_identity")})
                        expected_axes["condition"] = condition
                        if commitment is not None:
                            expected_axes.update({k: commitment.get(k) for k in ("config_identity", "parameter_identity")})
                        for field, expected_value in expected_axes.items():
                            if field not in row or not _equal(row[field], expected_value):
                                errors.append("prediction_axis_mismatch:" + field)
                        if row.get("status") != "ok":
                            errors.append("prediction_declared_failure")
                        if not _probability(row.get("p")):
                            errors.append("invalid_probability")
                    trial = {"case_id": cid, "ordinal": case["ordinal"], "split": "test",
                             "prior_case_id": case["prior_case_id"], "protected_y": case["y"],
                             "status": "unavailable" if errors else "arithmetically_valid_unqualified",
                             "failures": errors, "captured_rows": [_safe(r) for _, r in received]}
                    if errors:
                        failures.append({"reason": "trial_failure", "case_id": cid, "failures": errors})
                    else:
                        trial["arithmetic"] = trial_score(case["y"], row["p"])
                        valid_pairs.append((case["y"], row["p"]))
                    trial_rows.append(trial)
                descriptive = metrics_from_pairs(valid_pairs)
                complete = not failures and bool(prepared["cases"]) and len(valid_pairs) == len(prepared["cases"])
                result = {"session_id": eid, "subject_id": subject, "lab": lab,
                          "status": "complete_arithmetic_unqualified" if complete else "unavailable",
                          "support_identity": prepared["support_identity"],
                          "source_identity": _safe(session.get("source_identity")) if session else None,
                          "unit_ids": copy.deepcopy(session.get("unit_ids")) if session else None,
                          "commitment": _safe(commitment), "expected_n": len(prepared["cases"]),
                          "accepted_n": len(valid_pairs), "failures": failures, "trials": trial_rows,
                          "supported_descriptive": descriptive}
                result.update(descriptive if complete else _null_scores("incomplete_required_session_support"))
                condition_result["sessions"].append(result)
                accepted_by_session[eid] = valid_pairs
            for animal in ANIMAL_ORDER:
                selected = [r for r in condition_result["sessions"] if r["subject_id"] == animal]
                pairs = [pair for r in selected for pair in accepted_by_session[r["session_id"]]]
                descriptive = metrics_from_pairs(pairs)
                complete = all(r["status"] == "complete_arithmetic_unqualified" for r in selected)
                animal_result = {"subject_id": animal, "lab": selected[0]["lab"],
                                 "session_ids": [r["session_id"] for r in selected],
                                 "support_identities": [r["support_identity"] for r in selected],
                                 "expected_n": sum(r["expected_n"] for r in selected),
                                 "accepted_n": len(pairs), "supported_descriptive": descriptive,
                                 "status": "complete_arithmetic_unqualified" if complete else "unavailable",
                                 "failed_sessions": [r["session_id"] for r in selected if r["status"] != "complete_arithmetic_unqualified"]}
                animal_result.update(descriptive if complete else _null_scores("incomplete_required_animal_support"))
                condition_result["animals"].append(animal_result)
            macro, macro_reasons, supported = {}, {}, {}
            for metric in METRICS:
                values = [a["scores"][metric] for a in condition_result["animals"]]
                finite = [v for v in values if v is not None]
                macro[metric] = math.fsum(finite) / 13 if len(finite) == 13 else None
                macro_reasons[metric] = None if len(finite) == 13 else "requires_all_13_defined_animal_metrics"
                supported[metric] = {"mean": math.fsum(finite) / len(finite) if finite else None,
                                     "denominator": len(finite), "required_denominator": 13}
            condition_result["equal_animal_primary"] = {"scores": macro, "metric_reasons": macro_reasons,
                                                         "denominator": 13}
            condition_result["supported_animal_descriptive"] = supported
            pooled = metrics_from_pairs([pair for rows in accepted_by_session.values() for pair in rows])
            all_complete = all(r["status"] == "complete_arithmetic_unqualified" for r in condition_result["sessions"])
            condition_result["pooled_trial_secondary"] = {"complete": all_complete,
                                                            "supported_descriptive": pooled,
                                                            **(pooled if all_complete else _null_scores("incomplete_required_cohort_support"))}
            method_result["conditions"].append(condition_result)
            lookup[(key, condition)] = condition_result
        output["methods"].append(method_result)
    output["contrasts"] = _contrasts(methods, lookup)
    return output


def _contrasts(methods, lookup):
    declarations = []
    for method in methods:
        key = _method_key(method)
        for context, neural in (("SH", "SHN"), ("SBH", "SBHN")):
            declarations.append(("neural:" + ":".join(key) + ":" + context,
                                 [(key, context, 1), (key, neural, -1)],
                                 "loss(C)-loss(C+N); BA/AUC(C+N)-BA/AUC(C)"))
        for low, high in (("SH", "SBH"), ("SHN", "SBHN")):
            declarations.append(("privileged_context:" + ":".join(key) + ":" + low,
                                 [(key, low, 1), (key, high, -1)],
                                 "loss(without B)-loss(with B); BA/AUC(with B)-BA/AUC(without B)"))
    actor_ids = list(dict.fromkeys(m["method_id"] for m in methods if m["kind"] == "actor"))
    for method_id in actor_ids:
        f, i = (method_id, "F"), (method_id, "I")
        for condition in CONDITIONS:
            declarations.append(("investigation:" + method_id + ":" + condition,
                                 [(f, condition, 1), (i, condition, -1)],
                                 "loss(F)-loss(I); BA/AUC(I)-BA/AUC(F)"))
        for context, neural in (("SH", "SHN"), ("SBH", "SBHN")):
            declarations.append(("interaction:" + method_id + ":" + context,
                                 [(f, context, 1), (f, neural, -1), (i, context, -1), (i, neural, 1)],
                                 "[loss(F,C)-loss(F,C+N)]-[loss(I,C)-loss(I,C+N)]; BA/AUC uses reversed score orientation"))
    draws = tuple(_draws(ANIMAL_ORDER))
    results = []
    for name, terms, formula in declarations:
        for metric in METRICS:
            values, animal_support = {}, []
            for index, animal in enumerate(ANIMAL_ORDER):
                inputs, reasons, supports = [], [], []
                for key, condition, coefficient in terms:
                    cell = lookup.get((key, condition))
                    if cell is None:
                        reasons.append("missing_required_method_arm")
                        continue
                    row = cell["animals"][index]
                    supports.append(row["support_identities"])
                    value = row["scores"][metric]
                    if value is None:
                        reasons.append(row["metric_reasons"].get(metric, "unavailable_metric"))
                    else:
                        inputs.append(coefficient * value)
                if supports and any(s != supports[0] for s in supports[1:]):
                    reasons.append("unpaired_source_case_unit_support")
                value = None if reasons else math.fsum(inputs) * (-1 if metric in ("balanced_accuracy", "auc") else 1)
                values[animal] = value
                animal_support.append({"subject_id": animal, "value": value, "reasons": reasons,
                                       "session_ids": [r[0] for r in ROSTER if r[1] == animal],
                                       "support_identities": supports[0] if supports else []})
            results.append(_contrast_summary(name, metric, formula, terms, values, animal_support, draws))
    return results


def _contrast_summary(name, metric, formula, terms, values, animal_support, draws):
    def retained_mean(animals):
        supported = [a for a in animals if values[a] is not None]
        return {"value": math.fsum(values[a] for a in animals) / len(animals) if len(supported) == len(animals) and animals else None,
                "retained_animals": list(animals), "denominator": len(animals),
                "available_denominator": len(supported),
                "reason": None if len(supported) == len(animals) else "incomplete_prespecified_retained_support"}
    complete = retained_mean(ANIMAL_ORDER)
    finite = [v for v in values.values() if v is not None]
    return {"contrast_id": name, "metric": metric, "formula": formula,
            "terms": [{"method_id": k[0], "arm": k[1], "condition": c, "loss_coefficient": x} for k, c, x in terms],
            "animal_values": animal_support, "complete_equal_animal": complete,
            "supported_descriptive": {"mean": math.fsum(finite) / len(finite) if finite else None,
                                      "denominator": len(finite), "required_denominator": 13},
            "leave_one_animal": [{"omitted_animal": a, **retained_mean([x for x in ANIMAL_ORDER if x != a])} for a in ANIMAL_ORDER],
            "leave_one_lab": [{"omitted_lab": lab, **retained_mean([a for a in ANIMAL_ORDER if next(r[2] for r in ROSTER if r[1] == a) != lab])} for lab in LAB_ORDER],
            "conditional_spread": _spread(values, ANIMAL_ORDER, draws),
            "interpretation": "conditional predictive contrast; no causal effect, p-value or binary success rule"}


def score_diagnostic_change(prepared_sessions, primary_predictions, diagnostic_predictions, *,
                            primary_methods, diagnostic_methods, tag, replicate):
    """Recompute complete paired diagnostic changes from captured operands.

    Inputs contain references/priors only. Neural diagnostics reuse the exact
    original C rows, and all diagnostics reuse exact primary prior predictions.
    This consumes no actor arrays and selects or repairs no primary method.
    """
    if tag not in ("D-label", "D-neural") or type(replicate) is not int or not 0 <= replicate < 20:
        raise ValueError("undeclared_diagnostic_score_identity")
    for methods in (primary_methods, diagnostic_methods):
        if any(m.get("kind") not in ("reference", "prior") or m.get("arm") != "R" for m in methods):
            raise ValueError("diagnostics_are_fixed_references_only")
    if {_method_key(m) for m in primary_methods} != {_method_key(m) for m in diagnostic_methods}:
        raise ValueError("diagnostic_method_support_mismatch")
    for primary_method in primary_methods:
        matches = [m for m in diagnostic_methods if _method_key(m) == _method_key(primary_method)]
        if len(matches) != 1 or any(not _equal(primary_method.get(field), matches[0].get(field))
                                   for field in ("kind", "method_source_identity")):
            raise ValueError("diagnostic_requires_unchanged_reference_source")
    primary_rows = list(primary_predictions)
    diagnostic_rows = list(diagnostic_predictions)
    priors = {m["method_id"] for m in primary_methods if m["kind"] == "prior"}
    def reused(row):
        return row.get("method_id") in priors or (tag == "D-neural" and row.get("condition") in ("SH", "SBH"))
    def row_key(row):
        return tuple(row.get(k) for k in ("method_id", "arm", "session_id", "condition", "case_id"))
    originals = {}
    for row in primary_rows:
        originals.setdefault(row_key(row), []).append(row)
    reuse_failures = []
    for row in diagnostic_rows:
        if reused(row):
            candidates = originals.get(row_key(row), [])
            if len(candidates) != 1 or not _equal(row, candidates[0]):
                reuse_failures.append({"reason": "diagnostic_required_exact_reference_reuse", "original": _safe(row)})
    primary = score_panel(prepared_sessions, primary_rows, expected_methods=primary_methods)
    diagnostic = score_panel(prepared_sessions, diagnostic_rows, expected_methods=diagnostic_methods)
    lookup = {}
    for phase, report in (("primary", primary), ("diagnostic", diagnostic)):
        for method in report["methods"]:
            for condition in method["conditions"]:
                lookup[(phase, _method_key(method), condition["condition"])] = condition
    changes, draws = [], tuple(_draws(ANIMAL_ORDER))
    for method in primary_methods:
        key = _method_key(method)
        for condition in CONDITIONS:
            left = lookup[("primary", key, condition)]
            right = lookup[("diagnostic", key, condition)]
            for metric in METRICS:
                values, support = {}, []
                for a, b in zip(left["animals"], right["animals"]):
                    reasons = []
                    if a["support_identities"] != b["support_identities"]:
                        reasons.append("diagnostic_unpaired_support")
                    x, y = a["scores"][metric], b["scores"][metric]
                    if x is None or y is None:
                        reasons.append("diagnostic_incomplete_metric_support")
                    if reuse_failures:
                        reasons.append("diagnostic_exact_reuse_failed")
                    value = None if reasons else y - x
                    values[a["subject_id"]] = value
                    support.append({"subject_id": a["subject_id"], "value": value, "reasons": reasons,
                                    "session_ids": a["session_ids"], "support_identities": a["support_identities"]})
                changes.append(_contrast_summary(
                    "diagnostic_change:" + tag + ":" + str(replicate) + ":" + ":".join(key) + ":" + condition,
                    metric, "score(diagnostic)-score(primary); positive loss/Brier worsens, positive BA/AUC improves",
                    [(key, condition, 1)], values, support, draws))
    return {"status": STATUS, "tag": tag, "replicate": replicate,
            "primary": primary, "diagnostic": diagnostic, "paired_changes": changes,
            "reuse_failures": reuse_failures,
            "interpretation": "association stress diagnostic; no scientific null, p-value or primary selection"}
