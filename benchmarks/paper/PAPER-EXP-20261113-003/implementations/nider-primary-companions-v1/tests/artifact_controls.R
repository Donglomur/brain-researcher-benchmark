# Generated artifact controls only: no author source, meta/metafor, or model fit.
# Rscript --vanilla tests/artifact_controls.R /absolute/path/to/nider-primary-companions-v1
args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 1L)
root <- normalizePath(args[1L], mustWork = TRUE)
source(file.path(dirname(root), "nider-primary-producer-v2", "collector.R"))
source(file.path(root, "native_artifacts.R"))
if (!requireNamespace("jsonlite", quietly = TRUE)) stop("jsonlite missing; no installation attempted")

checks <- 0L
check <- function(ok) {
  artifact_need(ok, "generated artifact control failed")
  checks <<- checks + 1L
}
reject <- function(expression) {
  rejected <- tryCatch({ force(expression); FALSE }, error = function(error) TRUE)
  check(rejected)
}
wire_finite <- function(cell, value) {
  is.list(cell) && identical(names(cell), c("state", "value")) && identical(cell$state, "finite") &&
    is.numeric(cell$value) && identical(as.numeric(cell$value), as.numeric(value))
}
with_root <- function(callback) {
  directory <- tempfile(pattern = "nider-artifact-generated-")
  stopifnot(dir.create(directory))
  on.exit(unlink(directory, recursive = TRUE), add = TRUE)
  callback(directory)
}

fixture <- function() {
  env <- new.env(parent = emptyenv())
  specs <- artifact_specs()
  labels <- c("Generated first", "Generated merged", "Generated last")
  source_ids <- c("Generated1", "Morawetz2016b", "Generated4")
  ordinals <- c(1L, 2L, 4L)
  source_rows <- list(list(1L), list(2L, 3L), list(4L))
  opaque <- structure(matrix(c(.11, .23, .37, .41, .53, .67), nrow = 2L,
    dimnames = list(c("generated_row_A", "generated_row_B"), c("generated_C", "generated_D", "generated_E"))),
    generated_attribute = c("preserve", "verbatim"))
  states <- list(logical_na = NA, numeric_na = NA_real_, nan = NaN, pos_inf = Inf, neg_inf = -Inf)
  contrasts <- lapply(names(specs), function(contrast) {
    spec <- specs[[contrast]]
    subset <- data.frame(labels, labels, c(11, 22, 33), c(111, 222, 333),
      c(.12, .24, -.36), c(.13, -.25, .37), c(-.14, .26, .38), check.names = FALSE)
    names(subset) <- c("image name stem", "cleaned_author", "sample size quest", "sample size rating",
                       "questSelfRating", "amyQuestCorr", "amySelfRating")
    model <- structure(list(cor = as.numeric(subset[[spec$effect]]), n = as.numeric(subset[[spec$dl_n]]),
      studlab = labels, sm = "ZCOR", k.all = 3,
      TE = c(.31, .32, .33), seTE = c(.05, .06, .07), lower = c(-.41, -.42, -.43),
      upper = c(.51, .52, .53), w.common = c(0, 2, NA_real_), w.random = c(4, Inf, NaN),
      opaque = opaque, undefined = states), class = c("metacor", "meta"))
    converted <- subset
    converted$yi <- c(.21, -.43, .65)
    converted$vi <- c(.01, NA_real_, Inf)
    converted$vi_sqrt <- c(.17, NA_real_, Inf) # Invented sentinels: snapshot helpers must not recompute.
    class(converted) <- c("escalc", "data.frame")
    attr(converted, "generated_attribute") <- "native-dataframe-attribute"
    pairwise <- matrix(as.numeric(seq_len(16L)), nrow = 4L,
      dimnames = list(numerator = c("native_A", "native_B", "native_C", "native_D"),
                      denominator = c("native_A", "native_B", "native_C", "native_D")))
    bayes <- structure(list(inclusion = list(incl.BF = 5.25, incl.prior = .5, incl.posterior = .84,
      include = c(2, 4), prior = c(.1, .2, .3, .4), posterior = c(native_A = .02, native_B = .21, native_C = .14, native_D = .63)),
      prior_models = c(.1, .2, .3, .4), posterior_models = c(native_A = .02, native_B = .21, native_C = .14, native_D = .63),
      logml = c(native_A = -9.1, native_B = -7.3, native_C = -8.5, native_D = -6.7), BF = pairwise,
      generated_matrix = opaque, nested = list(states = states),
      named_values = c(generated_left = .19, generated_right = .83)),
      class = c("generated_bayes_object", "list"), generated_attribute = "unchanged")
    assign(spec$subset, subset, env)
    assign(spec$model, model, env)
    assign(spec$bayes_input, converted, env)
    assign(spec$bayes_model, bayes, env)
    list(contrast = contrast, membership = lapply(seq_along(labels), function(i)
      list(source_id = source_ids[i], source_rows = source_rows[[i]], retained_row = ordinals[i],
           author_label = labels[i], n_column = spec$dl_n, contributes_to_k = TRUE)))
  })
  columns <- c("Model", "r", "95% CIa", "pa", "k", "N", "tau", "95% CIb", "Q", "df", "pb")
  table <- as.data.frame(matrix(c(
    "Rating-Amygdala", "0.10", "[-0.20, 0.30]", "0.010", "3", "66", "0.05", "[0.00, 0.20]", "1.20", "2", "0.001",
    "Rating-Questionnaires", "-0.20", "[-0.40, 0.00]", "0.020", "3", "66", "0.06", "[0.01, 0.21]", "2.30", "2", "0.002",
    "Amygdala-Questionnaires", "0.30", "[0.10, 0.50]", "0.030", "3", "66", "0.07", "[0.02, 0.22]", "3.40", "2", "0.003"
  ), nrow = 3L, byrow = TRUE), stringsAsFactors = FALSE)
  names(table) <- columns
  env$outTable <- table
  # Only membership is consumed here; numerical full120 validation belongs to its unchanged collector/comparator.
  full120 <- list(schema = "nider_extended_reproduction_submission_v1", task = "PAPER-EXP-20261113-003",
                  workbook_sha256 = paste(rep("0", 64L), collapse = ""), contrasts = contrasts)
  list(env = env, full120 = full120)
}

