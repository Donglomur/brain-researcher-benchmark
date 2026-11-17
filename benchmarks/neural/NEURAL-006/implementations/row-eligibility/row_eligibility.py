"""Independent, no-fit row accounting for N006's complete author endpoint.

Inputs and detailed reports are owner-private. This is a processed-export
lineage check, not an independent EEG-event alignment or exclusion-cause proof.
"""
import json

SCHEMA = "neural006-original-row-eligibility-wire-v1"
MODELS = (
    ("fig3a_model", ("FRN_N2_offer_s", "abs_rpe_s", "abs_epe_valence_s", "abs_epe_arousal_s", "P2_offer_s", "P2_base_offer_s", "sub")),
    ("fig3a_model1", ("FRN_N2_offer_s", "abs_rpe_s", "P2_offer_s", "P2_base_offer_s", "sub")),
    ("fig3a_model2", ("FRN_N2_offer_s", "abs_epe_valence_s", "P2_offer_s", "P2_base_offer_s", "sub")),
    ("fig3a_model3", ("FRN_N2_offer_s", "abs_epe_arousal_s", "P2_offer_s", "P2_base_offer_s", "sub")),
    ("fig3b_model", ("P3a_offer_s", "abs_rpe_s", "abs_epe_valence_s", "abs_epe_arousal_s", "P3a_base_offer_s", "sub")),
    ("fig3b_model1", ("P3a_offer_s", "abs_rpe_s", "P3a_base_offer_s", "sub")),
    ("fig3b_model2", ("P3a_offer_s", "abs_epe_valence_s", "P3a_base_offer_s", "sub")),
    ("fig3b_model3", ("P3a_offer_s", "abs_epe_arousal_s", "P3a_base_offer_s", "sub")),
    ("fig3c_model", ("P3b_offer_s", "abs_rpe_s", "abs_epe_valence_s", "abs_epe_arousal_s", "P3b_base_offer_s", "sub")),
    ("fig3c_model1", ("P3b_offer_s", "abs_rpe_s", "P3b_base_offer_s", "sub")),
    ("fig3c_model2", ("P3b_offer_s", "abs_epe_valence_s", "P3b_base_offer_s", "sub")),
)
FILES = ("BEH_ug.csv", "df_FRN_N2_offer.csv", "df_P2_offer.csv", "df_P2_base.csv",
         "df_P3a_offer.csv", "df_P3a_base.csv", "df_P3b_offer.csv", "df_P3b_base.csv")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def strict_json(body):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, "duplicate JSON key")
            out[key] = value
        return out
    def bad_constant(_):
        raise ValueError("nonfinite JSON constant")
    return json.loads(body, object_pairs_hook=pairs, parse_constant=bad_constant)


def integer(value, lower, upper, label):
    require(type(value) is int and lower <= value <= upper, label)
    return value


def rows(value, upper, label):
    require(type(value) is list, label)
    require(all(type(x) is int and 1 <= x <= upper for x in value), label)
    require(value == sorted(set(value)), label)
    return value


def strings(value, n, label):
    require(type(value) is list and len(value) == n, label)
    require(all(type(x) is str and 0 < len(x) <= 128 for x in value), label)
    return value


def keys(obj, expected, label):
    require(type(obj) is dict and set(obj) == set(expected), label)


