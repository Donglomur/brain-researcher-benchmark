# Newly authored owner-side artifact snapshots; not recovered author code.
# No fitting, source evaluation, or package installation. Numeric projections use
# the independently accepted versioned forest and BMA native-field maps only.

artifact_need <- function(ok, message) {
  if (!isTRUE(ok)) stop(message, call. = FALSE)
}

artifact_specs <- function() list(
  quest_self = list(model = "meta_questSelf", subset = "dfQuestSelf",
    effect = "questSelfRating", dl_n = "sample size quest",
    bayes_input = "dfQuestSelf_conv", bayes_model = "Bmeta_questSelf"),
  amy_quest = list(model = "meta_amyQuest", subset = "dfAmyQuest",
    effect = "amyQuestCorr", dl_n = "sample size quest",
    bayes_input = "dfAmyQuest_conv", bayes_model = "Bmeta_amyQuest"),
  amy_self = list(model = "meta_amySelf", subset = "dfAmySelf",
    effect = "amySelfRating", dl_n = "sample size rating",
    bayes_input = "dfAmySelf_conv", bayes_model = "Bmeta_amySelf"))

artifact_object <- function(author_env, name) {
  artifact_need(is.environment(author_env) &&
    exists(name, envir = author_env, inherits = FALSE), paste("missing author object", name))
  value <- get(name, envir = author_env, inherits = FALSE)
  artifact_need(!is.null(value), paste("null author object", name))
  value
}

artifact_is_link <- function(path) {
  destination <- Sys.readlink(path)
  !is.na(destination) && nzchar(destination)
}

artifact_path <- function(output_root, relative) {
  artifact_need(is.character(output_root) && length(output_root) == 1L &&
    !is.na(output_root) && dir.exists(output_root) && !artifact_is_link(output_root),
    "existing nonsymlink output root required")
  artifact_need(is.character(relative) && length(relative) == 1L && !is.na(relative) &&
    !grepl("(^/|\\\\|(^|/)\\.\\.?(/|$))", relative), "internal relative artifact path required")
  root <- normalizePath(output_root, mustWork = TRUE)
  parts <- strsplit(relative, "/", fixed = TRUE)[[1L]]
  artifact_need(all(nzchar(parts)), "empty artifact path component")
  directory <- root
  if (length(parts) > 1L) for (part in parts[-length(parts)]) {
    directory <- file.path(directory, part)
    artifact_need(!artifact_is_link(directory), "symlink artifact directory forbidden")
    if (!dir.exists(directory))
      artifact_need(dir.create(directory, showWarnings = FALSE), "cannot create artifact directory")
    artifact_need(dir.exists(directory) && !artifact_is_link(directory), "unsafe artifact directory")
  }
  target <- file.path(directory, parts[length(parts)])
  artifact_need(!file.exists(target) && !artifact_is_link(target), "artifact already exists")
  target
}

artifact_write <- function(path, writer) {
  artifact_need(!file.exists(path) && !artifact_is_link(path), "artifact already exists")
  temporary <- tempfile(pattern = ".nider-pending-", tmpdir = dirname(path))
  on.exit(unlink(temporary), add = TRUE)
  writer(temporary)
  artifact_need(file.exists(temporary) && !artifact_is_link(temporary), "artifact writer produced no file")
  # A same-filesystem hard link publishes complete bytes without replacing a prior file.
  artifact_need(isTRUE(file.link(temporary, path)), "artifact publication failed without replacement")
  invisible(path)
}

artifact_rds <- function(value, path) {
  artifact_write(path, function(temporary) saveRDS(value, temporary, version = 3))
}

artifact_numeric_equal <- function(x, y) {
  is.numeric(x) && is.numeric(y) && typeof(x) %in% c("integer", "double") && typeof(y) %in% c("integer", "double") &&
    is.null(dim(x)) && is.null(dim(y)) && identical(as.numeric(x), as.numeric(y))
}

artifact_member <- function(object, key) {
  artifact_need(is.list(object) && key %in% names(object), paste("missing mapped native member", key))
  object[[key]]
}

artifact_numeric_vector <- function(value, extent) {
  artifact_need(is.numeric(value) && typeof(value) %in% c("integer", "double") && is.null(dim(value)) && length(value) == extent,
                "mapped native numeric vector extent")
  artifact_need(exists("numeric_cell", mode = "function"), "frozen numeric_cell helper required")
  list(length = length(value), storage_type = typeof(value),
    names = if (is.null(names(value))) NULL else as.list(names(value)),
    values = lapply(seq_along(value), function(i) numeric_cell(value[[i]])))
}

