"""Deterministic category statistics; import-safe, no original-source access.

SciPy supplies average ranks and chi-square survival. Exact integer doubled
ranks and rational H remove negative-statistic cancellation at H=0. The public
rational algebra is shared mathematics, not an independently fitted estimator.
"""
from fractions import Fraction
import math

import numpy as np
from scipy.stats import chi2, rankdata

CATEGORIES = (1, 2, 3, 4, 5)
N_REPEATS = 50
MIN_SELECTED = 5
POPULATIONS = ("full_data_selected_same_trials", "crossfit_selected_at_least_five_splits")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer_vector(value, name, nonnegative=False):
    a = np.asarray(value)
    require(a.ndim == 1 and a.dtype.kind in "iu", name + ": integer vector required")
    require(not len(a) or (int(a.min()) >= -(2**63) and int(a.max()) < 2**63), name + ": int64 overflow")
    a = a.astype(np.int64, copy=False)
    require(not nonnegative or np.all(a >= 0), name + ": negative value")
    return a


def selection(status, p):
    return bool(status == "ok" and p is not None and p < .05)


def auc_from_preference(counts, categories, preferred):
    counts = integer_vector(counts, "AUC counts", True)
    categories = integer_vector(categories, "AUC categories")
    require(len(counts) == len(categories) and np.isin(categories, CATEGORIES).all(), "AUC category axis")
    require(preferred in CATEGORIES, "Invalid preferred category")
    positive = categories == preferred
    n_positive, n_negative = int(positive.sum()), int((~positive).sum())
    if not n_positive or not n_negative:
        return dict(n_preferred=n_positive, n_rest=n_negative, u_preferred_twice=None, auc=None)
    doubled = (2 * rankdata(counts, method="average")).astype(np.int64)
    u2 = sum(map(int, doubled[positive])) - n_positive * (n_positive + 1)
    require(0 <= u2 <= 2 * n_positive * n_negative, "Invalid rank-sum AUC")
    return dict(n_preferred=n_positive, n_rest=n_negative, u_preferred_twice=u2,
                auc=u2 / (2 * n_positive * n_negative))


def category_statistics(counts, categories):
    counts = integer_vector(counts, "counts", True)
    categories = integer_vector(categories, "categories")
    require(len(counts) == len(categories) and np.isin(categories, CATEGORIES).all(), "Category axis mismatch")
    n = len(counts)
    doubled = (2 * rankdata(counts, method="average")).astype(np.int64) if n else np.empty(0, dtype=np.int64)
    multiplicities = np.unique(counts, return_counts=True)[1]
    tie_sum = sum(int(t)**3-int(t) for t in multiplicities)
    result = dict(tie_sum=tie_sum, status="insufficient_category_support", small_group_warning=False,
                  H=None, p=None, selected=False, preferred_category=None, preferred_tied=None,
                  n_preferred=None, n_rest=None, u_preferred_twice=None, auc=None)
    sizes, sums, ranks = [], [], []
    for c in CATEGORIES:
        mask = categories == c
        size, total, rank_sum = int(mask.sum()), sum(map(int, counts[mask])), sum(map(int, doubled[mask]))
        sizes.append(size); sums.append(total); ranks.append(rank_sum)
        result.update({f"n_cat_{c}": size, f"sum_count_cat_{c}": total,
                       f"mean_rate_cat_{c}": total / (1.5 * size) if size else None,
                       f"rank_sum_twice_cat_{c}": rank_sum})
    result["small_group_warning"] = any(0 < size < 5 for size in sizes)
    if not all(sizes):
        return result
    means = [Fraction(total, size) for total, size in zip(sums, sizes)]
    maximum = max(means)
    winners = [c for c, mean in zip(CATEGORIES, means) if mean == maximum]
    result.update(preferred_category=winners[0], preferred_tied=len(winners) > 1)
    if len(multiplicities) == 1:
        result.update(status="all_tied", H=0.0, p=1.0)
    else:
        h0 = Fraction(3, n*(n+1)) * sum((Fraction(r*r, size) for r, size in zip(ranks, sizes)), Fraction()) - 3*(n+1)
        correction = Fraction(n**3-n-tie_sum, n**3-n)
        require(h0 >= 0 and correction > 0, "Invalid exact Kruskal-Wallis statistic")
        h = float(h0 / correction)
        p = float(chi2.sf(h, 4))
        require(math.isfinite(h) and h >= 0 and math.isfinite(p) and 0 <= p <= 1, "Invalid KW survival")
        result.update(status="ok", H=h, p=p)
    result["selected"] = selection(result["status"], result["p"])
    result.update(auc_from_preference(counts, categories, result["preferred_category"]))
    return result


