"""Trusted development-only selector and existing owner-scoring integration.

Separate complete condition inputs are required. This code never fits a model.
A protected target is consumed only by the caller's later scoring phase.
"""
import math
import participant_core as core
import released_profile as profile
import grader
import episode_boundary as boundary

ALPHAS = (0.0001, 0.001, 0.01, 0.1, 1.0, 10.0, 100.0)
METHODS = ("calibration_mean", "count_ridge", "temporal_ridge")


def traces_for(model):
    return model["predictions"]


def validate_trace(episode, reference):
    boundary.validate_episode(episode)
    s = episode["session"]
    core.exact_keys(reference, (
        "schema", "implementation", "source_identity_authority", "session_id", "channel_ids",
        "partition_case_order", "alpha_grid", "prediction_policy", "label_endpoint",
        "observed_window", "development_use", "calibration_mean", "count_ridge", "temporal_ridge"))
    if (reference["schema"] != "apcx-session-reference-traces-v1" or
        reference["implementation"] != "apcx-public-session-ridge-v1" or
        reference["session_id"] != s["session_id"] or reference["channel_ids"] != s["channel_ids"] or
        reference["alpha_grid"] != list(ALPHAS) or
        reference["label_endpoint"] != "literal_deposited_Total_pulse" or
        reference["prediction_policy"] != "raw_finite_no_clipping_no_rounding" or
        reference["development_use"] != "returned_predictions_only_no_fitting_or_selection"):
        raise ValueError("exact complete reference/session protocol")
    order = {group: [r["case_id"] for r in s[group]]
             for group in ("calibration", "development", "queries")}
    if reference["partition_case_order"] != order:
        raise ValueError("complete unmodified partition case order")
    if reference["observed_window"] != {"start_seconds": .5, "end_seconds_exclusive": 5.0,
            "bin_seconds": .05, "bins": 90, "first_500ms": "unavailable_not_imputed"}:
        raise ValueError("whole declared observation support")
    n = len(s["calibration"])
    mean = math.fsum(r["count"]/n for r in s["calibration"])
    models = [reference["calibration_mean"]]
    for method, p in (("count_ridge", len(s["channel_ids"])),
                      ("temporal_ridge", len(s["channel_ids"])*90)):
        model = reference[method]
        expected_features = ([{"channel_id":c,"bins":"all_90_[0.5,5)_50ms"} for c in s["channel_ids"]]
            if method=="count_ridge" else [{"channel_id":c,"bin_index":i} for c in s["channel_ids"] for i in range(90)])
        if (model["calibration_count"] != n or len(model["feature_order"]) != p or
            model["feature_order"] != expected_features or
            model["normalization"]["fitted_partition"] != "calibration" or
            model["normalization"]["ddof"] != 0 or
            len(model["normalization"]["means"]) != p or
            len(model["normalization"]["population_standard_deviations"]) != p or
            len(model["normalization"]["active_mask"]) != p or
            [x["alpha"] for x in model["models"]] != list(ALPHAS)):
            raise ValueError("full feature support and calibration-only fit grid")
        norm=model["normalization"]
        if (any(not core.finite(x) for x in norm["means"]) or
            any(not core.finite(x) or x<0 for x in norm["population_standard_deviations"]) or
            any(type(x) is not bool for x in norm["active_mask"]) or
            norm["active_feature_count"] != sum(norm["active_mask"]) or
            len(model["calibration_centered_targets"]) != n or
            any(not core.finite(x) for x in model["calibration_centered_targets"]) or
            abs(model["calibration_target_mean"]-mean)>1e-12*max(1,abs(mean))):
            raise ValueError("complete finite calibration audit")
        for fit in model["models"]:
            c = fit["normal_equation_certificate"]
            if (fit["n_times_alpha"] != n*fit["alpha"] or len(fit["dual_coefficients"]) != n
                    or any(not core.finite(x) for x in fit["dual_coefficients"])
                    or c["passed"] is not True or not core.finite(c["relative_residual"])
                    or not 0 <= c["relative_residual"] <= 1e-8 or c["limit"] != 1e-8):
                raise ValueError("complete finite fit certificate")
        models.extend(model["models"])
    for model in models:
        predictions = traces_for(model)
        core.exact_keys(predictions, order)
        for group in order:
            rows = predictions[group]
            if type(rows) is not list or [r.get("case_id") for r in rows] != order[group]:
                raise ValueError("every reference prediction in exact public order")
            for r in rows:
                core.exact_keys(r, ("case_id", "prediction"))
                if not core.finite(r["prediction"]):
                    raise ValueError("finite complete prediction trace")
    prior = reference["calibration_mean"]
    if prior["calibration_count"] != n or abs(prior["calibration_target_mean"]-mean) > 1e-12*max(1,abs(mean)):
        raise ValueError("calibration-only mean baseline")
    if any(abs(r["prediction"]-mean)>1e-12*max(1,abs(mean))
           for rows in prior["predictions"].values() for r in rows):
        raise ValueError("constant baseline must equal calibration mean")
    return reference


