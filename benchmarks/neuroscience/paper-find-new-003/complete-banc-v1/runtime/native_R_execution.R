# Future execution admission. Definitions only: source jobs remain false-qualified.
# Load together with native_R_bridge.R/native_R.R from the authenticated runtime.
# Authority pins come from the independent trusted runner, never a candidate job.
banc_runtime_path <- function(x) {
  banc_bridge_need(banc_string(x) && all(as.integer(charToRaw(enc2utf8(x))) < 128L) && startsWith(x, "/") &&
    !grepl("//|(^|/)\\.\\.?(/|$)|/$", x), "canonical absolute qualified-runtime path")
  x
}

banc_runtime_closure <- function(raw_json) {
  banc_bridge_need(banc_string(raw_json), "exact closure JSON string")
  raw <- charToRaw(enc2utf8(raw_json))
  banc_bridge_need(all(as.integer(raw) < 128L), "ASCII closure bytes")
  c <- jsonlite::fromJSON(rawToChar(raw), simplifyVector = FALSE)
  banc_exact_fields(c, c("schema", "conda_environment", "python_executable", "python_prefix", "python_version",
    "package_init_path", "calculator_source_path", "distribution_versions", "files"))
  banc_bridge_need(identical(c$schema, "banc_python_runtime_closure_v1") &&
    identical(c$conda_environment, "r-reticulate") && banc_string(c$python_version) && nzchar(c$python_version), "original wrapper environment/version")
  for (k in c("python_executable", "python_prefix", "package_init_path", "calculator_source_path")) banc_runtime_path(c[[k]])
  versions <- c$distribution_versions
  banc_exact_fields(versions, c("numpy", "pandas", "bidict", "petsc4py", "slepc4py"))
  banc_bridge_need(all(vapply(versions, function(x) banc_string(x) && nzchar(x), logical(1))), "all qualified distribution versions")
  banc_bridge_need(is.list(c$files) && length(c$files) > 0L, "independently qualified full file closure")
  for (file in c$files) {
    banc_exact_fields(file, c("path", "bytes", "sha256")); banc_runtime_path(file$path)
    banc_bridge_need(banc_integer(file$bytes) && file$bytes >= 0 && file$bytes <= 9007199254740991 && banc_sha(file$sha256), "qualified file descriptor")
  }
  paths <- vapply(c$files, function(x) x$path, character(1))
  # Paths are ASCII in the qualification format: radix order matches Python.
  banc_bridge_need(all(vapply(paths, function(x) all(as.integer(charToRaw(enc2utf8(x))) < 128L), logical(1))) &&
    identical(paths, sort(unique(paths), method = "radix")), "canonical unique ASCII runtime-file order")
  banc_bridge_need(all(c(c$python_executable, c$package_init_path, c$calculator_source_path) %in% paths), "actual interpreter/package/calculator files in closure")
  actual <- c$files[[match(c$calculator_source_path, paths)]]; literal <- banc_native_sources()$Python
  banc_bridge_need(actual$bytes == literal$bytes && identical(actual$sha256, literal$sha256), "exact captured calculator source")
  list(closure = c, sha256 = digest::digest(raw, algo = "sha256", serialize = FALSE))
}

