"""Historical per-fit source selection; no fit, simulation or protected grading.

The trusted fixed producer supplies already live JSON operands. Six ordinary
JobContext captures precede lineage augmentation. Their pins are evidence of
the existing write/readback, not a claim of native qualification. No voltage
sample is read, converted, copied or hashed by this module.
"""
import hashlib
import json
import math

SCHEMA = 'jaxley_allen_historical_selector_v1'
KEYS = ('specimen', 'algorithm', 'budget', 'seed', 'particles', 'steps', 'profile')
CONDITIONS = ('A_R', 'B_R', 'A_I', 'B_I')
PRODUCTS = ('full_voltage', 'soft_DTW', 'spike_count', 'spike_times',
            'spike_amplitudes', 'best_final_hof_lineage', 'resource_trajectory')
CAPTURE_ORDER = tuple(x for x in PRODUCTS if x != 'best_final_hof_lineage')
SOURCE_WEIGHTS = (5., 2., 2., 1., 1.)
SOURCE_RECIPE = '5e7a86282adb9d4603b5546ac5d8dad59aec7cc0'


def require(ok, why):
    if not ok:
        raise ValueError(why)


def pin(value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'),
                     ensure_ascii=False, allow_nan=False).encode('utf8')
    return hashlib.sha256(raw).hexdigest()


def sha(value):
    require(type(value) is str and len(value) == 64 and
            all(c in '0123456789abcdef' for c in value), 'exact SHA256')
    return value


def integer(value, label, minimum=0):
    require(type(value) is int and value >= minimum, label)
    return value


def finite(value):
    require(type(value) in (int, float) and math.isfinite(value), 'finite numeric operand')
    return value


def vector(value, n):
    require(type(value) is list and len(value) == n, 'complete vector extent')
    for x in value:
        finite(x)
    return value


def key(row):
    require(type(row) is dict, 'record object')
    return tuple(row[k] for k in KEYS)


def capture_pin(row, artifact):
    require(type(row) is dict and row['artifact_id'] == artifact and
            row['format'] == 'json', 'actual named JSON capture')
    require(type(row['path']) is str and row['path'] and
            integer(row['bytes'], 'captured bytes', 1), 'capture path/extent')
    return {'artifact_id': artifact, 'path': row['path'],
            'bytes': row['bytes'], 'sha256': sha(row['sha256'])}


def context_binding(ctx, source):
    """Metadata from already admitted/read inputs, never another input open."""
    job = ctx.job
    require(ctx.group == 'J11' and job['condition'] in CONDITIONS, 'J11 condition')
    require(type(job['job_id']) is str and job['job_id'], 'original job identity')
    inputs = []
    for logical in ['allen_sources'] + [source[k] for k in ('time', 'stimulus', 'response', 'morphology')]:
        require(type(logical) is str and logical in ctx.inputs, 'declared source input')
        row = ctx.inputs[logical]
        require(row['logical'] == logical and type(row['path']) is str, 'input identity')
        inputs.append({'logical': logical, 'path': row['path'],
                       'bytes': integer(row['bytes'], 'input bytes', 1),
                       'sha256': sha(row['sha256'])})
    require(len({r['logical'] for r in inputs}) == 5, 'distinct complete source operands')
    return {'job_id': job['job_id'], 'condition': job['condition'],
            'source_tree_sha256': sha(job['source_tree_sha256']),
            'source_profile_sha256': sha(job['source_profile_sha256']),
            'producer_source_sha256': sha(job['producer_source_sha256']),
            'config_sha256': pin(ctx.config), 'inputs': inputs}