with_root(function(directory) {
  data <- fixture()
  before <- as.list(data$env)
  membership_before <- data$full120
  paths <- snapshot_dl(data$env, data$full120, directory)
  check(identical(paths, c("dl/quest_self.rds", "dl/amy_quest.rds", "dl/amy_self.rds",
    "dl/quest_self.json", "dl/amy_quest.json", "dl/amy_self.json", "row_lineage.json")))
  for (contrast in names(artifact_specs())) {
    model <- get(artifact_specs()[[contrast]]$model, data$env)
    recovered <- readRDS(file.path(directory, "dl", paste0(contrast, ".rds")))
    check(identical(model, recovered))
    check(identical(dimnames(recovered$opaque), dimnames(model$opaque)))
    check(identical(recovered$undefined, model$undefined))
    projected <- jsonlite::fromJSON(file.path(directory, "dl", paste0(contrast, ".json")), simplifyVector = FALSE)
    check(wire_finite(projected$vectors$cor$values[[1L]], c(quest_self = .12, amy_quest = .13, amy_self = -.14)[[contrast]]))
    check(wire_finite(projected$vectors$n$values[[1L]], if (contrast == "amy_self") 111 else 11))
    check(wire_finite(projected$vectors$TE$values[[1L]], .31))
    check(wire_finite(projected$vectors$seTE$values[[2L]], .06))
    check(wire_finite(projected$vectors$lower$values[[3L]], -.43))
    check(wire_finite(projected$vectors$upper$values[[1L]], .51))
    check(wire_finite(projected$vectors$w.common$values[[1L]], 0))
    check(identical(projected$vectors$w.common$values[[3L]], list(state = "NA")))
    check(identical(projected$vectors$w.random$values[[2L]], list(state = "+Inf")))
    check(identical(projected$vectors$w.random$values[[3L]], list(state = "NaN")))
    check(identical(projected$scales$w.common, "raw_native_weight_not_percent"))
  }
  ledger <- jsonlite::fromJSON(file.path(directory, "row_lineage.json"), simplifyVector = FALSE)
  check(identical(vapply(ledger$contrasts, function(row) row$contrast, character(1)), names(artifact_specs())))
  check(identical(ledger$contrasts[[3L]]$dl_n_column, "sample size rating"))
  check(all(vapply(ledger$contrasts, function(row) identical(row$bayes_n_column, "sample size quest"), logical(1))))
  check(is.list(ledger$contrasts[[1L]]$membership[[1L]]$source_rows))
  check(identical(unlist(ledger$contrasts[[1L]]$membership[[2L]]$source_rows, use.names = FALSE), c(2L, 3L)))
  check(identical(as.list(data$env), before))
  check(identical(data$full120, membership_before))
  reject(snapshot_dl(data$env, data$full120, directory))
})

