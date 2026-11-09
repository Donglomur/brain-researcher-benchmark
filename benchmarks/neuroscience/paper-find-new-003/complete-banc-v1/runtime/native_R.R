# Load definitions from native_R_bridge.R and native_R_execution.R in the same environment before
# calling banc_run_influence_wire / banc_run_sensory_wires. The caller authenticates
# all three files through RUNTIME_MANIFEST.json; no source/file operation occurs at import.
# Concrete native producers. Sourcing defines functions only; it runs no job.
# Native/package/authentic execution requires a separate qualified runner.

banc_need <- function(ok, message) {
  if (!isTRUE(ok)) stop(message, call. = FALSE)
}

banc_source_pinned <- function(root, member, envir) {
  banc_need(is.character(member$path) && length(member$path) == 1L &&
              !grepl("(^/|(^|/)\\.\\.(/|$)|\\\\)", member$path), "relative source member")
  path <- file.path(root, member$path)
  banc_need(file.info(path)$size == member$bytes, "exact native source extent")
  banc_need(identical(digest::digest(file = path, algo = "sha256", serialize = FALSE),
                     member$sha256), "exact native source hash")
  # Parent authenticated source staging and native process enclosure remain
  # required: this source operation alone is not a race-proof sandbox.
  sys.source(path, envir = envir, keep.source = TRUE)
}

banc_native_influence <- function(job, source_root, source_members, execution_context = NULL) {
  banc_need(job$operator_branch %in% c("captured_R_unsigned_literal",
             "captured_R_signed_labelled_literal", "R_to_Python_literal_wrapper"),
            "explicit literal R/wrapper branch")
  banc_need(is.data.frame(job$metadata) && is.data.frame(job$edges),
            "complete original native tables")
  banc_need(is.character(job$metadata$root_id), "literal string root_id")
  banc_need(identical(job$edge_indices_base, "one") &&
              all(job$selected_edge_indices >= 1L & job$selected_edge_indices <= nrow(job$edges)),
            "explicit complete selected graph rows, one-based R indices")
  banc_need(!endsWith(job$graph_variant, "/parallel_rebuild_default_global") || job$count_thresh == 5,
            "original PSOCK loop hardcodes count_thresh=5")
  job$edges <- job$edges[job$selected_edge_indices, , drop = FALSE]
  # meta$id is neither synthesized nor replaced by root_id. The signed R
  # count mutation, norm matrix and absolute response remain in exact source.
  e <- new.env(parent = globalenv())
  if (job$operator_branch == "R_to_Python_literal_wrapper") {
    banc_require_wrapper_execution(job, execution_context)
    banc_source_pinned(source_root, source_members$wrapper, e)
    calculator <- e$influence_calculator_py(edgelist_simple = job$edges,
                       meta = job$metadata, signed = job$signed,
                       count_thresh = job$count_thresh)
    calculate <- function(ids, silenced) {
      # The original wrapper owns its argument/return conversion. No missing
      # inhibitory set or id alias is repaired by the benchmark.
      banc_need(length(silenced) == 0L, "wrapper silencing signature requires source qualification")
      e$calculate_influence_py(calculator, ids)
    }
  } else {
    banc_source_pinned(source_root, source_members$R, e)
    args <- list(edgelist_simple = job$edges, meta = job$metadata,
                 signed = job$operator_branch == "captured_R_signed_labelled_literal",
                 count_thresh = job$count_thresh, const = job$const)
    if (!is.null(job$neg_neurotransmitters))
      args$neg_neurotransmitters <- job$neg_neurotransmitters
    calculator <- do.call(e$influence_calculator_r, args)
    calculate <- function(ids, silenced)
      calculator$calculate_influence(ids, silenced_neurons = silenced)
  }
  responses <- lapply(job$seed_requests, function(request) {
    value <- calculate(request$seed_ids, request$silenced_ids)
    list(seed = request$seed, response = value)
  })
  list(responses = responses, operator_branch = job$operator_branch,
       native_executed = TRUE, historical_reference_qualified = FALSE,
       residual_qualified = FALSE, scientific_qualification = FALSE)
}

