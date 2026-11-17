# Newly constructed collector v2; not recovered extended_reference.R.
# No fitting, source loading, package installation, or I/O in this file.
need <- function(ok, message) {
  if (!isTRUE(ok)) stop(message, call. = FALSE)
}

numeric_cell <- function(x) {
  # Native sparse branches use bare NA, which has logical storage in R.
  if (is.logical(x) && length(x) == 1L && is.na(x)) return(list(state = "NA"))
  need(is.numeric(x) && length(x) == 1L, "native numeric scalar required")
  if (is.nan(x)) return(list(state = "NaN"))
  if (is.na(x)) return(list(state = "NA"))
  if (is.infinite(x)) return(list(state = if (x > 0) "+Inf" else "-Inf"))
  list(state = "finite", value = unname(x))
}

native <- function(model, key) {
  need(key %in% names(model), paste("missing native field", key))
  model[[key]]
}

same_numeric <- function(x, y) {
  is.numeric(x) && is.numeric(y) && identical(as.numeric(x), as.numeric(y))
}

source_lineage <- function(original) {
  need(is.data.frame(original) && nrow(original) == 40L, "40 original records required")
  ids <- original[["image name stem"]]
  need(is.character(ids) && !anyNA(ids) && all(nzchar(ids)), "original source IDs")
  duplicate_rows <- which(ids == "Morawetz2016b")
  need(length(duplicate_rows) == 2L, "exact two-row Morawetz merge required")
  retained <- setdiff(seq_len(40L), duplicate_rows[2L])
  need(!anyDuplicated(ids[retained]), "unexpected duplicate source ID")
  lapply(retained, function(i) list(source_id = ids[i], retained_row = i,
    source_rows = as.list(if (i == duplicate_rows[1L]) duplicate_rows else i)))
}

