"""Exact selected configuration graph and cost algebra, not execution evidence."""
import hashlib
import itertools
import json
from .core import QualificationError
from .selection import FAMILIES

CONDITIONS = ("original", "spatial_scrambled", "C_only")
VIEW_ORDER = ("N", "C", "NC")
N = 9532


def grid():
    """Return exactly the frozen REFERENCE_GRID.json blocks, without aliases.

    R precedes rank, then numeric parameter axes. max_features choices have stable
    semantic order sqrt then full; sqrt(d)<=d. Do not collapse cells when dimension
    makes the two counts coincide. Inapplicable axes are None.
    """
    blocks = []
    global_index = 0
    for condition in CONDITIONS:
        views = ("C",) if condition == "C_only" else VIEW_ORDER
        for view in views:
            for family in FAMILIES:
                reps = (None,) if view == "C" else (("rms",) if family == "centroid" else ("raw", "rms"))
                ranks = (64, 256) if view != "C" and family in ("rbf_ovr_svm", "extra_trees") else (None,)
                lambdas = {"ridge": (1e-6, 1e-4, 1e-2, 1, 100),
                           "linear_ovr_svm": (1e-5, 1e-3, 1e-1, 10),
                           "rbf_ovr_svm": (1e-4, 1e-2, 1)}.get(family, (None,))
                gammas = (0.1, 1, 10) if family == "rbf_ovr_svm" else (None,)
                leaves = (1, 5) if family == "extra_trees" else (None,)
                feature_rules = ("floor_sqrt_d", "all_d") if family == "extra_trees" else (None,)
                cells = []
                for index, (rep, rank, lam, gamma, leaf, features) in enumerate(itertools.product(
                        reps, ranks, lambdas, gammas, leaves, feature_rules)):
                    cell = {"index": index, "representation": rep, "pca_rank": rank}
                    if lam is not None:
                        cell["lambda"] = lam
                    if gamma is not None:
                        cell["gamma_factor"] = gamma
                    if family == "extra_trees":
                        cell.update(min_samples_leaf=leaf, max_features_rule=features, trees=256)
                    cells.append(cell)
                    global_index += 1
                blocks.append({"condition": condition, "view": view,
                               "family": family, "H": len(cells), "configurations": cells})
    if len(blocks) != 35 or global_index != 353:
        raise QualificationError("complete graph cardinality invariant failed")
    return blocks


def _block_counts(h):
    return {"inner_base_bundles": 156 * h, "outer_refit_bundles": 13,
            "base_bundles": 156 * h + 13, "raw_prediction_vectors": (12 * h + 1) * N,
            "base_training_record_exposures": (132 * h + 12) * N,
            "calibrator_fits": 13, "temperature_objective_passes": 13 * 17,
            "calibration_training_rows": 12 * N, "temperature_loss_rows": 204 * N,
            "final_calibrated_vectors": N}


