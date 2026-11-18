# Export already-produced conditional lmer objects. This file never fits a model.
# Source it in an existing trusted R session; do not load untrusted serialized R.
erp_specs <- list(
  FRN = list(
    formula = "FRN_N2_offer_s ~ abs_rpe_s + abs_epe_valence_s + abs_epe_arousal_s + P2_offer_s + P2_base_offer_s + (1 + abs_epe_arousal_s + P2_offer_s + P2_base_offer_s | sub)",
    random = c("(Intercept)", "abs_epe_arousal_s", "P2_offer_s", "P2_base_offer_s")),
  P3a = list(
    formula = "P3a_offer_s ~ abs_rpe_s + abs_epe_valence_s + abs_epe_arousal_s + P3a_base_offer_s + (1 + abs_rpe_s + abs_epe_arousal_s + P3a_base_offer_s | sub)",
    random = c("(Intercept)", "abs_rpe_s", "abs_epe_arousal_s", "P3a_base_offer_s")),
  P3b = list(
    formula = "P3b_offer_s ~ abs_rpe_s + abs_epe_valence_s + abs_epe_arousal_s + P3b_base_offer_s + (1 + abs_rpe_s + P3b_base_offer_s | sub)",
    random = c("(Intercept)", "abs_rpe_s", "P3b_base_offer_s")))

erp_text <- function(x) paste(deparse(x, width.cutoff = 500L), collapse = " ")
erp_normalize <- function(x) gsub("[[:space:]]", "", x)
erp_assert <- function(ok, message) if (!isTRUE(ok)) stop(message, call. = FALSE)
erp_array <- function(x) unname(as.list(x))
erp_matrix <- function(x) lapply(seq_len(nrow(x)), function(i) erp_array(x[i, ]))