banc_admit_execution_description <- function(authority, job, operation) {
  banc_exact_fields(authority, c("capability_raw", "expected_capability_sha256", "expected_authority_id",
    "expected_qualification_evidence_sha256", "expected_runtime_closure_sha256"))
  banc_bridge_need(is.raw(authority$capability_raw) && banc_sha(authority$expected_capability_sha256) &&
    banc_sha(authority$expected_qualification_evidence_sha256) && banc_sha(authority$expected_runtime_closure_sha256) &&
    banc_string(authority$expected_authority_id) && nzchar(authority$expected_authority_id), "separately selected authority inputs")
  banc_bridge_need(identical(digest::digest(authority$capability_raw, algo = "sha256", serialize = FALSE),
    authority$expected_capability_sha256), "external capability pin before any runtime observation")
  v <- jsonlite::fromJSON(rawToChar(authority$capability_raw), simplifyVector = FALSE)
  banc_exact_fields(v, c("schema", "authority_id", "program_identity", "qualification_scope", "qualification_evidence_sha256",
    "runtime_closure_json", "runtime_closure_sha256", "allowed_job_payload_sha256s", "allowed_entrypoints",
    "source_members", "python_source_revision", "scientific_qualification"))
  banc_bridge_need(identical(v$schema, "banc_wrapper_execution_capability_v1") &&
    identical(v$authority_id, authority$expected_authority_id) &&
    identical(v$program_identity, job$bridge_receipt$program_identity) && banc_sha(v$program_identity) &&
    identical(job$operator_branch, "R_to_Python_literal_wrapper"), "independent authority/programme and literal wrapper")
  banc_bridge_need(identical(v$qualification_scope, "qualified_exact_python_import_closure_only") &&
    identical(v$qualification_evidence_sha256, authority$expected_qualification_evidence_sha256) &&
    identical(v$python_source_revision, "6b70294094ebcd97166ab646c5322eed957f8936"), "independent evidence and exact Python revision")
  # Materialization already authenticated every member. JSON object order is irrelevant.
  banc_exact_fields(v$source_members, names(banc_native_sources()))
  for (name in names(banc_native_sources())) {
    actual <- v$source_members[[name]]; expected <- banc_native_sources()[[name]]
    banc_exact_fields(actual, c("path", "bytes", "sha256"))
    banc_bridge_need(identical(actual$path, expected$path) && identical(actual$sha256, expected$sha256) &&
      banc_integer(actual$bytes) && actual$bytes == expected$bytes, "capability exact native and normalizer sources")
  }
  hashes <- banc_strings(v$allowed_job_payload_sha256s); entries <- banc_strings(v$allowed_entrypoints)
  banc_bridge_need(length(hashes) > 0L && !anyDuplicated(hashes) && all(vapply(hashes, banc_sha, logical(1))) &&
    banc_sha(job$bridge_receipt$job_payload_sha256) && job$bridge_receipt$job_payload_sha256 %in% hashes, "capability names this exact source wire")
  banc_bridge_need(length(entries) > 0L && !anyDuplicated(entries) && all(entries %in% c("influence", "sensory")) &&
    operation %in% entries, "separately selected entrypoint")
  closure <- banc_runtime_closure(v$runtime_closure_json)
  banc_bridge_need(identical(closure$sha256, v$runtime_closure_sha256) &&
    identical(closure$sha256, authority$expected_runtime_closure_sha256), "independently qualified closure pin")
  banc_bridge_need(identical(v$scientific_qualification, FALSE) &&
    identical(job$qualified_exact_python_import_closure, FALSE) && identical(job$native_dtype_parity_qualified, FALSE) &&
    identical(job$scientific_qualification, FALSE), "source/scientific qualification remains false")
  list(capability = v, capability_sha256 = authority$expected_capability_sha256, closure = closure$closure,
    job_payload_sha256 = job$bridge_receipt$job_payload_sha256, operation = operation)
}

banc_observe_python_runtime <- function(qualified_closure) {
  # This is real future native observation, not a candidate-supplied callback.
  # It is called only after every applicable job has passed authority preflight.
  reticulate::use_condaenv("r-reticulate", required = TRUE)
  sys <- reticulate::import("sys", convert = FALSE)
  inspect <- reticulate::import("inspect", convert = FALSE)
  metadata <- reticulate::import("importlib.metadata", convert = FALSE)
  module <- reticulate::import("InfluenceCalculator", convert = FALSE)
  actual_path <- function(value) {
    value <- reticulate::py_to_r(value)
    banc_bridge_need(banc_string(value), "observed Python path")
    normalizePath(value, winslash = "/", mustWork = TRUE)
  }
  observed <- qualified_closure
  observed$python_executable <- actual_path(sys$executable)
  observed$python_prefix <- actual_path(sys$prefix)
  observed$python_version <- reticulate::py_to_r(sys$version)
  observed$package_init_path <- actual_path(reticulate::py_get_attr(module, "__file__"))
  observed$calculator_source_path <- actual_path(inspect$getsourcefile(module$InfluenceCalculator))
  observed$distribution_versions <- lapply(names(qualified_closure$distribution_versions), function(name)
    reticulate::py_to_r(metadata$version(name)))
  names(observed$distribution_versions) <- names(qualified_closure$distribution_versions)
  observed$files <- lapply(qualified_closure$files, function(member) {
    path <- normalizePath(member$path, winslash = "/", mustWork = TRUE)
    banc_bridge_need(identical(path, member$path), "qualified canonical runtime path")
    before <- file.info(path)
    banc_bridge_need(nrow(before) == 1L && !is.na(before$isdir) && !before$isdir, "observed ordinary runtime file")
    hash <- digest::digest(file = path, algo = "sha256", serialize = FALSE)
    after <- file.info(path)
    banc_bridge_need(identical(before[c("size", "mtime", "ctime")], after[c("size", "mtime", "ctime")]), "runtime file changed during observation")
    list(path = path, bytes = unname(after$size), sha256 = hash)
  })
  observed
}

