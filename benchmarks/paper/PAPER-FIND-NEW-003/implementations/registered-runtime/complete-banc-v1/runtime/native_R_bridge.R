# Source-owned typed reader. Definitions only; no native/library/data execution.
banc_bridge_need <- function(ok, message) {
  if (!isTRUE(ok)) stop(message, call. = FALSE)
}
banc_exact_fields <- function(x, fields) {
  banc_bridge_need(is.list(x) && length(x) == length(fields) &&
    !anyDuplicated(names(x)) && setequal(names(x), fields), "exact wire object fields")
}
banc_string <- function(x) is.character(x) && length(x) == 1L && !is.na(x)
banc_sha <- function(x) banc_string(x) && grepl("^[0-9a-f]{64}$", x)
banc_number <- function(x) is.numeric(x) && length(x) == 1L && is.finite(x)
banc_integer <- function(x) banc_number(x) && x == floor(x)
banc_strings <- function(x) {
  banc_bridge_need(is.list(x) && all(vapply(x, banc_string, logical(1))), "ordered string wire vector")
  unname(vapply(x, identity, character(1)))
}
banc_unwrap <- function(envelope, schema, fields) {
  banc_exact_fields(envelope, fields)
  banc_bridge_need(identical(envelope$schema, schema) && banc_string(envelope$payload_json) &&
    banc_integer(envelope$bytes) && envelope$bytes >= 0 && banc_sha(envelope$sha256), "wire envelope identity")
  raw <- charToRaw(enc2utf8(envelope$payload_json))
  banc_bridge_need(all(as.integer(raw) < 128L) && length(raw) == envelope$bytes &&
    identical(digest::digest(raw, algo = "sha256", serialize = FALSE), envelope$sha256), "exact ASCII wire bytes/hash")
  jsonlite::fromJSON(rawToChar(raw), simplifyVector = FALSE)
}
banc_native_sources <- function() list(
  R = list(path = "source/native-source/natverse_influencer/R/influence-calculator-r.R", bytes = 19472,
    sha256 = "8c8e468b3576110c11d24221e968cc586f6aa0bb98e583f420ad6419f9932583"),
  wrapper = list(path = "source/native-source/natverse_influencer/R/python-wrapper.R", bytes = 11207,
    sha256 = "00e38f9f1a328cdf9bd1907aa17ac5b6cbf0a7f7cfc3416cfc0ce06c6be2cda0"),
  Python = list(path = "source/native-source/DrugowitschLab_ConnectomeInfluenceCalculator/InfluenceCalculator/InfluenceCalculator.py", bytes = 14594,
    sha256 = "cdfefac56797355d2ff8aeec8d587ee5841d87904a12321618c613bd9697121d"),
  normalizer = list(path = "source/captured-functions/calculate_influence_norms.R", bytes = 3342,
    sha256 = "ad7ee89734be62d670f384365e074aa0d3b6aaefd2b38cea19e70d7d5913e895"))