def full_row(record, stats):
    row = {k: record[k] for k in ("unit_key", "asset_path", "subject_id", "unit_id", "region")}
    row.update(n_trials=len(record["counts"]))
    for c in CATEGORIES:
        for prefix in ("n_cat_", "sum_count_cat_", "mean_rate_cat_", "rank_sum_twice_cat_"):
            row[prefix+str(c)] = stats[prefix+str(c)]
    for field in ("tie_sum", "small_group_warning", "preferred_category", "preferred_tied",
                  "n_preferred", "n_rest", "u_preferred_twice"):
        row[field] = stats[field]
    row.update(full_status=stats["status"], kw_H=stats["H"], kw_p=stats["p"],
               category_selective=stats["selected"], same_trial_auc=stats["auc"],
               n_usable_splits=0, n_selected_splits=0, conditional_auc=None,
               conditional_status="no_selected_splits", heldout_eligible=False)
    return row


def unsupported_split(unit_key, repeat):
    row = dict(unit_key=unit_key, repeat=repeat, status="insufficient_category_support",
               train_selected=False, included_in_conditional_summary=False)
    for c in CATEGORIES:
        for prefix in ("n_train_cat_", "n_test_cat_", "train_sum_count_cat_", "train_mean_rate_cat_", "train_rank_sum_twice_cat_"):
            row[prefix+str(c)] = None
    for field in ("tie_sum", "small_group_warning", "H", "p", "preferred_category", "preferred_tied",
                  "n_preferred", "n_rest", "u_preferred_twice", "auc"):
        row["train_"+field] = None
    for field in ("n_preferred", "n_rest", "u_preferred_twice", "auc"):
        row["test_"+field] = None
    return row


def split_row(record, repeat, membership):
    cats, counts = record["category_code"], record["counts"]
    train = category_statistics(counts[membership], cats[membership])
    require(train["status"] != "insufficient_category_support", "Generated split lacks category support")
    test = auc_from_preference(counts[~membership], cats[~membership], train["preferred_category"])
    require(test["auc"] is not None, "Generated test lacks preferred/rest support")
    row = dict(unit_key=record["unit_key"], repeat=repeat, status=train["status"],
               train_selected=train["selected"], included_in_conditional_summary=train["selected"])
    for c in CATEGORIES:
        row[f"n_train_cat_{c}"] = train[f"n_cat_{c}"]
        row[f"n_test_cat_{c}"] = int(np.count_nonzero(cats[~membership] == c))
        for prefix in ("sum_count_cat_", "mean_rate_cat_", "rank_sum_twice_cat_"):
            row["train_"+prefix+str(c)] = train[prefix+str(c)]
    for field in ("tie_sum", "small_group_warning", "H", "p", "preferred_category", "preferred_tied",
                  "n_preferred", "n_rest", "u_preferred_twice", "auc"):
        row["train_"+field] = train[field]
    row.update({"test_"+key: value for key, value in test.items()})
    return row


