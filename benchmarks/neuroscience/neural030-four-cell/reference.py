"""Original public-view reference composition. No private targets or file reads."""
import copy

from baseline import fit_baseline, predict_query
from features import features, training_counts, TRIAL_KEYS
from source_binding import closed, require


def validate_public(public):
    closed(public, ("schema", "cases", "view_scope", "query_target_feedback"), "public_fields")
    require(public["schema"] == "neural030_cerebellar_public_v1", "public_schema")
    require(public["view_scope"] == "retrospective_processed_within_session_calibration"
            and public["query_target_feedback"] is False, "public_scope")
    require(type(public["cases"]) is list and len(public["cases"]) == 16, "complete_public_cases")
    sessions, trial_ids = set(), set()
    conditions = {"one_second_expert": (1., 5), "two_second_novice": (2., 5), "two_second_expert": (2., 6)}
    seen_conditions = {k: 0 for k in conditions}
    for case in public["cases"]:
        closed(case, ("session_id", "condition", "delay_s", "train", "development", "query"), "case_fields")
        sid = case["session_id"]
        require(type(sid) is str and sid and sid not in sessions, "unique_cases")
        sessions.add(sid)
        require(case["condition"] in conditions and case["delay_s"] == conditions[case["condition"]][0], "condition_delay_binding")
        seen_conditions[case["condition"]] += 1
        last_order = 0
        for split in ("train", "development", "query"):
            require(type(case[split]) is list and case[split], "nonempty_public_split")
            for trial in case[split]:
                closed(trial, TRIAL_KEYS if split == "query" else TRIAL_KEYS | {"counts"}, "split_target_visibility")
                tid = trial["trial_id"]
                require(type(tid) is str and tid and tid not in trial_ids, "global_unique_trial_ids")
                trial_ids.add(tid)
                require(trial["session_id"] == sid and trial["delay_s"] == case["delay_s"]
                        and trial["stage"] == case["condition"], "case_trial_binding")
                require(type(trial["trial_order"]) is int and trial["trial_order"] > last_order, "complete_split_order")
                last_order = trial["trial_order"]
    require(all(seen_conditions[k] == v[1] for k, v in conditions.items()), "complete_public_group_5_5_6")
    return public


def predict_reference(public, arm="joint"):
    """Paired context+handle and optional neural ridge, same complete cases.

    The caller receives predictions only. No query label argument exists.
    Normalization/coefficients use training only; development selects alpha.
    This in-memory source API is not a participant sandbox or native runner.
    """
    validate_public(public)
    predictions = []
    for case in public["cases"]:
        xt, it, ft = features(case["train"], arm)
        xd, idv, fd = features(case["development"], arm)
        xq, iq, fq = features(case["query"], arm)
        require(ft == fd == fq, "same_features_across_splits")
        model = fit_baseline(xt, training_counts(case["train"]), xd,
                             training_counts(case["development"]),
                             train_trial_ids=it, dev_trial_ids=idv, feature_names=ft)
        values = predict_query(model, xq, trial_ids=iq, feature_names=fq)
        offset = 0
        for trial in case["query"]:
            n = int(round(trial["delay_s"] / 0.1))
            predictions.append({"trial_id": trial["trial_id"], "counts": values[offset:offset+n].tolist()})
            offset += n
        require(offset == len(values), "prediction_partition_complete")
    return predictions


def query_neural_mismatch(public):
    """Deterministic diagnostic: cyclic query-trial neural reassignment per case.

    Uses no labels. Neural clock and both neural arrays move together. Context,
    handle, trial IDs and expected target membership remain unchanged. This is
    a source-defined negative control, not an exchangeability/significance test.
    No authentic diagnostic is executed during construction.
    """
    validate_public(public)
    result = copy.deepcopy(public)
    for old, new in zip(public["cases"], result["cases"]):
        require(len(old["query"]) >= 2, "mismatch_needs_two_query_trials")
        for i, target in enumerate(new["query"]):
            donor = old["query"][(i + 1) % len(old["query"])]
            for key in ("neural_time", "grc", "cf"):
                target[key] = copy.deepcopy(donor[key])
    return result