artifact_numeric_scalar <- function(value) {
  artifact_need(length(value) == 1L && is.null(dim(value)) && (typeof(value) %in% c("integer", "double") ||
    (is.logical(value) && is.na(value))), "mapped native real scalar required")
  numeric_cell(value)
}

artifact_json <- function(value, path) {
  if (!requireNamespace("jsonlite", quietly = TRUE)) stop("jsonlite missing; no installation attempted")
  artifact_write(path, function(temporary)
    jsonlite::write_json(value, temporary, auto_unbox = TRUE, digits = NA, pretty = TRUE, null = "null"))
}

artifact_forest_export <- function(model, contrast, spec, units) {
  extent <- length(units)
  artifact_need(identical(model$sm, "ZCOR") && is.numeric(model$k.all) && typeof(model$k.all) %in% c("integer", "double") &&
    length(model$k.all) == 1L && is.null(dim(model$k.all)) && identical(as.numeric(model$k.all), as.numeric(extent)),
    "native forest scale or k.all mismatch")
  mapped <- c("cor", "n", "TE", "seTE", "lower", "upper", "w.common", "w.random")
  vectors <- lapply(mapped, function(key) artifact_numeric_vector(artifact_member(model, key), extent))
  names(vectors) <- mapped
  list(schema = "nider_original_forest_native_vectors_v1", contrast = contrast,
    native_model = spec$model, source_order = "unchanged_native_and_full120_membership_order",
    membership = units, studlab = as.list(artifact_member(model, "studlab")),
    scales = list(cor = "native_input_Pearson_r", n = "source_sample_size",
      TE = "Fisher_z", seTE = "Fisher_z", lower = "Fisher_z", upper = "Fisher_z",
      w.common = "raw_native_weight_not_percent", w.random = "raw_native_weight_not_percent"),
    vectors = vectors, transformation_performed = FALSE)
}

artifact_bayes_export <- function(model, contrast, spec) {
  artifact_need(exists("numeric_cell", mode = "function"), "frozen numeric_cell helper required")
  inclusion <- artifact_member(model, "inclusion")
  include <- artifact_member(inclusion, "include")
  artifact_need(is.numeric(include) && typeof(include) %in% c("integer", "double") && is.null(dim(include)) &&
    identical(as.numeric(include), c(2, 4)), "original effect-inclusion positions required")
  scalar_names <- c("incl.BF", "incl.prior", "incl.posterior")
  scalars <- lapply(scalar_names, function(key) artifact_numeric_scalar(artifact_member(inclusion, key)))
  names(scalars) <- scalar_names
  top_names <- c("prior_models", "posterior_models", "logml")
  top_vectors <- lapply(top_names, function(key) artifact_numeric_vector(artifact_member(model, key), 4L))
  names(top_vectors) <- top_names
  matrix <- artifact_member(model, "BF")
  artifact_need(is.numeric(matrix) && typeof(matrix) %in% c("integer", "double") && is.matrix(matrix) && identical(dim(matrix), c(4L, 4L)),
                "native pairwise BF matrix must remain 4 by 4")
  axes <- dimnames(matrix)
  matrix_export <- list(dimensions = as.list(dim(matrix)), storage_type = typeof(matrix),
    dimension_axis_names = if (is.null(names(axes))) NULL else as.list(names(axes)),
    dimension_labels = if (is.null(axes)) NULL else lapply(axes, function(axis)
      if (is.null(axis)) NULL else as.list(axis)),
    values_by_row = lapply(seq_len(4L), function(i) lapply(seq_len(4L), function(j) numeric_cell(matrix[i, j]))))
  list(schema = "nider_original_bma_native_values_v1", contrast = contrast,
    native_model = spec$bayes_model,
    documented_positional_model_order = as.list(c("fixed_H0", "fixed_H1", "random_H0", "random_H1")),
    inclusion_BF_role = "incl.BF_is_model_averaged_effect_inclusion_BF10_not_pairwise_BF",
    inclusion = c(scalars, list(include = artifact_numeric_vector(include, 2L),
      prior = artifact_numeric_vector(artifact_member(inclusion, "prior"), 4L),
      posterior = artifact_numeric_vector(artifact_member(inclusion, "posterior"), 4L))),
    model_vectors = top_vectors, pairwise_BF = matrix_export,
    native_names_or_absence_preserved = TRUE, numerical_repair_performed = FALSE)
}

