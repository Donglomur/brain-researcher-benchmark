"""Independent operator-only paired ERP loss arithmetic; standard library only.

No source reads, fitting, model calls or imports of the predecessor scorer occur.
Private held rows must never be passed to a participant process. Source custody,
split selection and immutable prediction commitment remain caller obligations.
"""
import math

TARGETS = ("FRN_N2_offer", "P3b_offer")
FEATURES = ("offer", "rp", "exp_valence", "ep_valence", "exp_arousal",
            "ep_arousal", "trialLocal", "trialGlobal", "abs_R", "abs_V", "abs_A")
ARMS = ("mean", "N", "R", "V", "J")
MODES = ("frozen_program", "adaptive_investigation")


class InvalidScoreInput(ValueError):
    """Input cannot establish the complete paired-loss endpoint."""


def require(condition, reason):
    if not condition:
        raise InvalidScoreInput(reason)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def identity(value):
    require(type(value) is int and 1 <= value <= 7380, "source_row_identity")
    return value


def same_number(actual, expected, reason):
    require(finite(actual) and math.isclose(actual, expected, rel_tol=1e-9,
                                         abs_tol=1e-8), reason)


def paired_truth(case, held_rows):
    """Rebuild query and paired mask from a complete 180-row private trajectory."""
    require(type(case) is dict and type(case.get("participant")) is str,
            "case_identity")
    require(type(held_rows) is list and len(held_rows) == 180,
            "complete_held_trajectory")
    expected_query = []
    truth = {}
    seen = set()
    fields = set(FEATURES + TARGETS + ("participant", "source_row"))
    for trial, row in enumerate(held_rows, 1):
        require(type(row) is dict and set(row) == fields, "held_row_fields")
        key = identity(row["source_row"])
        require(key not in seen, "duplicate_held_source_row")
        seen.add(key)
        require(row["participant"] == case["participant"] and
                type(row["trialGlobal"]) is int and row["trialGlobal"] == trial,
                "held_trajectory_identity")
        require(type(row["trialLocal"]) is int and 1 <= row["trialLocal"] <= 5,
                "held_local_trial")
        require(all(row[name] is None or finite(row[name])
                    for name in FEATURES + TARGETS), "held_numeric_values")
        if all(row[name] is not None for name in FEATURES):
            expected_query.append({name: row[name] for name in FEATURES + ("source_row",)})
            if all(row[name] is not None for name in TARGETS):
                truth[key] = tuple(row[name] for name in TARGETS)
    query = case.get("query")
    require(type(query) is list and len(query) == len(expected_query),
            "complete_behavior_query")
    for observed, expected in zip(query, expected_query):
        require(type(observed) is dict and set(observed) == set(expected),
                "query_fields")
        identity(observed["source_row"])
        require(all(finite(observed[name]) for name in FEATURES), "query_numeric_values")
        require(observed == expected, "query_matches_private_behavior_rows")
    require(query and truth, "nonempty_query_and_paired_support")
    return truth, seen


def training_normalizers(training_case, held_person, held_source_rows):
    """Equal mass per fit cluster, including distinct bootstrap cluster copies."""
    require(type(training_case) is dict, "training_case")
    clusters = training_case.get("clusters")
    require(type(clusters) is list and len(clusters) >= 2, "training_clusters")
    originals = {}
    for cluster in clusters:
        require(type(cluster) is dict and set(cluster) == {"fit_id", "original_participant"},
                "cluster_fields")
        key, original = cluster["fit_id"], cluster["original_participant"]
        require(type(key) is str and key and key not in originals and
                type(original) is str and original and original != held_person,
                "training_cluster_identity")
        originals[key] = original
    rows = training_case.get("training")
    require(type(rows) is list and rows, "training_rows")
    grouped = {key: [] for key in originals}
    seen = set()
    source_values = {}
    for row in rows:
        require(type(row) is dict and set(row) == set(FEATURES + TARGETS +
                ("participant", "original_participant", "source_row")), "training_row_fields")
        key, source_row = row["participant"], identity(row["source_row"])
        require(type(key) is str and key in originals and
                row["original_participant"] == originals[key], "training_row_cluster")
        require(source_row not in held_source_rows, "held_source_in_training")
        require((key, source_row) not in seen, "duplicate_training_cluster_row")
        seen.add((key, source_row))
        require(all(finite(row[name]) for name in FEATURES + TARGETS),
                "training_paired_finite_values")
        # A bootstrap copy may repeat a source row only with the same source person/values.
        signature = (row["original_participant"],) + tuple(row[name] for name in FEATURES + TARGETS)
        require(source_row not in source_values or source_values[source_row] == signature,
                "inconsistent_training_source_copy")
        source_values[source_row] = signature
        grouped[key].append(row)
    require(all(grouped.values()), "training_cluster_without_rows")
    original_support = {}
    for cluster, rows in grouped.items():
        original = originals[cluster]
        support = {row["source_row"] for row in rows}
        require(original not in original_support or original_support[original] == support,
                "inconsistent_training_copy_support")
        original_support[original] = support
    result = {}
    for target in TARGETS:
        mean = math.fsum(math.fsum(row[target] for row in rows) / len(rows)
                         for rows in grouped.values()) / len(grouped)
        variance = math.fsum(math.fsum((row[target] - mean) ** 2 for row in rows) / len(rows)
                             for rows in grouped.values()) / len(grouped)
        require(finite(mean) and finite(variance) and variance > 0,
                "positive_finite_training_variance")
        result[target] = (mean, variance)
    return result


