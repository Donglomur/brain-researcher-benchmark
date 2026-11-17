# Generated models and source text only. Never load meta or call an estimator.
# Rscript --vanilla tests/collector_controls.R /absolute/path/to/nider-primary-producer-v2
args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 1L)
root <- normalizePath(args[1L], mustWork = TRUE)
source(file.path(root, "collector.R"))
source(file.path(root, "source_selection.R"))
if (!requireNamespace("jsonlite", quietly = TRUE)) stop("jsonlite required; no installation attempted")
schema <- jsonlite::fromJSON(file.path(dirname(root), "nider-full120-reconstruction-profile-v1",
                                     "participant", "FIELD_SCHEMA.json"), simplifyVector = FALSE)
checks <- 0L
check <- function(ok) { need(ok, "generated control failed"); checks <<- checks + 1L }
reject <- function(expression) {
  failed <- tryCatch({ force(expression); FALSE }, error = function(e) TRUE)
  check(failed)
}
for (pair in list(list(NA_real_, "NA"), list(NaN, "NaN"), list(Inf, "+Inf"), list(-Inf, "-Inf")))
  check(identical(numeric_cell(pair[[1L]]), list(state = pair[[2L]])))
reject(numeric_cell(NULL)); reject(numeric_cell(c(1, 2))); reject(numeric_cell("1"))
check(identical(numeric_cell(NA), list(state = "NA")))
reject(numeric_cell(TRUE)); reject(numeric_cell(FALSE)); reject(numeric_cell("NA"))
check(identical(numeric_cell(-0)$value, -0))

original <- data.frame(id = paste0("Generated", seq_len(40L)), n = seq_len(40L) + 10,
                       rating_n = seq_len(40L) + 20, effect = rep(.25, 40L), check.names = FALSE)
names(original) <- c("image name stem", "sample size quest", "sample size rating", "questSelfRating")
original[["image name stem"]][5:6] <- "Morawetz2016b"
original$amyQuestCorr <- original$amySelfRating <- original$questSelfRating
postmerge <- original[-6L, ]
postmerge[["image name stem"]] <- paste0("Generated author ", seq_len(39L))
env <- new.env(parent = emptyenv()); env$dfcorrs <- postmerge
specs <- list(quest_self = c("meta_questSelf", "dfQuestSelf", "questSelfRating", "sample size quest"),
              amy_quest = c("meta_amyQuest", "dfAmyQuest", "amyQuestCorr", "sample size quest"),
              amy_self = c("meta_amySelf", "dfAmySelf", "amySelfRating", "sample size rating"))
make_model <- function(spec) {
  model <- list()
  native_keys <- unique(vapply(schema$fields_per_contrast, function(field) field$native_source, character(1)))
  native_keys <- setdiff(native_keys, c("sum(model$data$.n)", "length(selected original post-merge subset)"))
  # Every native scalar has a distinct invented sentinel; mapping swaps are observable.
  for (j in seq_along(native_keys)) model[[native_keys[j]]] <- j / 1000
  model$k <- model$k.all <- model$k.TE <- model$k.study <- 39
  model$df.Q <- 38
  model$cor <- as.numeric(postmerge[[spec[3L]]]); model$n <- as.numeric(postmerge[[spec[4L]]])
  model$studlab <- postmerge[["image name stem"]]
  model$data <- data.frame(.cor = model$cor, .n = model$n, .studlab = model$studlab)
  model <- c(model, list(exclude = NULL, cluster = NULL))
  model$TE <- rep(.25, 39L); model$seTE <- rep(.1, 39L)
  model$sm <- "ZCOR"; model$method.tau <- "DL"; model$method.random.ci <- "classic"
  model$level <- model$level.ma <- .95
  model$common <- model$random <- TRUE; model$three.level <- FALSE
  model$method.tau.ci <- "J"; model$sign.lower.tau <- "<"; model$sign.upper.tau <- ">"
  class(model) <- c("metacor", "meta")
  model
}
for (spec in specs) {
  assign(spec[1L], make_model(spec), env)
  assign(spec[2L], postmerge, env)
}
collect <- function() collect_full120(env, original, schema, "A", paste(rep("a", 64), collapse = ""))
document <- collect()
check(length(document$contrasts) == 3L)
first <- document$contrasts[[1L]]$fields
for (entry in list(c("common_z_estimate", .001), c("common_z_se", .002),
                   c("common_z_lower", .005), c("common_z_upper", .006),
                   c("random_z_estimate", .007), c("random_z_se", .008),
                   c("Q", .013), c("tau", .016), c("tau2", .017), c("I2", .026)))
  check(identical(first[[entry[1L]]], numeric_cell(as.numeric(entry[2L]))))
for (entry in list(c("common_r_estimate", .001), c("common_r_lower", .005),
                   c("common_r_upper", .006), c("random_r_estimate", .007),
                   c("random_r_lower", .011), c("random_r_upper", .012)))
  check(identical(first[[entry[1L]]], numeric_cell(tanh(as.numeric(entry[2L])))))
