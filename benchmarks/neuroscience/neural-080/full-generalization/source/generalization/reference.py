"""Complete prospective fixed reference; no scientific execution is implied.

Each outer case receives only its permitted TRAIN EEG and scoped feature rows.
Every one of 39,150 ridge fits is actual computation when this source is run.
Discarded fits retain exact state/output identities and loss bodies, not their
whole coefficient/prediction bodies. Hashes are not retained-body proof.
"""
from __future__ import annotations

import time

from . import models
from .splits import outer_cases, validate_family_plan, validate_outer_case


def _plain(value):
    from collections.abc import Mapping
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _resources(owner):
    return {key: int(value) for key, value in owner.used.items()}


def _resource_difference(before, after):
    return {key: after[key] - before[key] for key in before}


def _clock():
    return {"monotonic_ns": time.perf_counter_ns(), "process_cpu_ns": time.process_time_ns()}


def _elapsed(start):
    end = _clock()
    return {key: end[key] - start[key] for key in start}


def _observe_cost(owner, started, logical_before):
    ended = _clock()
    logical_after = _resources(owner)
    cost = {"monotonic_ns": ended["monotonic_ns"] - started["monotonic_ns"],
            "process_cpu_ns": ended["process_cpu_ns"] - started["process_cpu_ns"],
            "logical_delta": _resource_difference(logical_before, logical_after)}
    models.need(all(type(cost[key]) is int and cost[key] >= 0
                    for key in ("monotonic_ns", "process_cpu_ns")) and
                all(type(value) is int and value >= 0 for value in cost["logical_delta"].values()),
                "Monotonic actual resource observations required")
    return {"started": dict(started), "ended": ended,
            "logical_before": dict(logical_before), "logical_after": logical_after, "cost": cost}


def _exclude(intervals, label, owner, started, logical_before):
    intervals.append({"label": label, **_observe_cost(owner, started, logical_before)})


def _full_cost_document(plan, case, backend, owner, started, before, intervals, components):
    gross = _observe_cost(owner, started, before)
    expected = {f"inner-{index}:{arm}" for index in range(20)
                for arm in models.ARMS if arm != "full"}
    expected |= {"selection:" + arm for arm in models.ARMS if arm != "full"}
    expected |= {"outer:" + arm for arm in models.ARMS if arm != "full"}
    expected |= {"training_mean", "full_reverse"}
    labels = [row["label"] for row in intervals]
    models.need(len(intervals) == 90 and len(set(labels)) == 90 and set(labels) == expected,
                "Exactly all disjoint non-FULL computations must be observed")
    previous_clock, previous_logical = gross["started"], gross["logical_before"]
    for row in intervals:
        models.need(all(previous_clock[key] <= row["started"][key] <= row["ended"][key] <= gross["ended"][key]
                        for key in ("monotonic_ns", "process_cpu_ns")) and
                    all(previous_logical[key] <= row["logical_before"][key] <= row["logical_after"][key] <= gross["logical_after"][key]
                        for key in before), "Nonoverlapping observed exclusion intervals")
        previous_clock, previous_logical = row["ended"], row["logical_after"]
    excluded = {
        "monotonic_ns": sum(row["cost"]["monotonic_ns"] for row in intervals),
        "process_cpu_ns": sum(row["cost"]["process_cpu_ns"] for row in intervals),
        "logical_delta": {key: sum(row["cost"]["logical_delta"][key] for row in intervals) for key in before},
    }
    remainder = {
        "monotonic_ns": gross["cost"]["monotonic_ns"] - excluded["monotonic_ns"],
        "process_cpu_ns": gross["cost"]["process_cpu_ns"] - excluded["process_cpu_ns"],
        "logical_delta": {key: gross["cost"]["logical_delta"][key] - excluded["logical_delta"][key] for key in before},
    }
    models.need(remainder["monotonic_ns"] > 0 and remainder["process_cpu_ns"] > 0 and
                all(value >= 0 for value in remainder["logical_delta"].values()),
                "Missing, zero, negative or infeasible FULL construction observation")
    return {
        "schema": "neural080_full_arm_cost_v1", "case_id": case.case_id,
        "assignment_sha256": plan.assignment_sha256, "feature_backend": backend,
        "actual_full_ridge_fits": 261, "gross_prefix_cost": gross["cost"],
        "excluded_cost": excluded, "cost": remainder, "components": components,
        "exclusion_intervals": intervals,
        "debit_rule": "complete_run_outer_observation_minus_excluded_cost",
        "receipt_tail": "Worker measures the complete call; receipt/case-summary tail is charged to FULL, not assumed zero.",
        "residual_allocation": "All observed work outside the 90 excluded intervals is allocated once to FULL.",
        "native_aggregate_cost": "Process clocks and logical counters do not establish whole-job native cost; independent aggregate qualification remains required.",
    }


