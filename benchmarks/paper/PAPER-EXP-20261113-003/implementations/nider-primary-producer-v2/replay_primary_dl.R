# Internal driver; launch via replay_primary_dl.py in a fresh owner-controlled process.
# Never source the official file: only parsed, authenticated, complete expressions run.
stopifnot(identical(as.character(getRversion()), "4.3.2"))
required <- c(renv = "1.0.4", here = "1.0.1", readxl = "1.4.3", stringr = "1.5.1",
              dplyr = "1.1.4", meta = "7.0.0", metafor = "4.6.0",
              jsonlite = "1.8.8", digest = "0.6.35")
for (package in names(required)) {
  if (!requireNamespace(package, quietly = TRUE)) stop("Missing installed package: ", package)
  if (packageVersion(package) != package_version(required[[package]]))
    stop("Installed package version mismatch: ", package)
}
job <- jsonlite::fromJSON("job.json", simplifyVector = FALSE)
sha_file <- function(path) digest::digest(file = path, algo = "sha256", serialize = FALSE)
paths <- c(workbook = "data/studyInformation/studyInformation_publication.xlsx",
           script = "official.R", lock = "original-renv.lock", schema = "FIELD_SCHEMA.json")
for (key in names(paths)) stopifnot(identical(sha_file(paths[[key]]), job$pins[[key]]))
for (name in names(job$implementation_hashes))
  stopifnot(identical(sha_file(name), job$implementation_hashes[[name]]))
lock <- jsonlite::fromJSON(paths[["lock"]], simplifyVector = FALSE)
schema <- jsonlite::fromJSON(paths[["schema"]], simplifyVector = FALSE)
source("collector.R", local = TRUE, keep.source = TRUE)
source("source_selection.R", local = TRUE, keep.source = TRUE)

check_loaded <- function() {
  lapply(loadedNamespaces(), function(package) {
    version <- as.character(packageVersion(package))
    desc <- packageDescription(package)
    if (!identical(desc$Priority, "base")) {
      pinned <- lock$Packages[[package]]
      need(!is.null(pinned) && package_version(pinned$Version) == package_version(version),
           paste("loaded dependency missing or different from original lock", package))
    }
    list(package = package, version = version, path = find.package(package))
  })
}
invisible(check_loaded())

expressions <- parse(paths[["script"]], keep.source = TRUE, encoding = "UTF-8")
selected <- select_source_expressions(expressions, job$expressions)
source_lines <- strsplit(readChar(paths[["script"]], file.info(paths[["script"]])$size,
                                 useBytes = TRUE), "\n", fixed = TRUE)[[1L]]
for (span in job$expressions) {
  source_text <- paste0(paste(source_lines[span$start:span$end], collapse = "\n"), "\n")
  need(identical(digest::digest(source_text, algo = "sha256", serialize = FALSE), span$sha256),
       "selected expression text mismatch")
}
author_env <- new.env(parent = globalenv())
original <- NULL
warnings_seen <- character()
for (i in seq_along(selected)) {
  span <- job$expressions[[i]]
  if (span$start == 28L) {
    resolved <- normalizePath(here::here("data", "studyInformation", "studyInformation_publication.xlsx"),
                              mustWork = TRUE)
    need(identical(resolved, normalizePath(paths[["workbook"]], mustWork = TRUE)),
         "here workbook resolution mismatch before read")
    need(identical(sha_file(resolved), job$pins$workbook), "workbook changed before read")
  }
  withCallingHandlers(eval(expressions[[selected[i]]], envir = author_env), warning = function(w) {
    warnings_seen <<- c(warnings_seen, conditionMessage(w))
  })
  if (span$start == 29L) original <- author_env$dfcorrs
}
need(!is.null(original), "original scientific dataframe not captured")
document <- collect_full120(author_env, original, schema, job$arm, job$pins$workbook)
jsonlite::write_json(document, "full120.json", auto_unbox = TRUE, digits = NA, pretty = FALSE)
need(file.info("full120.json")$size <= 65536, "full120 output exceeds interface limit")
packages <- check_loaded()
runtime <- list(R_version = as.character(getRversion()), platform = R.version$platform,
  R_home = R.home(), locale = Sys.getlocale(), timezone = Sys.timezone(),
  executable_sha256 = sha_file(file.path(R.home("bin"), "exec", "R")),
  loaded_packages = packages, session_info = capture.output(sessionInfo()),
  evaluated_expression_count = length(selected), warnings = as.list(warnings_seen),
  source_record_count = nrow(original), postmerge_record_count = nrow(author_env$dfcorrs),
  clean_source_replay_not_recovered_historical_ambient_settings = TRUE)
jsonlite::write_json(runtime, "runtime.json", auto_unbox = TRUE, digits = NA, pretty = TRUE)
