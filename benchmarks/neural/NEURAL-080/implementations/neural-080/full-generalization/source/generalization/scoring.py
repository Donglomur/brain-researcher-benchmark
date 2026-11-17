"""Protected full-support comparison in original EEG units.

Only compare is the public score entry point. It re-admits every prediction and
reference scale before opening the private pool manifest. Source preparation
has already handled private EEG under its trusted operator; target-last here
means the comparison/candidate boundary, not absence of earlier trusted access.
No import of this module performs numerical work or opens an operand.
"""
from __future__ import annotations

import math
from .artifacts import (ARMS, MODES, TOOL_REGIMES, CANDIDATE_CELLS, CANDIDATE_KEYS,
                        TARGET_SHAPE, CapturedPanel, admit_panel,
                        array_limit, capture_array, capture_document, decode_array,
                        descriptor, need, read_operand)
from .splits import PERSONS, VIDEO_IDS, outer_cases, validate_family_plan

SCORE_LABELS = tuple("reference:" + arm for arm in ARMS) + tuple(
    "candidate:" + key for key in CANDIDATE_KEYS)
CONTRAST_LABELS = (
    "scientific_dynamic_gain", "dynamic_gain_without_eye", "ocular_gain_in_full",
    "ocular_gain_in_nuisance", "eye_adjustment_attenuation", "reversal_risk_increase") + tuple(
    "candidate_improvement:" + key for key in CANDIDATE_KEYS)
METRIC_LABELS = SCORE_LABELS + CONTRAST_LABELS
RESAMPLES = 10000
RESAMPLE_SEED = 80080
PROFILE = "released_whole_record_derivatives_disclosed_v1"
SOURCE_CLOCK = {"samples": 1800, "sampling_hz": 500, "start_s": -0.1,
                "last_s": 3.498, "analysis_slice": [50, 1550]}


def _finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _text(value):
    return (type(value) is str and bool(value.strip()) and value == value.strip() and
            not any(ord(character) < 32 or ord(character) == 127 for character in value))


def _target_contract(root, document, owner):
    """Read actual locally captured provenance; this is not an input issuer."""
    descriptor(document.get("target_contract"), 4 * 1024 * 1024)
    _, contract = capture_document(root, document["target_contract"], owner)
    need(type(contract) is dict and set(contract) == {
        "schema", "channel_names", "eeg_reference", "eeg_units", "source_clock",
        "preprocessing_profile", "preprocessing_evidence"} and
        contract["schema"] == "neural080_target_basis_v1" and
        contract["preprocessing_profile"] == PROFILE,
        "Actual disclosed whole-record derivative target basis required")
    names = contract["channel_names"]
    need(type(names) is list and len(names) == TARGET_SHAPE[0] and
         all(_text(name) for name in names) and len(set(names)) == TARGET_SHAPE[0] and
         _text(contract["eeg_reference"]) and _text(contract["eeg_units"]),
         "All 127 actual ordered sensor names, reference and numerical units required")
    clock = contract["source_clock"]
    need(type(clock) is dict and set(clock) == set(SOURCE_CLOCK) and
         type(clock["samples"]) is int and type(clock["sampling_hz"]) is int and
         type(clock["analysis_slice"]) is list and
         all(type(value) is int for value in clock["analysis_slice"]) and
         _finite_number(clock["start_s"]) and _finite_number(clock["last_s"]) and
         clock == SOURCE_CLOCK, "Exact fixed native source and analysis clock required")
    evidence = contract["preprocessing_evidence"]
    need(type(evidence) is list and bool(evidence) and len(evidence) <= 96,
         "Actual bounded local preprocessing evidence bodies required")
    paths = set()
    for row in evidence:
        descriptor(row, 4 * 1024 * 1024)
        need(row["path"] not in paths, "Distinct preprocessing evidence bodies required")
        paths.add(row["path"])
        # This preserves the exact prepared evidence identity. Its scientific
        # interpretation and nested source closure were validated by preparation;
        # the scorer does not turn a metadata string into native/source authority.
        capture_document(root, row, owner)
    return contract


