calculate_influence_norms <- function(influence.df,
                                      const = -24,
                                      quantile = FALSE){
  # Use data.table for fast grouped operations on large datasets
  has_target <- "target" %in% colnames(influence.df)
  inf.threshold <- exp(const)

  dt <- data.table::as.data.table(influence.df)
  if (!has_target) dt[, target := id]
  if (!"influence_original" %in% names(dt)) dt[, influence_original := influence]
  if (!"influence_norm_original" %in% names(dt)) dt[, influence_norm_original := influence_norm]

  # Compute no_seeds from ratio of original to norm_original
  dt[, no_seeds := data.table::fifelse(is.na(influence_original / influence_norm_original),
                           1, influence_original / influence_norm_original)]

  # Aggregate per (target, seed): sum influence, then deduplicate
  dt[, `:=`(
    influence_per_seed_sum = sum(influence_original, na.rm = TRUE)
  ), by = .(target, seed)]
  dt <- unique(dt, by = c("target", "seed"), fromLast = FALSE)

  # Count unique IDs per target group AFTER deduplication
  # (when target==id, this is always 1 — matching old dplyr behavior)
  dt[, no_targets := data.table::uniqueN(id), by = target]

  # Compute normalized values
  dt[, `:=`(
    influence = pmax(influence_per_seed_sum, inf.threshold),
    influence_norm = pmax(influence_per_seed_sum / (no_seeds[1] * no_targets[1]),
                         inf.threshold)
  ), by = .(target, seed)]

  # Log transforms
  dt[, `:=`(
    influence_norm_log = log(influence_norm) - const,
    influence_log = log(influence / no_targets) - const
  )]
  dt[is.na(influence), influence_log := 0]
  dt[, influence_per_seed_sum := NULL]

  # Quantile (per-seed)
  if (!is.null(quantile)) {
    dt[, influence_quantile := signif(stats::quantile(influence_original, quantile, na.rm = TRUE), 4),
       by = seed]
  }

  # Min-max normalization by target and by seed in two passes
  dt[, `:=`(
    influence_norm_log_minmax = {
      mn <- min(influence_norm_log, na.rm = TRUE); mx <- max(influence_norm_log, na.rm = TRUE)
      if (mx == mn) rep(0, .N) else (influence_norm_log - mn) / (mx - mn)
    },
    influence_log_minmax = {
      mn <- min(influence_log, na.rm = TRUE); mx <- max(influence_log, na.rm = TRUE)
      if (mx == mn) rep(0, .N) else (influence_log - mn) / (mx - mn)
    }
  ), by = target]

  dt[, `:=`(
    influence_norm_log_minmax_seed = {
      mn <- min(influence_norm_log, na.rm = TRUE); mx <- max(influence_norm_log, na.rm = TRUE)
      if (mx == mn) rep(0, .N) else (influence_norm_log - mn) / (mx - mn)
    },
    influence_log_minmax_seed = {
      mn <- min(influence_log, na.rm = TRUE); mx <- max(influence_log, na.rm = TRUE)
      if (mx == mn) rep(0, .N) else (influence_log - mn) / (mx - mn)
    }
  ), by = seed]

  # Round to 4 significant figures
  for (col in c("influence", "influence_log", "influence_norm", "influence_norm_log",
                "influence_log_minmax", "influence_norm_log_minmax",
                "influence_log_minmax_seed", "influence_norm_log_minmax_seed")) {
    if (col %in% names(dt)) data.table::set(dt, j = col, value = signif(dt[[col]], 4))
  }

  # Clean up
  dt[, c("no_seeds", "no_targets") := NULL]
  if (!has_target) dt[, target := NULL]

  # Convert back to tibble
  tibble::as_tibble(dt)
}