banc_native_sensory <- function(job, source_root, source_members, execution_contexts = NULL) {
  # Actual full threshold/native-response/normalization/matrix producer.
  # It requires complete original sensory/effector memberships and maps;
  # frozen GCS and manuscript annotations remain separate source namespaces.
  banc_need(identical(as.integer(job$thresholds), c(3L, 5L, 10L)) &&
              length(job$seed_order) == 19L && length(job$target_order) == 17L &&
              length(job$matched_groups) == 14L, "complete 17x19x3 source/extension scope")
  banc_need(is.list(job$native_jobs) && length(job$native_jobs) == 3L, "all3 source-owned typed native jobs")
  banc_need(!endsWith(job$native_jobs[[1L]]$graph_variant, "/parallel_rebuild_default_global"),
            "original parallel source cannot supply distinct3/5/10 outputs")
  if (is.null(execution_contexts)) execution_contexts <- rep(list(NULL), 3L)
  banc_need(is.list(execution_contexts) && length(execution_contexts) == 3L, "all3 threshold execution contexts")
  e <- new.env(parent = globalenv())
  banc_source_pinned(source_root, source_members$normalizer, e)
  panels <- lapply(job$thresholds, function(threshold) {
    threshold_index <- match(threshold, job$thresholds)
    native_job <- job$native_jobs[[threshold_index]]
    banc_need(native_job$count_thresh == threshold, "selected threshold-specific native request")
    native <- banc_native_influence(native_job, source_root, source_members,
      execution_context = execution_contexts[[threshold_index]])
    rows <- lapply(seq_along(native$responses), function(k) {
      response <- native$responses[[k]]$response
      request <- native_job$seed_requests[[k]]
      # Complete response support is checked before filtering to effectors.
      banc_need(identical(as.character(response$id), as.character(job$ordered_nodes_by_threshold[[as.character(threshold)]])),
                "complete threshold-specific native node support")
      response <- response[response$id %in% job$target_ids, , drop = FALSE]
      response$seed <- request$seed
      response$influence_original <- response[[job$score_column]]
      response$influence_norm_original <- response$influence_original / length(unique(request$seed_ids))
      response
    })
    rows <- data.table::rbindlist(rows, fill = TRUE)
    rows <- dplyr::left_join(rows, job$effector_lookup, by = "id")
    original_seed <- rows$seed
    mapped <- job$seed_map[original_seed]
    rows$seed <- ifelse(original_seed %in% names(job$seed_map), mapped, original_seed)
    original_target <- rows$target
    mapped <- job$target_map[original_target]
    rows$target <- ifelse(original_target %in% names(job$target_map), mapped, original_target)
    rows <- rows[rows$seed %in% job$seed_order & rows$target %in% job$target_order, , drop = FALSE]
    normalized <- e$calculate_influence_norms(rows)
    # Preserve support before the original plot's zero filling. The full
    # 17x19 axes are not shrunk to the groups that happened to be observed.
    mat <- matrix(NA_real_, nrow = 17L, ncol = 19L,
                  dimnames = list(job$target_order, job$seed_order))
    for (target in job$target_order) for (seed in job$seed_order) {
      values <- normalized$influence_log_minmax[normalized$target == target & normalized$seed == seed]
      if (length(values)) mat[target, seed] <- mean(values, na.rm = TRUE)
    }
    supported <- is.finite(mat)
    plotted <- mat; plotted[!supported] <- 0
    list(threshold = threshold, normalized = normalized, values = mat,
         supported = supported, original_plot_zero_filled = plotted,
         native_branch = native_job$operator_branch)
  })
  list(panels = panels, cells = 969L, primary_threshold = 5L,
       extension_thresholds = c(3L, 10L), biological_units = 1L,
       historical_snapshot_equivalence = FALSE, scientific_qualification = FALSE)
}

