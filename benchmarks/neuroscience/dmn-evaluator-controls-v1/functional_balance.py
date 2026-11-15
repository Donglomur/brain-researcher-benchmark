"""All56 functional-balance comparison source; no default scientific protocol.

Native and reference execution are separately selected operations. This module
has no CLI and importing it does not import NumPy or decode any input.
"""
import hashlib
import json
import math
import time

NETWORK_CODES = tuple(range(2, 9))
TYPE_CODES = tuple(range(1, 7))
COHORTS = ("mics", "hcp")
EXTENTS = ("cortical", "extended")
DIRECTIONS = ("input", "output")
KEYS = tuple((c, e, d, n) for c in COHORTS for e in EXTENTS
             for d in DIRECTIONS for n in NETWORK_CODES)
NUMPY_VERSION = "2.4.6"


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def kl_uniform_to_profile(strengths, undefined="strict"):
    """D_KL(U6 || p), bits, with explicit historical-nansum compatibility."""
    need(undefined in ("strict", "historical_nansum_diagnostic"), "named undefined protocol")
    need(len(strengths) == 6, "six cortical types, no second type0 slice")
    values = [float(x) for x in strengths]
    if any(x < 0 for x in values if math.isfinite(x)):
        raise ValueError("negative absolute-strength profile")
    missing = any(math.isnan(x) for x in values)
    total = sum(values)
    if undefined == "strict" and (missing or not math.isfinite(total) or total <= 0):
        return {"status": "UNDEFINED", "reason": "missing or nonpositive/nonfinite mass",
                "strengths": values, "probabilities": None, "KL_bits": None}
    probabilities = [x / total if math.isfinite(total) and total > 0 else math.nan for x in values]
    terms = []
    for p in probabilities:
        if math.isnan(p):
            terms.append(math.nan)
        elif p == 0:
            terms.append(math.inf)
        elif p > 0 and math.isfinite(p):
            terms.append((math.log2(1 / 6) - math.log2(p)) / 6)
        else:
            terms.append(math.nan)
    if undefined == "historical_nansum_diagnostic":
        # This intentionally reproduces the dangerous all-NaN ->0 behavior.
        result = sum(t for t in terms if not math.isnan(t))
        return {"status": "HISTORICAL_DIAGNOSTIC_ONLY", "strengths": values,
                "probabilities": probabilities, "KL_bits": result,
                "NaN_terms_dropped": sum(math.isnan(t) for t in terms),
                "scientifically_qualified": False}
    if any(math.isnan(t) for t in terms):
        return {"status": "UNDEFINED", "reason": "undefined probability component",
                "strengths": values, "probabilities": probabilities, "KL_bits": None}
    return {"status": "INFINITE" if any(math.isinf(t) for t in terms) else "FINITE",
            "strengths": values, "probabilities": probabilities, "KL_bits": sum(terms)}


def strict_lower_tail(empirical, nulls, expected=10000):
    """The frozen source's strict k/N tail; no automatic plus-one replacement."""
    need(len(nulls) == expected, "complete prescribed null distribution")
    if empirical is None or math.isnan(empirical) or empirical == -math.inf or any(
            x is None or math.isnan(x) or x == -math.inf for x in nulls):
        return {"status": "UNDEFINED", "p": None, "strict_count": None,
                "N": expected, "reason": "all prescribed comparisons must be defined; no omitted NaN or missing null"}
    count = sum(empirical > x for x in nulls)
    status = "EXTENDED_REAL" if math.isinf(empirical) or any(math.isinf(x) for x in nulls) else "FINITE"
    return {"status": status, "p": count / expected, "strict_count": count,
            "N": expected, "protocol": "historical_strict_lower_tail_k_over_N"}


def plus_one_tail_separate(empirical, nulls, expected=10000):
    result = strict_lower_tail(empirical, nulls, expected)
    if result["status"] in ("FINITE", "EXTENDED_REAL"):
        result = dict(result, p=(result["strict_count"] + 1) / (expected + 1),
                      protocol="prospective_plus_one_lower_tail_separate")
    return result


def numpy_runtime():
    import numpy as np
    need(np.__version__ == NUMPY_VERSION, "existing NumPy version must be separately qualified")
    return np


def empirical_profile(matrix, networks, types, network_code, direction):
    """Mean of type-specific partner means, then mean over network centers."""
    np = numpy_runtime()
    need(direction in DIRECTIONS, "input/output orientation")
    work = matrix if direction == "input" else matrix.T
    centers = networks == network_code
    result, counts = [], []
    for type_code in TYPE_CODES:
        partners = (networks != network_code) & (types == type_code)
        counts.append({"type": type_code, "center_count": int(centers.sum()),
                       "outside_type_count": int(partners.sum())})
        if not centers.any() or not partners.any():
            result.append(math.nan)
        else:
            # Explicit two-stage order from grpstats(...), then network average.
            result.append(float(work[np.ix_(centers, partners)].mean(axis=1).mean()))
    return result, counts


