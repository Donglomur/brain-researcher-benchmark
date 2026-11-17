"""Released-code Ward/height curves only; no I/O or numerical imports.

The trusted worker supplies NumPy and the held SciPy linkage callable. The
source-deduplicated branch is primary; multiplicity is a fixed diagnostic. This
module implements neither Figure3F nor a root-frontier/paper reconstruction.
"""

LABEL_NAMES = ('Context', 'Direction', 'Position')
BEHAVIOR_FIELDS = ('Context', 'Start', 'Correct', 'Type', 'U', 'A', 'B', 'Other')
MAX_LEAVES = 360
MAX_COLUMNS = 92


class ScientificError(ValueError):
    pass


def _need(condition, message):
    if not condition:
        raise ScientificError(message)


def _labels(np, labels, n):
    _need(isinstance(labels, np.ndarray) and labels.shape == (n, 3) and
          labels.dtype.kind in 'iuf' and bool(np.all(np.isfinite(labels))),
          'Finite numeric Context/Direction/Position labels, one row per leaf')
    _need(bool(np.all((labels[:, :2] == 0) | (labels[:, :2] == 1))) and
          bool(np.all((labels[:, 2] >= 0) & (labels[:, 2] <= 8) &
                      (labels[:, 2] == np.floor(labels[:, 2])))),
          'Binary Context/Direction and exact source position indices0..8')
    return labels.astype(np.int8, copy=True)


def normalize(np, raw):
    """Last retained NONROOT entry; zero/nonfinite denominators stay undefined."""
    _need(isinstance(raw, np.ndarray) and raw.ndim == 2 and raw.shape[0] == 3,
          'Three source-height curves')
    normalized = np.full(raw.shape, np.nan, dtype=np.float64)
    status = []
    for label, name in enumerate(LABEL_NAMES):
        denominator = float(raw[label, -1]) if raw.shape[1] else None
        if denominator is None:
            reason = 'no_nonroot_curve'
        elif not bool(np.isfinite(denominator)):
            reason = 'nonfinite_last_nonroot_denominator'
        elif denominator == 0:
            reason = 'zero_last_nonroot_denominator'
        else:
            _need(denominator > 0, 'A source variance normalizer cannot be negative')
            with np.errstate(invalid='ignore', over='ignore', divide='ignore'):
                values = raw[label] / denominator
            if bool(np.any(np.isinf(values))):
                reason = 'nonfinite_normalized_curve'
            else:
                normalized[label] = values
                reason = None
        status.append({'label': name, 'status': 'defined' if reason is None else 'undefined',
                       'reason': reason,
                       'denominator': denominator if denominator is not None and
                       bool(np.isfinite(denominator)) else None})
    return normalized, status