artifact_memberships <- function(full120) {
  specs <- artifact_specs()
  artifact_need(is.list(full120) &&
    identical(full120$schema, "nider_extended_reproduction_submission_v1") &&
    identical(full120$task, "PAPER-EXP-20261113-003") &&
    is.list(full120$contrasts) && length(full120$contrasts) == 3L,
    "validated full120 document required")
  ids <- vapply(full120$contrasts, function(row) row$contrast, character(1))
  artifact_need(identical(ids, names(specs)), "original ordered contrast universe required")
  output <- lapply(seq_along(ids), function(i) {
    units <- full120$contrasts[[i]]$membership
    artifact_need(is.list(units) && length(units) >= 1L && length(units) <= 39L,
                  "complete nonempty membership required")
    labels <- vapply(units, function(unit) unit$author_label, character(1))
    sources <- vapply(units, function(unit) unit$source_id, character(1))
    ordinals <- vapply(units, function(unit) {
      artifact_need(is.numeric(unit$retained_row) && length(unit$retained_row) == 1L,
                    "numeric retained row ordinal required")
      as.numeric(unit$retained_row)
    }, numeric(1))
    artifact_need(!anyNA(labels) && all(nzchar(labels)) && !anyDuplicated(labels) &&
      !anyNA(sources) && all(nzchar(sources)) && !anyDuplicated(sources) &&
      !anyNA(ordinals) && all(ordinals == as.integer(ordinals)) &&
      identical(ordinals, sort(unique(ordinals))), "source membership ordering or identity mismatch")
    all_rows <- numeric()
    for (unit in units) {
      rows <- unlist(unit$source_rows, use.names = FALSE)
      artifact_need(is.list(unit$source_rows) && is.numeric(rows) && length(rows) %in% 1:2 &&
        !anyNA(rows) && all(rows == as.integer(rows)) && all(rows >= 1 & rows <= 40) &&
        identical(as.numeric(rows), sort(unique(as.numeric(rows)))) &&
        identical(as.numeric(unit$retained_row), as.numeric(rows[1L])) &&
        (length(rows) == 2L) == identical(unit$source_id, "Morawetz2016b") &&
        identical(unit$n_column, specs[[ids[i]]]$dl_n), "source row lineage or DL n column mismatch")
      all_rows <- c(all_rows, rows)
    }
    artifact_need(!anyDuplicated(all_rows), "reused source row ordinal")
    units
  })
  names(output) <- ids
  output
}

artifact_subset <- function(author_env, spec, units) {
  subset <- artifact_object(author_env, spec$subset)
  labels <- vapply(units, function(unit) unit$author_label, character(1))
  artifact_need(is.data.frame(subset) && nrow(subset) == length(units) &&
    all(c("image name stem", "cleaned_author", spec$effect, "sample size quest", spec$dl_n) %in%
          names(subset)) && identical(subset[["image name stem"]], labels) &&
    identical(subset$cleaned_author, labels), "author subset/source membership alignment")
  subset
}

snapshot_dl <- function(author_env, full120, output_root) {
  if (!requireNamespace("jsonlite", quietly = TRUE)) stop("jsonlite missing; no installation attempted")
  specs <- artifact_specs()
  membership <- artifact_memberships(full120)
  models <- lapply(names(specs), function(contrast) {
    spec <- specs[[contrast]]
    subset <- artifact_subset(author_env, spec, membership[[contrast]])
    model <- artifact_object(author_env, spec$model)
    artifact_need(inherits(model, "metacor") && inherits(model, "meta") &&
      artifact_numeric_equal(model$n, as.numeric(subset[[spec$dl_n]])) &&
      artifact_numeric_equal(model$cor, as.numeric(subset[[spec$effect]])) &&
      identical(model$studlab, subset[["image name stem"]]), "native DL/source subset alignment")
    model
  })
  exports <- lapply(seq_along(models), function(i)
    artifact_forest_export(models[[i]], names(specs)[i], specs[[i]], membership[[i]]))
  relative <- c(paste0("dl/", names(specs), ".rds"), paste0("dl/", names(specs), ".json"), "row_lineage.json")
  paths <- vapply(relative, function(path) artifact_path(output_root, path), character(1))
  for (i in seq_along(models)) artifact_rds(models[[i]], paths[i])
  for (i in seq_along(exports)) artifact_json(exports[[i]], paths[i + 3L])
  ledger <- list(schema = "nider_primary_native_row_lineage_v1",
    task = full120$task, workbook_sha256 = full120$workbook_sha256,
    contrasts = lapply(names(specs), function(contrast) {
      spec <- specs[[contrast]]
      list(contrast = contrast, native_model = spec$model, native_subset = spec$subset,
        dl_n_column = spec$dl_n, bayes_input_object = spec$bayes_input,
        bayes_n_column = "sample size quest",
        bayes_n_choice_authority = "authenticated_original_escalc_expression_not_column_presence",
        membership = membership[[contrast]])
    }))
  artifact_json(ledger, paths[7L])
  invisible(relative)
}

