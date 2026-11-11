"""Finite source-operation registry and policy admission, not a paper40 guess.

An implemented constructor is not its historical invocation. Reconstruction
choices enter only through the host's externally selected definition record.
The original two numerical banks are neither imported nor replaced here.
"""
from .protocol import require, validate_pin, digest, integer, identifier
from .identity import plan_digest, job_digest, profile_digest


SOURCE_OPERATIONS = {
    'native_gui_diagnostic_v4_0_2': {
        'source': 'kilosort/gui/sanity_plots.py',
        'sha256': 'ba42a7a2e75e5e3d3bd4fb6b304dc06d092317adafa1bba050de7e5457516eae',
        'functions': ['PlotWindow', 'plot_drift_amount', 'plot_drift_scatter', 'plot_diagnostics'],
        'inputs': ['gui_operands'],
        'definition': 'literal-GUI-sanity-plots-not-original-paper-window-selection',
    },
    'native_ccg_v4_0_2': {
        'source': 'kilosort/CCG.py',
        'sha256': '3ec752f016d0ca825b9dea7617f5a702effaa8a271f3d18707e844c88dc7d270',
        'functions': ['compute_CCG', 'CCG_metrics', 'check_CCG'],
        'inputs': ['spike_train_1', 'spike_train_2'],
        'definition': 'literal-v4.0.2-floating-not-I',
    },
    'native_split_projection_v4_0_2': {
        'source': 'kilosort/swarmsplitter.py',
        'sha256': '51b8ebbbe14627032defa963b7b3dc807e8bd317b3df463004b32cada59e2118',
        'functions': ['check_split'],
        'inputs': ['features', 'tree', 'cluster_labels', 'cluster_membership'],
        'definition': 'literal-replaced-last-feature-ridge-0.01-399-bin',
    },
    'native_bimodality_v4_0_2': {
        'source': 'kilosort/swarmsplitter.py',
        'sha256': '51b8ebbbe14627032defa963b7b3dc807e8bd317b3df463004b32cada59e2118',
        'functions': ['bimod_score'],
        'inputs': ['projection'],
        'definition': 'literal-400-edges-399-bins-float32-gaussian4',
    },
}

SUMMARY_OPERATIONS = {
    'drift512_processed': {'inputs': ['drift_records'], 'policies': ['percentile_method'],
                           'source': 'Methods Sec37', 'support': 512},
    'waveform_statistics': {'inputs': ['waveforms'],
                            'policies': ['best_channel_ties', 'trough_ties', 'T2P_index',
                                         'missing_decrease', 'distance_geometry'],
                            'source': 'Methods Sec36', 'support': 'all admitted units'},
    'runtime_mean_sem': {'inputs': ['runtime_rows', 'runtime_evidence'], 'policies': ['variance_ddof', 'timing_boundary'],
                         'source': 'Fig4l; six complete simulations', 'support': 6},
    'score_curves': {'inputs': ['case_score_rows'], 'policies': [],
                     'source': 'Methods Sec33; complete per-unit score domain',
                     'support': 'all designated SU; MUA excluded by role, not by position'},
    'ablation_deltas': {'inputs': ['ablation_rows'], 'policies': [],
                        'source': 'Fig5; paired identical simulation support',
                        'support': 'six named ablations, all six simulations'},
}

OPERATIONS = {**SOURCE_OPERATIONS, **SUMMARY_OPERATIONS}

# From the previously authenticated Reporting Summary. Python patch, GUI image
# backend, and unreported libraries still require an exact external image lock.
REPORTED_LIBRARIES = {'numpy':'1.24.4','numba':'0.58.0','torch':'2.1.0',
                      'scipy':'1.10.1','tqdm':'4.66.1'}


def timing_boundary_contract(boundary):
    require(isinstance(boundary,dict) and set(boundary)=={'id','clock','start_event','end_event',
            'included_stages','excluded_stages'},'timing-boundary-schema','explicit scientific timing definition')
    for key in ('id','start_event','end_event'):identifier(boundary[key],key)
    require(boundary['clock']=='monotonic-wall-seconds' and boundary['start_event']!=boundary['end_event'],
            'timing-clock-or-events','no implicit conversion')
    for key in ('included_stages','excluded_stages'):
        require(isinstance(boundary[key],list),'timing-stages',key)
        for stage in boundary[key]:identifier(stage)
        require(len(boundary[key])==len(set(boundary[key])),'duplicate-timing-stage',key)
    require(boundary['included_stages'] and not(set(boundary['included_stages'])&set(boundary['excluded_stages'])),
            'timing-stage-conflict','included versus excluded work')
    return boundary