def _pool(root, manifest, owner):
    """Called only after admit_panel completes every prediction body."""
    _, pool = capture_document(root, manifest, owner)
    need(type(pool) is dict and pool.get("schema") == "neural080_unscaled_recording_pool_v1" and
         pool.get("persons") == list(PERSONS) and type(pool.get("video_ids")) is list and
         all(type(video) is int for video in pool["video_ids"]) and
         pool["video_ids"] == list(VIDEO_IDS) and
         type(pool.get("projected_joined_trials")) is int and pool["projected_joined_trials"] == 45144,
         "Complete original unscaled private recording pool required")
    contract = _target_contract(root, pool, owner)
    basis = pool.get("basis")
    need(type(basis) is dict and basis.get("channel_names") == contract["channel_names"] and
         basis.get("eeg_shape_per_video") == list(TARGET_SHAPE) and
         basis.get("source_epoch_samples") == 1800 and
         basis.get("declared_source_sampling_hz") == 500 and
         basis.get("declared_source_epoch_start_s") == -0.1 and
         basis.get("declared_source_epoch_last_sample_s") == 3.498 and
         basis.get("analysis_native_sample_slice") == [50, 1550] and
         basis.get("analysis_interval_s") == [0.0, 3.0] and
         basis.get("analysis_bin_width_s") == 0.02 and basis.get("native_samples_per_bin") == 10 and
         basis.get("eeg_normalization") == "none; no fitted target mean or scale is applied here",
         "Fixed unnormalized original-unit 127-sensor/150-bin source basis required")
    subjects = pool.get("subjects")
    need(type(subjects) is list and len(subjects) == 6 and
         [row.get("subject") for row in subjects if type(row) is dict] == list(PERSONS),
         "Every canonical private person in exact source order required")
    recordings = pool.get("source_recordings")
    need(type(recordings) is list and len(recordings) == 96,
         "Full 96-recording source disposition roster required")
    source_keys = set()
    for row in recordings:
        need(type(row) is dict and row.get("subject") in PERSONS and
             row.get("session") in tuple("ses-%02d" % number for number in range(1, 9)) and
             row.get("modality") in ("eeg", "eye"), "Complete original recording role required")
        key = row["subject"], row["session"], row["modality"]
        need(key not in source_keys and type(row.get("bytes")) is int and row["bytes"] > 0 and
             type(row.get("captured_sha256")) is str and len(row["captured_sha256"]) == 64 and
             all(character in "0123456789abcdef" for character in row["captured_sha256"]),
             "Distinct exact captured source recording identities required")
        source_keys.add(key)
    need(len(source_keys) == 96, "Every original recording role must be represented")
    arrays, total = {}, 0
    shape = (len(VIDEO_IDS), *TARGET_SHAPE)
    for person, row in zip(PERSONS, subjects):
        need(type(row.get("arrays")) is dict and "eeg_unscaled" in row["arrays"] and
             type(row.get("joined_trials")) is int and row["joined_trials"] > 0,
             "Full unnormalized EEG and retained repeat denominator required")
        _, support = capture_document(root, row["support"], owner)
        need(type(support) is dict, "Closed private support document required")
        counts = support.get("counts_per_video")
        need(type(support) is dict and support.get("schema") == "neural080_unnormalized_person_support_v1" and
             support.get("subject") == person and type(counts) is list and len(counts) == 1102 and
             all(type(count) is int and count > 0 for count in counts) and
             sum(counts) == row["joined_trials"] == support.get("retained_joined_trials"),
             "No omitted video or repeated-trial support in private target means")
        body = capture_array(root, row["arrays"]["eeg_unscaled"], shape, owner)
        arrays[person] = decode_array(body, shape, owner)
        total += row["joined_trials"]
    need(total == 45144, "Every accepted joined repeat must retain its disposition")
    return pool, contract, arrays