def clock_pin(clock, projection, profile, long):
    """Clock only, not voltage. Preserve observed floating samples verbatim."""
    duration = (1100. if long else 199.5) if profile == 'source_literal' else (1150. if long else 200.)
    count = int((duration + .05) / .025)
    vector(clock, count)
    require(clock[0] == 0 and all(b > a for a, b in zip(clock, clock[1:])),
            'complete monotonic rebased clock')
    require(projection['cutoff'] == count and projection['junction_mV'] == -14.,
            'literal projection cutoff/junction')
    stride = integer(projection['stride'], 'positive source stride', 1)
    start = integer(projection['start'], 'source start')
    end = integer(projection['end'], 'source end', 1)
    dt = finite(projection['dt_seconds_observed'])
    require(dt > 0 and end - start >= count, 'full original clock support')
    # Native fit assumes .025ms. This is a prospective refusal of incompatible
    # clocks, not a silent resampling or a historical tolerance inference.
    require(math.isclose(stride * dt * 1000, .025, rel_tol=1e-9, abs_tol=1e-10),
            'source sample stride differs from native .025ms clock')
    require(all(math.isclose(x, i * .025, rel_tol=1e-9, abs_tol=1e-7)
                for i, x in enumerate(clock)), 'clock samples differ from native support')
    return pin(clock)


def support(ctx, source, row, lineage):
    """Build the same support identity before emission and during consumption.

    row is the existing full-voltage record. Only its clocks and list lengths
    are touched; candidate parameters are small relative to voltage captures.
    """
    profile = row['profile']
    require(profile in ('source_literal', 'prospective_paper'), 'separate profile')
    require(profile == ctx.config['profile'], 'selected source/paper profile')
    require(key(row) == key(lineage), 'voltage/lineage job join')
    candidates = lineage['candidates']
    require(type(candidates) is list and candidates, 'complete parameter candidates')
    for candidate in candidates:
        vector(candidate, 25)
    n = len(candidates)
    for prefix in ('fit', 'long'):
        clock = row[prefix + '_clock_ms']
        require(type(row[prefix + '_target']) is list and len(row[prefix + '_target']) == len(clock),
                'target/clock support')
        traces = row[prefix + '_voltage']
        require(type(traces) is list and len(traces) == n and
                all(type(t) is list and len(t) == len(clock) for t in traces),
                'full voltage candidate/clock support')
    return {'key': dict(zip(KEYS, key(row))), 'context': context_binding(ctx, source),
            'candidate_count': n, 'candidate_order_sha256': pin(candidates),
            'fit_clock_sha256': clock_pin(row['fit_clock_ms'], lineage['fit_projection'], profile, False),
            'long_clock_sha256': clock_pin(row['long_clock_ms'], lineage['long_projection'], profile, True),
            'fit_projection_sha256': pin(lineage['fit_projection']),
            'long_projection_sha256': pin(lineage['long_projection']),
            'fit_samples': len(row['fit_clock_ms']), 'long_samples': len(row['long_clock_ms'])}


def bind_job(ctx, source, records):
    """Called by the actual Allen producer on all seven just-created records."""
    require(set(records) == set(PRODUCTS), 'all seven per-job products')
    full = records['full_voltage']; lineage = records['best_final_hof_lineage']
    require(all(key(r) == key(full) for r in records.values()), 'per-job product key join')
    join = pin(support(ctx, source, full, lineage))
    for row in records.values():
        require('source_selector_join' not in row, 'once-only source support binding')
        row['source_selector_join'] = join
    return join


def plain_rank(values, eligible):
    import numpy as np
    require(eligible and len(set(eligible)) == len(eligible), 'nonempty unique eligible candidates')
    x = np.asarray([finite(values[i]) for i in eligible], dtype=np.float64)
    order = np.argsort(x)  # Literal source default, deliberately no stable kind.
    ranking = [eligible[int(i)] for i in order]
    low = float(x[int(order[0])])
    ties = [eligible[i] for i, v in enumerate(x) if float(v) == low]
    return ranking, ties