banc_decode_table <- function(envelope, role, original_sha256) {
  t <- banc_unwrap(envelope, "banc_R_table_envelope_v1",
                  c("schema", "payload_json", "bytes", "sha256", "declared_content_sha256"))
  banc_bridge_need(banc_sha(envelope$declared_content_sha256) &&
    identical(envelope$declared_content_sha256, original_sha256), "table/original source identity")
  banc_exact_fields(t, c("schema", "role", "columns", "rows", "row_count"))
  banc_bridge_need(identical(t$schema, "banc_typed_R_table_v1") && identical(t$role, role) &&
    is.list(t$columns) && length(t$columns) > 0L && is.list(t$rows) &&
    banc_integer(t$row_count) && t$row_count >= 0 && t$row_count <= 2147483647 &&
    length(t$rows) == t$row_count, "complete typed table shape")
  for (column in t$columns) {
    banc_exact_fields(column, c("name", "r_type"))
    banc_bridge_need(banc_string(column$name) && nzchar(column$name) &&
      column$r_type %in% c("character", "logical", "integer32", "binary64"), "explicit original column dtype")
  }
  column_names <- vapply(t$columns, function(x) x$name, character(1))
  types <- vapply(t$columns, function(x) x$r_type, character(1))
  banc_bridge_need(!anyDuplicated(column_names) &&
    all(vapply(t$rows, function(row) is.list(row) && length(row) == length(column_names), logical(1))), "complete ordered row/column support")
  names(types) <- column_names
  if (role == "metadata") {
    banc_bridge_need(identical(unname(types["root_id"]), "character") &&
      (!("id" %in% column_names) || types[["id"]] == "character") &&
      (!("top_nt" %in% column_names) || types[["top_nt"]] == "character"), "root_id/id/transmitter string contracts")
  } else {
    banc_bridge_need(identical(unname(types[c("pre", "post", "norm")]), c("character", "character", "binary64")) &&
      types[["count"]] %in% c("integer32", "binary64"), "pre/post/count/norm remain distinct typed columns")
  }
  decode <- function(value, type) {
    if (is.null(value)) return(switch(type, character = NA_character_, logical = NA, integer32 = NA_integer_, binary64 = NA_real_))
    if (type == "character") { banc_bridge_need(banc_string(value), "string cell"); return(value) }
    if (type == "logical") { banc_bridge_need(is.logical(value) && length(value) == 1L && !is.na(value), "logical cell"); return(value) }
    if (type == "integer32") {
      banc_bridge_need(banc_string(value) && grepl("^(0|-[1-9][0-9]*|[1-9][0-9]*)$", value), "canonical integer wire cell")
      n <- suppressWarnings(as.integer(value))
      banc_bridge_need(!is.na(n) && n >= -2147483647 && identical(as.character(n), value), "exact R integer excluding NA sentinel")
      return(n)
    }
    banc_bridge_need(banc_string(value) && grepl("^[0-9a-f]{16}$", value), "binary64 big-endian hexadecimal cell")
    bytes <- as.raw(strtoi(substring(value, seq(1L, 15L, 2L), seq(2L, 16L, 2L)), base = 16L))
    n <- readBin(bytes, what = double(), n = 1L, size = 8L, endian = "big")
    banc_bridge_need(length(n) == 1L && is.finite(n), "finite exact binary64 value")
    n
  }
  columns <- lapply(seq_along(column_names), function(j) {
    type <- types[[j]]
    template <- switch(type, character = character(1), logical = logical(1), integer32 = integer(1), binary64 = double(1))
    vapply(t$rows, function(row) decode(row[[j]], type), template, USE.NAMES = FALSE)
  })
  names(columns) <- column_names
  # Direct construction preserves original names (including spaces/reserved
  # argument names), row order, empty columns and typed NAs; no factor inference.
  frame <- structure(columns, class = "data.frame", row.names = seq_len(t$row_count))
  id_columns <- if (role == "metadata") "root_id" else c("pre", "post")
  banc_bridge_need(all(vapply(frame[id_columns], function(v) !anyNA(v), logical(1))), "required string IDs cannot be missing")
  frame
}

