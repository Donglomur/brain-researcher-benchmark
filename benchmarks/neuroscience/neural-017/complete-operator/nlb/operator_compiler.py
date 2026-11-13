"""Concrete, deterministic full-scope MC_Maze campaign recipes.

Only deployment operands and actual pre-data authoring records are supplied by
the operator. The operator does not supply scientific actions, case rosters,
tool callbacks, fabricated predictions or qualification verdicts.
"""
from .operator_roster import JobRoster, slots, job_roster, path_selection
from .contracts import Budget, canonical, closed, descriptor, digest, integer, need, relative
from .programme import (CONDITIONS, REFERENCES, P4H, allowed_references, bank_id,
                        expected_groups, expected_jobs, group_id, execution_plan_identity,
                        programme)

SLOT_KEYS = {'authoring_token_caps', 'investigation_exchanges',
             'investigation_tool_slots', 'f_reference_calls'}
SOURCE_KEYS = {'source', 'design', 'roster', 'contrasts', 'planned_support',
               'shuffle_commitment', 'split', 'rubric', 'qualification_schedule',
               'exposure', 'raw_asset', 'organizer_source', 'protected_shuffle_seed',
               'dependencies'}
GROUPS = expected_groups()


def wire_size(value, cap):
    """Exact canonical JSON extent, including LF, before allocating a full wire body."""
    from .operator_wire import extent
    return extent(value,cap)


def ref(name):
    return {'artifact': name}


def sha(name):
    return {'artifact_sha256': name}








def authoring_selection(recipe, code_views):
    """All fifty F procedures, before any empirical stage; no supplied records."""
    closed(recipe, {'root_source', 'driver_source', 'model', 'clock_domain', 'clock_review',
                    'context_roots', 'context_programme', 'syntax_policy', 'group_limits',
                    'slots', 'output_prefix'})
    slots(recipe['slots']); closed(code_views, {'A', 'B'})
    closed(recipe['group_limits'], Budget.KEYS)
    need(recipe['group_limits']['cpu_seconds'] == P4H['cpu_seconds'] and
         recipe['group_limits']['model_tokens'] == P4H['model_tokens'], 'full matched P4H budget')
    relative(recipe['output_prefix'])
    out = {k: recipe[k] for k in ('root_source', 'driver_source', 'model', 'clock_domain',
        'clock_review', 'context_roots', 'context_programme', 'syntax_policy')}
    out.update(schema='NLB017_F_authoring_production_selection_v1', code_views=code_views,
               outer_output_prefix=recipe['output_prefix'], groups={})
    for g in GROUPS:
        if g['mode'] != 'F':
            continue
        gid = group_id(g)
        out['groups'][gid] = dict(seed=g['agent_seed'], code_view=g['code_view'],
            public_context=code_views[g['code_view']], limits=recipe['group_limits'],
            wall_seconds=P4H['wall_seconds'],
            exchange_slots=[gid + '/author-model-%04d' % n for n in range(len(recipe['slots']['authoring_token_caps']))],
            checker_slots=[gid + '/author-check-%04d' % n for n in range(len(recipe['slots']['authoring_token_caps']))],
            exchange_token_caps=recipe['slots']['authoring_token_caps'],
            output_prefix=recipe['output_prefix'] + '/' + digest(gid.encode()))
    return out


def _action(job, stage, role, body, outputs, *, collection=None, condition=None, group=None):
    row = dict(job=job, role=role, body=body,
               outputs={k: {'name': n, 'role': r} for k, (n, r) in outputs.items()})
    if collection is not None:
        row['collection_product'] = collection
    if condition is not None:
        row['condition'] = condition
    if group is not None:
        row['group'] = group
    return stage, row


def _pair(prefix):
    return {'metadata': ref(prefix + '/metadata'), 'arrays': ref(prefix + '/arrays')}


def _config(recipe, training, query=None):
    value = {'bindings': {'programme': '@programme',
                         'source': recipe['reference_source']['sha256'],
                         'dependencies': recipe['inputs']['dependencies']['sha256'],
                         'training': sha(training)},
             'limits': recipe['scientific_limits'],
             'gpfa_qualification': {'schema': 'NLB017_GPFA_runtime_qualification_v2',
                'source_contract_sha256': 'bbf72d8d2a62a94efa9fc340a307a5ac05022826e4eb42b93469ae701e6e331d',
                'qualification_binding': recipe['inputs']['dependencies']['sha256']}}
    if query is not None:
        value['bindings']['query'] = sha(query)
    return value