def gd_history(lineage, n, steps):
    optimizer = lineage['optimizer']; candidates = lineage['candidates']
    require(len(candidates) == 2 * n and optimizer['best_indices'] == list(range(n)) and
            optimizer['terminal_indices'] == list(range(n, 2 * n)), 'GD best/terminal identity')
    history = optimizer['history']
    require(type(history) is list and len(history) == steps, 'complete GD history')
    best = [1e10] * n; epochs = [None] * n
    for epoch, row in enumerate(history):
        require(row['epoch'] == epoch, 'ordered original GD history')
        values = vector(row['loss'], n)
        require(type(row['parameters']) is list and len(row['parameters']) == n,
                'GD history parameter roster')
        for i, value in enumerate(values):
            if value < best[i]:
                best[i] = value; epochs[i] = epoch
        require(vector(row['best_loss'], n) == best, 'strict best loss history')
    require(vector(optimizer['best_loss'], n) == best, 'final strict best loss')
    for i, epoch in enumerate(epochs):
        # If no value beats1e10, source retains initial parameters. The history
        # epoch0 contains those same physical parameters, not terminal values.
        expected = vector(history[0 if epoch is None else epoch]['parameters'][i], 25)
        require(candidates[i] == expected, 'best candidate must be strict history state')
    vector(optimizer['terminal_loss'], n)
    return best


def select_job(records, support_value, captures):
    """Pure scalar/history consumer. Caller has already joined actual captures."""
    import numpy as np
    row = records['best_final_hof_lineage']; n = support_value['candidate_count']
    job = support_value['key']; source = job['profile'] == 'source_literal'
    count = records['spike_count']; times = records['spike_times']; amp = records['spike_amplitudes']
    vector(count['candidates'], n); require(type(count['target']) is int and count['target'] >= 0,
                                          'target spike count')
    require(all(type(x) is int and x >= 0 for x in count['candidates']), 'candidate spike counts')
    require(len(times['candidates']) == len(amp['candidates']) == n, 'complete feature roster')
    target = [count['target']] + vector(times['target'], 2) + vector(amp['target'], 2)
    features = [[count['candidates'][i]] + vector(times['candidates'][i], 2) +
                vector(amp['candidates'][i], 2) for i in range(n)]
    errors = [[abs(a - b) for a, b in zip(x, target)] for x in features]
    weights = list(SOURCE_WEIGHTS) if source else [1., 1., 1., 1/3, 1/3]
    generic_weighted = [float(np.dot(np.asarray(x), weights)) for x in errors]
    require(row['posthoc_weights'] == weights and row['posthoc_errors'] == errors and
            row['posthoc_weighted_errors'] == generic_weighted, 'captured five-feature arithmetic')
    require(row['posthoc_best_index'] == int(np.argmin(generic_weighted)), 'retained generic diagnostic')
    columns = np.asarray(errors, dtype=np.float64).T
    # Exact source left-associated vector arithmetic, separate from the old dot.
    weighted = (columns[0] * weights[0] + columns[1] * weights[1] +
                columns[2] * weights[2] + columns[3] * weights[3] +
                columns[4] * weights[4]).tolist()
    losses = records['soft_DTW']; candidate_losses = vector(losses['candidate_losses'], n)
    require(losses['scale'] == .05 and losses['gamma'] == .1, 'short objective constants')
    require(losses['time_penalty'] == ('source_normalized_index' if source else
            support_value['paper_time_penalty']), 'short objective/source profile')
    short_rank = []; short_ties = []; eligible = []
    if source:
        population = job['particles']
        if job['algorithm'] == 'GD':
            best = gd_history(row, population, job['steps'])
            # Re-evaluation can differ in last bits; disagreement is exposed and
            # cannot change the literal history operand used by the selector.
            require(all(math.isclose(candidate_losses[i], best[i], rel_tol=1e-10, abs_tol=1e-10)
                        for i in range(population)), 'short loss/best-state support mismatch')
            eligible = list(range(population))
            if job['budget'] == 'low':
                short_rank, short_ties = plain_rank(best, eligible)
                eligible = short_rank[:1]
        else:
            optimizer = row['optimizer']
            require(n >= population and optimizer['final_indices'] == list(range(population)) and
                    optimizer['hof_indices'] == list(range(population, n)), 'complete GA final/HOF order')
            eligible = list(range(max(0, n - population - 10), n))
            require(optimizer['source_posthoc_indices'] == eligible, 'literal full-HOF tail identity')
        ranking, ties = plain_rank(weighted, eligible)
    else:
        ranking = []; ties = []
    return {'schema': SCHEMA, 'status': 'historical_target_selection' if source else 'not_applicable_paper_profile',
            'support': {k: v for k, v in support_value.items() if k != 'paper_time_penalty'},
            'capture_pins': captures, 'source_recipe_commit': SOURCE_RECIPE,
            'weights': weights, 'target_features': target,
            'eligible_indices': eligible, 'eligible_absolute_errors': [errors[i] for i in eligible],
            'eligible_weighted_errors': [weighted[i] for i in eligible],
            'ranked_global_indices': ranking, 'equal_minimum_global_indices': ties,
            'selected_global_index': ranking[0] if ranking else None,
            'short_ranked_best_indices': short_rank, 'short_equal_minimum_indices': short_ties,
            'numpy_version': np.__version__, 'sort_call': 'np.argsort(float64_values), default kind; no stable tie policy',
            'historical_tie_identity_verified': False,
            'protected_improvement_ready': False,
            'protected_status': 'unresolved_pre_target_policy_and_success_rule' if support_value['context']['condition'].endswith('_I') else 'not_a_protected_improvement_result',
            'figure_aggregation_status': 'revision_aliases_and_imported_threshold_arrays_unjoined',
            'voltage_access': 'existing_capture_identity_and_shape_clock_join_only_no_sample_scan'}