banc_materialize_r_job <- function(job, expected_program_identity) {
  fields <- c("schema", "selection", "operator_branch", "graph_variant", "metadata_table", "edges_table", "source_members",
    "selected_edge_indices", "edge_indices_base", "count_thresh", "const", "signed", "neg_neurotransmitters", "seed_requests",
    "source_ids", "silenced_ids", "target_ids", "ordered_node_ids", "holds", "operator_contract", "qualified_exact_python_import_closure",
    "native_dtype_parity_qualified", "scientific_qualification")
  banc_exact_fields(job, fields)
  banc_exact_fields(job$selection, c("program_identity", "metadata_sha256", "edges_sha256", "materialization", "synapse_source",
    "annotation_profile", "id_cast_profile", "producer_revision"))
  s <- job$selection
  banc_bridge_need(identical(job$schema, "banc_native_r_job_v2") && banc_sha(expected_program_identity) &&
    identical(s$program_identity, expected_program_identity) && banc_sha(s$metadata_sha256) && banc_sha(s$edges_sha256) &&
    s$materialization == 888 && identical(s$synapse_source, "v2") &&
    identical(s$annotation_profile, "canonical_enriched_metadata") &&
    identical(s$id_cast_profile, "already_plain_string_ids_no_missing_scalars") &&
    identical(s$producer_revision, "2e78ce38e946ab80e120a42f504a019b3a567fef"), "independent programme and original source profile")
  banc_bridge_need(job$operator_branch %in% c("captured_R_unsigned_literal", "captured_R_signed_labelled_literal", "R_to_Python_literal_wrapper") &&
    job$graph_variant %in% c("full_CNS_source/sequential_supplied_calculator", "no_neck_CNS_source/sequential_supplied_calculator",
    "full_CNS_source/parallel_rebuild_default_global", "no_neck_CNS_source/parallel_rebuild_default_global") &&
    identical(job$edge_indices_base, "one"), "explicit original graph/operator/index branches")
  banc_bridge_need(banc_integer(job$count_thresh) && job$count_thresh >= 0 && job$count_thresh <= 2147483647 && banc_number(job$const) &&
    is.logical(job$signed) && length(job$signed) == 1L && !is.na(job$signed), "native scalar constructor types")
  banc_bridge_need(!endsWith(job$graph_variant, "/parallel_rebuild_default_global") || job$count_thresh == 5, "literal parallel threshold5")
  expected_sources <- banc_native_sources(); banc_exact_fields(job$source_members, names(expected_sources))
  for (name in names(expected_sources)) {
    member <- job$source_members[[name]]; banc_exact_fields(member, c("path", "bytes", "sha256"))
    expected <- expected_sources[[name]]
    banc_bridge_need(identical(member$path, expected$path) && identical(member$sha256, expected$sha256) &&
      banc_integer(member$bytes) && member$bytes == expected$bytes, "captured native source member")
  }
  banc_exact_fields(job$operator_contract, c("weight", "scaling_rule", "response_rule"))
  r <- job$operator_branch != "R_to_Python_literal_wrapper"
  scaling <- if (r) "largest_real_RSPECTRA_LR;scale_0.99/lambda_only_if_lambda>0.99;then_minus_identity" else
    "largest_real_SLEPc;require_converged_eigenpair;scale_lambda_max/lambda_if_lambda>0;then_minus_identity"
  response <- if (!r && job$signed) "real_part_preserving_sign" else "absolute_real_part"
  banc_bridge_need(identical(job$operator_contract$weight, if (r) "norm" else "count") &&
    identical(job$operator_contract$scaling_rule, scaling) && identical(job$operator_contract$response_rule, response) &&
    (!r || identical(job$signed, job$operator_branch == "captured_R_signed_labelled_literal")), "literal weight/scaling/sign/response contract")
  banc_bridge_need(identical(job$qualified_exact_python_import_closure, FALSE) &&
    identical(job$native_dtype_parity_qualified, FALSE) && identical(job$scientific_qualification, FALSE), "source build grants no native qualification")
  job$metadata <- banc_decode_table(job$metadata_table, "metadata", s$metadata_sha256)
  job$edges <- banc_decode_table(job$edges_table, "edges", s$edges_sha256)
  banc_bridge_need(is.list(job$selected_edge_indices) && all(vapply(job$selected_edge_indices, banc_integer, logical(1))), "one-based selected row vector")
  indices <- unlist(job$selected_edge_indices, use.names = FALSE)
  if (!length(indices)) indices <- integer(0)
  banc_bridge_need(all(indices >= 1 & indices <= nrow(job$edges)) && identical(indices, sort(unique(indices))), "complete ordered distinct selected indices")
  job$selected_edge_indices <- indices
  for (name in c("source_ids", "silenced_ids", "target_ids", "ordered_node_ids", "holds", "neg_neurotransmitters")) job[[name]] <- banc_strings(job[[name]])
  banc_bridge_need(is.list(job$seed_requests) && length(job$seed_requests) > 0L, "complete seed request list")
  job$seed_requests <- lapply(job$seed_requests, function(row) {
    banc_exact_fields(row, c("seed", "seed_ids", "silenced_ids")); banc_bridge_need(banc_string(row$seed), "seed name")
    row$seed_ids <- banc_strings(row$seed_ids); row$silenced_ids <- banc_strings(row$silenced_ids); row
  })
  banc_bridge_need(!anyDuplicated(vapply(job$seed_requests, function(row) row$seed, character(1))), "unique seed request identities")
  banc_bridge_need(setequal(unlist(lapply(job$seed_requests, function(row) row$seed_ids), use.names = FALSE), job$source_ids) &&
    all(unlist(lapply(job$seed_requests, function(row) row$silenced_ids), use.names = FALSE) %in% job$silenced_ids), "complete declared source/silencing support")
  job$bridge_receipt <- list(schema = "banc_R_bridge_receipt_v1", program_identity = expected_program_identity,
    metadata_wire_sha256 = job$metadata_table$sha256, edges_wire_sha256 = job$edges_table$sha256,
    exact_columns_rows_and_typed_nulls_preserved = TRUE, native_dtype_parity_qualified = FALSE)
  job
}