def null_profiles(matrix, full_networks, full_types, cortical_positions, spins,
                  direction, protocol, deadline):
    """All columns; code-aligned source-mask diagnostic or matched-mask variant.

    Neither alternative is historical scientific equivalence without a frozen
    method disposition. We never use positional first7 groups as named networks.
    """
    np = numpy_runtime()
    need(protocol in ("code_aligned_source_unmasked_null",
                      "matched_extrinsic_null_prospective"), "explicit null-mask protocol")
    work = matrix if direction == "input" else matrix.T
    types = full_types[cortical_positions]
    result = {n: [] for n in NETWORK_CODES}
    group_evidence = []
    precomputed = []
    for type_code in TYPE_CODES:
        mask = types == type_code
        precomputed.append(work[:, mask].mean(axis=1) if mask.any()
                           else np.full(len(types), np.nan))
    precomputed = np.asarray(precomputed).T
    for column in range(spins.shape[1]):
        need(time.monotonic() < deadline, "complete-reference deadline; no partial admission")
        rotated_full = full_networks[spins[:, column]]
        groups = np.unique(rotated_full).tolist()
        cortical_networks = rotated_full[cortical_positions]
        group_evidence.append({"column_one_based": column + 1,
                               "sorted_group_codes": groups,
                               "literal_first_seven": groups[:7],
                               "literal_first_seven_align": groups[:7] == list(NETWORK_CODES)})
        for network in NETWORK_CODES:
            centers = cortical_networks == network
            if protocol == "code_aligned_source_unmasked_null":
                strengths = precomputed[centers].mean(axis=0).tolist() if centers.any() else [math.nan] * 6
            else:
                strengths = []
                for type_code in TYPE_CODES:
                    partners = (cortical_networks != network) & (types == type_code)
                    strengths.append(float(work[np.ix_(centers, partners)].mean(axis=1).mean())
                                     if centers.any() and partners.any() else math.nan)
            result[network].append(kl_uniform_to_profile(strengths, "strict"))
    return result, group_evidence


def require_closed_provenance(policy):
    need(policy.get("scientific_execution_selected") is True, "reference operation not selected")
    need(policy.get("reference_scope") == "all56_cells_all10000_spins", "complete fixed scope")
    required = ("mean_matrix_lineage", "directed_axis_orientation", "all_four_matrix_label_joins",
                "extended_model_endpoint", "external_type_mapping_helper", "wall_and_spin_semantics",
                "producer_consumer_field_disposition", "six_type_row_disposition",
                "null_network_column_disposition", "empirical_null_mask_disposition",
                "undefined_value_disposition", "strict_tail_disposition", "private_evaluation_rights")
    for key in required:
        evidence = policy.get("accepted_provenance", {}).get(key)
        need(isinstance(evidence, dict) and evidence.get("status") == "ACCEPTED"
             and isinstance(evidence.get("review_sha256"), str)
             and len(evidence["review_sha256"]) == 64, "unclosed scientific gate: " + key)
    need(policy.get("null_protocol") in ("code_aligned_source_unmasked_null",
                                        "matched_extrinsic_null_prospective"), "unselected null protocol")
    need(policy.get("historical_equivalence_established") is True,
         "no paper-reproduction claim from an unproved method substitution")


