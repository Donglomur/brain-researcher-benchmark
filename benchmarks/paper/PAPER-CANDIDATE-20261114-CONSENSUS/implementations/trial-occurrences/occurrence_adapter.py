"""Reconstruct declared Consensus loader occurrences from supplied records.

No native binary, NPY, neural value or historical configuration is authenticated
by this component. Repetitions and discrepancies are reported, never repaired.
"""
import json
import math

ANIMALS = (
    "MPV17_FB_5", "MPV18_FB_5", "MPV31_FF_5", "MPV33_FF_5",
    "MPV34_FF_5", "VL63_FF_5", "VL66_FB_5",
)
MAX_TRIALS = 10000
MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_OUTPUT_BYTES = 64 * 1024 * 1024


def require(value, message):
    if not value:
        raise ValueError(message)


def exact_keys(value, keys, name):
    require(type(value) is dict and set(value) == set(keys), name + ": fields")


def integer(value, lower, upper, name):
    require(type(value) is int and lower <= value <= upper, name + ": integer domain")
    return value


def vector(value, n, name, integral_float=False):
    require(type(value) is list and len(value) == n, name + ": extent")
    result = []
    for item in value:
        if integral_float and type(item) is float:
            require(math.isfinite(item) and item.is_integer(), name + ": exact integral float")
            item = int(item)
        result.append(integer(item, 0, n - 1, name))
    return result


def pair(value, name):
    require(type(value) is list and len(value) == 2, name + ": two columns")
    for item in value:
        require(type(item) in (int, float), name + ": numeric column")
        require(abs(item) <= 2**53 and math.isfinite(item), name + ": finite exact numeric range")
    return tuple(value)


def counts(indices, n):
    result = [0] * n
    for item in indices:
        result[item] += 1
    return result


def mapping_summary(indices, n):
    c = counts(indices, n)
    return {
        "occurrences": len(indices), "unique_source_ids": sum(x > 0 for x in c),
        "repeated_occurrences": sum(max(0, x - 1) for x in c),
        "omitted_source_ids": [i for i, x in enumerate(c) if x == 0],
        "count_by_source_id": c,
    }


def configuration(value):
    if value is None:
        return None
    exact_keys(value, ("branch", "selected_condition_pairs", "entrypoint", "basis"), "configuration")
    require(value["branch"] in ("no_condition", "condition_pairs"), "configuration: branch")
    require(value["entrypoint"] in ("fit", "analyze", None), "configuration: entrypoint")
    require(value["basis"] in ("declared_scenario", "supplied_historical_record"), "configuration: basis")
    if value["branch"] == "no_condition":
        require(value["selected_condition_pairs"] is None, "no_condition: no condition list")
        return dict(value)
    ps = value["selected_condition_pairs"]
    require(type(ps) is list and len(ps) <= MAX_TRIALS, "configuration: condition list")
    # Preserve duplicates. Upstream List.mem makes duplicate requested pairs inert.
    return {**value, "selected_condition_pairs": [list(pair(x, "selected condition")) for x in ps]}


