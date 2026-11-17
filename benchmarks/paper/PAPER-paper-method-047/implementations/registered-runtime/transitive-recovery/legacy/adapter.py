"""Metadata-only pair binding; actual controller execution belongs to observer.py."""
import os
from pathlib import Path
import sys
import common as U


def sources(capture, expected):
    own = U.parse(capture.read(U.HERE / 'SOURCE_MANIFEST.json', 65536, expected))
    U.need(own['schema'] == 'gcamp8_full117_registration_source_v1' and own['task_id'] == U.TASK,
           'exact registration source')
    names = {'common.py', 'adapter.py', 'observer.py', 'BINDINGS.json', 'README.md'}
    U.need(set(own['files']) == names, 'complete wrapper source closure')
    bodies = {n: capture.read(U.HERE / n, 1000000, p) for n, p in own['files'].items()}
    binding = U.parse(bodies['BINDINGS.json'])
    row = binding['controller_source']
    controller = U.parse(capture.read(U.relative(row['path']), 65536, U.only(row)))
    U.need(controller['task_id'] == U.TASK and controller['source_only'] is True and
           controller['neurons'] == 117 and controller['cases'] == 468 and controller['tracks'] == 2 and
           controller['arms'] == ['A', 'B'], 'full released117 controller source')
    U.need(set(controller['runtime_files']) == set(binding['controller_members']), 'exact controller members')
    captured = {}
    for name, row in binding['controller_members'].items():
        U.need(controller['runtime_files'][name] == U.only(row), 'controller member pin')
        captured[name] = capture.read(U.relative(row['path']), 1000000, U.only(row))
    dep = U.parse(captured['BINDINGS.json'])
    for name, row in binding['dependencies'].items():
        U.need(dep[name] == row, 'unchanged controller dependency binding')
        capture.read(U.relative(row['path']), 1000000, U.only(row))
    for name, row in binding['scientific_sources'].items():
        if name != 'private/stage_view.py':
            U.need(dep['scientific_sources'][name] == U.only(row), 'unchanged scientific source')
        capture.read(U.relative(row['path']), 1000000, U.only(row))
    control = U.module(captured['control.py'], U.relative(binding['controller_members']['control.py']['path']),
                       '_gcamp_full117_registration_control')
    row = binding['dependencies']['stager_process']
    process = U.module(capture.read(U.relative(row['path']), 65536, U.only(row)), U.relative(row['path']),
                       '_gcamp_full117_owned_child')
    return binding, control, process