def _digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                         allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def workload():
    blocks = grid()
    counted = [{"block_index": index, **{k: b[k] for k in ("condition", "view", "family", "H")},
                **_block_counts(b["H"])} for index, b in enumerate(blocks)]
    totals = {k: sum(b[k] for b in counted) for k in _block_counts(1)}
    families = {f: {"H": sum(b["H"] for b in counted if b["family"] == f),
                    "blocks": sum(b["family"] == f for b in counted),
                    **{k: sum(b[k] for b in counted if b["family"] == f) for k in totals}}
                for f in FAMILIES}
    conditions = {c: {"H": sum(b["H"] for b in counted if b["condition"] == c),
                      "blocks": sum(b["condition"] == c for b in counted),
                      **{k: sum(b[k] for b in counted if b["condition"] == c) for k in totals}}
                  for c in CONDITIONS}
    reference = {"configurations": sum(b["H"] for b in counted), "blocks": len(counted), **totals,
                 "ridge_shared_25_output_solves": families["ridge"]["base_bundles"],
                 "linear_binary_ovr_optimizations": 25 * families["linear_ovr_svm"]["base_bundles"],
                 "rbf_binary_ovr_optimizations": 25 * families["rbf_ovr_svm"]["base_bundles"],
                 "extra_trees_constructed": 256 * families["extra_trees"]["base_bundles"],
                 "centroid_class_aggregations": 25 * families["centroid"]["base_bundles"],
                 "ovr_head_row_exposures": 25 * (families["linear_ovr_svm"]["base_training_record_exposures"] + families["rbf_ovr_svm"]["base_training_record_exposures"])}
    reference["binary_ovr_optimizations"] = reference["linear_binary_ovr_optimizations"] + reference["rbf_binary_ovr_optimizations"]
    contexts = 2 * 3 * 13 * 3
    candidate = {"policies": 1, "arms": 2, "conditions": 3, "outer_folds": 13, "repetitions": 3,
                 "contexts": contexts, "contexts_per_arm": contexts // 2, "logical_phases": 2 * contexts,
                 "complete_oof_panels": 18, "final_case_vectors": 18 * N,
                 "probability_components": 18 * N * 25, "biological_people": 13}
    caps = {"model_requests": 512, "input_tokens": 2097152, "generated_tokens": 131072,
            "tool_invocations": 10000, "wall_seconds": 172800, "cpu_core_seconds": 2764800,
            "simultaneous_cpu_cores": 16, "private_memory_bytes": 64 * 2**30,
            "writable_scratch_bytes": 512 * 2**30, "gpu_devices": 0}
    summed = {k: contexts * caps[k] for k in ("model_requests", "input_tokens", "generated_tokens",
                                            "tool_invocations", "wall_seconds", "cpu_core_seconds")}
    result = {"schema": "n073_full_workload_v1", "status": "prospective_algebra_no_execution",
        "records": N, "classes": 25, "available_person_label_cells": 300,
        "reference": reference, "blocks": counted, "families": families, "conditions": conditions,
        "preprocessing": {"maxrank256_pca_fits": 4 * 13 * 13 * 2,
            "pca_training_record_exposures": 4 * 2 * (132 + 12) * N,
            "neural_scale_fits": 1352, "C_scale_fits": 845, "pca_score_scale_fits": 2704,
            "neural_scale_training_rows": 8 * 144 * N,
            "C_scale_training_rows": 5 * 144 * N,
            "pca_score_scale_training_rows": 16 * 144 * N,
            "training_gram_builds": (27 * 2 + 3) * 13 * 13,
            "scrambled_records": 13 * N, "scrambled_full_bank_passes": 13},
        "anchors": {"prior_aggregations": 3 * 13, "optimized_fits": 0, "calibrators": 0,
            "prior_training_record_exposures": 3 * 12 * N, "materialized_case_vectors": 2 * 3 * N},
        "candidate": candidate, "per_context_caps": caps, "summed_candidate_ceilings": summed,
        "grid_sha256": _digest(blocks),
        "cache_rule": "same outer/condition/view/exact-training-subset/R/spec/data/parameter parents only",
        "units_warning": "nested units overlap; counts are not benchmarks, memory measurements or FLOPs"}
    result["work_count_sha256"] = _digest(result)
    return result