def _training(rid, condition=None):
    c = 'training_rate_only' if condition == 'training_rate_only' else ('context_only' if rid in ('R0', 'R1', 'R2') else 'intact')
    return 'prepared/' + c + '/training'


def scientific_actions(recipe):
    """Actual original numerical producer inputs, full support, no proxy leaves."""
    stages = {'S%02d' % i: {'jobs': [], 'evidence': {}} for i in range(1, 17)}
    def add(*a, **k):
        stage, action = _action(*a, **k); stages[stage]['jobs'].append(action)
    add('prepare/raw', 'S02', 'raw_prepare',
        {k: ref('input/' + n) for k, n in [('raw', 'raw_asset'), ('planned_support', 'planned_support'),
            ('organizer_source', 'organizer_source'), ('source_manifest', 'source')]},
        {'public': ('prepared/public', 'public_training'), 'target': ('assessment/target', 'assessment_target'),
         'conversion': ('prepared/conversion', 'metadata')})
    projections = {c + '_' + kind: ('prepared/' + c + '/' + kind, 'public_' + kind)
                   for c in CONDITIONS for kind in ('training', 'query')}
    projections.update(support=('prepared/support', 'metadata'), protected_map=('prepared/private_map', 'protected_seed'))
    add('prepare/views', 'S03', 'project_views',
        {'public': ref('prepared/public'), 'planned_support': ref('input/planned_support'),
         'shuffle_commitment': ref('input/shuffle_commitment'), 'protected_shuffle_seed': ref('input/protected_shuffle_seed')}, projections)
    for rid in REFERENCES:
        train = _training(rid)
        body = dict(reference=rid, training=ref(train), split=ref('input/split'), config=_config(recipe, train))
        outputs = {'state_metadata': ('train/' + rid + '/metadata', 'source_state'),
                   'state_arrays': ('train/' + rid + '/arrays', 'source_state')}
        if rid == 'R0':
            body['rate_training'] = ref('prepared/training_rate_only/training')
            outputs.update(rate_state_metadata=('train/R0-rate/metadata', 'source_state'),
                           rate_state_arrays=('train/R0-rate/arrays', 'source_state'))
        add('train/' + rid, 'S05', 'reference_train', body, outputs, collection='state_metadata')
    for rid, label in [('R0', 'R0-R1'), ('R3', 'R3')]:
        prefix = 'development/' + label
        add(prefix, 'S05', 'reference_development',
            dict(reference=rid, training=ref(_training(rid)), split=ref('input/split'), config=_config(recipe, _training(rid))),
            {'development_metadata': (prefix + '/metadata', 'development'),
             'development_arrays': (prefix + '/arrays', 'development')}, collection='development_metadata')
    for condition in CONDITIONS:
        for rid in allowed_references(condition):
            name = bank_id(condition, rid); train = _training(rid, condition)
            query = 'prepared/' + condition + '/query'
            state = 'train/R0-rate' if condition == 'training_rate_only' else 'train/' + rid
            add(name, 'S06', 'reference_predict',
                dict(reference=rid, training=ref(train), query=ref(query), support=ref('prepared/support'),
                     state=_pair(state), config=_config(recipe, train, query)),
                {'state_metadata': (name + '/metadata', 'source_state'), 'state_arrays': (name + '/arrays', 'source_state'),
                 'prediction': (name + '/prediction', 'prediction')}, collection='prediction', condition=condition)
    for case_route, name in [(False, 'TOOL_ONLY_BATCH'), (True, 'TOOL_ONLY_CASE')]:
        add(name, 'S06', 'tool_only', dict(reference='R1', training=ref(_training('R1')),
            query=ref('prepared/intact/query'), support=ref('prepared/support'),
            state=_pair(bank_id('intact', 'R1')), config=_config(recipe, _training('R1'), 'prepared/intact/query'),
            case_route=case_route), {'prediction': (name + '/prediction', 'prediction')},
            collection='prediction', condition='intact')
    for g in GROUPS:
        if g['mode'] != 'F':
            continue
        gid = group_id(g); c = g['condition']
        request = dict(schema='NLB017_arbitrary_method_inputs_v1', training=ref('prepared/' + c + '/training'),
            query=ref('prepared/' + c + '/query'), state=None, case_index=None,
            context=dict(programme='@programme', group=gid, condition=c, code_view=g['code_view'], mode='F'),
            output_contract='six_array_expected_spikes_per_bin')
        add(gid + '/programme', 'S07', 'participant_F',
            {'submitted_source': ref('author/' + gid), 'input_request_template': request},
            {'prediction': (gid + '/prediction', 'prediction')}, collection='prediction', condition=c, group=gid)
    add('assessment/grade', 'S13', 'protected_score',
        {'collection': ref('collection'), 'target': ref('assessment/target'), 'contrasts': ref('input/contrasts')},
        {'grade': ('grade', 'metadata'), 'private_ledger': ('private_ledger', 'private_ledger')})
    add('assessment/uncertainty', 'S14', 'protected_uncertainty',
        {'grade': ref('grade'), 'private_ledger': ref('private_ledger'), 'contrasts': ref('input/contrasts'),
         'support': ref('prepared/support')},
        {'uncertainty': ('uncertainty', 'metadata'), 'private_draws': ('private_draws', 'private_draws')})
    add('report/aggregate', 'S15', 'aggregate_report',
        {'grade': ref('grade'), 'uncertainty': ref('uncertainty'), 'costs': ref('actual_costs'),
         'exposure': ref('input/exposure'), 'disposition': 'complete_global_release'},
        {'aggregate': ('aggregate', 'aggregate')})
    evidence = {
        'S01': {'E04': ['input/source', 'f_authoring']},
        'S04': {'E06': ['input/planned_support', 'input/shuffle_commitment', 'f_authoring']},
        'S02': {}, 'S03': {'E05': ['prepared/support'] + ['prepared/' + c + '/' + k for c in CONDITIONS for k in ('training', 'query')]},
        'S05': {'E08': ['train/' + r + '/metadata' for r in REFERENCES]},
        'S06': {'E11': [bank_id(c, r) + '/metadata' for c in CONDITIONS for r in allowed_references(c)]},
        'S07': {}, 'S08': {}, 'S09': {}, 'S10': {'E12': ['f_authoring']},
        'S11': {'E13': ['collection']}, 'S12': {'E14': ['release']},
        'S13': {'E15': ['grade', 'private_ledger']}, 'S14': {'E16': ['uncertainty', 'private_draws']},
        'S15': {'E17': ['report/text', 'report/judgment']}, 'S16': {'E18': ['report/judgment']}}
    for stage, products in evidence.items():
        stages[stage]['evidence'] = {k: {'artifacts': v} for k, v in products.items()}
    for key in ('E07', 'E09', 'E10'):
        stages['S05']['evidence'][key] = {'qualification': {'report': None}}
    return stages