banc_native_statistics <- function(job, source_root, source_members) {
  e <- new.env(parent = globalenv())
  # Helpers use literal package behavior, options, contrasts, locale, grouping
  # and RNG. Every one must be in the native execution receipt, not guessed.
  e$`%>%` <- magrittr::`%>%`
  banc_source_pinned(source_root, source_members$functions, e)
  recipe <- job$recipe
  if (identical(recipe, "original_influence_normalization")) {
    value <- e$calculate_influence_norms(job$rows, const = job$const,
                                        quantile = job$quantile)
  } else if (identical(recipe, "original_anova_summary")) {
    # Includes the source's large-design analytic branch, contrast behavior,
    # and unreplicated permutation branch. It is not silently replaced by a
    # generic sum-contrast ANOVA implementation.
    value <- e$write_anova_summary(job$rows, job$out_path,
              perms = job$perms, seed = job$seed, alpha = job$alpha,
              use_sum_to_zero = job$use_sum_to_zero,
              force_treatment = job$force_treatment)
  } else if (identical(recipe, "original_ks_summary")) {
    value <- e$write_ks_summary(job$rows, job$out_path,
              type_col = job$type_col, value_col = job$value_col,
              ref_type = job$ref_type, adjust_method = job$adjust_method,
              alpha = job$alpha, p_floor = job$p_floor)
  } else if (identical(recipe, "original_nonparam_summary")) {
    value <- do.call(e$write_nonparam_summary, job$arguments)
  } else if (identical(recipe, "sensory_diagonal_wilcoxon_greater")) {
    value <- stats::wilcox.test(job$diagonal, job$off_diagonal, alternative = "greater")
  } else if (identical(recipe, "original_source_binomial_greater")) {
    # This probability is the literal source assumption, NOT a graph null.
    value <- stats::binom.test(job$successes, job$total, p = 0.5,
                              alternative = "greater")
  } else if (identical(recipe, "sensory_locality_column_label_permutation")) {
    hm_loc <- job$hm[job$matched_rows, , drop = FALSE]
    banc_need(nrow(hm_loc) > 1L, "literal source permutation applicability")
    sh_loc <- sweep(hm_loc, 1, pmax(rowSums(hm_loc), job$eps_share), "/")
    local_mat <- outer(rownames(hm_loc), colnames(hm_loc), "==")
    df_pairs <- data.frame(share = as.numeric(sh_loc),
      local = factor(as.numeric(local_mat), levels = c(0, 1), labels = c("other", "local")))
    F_obs <- as.numeric(summary(stats::aov(share ~ local, data = df_pairs))[[1]][["F value"]][1])
    set.seed(1)
    F_null <- replicate(999L, {
      perm_cols <- sample(colnames(hm_loc))
      local_perm <- factor(as.numeric(outer(rownames(hm_loc), perm_cols, "==")),
                    levels = c(0, 1), labels = c("other", "local"))
      dfp <- data.frame(share = as.numeric(sh_loc), local = local_perm)
      as.numeric(summary(stats::aov(share ~ local, data = dfp))[[1]][["F value"]][1])
    })
    value <- list(F_obs = F_obs, F_null = F_null,
                  p_perm = (sum(F_null >= F_obs) + 1) / 1000,
                  null_kind = "source_column_label_permutation_not_randomized_graph")
  } else stop("unknown/unlocated native statistical producer; no fallback")
  list(value = value, recipe = recipe, R_session = utils::sessionInfo(),
       options = options(c("contrasts", "banc.fast_anova_threshold")),
       locale = Sys.getlocale(), biological_units = 1L,
       conditional_graph_analysis = TRUE, scientific_qualification = FALSE)
}

banc_original_figure <- function(job, source_root, source_members) {
  # Direct exact original producer, not a user-supplied callable. This entry
  # cannot be called until ALL original context, sources and upstream raw-to-
  # product receipts have been audited. Cached answers are not raw evidence.
  banc_need(isTRUE(job$complete_source_context_qualified) &&
            isTRUE(job$offline_external_enclosure_qualified) &&
            isTRUE(job$upstream_raw_to_product_receipts_qualified),
            "original figure producer closure and offline runner unqualified")
  banc_need(job$script %in% names(source_members$figure_scripts), "closed original figure source")
  script <- source_members$figure_scripts[[job$script]]
  e <- new.env(parent = globalenv())
  # Original startup/source/file paths and package loading remain unchanged.
  # The externally staged working tree must contain their full pinned closure.
  banc_source_pinned(source_root, script, e)
  list(script = job$script, producer_executed = TRUE,
       output_collection_required = TRUE, scientific_qualification = FALSE)
}