def candidate_vector(value, query_keys):
    require(type(value) is dict and set(value) == {"status", "predictions"} and
            value["status"] == "complete", "candidate_complete")
    rows = value["predictions"]
    require(type(rows) is list and len(rows) == len(query_keys), "complete_candidate_queries")
    result = {}
    for row in rows:
        require(type(row) is list and len(row) == 3, "candidate_row")
        key = identity(row[0])
        require(key in query_keys and key not in result and all(finite(v) for v in row[1:]),
                "candidate_identity_and_values")
        result[key] = tuple(row[1:])
    return result


def score_case(case, held_rows, reference, candidates, *, training_case=None):
    """Return the predecessor score shape from independently reconstructed inputs.

    `held_rows` is the complete private projected trajectory, including missing
    values. For frozen33/test8, pass the separately retained common training case;
    the public per-person query case intentionally contains no training rows.
    """
    try:
        truth, held_ids = paired_truth(case, held_rows)
        normalizers = training_normalizers(case if training_case is None else training_case,
                                          case["participant"], held_ids)
        keys = [row["source_row"] for row in case["query"]]
        require(type(reference) is dict and reference.get("schema") == "neural006-reference-v1" and
                reference.get("participant") == case["participant"] and
                reference.get("status") == "complete", "reference_identity_and_status")
        reference_keys = reference.get("source_rows")
        require(type(reference_keys) is list and all(type(key) is int for key in reference_keys) and
                reference_keys == keys, "reference_query_order")
        require(type(candidates) is dict and set(candidates) == set(MODES), "matched_modes")
        parsed = {mode: candidate_vector(candidates[mode], set(keys)) for mode in MODES}
        require(type(reference.get("results")) is dict and set(reference["results"]) == set(TARGETS),
                "reference_target_inventory")
        scores = {}
        for component, target in enumerate(TARGETS):
            entry = reference["results"][target]
            require(type(entry) is dict and type(entry.get("normalizer")) is dict and
                    type(entry.get("arms")) is dict and set(entry["arms"]) == set(ARMS),
                    "reference_target_fields")
            mean, variance = normalizers[target]
            same_number(entry["normalizer"].get("training_equal_person_mean"), mean,
                        "independent_training_mean")
            same_number(entry["normalizer"].get("training_equal_person_variance"), variance,
                        "independent_training_variance")
            vectors = {}
            for arm in ARMS:
                item = entry["arms"][arm]
                require(type(item) is dict and item.get("status") == "fit_completed" and
                        type(item.get("prediction")) is list and len(item["prediction"]) == len(keys) and
                        all(finite(v) for v in item["prediction"]), "complete_reference_arm")
                vectors[arm] = dict(zip(keys, item["prediction"]))
            for value in vectors["mean"].values():
                same_number(value, mean, "independent_mean_reference")
            vectors.update({mode: {key: values[component] for key, values in parsed[mode].items()}
                            for mode in MODES})
            scores[target] = {}
            for name, vector in vectors.items():
                residuals = [truth[key][component] - vector[key] for key in truth]
                mse = math.fsum(value * value for value in residuals) / len(residuals)
                mae = math.fsum(abs(value) for value in residuals) / len(residuals)
                normalized = mse / variance
                require(all(finite(v) for v in (mse, mae, normalized)), "finite_derived_losses")
                scores[target][name] = {"mse": mse, "mae": mae, "normalized_mse": normalized}
        return {"participant": case["participant"], "paired_scored_rows": len(truth), "components": scores}
    except (OverflowError, ZeroDivisionError) as error:
        raise InvalidScoreInput("unsupported_derived_numerics") from error