def resource_algebra(*, D, person_counts, equal_support_pairs, index_bytes=8, concurrency=1,
                     authenticated_compressed_bytes=0, original_decoded_bytes=0,
                     model_cache_bytes=0, retained_log_output_bytes=0, peak_staging_bytes=0):
    """Evaluate symbols from explicit prospective inputs; does not admit geometry.

    Complete person counts are required to expose all pair/fit/storage costs. Exact
    n_s membership is authenticated elsewhere. Unknown measured terms may remain0
    only as explicit lower-bound placeholders, never as capacity qualification.
    """
    ints = (D, equal_support_pairs, index_bytes, concurrency, authenticated_compressed_bytes,
            original_decoded_bytes, model_cache_bytes, retained_log_output_bytes, peak_staging_bytes)
    if any(type(x) is not int or x < 0 for x in ints) or D < 256 or index_bytes not in (4, 8) or concurrency < 1:
        raise QualificationError("invalid prospective resource dimensions")
    if (len(person_counts) != 13 or any(type(x) is not int or x <= 0 for x in person_counts.values())
            or sum(person_counts.values()) != N):
        raise QualificationError("13 complete person counts summing9532 required")
    pairs = (N*N - sum(n*n for n in person_counts.values())) // 2
    if not 0 <= equal_support_pairs <= pairs:
        raise QualificationError("equal-support pair count outside complete support")
    folds = {}
    for person, n_o in sorted(person_counts.items()):
        n_train = N - n_o
        folds[person] = {"outer_training_rows": n_train, "query_rows": n_o,
            "full_feature_matrix_bytes": 8 * n_train * D,
            "outer_dense_gram_bytes": 8 * n_train*n_train,
            "oof_score_bank_bytes_per_H": 8 * 25 * n_train,
            "all_outer_block_oof_bank_bytes_if_retained": 8 * 25 * 353 * n_train,
            "inner_training_rows": {v: N - n_o - n_v for v, n_v in person_counts.items() if v != person}}
    canonical = 8*N*D
    gram_entries = 57 * sum(f["outer_training_rows"]**2 + sum(n*n for n in f["inner_training_rows"].values())
                            for f in folds.values())
    return {"status": "symbolic_inputs_evaluated_not_resource_admission", "D": D,
        "original_numeric_export_bytes": canonical, "one_scrambled_bank_bytes": canonical,
        "all13_scrambled_banks_bytes": 13 * canonical,
        "original_plus13_scrambled_numeric_bytes": 14 * canonical,
        "scramble_minimum_voxel_placements": 13*N*D,
        "scramble_nominal_value_read_write_bytes": 13*16*N*D,
        "one_permutation_index_bank_bytes": index_bytes*N*D,
        "all13_permutation_index_banks_bytes": 13*index_bytes*N*D,
        "C_numeric_matrix_bytes": 8*105*N, "one_pca_loading_bytes": 8*D*256,
        "all1352_pca_loading_bytes_if_retained": 1352*8*D*256,
        "all9633_training_gram_numeric_entries": gram_entries,
        "all_training_grams_numeric_bytes_if_retained": 8*gram_entries,
        "candidate_final_probability_numeric_bytes": 8*25*18*N,
        "reference_final_probability_numeric_bytes": 8*25*35*N,
        "anchor_final_probability_numeric_bytes": 8*25*6*N,
        "all_reference_raw_score_numeric_bytes_if_materialized": 8*25*(12*353+35)*N,
        "candidate_parser_total_admitted_stream_byte_ceiling": 234*16*2**20,
        "catalogue_advertised_compressed_bytes_not_authenticated": 29160227222,
        "all_unordered_record_pairs": N*(N-1)//2, "cross_person_pairs": pairs,
        "declared_source_cross_person_pairs": 41901550,
        "given_counts_match_declared_pair_count": pairs == 41901550,
        "equal_support_pairs": equal_support_pairs,
        "full_value_digest_inspection_bytes": 8*N*D,
        "near_pair_nominal_value_touches_bytes": 16*D*equal_support_pairs,
        "retained_bitpacked_support_bytes": N*((D+7)//8),
        "candidate_private_memory_ceiling_bytes": concurrency*64*2**30,
        "candidate_live_scratch_ceiling_bytes": concurrency*512*2**30,
        "candidate_simultaneous_core_ceiling": concurrency*16,
        "provided_measured_terms": {"B_auth": authenticated_compressed_bytes, "U": original_decoded_bytes,
            "M": model_cache_bytes, "L": retained_log_output_bytes, "W": peak_staging_bytes},
        "provided_terms_sum_plus_original_export_bytes": sum((authenticated_compressed_bytes,
            original_decoded_bytes, model_cache_bytes, retained_log_output_bytes, peak_staging_bytes, canonical)),
        "folds": folds,
        "additional_costs": ["kernel train-validation and train-query evaluations", "solver passes/copies",
            "PCA backend scratch", "tree/support-vector storage", "reference tool copies",
            "candidate subprocess logs", "duplicate adjudication", "metadata and source staging"],
        "qualification": "capacity remains unqualified;0 measured terms mean unknown lower bounds"}