def choose_alpha(losses):
    if len(losses) != len(ALPHAS) or any(not core.finite(x) or x < 0 for x in losses):
        raise ValueError("whole finite development loss table")
    best = min(losses)
    tolerance = 1e-12 * max(1.0, best)
    return max(i for i, loss in enumerate(losses) if loss <= best+tolerance)


def select_condition(packet, responses):
    profile.audit_public(packet)
    packet_sha = core.digest(packet)
    episodes = boundary.from_public_packet(packet)
    if type(responses) is not dict or set(responses) != {e["session"]["session_id"] for e in episodes}:
        raise ValueError("all complete session responses; no successful subset")
    refs = {}
    for e in episodes:
        sid = e["session"]["session_id"]
        response = responses[sid]
        if (response.get("status") != "COMPLETE_ONE_SESSION_REFERENCE_TRACE" or
            response.get("condition") != packet["condition"] or
            response.get("session_id") != sid or
            response.get("participant_packet_sha256") != packet_sha or
            response.get("input_sha256") != boundary.digest(e) or
            response.get("invented") != packet["invented"]):
            raise ValueError("exact selected condition/session response")
        refs[sid] = validate_trace(e, response["reference"])
    selected = {}
    dev_tables = {}
    for method in ("count_ridge", "temporal_ridge"):
        session_losses = []
        selected[method] = {}
        for e in episodes:
            sid = e["session"]["session_id"]
            dev = e["session"]["development"]
            losses = []
            for fit in refs[sid][method]["models"]:
                # Immutable scorer lower clip only; no query value or label used.
                loss = math.fsum((max(0.0, r["prediction"])-d["count"])**2/len(dev)
                                 for r, d in zip(fit["predictions"]["development"], dev))
                if not core.finite(loss):
                    raise ValueError("finite complete development loss")
                losses.append(loss)
            index = choose_alpha(losses)
            selected[method][sid] = index
            session_losses.append({"session_id": sid, "development_trials": len(dev), "losses": losses,
                                   "selected_index": index, "selected_alpha": ALPHAS[index]})
        dev_tables[method] = {"alpha_grid": list(ALPHAS),
            "all_session_losses": session_losses,
            "selection_partition": "own_session_development_only",
            "selection_weighting": "within_session_trial_mean_squared_error",
            "tie_rule": "largest alpha within1e-12*max(1,minloss)",
            "owner_animal_metadata_used": False, "other_session_development_used": False,
            "refit_on_development": False}
    submissions = {}
    for method in METHODS:
        records = []
        for e in episodes:
            sid = e["session"]["session_id"]
            fit = refs[sid]["calibration_mean"] if method == "calibration_mean" else refs[sid][method]["models"][selected[method][sid]]
            rows = [{"case_id": r["case_id"], "count": r["prediction"]}
                    for r in fit["predictions"]["queries"]]
            boundary.validate_candidate_records(e, rows)
            records.extend(rows)
        records.sort(key=lambda r: r["case_id"])
        submissions[method] = profile.submission(packet, records)
    return {"schema": "apcx-complete-condition-reference-selection-v1",
            "condition": packet["condition"], "participant_packet_sha256": packet_sha,
            "session_count": len(episodes), "protected_queries": len(submissions["calibration_mean"]["records"]),
            "development_selection": dev_tables, "submissions": submissions,
            "query_labels_available_to_selection": False, "scientific_qualification": False,
            "benchmark_count_delta": 0}


def score_frozen(owner, selection, expected_selection_sha256):
    """Caller freezes/hashes every complete prediction before reading owner."""
    if core.digest(selection) != expected_selection_sha256:
        raise ValueError("immutable complete prediction selection")
    if (selection["schema"] != "apcx-complete-condition-reference-selection-v1" or
        selection["condition"] != owner["condition"] or
        selection["participant_packet_sha256"] != owner["participant_packet_sha256"] or
        set(selection["submissions"]) != set(METHODS)):
        raise ValueError("complete condition/owner/submission join")
    reports = {method: grader.grade(owner, selection["submissions"][method]) for method in METHODS}
    if any(r.get("status") != "COMPLETE_DEPOSITED_LABEL_SCORE_ONLY" or
           r["primary_metric"] is None for r in reports.values()):
        raise ValueError("no scientific result for incomplete reference")
    primary = {m: r["primary_metric"]["value"] for m, r in reports.items()}
    return {"schema": "apcx-complete-condition-reference-scores-v1", "condition": owner["condition"],
            "selection_sha256": expected_selection_sha256, "reports": reports,
            "predeclared_primary_differences": {
                "count_minus_mean": primary["count_ridge"]-primary["calibration_mean"],
                "temporal_minus_mean": primary["temporal_ridge"]-primary["calibration_mean"],
                "temporal_minus_count": primary["temporal_ridge"]-primary["count_ridge"]},
            "primary_formula": "arithmetic mean of3 animal RMSEs, each over that animal's protected trials",
            "all_session_and_animal_metrics_required": True,
            "inference_scope": "Within released sessions only; no population, chronological or physical-delivery claim.",
            "seven_physical_primary_holds": list(core.HOLDS), "benchmark_count_delta": 0,
            "scientific_qualification": False}