collect_contrast <- function(model, subset, postmerge, lineage, contrast, spec, fields) {
  need(inherits(model, "metacor") && inherits(model, "meta"), "native metacor model required")
  need(is.data.frame(subset) && is.data.frame(postmerge) && nrow(postmerge) == 39L,
       "author subsets required")
  labels <- postmerge[["image name stem"]]
  need(is.character(labels) && !anyNA(labels) && !anyDuplicated(labels), "postmerge labels")
  indices <- match(subset[["image name stem"]], labels)
  need(!anyNA(indices) && !anyDuplicated(indices) && identical(indices, sort(indices)),
       "ordered source membership")
  online <- !labels %in% c("Diers, Gärtner et al. (2023)", "Scheffel et al. (2019)",
                           "Hofhansel et al. (2023)")
  expected <- which(!is.na(postmerge[[spec$correlation]]) &
                    if (isTRUE(spec$online)) online else TRUE)
  need(identical(indices, expected) && identical(subset, postmerge[expected, ]),
       "literal author subset alignment")
  n <- as.numeric(subset[[spec$n_column]])
  correlations <- as.numeric(subset[[spec$correlation]])
  data <- native(model, "data")
  need(is.data.frame(data) && nrow(data) == nrow(subset), "native data row alignment")
  need(same_numeric(native(model, "n"), n) && same_numeric(data[[".n"]], n),
       "native sample-size column alignment")
  need(same_numeric(native(model, "cor"), correlations) &&
       same_numeric(data[[".cor"]], correlations), "native correlation alignment")
  need(identical(native(model, "studlab"), subset[["image name stem"]]) &&
       identical(data[[".studlab"]], subset[["image name stem"]]), "native label alignment")
  exclude <- native(model, "exclude")
  # meta 7.0-0 returns NULL for the author's absent exclude argument.
  if (is.null(exclude)) exclude <- rep(FALSE, nrow(subset))
  need(is.logical(exclude) && length(exclude) == nrow(subset) && !anyNA(exclude) &&
       !any(exclude), "unexpected native exclusion")
  te <- native(model, "TE"); se <- native(model, "seTE")
  need(is.numeric(te) && is.numeric(se) && length(te) == nrow(subset) &&
       length(se) == nrow(subset), "native fitted vectors")
  # meta 7.0-0 metagen uses missingness, not is.finite(), for k.
  contributes <- !is.na(te) & !is.na(se) & !exclude
  need(identical(as.numeric(native(model, "k")), as.numeric(sum(contributes))) &&
       identical(as.numeric(native(model, "k.study")), as.numeric(sum(contributes))) &&
       identical(as.numeric(native(model, "k.all")), as.numeric(nrow(subset))) &&
       identical(as.numeric(native(model, "k.TE")), as.numeric(sum(!is.na(te)))),
       "native count alignment")
  need(is.null(model$cluster) && !isTRUE(model$three.level), "clustering is outside source calls")
  settings <- list(sm = native(model, "sm"), method_tau = native(model, "method.tau"),
    method_random_ci = native(model, "method.random.ci"),
    level = as.character(native(model, "level")), level_ma = as.character(native(model, "level.ma")),
    common = native(model, "common"), random = native(model, "random"),
    three_level = native(model, "three.level"), cluster_supplied = !is.null(model$cluster))
  need(identical(settings, list(sm = "ZCOR", method_tau = "DL", method_random_ci = "classic",
    level = "0.95", level_ma = "0.95", common = TRUE, random = TRUE,
    three_level = FALSE, cluster_supplied = FALSE)), "unexpected actual model settings")
  tau <- list(method = native(model, "method.tau.ci"),
    lower_sign = native(model, "sign.lower.tau"), upper_sign = native(model, "sign.upper.tau"))
  need(length(tau$method) == 1L && tau$method %in% c("J", "") &&
       all(vapply(tau[2:3], function(x) is.character(x) && length(x) == 1L &&
                  x %in% c("", "<", ">"), logical(1))), "native tau method/signs")
  members <- lapply(seq_along(indices), function(j) {
    item <- lineage[[indices[j]]]
    list(source_id = item$source_id, source_rows = item$source_rows,
      retained_row = item$retained_row, author_label = subset[["image name stem"]][j],
      n_column = spec$n_column, contributes_to_k = contributes[j])
  })
  values <- lapply(fields, function(field) {
    key <- field$native_source
    value <- if (key == "sum(model$data$.n)") sum(data$.n) else if (
      key == "length(selected original post-merge subset)") nrow(subset) else native(model, key)
    need(field$transform %in% c("identity", "tanh"), "unsupported schema transform")
    if (field$transform == "tanh") value <- tanh(value)
    numeric_cell(value)
  })
  names(values) <- vapply(fields, function(x) x$field, character(1))
  need(length(values) == 40L && !anyDuplicated(names(values)), "complete forty fields")
  list(contrast = contrast, settings = settings, tau_interval = tau, membership = members, fields = values)
}

collect_full120 <- function(author_env, original, field_schema, arm, workbook_sha256) {
  need(is.environment(author_env) && arm %in% c("A", "B"), "trusted producer arguments")
  lineage <- source_lineage(original)
  specs <- list(
    quest_self = list(model = "meta_questSelf", subset = "dfQuestSelf",
      correlation = "questSelfRating", n_column = "sample size quest", online = TRUE),
    amy_quest = list(model = "meta_amyQuest", subset = "dfAmyQuest",
      correlation = "amyQuestCorr", n_column = "sample size quest", online = FALSE),
    amy_self = list(model = "meta_amySelf", subset = "dfAmySelf",
      correlation = "amySelfRating", n_column = "sample size rating", online = TRUE))
  get_author <- function(key) {
    need(exists(key, envir = author_env, inherits = FALSE), paste("author object missing", key))
    get(key, envir = author_env, inherits = FALSE)
  }
  postmerge <- get_author("dfcorrs")
  need(length(lineage) == nrow(postmerge), "complete postmerge lineage")
  contrasts <- lapply(names(specs), function(key) {
    spec <- specs[[key]]
    collect_contrast(get_author(spec$model), get_author(spec$subset), postmerge, lineage,
                     key, spec, field_schema$fields_per_contrast)
  })
  list(schema = "nider_extended_reproduction_submission_v1", task = "PAPER-EXP-20261113-003",
       arm = arm, workbook_sha256 = workbook_sha256, contrasts = contrasts)
}