def bind(args, capture, expected, binding, control):
    U.need(type(args.other_reserve_bytes) is int and args.other_reserve_bytes >= 0, 'explicit current OTHER')
    review_path = U.literal(args.review)
    review_raw = capture.read(review_path, 65536)
    review = U.parse(review_raw)
    U.need(set(review) == {'schema', 'task_id', 'approved', 'adapter_source', 'selection',
           'program_bundle', 'private_grading_authorized', 'template_not_evidence'}, 'exact root review')
    U.need(review['schema'] == 'gcamp8_full117_registration_review_v1' and review['task_id'] == U.TASK and
           review['approved'] is True and review['private_grading_authorized'] is True and
           review['template_not_evidence'] is False and review['adapter_source'] == expected,
           'explicit current root pair and private grading authority')
    selection, selected_operand = capture.document(review['selection'])
    keys = {'schema', 'task_id', 'enabled', 'adapter_source', 'repository', 'export', 'output',
            'controller_selection', 'paired_authoring_attestation', 'other_reserved_bytes',
            'observer_retention_bytes', 'whole_seconds', 'private_grading_authorized', 'template_not_evidence'}
    U.need(set(selection) == keys and selection['schema'] == 'gcamp8_full117_registration_selection_v1' and
           selection['task_id'] == U.TASK and selection['enabled'] is True and
           selection['template_not_evidence'] is False and selection['private_grading_authorized'] is True,
           'selected full pair, never disabled template')
    U.need(selection['adapter_source'] == expected and selection['repository'] == str(U.ROOT) and
           selection['export'] == str(U.relative(binding['export'])) and
           selection['other_reserved_bytes'] == args.other_reserve_bytes and
           selection['observer_retention_bytes'] == U.META, 'same root/export/complete reservation')
    output = U.literal(args.output)
    U.need(str(output) == selection['output'] and not os.path.lexists(output) and output.parent.is_dir(),
           'exact fresh outer output')
    for old in (U.HERE, U.relative(binding['export']), U.relative(binding['controller_source']['path']).parent):
        U.need(not output.is_relative_to(old) and not old.is_relative_to(output), 'disjoint owned output')
    cfg, controller_operand = capture.document(selection['controller_selection'])
    control.validate_selection(cfg)
    U.need(cfg['source'] == U.only(binding['controller_source']) and
           cfg['other_reserved_bytes'] == args.other_reserve_bytes + U.META,
           'controller sees separate observer reserve, unchanged full33GB own envelope')
    whole = control.whole_seconds(cfg)
    U.need(type(selection['whole_seconds']) is int and selection['whole_seconds'] == whole,
           'original complete controller formula is outer whole endpoint')
    bundle_path, bundle_pin = U.selected(review['program_bundle'])
    U.need(bundle_path == U.literal(args.program), 'program operand is root-selected pair descriptor')
    bundle = U.parse(capture.read(bundle_path, 65536, bundle_pin))
    U.need(set(bundle) == {'schema', 'task_id', 'programs'} and
           bundle['schema'] == 'gcamp8_released117_pair_descriptor_v1' and bundle['task_id'] == U.TASK and
           bundle['programs'] == cfg['programs'], 'exact two-program pair, no single-arm default')
    programs = {}
    for arm in ('A', 'B'):
        _, programs[arm] = U.selected(cfg['programs'][arm], 131072)
    author, author_operand = capture.document(cfg['authoring_receipt'])
    runtime, runtime_operand = capture.document(cfg['runtime_receipt'])
    U.need(author['schema'] == 'gcamp8_separate_author_contexts_v1' and author['task_id'] == U.TASK and
           author['template_not_evidence'] is False and author['source'] == cfg['source'] and
           author['programs'] == programs and author['empirical_inputs_released_to_authors'] is False and
           author['cross_context_exchange'] is False and author['prior_exposure_limitations_declared'] is True and
           author['allowed_source_catalog'] == U.only(binding['dependencies']['view_files']) and
           author['candidate_abi'] == U.only(binding['controller_members']['CANDIDATE_ABI.md']) and
           author['candidate_abi_supplied_to_both_contexts'] is True, 'same source-only author custody')
    U.need(cfg['python'] == str(Path(sys.executable).resolve()),
           'child uses the already centrally selected running interpreter')
    U.need(runtime['schema'] == 'gcamp8_future_runtime_custody_v1' and
           runtime['template_not_evidence'] is False and runtime['source'] == cfg['source'] and
           runtime['python'] == cfg['python'] and runtime['docker'] == cfg['docker'] and
           runtime['socket'] == cfg['socket'] and runtime['image'] == cfg['image'] and
           runtime['candidate_memory_bytes'] == cfg['memory_bytes'] and
           runtime['full_selected_reservation_bytes'] >= 33000000000 and
           runtime['other_reserved_bytes'] == cfg['other_reserved_bytes'] and
           runtime['host_source_immutable'] is True and runtime['image_runtime_checked'] is True and
           set(runtime['executable_pins']) == {'python', 'docker'}, 'same non-template runtime custody')
    for value in runtime['executable_pins'].values():
        U.descriptor(value, 268435456)
    att, att_operand = capture.document(selection['paired_authoring_attestation'])
    fields = {'schema', 'task_id', 'qualified', 'template_not_evidence', 'adapter_source', 'controller_source',
              'controller_authoring_receipt', 'program_bundle', 'programs', 'candidate_abi', 'conditions',
              'separately_authored', 'empirical_queries_before_global_commitment', 'arms'}
    U.need(set(att) == fields and att['schema'] == 'gcamp8_root_released117_pair_attestation_v1' and
           att['task_id'] == U.TASK and att['qualified'] is True and att['template_not_evidence'] is False and
           att['adapter_source'] == expected and att['controller_source'] == cfg['source'] and
           att['controller_authoring_receipt'] == cfg['authoring_receipt'] and
           att['program_bundle'] == bundle_pin and att['programs'] == programs and
           att['candidate_abi'] == author['candidate_abi'] and att['conditions'] == binding['conditions'] and
           att['separately_authored'] is True and att['empirical_queries_before_global_commitment'] is False,
           'externally substantiated paired authoring attestation')
    U.need(set(att['arms']) == set(author['contexts']) == {'A', 'B'}, 'both author contexts')
    contexts, provenance = [], []
    for arm in ('A', 'B'):
        row = att['arms'][arm]
        U.need(set(row) == {'context_id', 'information_condition', 'program', 'provenance'}, 'exact arm provenance')
        context = row['context_id']
        U.need(type(context) is str and 1 <= len(context) <= 256 and context == author['contexts'][arm] and
               row['information_condition'] == binding['conditions'][arm] and row['program'] == programs[arm],
               'same distinct declared author identity and source condition')
        _, evidence = U.selected(row['provenance'], 1000000)
        contexts.append(context)
        provenance.append((evidence['bytes'], evidence['sha256']))
    U.need(len(set(contexts)) == len(set(provenance)) == 2, 'two distinct contexts and provenance contents')
    # No program or provenance bodies are opened here. Independent root review
    # substantiates authoring history; these hashes are not signatures.
    operands = [(review_path, U.pin(review_raw)), selected_operand, controller_operand,
                (bundle_path, bundle_pin), author_operand, runtime_operand, att_operand]
    return dict(cfg=cfg, selection=selection, output=output, whole=whole, programs=programs,
                controller_operand=controller_operand, operands=operands, bundle=bundle_pin)