def audit_fold(record, n, condition_pairs):
    exact_keys(record, ("fold_id", "companion_indices", "native_indices", "configuration"), "fold")
    fold_id = integer(record["fold_id"], 0, 2, "fold_id")
    companion = vector(record["companion_indices"], n, "companion", integral_float=True)
    native = None if record["native_indices"] is None else vector(record["native_indices"], n, "native")
    config = configuration(record["configuration"])
    holds = ["historical_configuration_and_input_provenance_not_authenticated",
             "held_neuron_and_condition_average_leakage_not_resolved",
             "CLI_condition_conversion_not_reproduced"]
    equal = None if native is None else native == companion
    result = {
        "fold_id": fold_id, "source_trial_count": n,
        "companion_mapping": mapping_summary(companion, n),
        "native_mapping": None if native is None else mapping_summary(native, n),
        "supplied_native_companion_equal": equal, "configuration": config,
        "occurrences": None, "partition_summary": None, "holds": holds,
        "historical_native_parity_authenticated": False,
        "scientific_qualification": False,
    }
    if native is None:
        holds.append("native_mapping_unavailable")
    elif not equal:
        holds.append("native_companion_disagreement")
    if config is None:
        holds.append("loader_branch_configuration_unavailable")
    if native is None or config is None:
        return result
    if config["branch"] == "no_condition":
        # Upstream arrays were first indexed by P; data(P) indexes those arrays
        # again. Each entry of P remains a separate selection occurrence.
        selected, nonselected = list(native), []
    else:
        if condition_pairs is None:
            holds.append("original_condition_rows_unavailable")
            return result
        requested = {tuple(x) for x in config["selected_condition_pairs"]}
        selected, nonselected = [], []
        for position, original_id in enumerate(native):
            target = selected if condition_pairs[original_id] in requested else nonselected
            target.append(position)
    order = selected + nonselected
    require(len(order) == n, "complete loader occurrence extent")
    training_count = (2 * len(selected)) // 3
    occurrences = [
        {"occurrence_index": k, "loader_position": position,
         "original_source_trial_index": native[position],
         "selection_group": "selected" if k < len(selected) else "nonselected",
         "partition": "train" if k < training_count else "test"}
        for k, position in enumerate(order)
    ]
    effective = [x["original_source_trial_index"] for x in occurrences]
    train, test = effective[:training_count], effective[training_count:]
    train_counts, test_counts = counts(train, n), counts(test, n)
    overlap = [i for i in range(n) if train_counts[i] and test_counts[i]]
    result["occurrences"] = occurrences
    result["partition_summary"] = {
        "basis": "native-derived supplied record, conditional on declared configuration",
        "selected_occurrences": len(selected), "nonselected_occurrences": len(nonselected),
        "training_occurrences": len(train), "test_occurrences": len(test),
        "effective_mapping": mapping_summary(effective, n),
        "training_count_by_source_id": train_counts, "test_count_by_source_id": test_counts,
        "overlap_source_ids": overlap, "source_identity_disjoint": not overlap,
        "clean_generalization_established": False,
    }
    if not train:
        holds.append("empty_training_partition")
    if not test:
        holds.append("empty_test_partition")
    if overlap:
        holds.append("source_identity_train_test_overlap")
    if any(x == 0 for x in counts(effective, n)):
        holds.append("original_source_trials_omitted_by_loader")
    return result


def audit(document):
    exact_keys(document, ("schema", "animals"), "input")
    require(document["schema"] == "consensus_occurrence_input_v1", "input schema")
    records = document["animals"]
    require(type(records) is list and len(records) == len(ANIMALS), "complete seven-animal roster")
    by_animal = {}
    for record in records:
        exact_keys(record, ("animal_id", "source_trial_count", "source_condition_pairs", "folds"), "animal")
        name = record["animal_id"]
        require(type(name) is str and name in ANIMALS and name not in by_animal, "unique exact animal roster")
        n = integer(record["source_trial_count"], 1, MAX_TRIALS, "source_trial_count")
        pairs = record["source_condition_pairs"]
        if pairs is not None:
            require(type(pairs) is list and len(pairs) == n, "complete original condition rows")
            pairs = [pair(x, "original condition") for x in pairs]
        fs = record["folds"]
        require(type(fs) is list and len(fs) == 3, "complete three-fold roster")
        by_fold = {}
        for fold in fs:
            result = audit_fold(fold, n, pairs)
            key = result["fold_id"]
            require(key not in by_fold, "duplicate fold")
            by_fold[key] = result
        require(set(by_fold) == {0, 1, 2}, "complete fold ids")
        folds = [by_fold[i] for i in range(3)]
        complete = all(x["partition_summary"] is not None for x in folds)
        coverage = None
        if complete:
            coverage = {
                "test_occurrence_count_by_source_id": [sum(f["partition_summary"]["test_count_by_source_id"][i] for f in folds) for i in range(n)],
                "training_occurrence_count_by_source_id": [sum(f["partition_summary"]["training_count_by_source_id"][i] for f in folds) for i in range(n)],
                "folds_are_not_independent_animals": True,
            }
        by_animal[name] = {"animal_id": name, "source_trial_count": n, "folds": folds,
                           "all_three_mappings_reconstructed": complete, "three_fold_coverage": coverage}
    require(set(by_animal) == set(ANIMALS), "exact animal coverage")
    return {
        "schema": "consensus_occurrence_audit_v1",
        "status": "COMPLETE_SUPPLIED_RECORD_AUDIT_NOT_QUALIFICATION",
        "animals": [by_animal[name] for name in ANIMALS],
        "animal_count": 7, "fold_count": 21,
        "original_intake_or_scientific_contract_modified": False,
        "native_bytes_or_source_axes_authenticated": False,
        "scientific_qualification": False,
    }


def parse_input(raw):
    require(type(raw) is bytes and len(raw) <= MAX_INPUT_BYTES, "input byte limit")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    def bad_constant(_):
        raise ValueError("nonfinite JSON constant")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=bad_constant)


def main():
    import sys
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    result = audit(parse_input(raw))
    body = (json.dumps(result, sort_keys=True, allow_nan=False, separators=(",", ":")) + "\n").encode()
    require(len(body) <= MAX_OUTPUT_BYTES, "output byte limit")
    sys.stdout.buffer.write(body)


if __name__ == "__main__":
    main()