def _preparation_identity(preparation):
    return {name: models.array_identity(getattr(preparation, name))
            for name in ("weighted_design", "design_mean", "target_mean", "weighted_targets", "gram")}


def _validation_families(plan, case, coordinates, losses):
    """Equal genuine families and persons across twenty cells, not equal folds."""
    models.need(len(coordinates) == len(losses), "Complete validation loss support")
    family_of = {video: component.component_sha256
                 for component in plan.components for video in component.video_ids}
    outer_families = {family_of[video] for video in case.training_video_ids}
    groups = {}
    for (person, video), loss in zip(coordinates, losses):
        groups.setdefault((person, family_of[video]), []).append(float(loss))
    rows, contribution = [], 0.0
    for (person, family), values in sorted(groups.items()):
        mean = sum(values) / len(values)
        contribution += mean / (len(case.training_persons) * len(outer_families))
        rows.append({"person": person, "family_sha256": family,
                     "video_count": len(values), "mean_video_loss": mean})
    return rows, contribution


def _check_selection_support(plan, case, records):
    family_of = {video: component.component_sha256
                 for component in plan.components for video in component.video_ids}
    expected = {(person, family_of[video]) for person in case.training_persons
                for video in case.training_video_ids}
    models.need(len(records) == 20 * 13, "All twenty cells and thirteen alpha fits required")
    for alpha in models.ALPHAS:
        selected = [record for record in records if record["alpha"] == alpha]
        models.need(len(selected) == 20 and {r["inner_index"] for r in selected} == set(range(20)),
                    "Every alpha requires all twenty actual validation cells")
        actual = [(row["person"], row["family_sha256"])
                  for record in selected for row in record["family_losses"]]
        models.need(len(actual) == len(set(actual)) and set(actual) == expected,
                    "Every inner person/family must appear exactly once per alpha")


