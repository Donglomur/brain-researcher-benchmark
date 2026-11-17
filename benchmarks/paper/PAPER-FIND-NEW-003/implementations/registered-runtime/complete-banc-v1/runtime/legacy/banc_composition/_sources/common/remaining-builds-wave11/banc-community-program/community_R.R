# Source-derived native R branch, deliberately separate from Python float32.
# No startup/source/file/network/publication side effects at load or invocation.
# Function invocation would run native scientific algorithms and is NOT exercised
# by source-build controls. Caller supplies complete original tables and labels.
banc_community_R <- function(meta, edgelist, binding, label_origin,
                             prior_labels = NULL, prior_label_sha256 = NULL,
                             runtime_declaration) {
  if (!is.data.frame(meta) || !is.data.frame(edgelist)) stop("Complete data frames required")
  required <- c("branch", "producer_revision", "producer_sha256", "materialization",
                "synapse_source", "metadata_sha256", "edges_sha256")
  if (!is.list(binding) || !all(required %in% names(binding))) stop("Explicit source binding required")
  if (!identical(binding$branch, "R") ||
      !identical(binding$producer_revision, "65adfc22458b6084830c71f40e8c71c26414609e") ||
      !identical(binding$producer_sha256, "da0aa17296e30191bd439e0ad005d9bbbabd3c7f57ce8873f1074bae356c7fcc") ||
      binding$materialization != 888 || !identical(binding$synapse_source, "v2"))
    stop("Only declared original R / 888 / v2 profile")
  for (name in c("metadata_sha256", "edges_sha256")) {
    value <- binding[[name]]
    if (!is.character(value) || length(value) != 1L || is.na(value) ||
        !grepl("^[a-f0-9]{64}$", value)) stop("Declared input SHA256 required")
  }
  if (!label_origin %in% c("seatable_snapshot", "local_metadata_fallback")) stop("Explicit R label source required")
  if (label_origin == "local_metadata_fallback" && !is.null(prior_labels)) stop("Fallback labels derive from same metadata")
  if (label_origin == "local_metadata_fallback" && !is.null(prior_label_sha256)) stop("Fallback labels inherit metadata binding")
  if (label_origin == "seatable_snapshot" && !is.data.frame(prior_labels)) stop("Complete supplied prior-label snapshot required")
  if (label_origin == "seatable_snapshot" &&
      (!is.character(prior_label_sha256) || length(prior_label_sha256) != 1L ||
       is.na(prior_label_sha256) || !grepl("^[a-f0-9]{64}$", prior_label_sha256)))
    stop("Explicit complete prior-label snapshot hash declaration required")
  packages <- c("dplyr", "Matrix", "RSpectra", "uwot")
  observed <- c(list(R = R.version.string), setNames(lapply(packages, function(p) as.character(utils::packageVersion(p))), packages))
  if (!identical(runtime_declaration, observed)) stop("Exact declared native R runtime required; not historical qualification")
  `%>%` <- dplyr::`%>%`
  dataset_version <- 888L
  id_col <- "root_888"
  min_connection_strength <- 1L
  cluster_count <- 13L
  cluster_seed <- 10
  embedding_seed <- 3
  umap_n_neighbors <- 100
  meta$root_id <- meta[[id_col]]
  meta <- meta[!is.na(meta$root_id) & meta$root_id != "", ]
  message(sprintf("  Meta: %d neurons, Edgelist: %d edges",
                  nrow(meta), nrow(edgelist)))

  # ---------------------------------------------------------------
  # 2. Quality filter
  # ---------------------------------------------------------------
  message("Applying quality filter...")
  meta <- meta %>%
    dplyr::filter(
      !grepl("glia|trachea|not_a_neuron|merge|debris",
             super_class, ignore.case = TRUE),
      !grepl("GLIA|TRACHEA|NOT_A_NEURON|DEBRIS|MERGE|DELETE", status),
      proofread == "TRUE" | roughly_proofread == "TRUE"
    )
  message(sprintf("  After quality filter: %d neurons", nrow(meta)))

  # ---------------------------------------------------------------
  # 3. Assign clustering_set
  # ---------------------------------------------------------------
  # Identify neck_connective neurons via super_class (ascending/descending) —
  # backwards-compatible with the now-deprecated region=="neck_connective" filter.
  clustering_regions <- c("central_brain", "ventral_nerve_cord")
  excluded_sc <- c("sensory", "motor", "efferent", "afferent", "visceral")

  meta <- meta %>%
    dplyr::mutate(
      clustering_set = dplyr::case_when(
        super_class %in% c("visual_centrifugal", "visual_projection") ~ "visual",
        grepl("ascending|descending", super_class) ~ "neck_connective",
        region %in% clustering_regions &
          !grepl(paste(excluded_sc, collapse = "|"), super_class) ~ region,
        TRUE ~ NA_character_
      )
    )

  clustering_values <- c("central_brain", "neck_connective",
                         "ventral_nerve_cord", "visual")
  cluster_ids <- meta %>%
    dplyr::filter(clustering_set %in% clustering_values) %>%
    dplyr::pull(root_id) %>%
    unique()
  message(sprintf("  Neurons in clustering set: %d", length(cluster_ids)))

  # ---------------------------------------------------------------
  # 4. Filter edgelist + prune
  # ---------------------------------------------------------------
  message("Filtering edgelist...")
  el <- edgelist %>%
    dplyr::filter(
      count >= min_connection_strength,
      pre != post,
      pre %in% cluster_ids,
      post %in% cluster_ids
    )
  message(sprintf("  Edges after filter: %d", nrow(el)))

  # Iterative pruning to strongly connected component
  message("Pruning to strongly connected component...")
  prev_n <- -1
  while (TRUE) {
    both <- intersect(unique(el$pre), unique(el$post))
    if (length(both) == prev_n) break
    prev_n <- length(both)
    el <- el %>% dplyr::filter(pre %in% both, post %in% both)
    message(sprintf("  Pruning: %d neurons", prev_n))
  }

  neuron_ids <- sort(both)
  n <- length(neuron_ids)
  message(sprintf("  Final: %d neurons, %d edges", n, nrow(el)))

  # ---------------------------------------------------------------
  # 5. Build sparse adjacency matrix
  # ---------------------------------------------------------------
  message("Building adjacency matrix...")
  id_map <- setNames(seq_along(neuron_ids), neuron_ids)

  # Aggregate weights per pre-post pair
  el_agg <- el %>%
    dplyr::group_by(pre, post) %>%
    dplyr::summarise(weight = sum(count), .groups = "drop")

  i_idx <- id_map[el_agg$pre]
  j_idx <- id_map[el_agg$post]

  adj <- Matrix::sparseMatrix(
    i = i_idx, j = j_idx, x = el_agg$weight,
    dims = c(n, n),
    dimnames = list(neuron_ids, neuron_ids)
  )

  # Column-normalize
  col_sums <- Matrix::colSums(adj)
  col_sums[col_sums == 0] <- 1
  adj_norm <- adj %*% Matrix::Diagonal(n, 1 / col_sums)

  # Symmetrize
  adj_sym <- 0.5 * (adj_norm + Matrix::t(adj_norm))
  message("  Matrix built and symmetrized")

  # ---------------------------------------------------------------
  # 6. Spectral clustering
  # ---------------------------------------------------------------
  message(sprintf("Computing spectral clustering (k=%d)...", cluster_count))

  if (n <= cluster_count) stop("Original eigenproblem requires n > k; no reduced substitute")

  # Normalized Laplacian: L = I - D^{-1/2} A D^{-1/2}
  deg <- Matrix::rowSums(adj_sym)
  deg[deg == 0] <- 1
  deg_inv_sqrt <- 1 / sqrt(deg)
  D_inv_sqrt <- Matrix::Diagonal(n, deg_inv_sqrt)
  lap <- Matrix::Diagonal(n) - D_inv_sqrt %*% adj_sym %*% D_inv_sqrt

  # Bottom-k eigenvectors
  eig <- RSpectra::eigs_sym(lap, k = cluster_count, which = "SM")
  eigvec <- eig$vectors

  # Row-normalize
  row_norms <- sqrt(rowSums(eigvec^2))
  row_norms[row_norms == 0] <- 1
  embedding <- eigvec / row_norms

  # KMeans
  set.seed(cluster_seed)
  km <- kmeans(embedding, centers = cluster_count, nstart = 25, iter.max = 100)
  labels <- km$cluster  # 1-indexed

  for (cl in sort(unique(labels))) {
    message(sprintf("  Cluster %d: %d neurons", cl, sum(labels == cl)))
  }

  # ---------------------------------------------------------------
  # 7. UMAP embedding
  # ---------------------------------------------------------------
  message("Computing UMAP embedding...")
  umap_result <- uwot::umap(
    embedding,
    n_neighbors = umap_n_neighbors,
    metric = "cosine",
    min_dist = 0,
    n_components = 2,
    seed = embedding_seed,
    n_threads = 1
  )

  result <- data.frame(
    root_id = neuron_ids,
    spectral_cluster = labels,
    umap_x = umap_result[, 1],
    umap_y = umap_result[, 2],
    stringsAsFactors = FALSE
  )

  # Join supervoxel_id and position from meta
  meta_cols <- meta %>%
    dplyr::select(root_id, supervoxel_id, position) %>%
    dplyr::distinct(root_id, .keep_all = TRUE)
  result <- result %>%
    dplyr::left_join(meta_cols, by = "root_id")

  # Query/fallback has already been resolved by an explicitly supplied source.
  # This in-memory program performs neither a SeaTable call nor silent fallback.
  st <- if (label_origin == "seatable_snapshot") prior_labels else
    meta %>% dplyr::select(root_id, cns_network)
  # Normalise column names
  if (id_col %in% names(st)) {
    names(st)[names(st) == id_col] <- "root_id"
  }
  st <- st %>%
    dplyr::filter(!is.na(cns_network), cns_network != "") %>%
    dplyr::distinct(root_id, .keep_all = TRUE)

  # Assign cns_network per cluster by plain per-cluster majority vote on the
  # OLD SeaTable cns_network labels (neurons missing a label are discounted).
  # Same OLD label may be assigned to multiple clusters when the network
  # genuinely splits a region (e.g., leg VNC into left/right). Clusters with
  # zero overlap with any OLD label keep their numeric cluster string.
  result <- result %>%
    dplyr::left_join(
      st %>% dplyr::select(root_id, existing_cns = cns_network),
      by = "root_id"
    )
  result$cns_network <- as.character(result$spectral_cluster)

  cluster_ids <- sort(unique(result$spectral_cluster))
  old_labels <- sort(unique(result$existing_cns[
    !is.na(result$existing_cns) & result$existing_cns != ""
  ]))

  if (length(old_labels) == 0L) {
    message("  No old cns_network labels available — using cluster numbers")
  } else {
    for (cl in cluster_ids) {
      mask <- result$spectral_cluster == cl
      ex <- result$existing_cns[mask]
      ex <- ex[!is.na(ex) & ex != ""]
      if (length(ex) == 0L) {
        message(sprintf("  Cluster %d -> '%s' (no labelled neurons — using cluster number)",
                        cl, as.character(cl)))
        next
      }
      tab <- sort(table(ex), decreasing = TRUE)
      lbl <- names(tab)[1]
      result$cns_network[mask] <- lbl
      message(sprintf("  Cluster %d -> '%s' (%d/%d neurons, %.1f%% of labelled)",
                      cl, lbl, tab[1], sum(mask),
                      100 * tab[1] / length(ex)))
    }
  }

  result <- result %>% dplyr::select(-existing_cns)

  output_df <- result %>%
    dplyr::select(root_id, supervoxel_id, position,
                  spectral_cluster, umap_x, umap_y, cns_network)
  if (nrow(output_df) != length(neuron_ids) ||
      !identical(output_df$root_id, neuron_ids) || anyDuplicated(output_df$root_id))
    stop("Complete ordered community output required")
  if (!is.numeric(output_df$spectral_cluster) || anyNA(output_df$spectral_cluster) ||
      any(!output_df$spectral_cluster %in% seq_len(13L)) ||
      !is.numeric(output_df$umap_x) || !is.numeric(output_df$umap_y) ||
      any(!is.finite(output_df$umap_x)) || any(!is.finite(output_df$umap_y)) ||
      !is.character(output_df$cns_network) || anyNA(output_df$cns_network) ||
      any(output_df$cns_network == "")) stop("Complete finite native community fields required")
  list(branch = "R", method_id = "source_reference", result = output_df,
       neuron_ids = neuron_ids, label_snapshot = st,
       declared_input_binding = binding, label_origin = label_origin,
       prior_label_sha256 = prior_label_sha256,
       numerical_runtime_declaration = observed,
       affinity_numeric_representation = "native Matrix operations; no Python dtype conversion",
       historical_producer_identified = FALSE, scientific_qualification = FALSE)
}