def _metrics(risks, np):
    """Linear contrasts, retaining signed values and candidate-fixed references."""
    index = {label: number for number, label in enumerate(SCORE_LABELS)}
    r = lambda arm: risks[index["reference:" + arm]]
    dynamic = r("nuisance_eye") - r("full")
    without_eye = r("nuisance") - r("nuisance_dynamic")
    extras = [dynamic, without_eye, r("nuisance_dynamic") - r("full"),
              r("nuisance") - r("nuisance_eye"), without_eye - dynamic,
              r("full_reverse") - r("full")]
    extras.extend(r("full") - risks[index["candidate:" + key]] for key in CANDIDATE_KEYS)
    return np.concatenate((risks, np.asarray(extras)), axis=0)


def _mapping(values):
    return {label: float(value) for label, value in zip(METRIC_LABELS, values)}


def _stability(family_risks, writer, owner, np):
    """Prespecified descriptive, conditional two-way resampling; no refits."""
    family_count = family_risks.shape[2]
    owner.reserve("retained_bytes", RESAMPLES * (6 + family_count) * 4 +
                  RESAMPLES * len(METRIC_LABELS) * 8 + family_risks.nbytes * 2)
    generator = np.random.Generator(np.random.PCG64(RESAMPLE_SEED))
    # One shared schedule, saved in full and applied to all arms/contrasts.
    person_draws = np.empty((RESAMPLES, len(PERSONS)), dtype=np.int32)
    family_draws = np.empty((RESAMPLES, family_count), dtype=np.int32)
    samples = np.empty((RESAMPLES, len(METRIC_LABELS)), dtype=np.float64)
    for repeat in range(RESAMPLES):
        person_draws[repeat] = generator.integers(0, len(PERSONS), size=len(PERSONS), dtype=np.int32)
        family_draws[repeat] = generator.integers(0, family_count, size=family_count, dtype=np.int32)
        # Every draw includes entire provenance families, never individual trials,
        # channels, bins or selectively successful observations.
        by_person = np.take(family_risks, family_draws[repeat], axis=2).mean(axis=2)
        risks = np.take(by_person, person_draws[repeat], axis=1).mean(axis=1)
        samples[repeat] = _metrics(risks, np)
    need(np.isfinite(samples).all(), "Complete finite conditional resampling required")
    bounds = np.quantile(samples, [0.025, 0.975], axis=0, method="linear")
    return {
        "interpretation": "Descriptive conditional stability only, conditional on the captured fitted crossvalidated predictions; no retraining uncertainty, coverage guarantee, population confidence or confirmatory winner inference",
        "algorithm": "NumPy Generator(PCG64(80080)); each iteration draws six person indices then F family indices independently with replacement; identical draws for every arm and contrast; linear empirical percentiles",
        "iterations": RESAMPLES, "seed": RESAMPLE_SEED,
        "person_draws": writer.array("stability-person-draws.npy", person_draws),
        "family_draws": writer.array("stability-family-draws.npy", family_draws),
        "metric_samples": writer.array("stability-metric-samples.npy", samples),
        "pointwise_2_5_97_5_percentiles": {
            label: [float(bounds[0, index]), float(bounds[1, index])]
            for index, label in enumerate(METRIC_LABELS)},
    }