def run_outer(plan, case, training_targets, feature_pool, owner, writer):
    """Return a complete captured case; every prediction is ORIGINAL EEG units.

    training_targets is an immutable snapshot of EXACT case.training_coordinates.
    feature_pool has EXACT outer TRAIN+QUERY personal rows and no EEG. Query EEG
    is not an operand. A partial output is never returned as an available case.
    """
    started, before = _clock(), _resources(owner)
    rec = owner.begin("fixed_reference_outer:" + case.case_id)
    result = None
    exclusions = []
    try:
        import numpy as np
        validate_outer_case(plan, case)
        models.need(writer.owner is owner, "One explicit resource owner")
        models.check_feature_pool(feature_pool)
        train_coords = tuple(case.training_coordinates())
        query_coords = tuple(case.query_coordinates())
        models.need(feature_pool.personal_coordinates == train_coords + query_coords,
                    "Outer worker receives only exact ordered TRAIN+QUERY personal features")
        models.need(type(training_targets) is models.TrainingTargets and
                    training_targets.coordinates == train_coords, "Exact outer FIT-only targets")
        raw_outer = models.target_rows(training_targets, train_coords, owner)
        outer_weights = models.family_weights(plan, train_coords, owner)
        outer_scale, z_outer = models.fit_target_scale(raw_outer, outer_weights, owner)
        prefix = case.case_id
        fit_support = writer.document(prefix + ".fit_support.json", {
            "assignment_sha256": plan.assignment_sha256, "coordinates": _plain(train_coords),
            "query_coordinates": _plain(query_coords),
            "target_values_identity": _plain(training_targets.identity),
            "feature_values_identity": _plain(feature_pool.identities),
            "weighting": "equal_person_then_genuine_family_then_video",
            "weights": writer.array(prefix + ".fit_weights.npy", outer_weights),
            "original_preprocessing": "Recording-level artifact/ICA processing separately disclosed; only these readout transformations are fitted on TRAIN."
        })
        scale_descriptor = models.capture_target_scale(outer_scale, writer, prefix)
        initial_observation = _observe_cost(owner, started, before)
        full_budget = {
            "outer_initial": initial_observation["cost"]["logical_delta"],
            "outer_initial_duration": {key: initial_observation["cost"][key]
                                       for key in ("monotonic_ns", "process_cpu_ns")},
            "inner": [],
            "attribution_basis": "Diagnostic component observations only; authoritative debit is the complete run_outer observation minus excluded_cost.",
        }
        records = {arm: [] for arm in models.ARMS}
        scores = {arm: [0.0] * 13 for arm in models.ARMS}
        fit_count, inner_preprocessing = 0, []
        for inner_index, cell in enumerate(case.inner_cells):
            cell_rec = owner.begin(prefix + ".inner:" + str(inner_index))
            cell_started, cell_before = _clock(), _resources(owner)
            try:
                fit_coords = tuple(cell.fit_coordinates())
                valid_coords = tuple(cell.validation_coordinates())
                raw_fit = models.target_rows(training_targets, fit_coords, owner)
                raw_valid = models.target_rows(training_targets, valid_coords, owner)
                weights = models.family_weights(plan, fit_coords, owner)
                scale, z_fit = models.fit_target_scale(raw_fit, weights, owner)
                cell_prefix = prefix + ".i" + str(inner_index).zfill(2)
                transforms = models.fit_transforms(feature_pool, fit_coords, owner, writer=writer, prefix=cell_prefix)
                inner_state = {
                    "inner_index": inner_index, "fit_coordinates": _plain(fit_coords),
                    "validation_coordinates": _plain(valid_coords),
                    "fit_targets_identity": models.array_identity(raw_fit),
                    "validation_targets_identity": models.array_identity(raw_valid),
                    "weights": writer.array(cell_prefix + ".weights.npy", weights),
                    "target_scale": models.capture_target_scale(scale, writer, cell_prefix),
                    "transforms": models.capture_transforms(transforms, writer, cell_prefix),
                }
                state_descriptor = writer.document(cell_prefix + ".preprocessing.json", inner_state)
                inner_preprocessing.append(state_descriptor)
                shared_cell_cost = _resource_difference(cell_before, _resources(owner))
                shared_cell_duration = _elapsed(cell_started)
                for arm in models.ARMS:
                    arm_before, arm_started = _resources(owner), _clock()
                    fit_design = models.design(feature_pool, transforms, arm, fit_coords, owner)
                    valid_design = models.design(feature_pool, transforms, arm, valid_coords, owner)
                    preparation = models.prepare_ridge(fit_design, z_fit, weights, scale, owner)
                    prep_descriptor = writer.document(cell_prefix + "." + arm + ".preparation_identity.json", {
                        "numeric_identity": _preparation_identity(preparation),
                        "preprocessing": state_descriptor, "arm": arm, "blocks": list(models.ARMS[arm]),
                        "retention": "Actual numeric identity; discarded preparation bodies not retained."
                    })
                    for alpha_index, alpha in enumerate(models.ALPHAS):
                        fit_started, fit_before = _clock(), _resources(owner)
                        owner.reserve("retained_bytes", 32768)
                        model = models.fit_ridge(preparation, alpha, owner)
                        fit_count += 1
                        prediction = models.predict_original(model, valid_design, owner)
                        losses = models.video_losses(prediction, raw_valid, scale, owner)
                        family_losses, contribution = _validation_families(plan, case, valid_coords, losses)
                        models.need(np.isfinite(contribution), "Finite complete inner family risk")
                        scores[arm][alpha_index] += contribution
                        fit_prefix = cell_prefix + "." + arm + ".a" + str(alpha_index).zfill(2)
                        record = {
                            "inner_index": inner_index, "alpha_index": alpha_index, "alpha": alpha,
                            "arm": arm, "state": "fit_and_validation_completed",
                            "preparation": prep_descriptor, "solver": "numpy.linalg.solve",
                            "dual_identity": models.array_identity(model.dual),
                            "prediction_units": "original_eeg",
                            "prediction_identity": models.array_identity(prediction),
                            "prediction_retention": "Exact actual identity only; discarded prediction body not retained.",
                            "video_losses": writer.array(fit_prefix + ".video_losses.npy", losses),
                            "family_losses": family_losses, "selection_contribution": contribution,
                            "resource_before": fit_before, "resource_after": _resources(owner),
                            "observed_duration": _elapsed(fit_started),
                        }
                        # Capture each completed attempt immediately. A later
                        # failure cannot erase prior fit observations.
                        record_descriptor = writer.document(fit_prefix + ".fit.json", record)
                        record["record_body"] = record_descriptor
                        records[arm].append(record)
                        del model, prediction, losses
                    if arm == "full":
                        full_budget["inner"].append({
                            "inner_index": inner_index, "shared_preprocessing": shared_cell_cost,
                            "shared_preprocessing_duration": shared_cell_duration,
                            "full_arm": _resource_difference(arm_before, _resources(owner)),
                            "full_arm_duration": _elapsed(arm_started), "actual_fits": 13})
                    del preparation, fit_design, valid_design
                    if arm != "full":
                        _exclude(exclusions, f"inner-{inner_index}:{arm}", owner, arm_started, arm_before)
                writer.document(cell_prefix + ".completion.json", {
                    "preprocessing": state_descriptor, "actual_ridge_fits": 65,
                    "resource_before": cell_before, "resource_after": _resources(owner),
                    "observed_duration": _elapsed(cell_started)
                })
                del raw_fit, raw_valid, z_fit, transforms
            except BaseException as exc:
                owner.failure(cell_rec, exc)
            owner.complete(cell_rec)
        models.need(fit_count == 1300, "All 1300 inner fits complete before selection")
        selected = {}
        for arm in models.ARMS:
            selection_started, selection_before = _clock(), _resources(owner)
            _check_selection_support(plan, case, records[arm])
            risks = scores[arm]
            models.need(len(risks) == 13 and np.isfinite(risks).all(), "No failed/missing alpha may be dropped")
            best = min(range(13), key=lambda index: (risks[index], -models.ALPHAS[index]))
            selected[arm] = {"alpha": models.ALPHAS[best], "risk": float(risks[best]), "alpha_index": best}
            if arm != "full":
                _exclude(exclusions, "selection:" + arm, owner, selection_started, selection_before)
        # Fresh full-outer transforms, fitted after complete inner selection.
        outer_common_before, outer_common_started = _resources(owner), _clock()
        transforms = models.fit_transforms(feature_pool, train_coords, owner, writer=writer, prefix=prefix + ".outer")
        transform_state = models.capture_transforms(transforms, writer, prefix + ".outer")
        preprocessing = writer.document(prefix + ".preprocessing.json", {
            "fit_support": fit_support, "target_scale": scale_descriptor,
            "transforms": transform_state,
            "inner_preprocessing": inner_preprocessing,
            "same_transform_state_for_all_arms": True, "query_fitted_parameters": [],
        })
        full_budget["outer_transforms"] = _resource_difference(outer_common_before, _resources(owner))
        full_budget["outer_transforms_duration"] = _elapsed(outer_common_started)
        mean_started, mean_before = _clock(), _resources(owner)
        models.reserve_array(owner, (len(query_coords), *models.TARGET_SHAPE))
        mean_prediction = np.broadcast_to(outer_scale.mean.reshape(1, *models.TARGET_SHAPE),
                                          (len(query_coords), *models.TARGET_SHAPE)).copy()
        predictions = {"training_mean": writer.array(prefix + ".training_mean.prediction.npy", mean_prediction)}
        del mean_prediction
        _exclude(exclusions, "training_mean", owner, mean_started, mean_before)
        final_models, selection = {}, {}
        for arm in models.ARMS:
            fit_started, fit_before = _clock(), _resources(owner)
            fit_design = models.design(feature_pool, transforms, arm, train_coords, owner)
            query_design = models.design(feature_pool, transforms, arm, query_coords, owner)
            preparation = models.prepare_ridge(fit_design, z_outer, outer_weights, outer_scale, owner)
            model = models.fit_ridge(preparation, selected[arm]["alpha"], owner)
            fit_count += 1
            arm_prefix = prefix + ".outer." + arm
            saved_prep = models.capture_preparation(preparation, writer, arm_prefix)
            prediction = models.predict_original(model, query_design, owner)
            predictions[arm] = writer.array(prefix + "." + arm + ".prediction.npy", prediction)
            final_state = models.capture_model(model, writer, arm_prefix, saved_prep)
            final_state.update({"preprocessing": preprocessing, "fit_support": fit_support,
                                "target_scale": scale_descriptor, "groups": list(models.ARMS[arm])})
            if arm == "full":
                final_state["decoder"] = models.capture_decoder(
                    model, transform_state, scale_descriptor, saved_prep, plan, case, writer, arm_prefix)
            final_models[arm] = writer.document(arm_prefix + ".model.json", final_state)
            final_record = {
                "state": "full_outer_refit_and_prediction_completed", "arm": arm,
                "alpha": selected[arm]["alpha"], "model": final_models[arm], "prediction": predictions[arm],
                "resource_before": fit_before, "resource_after": _resources(owner),
                "observed_duration": _elapsed(fit_started),
            }
            if arm == "full":
                full_budget["final_full"] = _resource_difference(fit_before, _resources(owner))
                full_budget["final_full_duration"] = _elapsed(fit_started)
                full_budget["actual_ridge_fits"] = 261
                full_budget["scope"] = "All shared TRAIN preprocessing plus FULL-only fits; excludes other four arms and query reversal. In-call feature regeneration is included; staging and pre-call feature preparation are measured separately. Native aggregate qualification remains required."
                # Exactly the same model/transforms/alpha/nuisance features.
                reverse_started, reverse_before = _clock(), _resources(owner)
                reverse_design = models.design(feature_pool, transforms, "full", query_coords, owner, reverse=True)
                reverse_prediction = models.predict_original(model, reverse_design, owner)
                predictions["full_reverse"] = writer.array(prefix + ".full_reverse.prediction.npy", reverse_prediction)
                final_record["same_model_reverse_prediction"] = predictions["full_reverse"]
                final_record["reverse_resource_after"] = _resources(owner)
                del reverse_design, reverse_prediction
                _exclude(exclusions, "full_reverse", owner, reverse_started, reverse_before)
            ledger = writer.document(prefix + "." + arm + ".fit_ledger.json", {
                "case_id": case.case_id, "arm": arm, "assignment_sha256": plan.assignment_sha256,
                "alpha_grid": list(models.ALPHAS), "alpha_risks": scores[arm],
                "selected": selected[arm], "inner_fits": records[arm], "final_refit": final_record,
                "actual_ridge_fit_count": 261,
                "full_arm_resource_observations": full_budget if arm == "full" else None,
                "discarded_retention": "Complete support, preprocessing states, actual solver/output identities and losses; discarded coefficient/prediction bodies not retained."
            })
            selection[arm] = {"alpha": selected[arm]["alpha"], "risk": selected[arm]["risk"], "ledger": ledger}
            del preparation, model, prediction, fit_design, query_design
            if arm != "full":
                _exclude(exclusions, "outer:" + arm, owner, fit_started, fit_before)
        models.need(fit_count == 1305 and set(predictions) == set(models.ALL_ARMS),
                    "All actual fits and seven arms required for available outer case")
        backend = "streamed_dual_certified" if type(feature_pool) is models.StreamFeaturePool else "full_svd_materialized"
        cost_document = _full_cost_document(plan, case, backend, owner, started, before, exclusions, full_budget)
        full_arm_cost = writer.document(prefix + ".FULL_ARM_COST.json", cost_document)
        result = {
            "schema": "neural080_reference_case_v1", "case_id": case.case_id,
            "assignment_sha256": plan.assignment_sha256, "units": "original_eeg",
            "feature_backend": "streamed_dual_certified" if type(feature_pool) is models.StreamFeaturePool else "full_svd_materialized",
            "query_coordinates": _plain(query_coords),
            "predictions": {arm: predictions[arm] for arm in models.ALL_ARMS},
            "target_scale": scale_descriptor, "selection": selection, "actual_ridge_fit_count": fit_count,
            "fit_support": fit_support, "preprocessing": preprocessing, "final_models": final_models,
            "full_arm_cost": full_arm_cost,
            "resource_before": before, "resource_after": _resources(owner),
            "observed_duration": _elapsed(started),
            "resource_scope": "Cumulative logical charges and observed clocks; native resource/isolation qualification remains required."
        }
        writer.document(prefix + ".reference.json", result)
    except BaseException as exc:
        owner.failure(rec, exc)
    owner.complete(rec)
    return result


