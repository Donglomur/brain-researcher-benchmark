"""Isolated choice/context projection over the unchanged093 source geometry.

The trusted caller authenticates all sources and complete39-session eligibility,
performs original object/clock/closed-census parity, and decodes final choices with
the unchanged schema kernel. Dependencies and arrays are injected only inside the
isolated worker. No I/O, NumPy import, fit, candidate invocation or CLI lives here.
"""
PROBABILITY_CLASS_ORDER = ('right', 'NoGo', 'left')
SOURCE_CHOICE_TO_CLASS = ((-1, 0), (0, 1), (1, 2))
CONTEXT_COLUMNS = (
    'stimulus_left', 'stimulus_right', 'stimulus_difference',
    'stimulus_absolute_difference', 'stimulus_sum', 'stimulus_product',
    'u', 'u_squared', 'previous_stimulus_left', 'previous_stimulus_right',
    'first_source_row',
)
CONTEXT_FIELDS = CONTEXT_COLUMNS


class ChoiceProjectionUnsupported(Exception):
    """Refuse the complete session; no reduced or repaired support is returned."""


def need(condition, label):
    if not bool(condition):
        raise ChoiceProjectionUnsupported(label)


def validate_context(context, *, np):
    """Validate the public scalar-column contract without inspecting any targets.

    Values alone cannot prove an omitted source predecessor's identity. That
    join is performed by stimulus_history before phase export. Zero previous
    contrasts are valid stimuli and do not imply missing history.
    """
    need(type(context) is dict and set(context) == set(CONTEXT_COLUMNS),
         'exact_permitted_context_columns')
    values = tuple(context[name] for name in CONTEXT_COLUMNS)
    need(all(isinstance(value, np.ndarray) and value.ndim == 1
             and value.dtype == np.dtype('float64') for value in values),
         'context_float64_one_dimensional_columns')
    n = len(values[0])
    need(all(value.shape == (n,) and np.isfinite(value).all() for value in values),
         'context_common_shape_finite')
    for name in ('stimulus_left', 'stimulus_right', 'previous_stimulus_left',
                 'previous_stimulus_right', 'u'):
        need((context[name] >= 0).all() and (context[name] <= 1).all(),
             'context_finite_0_1:' + name)
    left, right = context['stimulus_left'], context['stimulus_right']
    difference = left - right
    need(np.array_equal(context['stimulus_difference'], difference)
         and np.array_equal(context['stimulus_absolute_difference'], np.abs(difference))
         and np.array_equal(context['stimulus_sum'], left + right)
         and np.array_equal(context['stimulus_product'], left * right),
         'context_exact_stimulus_algebra')
    u = context['u']
    need(np.array_equal(context['u_squared'], np.square(u))
         and (u[1:] > u[:-1]).all(), 'context_original_order_u_and_u_squared')
    first = context['first_source_row']
    need(np.isin(first, [0., 1.]).all()
         and np.array_equal(first == 1., u == 0.),
         'context_first_original_row_flag_not_phase_reset')
    need((context['previous_stimulus_left'][first == 1.] == 0.).all()
         and (context['previous_stimulus_right'][first == 1.] == 0.).all(),
         'context_first_original_row_zero_history_sentinel')
    return n


def source_rows(geometry, *, np):
    """Only original-source geometry; never inspect choices or labels."""
    n = geometry['original_n']
    rows, eligible = geometry['row_ids'], geometry['eligible']
    need(type(n) is int and n > 0, 'positive_original_source_row_count')
    need(isinstance(rows, np.ndarray) and rows.ndim == 1
         and rows.dtype == np.dtype('int64')
         and isinstance(eligible, np.ndarray) and eligible.shape == (n,)
         and eligible.dtype == np.dtype('bool'), 'exact_original_row_geometry')
    need(np.array_equal(rows, np.flatnonzero(eligible)),
         'complete_original_eligible_rows_in_source_order')
    return rows


def stimulus_history(data, geometry, *, np, census):
    """Validate every required original predecessor before any phase can export.

    An ineligible predecessor is still the previous presented stimulus. Invalid
    predecessor values fail the whole projection; they are never a second mask.
    Only original row0 has no predecessor and receives the explicit zero sentinel.
    """
    rows = source_rows(geometry, np=np)
    n = geometry['original_n']
    left = census.vector(data['trials.visualStim_contrastLeft.npy'])
    right = census.vector(data['trials.visualStim_contrastRight.npy'])
    need(isinstance(left, np.ndarray) and isinstance(right, np.ndarray)
         and left.shape == right.shape == (n,)
         and left.dtype.kind in 'fiu' and right.dtype.kind in 'fiu',
         'complete_original_stimulus_vectors')
    prior_rows = rows[rows > 0] - 1
    for name, values in (('left', left), ('right', right)):
        for indices, role in ((rows, 'current'), (prior_rows, 'previous_source_row')):
            selected = values[indices]
            need(np.isfinite(selected).all() and (selected >= 0).all()
                 and (selected <= 1).all(), 'finite_0_1_' + name + '_' + role)
    current_left = left[rows].astype(np.float64, copy=True)
    current_right = right[rows].astype(np.float64, copy=True)
    previous_left = np.zeros(len(rows), dtype=np.float64)
    previous_right = np.zeros(len(rows), dtype=np.float64)
    has_previous = rows > 0
    previous_left[has_previous] = left[prior_rows]
    previous_right[has_previous] = right[prior_rows]
    return current_left, current_right, previous_left, previous_right