def child_argv(plan, binding):
    path, selected_pin = plan['controller_operand']
    return [str(Path(sys.executable).resolve()), '-I', '-B', str(U.relative(binding['controller_members']['coordinator.py']['path'])),
            '--repo', str(U.ROOT), '--export', plan['selection']['export'], '--selection', str(path),
            '--selection-bytes', str(selected_pin['bytes']), '--selection-sha256', selected_pin['sha256'],
            '--output', str(plan['output'] / 'controller')]


def accept(plan, capture, stdout, observed):
    U.need(observed['natural_exit'] is True and type(observed['exit_code']) is int and observed['exit_code'] == 0 and
           observed['process_reaped'] is True and observed['process_group_absent'] is True and
           observed['streams_closed'] is True and observed['timed_out'] is False and
           observed['kill_sent'] is False and observed['error_type'] is None and
           type(observed['pid']) is int and observed['pid'] > 0 and
           observed['combined_stream_bytes'] == observed['stdout_bytes'] == len(stdout),
           'owned child natural-zero complete closure with no stderr')
    root = plan['output'] / 'controller'
    U.need(not os.path.lexists(root / 'FAILURE.json'), 'no controller failure')
    stdout_pin = U.descriptor(U.parse(stdout), 65536)
    collection = U.parse(capture.read(root / 'COLLECTION.json', 65536, stdout_pin))
    keys = {'schema', 'task_id', 'status', 'cases', 'neurons', 'tracks', 'arms', 'source', 'selection',
            'programs', 'elapsed_before_collection', 'whole_seconds', 'historical105_reproduced',
            'managed_read_reserved_bytes', 'managed_write_reserved_bytes', 'scientific_qualification_added'}
    U.need(set(collection) == keys and collection['schema'] == 'gcamp8_full117_collection_v1' and
           collection['task_id'] == U.TASK and collection['status'] == 'pending_independent_root_outer_exit_admission' and
           collection['cases'] == 468 and collection['neurons'] == 117 and collection['tracks'] == 2 and
           collection['arms'] == ['A', 'B'] and collection['source'] == plan['cfg']['source'] and
           collection['selection'] == plan['controller_operand'][1] and collection['programs'] == plan['programs'] and
           collection['whole_seconds'] == plan['whole'] and collection['historical105_reproduced'] is False and
           collection['scientific_qualification_added'] is False, 'exact source-typed full collection')
    U.need(type(collection['elapsed_before_collection']) in (int, float) and
           0 <= collection['elapsed_before_collection'] < plan['whole'] and
           type(collection['managed_read_reserved_bytes']) is int and
           0 < collection['managed_read_reserved_bytes'] <= 700000000000 and
           type(collection['managed_write_reserved_bytes']) is int and
           0 < collection['managed_write_reserved_bytes'] <= 100000000000, 'complete managed limits')
    commit_raw = capture.read(root / 'COMMITMENT.json', 1000000)
    barrier_raw = capture.read(root / 'PRODUCER_BARRIER.json', 1000000)
    commit, barrier = U.parse(commit_raw), U.parse(barrier_raw)
    U.need(commit['schema'] == 'gcamp8_full117_commitment_v1' and commit['task_id'] == U.TASK and
           commit['source'] == plan['cfg']['source'] and commit['selection'] == plan['controller_operand'][1] and
           commit['programs'] == plan['programs'] and commit['whole_seconds'] == plan['whole'] and
           commit['candidate_image'] == plan['cfg']['image'], 'same global program/source commitment')
    identities = commit['identities']
    U.need(type(identities) is list and len(identities) == 468 and
           all(type(x) is list and len(x) == 3 and all(type(z) is str for z in x) for x in identities),
           'full identities')
    neurons = {x[0] for x in identities}
    U.need(len(neurons) == 117 and len({tuple(x) for x in identities}) == 468 and
           {tuple(x) for x in identities} == {(n, t, a) for n in neurons for t in ('pooled', 'variant') for a in ('A', 'B')},
           'all released117 track/arm combinations')
    U.need(set(barrier) == {'schema', 'count', 'identities', 'all_producers_closed_before_any_grade'} and
           barrier['schema'] == 'gcamp8_full468_barrier_v1' and barrier['count'] == 468 and
           barrier['identities'] == identities and barrier['all_producers_closed_before_any_grade'] is True,
           'complete ordered producer barrier')
    proofs = []
    natural = {'Status': 'exited', 'Running': False, 'Dead': False, 'Pid': 0, 'ExitCode': 0, 'OOMKilled': False}
    for i, identity in enumerate(identities):
        case = root / 'cases' / f'{i:04d}'
        raw = capture.read(case / 'OUTCOME.json', 1000000)
        outcome = U.parse(raw)
        U.need(outcome['schema'] == 'gcamp8_two_phase_closed_case_v1' and outcome['task_id'] == U.TASK and
               outcome['identity'] == identity and outcome['status'] == 'captured' and
               outcome['error_type'] is None and outcome['all_resources_closed'] is True and
               outcome['cli_groups_closed'] is True and outcome['input_retired'] is True and
               outcome['private_grade_started'] is False, 'every complete internal case closure')
        U.need([p['phase'] for p in outcome['phases']] == ['train', 'predict'] and
               all(p['natural_exit'] == natural and type(p['natural_exit']['Pid']) is int and
                   type(p['natural_exit']['ExitCode']) is int and
                   all(p['natural_exit'][k] is False for k in ('Running', 'Dead', 'OOMKilled')) and
                   p['closed']['closed'] is True for p in outcome['phases']) and
               outcome['closures'] and all(x['closed'] is True for x in outcome['closures']),
               'both natural phases and all retained resource closures')
        U.need(outcome['commands'] and all(x['client_reaped'] is True and x['cleanup_complete'] is True and
               x['cleanup_before_original_cutoff'] is True and x['owned_group_absence_observed'] is True
               for x in outcome['commands']), 'every independently owned Docker CLI group closure')
        stage_raw = capture.read(root / 'transient' / f'{i:04d}' / 'STAGE.json', 1000000)
        stage = U.parse(stage_raw)
        U.need(stage['identity'] == identity, 'matching trusted input construction')
        host_exit(stage['process'])
        ack_raw = capture.read(case / 'RETIRE_ACK.json', 65536, U.descriptor(outcome['retirement'], 65536))
        U.need(U.parse(ack_raw)['absence_observed'] is True, 'exact input retirement acknowledgment')
        grade_raw = capture.read(case / 'GRADE_EXIT.json', 65536)
        host_exit(U.parse(grade_raw))
        proofs.append({'identity': identity, 'outcome': U.pin(raw), 'stage': U.pin(stage_raw),
                       'retirement': U.pin(ack_raw), 'grade_exit': U.pin(grade_raw)})
    aggregates = {}
    for arm in ('A', 'B'):
        raw = capture.read(root / ('AGGREGATE_EXIT-' + arm + '.json'), 65536)
        host_exit(U.parse(raw))
        aggregates[arm] = U.pin(raw)
    return {'collection': stdout_pin, 'commitment': U.pin(commit_raw), 'producer_barrier': U.pin(barrier_raw),
            'complete_internal_closure_proofs': proofs, 'aggregate_exit_proofs': aggregates}


def host_exit(value):
    U.need(value['natural_exit'] is True and type(value['exit_code']) is int and value['exit_code'] == 0 and
           type(value['pid']) is int and value['pid'] > 0 and value['process_reaped'] is True and
           value['process_group_absent'] is True and value['streams_closed'] is True and
           value['timed_out'] is False and value['kill_sent'] is False and value['error_type'] is None,
           'trusted independent host child closed naturally')
