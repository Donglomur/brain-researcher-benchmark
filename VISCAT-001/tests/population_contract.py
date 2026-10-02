"""Both descriptive populations from exact category-count primitives."""
import numpy as np
import category_statistics as stats

POPULATIONS = ("full_data_selected_same_trials", "crossfit_selected_at_least_five_splits")


def full_fields(test):
    row = dict(n_trials=test["n"], tie_sum=test["tie_sum"], full_status=test["status"],
        small_group_warning=test["small_group_warning"], kw_H=test["H"], kw_p=test["p"],
        category_selective=test["selected"], preferred_category=test["preferred"],
        preferred_tied=test["preferred_tied"], n_preferred=test["n_preferred"], n_rest=test["n_rest"],
        u_preferred_twice=test["u_preferred_twice"], same_trial_auc=test["auc"])
    for i, code in enumerate(stats.CATEGORIES):
        for column, field in (("n_cat_", "supports"), ("sum_count_cat_", "sums"),
                              ("mean_rate_cat_", "means"), ("rank_sum_twice_cat_", "rank_sum_twice")):
            row[column+str(code)] = test[field][i]
    return row


def split_fields(key, repeat, test, columns):
    row = {column: None for column in columns}
    row.update(unit_key=key, repeat=repeat, status="insufficient_category_support",
               train_selected=False, included_in_conditional_summary=False)
    if test is None: return row
    row.update(status=test["status"], train_tie_sum=test["tie_sum"],
        train_small_group_warning=test["small_group_warning"], train_H=test["H"], train_p=test["p"],
        train_selected=test["selected"], train_preferred_category=test["preferred"], train_preferred_tied=test["preferred_tied"],
        train_n_preferred=test["n_preferred"], train_n_rest=test["n_rest"], train_u_preferred_twice=test["u_preferred_twice"],
        train_auc=test["auc"], test_n_preferred=test["test"]["n_preferred"], test_n_rest=test["test"]["n_rest"],
        test_u_preferred_twice=test["test"]["u_preferred_twice"], test_auc=test["test"]["auc"],
        included_in_conditional_summary=test["selected"])
    for i, code in enumerate(stats.CATEGORIES):
        for column, field in (("n_train_cat_", "supports"), ("n_test_cat_", "test_supports"),
                ("train_sum_count_cat_", "sums"), ("train_mean_rate_cat_", "means"),
                ("train_rank_sum_twice_cat_", "rank_sum_twice")):
            row[column+str(code)] = test[field][i]
    return row


def analyze(ref):
    """Cache only canonical source arithmetic, never submitted values or verdicts."""
    if "_analysis" in ref: return ref["_analysis"]
    arrays = ref["arrays"]
    unit_by_key = {r["unit_key"]: r for r in ref["units"] if r["included"]}
    subject = {r["asset_path"]: r["subject_id"] for r in ref["sessions"]}
    neurons, split_events = [], []
    for index, key in enumerate(arrays["unit_key"].tolist()):
        source = unit_by_key[key]
        selected = np.flatnonzero(arrays["response_unit_index"] == index)
        counts, categories = arrays["spike_count"][selected], arrays["category_code"][selected]
        row = {name: source[name] for name in ("unit_key", "asset_path", "unit_id", "region")}
        row["subject_id"] = subject[row["asset_path"]]
        row.update(full_fields(stats.category_test(counts, categories)))
        fitted = []
        for repeat in range(stats.N_REPEATS):
            item = stats.split_test(counts, categories, arrays["train_membership"][repeat, selected])
            fitted.append(item)
            split_events.append(split_fields(key, repeat, item, ref["method"]["outputs"]["split_events.csv"]["columns"]))
        row.update(stats.conditional_summary(fitted)); neurons.append(row)
    ref["_analysis"] = dict(neurons=neurons, split_events=split_events)
    return ref["_analysis"]


def summarize(ref, neurons, headline=POPULATIONS[1]):
    stats.require(headline in POPULATIONS, "Unknown headline population")
    populations = {
        POPULATIONS[0]: stats.population(r["same_trial_auc"] for r in neurons if r["category_selective"]),
        POPULATIONS[1]: stats.population(r["conditional_auc"] for r in neurons if r["heldout_eligible"])}
    selected = sum(r["category_selective"] for r in neurons)
    n_units = len(neurons)
    overlap = dict(full_only=0, conditional_only=0, both=0, neither=0)
    for row in neurons:
        a, b = row["category_selective"], row["heldout_eligible"]
        overlap["both" if a and b else "full_only" if a else "conditional_only" if b else "neither"] += 1
    result = dict(status=ref["metadata"]["status"], task_id="VISCAT-001", headline_population=headline,
        headline_status=populations[headline]["status"], preferred_category_auc=populations[headline]["mean_auc"],
        n_sessions=len(ref["sessions"]), n_patients=len({r["subject_id"] for r in ref["sessions"]}),
        n_source_units=len(ref["units"]), n_mtl_units=n_units,
        n_full_test_defined=sum(r["full_status"] != "insufficient_category_support" for r in neurons),
        n_full_test_undefined=sum(r["full_status"] == "insufficient_category_support" for r in neurons),
        n_category_selective=selected, proportion_category_selective=selected/n_units if n_units else None,
        n_crossfit_eligible=sum(r["heldout_eligible"] for r in neurons),
        n_response_rows=len(ref["arrays"]["spike_count"]), n_split_events=stats.N_REPEATS*n_units,
        populations=populations, population_overlap=overlap)
    if "resource_pilot_scope" in ref["metadata"]: result["resource_pilot_scope"] = ref["metadata"]["resource_pilot_scope"]
    return result