def compare(plan, captured_panel, private_pool_root, private_pool_manifest, output, owner):
    """Run the full protected comparison; no target input is opened early.

    All scientific libraries are lazy. The caller must separately provide actual
    source/runtime/isolation eligibility; metadata and this logical I/O Owner do
    not confer it. A failed coordinate/fit/array refuses the complete comparison.
    """
    from input_owner import Writer
    record = owner.begin("complete_protected_generalization_comparison")
    answer = None
    try:
        validate_family_plan(plan)
        # This function, rather than a caller-created type/flag, performs the
        # entire ordered admission immediately before the target opening below.
        admitted = admit_panel(plan, captured_panel, owner)
        descriptor(private_pool_manifest, 4 * 1024 * 1024)
        need(admitted.document["target_manifest_identity"] == private_pool_manifest,
             "Protected pool identity must equal the pool bound before prediction capture")
        pool, target_contract, targets = _pool(private_pool_root, private_pool_manifest, owner)
        import numpy as np
        from .models import family_weights, fit_target_scale, array_identity
        writer = Writer(output, owner)
        label_count, family_count = len(SCORE_LABELS), len(plan.components)
        owner.reserve("retained_bytes", label_count * len(PERSONS) * len(VIDEO_IDS) * 8 +
                      label_count * len(PERSONS) * math.prod(TARGET_SHAPE) * 8)
        losses = np.empty((label_count, len(PERSONS), len(VIDEO_IDS)), dtype=np.float64)
        curves = np.zeros((label_count, len(PERSONS), *TARGET_SHAPE), dtype=np.float64)
        seen = set()
        family_by_video = {video: component for component in plan.components for video in component.video_ids}
        cases = outer_cases(plan)
        completion = []
        comparison_cells = []
        for case in cases:
            coordinates = tuple(case.training_coordinates())
            fit_ids = np.asarray(case.training_video_ids, dtype=np.int64) - 1
            train_count = len(coordinates)
            owner.reserve("retained_bytes", train_count * math.prod(TARGET_SHAPE) * 8 * 3)
            raw_targets = np.concatenate([
                np.asarray(targets[person][fit_ids], dtype=np.float64)
                for person in case.training_persons], axis=0).reshape(train_count, -1)
            need(array_identity(raw_targets.reshape(train_count, *TARGET_SHAPE)) ==
                 admitted.fit_supports[case.case_id]["target_values_identity"],
                 "Actual reference TRAIN values must equal private pool values in exact person/video order")
            weights = family_weights(plan, coordinates, owner)
            exact_scale, standardized = fit_target_scale(raw_targets, weights, owner)
            mean = read_operand(admitted, case.case_id, "scale:mean", owner)
            sigma = read_operand(admitted, case.case_id, "scale:sigma", owner)
            need(np.array_equal(exact_scale.mean.reshape(TARGET_SHAPE), mean) and
                 np.array_equal(exact_scale.sigma.reshape(TARGET_SHAPE), sigma),
                 "Captured mean/sigma must equal the exact selected outer TRAIN-only transform")
            del standardized, raw_targets, weights, exact_scale
            person_index = PERSONS.index(case.query_person)
            query_ids = np.asarray(case.query_video_ids, dtype=np.int64) - 1
            owner.reserve("retained_bytes", len(query_ids) * math.prod(TARGET_SHAPE) * 8 * 4 +
                          len(query_ids) * 8)
            query = np.asarray(targets[case.query_person][query_ids], dtype=np.float64)
            for video_id in case.query_video_ids:
                key = case.query_person, video_id
                need(key not in seen, "No repeated protected person/video coordinate")
                seen.add(key)
            reduction = np.asarray([1.0 / (family_count * len(family_by_video[video].video_ids))
                                    for video in case.query_video_ids], dtype=np.float64)
            for label_index, label in enumerate(SCORE_LABELS):
                prediction = read_operand(admitted, case.case_id, label, owner)
                # Both operands are ORIGINAL EEG units. This is the only target
                # scale division in the score. The fitted mean is not subtracted
                # separately: it already belongs in each raw-unit prediction.
                residual = (query - prediction) / sigma[None, :, :]
                squared = residual * residual
                need(np.isfinite(squared).all(), "Overflow/nonfinite loss refuses the whole case")
                row_losses = squared.mean(axis=(1, 2))
                losses[label_index, person_index, query_ids] = row_losses
                curves[label_index, person_index] += np.tensordot(reduction, squared, axes=(0, 0))
            case_components = tuple(component for component in plan.components
                                    if component.fold == case.query_fold)
            case_risks = np.stack([
                losses[:, person_index, np.asarray(component.video_ids, dtype=np.int64) - 1].mean(axis=1)
                for component in case_components], axis=1).mean(axis=1)
            fixed_full_risk = float(case_risks[SCORE_LABELS.index("reference:full")])
            for (mode, regime), key in zip(CANDIDATE_CELLS, CANDIDATE_KEYS):
                candidate_risk = float(case_risks[SCORE_LABELS.index("candidate:" + key)])
                comparison_cells.append({"case_id": case.case_id, "access_mode": mode,
                    "tool_regime": regime, "candidate_role": "candidate:" + key,
                    "fixed_full_risk": fixed_full_risk, "candidate_full_risk": candidate_risk,
                    "improvement": fixed_full_risk - candidate_risk,
                    "captured_prediction": admitted.rows[(case.case_id, "candidate:" + key)]["captured"],
                    "scope": "Per-case descriptive reduction; the primary pools all families with their selected equal-family weights"})
            # These sixty cells alias the thirty already captured fixed-FULL
            # outputs. They are not additional candidate runs, captures or fits.
            for mode in MODES:
                comparison_cells.append({"case_id": case.case_id, "access_mode": mode,
                    "tool_regime": "decoder_only_shared_reference", "candidate_role": "reference:full",
                    "fixed_full_risk": fixed_full_risk, "candidate_full_risk": fixed_full_risk,
                    "improvement": 0.0,
                    "captured_prediction": admitted.rows[(case.case_id, "reference:full")]["captured"],
                    "scope": "Alias of the one shared fixed-FULL decoder bank; not an extra prediction capture"})
            completion.append({"case_id": case.case_id, "state": "complete",
                               "query_person": case.query_person,
                               "query_video_ids": list(case.query_video_ids),
                               "query_video_count": len(case.query_video_ids),
                               "full_channel_count": 127, "full_bin_count": 150,
                               "prediction_roles": list(SCORE_LABELS),
                               "outer_train_values_and_row_pairing_recomputed_and_equal": True,
                               "outer_train_scale_recomputed_and_equal": True,
                               "scorer_residual_sigma_divisions": 1})
        need(seen == {(person, video) for person in PERSONS for video in VIDEO_IDS} and
             len(completion) == 30 and np.isfinite(losses).all() and np.isfinite(curves).all(),
             "Complete six-person/all-video/full-coordinate loss panel required")
        owner.reserve("retained_bytes", label_count * len(PERSONS) * family_count * 8)
        family_risks = np.stack([
            losses[:, :, np.asarray(component.video_ids, dtype=np.int64) - 1].mean(axis=2)
            for component in plan.components], axis=2)
        person_risks = family_risks.mean(axis=2)
        overall_risks = person_risks.mean(axis=1)
        overall = _metrics(overall_risks, np)
        person_metrics = np.stack([_metrics(person_risks[:, index], np)
                                   for index in range(len(PERSONS))], axis=1)
        need(np.isfinite(overall).all() and np.isfinite(person_metrics).all(),
             "Every primary and secondary estimand must be finite")
        stability = _stability(family_risks, writer, owner, np)
        leave_one = {}
        for index, person in enumerate(PERSONS):
            remaining = tuple(other for other in range(len(PERSONS)) if other != index)
            leave_one[person] = _mapping(_metrics(person_risks[:, remaining].mean(axis=1), np))
        arrays = {
            "video_losses": writer.array("complete-video-losses.npy", losses),
            "family_risks": writer.array("complete-family-risks.npy", family_risks),
            "person_metrics": writer.array("complete-person-metrics.npy", person_metrics),
            "person_channel_time_risks": writer.array("complete-person-channel-time-risks.npy", curves),
            "mean_channel_time_risks": writer.array("mean-channel-time-risks.npy", curves.mean(axis=1)),
        }
        result = {
            "schema": "neural080_protected_generalization_comparison_v1",
            "assignment_sha256": plan.assignment_sha256,
            "feature_backend": admitted.reference["cases"][0]["feature_backend"],
            "prediction_archive": dict(captured_panel.manifest),
            "private_pool_manifest": dict(private_pool_manifest),
            "target_contract": pool["target_contract"],
            "units": {"predictions_and_targets": "original_eeg", "actual_eeg_units": target_contract["eeg_units"],
                      "reference": target_contract["eeg_reference"], "risk": "dimensionless squared error",
                      "residual_scale": "exact outer TRAIN sigma", "sigma_divisions": 1},
            "risk_formula": "mean_person mean_genuine_family mean_video_in_family mean_127channels_150bins ((Y_original-pred_original)/sigma_outerTRAIN)^2; all five held-family folds pooled by actual families",
            "risk_labels": list(SCORE_LABELS), "metric_labels": list(METRIC_LABELS),
            "persons": list(PERSONS), "video_ids": list(VIDEO_IDS),
            "families": [{"component_sha256": component.component_sha256,
                          "video_ids": list(component.video_ids), "fold": component.fold}
                         for component in plan.components],
            "support": {"persons": 6, "videos_per_person": 1102, "person_video_pairs": 6612,
                        "genuine_families": family_count, "outer_cases": 30,
                        "reference_arms": 7, "candidate_access_modes": 2, "candidate_tool_regimes": 2,
                        "reference_prediction_captures": 210, "candidate_prediction_captures": 120,
                        "scale_captures": 60, "shared_decoder_only_bank_captures": 30,
                        "comparison_cells_including_shared_decoder_aliases": 180,
                        "channels": 127, "bins": 150, "retained_joined_trials": 45144},
            "overall": _mapping(overall),
            "per_person": {person: _mapping(person_metrics[:, index])
                           for index, person in enumerate(PERSONS)},
            "fixed_leave_one_person_out_reductions": leave_one,
            "prespecified_sub03_exclusion_sensitivity": leave_one["sub-03"],
            "descriptive_stability": stability, "arrays": arrays,
            "complete_case_dispositions": completion, "comparison_cells": comparison_cells,
            "candidate_cell_policy": "Report all four access-mode/tool-regime improvement estimands separately; no best-cell winner selection or pooled substitute",
            "failure_policy": "Any missing fit, target coordinate, prediction, positive TRAIN variance or finite loss makes the complete comparison unavailable; no best-success subset or dropped sensor/time coordinate",
            "preprocessing_profile": PROFILE,
            "interpretation_limits": [
                "Exposed public six-person crossvalidation is developmental, never a freshly sealed improvement test",
                "Whole-record artifact/ICA preprocessing dependencies remain disclosed; downstream TRAIN-only scaling does not erase them",
                "The scientific dynamic contrast always uses the fixed competent reference nuisance_eye and full arms; candidate improvement compares candidate FULL with the same fixed FULL reference",
                "Every signed/null/negative estimand is retained; no channel/time/noise-ceiling selection",
                "Conditional stability excludes refitting variability and is not population confidence, a causal or pure-visual estimate, clinical evidence or a SOTA/winner claim",
                "Actual source rights, provenance/clock compatibility, checkpoint exposure, reference competence and execution isolation/resource qualification require independent evidence",
            ],
            "resource_accounting": "Accepted logical Owner records complete admission, target and archive recaptures, full scale recomputation, array temporaries and output serialization; native CPU/memory/physical I/O qualification is separate",
        }
        manifest = writer.document("PROTECTED_COMPARISON.json", result)
        answer = {"manifest": manifest, "comparison": result, "output": str(writer.root)}
    except BaseException as exc:
        owner.failure(record, exc)
    owner.complete(record)
    return answer