def curves(np, linkage_matrix, labels):
    """Exact bottom-up source heights, sample variances and nonroot curves.

    Input labels are Context0/1, Direction0/1 and unscaled Position0..8. Internal
    node row i is node n+i; packed descendant bit j denotes input leaf j, little
    bit order. Linkage/leaf order preserve child ordering and all identities.
    """
    _need(isinstance(linkage_matrix, np.ndarray) and linkage_matrix.ndim == 2 and
          linkage_matrix.shape[1] == 4 and linkage_matrix.dtype.kind == 'f', 'Numeric linkage rows')
    n = linkage_matrix.shape[0] + 1
    _need(2 <= n <= MAX_LEAVES, 'Bounded tree with at least two leaves')
    raw_labels = _labels(np, labels, n)
    _need(bool(np.all(np.isfinite(linkage_matrix))) and bool(np.all(linkage_matrix >= 0)),
          'Finite nonnegative linkage fields')
    scaled = raw_labels.astype(np.float64)
    position_max = int(raw_labels[:, 2].max())
    if position_max == 0:
        scaled[:, 2] = np.nan
        position_reason = 'zero_retained_position_maximum'
    else:
        scaled[:, 2] /= position_max
        position_reason = None
    heights = np.zeros(2 * n - 1, dtype=np.int16)
    sizes = np.ones(2 * n - 1, dtype=np.int16)
    descendants = [[i] for i in range(n)]
    consumed = set()
    node_variances = np.full((n - 1, 3), np.nan, dtype=np.float64)
    packed = np.zeros((n - 1, (n + 7) // 8), dtype=np.uint8)
    for i, row in enumerate(linkage_matrix):
        node = n + i
        _need(row[0] == int(row[0]) and row[1] == int(row[1]), 'Exact integer linkage child IDs')
        left, right = int(row[0]), int(row[1])
        _need(0 <= left < node and 0 <= right < node and left != right and
              left not in consumed and right not in consumed,
              'Each child occurs once and precedes its parent')
        consumed.update((left, right))
        children = descendants[left] + descendants[right]
        _need(len(children) == len(set(children)) and row[3] == len(children),
              'Exact linkage support count and disjoint descendant leaves')
        descendants.append(children)
        heights[node] = 1 + max(int(heights[left]), int(heights[right]))
        sizes[node] = len(children)
        # Preserve source child/label order. ddof1 matches pandas Series.var().
        with np.errstate(invalid='ignore', over='ignore'):
            for label in range(3):
                node_variances[i, label] = np.var(scaled[children, label], ddof=1)
        bits = np.zeros(n, dtype=np.uint8)
        bits[children] = 1
        packed[i] = np.packbits(bits, bitorder='little')
    _need(consumed == set(range(2 * n - 2)) and
          sorted(descendants[-1]) == list(range(n)), 'Single complete root covers every leaf exactly once')
    height = int(heights[-1])
    raw_curve = np.zeros((3, height), dtype=np.float64)
    nodes_per_height = np.zeros(height, dtype=np.int16)
    nodes_per_height[0] = n
    for h in range(1, height):
        selected = np.flatnonzero(heights[n:] == h)
        _need(len(selected) > 0, 'Every source height below the root has support')
        nodes_per_height[h] = len(selected)
        for label in range(3):
            raw_curve[label, h] = np.mean(node_variances[selected, label])
    normalized, normalization = normalize(np, raw_curve)
    arrays = {
        'linkage': linkage_matrix.copy(), 'node_height': heights, 'node_size': sizes,
        'internal_node_variance': node_variances, 'internal_descendant_bits': packed,
        'raw_curve': raw_curve, 'normalized_curve': normalized,
        'nodes_per_height': nodes_per_height,
        'leaf_order': np.asarray(descendants[-1], dtype=np.int16),
        'raw_labels': raw_labels,
    }
    report = {
        'tree_status': 'available', 'leaf_count': n, 'internal_nodes': n - 1,
        'root_height': height, 'curve_length': height, 'root_excluded_from_curve': True,
        'label_order': list(LABEL_NAMES), 'position_retained_maximum': position_max,
        'position_scaling_undefined_reason': position_reason, 'normalization': normalization,
        'zero_distance_merges': int(np.count_nonzero(linkage_matrix[:, 2] == 0)),
        'repeated_merge_height_values': int(n - 1 - len(np.unique(linkage_matrix[:, 2]))),
        'descendant_encoding': 'internal row i=node n+i; packed uint8; little bit j=input leaf j',
        'variance_convention': 'internal descendant sample variance ddof1; equal-node means at exact bottom-up height',
        'leaf_curve_convention': 'height0 explicitly zero; leaf sample variances are not computed',
        'missing_encoding': 'undefined normalized values are numeric NaN; JSON nonfinite denominator is null',
        'paper_root_normalization': False, 'figure3f_enabled': False,
    }
    return {'arrays': arrays, 'report': report}


def analyze(np, linkage_callable, pv, labels, row_ids):
    """Fit one bounded raw-Hz tree; labels and row IDs never enter linkage."""
    _need(isinstance(pv, np.ndarray) and pv.ndim == 2 and pv.dtype == np.dtype('float64') and
          pv.shape[0] <= MAX_LEAVES and 1 <= pv.shape[1] <= MAX_COLUMNS,
          'At most360 admitted raw-Hz vectors and all1..92 p1 columns')
    n = len(pv)
    _need(bool(np.all(np.isfinite(pv))), 'Nonfinite admitted PV invalidates the session; no additional exclusion')
    raw_labels = _labels(np, labels, n)
    _need(isinstance(row_ids, np.ndarray) and row_ids.shape == (n, 2) and
          row_ids.dtype.kind in 'iu' and bool(np.all(row_ids >= 0)) and
          bool(np.all(row_ids[:, 0] < 54)) and bool(np.all(row_ids[:, 1] < 9)) and
          len(set(map(tuple, row_ids.tolist()))) == n, 'Unique bounded original trial/bin row identities')
    if n < 2:
        arrays = {'linkage': np.empty((0, 4), dtype=np.float64),
                  'node_height': np.zeros(n, dtype=np.int16), 'node_size': np.ones(n, dtype=np.int16),
                  'internal_node_variance': np.empty((0, 3), dtype=np.float64),
                  'internal_descendant_bits': np.empty((0, (n + 7) // 8), dtype=np.uint8),
                  'raw_curve': np.empty((3, 0), dtype=np.float64),
                  'normalized_curve': np.empty((3, 0), dtype=np.float64),
                  'nodes_per_height': np.empty(0, dtype=np.int16),
                  'leaf_order': np.arange(n, dtype=np.int16), 'raw_labels': raw_labels}
        report = {'tree_status': 'unavailable_insufficient_rows', 'leaf_count': n,
                  'root_height': None, 'curve_length': 0, 'ward_calls': 0,
                  'normalization': normalize(np, arrays['raw_curve'])[1],
                  'figure3f_enabled': False}
    else:
        result = curves(np, linkage_callable(pv, method='ward', metric='euclidean',
                                             optimal_ordering=False), raw_labels)
        arrays, report = result['arrays'], result['report']
        report['ward_calls'] = 1
    arrays['leaf_row_ids'] = row_ids.astype(np.int16, copy=True)
    report.update({'p1_columns': pv.shape[1], 'input_order': 'original trial-major then bin-major',
                   'linkage_method': 'ward', 'linkage_metric': 'euclidean', 'optimal_ordering': False,
                   'unit_scaling_or_selection': False,
                   'tie_policy': 'Actual SciPy runtime output in original input order; no historical paper bit-parity claim'})
    return {'arrays': arrays, 'report': report}


def prepare_support(np, primary_pv, multiplicity_pv, valid_mask, primary_mask,
                    training_row_ids, behavior_rows):
    """Join original labels and preserve every occupancy exclusion without reordering."""
    _need(isinstance(primary_pv, np.ndarray) and primary_pv.dtype == np.dtype('float64') and
          primary_pv.ndim == 3 and primary_pv.shape[0] in (40, 50) and primary_pv.shape[1] == 9 and
          1 <= primary_pv.shape[2] <= MAX_COLUMNS, 'Exact all-training x9 xall-p1 primary PV shape')
    _need(isinstance(multiplicity_pv, np.ndarray) and multiplicity_pv.dtype == np.dtype('float64') and
          multiplicity_pv.shape == primary_pv.shape, 'Same-support multiplicity diagnostic PV shape')
    ntraining, _, columns = primary_pv.shape
    _need(isinstance(valid_mask, np.ndarray) and valid_mask.dtype.kind == 'b' and
          valid_mask.shape == (ntraining, 9), 'Explicit occupancy row mask')
    _need(isinstance(primary_mask, np.ndarray) and primary_mask.dtype.kind == 'b' and
          primary_mask.shape == (ntraining,) and
          np.array_equal(primary_mask, np.arange(ntraining) < 40), 'Fixed first40 primary trial mask')
    _need(isinstance(training_row_ids, np.ndarray) and training_row_ids.dtype.kind in 'iu' and
          training_row_ids.shape == (ntraining,), 'Original training row IDs')
    _need(isinstance(behavior_rows, list) and len(behavior_rows) == ntraining + 4,
          'All training and four probe rows remain in input evidence')
    fields = set(BEHAVIOR_FIELDS) | {'original_row_ordinal'}
    for i, row in enumerate(behavior_rows):
        _need(type(row) is dict and set(row) == fields and type(row['original_row_ordinal']) is int and
              row['original_row_ordinal'] == i and all(type(row[k]) is str for k in BEHAVIOR_FIELDS),
              'Exact original eight-field behavior rows and ordinals')
    types = [r['Type'].strip().casefold() for r in behavior_rows]
    train = [i for i, value in enumerate(types) if value in ('learning', 'visible')]
    probes = [i for i, value in enumerate(types) if value == 'probe']
    _need(len(train) == ntraining and len(probes) == 4 and
          np.array_equal(training_row_ids, np.asarray(train)), 'Exact full original training/probe membership')
    for ordinal in train[:40]:
        _need(behavior_rows[ordinal]['Context'] in ('A', 'B') and
              behavior_rows[ordinal]['Start'] in ('L', 'R'), 'Exact primary Context A/B and Start L/R labels')
    all_ids = np.column_stack((np.repeat(training_row_ids, 9), np.tile(np.arange(9), ntraining)))
    primary_flat = np.repeat(primary_mask, 9)
    admitted = (primary_mask[:, None] & valid_mask).reshape(-1)
    excluded = primary_flat & ~valid_mask.reshape(-1)
    row_ids = all_ids[admitted].astype(np.int16)
    labels = np.empty((len(row_ids), 3), dtype=np.int8)
    for i, (ordinal, position) in enumerate(row_ids):
        row = behavior_rows[int(ordinal)]
        labels[i] = (0 if row['Context'] == 'A' else 1,
                     0 if row['Start'] == 'L' else 1, int(position))
    source = primary_pv.reshape(-1, columns)[admitted]
    multiplicity = multiplicity_pv.reshape(-1, columns)[admitted]
    _need(bool(np.all(np.isfinite(source))) and bool(np.all(np.isfinite(multiplicity))),
          'Nonfinite admitted PV invalidates the session; no additional exclusion')
    arrays = {'leaf_row_ids': row_ids, 'raw_labels': labels,
              'excluded_primary_row_ids': all_ids[excluded].astype(np.int16),
              'training_row_ids': training_row_ids.astype(np.int16, copy=True),
              'training_primary_mask': primary_mask.copy(),
              'extra_training_row_ids': training_row_ids[~primary_mask].astype(np.int16),
              'probe_row_ids': np.asarray(probes, dtype=np.int16),
              'p1_column_indices': np.arange(columns, dtype=np.int16)}
    report = {'primary_training_rows': 40, 'all_training_rows_retained': ntraining,
              'extra_training_rows_not_fitted': ntraining - 40, 'probe_rows_not_fitted': 4,
              'nominal_primary_pv_rows': 360, 'admitted_primary_pv_rows': len(row_ids),
              'excluded_zero_occupancy_rows': int(np.count_nonzero(excluded)),
              'all_p1_columns_preserved': columns,
              'exclusion_rule': 'Only explicit invalid occupancy among fixed first40; no outcome/rate/label selection'}
    return {'source_pv': source, 'multiplicity_pv': multiplicity, 'arrays': arrays, 'report': report}


def analyze_session(np, linkage_callable, primary_pv, multiplicity_pv, valid_mask,
                    primary_mask, training_row_ids, behavior_rows):
    """Two fixed branches; arrays have source_/multiplicity_ prefixes and shared row maps."""
    support = prepare_support(np, primary_pv, multiplicity_pv, valid_mask, primary_mask,
                              training_row_ids, behavior_rows)
    arrays = dict(support['arrays'])
    report = {'schema': 'hierarchy_source_curves_session_v1', 'support': support['report'],
              'source_primary': 'source_frame_deduplicated_raw_Hz',
              'diagnostic': 'multiplicity_preserving_raw_Hz_same_protocol',
              'figure3f_enabled': False, 'root_frontier_reconstruction_enabled': False,
              'learning_contrasts_enabled': False, 'ward_calls': 0}
    for branch in ('source', 'multiplicity'):
        result = analyze(np, linkage_callable, support[branch + '_pv'], arrays['raw_labels'], arrays['leaf_row_ids'])
        report[branch] = result['report']
        report['ward_calls'] += result['report']['ward_calls']
        for name, value in result['arrays'].items():
            if name not in ('raw_labels', 'leaf_row_ids'):
                arrays[branch + '_' + name] = value
    report['tree_pair_status'] = ('available' if report['ward_calls'] == 2 else 'unavailable_insufficient_rows')
    report['arrays_bytes'] = sum(int(a.nbytes) for a in arrays.values())
    return {'arrays': arrays, 'report': report}


def pool(np, normalized_curves):
    """Right-pad all session slots, equal-session sample SEM, then reverse display.

    Accept a list of source_normalized_curve OR multiplicity_normalized_curve
    arrays, never a mixture. All-NaN undefined sessions retain their padded slots.
    These session SEMs are descriptive, not independent-animal inference.
    """
    _need(isinstance(normalized_curves, list) and 1 <= len(normalized_curves) <= 25,
          'Explicit list of retained session slots')
    for values in normalized_curves:
        _need(isinstance(values, np.ndarray) and values.dtype.kind == 'f' and
              values.ndim == 2 and values.shape[0] == 3 and values.shape[1] <= MAX_LEAVES - 1 and
              not bool(np.any(np.isinf(values))), 'Source-normalized curves contain finite values or explicit NaN only')
    width = max(v.shape[1] for v in normalized_curves)
    padded = np.full((len(normalized_curves), 3, width), np.nan, dtype=np.float64)
    for i, values in enumerate(normalized_curves):
        padded[i, :, :values.shape[1]] = values
    mean = np.full((3, width), np.nan, dtype=np.float64)
    sem = np.full((3, width), np.nan, dtype=np.float64)
    counts = np.zeros((3, width), dtype=np.int16)
    for label in range(3):
        for h in range(width):
            values = padded[:, label, h]
            values = values[~np.isnan(values)]
            counts[label, h] = len(values)
            if len(values):
                mean[label, h] = np.mean(values)
            if len(values) > 1:
                sem[label, h] = np.std(values, ddof=1) / np.sqrt(len(values))
    arrays = {'padded_normalized_curves': padded, 'mean_bottom_up': mean, 'sem_bottom_up': sem,
              'contributing_sessions': counts, 'mean_display': mean[:, ::-1].copy(),
              'sem_display': sem[:, ::-1].copy(),
              'contributing_sessions_display': counts[:, ::-1].copy(),
              'bottom_up_height': np.arange(width, dtype=np.int16),
              'display_index': np.arange(width, dtype=np.int16)}
    report = {'schema': 'hierarchy_source_curve_pool_v1', 'session_slots': len(normalized_curves),
              'maximum_source_height': width, 'label_order': list(LABEL_NAMES),
              'status': 'available' if bool(np.any(counts)) else 'undefined_no_contributing_curves',
              'padding': 'Right NaN padding before equal-session mean/SEM; only final pooled arrays reversed',
              'mean_denominator': 'Per-label/per-height contributing_sessions',
              'sem_denominator': 'Sample std ddof1 divided by sqrt(contributing_sessions); n<2 -> NaN',
              'biological_replication': 'Five animals; session SEM is descriptive, not25 independent animals',
              'undefined_session_slots_dropped': False, 'figure3f_enabled': False}
    return {'arrays': arrays, 'report': report}