for (mutation in c("reverse_membership", "duplicate_label", "duplicate_ordinal", "wrong_dl_n_column",
                    "reverse_model_labels", "wrong_model_n", "wrong_model_cor", "missing_model", "missing_subset",
                    "missing_weight", "weight_matrix", "wrong_extent", "wrong_scale", "wrong_k_all")) {
  with_root(function(directory) {
    data <- fixture()
    if (mutation == "reverse_membership") data$full120$contrasts[[1L]]$membership <- rev(data$full120$contrasts[[1L]]$membership)
    if (mutation == "duplicate_label") data$full120$contrasts[[1L]]$membership[[2L]]$author_label <- "Generated first"
    if (mutation == "duplicate_ordinal") data$full120$contrasts[[1L]]$membership[[3L]]$source_rows <- list(1L)
    if (mutation == "wrong_dl_n_column") data$full120$contrasts[[3L]]$membership[[1L]]$n_column <- "sample size quest"
    if (mutation == "reverse_model_labels") data$env$meta_questSelf$studlab <- rev(data$env$meta_questSelf$studlab)
    if (mutation == "wrong_model_n") data$env$meta_amySelf$n <- data$env$dfAmySelf[["sample size quest"]]
    if (mutation == "wrong_model_cor") data$env$meta_amyQuest$cor <- rev(data$env$meta_amyQuest$cor)
    if (mutation == "missing_model") rm("meta_amyQuest", envir = data$env)
    if (mutation == "missing_subset") rm("dfAmySelf", envir = data$env)
    if (mutation == "missing_weight") data$env$meta_questSelf$w.common <- NULL
    if (mutation == "weight_matrix") data$env$meta_questSelf$w.random <- matrix(1:3, nrow = 1L)
    if (mutation == "wrong_extent") data$env$meta_amySelf$lower <- c(.1, .2)
    if (mutation == "wrong_scale") data$env$meta_amySelf$sm <- "COR"
    if (mutation == "wrong_k_all") data$env$meta_amySelf$k.all <- 2
    reject(snapshot_dl(data$env, data$full120, directory))
    check(length(list.files(directory, recursive = TRUE)) == 0L)
  })
}

with_root(function(directory) {
  data <- fixture()
  before <- data$env$outTable
  check(identical(snapshot_table(data$env, directory),
    c("table1/habit_associations.rds", "table1/habit_associations.csv")))
  check(identical(readRDS(file.path(directory, "table1/habit_associations.rds")), before))
  csv <- utils::read.csv(file.path(directory, "table1/habit_associations.csv"),
    colClasses = "character", check.names = FALSE, stringsAsFactors = FALSE,
    na.strings = character(), fileEncoding = "UTF-8")
  check(identical(csv, before))
  check(identical(csv$r[1L], "0.10") && identical(csv$pa[1L], "0.010"))
  check(identical(csv[["95% CIa"]][1L], "[-0.20, 0.30]"))
  check(identical(data$env$outTable, before))
  reject(snapshot_table(data$env, directory))
})
for (mutation in c("row_order", "column_order", "missing_row", "numeric_coercion", "ability_row", "missing_object")) {
  with_root(function(directory) {
    data <- fixture()
    if (mutation == "row_order") data$env$outTable <- data$env$outTable[3:1, ]
    if (mutation == "column_order") data$env$outTable <- data$env$outTable[, 11:1]
    if (mutation == "missing_row") data$env$outTable <- data$env$outTable[-1L, ]
    if (mutation == "numeric_coercion") data$env$outTable$r <- as.numeric(data$env$outTable$r)
    if (mutation == "ability_row") data$env$outTable$Model[1L] <- "Generated ability row"
    if (mutation == "missing_object") rm("outTable", envir = data$env)
    reject(snapshot_table(data$env, directory))
    check(length(list.files(directory, recursive = TRUE)) == 0L)
  })
}