snapshot_table <- function(author_env, output_root) {
  table <- artifact_object(author_env, "outTable")
  expected_columns <- c("Model", "r", "95% CIa", "pa", "k", "N", "tau", "95% CIb", "Q", "df", "pb")
  artifact_need(is.data.frame(table) && identical(dim(table), c(3L, 11L)) &&
    identical(names(table), expected_columns) && all(vapply(table, is.character, logical(1))) &&
    identical(table$Model, c("Rating-Amygdala", "Rating-Questionnaires", "Amygdala-Questionnaires")),
    "original three-row habit table required")
  relative <- c("table1/habit_associations.rds", "table1/habit_associations.csv")
  paths <- vapply(relative, function(path) artifact_path(output_root, path), character(1))
  artifact_rds(table, paths[1L])
  # New CSV serialization of the literal author dataframe; no relabeling or back-transform.
  artifact_write(paths[2L], function(temporary)
    utils::write.csv(table, temporary, row.names = FALSE, fileEncoding = "UTF-8"))
  invisible(relative)
}

snapshot_bayes_input <- function(author_env, contrast, full120, output_root) {
  specs <- artifact_specs()
  artifact_need(is.character(contrast) && length(contrast) == 1L && contrast %in% names(specs),
                "unknown Bayesian contrast")
  spec <- specs[[contrast]]
  membership <- artifact_memberships(full120)[[contrast]]
  subset <- artifact_subset(author_env, spec, membership)
  converted <- artifact_object(author_env, spec$bayes_input)
  artifact_need(is.data.frame(converted) && nrow(converted) == nrow(subset) &&
    all(c(names(subset), "yi", "vi", "vi_sqrt") %in% names(converted)),
    "complete original escalc dataframe required")
  artifact_need(identical(converted[["image name stem"]], subset[["image name stem"]]) &&
    identical(converted$cleaned_author, subset$cleaned_author) &&
    artifact_numeric_equal(converted[["sample size quest"]], as.numeric(subset[["sample size quest"]])) &&
    artifact_numeric_equal(converted[[spec$effect]], as.numeric(subset[[spec$effect]])),
    "Bayesian source row/quest-n/effect alignment")
  artifact_need(all(vapply(converted[c("yi", "vi", "vi_sqrt")], function(column)
    is.numeric(column) && typeof(column) %in% c("integer", "double") && is.null(dim(column)) &&
      length(column) == nrow(subset), logical(1))), "native escalc vector extent")
  # The authenticated original expression establishes ni = sample size quest.
  # Column agreement here checks snapshot lineage; it does not infer that choice.
  relative <- paste0("bayes/", contrast, ".input.rds")
  artifact_rds(converted, artifact_path(output_root, relative))
  invisible(relative)
}

snapshot_bayes_model <- function(author_env, contrast, output_root) {
  specs <- artifact_specs()
  artifact_need(is.character(contrast) && length(contrast) == 1L && contrast %in% names(specs),
                "unknown Bayesian contrast")
  model <- artifact_object(author_env, specs[[contrast]]$bayes_model)
  exported <- artifact_bayes_export(model, contrast, specs[[contrast]])
  # Keep the whole native object alongside the independently source-mapped projection.
  relative <- paste0("bayes/", contrast, c(".rds", ".json"))
  paths <- vapply(relative, function(path) artifact_path(output_root, path), character(1))
  artifact_rds(model, paths[1L])
  artifact_json(exported, paths[2L])
  invisible(relative)
}