def publish(ctx, products, sources, expected_schedule):
    """Actual Allen caller tail: six full captures, then enriched lineage seventh.

    No partial family is selected. No self-referential final lineage hash or
    future result.json receipt is invented. Existing finish/collector seals it.
    """
    require(set(products) == set(PRODUCTS), 'complete seven products')
    from .technical_support.contracts import ALLEN
    authoritative = []
    for specimen in ALLEN:
        authoritative.extend([{'specimen': specimen, 'algorithm': 'GD', 'budget': 'high', 'seed': 0, 'particles': 1000, 'steps': 50},
                              {'specimen': specimen, 'algorithm': 'GA', 'budget': 'high', 'seed': 0, 'particles': 1000, 'steps': 50},
                              {'specimen': specimen, 'algorithm': 'GD', 'budget': 'low', 'seed': 42, 'particles': 10, 'steps': 10}])
        authoritative.extend({'specimen': specimen, 'algorithm': 'GA', 'budget': 'low', 'seed': seed, 'particles': 10, 'steps': 10} for seed in range(10))
    require(expected_schedule == authoritative, 'literal complete52 source schedule')
    expected = [tuple(j[k] if k != 'profile' else ctx.config['profile'] for k in KEYS)
                for j in expected_schedule]
    require(len(expected) == 52 and len(set(expected)) == 52, 'full52 schedule')
    for name in PRODUCTS:
        require(type(products[name]) is list and [key(r) for r in products[name]] == expected,
                'full52 ordered unique keys for ' + name)
    require(set(sources) == {j['specimen'] for j in expected_schedule}, 'full four-cell sources')
    supports = []
    for i, coordinate in enumerate(expected):
        ctx.checkpoint()
        records = {name: products[name][i] for name in PRODUCTS}
        s = support(ctx, sources[coordinate[0]], records['full_voltage'], records['best_final_hof_lineage'])
        join = pin(s)
        require(all(r.get('source_selector_join') == join for r in records.values()),
                'condition/source/candidate/clock join changed')
        s['paper_time_penalty'] = ctx.config['time_penalty']
        supports.append(s)
    # Existing full-product writes and full readback happen exactly once.
    for name in CAPTURE_ORDER:
        ctx.emit_json(name, products[name])
    captures = [capture_pin(ctx.rows[name], name) for name in CAPTURE_ORDER]
    for i, s in enumerate(supports):
        ctx.checkpoint()
        records = {name: products[name][i] for name in PRODUCTS}
        lineage = records['best_final_hof_lineage']
        require('source_selection' not in lineage, 'once-only selection')
        lineage['source_selection'] = select_job(records, s, captures)
    ctx.emit_json('best_final_hof_lineage', products['best_final_hof_lineage'])