def request_contract(request, *, allow_invented=False):
    op = request['operation']
    require(op in OPERATIONS, 'unimplemented-concrete-producer', str(op))
    require(request['schema'] == 'kilosort4_scientific_request_v3', 'scientific-request-schema', op)
    context = request['execution_context']
    require(set(context) == {'plan_digest', 'job_digest', 'producer_profile_digest',
                             'job_id', 'cell', 'query_id'}, 'execution-context', op)
    for k in ('plan_digest', 'job_digest', 'producer_profile_digest'):
        require(isinstance(context[k], str) and len(context[k]) == 64
                and all(c in '0123456789abcdef' for c in context[k]), 'execution-identity', k)
    identifier(context['job_id'])
    require(request['support_digest'] == digest(request['support']), 'support-digest', op)
    require(request['numerical_scope'] in {'R_source20', 'R_paper40', 'I_bijective_full'},
            'scope-collapse', op)
    require(set(request['inputs']) == set(OPERATIONS[op]['inputs']), 'operand-support', op)
    for role, row in request['inputs'].items():
        p = row['pin']
        require(p['path'].startswith('/input/') and '..' not in p['path'].split('/'),
                'operand-namespace', role)
        require(row['format'] == 'strict-json', 'operand-format', role)
        integer(p['bytes'], 'operand bytes')
        require(p['bytes'] <= request['limits']['input_bytes'], 'operand-size-cap', role)
    for k in ('input_bytes', 'output_bytes', 'max_points', 'max_work'):
        integer(request['limits'][k], k, 1)
    require(sum(x['pin']['bytes'] for x in request['inputs'].values()) <=
            request['limits']['input_bytes'], 'input-byte-cap', op)
    if op in SOURCE_OPERATIONS:
        spec = SOURCE_OPERATIONS[op]
        matches = [p for p in request['source_pins']
                   if p['path'] == '/opt/author/' + spec['source']]
        require(len(matches) == 1 and matches[0]['sha256'] == spec['sha256'],
                'wrong-native-source', op)
        require(request['definition']['kind'] == 'literal-source'
                and request['definition']['name'] == spec['definition'], 'native-definition', op)
        require(request['numerical_scope'] == 'R_source20', 'native-is-not-paper-or-I', op)
    else:
        definition = request['definition']
        require(set(definition['policies']) == set(SUMMARY_OPERATIONS[op]['policies']),
                'missing-scientific-policy', op)
        require(definition['kind'] in {'source-closed', 'accepted-reconstruction', 'invented-control'},
                'unresolved-scientific-definition', op)
        require(allow_invented or definition['kind'] != 'invented-control',
                'invented-definition-in-native-run', op)
        if SUMMARY_OPERATIONS[op]['policies']:
            require(definition['kind'] != 'source-closed', 'unclosed-historical-policy', op)
        if op=='runtime_mean_sem':timing_boundary_contract(definition['policies']['timing_boundary'])
    return OPERATIONS[op]


def bind_definition(store, authority, manifest, job, profile, request):
    """External admission, not a caller assertion, selects the science policy.

    Even a source-closed operation binds complete original support. Existing
    unresolved definitions cannot be closed by naming a newly written profile.
    """
    request_contract(request)
    expected = {'plan_digest': plan_digest(manifest), 'job_digest': job_digest(job),
                'producer_profile_digest': profile_digest(profile), 'job_id': job['id'],
                'cell': job['cell'], 'query_id': job.get('query_id')}
    require(request['execution_context'] == expected, 'scientific-request-binding', job['id'])
    require(profile['worker_kind'] == 'scientific' and
            request['numerical_scope'] == job['profile'], 'producer-scope-binding', job['id'])
    support = request['support'];op = request['operation']
    if op == 'drift512_processed':
        require(support['recording_ids'] == manifest['source_rosters']['drift_roots'],
                'drift-manifest-roster', job['id'])
    if op in {'runtime_mean_sem', 'ablation_deltas'}:
        require(set(support['case_ids']) == {c['id'] for c in manifest['cases'] if c['kind']=='synthetic'},
                'summary-simulation-support', job['id'])
    if op == 'score_curves':
        cases = {c['id']: c for c in manifest['cases']}
        for case_id, unit_ids in support['case_unit_ids'].items():
            require(case_id in cases and set(unit_ids) == {u['unit_id'] for u in cases[case_id]['unit_roles']
                    if u['role']=='single-unit-target'}, 'curve-SU-role-join', case_id)
    selected = authority.admission['definition_bindings'][job['id']]
    require(selected['request_digest'] == digest(request), 'definition-request-mismatch', job['id'])
    definition_pin = validate_pin(selected['definition_pin'])
    definition = store.json(definition_pin, 1024 * 1024)
    require(definition == request['definition'], 'definition-substitution', job['id'])
    accepted = store.json(validate_pin(selected['acceptance_pin']), 1024 * 1024)
    require(accepted['purpose'] == 'scientific-definition-admission'
            and accepted['canonical_id'] == manifest['canonical_id']
            and accepted['definition_pin'] == definition_pin
            and accepted['operation'] == request['operation']
            and accepted['numerical_scope'] == request['numerical_scope']
            and accepted['original_support_digest'] == digest(job['original_support'])
            and accepted['original_support_digest'] == request['support_digest'],
            'definition-acceptance-mismatch', job['id'])
    require(accepted['unresolved_choices'] == [], 'unresolved-scientific-definition', job['id'])
    for pin in accepted['primary_source_pins']:
        store.read(validate_pin(pin))
    require(accepted['primary_source_pins'], 'definition-without-source', job['id'])
    # Reconstruction is explicitly different from historical reproduction.
    require(accepted['historical_parity_established'] is False,
            'source-admission-cannot-assert-native-parity', job['id'])
    if op == 'runtime_mean_sem':
        from .product_validation import qualify_runtime_evidence
        qualify_runtime_evidence(store, authority, manifest, job, request)
    return {'definition_pin': definition_pin, 'acceptance_pin': selected['acceptance_pin'],
            'historical_parity': False}