def audit(wire, *, expected_people=41, trials_per_person=180):
    """Recompute every row set; retain mismatches as scientific findings.

    The keyword dimensions permit invented controls. Native execution fixes
    them to 41 x 180 and cannot select a successful subset.
    """
    integer(expected_people, 1, 41, "people dimension")
    integer(trials_per_person, 1, 180, "trial dimension")
    n = expected_people * trials_per_person
    keys(wire, ("schema", "source", "runtime", "models"), "wire fields")
    require(wire["schema"] == SCHEMA, "wire schema")
    source = wire["source"]
    keys(source, ("files", "subjects", "trial_global", "author_filter_missing_rows",
                  "saved_original_rows", "saved_subjects", "saved_ordered_people",
                  "saved_author_filter_source_rows"), "source fields")
    require(type(source["files"]) is list and len(source["files"]) == 8, "all eight files")
    parse_problems = 0
    for record, name in zip(source["files"], FILES):
        keys(record, ("name", "rows", "columns", "parse_problems"), "file fields")
        require(record["name"] == name, "literal positional file order")
        require(type(record["rows"]) is int and record["rows"] == n, "complete source rows")
        cols = strings(record["columns"], len(record["columns"]), "source columns")
        require(bool(cols) and len(cols) == len(set(cols)), "source column uniqueness")
        parse_problems += integer(record["parse_problems"], 0, n * len(cols), "parse problem count")
    subjects = strings(source["subjects"], n, "source subjects")
    ordered_people = list(dict.fromkeys(subjects))
    require(len(ordered_people) == expected_people, "complete person coverage")
    trials = source["trial_global"]
    require(type(trials) is list and len(trials) == n, "trial extent")
    require(all(type(x) is int for x in trials), "integer trials")
    for person in ordered_people:
        observed = [trials[i] for i, value in enumerate(subjects) if value == person]
        require(observed == list(range(1, trials_per_person + 1)), "person trial ordering")
    filter_missing = rows(source["author_filter_missing_rows"], n, "author filter omissions")
    filter_set = set(filter_missing)
    after_filter = [i for i in range(1, n + 1) if i not in filter_set]
    require(bool(after_filter), "nonempty author-filter support")
    saved_original = rows(source["saved_original_rows"], n, "saved original rows")
    saved_subjects = strings(source["saved_subjects"], n, "saved subjects")
    saved_people = strings(source["saved_ordered_people"], expected_people, "saved ordered people")
    saved_filter = rows(source["saved_author_filter_source_rows"], n, "saved filter rows")
    source_checks = {
        "saved_original_rows_match": saved_original == list(range(1, n + 1)),
        "saved_subjects_match": saved_subjects == subjects,
        "saved_ordered_people_match": saved_people == ordered_people,
        "saved_filter_rows_match": saved_filter == after_filter,
    }
    runtime = wire["runtime"]
    keys(runtime, ("na_action", "R", "platform", "package_versions"), "runtime fields")
    require(runtime["na_action"] == "na.omit", "unsupported observed na.action")
    require(type(runtime["R"]) is str and type(runtime["platform"]) is str, "runtime identity")
    require(type(runtime["package_versions"]) is dict and
            set(runtime["package_versions"]) == {"readr", "dplyr", "lme4", "jsonlite"}, "runtime packages")
    require(all(type(v) is str and v for v in runtime["package_versions"].values()), "package versions")
    require(type(wire["models"]) is list and len(wire["models"]) == 11, "all eleven models")
    detailed = []
    for model, (name, variables) in zip(wire["models"], MODELS):
        keys(model, ("name", "variables", "missing_rows_by_variable", "nonfinite_rows_by_variable",
                     "native_frame_rows", "native_omitted_rows", "native_na_action_class",
                     "saved_frame_rows", "saved_source_rows", "saved_nobs", "saved_group_count",
                     "saved_formula_matches"), "model fields")
        require(model["name"] == name and model["variables"] == list(variables), "ordered model/variables")
        keys(model["missing_rows_by_variable"], variables, "complete variable missingness")
        keys(model["nonfinite_rows_by_variable"], variables, "complete variable nonfinite census")
        missing = {var: rows(model["missing_rows_by_variable"][var], n, "missing source rows") for var in variables}
        infinite = {var: rows(model["nonfinite_rows_by_variable"][var], n, "nonmissing nonfinite rows") for var in variables}
        require(all(not set(missing[v]).intersection(infinite[v]) for v in variables), "disjoint missing/nonfinite")
        omissions = set().union(*(set(x) for x in missing.values()))
        kept_positions = [j for j, src in enumerate(after_filter, 1) if src not in omissions]
        kept_sources = [after_filter[j - 1] for j in kept_positions]
        kept_set = set(kept_positions)
        omitted_positions = [j for j in range(1, len(after_filter) + 1) if j not in kept_set]
        native_rows = rows(model["native_frame_rows"], len(after_filter), "native frame rows")
        native_omitted = rows(model["native_omitted_rows"], len(after_filter), "native omission rows")
        saved_rows = rows(model["saved_frame_rows"], len(after_filter), "saved frame rows")
        saved_sources = rows(model["saved_source_rows"], n, "saved original source rows")
        nobs = integer(model["saved_nobs"], 0, n, "saved nobs")
        groups = integer(model["saved_group_count"], 0, expected_people, "saved groups")
        require(type(model["saved_formula_matches"]) is bool, "formula comparison type")
        require(model["native_na_action_class"] in ([], ["omit"]), "native na.action class")
        expected_class = ["omit"] if omitted_positions else []
        checks = {
            "saved_formula_matches": model["saved_formula_matches"],
            "native_frame_matches_independent_mask": native_rows == kept_positions,
            "native_omissions_match_independent_mask": native_omitted == omitted_positions,
            "native_omission_class_matches": model["native_na_action_class"] == expected_class,
            "saved_frame_matches_independent_mask": saved_rows == kept_positions,
            "saved_source_composition_matches": saved_sources == kept_sources,
            "saved_observations_match": nobs == len(kept_sources),
            "saved_groups_match": groups == len({subjects[i - 1] for i in kept_sources}),
        }
        detailed.append({"name": name, "checks": checks,
                         "author_filter_source_rows": after_filter,
                         "expected_model_frame_rows": kept_positions,
                         "expected_original_source_rows": kept_sources,
                         "post_filter_omitted_positions": omitted_positions,
                         "post_filter_omitted_source_rows": [after_filter[j-1] for j in omitted_positions],
                         "missing_rows_by_variable": missing,
                         "nonfinite_rows_by_variable": infinite,
                         "nonfinite_modeled_source_rows": sorted(set(kept_sources).intersection(
                             set().union(*(set(x) for x in infinite.values()))))})
    matches = sum(all(m["checks"].values()) for m in detailed)
    infinite_models = sum(bool(m["nonfinite_modeled_source_rows"]) for m in detailed)
    status = "consistent" if all(source_checks.values()) and matches == 11 and not parse_problems and not infinite_models else "inconsistent_or_held"
    safe = {"schema": "neural006-row-eligibility-technical-v1", "status": status,
            "input_files": 8, "input_people": expected_people, "input_rows_per_file": n,
            "models_checked": 11, "models_matching": matches,
            "source_support_matches": all(source_checks.values()),
            "author_filter_exclusions": len(filter_missing),
            "post_filter_exclusions_per_model": [len(m["post_filter_omitted_positions"]) for m in detailed],
            "parse_problems": parse_problems, "nonfinite_modeled_models": infinite_models,
            "refits": 0, "candidate_calls": 0,
            "independent_erp_event_alignment": False, "exclusion_cause_established": False,
            "raw_preprocessing_validated": False, "publication_parity": False,
            "scientifically_qualified": False}
    private = {"schema": "neural006-row-eligibility-private-v1", "source_checks": source_checks,
               "source_subjects": subjects, "author_filter_missing_source_rows": filter_missing,
               "models": detailed, "technical": safe}
    return private, safe
