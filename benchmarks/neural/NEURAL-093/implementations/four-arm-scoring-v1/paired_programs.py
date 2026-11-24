"""Same-information comparison of two complete frozen NEURAL-093 programmes.

Both submissions pass the recovered output gate before protected target access.
The original single-program scores remain intact; this adds paired method
differences on their identical cases. Operator authentication and participant
isolation remain external requirements, not assertions established here.
"""
import copy
import math

import scorer


METHODS = ("reference", "candidate")


def _interval(mouse_rows, sources, np):
    """Prospective descriptive method interval, conditional on fitted models."""
    core, comparison = sources["score_core"], sources["comparison"]
    values = [comparison.number(row["candidate_improvements"][
        "neural_wheel_plus_context"]["natural_log_loss"]) for row in mouse_rows]
    result = dict(
        schema="neural093_paired_program_mouse_interval_v1",
        arm="neural_wheel_plus_context", metric="natural_log_loss",
        contrast="reference_minus_candidate", mouse_count=10,
        draws=core.BOOTSTRAP_DRAWS, seed=core.BOOTSTRAP_SEED,
        generator="PCG64", interval_percentiles=[2.5, 97.5], quantile_method="linear",
        descriptive=True, historical_neural_increment_interval_replaced=False,
        conditional_on_fitted_models=True, includes_training_randomness=False,
    )
    if not all(math.isfinite(value) for value in values):
        return dict(result, status="undefined_nonfinite_mouse_effect", lower=None, upper=None)
    rng = np.random.Generator(np.random.PCG64(core.BOOTSTRAP_SEED))
    indices = rng.integers(0, 10, size=(core.BOOTSTRAP_DRAWS, 10), dtype=np.int64)
    draws = np.asarray(values, dtype=np.float64)[indices].mean(axis=1)
    lower, upper = np.quantile(draws, [.025, .975], method="linear")
    return dict(result, status="finite", lower=float(lower), upper=float(upper))


def compare_programs(panel, plan, commits, raw_outputs, private_reader, np):
    """Compare reference/candidate on all39 sessions, ten mice, and2042 queries.

    commits and raw_outputs each have exactly reference/candidate keys. Each
    value uses the original four-arm scorer format. The common panel and plan
    bind both programmes to identical fit/validation/query bytes, target mapping
    and case identities; the reviewed tuning-policy digest must also match.
    All inputs are captured before calling the externally supplied reader.
    A target descriptor is read once, then its exact captured bytes are reused.
    """
    sources = scorer.load_sources()
    controls, comparison = sources["controls"], sources["comparison"]
    comparison.fields(commits, METHODS, "exact paired programme commitments")
    comparison.fields(raw_outputs, METHODS, "exact paired programme outputs")
    panel, plan, commits, raw_outputs = copy.deepcopy((panel, plan, commits, raw_outputs))
    scorer.verify_plan(panel, plan, sources)
    for method in METHODS:
        # Crucially, neither method can trigger targets before the OTHER
        # method's complete output/commit validation has succeeded.
        sources["trusted_metrics"].validate_outputs(panel, commits[method], raw_outputs[method], np)
    controls.need(commits["reference"]["tuning_policy_sha256"] ==
                  commits["candidate"]["tuning_policy_sha256"],
                  "same reviewed tuning policy and budget across programmes")

    captured_targets = {}

    def read_once(descriptor):
        key = tuple(descriptor[name] for name in ("path", "bytes", "sha256"))
        if key not in captured_targets:
            captured_targets[key] = private_reader(dict(descriptor))
        return captured_targets[key]

    reports = {method: scorer.score_study(
        panel, plan, commits[method], raw_outputs[method], read_once, np) for method in METHODS}
    summaries = {method: reports[method]["recovered_four_arm_summary"] for method in METHODS}
    controls.need(len(captured_targets) == 39, "one complete shared target capture per source session")

    def differences(reference, candidate):
        return {arm: {metric: comparison.improvement(reference[arm][metric],
                          candidate[arm][metric], metric) for metric in comparison.METRICS}
                for arm in controls.ARMS}

    session_rows, mouse_rows = [], []
    for reference, candidate in zip(summaries["reference"]["session_records"],
                                    summaries["candidate"]["session_records"], strict=True):
        identity = ("ordinal", "session", "mouse", "query_rows")
        controls.need(all(reference[key] == candidate[key] for key in identity),
                      "same ordered session support for paired programme scores")
        session_rows.append({**{key: reference[key] for key in identity},
            "candidate_improvements": differences(reference["absolute"], candidate["absolute"])})
    for reference, candidate in zip(summaries["reference"]["mouse_records"],
                                    summaries["candidate"]["mouse_records"], strict=True):
        controls.need(reference["mouse"] == candidate["mouse"]
                      and reference["sessions"] == candidate["sessions"],
                      "same ordered mouse and equal-session support")
        mouse_rows.append(dict(mouse=reference["mouse"], sessions=reference["sessions"],
            candidate_improvements=differences(reference["absolute"], candidate["absolute"])))
    improvements = {arm: {metric: comparison.extended(comparison.mean([
        comparison.number(row["candidate_improvements"][arm][metric]) for row in mouse_rows]))
        for metric in comparison.METRICS} for arm in controls.ARMS}
    return dict(
        schema="neural093_same_information_paired_programs_v1",
        sessions=39, mice=10, queries_per_arm=2042, predictions_per_program=156,
        programme_scores=reports, session_records=session_rows, mouse_records=mouse_rows,
        equal_mouse_candidate_improvements=improvements,
        comparison_endpoint=dict(arm="neural_wheel_plus_context", metric="natural_log_loss",
            units="nats_per_query", positive_means="candidate_lower_loss",
            value=improvements["neural_wheel_plus_context"]["natural_log_loss"]),
        paired_mouse_interval=_interval(mouse_rows, sources, np),
        source_commits={method: {name: commits[method][name] for name in
            ("program_sha256", "recipe_sha256", "tuning_policy_sha256")} for method in METHODS},
        information_identity="same operator-supplied panel and complete 312-packet plan",
        metric_directions_and_units=comparison.METRICS,
        all_312_outputs_validated_before_first_target_read=True,
        protected_mapping_reads=39, subset_renormalization=False,
        original_scores_or_historical_pins_modified=False,
        operator_authentication_performed=False, participant_runtime_qualified=False,
        restricted_direct_observation_qualified=False, equal_compute_measured=False,
        scientific_result_established=False,
    )