def run_panel(plan, operands_by_case, feature_pool, owner, writer, *, target_manifest_identity):
    """Operator-only complete controller, with no target-provider callback.

    Each call to run_outer receives a separately scoped feature snapshot and the
    corresponding FIT-only targets. Fitted state is never shared across cases.
    Candidate workers must not receive this operator-private operands mapping.
    """
    rec = owner.begin("fixed_reference_complete_panel")
    result = None
    try:
        validate_family_plan(plan)
        identity = _manifest_identity(target_manifest_identity)
        cases = outer_cases(plan)
        models.need(type(feature_pool) is models.FeaturePool,
                    "In-process panel helper is materialized-only; streamed campaigns use isolated case workers")
        models.need(type(operands_by_case) is dict and
                    set(operands_by_case) == {case.case_id for case in cases}, "All thirty exact outer operands")
        for case in cases:
            operand = operands_by_case[case.case_id]
            models.need(type(operand) is models.TrainingTargets and
                        operand.coordinates == tuple(case.training_coordinates()), "Each operand is exact FIT-only support")
        documents = []
        for case in cases:
            owner.reserve("retained_bytes", 65536)
            scoped = models.restrict_case_features(feature_pool, plan, case, owner)
            documents.append(run_outer(plan, case, operands_by_case[case.case_id], scoped, owner, writer))
            del scoped
        actual = sum(row["actual_ridge_fit_count"] for row in documents)
        models.need(len(documents) == 30 and actual == 39150, "Complete actual fit campaign required")
        result = {
            "schema": "neural080_reference_panel_v1", "assignment_sha256": plan.assignment_sha256,
            "target_manifest_identity": identity,
            "units": "original_eeg", "arms": list(models.ALL_ARMS), "cases": documents,
            "actual_ridge_fit_count": actual,
            "historical_scope": "Developmental public crossvalidation; no freshness or competence claim."
        }
        writer.document("REFERENCE_PANEL.json", result)
    except BaseException as exc:
        owner.failure(rec, exc)
    owner.complete(rec)
    return result