def _context(recipe, g, messages, public_members, public_roles, case_index):
    gid = group_id(g); c = g['condition']
    states = {}
    for rid in allowed_references(c):
        states[rid] = {'reference': rid, 'source': _pair(bank_id(c, rid)),
            'config': _config(recipe, _training(rid, c), 'prepared/' + c + '/query'),
            'public_metadata': {'reference': rid, 'condition': c, 'source': recipe['reference_source'],
                                'training': sha(_training(rid, c)), 'query': sha('prepared/' + c + '/query')}}
    return {'binding': {'programme': '@programme', 'group': gid, 'condition': c, 'code_view': g['code_view']},
        'references': list(allowed_references(c)), 'states': states,
        'training': ref('prepared/' + c + '/training'), 'query': ref('prepared/' + c + '/query'),
        'support': ref('prepared/support'), 'job_prefix': gid + ('/preparation' if case_index is None else '/case-%04d' % case_index),
        'case_index': case_index, 'mode': 'I', 'agent_seed': g['agent_seed'],
        'stage': 'S08' if case_index is None else 'S09', 'initial_messages': messages,
        'initial_context_sha256': digest(canonical(messages)), 'public_members': public_members,
        'public_member_roles': public_roles, 'produced_predictions': [],
        'shared_preparation_frozen': False, 'prior_case_answers': []}