def analyze(records):
    """Canonical source records in, complete statistics/receipt arrays out."""
    keys = [r["unit_key"] for r in records]
    require(len(set(keys)) == len(keys), "Duplicate unit keys")
    records = [dict(r) for r in records]
    starts, categories, rows = [0], [], []
    for r in records:
        r["counts"] = integer_vector(r["counts"], "record counts", True)
        r["category_code"] = integer_vector(r["category_code"], "record categories")
        r["source_trial_row"] = integer_vector(r["source_trial_row"], "source trial rows", True)
        r["trial_id"] = integer_vector(r["trial_id"], "trial IDs")
        require(len(r["counts"]) == len(r["category_code"]) == len(r["source_trial_row"]) == len(r["trial_id"]), "Response axes")
        require(len(np.unique(r["trial_id"])) == len(r["trial_id"]) and np.all(np.diff(r["source_trial_row"]) > 0), "Original trial identity/order")
        rows.append(full_row(r, category_statistics(r["counts"], r["category_code"])))
        categories.append([np.flatnonzero(r["category_code"] == c) for c in CATEGORIES])
        starts.append(starts[-1]+len(r["counts"]))
    membership = np.zeros((N_REPEATS, starts[-1]), dtype=bool)
    rng = np.random.Generator(np.random.PCG64(0))
    events, selected_values = [], [[] for _ in records]
    for repeat in range(N_REPEATS):
        for unit_index, (r, groups) in enumerate(zip(records, categories)):
            if any(len(group) < 2 for group in groups):
                events.append(unsupported_split(r["unit_key"], repeat))
                continue
            mask = membership[repeat, starts[unit_index]:starts[unit_index+1]]
            for group in groups:
                permuted = group.copy()
                rng.shuffle(permuted)
                mask[permuted[:len(group)//2]] = True
            event = split_row(r, repeat, mask)
            events.append(event)
            rows[unit_index]["n_usable_splits"] += 1
            if event["train_selected"]:
                selected_values[unit_index].append(event["test_auc"])
    for row, values in zip(rows, selected_values):
        row.update(n_selected_splits=len(values), conditional_auc=math.fsum(values)/len(values) if values else None,
                   conditional_status="defined" if values else "no_selected_splits", heldout_eligible=len(values) >= MIN_SELECTED)
    def concat(key, dtype):
        return np.concatenate([r[key] for r in records]).astype(dtype) if records else np.empty(0, dtype=dtype)
    arrays = dict(unit_key=np.asarray(keys, dtype=str), response_unit_index=np.repeat(np.arange(len(records), dtype=np.int64), np.diff(starts)),
                  source_trial_row=concat("source_trial_row", np.int64), trial_id=concat("trial_id", np.int64),
                  category_code=concat("category_code", np.int64), spike_count=concat("counts", np.int64),
                  repeat_id=np.arange(N_REPEATS, dtype=np.int64), train_membership=membership)
    arrays["rate_hz"] = arrays["spike_count"].astype(np.float64) / 1.5
    return rows, events, arrays


def summarize(neurons, sessions, response_count, headline=POPULATIONS[1], status="complete"):
    require(headline in POPULATIONS and status in ("complete", "resource_pilot"), "Invalid summary declaration")
    full = [r["same_trial_auc"] for r in neurons if r["category_selective"]]
    crossfit = [r["conditional_auc"] for r in neurons if r["heldout_eligible"]]
    def population(values):
        require(all(v is not None and math.isfinite(v) and 0 <= v <= 1 for v in values), "Invalid eligible AUC")
        return dict(n_units=len(values), mean_auc=math.fsum(values)/len(values) if values else None,
                    status="defined" if values else "empty_population")
    populations = {POPULATIONS[0]: population(full), POPULATIONS[1]: population(crossfit)}
    overlap = dict(full_only=0, conditional_only=0, both=0, neither=0)
    for row in neurons:
        key = "both" if row["category_selective"] and row["heldout_eligible"] else "full_only" if row["category_selective"] else "conditional_only" if row["heldout_eligible"] else "neither"
        overlap[key] += 1
    defined = sum(r["full_status"] != "insufficient_category_support" for r in neurons)
    return dict(status=status, task_id="VISCAT-001", headline_population=headline,
                headline_status=populations[headline]["status"], preferred_category_auc=populations[headline]["mean_auc"],
                n_sessions=len(sessions), n_patients=len({r["subject_id"] for r in sessions}),
                n_source_units=sum(r["n_source_units"] for r in sessions), n_mtl_units=len(neurons),
                n_full_test_defined=defined, n_full_test_undefined=len(neurons)-defined,
                n_category_selective=len(full), proportion_category_selective=len(full)/len(neurons) if neurons else None,
                n_crossfit_eligible=len(crossfit), n_response_rows=response_count,
                n_split_events=N_REPEATS*len(neurons), populations=populations, population_overlap=overlap)