def run_all56(prepared, policy, deadline):
    """Protected evaluator/reference API. Caller must bind exact native identities."""
    require_closed_provenance(policy)
    np = numpy_runtime()
    need(set(prepared["matrices"]) == {c + ":" + e for c in COHORTS for e in EXTENTS},
         "both cohorts and both extents")
    networks = np.asarray(prepared["full_network_codes"], dtype=np.int64)
    types = np.asarray(prepared["full_type_codes"], dtype=np.int64)
    positions = np.asarray(prepared["cortical_positions_zero_based"], dtype=np.int64)
    spins = np.asarray(prepared["spin_indices_zero_based"])
    need(networks.shape == types.shape == (402,), "full wall-inclusive atlas domains")
    need(positions.tolist() == list(range(1, 201)) + list(range(202, 402)),
         "native-joined original cortical positions")
    need(spins.shape == (402, 10000) and spins.dtype.kind in "iu", "complete integer spin matrix")
    need(np.array_equal(np.sort(spins, axis=0), np.repeat(np.arange(402)[:, None], 10000, axis=1)),
         "every spin is a complete permutation")
    need((spins[:201] < 201).all() and (spins[:201] >= 0).all()
         and (spins[201:] >= 201).all() and (spins[201:] < 402).all(), "hemisphere preservation")
    need(set(networks[positions].tolist()) == set(NETWORK_CODES), "all seven cortical networks")
    need(set(types[positions].tolist()) == set(TYPE_CODES), "all six cortical types")
    records, diagnostics = [], []
    for cohort in COHORTS:
        for extent in EXTENTS:
            signed = np.asarray(prepared["matrices"][cohort + ":" + extent], dtype=np.float64)
            need(signed.shape == (400, 400) and np.isfinite(signed).all(), "complete finite400 cortical block")
            matrix = np.abs(signed).copy()
            np.fill_diagonal(matrix, 0.0)
            for direction in DIRECTIONS:
                nulls, groups = null_profiles(matrix, networks, types, positions, spins,
                                             direction, policy["null_protocol"], deadline)
                diagnostics.append({"cohort": cohort, "extent": extent, "direction": direction,
                                    "literal_null_group_diagnostics": groups})
                for network in NETWORK_CODES:
                    strengths, counts = empirical_profile(matrix, networks[positions], types[positions],
                                                           network, direction)
                    empirical = kl_uniform_to_profile(strengths, "strict")
                    null_kl = [x["KL_bits"] for x in nulls[network]]
                    tail = strict_lower_tail(empirical["KL_bits"], null_kl)
                    records.append({"key": [cohort, extent, direction, network], "partner_counts": counts,
                                    "empirical": empirical, "all10000_null_profiles": nulls[network],
                                    "historical_strict_tail": tail,
                                    "plus_one_tail_separate": plus_one_tail_separate(empirical["KL_bits"], null_kl),
                                    "null_protocol": policy["null_protocol"]})
    need([tuple(x["key"]) for x in records] == list(KEYS), "complete ordered56-cell output")
    finite = all(x["historical_strict_tail"]["status"] == "FINITE" for x in records)
    return {"schema": "dmn-complete-functional-balance56-v1", "records": records,
            "complete_cells": 56, "spins_each": 10000, "all_cells_finite": finite,
            "status": "COMPLETE_FINITE56" if finite else "COMPLETE56_WITH_UNDEFINED_RESULTS",
            "diagnostics": diagnostics, "biological_units": "two cohort aggregates",
            "independent_participant_count": None, "full_paper_reproduction": False,
            "frontier_improvement_established": False, "benchmark_count": 1}


def compare_complete_reference(candidate, reference, tolerance):
    """Require every empirical and null output; paper-table copying is insufficient."""
    need([tuple(x["key"]) for x in candidate["records"]] == list(KEYS), "candidate complete56 order")
    need([tuple(x["key"]) for x in reference["records"]] == list(KEYS), "reference complete56 order")
    need(tolerance["selected_before_results"] is True, "tolerance cannot be chosen after observing a run")
    absolute, relative = tolerance["absolute"], tolerance["relative"]
    need(0 <= absolute <= 1e-6 and 0 <= relative <= 1e-6, "declared numerical comparison tolerance")
    differences = []

    def scalar_matches(a, e):
        if a is None or e is None:
            return a is None and e is None
        if math.isnan(a) or math.isnan(e):
            return math.isnan(a) and math.isnan(e)
        if math.isinf(e) or math.isinf(a):
            return a == e
        return math.isclose(a, e, rel_tol=relative, abs_tol=absolute)

    for actual, expected in zip(candidate["records"], reference["records"]):
        need(actual["null_protocol"] == expected["null_protocol"], "same declared null method")
        need(len(actual["all10000_null_profiles"]) == len(expected["all10000_null_profiles"]) == 10000,
             "no missing null columns")
        for label, aa, ee in [("empirical", actual["empirical"], expected["empirical"])] + [
                ("spin:%d" % (i + 1), x, y) for i, (x, y) in enumerate(zip(
                    actual["all10000_null_profiles"], expected["all10000_null_profiles"]))]:
            if aa["status"] != ee["status"]:
                differences.append({"key": actual["key"], "field": label, "reason": "undefined/status disagreement"})
                continue
            if not scalar_matches(aa["KL_bits"], ee["KL_bits"]):
                differences.append({"key": actual["key"], "field": label, "reason": "KL disagreement"})
            for vector_name in ("strengths", "probabilities"):
                av, ev = aa[vector_name], ee[vector_name]
                if av is None or ev is None:
                    same = av is None and ev is None
                else:
                    same = len(av) == len(ev) == 6 and all(scalar_matches(a, e) for a, e in zip(av, ev))
                if not same:
                    differences.append({"key": actual["key"], "field": label + ":" + vector_name,
                                        "reason": "complete six-type profile disagreement"})
        if actual["historical_strict_tail"] != expected["historical_strict_tail"]:
            differences.append({"key": actual["key"], "field": "strict_tail", "reason": "tail/count disagreement"})
    return {"complete": True, "all56_and560000_null_profiles_match": not differences,
            "differences": differences, "scientific_improvement_score": None,
            "limitation": "Numerical agreement does not establish independent implementation, contamination freedom, rights or frontier improvement."}