banc_confirm_execution <- function(description, observed_runtime) {
  # jsonlite may parse small integer sizes as integers; observed file sizes are
  # doubles. Compare their exact allowed integer values, not R storage classes.
  expected <- description$closure
  banc_exact_fields(observed_runtime, names(expected))
  for (k in setdiff(names(expected), "files"))
    banc_bridge_need(identical(observed_runtime[[k]], expected[[k]]), "actual runtime source/path/version differs from qualification")
  banc_bridge_need(length(observed_runtime$files) == length(expected$files), "complete observed file closure")
  for (i in seq_along(expected$files)) {
    actual <- observed_runtime$files[[i]]; wanted <- expected$files[[i]]
    banc_exact_fields(actual, c("path", "bytes", "sha256"))
    banc_bridge_need(identical(actual$path, wanted$path) && identical(actual$sha256, wanted$sha256) &&
      banc_integer(actual$bytes) && actual$bytes == wanted$bytes, "actual runtime file identity differs from qualification")
  }
  v <- description$capability
  structure(list(program_identity = v$program_identity, job_payload_sha256 = description$job_payload_sha256,
    capability_sha256 = description$capability_sha256, authority_id = v$authority_id,
    qualification_evidence_sha256 = v$qualification_evidence_sha256,
    runtime_closure_sha256 = v$runtime_closure_sha256, operation = description$operation,
    scientific_qualification = FALSE), class = "banc_wrapper_execution")
}

banc_require_wrapper_execution <- function(job, context) {
  banc_bridge_need(inherits(context, "banc_wrapper_execution") &&
    identical(context$program_identity, job$bridge_receipt$program_identity) &&
    identical(context$job_payload_sha256, job$bridge_receipt$job_payload_sha256) &&
    banc_sha(context$capability_sha256) && banc_sha(context$qualification_evidence_sha256) &&
    banc_sha(context$runtime_closure_sha256) && banc_string(context$authority_id) && nzchar(context$authority_id) &&
    context$operation %in% c("influence", "sensory") && identical(context$scientific_qualification, FALSE),
    "separately admitted execution capability bound to this job")
  banc_bridge_need(identical(job$qualified_exact_python_import_closure, FALSE) &&
    identical(job$native_dtype_parity_qualified, FALSE) && identical(job$scientific_qualification, FALSE),
    "source description remains false-qualified")
  invisible(context)
}

banc_prepare_wrapper_contexts <- function(jobs, authority, operation) {
  wrapper <- identical(jobs[[1L]]$operator_branch, "R_to_Python_literal_wrapper")
  if (!wrapper) {
    banc_bridge_need(is.null(authority), "Python capability does not select or rewrite R operators")
    return(rep(list(NULL), length(jobs)))
  }
  # All3 sensory payloads must be admitted before even one native import.
  descriptions <- lapply(jobs, function(job) banc_admit_execution_description(authority, job, operation))
  observed <- banc_observe_python_runtime(descriptions[[1L]]$closure)
  lapply(descriptions, function(description) banc_confirm_execution(description, observed))
}