with_root(function(directory) {
  data <- fixture()
  before <- as.list(data$env)
  for (contrast in names(artifact_specs())) {
    spec <- artifact_specs()[[contrast]]
    check(identical(snapshot_bayes_input(data$env, contrast, data$full120, directory), paste0("bayes/", contrast, ".input.rds")))
    recovered <- readRDS(file.path(directory, "bayes", paste0(contrast, ".input.rds")))
    check(identical(recovered, get(spec$bayes_input, data$env)))
    check(identical(recovered[["sample size quest"]], c(11, 22, 33)))
    check(identical(recovered$vi_sqrt[1L], .17))
    check(identical(snapshot_bayes_model(data$env, contrast, directory), paste0("bayes/", contrast, c(".rds", ".json"))))
    check(identical(readRDS(file.path(directory, "bayes", paste0(contrast, ".rds"))), get(spec$bayes_model, data$env)))
    projected <- jsonlite::fromJSON(file.path(directory, "bayes", paste0(contrast, ".json")), simplifyVector = FALSE)
    check(wire_finite(projected$inclusion$incl.BF, 5.25))
    check(wire_finite(projected$inclusion$incl.prior, .5))
    check(wire_finite(projected$inclusion$incl.posterior, .84))
    check(wire_finite(projected$inclusion$include$values[[1L]], 2))
    check(wire_finite(projected$inclusion$include$values[[2L]], 4))
    check(wire_finite(projected$inclusion$prior$values[[3L]], .3))
    check(wire_finite(projected$inclusion$posterior$values[[4L]], .63))
    check(wire_finite(projected$model_vectors$prior_models$values[[2L]], .2))
    check(wire_finite(projected$model_vectors$posterior_models$values[[1L]], .02))
    check(wire_finite(projected$model_vectors$logml$values[[2L]], -7.3))
    check(identical(projected$inclusion$include$storage_type, "double"))
    check(identical(projected$inclusion$prior$names, NULL))
    check(identical(projected$model_vectors$logml$names, as.list(c("native_A", "native_B", "native_C", "native_D"))))
    check(identical(projected$pairwise_BF$dimension_axis_names, as.list(c("numerator", "denominator"))))
    check(wire_finite(projected$pairwise_BF$values_by_row[[1L]][[2L]], 5))
    check(wire_finite(projected$pairwise_BF$values_by_row[[2L]][[1L]], 2))
    reject(snapshot_bayes_input(data$env, contrast, data$full120, directory))
    reject(snapshot_bayes_model(data$env, contrast, directory))
  }
  check(identical(as.list(data$env), before))
  reject(snapshot_bayes_input(data$env, "invented", data$full120, directory))
  reject(snapshot_bayes_model(data$env, "invented", directory))
})
for (mutation in c("rating_n_substitution", "row_order", "missing_yi", "missing_vi", "missing_vi_sqrt",
                    "wrong_effect", "missing_input", "dropped_row")) {
  with_root(function(directory) {
    data <- fixture()
    if (mutation == "rating_n_substitution") data$env$dfAmySelf_conv[["sample size quest"]] <- data$env$dfAmySelf_conv[["sample size rating"]]
    if (mutation == "row_order") data$env$dfAmySelf_conv <- data$env$dfAmySelf_conv[3:1, ]
    if (mutation == "missing_yi") data$env$dfAmySelf_conv$yi <- NULL
    if (mutation == "missing_vi") data$env$dfAmySelf_conv$vi <- NULL
    if (mutation == "missing_vi_sqrt") data$env$dfAmySelf_conv$vi_sqrt <- NULL
    if (mutation == "wrong_effect") data$env$dfAmySelf_conv$amySelfRating <- rev(data$env$dfAmySelf_conv$amySelfRating)
    if (mutation == "missing_input") rm("dfAmySelf_conv", envir = data$env)
    if (mutation == "dropped_row") data$env$dfAmySelf_conv <- data$env$dfAmySelf_conv[-1L, ]
    reject(snapshot_bayes_input(data$env, "amy_self", data$full120, directory))
    check(length(list.files(directory, recursive = TRUE)) == 0L)
  })
}
with_root(function(directory) {
  data <- fixture()
  rm("Bmeta_amySelf", envir = data$env)
  reject(snapshot_bayes_model(data$env, "amy_self", directory))
  data$env$Bmeta_amySelf <- NULL
  reject(snapshot_bayes_model(data$env, "amy_self", directory))
})
for (mutation in c("missing_inclusion_BF", "missing_prior_models", "missing_posterior_models", "missing_logml",
                    "wrong_include_positions", "wrong_include_type", "wrong_vector_length", "wrong_matrix_shape",
                    "complex_scalar", "complex_vector", "complex_matrix", "complex_include",
                    "scalar_matrix", "logical_NA_matrix")) {
  with_root(function(directory) {
    data <- fixture()
    if (mutation == "missing_inclusion_BF") data$env$Bmeta_amySelf$inclusion$incl.BF <- NULL
    if (mutation == "missing_prior_models") data$env$Bmeta_amySelf$prior_models <- NULL
    if (mutation == "missing_posterior_models") data$env$Bmeta_amySelf$posterior_models <- NULL
    if (mutation == "missing_logml") data$env$Bmeta_amySelf$logml <- NULL
    if (mutation == "wrong_include_positions") data$env$Bmeta_amySelf$inclusion$include <- c(1, 3)
    if (mutation == "wrong_include_type") data$env$Bmeta_amySelf$inclusion$include <- c("2", "4")
    if (mutation == "wrong_vector_length") data$env$Bmeta_amySelf$inclusion$posterior <- c(.5, .5)
    if (mutation == "wrong_matrix_shape") data$env$Bmeta_amySelf$BF <- matrix(1:16, nrow = 2L)
    if (mutation == "complex_scalar") data$env$Bmeta_amySelf$inclusion$incl.BF <- 1 + 2i
    if (mutation == "complex_vector") data$env$Bmeta_amySelf$logml <- c(1 + 2i, 2, 3, 4)
    if (mutation == "complex_matrix") data$env$Bmeta_amySelf$BF <- matrix(1 + 2i, nrow = 4L, ncol = 4L)
    if (mutation == "complex_include") data$env$Bmeta_amySelf$inclusion$include <- c(2 + 1i, 4)
    if (mutation == "scalar_matrix") data$env$Bmeta_amySelf$inclusion$incl.BF <- matrix(1, nrow = 1L)
    if (mutation == "logical_NA_matrix") data$env$Bmeta_amySelf$inclusion$incl.BF <- matrix(NA, nrow = 1L)
    reject(snapshot_bayes_model(data$env, "amy_self", directory))
    check(length(list.files(directory, recursive = TRUE)) == 0L)
  })
}
with_root(function(directory) {
  data <- fixture()
  data$env$Bmeta_amySelf$inclusion$incl.BF <- NA
  data$env$Bmeta_amySelf$logml <- c(NA_real_, NaN, Inf, -Inf)
  dimnames(data$env$Bmeta_amySelf$BF) <- NULL
  snapshot_bayes_model(data$env, "amy_self", directory)
  projected <- jsonlite::fromJSON(file.path(directory, "bayes/amy_self.json"), simplifyVector = FALSE)
  check(identical(projected$inclusion$incl.BF, list(state = "NA")))
  check(identical(vapply(projected$model_vectors$logml$values, function(cell) cell$state, character(1)),
    c("NA", "NaN", "+Inf", "-Inf")))
  check(is.null(projected$model_vectors$logml$names))
  check(is.null(projected$pairwise_BF$dimension_labels))
  check(is.null(projected$pairwise_BF$dimension_axis_names))
})