def _manifest_identity(value):
    """Exact existing private manifest descriptor, not a read or authority token."""
    from pathlib import PurePosixPath
    models.need(type(value) is dict and set(value) == {"path", "bytes", "sha256"},
                "Closed private target-manifest identity")
    path = value["path"]
    models.need(type(path) is str and bool(path) and "\\" not in path and
                not PurePosixPath(path).is_absolute() and
                all(part not in ("", ".", "..") for part in path.split("/")),
                "Canonical relative target-manifest identity path")
    models.need(type(value["bytes"]) is int and 0 < value["bytes"] < 2**63 and
                type(value["sha256"]) is str and len(value["sha256"]) == 64 and
                all(char in "0123456789abcdef" for char in value["sha256"]),
                "Exact target-manifest observed extent and SHA-256")
    return dict(value)


def output_names(case, *, backend, max_members, column_width=None):
    """Finite exact worker output basenames, including caller CASE_REFERENCE.json.

    This enumerates every successful run_outer artifact before process launch.
    Failure may leave a proper subset; a subset never qualifies as a full case.
    """
    from .splits import OuterCase, PERSONS, FOLDS
    models.need(type(case) is OuterCase and case.query_person in PERSONS and
                type(case.query_fold) is int and case.query_fold in FOLDS and
                case.case_id == f"{case.query_person}.family-{case.query_fold}",
                "Canonical case identity for finite output plan")
    models.need(backend in ("full_svd_materialized", "streamed_dual_certified") and
                type(max_members) is int and 0 < max_members < 2**63, "Explicit backend and output-member capacity")
    stream_passes = 0
    transform_count = 25
    if backend == "streamed_dual_certified":
        from . import dual
        models.need(type(column_width) is int and column_width > 0, "Explicit selected feature column width")
        transform_count = 15 + sum(len(dual.output_names(case.case_id + ".outer." + name + ".dual", name))
                                   for name in models.LEARNED)
        stream_passes = sum((width + column_width - 1) // column_width for width in (15360, 19260, 1))
        stream_passes += 21 * sum(dual.required_stream_passes(name, column_width) for name in models.LEARNED)
    else:
        models.need(column_width is None, "Materialized backend has no hidden stream width")
    required_count = 21 * transform_count + 2857 + stream_passes
    models.need(required_count <= max_members, "Exact successful output roster exceeds selected metadata capacity")
    names = []

    def transforms(prefix):
        for name in models.BLOCKS:
            base = prefix + "." + name
            if backend == "streamed_dual_certified" and name in models.LEARNED:
                names.extend(dual.output_names(base + ".dual", name))
                continue
            names.extend(base + "." + suffix + ".npy" for suffix in ("mean", "scale", "constant"))
            if name in models.LEARNED:
                names.extend(base + "." + suffix + ".npy" for suffix in ("pca_mean", "pca_components"))

    def scale(prefix):
        names.extend((prefix + ".target_mean.npy", prefix + ".target_sigma.npy"))

    prefix = case.case_id
    names.extend((prefix + ".fit_support.json", prefix + ".fit_weights.npy"))
    scale(prefix)
    for inner_index in range(20):
        cell_prefix = prefix + ".i" + str(inner_index).zfill(2)
        names.extend((cell_prefix + ".weights.npy", cell_prefix + ".preprocessing.json",
                      cell_prefix + ".completion.json"))
        scale(cell_prefix)
        transforms(cell_prefix)
        for arm in models.ARMS:
            names.append(cell_prefix + "." + arm + ".preparation_identity.json")
            for alpha_index in range(13):
                fit_prefix = cell_prefix + "." + arm + ".a" + str(alpha_index).zfill(2)
                names.extend((fit_prefix + ".video_losses.npy", fit_prefix + ".fit.json"))
    transforms(prefix + ".outer")
    names.extend((prefix + ".preprocessing.json", prefix + ".training_mean.prediction.npy"))
    for arm in models.ARMS:
        arm_prefix = prefix + ".outer." + arm
        names.extend(arm_prefix + "." + key + ".npy"
                     for key in ("weighted_design", "design_mean", "target_mean",
                                 "weighted_targets", "gram", "dual"))
        names.extend((arm_prefix + ".model.json", prefix + "." + arm + ".prediction.npy",
                      prefix + "." + arm + ".fit_ledger.json"))
    names.extend((prefix + ".outer.full.FULL_DECODER.json", prefix + ".outer.full.decoder_dual.npy",
                  prefix + ".FULL_ARM_COST.json"))
    names.extend((prefix + ".full_reverse.prediction.npy", prefix + ".reference.json",
                  "CASE_REFERENCE.json"))
    names.extend("feature-pass-" + str(index).zfill(6) + ".json" for index in range(stream_passes))
    models.need(len(names) == required_count and len(names) == len(set(names)), "Exact finite output ownership")
    return tuple(sorted(names))
