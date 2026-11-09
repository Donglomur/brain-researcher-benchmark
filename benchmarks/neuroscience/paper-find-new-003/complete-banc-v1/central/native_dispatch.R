# Concrete source-owned R process entry. Never sourced or parsed by inspection.
# Parent admits independently signed runtime/job evidence before spawning us.
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1L) stop("one exact source-owned dispatch document")
d <- jsonlite::fromJSON(args[[1L]], simplifyVector = FALSE)
root <- d$source_root
for (member in c("native_R_bridge.R", "native_R_execution.R", "native_R.R"))
  sys.source(file.path(root, member), envir = globalenv())
banc_exact_fields(d, c("schema", "kind", "program_identity", "job", "wires", "native_authority", "source_root", "output_path"))
banc_need(identical(d$schema, "banc_R_dispatch_v1"), "closed R dispatcher")

read_raw <- function(member) {
  banc_need(!grepl("(^/|(^|/)\\.\\.(/|$)|\\\\)", member$path), "ordinary staged file")
  bytes <- readBin(member$path, what = "raw", n = member$bytes + 1)
  banc_need(length(bytes) == member$bytes && identical(digest::digest(bytes, algo = "sha256", serialize = FALSE), member$sha256), "exact complete staged body")
  bytes
}

# Explicit generic R values retain types and IEEE bits, including typed nulls.
# This closed data reader is not R source, expression evaluation or a callback.
typed_value <- function(x) {
  if (!is.list(x) || is.null(x$encoding)) return(x)
  if (identical(x$encoding, "typed_frame_v1")) {
    banc_exact_fields(x, c("encoding", "columns", "rows"))
    names <- vapply(x$columns, function(c) c$name, character(1))
    banc_need(!anyDuplicated(names) && length(names) > 0L, "ordered unique frame columns")
    decode <- function(v, t) {
      if (is.null(v)) return(switch(t, character = NA_character_, logical = NA, integer32 = NA_integer_, binary64 = NA_real_, stop("dtype")))
      if (t == "character") { banc_need(banc_string(v), "string cell"); return(v) }
      if (t == "logical") { banc_need(is.logical(v) && length(v) == 1L && !is.na(v), "logical cell"); return(v) }
      if (t == "integer32") {
        banc_need(banc_string(v) && grepl("^(0|-[1-9][0-9]*|[1-9][0-9]*)$", v), "integer cell")
        n <- suppressWarnings(as.integer(v)); banc_need(!is.na(n) && identical(as.character(n), v), "exact integer cell"); return(n)
      }
      banc_need(t == "binary64" && banc_string(v) && grepl("^[0-9a-f]{16}$", v), "binary64 bits")
      raw <- as.raw(strtoi(substring(v, seq(1L, 15L, 2L), seq(2L, 16L, 2L)), 16L))
      n <- readBin(raw, double(), n = 1L, size = 8L, endian = "big")
      banc_need(is.finite(n), "finite IEEE cell"); n
    }
    columns <- lapply(seq_along(names), function(i) {
      t <- x$columns[[i]]$r_type
      template <- switch(t, character = character(1), logical = logical(1), integer32 = integer(1), binary64 = double(1), stop("dtype"))
      vapply(x$rows, function(row) { banc_need(length(row) == length(names), "row width"); decode(row[[i]], t) }, template)
    })
    names(columns) <- names
    return(structure(columns, class = "data.frame", row.names = seq_along(x$rows)))
  }
  if (identical(x$encoding, "named_matrix_v1")) {
    banc_exact_fields(x, c("encoding", "rows", "columns", "values"))
    rows <- banc_strings(x$rows); columns <- banc_strings(x$columns)
    banc_need(length(x$values) == length(rows) * length(columns), "complete matrix")
    return(matrix(unlist(x$values), nrow = length(rows), ncol = length(columns), dimnames = list(rows, columns)))
  }
  stop("unknown typed value encoding")
}
materialize <- function(x) {
  if (!is.list(x)) return(x)
  if (!is.null(x$encoding)) return(typed_value(x))
  lapply(x, materialize)
}
authority <- d$native_authority$wrapper
if (!is.null(authority)) {
  banc_exact_fields(authority, c("capability", "expected_authority_id", "expected_qualification_evidence_sha256", "expected_runtime_closure_sha256"))
  authority <- list(capability_raw = read_raw(authority$capability), expected_capability_sha256 = authority$capability$sha256,
    expected_authority_id = authority$expected_authority_id,
    expected_qualification_evidence_sha256 = authority$expected_qualification_evidence_sha256,
    expected_runtime_closure_sha256 = authority$expected_runtime_closure_sha256)
}
if (identical(d$kind, "influence_R_wire")) {
  banc_need(length(d$wires) == 1L, "one complete native wire")
  value <- banc_run_influence_wire(read_raw(d$wires[[1L]]$file), d$program_identity,
    d$wires[[1L]]$payload_sha256, root, execution_authority = authority)
} else if (identical(d$kind, "sensory_R_wires")) {
  job <- materialize(d$job)
  # Exact scalar vectors required by the original worker; no label recoding.
  for (name in c("thresholds", "seed_order", "target_order", "matched_groups", "target_ids")) job[[name]] <- unlist(job[[name]], use.names = FALSE)
  job$seed_map <- unlist(job$seed_map); job$target_map <- unlist(job$target_map)
  job$ordered_nodes_by_threshold <- lapply(job$ordered_nodes_by_threshold, function(x) unlist(x, use.names = FALSE))
  value <- banc_run_sensory_wires(job, lapply(d$wires, function(w) read_raw(w$file)), d$program_identity,
    lapply(d$wires, function(w) w$payload_sha256), root, execution_authority = authority)
} else if (identical(d$kind, "sensory_python_normalization")) {
  job <- materialize(d$job)
  e <- new.env(parent = globalenv())
  banc_source_pinned(root, banc_native_sources()$normalizer, e)
  value <- e$calculate_influence_norms(job$rows)
} else if (identical(d$kind, "native_statistics")) {
  job <- materialize(d$job)
  # Vector arguments are explicit in the declared original recipe.
  for (name in c("diagonal", "off_diagonal", "matched_rows")) if (!is.null(job[[name]])) job[[name]] <- unlist(job[[name]], use.names = FALSE)
  functions <- list(path = "source/primary-source/R/startup/banc-functions.R")
  path <- file.path(root, functions$path)
  functions$bytes <- file.info(path)$size
  functions$sha256 <- digest::digest(file = path, algo = "sha256", serialize = FALSE)
  value <- banc_native_statistics(job, root, list(functions = functions))
} else if (identical(d$kind, "original_figure")) {
  evidence <- d$native_authority$original_figure
  banc_need(identical(evidence$program_identity, d$program_identity) && identical(evidence$script, d$job$script) &&
    identical(evidence$runtime_context_qualified, TRUE) && banc_sha(evidence$qualification_evidence_sha256), "independently admitted exact original figure context")
  # These are execution context properties derived only from independent
  # operator evidence; the original source job and scientific flags stay false.
  job <- list(script = d$job$script, complete_source_context_qualified = TRUE,
    offline_external_enclosure_qualified = TRUE, upstream_raw_to_product_receipts_qualified = TRUE)
  member <- evidence$script_member; members <- list(); members[[job$script]] <- member
  value <- banc_original_figure(job, root, list(figure_scripts = members))
} else stop("unknown concrete R producer")
jsonlite::write_json(value, d$output_path, auto_unbox = TRUE, null = "null", na = "null", digits = NA, dataframe = "rows")