def compile_campaign(recipe, *, runtime, authored, author_reviews, contexts, design):
    """Build the complete current CLI operands from actual source-owned products.

    Actual body authentication is the driver's Store responsibility; this pure
    compiler closes the schema and checks the full identities/rosters. External
    E01/E02/E03 and late independent review pins are attached only after this
    acyclic identity exists; they do not rewrite the scientific execution plan.
    """
    closed(recipe, {'schema', 'root_source', 'inputs', 'code_views', 'model', 'reference_source',
        'scientific_limits', 'slots', 'group_limits', 'reference_limits', 'reference_original_deadline',
        'original_deadline', 'report_limits', 'report_max_tokens', 'report_seed', 'f_io_reserve',
        'authoring_clock_domain'})
    need(recipe['schema'] == 'NLB017_full_campaign_recipe_v1', 'full compiler recipe')
    closed(recipe['inputs'], SOURCE_KEYS)
    for pin in [*recipe['inputs'].values(), *recipe['model'].values(), *recipe['code_views'].values(), recipe['reference_source']]:
        descriptor(pin)
    need(recipe['inputs']['source']['sha256'] == recipe['root_source'], 'one original root source')
    slots(recipe['slots']); closed(recipe['group_limits'], Budget.KEYS)
    need(recipe['group_limits']['cpu_seconds'] == 14400 and recipe['group_limits']['model_tokens'] == 2097152, 'original full P4H')
    closed(recipe['scientific_limits'], {'max_state_bytes', 'max_state_nodes', 'max_trace_events'})
    for n in recipe['scientific_limits'].values(): integer(n, 1)
    from .factored_runtime import FactoredRuntime
    from .operator_roster import JobRoster
    factored = type(runtime) is FactoredRuntime
    expected = JobRoster.from_selection(recipe['slots'], 'campaign')
    if factored:
        need(runtime.roster.specification() == expected.specification(), 'same complete source-owned factored runtime census')
        native_jobs = runtime
    else:
        need(set(runtime['native_jobs']) == set(expected) and
             set(runtime['worker_context']) == set(runtime['native_jobs']), 'source-built full expanded runtime union')
        native_jobs = runtime['native_jobs']
    fids = {group_id(g) for g in GROUPS if g['mode'] == 'F'}
    need(authored['schema'] == 'NLB017_original_F_authoring_pending_v1' and
         authored['status'] == 'pending_independent_reviews' and authored['complete_scope'] is True and
         set(authored['groups']) == set(author_reviews) == fids, 'all fifty actual pre-data authors and selected review pins')
    stages = scientific_actions(recipe); groups = {}; initial = []
    roles = {'raw_asset': 'raw_asset', 'protected_shuffle_seed': 'protected_shuffle_seed',
             'planned_support': 'planned_support', 'source': 'source', 'dependencies': 'qualification'}
    for name, pin in recipe['inputs'].items():
        initial.append(dict(name='input/' + name, pin=pin, role=roles.get(name, 'metadata'), producer='selected_operator'))
    for g in GROUPS:
        gid = group_id(g)
        config = {'limits': recipe['group_limits'], 'original_deadline': recipe['original_deadline']}
        if g['mode'] == 'F':
            row = authored['groups'][gid]
            need(row['state'] == 'pending_independent_review' and row['independent_review'] is None,
                 'actual authoring producer did not fabricate review')
            for key in ('record', 'plan', 'clock_identity', 'captured_source'): descriptor(row[key])
            descriptor(author_reviews[gid])
            config.update(authoring={**{k: row[k] for k in ('record', 'plan', 'clock_identity')},
                                     'review': author_reviews[gid]},
                authoring_original_started=row['original_started'], original_deadline=row['original_deadline'],
                authoring_clock_domain=recipe['authoring_clock_domain'])
            initial.append(dict(name='author/' + gid, pin=row['captured_source'], role='source', producer='original_F_authoring'))
        else:
            context = contexts[gid]
            closed(context, {'preparation_messages', 'case_messages', 'public_members', 'public_member_roles'})
            config.update(model_service=model_service(recipe['model']), source=recipe['model']['runtime'],
                          max_model_exchanges=recipe['slots']['investigation_exchanges'])
            config['preparation_context'] = _context(recipe, g, context['preparation_messages'], context['public_members'], context['public_member_roles'], None)
            # Immutable pre-data templates are shared only during compilation.
            # Campaign.resolve constructs a fresh actual case value before use.
            case_template = _context(recipe, g, context['case_messages'], context['public_members'], context['public_member_roles'], 0)
            config['case_context_template'] = {k:v for k,v in case_template.items() if k not in ('case_index','job_prefix')}
            config['case_count'] = 574
        groups[gid] = config
    for g in GROUPS:
        if g['mode'] != 'F': continue
        gid = group_id(g); peer = gid.replace('/F-', '/I-')
        pc = groups[peer]['preparation_context']; context = {k: pc[k] for k in ('references', 'states', 'query', 'support')}
        context['binding'] = {**pc['binding'], 'group': gid}
        groups[gid]['reference_service'] = dict(context=context,
            slots=[gid + '/reference-service-%06d' % n for n in range(1, recipe['slots']['f_reference_calls'] + 1)],
            io_reserve=recipe['f_io_reserve'])
    members = {}
    for context in contexts.values():
        for name, pin in context['public_members'].items():
            descriptor(pin); kind = context['public_member_roles'][name]
            role = 'curated_code_B' if kind == 'curated_code_B' else 'licensed_primary'
            need(pin['path'] not in members or members[pin['path']][:2] == (pin, role), 'unique original public context identity')
            members[pin['path']] = (pin, role, name)
    initial += [dict(name='context/' + digest(path.encode()), pin=pin, role=role, producer='context_builder')
                for path, (pin, role, _) in sorted(members.items())]
    collected = {group_id(g) for g in GROUPS} | {bank_id(c,r) for c in CONDITIONS for r in allowed_references(c)} | {'TOOL_ONLY_BATCH','TOOL_ONLY_CASE'}
    declared = [ref('collected/' + k) for k in sorted(collected)]
    if factored:
        worker_contexts = {'schema':'NLB017_factored_worker_contexts_v1',
            'native_jobs_sha256':runtime.wire_identity['sha256'], 'assessment_declared_inputs':declared}
    else:
        worker_contexts = dict(runtime['worker_context'])
        worker_contexts['assessment/grade'] = {**worker_contexts['assessment/grade'], 'declared_inputs':declared}
    selection = dict(native_jobs=native_jobs, worker_contexts=worker_contexts,
        participant_groups=groups, initial_artifacts=initial,
        original_deadline=recipe['original_deadline'], reference_limits=recipe['reference_limits'],
        reference_original_deadline=recipe['reference_original_deadline'], stages=stages,
        checkpoint_reviews=[], preconditions={'E01': None, 'E02': None, 'E03': None},
        reporting=dict(model_service=model_service(recipe['model']), job='report/model', seed=recipe['report_seed'],
            max_tokens=recipe['report_max_tokens'], limits=recipe['report_limits'], original_deadline=recipe['original_deadline'],
            aggregate_artifact='aggregate'))
    # The unchanged cli.py reads the campaign at1GiB. Reserve the exact final
    # programme identity field before its acyclic hash is available. No record
    # or case is removed to force a fit; oversized selected slots refuse.
    wire_size({**selection,'programme_sha256':'0'*64},1024*2**20)
    spec = {k: recipe['inputs'][k] for k in ('source','design','roster','contrasts','planned_support','shuffle_commitment',
                                            'split','rubric','qualification_schedule','exposure')}
    spec.update(schema='NLB017_programme_v1', canonical_id='NEURAL-017', groups=sorted(groups),
        code_views=recipe['code_views'], model=recipe['model'],
        tool_policy=['read_public','run_python','reference_predict','inspect_state','commit_prediction'],
        budgets=P4H, reference_budget=dict(cpu_seconds=720000,wall_seconds=259200,cpus=4,memory_bytes=16*2**30,gpu=False),
        created_before_activity=True, execution_plan_sha256=execution_plan_identity(selection))
    selection['programme_sha256'] = programme(spec, design['roster'], design['contrasts'])
    wire_size(spec,16*2**20)
    need(len(expected_jobs(spec)) == 28844 and len(groups) == 100, 'unchanged full scientific role census')
    for stage in stages:
        need(set(stages[stage]['evidence']) == set(design['dag_stages'][stage]['evidence_products']), 'exact original DAG evidence products: ' + stage)
    return {'programme': spec, 'campaign': selection}


def model_service(model):
    return {'identity': model['model_identity'], 'configuration': model['configuration'],
            'prompt': model['prompt'], 'tokenizer': model['tokenizer'],
            'qualification': model['service_qualification']}


def attach_reviews(compiled, preconditions, checkpoint_reviews):
    """Attach genuine later selected pins without changing any frozen plan field."""
    closed(preconditions, {'E01', 'E02', 'E03'})
    for pin in preconditions.values(): descriptor(pin)
    seen = set()
    for row in checkpoint_reviews:
        closed(row, {'checkpoint', 'review'}); descriptor(row['review'])
        need(row['checkpoint'] not in seen, 'unique selected independent checkpoint')
        seen.add(row['checkpoint'])
    campaign = {**compiled['campaign'], 'preconditions': preconditions, 'checkpoint_reviews': checkpoint_reviews}
    need(execution_plan_identity(campaign) == compiled['programme']['execution_plan_sha256'], 'review attachment preserves frozen plan')
    return {'programme': compiled['programme'], 'campaign': campaign}