def choice_geometry(data, encoded_choices, source_row, *, ordinal, session, mouse,
                    np, census, old_projection):
    """Replace only private labels after the complete unchanged geometry gate.

    encoded_choices is exactly the unchanged schema_kernel.decode_labels return:
    int8 right/NoGo/left =0/1/2 in original ALF row order. It is not raw-1/0/+1
    and must not be mapped again. source_row is the exact held SCHEMA_PLAN row.
    Returned geometry, including its labels, is private trusted-worker state.
    """
    old = old_projection.geometry(census, data, np, old_projection.LIMITS)
    rows = source_rows(old, np=np)
    n = old['original_n']
    need(type(ordinal) is int and 1 <= ordinal <= 39
         and type(source_row['original_ordinal']) is int
         and source_row['original_ordinal'] == ordinal
         and source_row['session'] == session and source_row['mouse'] == mouse
         and type(session) is str and bool(session)
         and type(mouse) is str and bool(mouse), 'exact_original_session_ordinal_mouse')
    need(type(source_row['expected_source_trial_rows']) is int
         and source_row['expected_source_trial_rows'] == n,
         'choice_source_full_original_row_count')
    for phase, (lo, hi) in census.partitions(n).items():
        declared = source_row['source_partitions'][phase]
        need(all(type(declared[k]) is int for k in (
            'original_source_row_start', 'original_source_row_stop_exclusive', 'source_rows'))
             and (declared['original_source_row_start'],
                  declared['original_source_row_stop_exclusive'], declared['source_rows'])
             == (lo, hi, hi - lo), 'original_split_boundaries_before_eligibility:' + phase)
    # Validate history for the entire eligible population, including both phases,
    # before labels are substituted or any phase context may be returned.
    stimulus_history(data, old, np=np, census=census)
    need(isinstance(encoded_choices, np.ndarray) and encoded_choices.shape == (n,)
         and encoded_choices.dtype == np.dtype('int8')
         and np.isin(encoded_choices, [0, 1, 2]).all(),
         'complete_original_encoded_choices_from_exact_private_decoder')
    joined = dict(old)
    joined['labels'] = encoded_choices[rows].astype(np.int8, copy=True)
    need(joined['labels'].shape == rows.shape, 'one_choice_per_unchanged_eligible_source_row')
    return joined


def phase_context(phase, data, geometry, native_plan, *, np, census):
    """Return only11 permitted arrays plus private source alignment rows.

    This function never indexes geometry['labels'], choices, responses, reward,
    correctness, engagement, wheel or neural arrays. Existing exporter handles
    its unchanged native wheel/spike windows and fitting-label publication.
    """
    need(phase in ('fitval', 'query'), 'original_native_export_phase')
    rows = source_rows(geometry, np=np)
    n = geometry['original_n']
    partitions = census.partitions(n)
    expected = np.flatnonzero(rows < partitions['query'][0]) if phase == 'fitval' else np.flatnonzero(rows >= partitions['query'][0])
    supplied = native_plan['phase_rows'][phase]
    need(type(supplied) is list and all(type(x) is int for x in supplied)
         and supplied == expected.tolist(), 'full_phase_indices_source_order_no_repair')
    need(native_plan['partitions'] == partitions, 'unchanged_original_phase_boundaries')
    left, right, previous_left, previous_right = stimulus_history(data, geometry, np=np, census=census)
    selected_rows = rows[expected].copy()
    left, right = left[expected], right[expected]
    difference = left - right
    u = selected_rows.astype(np.float64) / max(n - 1, 1)
    context = {
        'stimulus_left': left,
        'stimulus_right': right,
        'stimulus_difference': difference,
        'stimulus_absolute_difference': np.abs(difference),
        'stimulus_sum': left + right,
        'stimulus_product': left * right,
        'u': u,
        'u_squared': np.square(u),
        'previous_stimulus_left': previous_left[expected],
        'previous_stimulus_right': previous_right[expected],
        'first_source_row': (selected_rows == 0).astype(np.float64),
    }
    need(validate_context(context, np=np) == len(selected_rows),
         'exact_finite_complete_permitted_context_only')
    return {'context': context, 'source_rows': selected_rows}