for (i in seq_along(document$contrasts)) {
  row <- document$contrasts[[i]]; model <- get(specs[[i]][1L], env)
  check(length(row$fields) == 40L)
  check(identical(row$membership[[5L]]$source_rows, list(5L, 6L)))
  check(identical(row$membership[[5L]]$source_id, "Morawetz2016b"))
  for (field in schema$fields_per_contrast) {
    expected <- if (field$native_source == "sum(model$data$.n)") sum(model$data$.n) else if (
      field$native_source == "length(selected original post-merge subset)") 39L else model[[field$native_source]]
    if (field$transform == "tanh") expected <- tanh(expected)
    check(identical(row$fields[[field$field]], numeric_cell(expected)))
  }
}
encoded <- jsonlite::toJSON(document, auto_unbox = TRUE, digits = NA)
decoded <- jsonlite::fromJSON(encoded, simplifyVector = FALSE)
check(is.list(decoded$contrasts[[1L]]$membership[[1L]]$source_rows))
check(length(decoded$contrasts[[1L]]$membership[[1L]]$source_rows) == 1L)

baseline <- env$meta_questSelf
for (state in list(NA_real_, NaN, Inf, -Inf)) {
  env$meta_questSelf$TE.common <- state
  row <- collect()$contrasts[[1L]]
  check(identical(row$fields$common_z_estimate, numeric_cell(state)))
  check(identical(row$fields$common_r_estimate, numeric_cell(tanh(state))))
}
env$meta_questSelf <- baseline
env$meta_questSelf$method.tau.ci <- ""
env$meta_questSelf$lower.tau <- env$meta_questSelf$upper.tau <- NA
env$meta_questSelf$lower.tau2 <- env$meta_questSelf$upper.tau2 <- NA
env$meta_questSelf$sign.lower.tau <- env$meta_questSelf$sign.upper.tau <- ""
sparse <- collect()$contrasts[[1L]]
check(identical(sparse$tau_interval, list(method = "", lower_sign = "", upper_sign = "")))
for (key in c("lower_tau", "upper_tau", "lower_tau2", "upper_tau2"))
  check(identical(sparse$fields[[key]], list(state = "NA")))
env$meta_questSelf <- baseline
for (key in unique(vapply(schema$fields_per_contrast, function(field) field$native_source, character(1)))) {
  if (key %in% c("sum(model$data$.n)", "length(selected original post-merge subset)")) next
  env$meta_questSelf[[key]] <- NULL
  reject(collect())
  env$meta_questSelf <- baseline
}
for (mutation in c("sample", "label", "order", "count", "method", "cluster", "vector", "subset")) {
  if (mutation == "sample") env$meta_questSelf$data$.n[1L] <- 999
  if (mutation == "label") env$meta_questSelf$studlab[1L] <- "wrong"
  if (mutation == "order") env$meta_questSelf$studlab <- rev(env$meta_questSelf$studlab)
  if (mutation == "count") env$meta_questSelf$k <- 38
  if (mutation == "method") env$meta_questSelf$method.tau <- "REML"
  if (mutation == "cluster") env$meta_questSelf$cluster <- rep(1, 39L)
  if (mutation == "vector") env$meta_questSelf$tau <- c(.1, .2)
  if (mutation == "subset") env$dfQuestSelf <- postmerge[39:1, ]
  reject(collect())
  env$meta_questSelf <- baseline; env$dfQuestSelf <- postmerge
}
env$meta_questSelf$TE[1L] <- NA_real_
env$meta_questSelf$k <- env$meta_questSelf$k.study <- env$meta_questSelf$k.TE <- 38
check(identical(collect()$contrasts[[1L]]$membership[[1L]]$contributes_to_k, FALSE))
env$meta_questSelf <- baseline
env$meta_questSelf$TE[1L] <- Inf
check(identical(collect()$contrasts[[1L]]$membership[[1L]]$contributes_to_k, TRUE))
env$meta_questSelf <- baseline

# Build inert expressions at the exact allowed spans. An out-of-scope stop()
# stays parsed but unexecuted. No authentic script or scientific input is needed.
lines <- rep("# generated", 625L)
manifest <- lapply(allowed_spans(), function(span) list(start = span[1L], end = span[2L]))
for (span in allowed_spans()) {
  if (span[1L] == span[2L]) lines[span[1L]] <- "x <- 1" else {
    lines[span[1L]] <- "x <- ("; lines[span[2L]] <- "1)"
  }
}
lines[470L] <- 'stop("must never execute")'
parsed <- parse(text = lines, keep.source = TRUE)
check(length(select_source_expressions(parsed, manifest)) == 23L)
reject(select_source_expressions(parsed, manifest[-1L]))
changed <- manifest; changed[[1L]]$start <- changed[[1L]]$end <- 470
reject(select_source_expressions(parsed, changed))
lines[77L] <- "x <- 1"; lines[82L] <- "x <- 2"
reject(select_source_expressions(parse(text = lines, keep.source = TRUE), manifest))
cat("Generated R collector/parse checks:", checks, "passed; no estimator called.\n")