banc_read_r_job <- function(wire_raw, expected_program_identity, expected_payload_sha256) {
  banc_bridge_need(is.raw(wire_raw) && banc_sha(expected_payload_sha256), "raw serialized job and independently selected payload pin")
  wire <- jsonlite::fromJSON(rawToChar(wire_raw), simplifyVector = FALSE)
  job <- banc_unwrap(wire, "banc_native_r_wire_v2", c("schema", "payload_json", "bytes", "sha256"))
  banc_bridge_need(identical(wire$sha256, expected_payload_sha256), "independent complete handoff pin")
  job <- banc_materialize_r_job(job, expected_program_identity)
  job$bridge_receipt$job_payload_sha256 <- wire$sha256
  job
}

banc_run_influence_wire <- function(wire_raw, expected_program_identity, expected_payload_sha256, source_root, execution_authority = NULL) {
  job <- banc_read_r_job(wire_raw, expected_program_identity, expected_payload_sha256)
  contexts <- banc_prepare_wrapper_contexts(list(job), execution_authority, "influence")
  banc_native_influence(job, source_root, job$source_members, execution_context = contexts[[1L]])
}

banc_run_sensory_wires <- function(job, wires, expected_program_identity, expected_payload_sha256s, source_root, execution_authority = NULL) {
  banc_bridge_need(is.list(wires) && length(wires) == 3L && length(expected_payload_sha256s) == 3L, "all3 complete threshold handoffs")
  job$native_jobs <- lapply(seq_len(3L), function(k)
    banc_read_r_job(wires[[k]], expected_program_identity, expected_payload_sha256s[[k]]))
  banc_bridge_need(identical(vapply(job$native_jobs, function(x) as.integer(x$count_thresh), integer(1)), c(3L, 5L, 10L)), "distinct selected3/5/10 jobs")
  first <- job$native_jobs[[1L]]
  banc_bridge_need(all(vapply(job$native_jobs, function(x)
    identical(x$selection, first$selection) && identical(x$operator_branch, first$operator_branch) &&
    identical(x$graph_variant, first$graph_variant) && identical(x$source_ids, first$source_ids) &&
    identical(x$silenced_ids, first$silenced_ids) && identical(x$target_ids, first$target_ids) &&
    identical(x$seed_requests, first$seed_requests) && identical(x$selected_edge_indices, first$selected_edge_indices) &&
    identical(x$operator_contract, first$operator_contract) && identical(x$const, first$const) &&
    identical(x$signed, first$signed) && identical(x$neg_neurotransmitters, first$neg_neurotransmitters) &&
    identical(x$metadata_table, first$metadata_table) &&
    identical(x$edges_table, first$edges_table) && identical(x$source_members, first$source_members), logical(1))), "same full sensory source/operator support across thresholds")
  contexts <- banc_prepare_wrapper_contexts(job$native_jobs, execution_authority, "sensory")
  banc_native_sensory(job, source_root, first$source_members, execution_contexts = contexts)
}