erp_export_one <- function(fit, source_rows, spec) {
  erp_assert(inherits(fit, "lmerMod"), "Only already-fitted Gaussian lmer objects are supported")
  erp_assert(lme4::isREML(fit), "Source conditional models require REML")
  erp_assert(identical(erp_normalize(erp_text(stats::formula(fit))),
                       erp_normalize(spec$formula)), "Source formula differs")
  mf <- stats::model.frame(fit)
  expected_formula <- stats::as.formula(spec$formula)
  columns <- all.vars(expected_formula)
  erp_assert(setequal(names(mf), columns), "Unexpected model-frame columns")
  erp_assert(is.null(stats::model.weights(mf)), "Weighted fits are unsupported")
  erp_assert(is.null(stats::model.offset(mf)), "Offset fits are unsupported")
  erp_assert(nrow(mf) == 6403L && stats::nobs(fit) == nrow(mf), "Conditional row support differs")
  erp_assert(is.numeric(source_rows) && length(source_rows) == nrow(mf) &&
    all(is.finite(source_rows)) && all(source_rows == floor(source_rows)) &&
    all(source_rows >= 1 & source_rows <= 7380) && !anyDuplicated(source_rows),
    "An explicit original source-row binding is required")
  erp_assert(length(unique(as.character(mf$sub))) == 41L,
             "Expected 41 participant identities")
  numeric_columns <- setdiff(columns, "sub")
  erp_assert(all(vapply(mf[numeric_columns], function(x)
    is.numeric(x) && is.null(dim(x)) && all(is.finite(x)), logical(1))),
    "Model frame must contain finite untransformed numeric source columns")
  fixed_formula <- lme4::nobars(expected_formula)
  X_expected <- stats::model.matrix(fixed_formula, mf)
  X <- lme4::getME(fit, "X")
  erp_assert(is.null(attr(X, "col.dropped")) &&
    identical(dim(X), dim(X_expected)) && identical(colnames(X), colnames(X_expected)) &&
    all(X == X_expected), "Actual fixed design differs or is rank deficient")
  erp_assert(all(lme4::getME(fit, "y") == mf[[columns[1L]]]), "Actual fitted response differs")
  cnms <- lme4::getME(fit, "cnms")
  erp_assert(length(cnms) == 1L && identical(names(cnms), "sub") &&
    identical(cnms[[1L]], spec$random), "Actual random-effect structure differs")
  random_expected <- lme4::mkReTrms(lme4::findbars(expected_formula), mf)
  erp_assert(isTRUE(all.equal(lme4::getME(fit, "Zt"), random_expected$Zt,
    tolerance = 0, check.attributes = FALSE)), "Actual random design differs")
  groups <- lme4::getME(fit, "flist")
  erp_assert(length(groups) == 1L && identical(names(groups), "sub") && is.factor(groups[[1L]]) &&
    identical(as.character(groups[[1L]]), as.character(mf$sub)), "Actual group order differs")
  beta <- lme4::fixef(fit)
  covariance <- as.matrix(stats::vcov(fit))
  erp_assert(identical(names(beta), colnames(X)) &&
    identical(rownames(covariance), names(beta)) &&
    identical(colnames(covariance), names(beta)) &&
    all(is.finite(beta)) && all(is.finite(covariance)), "Fixed-effect covariance axes differ")
  opt <- fit@optinfo
  list(
    formula = erp_text(stats::formula(fit)), REML = TRUE,
    weights = NULL, offset = NULL,
    fixed_design_verified = TRUE, random_design_verified = TRUE,
    random_group = "sub", random_terms = erp_array(cnms[[1L]]),
    group_levels = erp_array(levels(groups[[1L]])),
    frame = setNames(lapply(columns, function(name)
      if (name == "sub") erp_array(as.character(mf[[name]])) else erp_array(mf[[name]])), columns),
    native_frame_row_names = erp_array(rownames(mf)),
    operator_bound_source_rows = erp_array(as.integer(source_rows)),
    terms = erp_array(names(beta)), coefficients = erp_array(unname(beta)),
    covariance = erp_matrix(covariance),
    diagnostics = list(
      native_model_frame_sub_class = erp_array(class(mf$sub)),
      native_model_frame_sub_values = erp_array(mf$sub),
      fitted_call = erp_text(stats::getCall(fit)),
      optimizer = opt$optimizer, optimizer_control = opt$control,
      convergence_code = opt$conv$opt, convergence_messages = opt$conv$lme4$messages,
      optimizer_warnings = opt$warnings, singular = lme4::isSingular(fit),
      residual_sigma = stats::sigma(fit), log_likelihood = as.numeric(stats::logLik(fit))))
}

export_erp_models <- function(fits, source_rows, output_path) {
  for (package in c("lme4", "jsonlite")) {
    erp_assert(requireNamespace(package, quietly = TRUE), paste("Existing package required:", package))
  }
  erp_assert(identical(sort(names(fits)), sort(names(erp_specs))) &&
    identical(sort(names(source_rows)), sort(names(erp_specs))), "Exactly FRN, P3a and P3b are required")
  erp_assert(!file.exists(output_path), "Output must be fresh")
  models <- lapply(names(erp_specs), function(name)
    erp_export_one(fits[[name]], source_rows[[name]], erp_specs[[name]]))
  names(models) <- names(erp_specs)
  package_names <- c("lme4", "lmerTest", "Matrix", "jsonlite", "minqa")
  versions <- lapply(package_names, function(name)
    if (requireNamespace(name, quietly = TRUE)) as.character(utils::packageVersion(name)) else NULL)
  names(versions) <- package_names
  document <- list(
    schema = "erp-original-model-export/v1",
    source_revision = "4f5767df1516e0ec3c234d51ba36e4b741eb60e8",
    binding_basis = "operator_supplied_original_source_rows",
    export_runtime = list(R = R.version.string, packages = versions,
      qualification = "Runtime at export only; original author and fit-time versions are not established"),
    models = models)
  # digits=NA retains double precision; null prevents missing diagnostics becoming strings.
  jsonlite::write_json(document, output_path, auto_unbox = TRUE, digits = NA,
                       na = "null", null = "null", pretty = FALSE)
  invisible(output_path)
}