with_root(function(directory) {
  data <- fixture()
  dir.create(file.path(directory, "dl"))
  existing <- file.path(directory, "dl/quest_self.rds")
  writeLines("preserve previous artifact", existing)
  reject(snapshot_dl(data$env, data$full120, directory))
  check(identical(readLines(existing), "preserve previous artifact"))
  reject(artifact_path(directory, "../escape.rds"))
  reject(artifact_path(directory, "/absolute.rds"))
})
with_root(function(directory) {
  data <- fixture()
  outside <- tempfile(pattern = "nider-artifact-outside-")
  stopifnot(dir.create(outside))
  on.exit(unlink(outside, recursive = TRUE), add = TRUE)
  check(isTRUE(file.symlink(outside, file.path(directory, "dl"))))
  reject(snapshot_dl(data$env, data$full120, directory))
  check(length(list.files(outside, recursive = TRUE)) == 0L)
})
with_root(function(directory) {
  data <- fixture()
  dir.create(file.path(directory, "dl"))
  dangling <- file.path(directory, "dl/quest_self.rds")
  check(isTRUE(file.symlink(file.path(directory, "absent-target"), dangling)))
  reject(snapshot_dl(data$env, data$full120, directory))
  check(artifact_is_link(dangling))
})
with_root(function(directory) {
  target <- artifact_path(directory, "race.rds")
  reject(artifact_write(target, function(temporary) {
    writeLines("new generated bytes", temporary)
    writeLines("prior concurrent writer", target)
  }))
  check(identical(readLines(target), "prior concurrent writer"))
  check(!any(grepl("nider-pending", list.files(directory, all.files = TRUE))))
})

summary_line <- sprintf("Generated native artifact checks: %d passed; no estimator called.\n", checks)
cat(summary_line)
