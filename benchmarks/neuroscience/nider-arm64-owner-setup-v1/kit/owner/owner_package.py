"""Owner-only session configuration and saved-result presentation.

No subprocess, Docker, network, model, fixture generation or estimator call.
Run the returned existing gateway/observer invocations separately. Never give
this CLI, its requests or its output paths to the candidate.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

LOCK_BYTES = 913
LOCK_SHA256 = '229446a725c2be6b2573a2a010b5bace907abe973ff05609b5aa6c35e4a8b88f'


def need(ok, code):
    if not ok:
        raise ValueError(code)


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'duplicate_json_key')
        result[key] = value
    return result


def decode(raw):
    def invalid_constant(_):
        raise ValueError('nonfinite_json_constant')
    return json.loads(raw, object_pairs_hook=unique_pairs, parse_constant=invalid_constant)


def plain(path):
    p = Path(path)
    need(p.is_absolute() and '..' not in p.parts and
         not any(x.is_symlink() for x in (p, *p.parents)), 'owner_path')
    return p


def read_pin(entry, maximum=1048576):
    need(type(entry) is dict and set(entry) == {'path', 'bytes', 'sha256'}, 'pin_keys')
    p = plain(entry['path'])
    need(type(entry['bytes']) is int and 0 <= entry['bytes'] <= maximum, 'pin_extent')
    with os.fdopen(os.open(p, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             before.st_size == entry['bytes'], 'pin_file')
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    current = p.lstat()
    need(all(getattr(before, key) == getattr(after, key) == getattr(current, key)
             for key in ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')),
         'pin_changed')
    need(len(raw) == entry['bytes'] and hashlib.sha256(raw).hexdigest() == entry['sha256'], 'pin_identity')
    return raw


def observed_pin(path, maximum=1048576):
    """Record an owner-produced artifact; caller fixes its exact sibling path."""
    p = plain(path)
    with os.fdopen(os.open(p, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        info = os.fstat(stream.fileno())
        need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= maximum, 'owner_artifact')
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    current = p.lstat()
    need(len(raw) == info.st_size and all(getattr(info, k) == getattr(after, k) == getattr(current, k)
         for k in ('st_dev','st_ino','st_size','st_mode','st_nlink','st_mtime_ns','st_ctime_ns')), 'owner_artifact_changed')
    entry = {'path': str(p), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    read_pin(entry, maximum)
    return entry


def package_lock():
    return decode(read_pin({'path': str(Path(__file__).with_name('PACKAGE_LOCK.json')),
                            'bytes': LOCK_BYTES, 'sha256': LOCK_SHA256}))


def configuration(anchor):
    fixed = package_lock()
    anchor = plain(anchor)
    bodies = {name: read_pin({'path': str(anchor / name), **identity})
              for name, identity in fixed['configuration_sources'].items()}
    need('configuration' not in sys.modules, 'fresh_owner_process')
    path = anchor / 'configuration.py'
    spec = importlib.util.spec_from_file_location('configuration', path)
    cfg = importlib.util.module_from_spec(spec)
    sys.modules['configuration'] = cfg
    try:
        exec(compile(bodies['configuration.py'], str(path), 'exec'), cfg.__dict__)
    except BaseException:
        del sys.modules['configuration']
        raise
    return cfg, fixed


def source_identity(anchor, fixed):
    return {name: {'path': str(plain(anchor) / name), **identity}
            for name, identity in fixed['configuration_sources'].items()}


def prepare(request, request_pin):
    need(set(request) == {'operation', 'configuration_anchor', 'source_anchor', 'asset_manifest', 'runtime_policy',
                           'arm', 'policy', 'output_root'}, 'prepare_keys')
    cfg, fixed = configuration(request['configuration_anchor'])
    cfg.authoring_policy(request['policy'])
    need(request['arm'] in ('A', 'B'), 'arm')
    root = plain(request['output_root'])
    root.mkdir(mode=0o700)
    modules, _ = cfg.load_runtime(request['source_anchor'])
    c = modules['custody']
    c.write_new(root / 'PREPARATION_REQUEST.json', c.encoded({'request': request_pin, 'operation': 'prepare'}))
    prepared = cfg.prepare_bundle(request['source_anchor'], request['asset_manifest'], root / 'bundle', request['runtime_policy'])
    authoring = cfg.prepare_authoring(prepared, request['arm'], request['policy'],
                                     root / 'authoring_plan', root / 'authoring')
    value = {'schema': 'nider_owner_package_session_v1', 'task': fixed['task'], 'profile': fixed['profile'],
             'package_lock_sha256': LOCK_SHA256, 'configuration_anchor': request['configuration_anchor'],
             'configuration_sources': source_identity(request['configuration_anchor'], fixed),
             'root': str(root), 'arm': request['arm'], 'policy': request['policy'], 'runtime_policy': request['runtime_policy'],
             'prepared': prepared, 'authoring': authoring,
             'scope': fixed['scope'], 'candidate_language': 'R', 'execution_selected': False}
    entry = c.write_new(root / 'OWNER_SESSION.json', c.encoded(value))
    return {'session': entry, 'authoring_argv': authoring['argv'], 'execution_selected': False}


def admit_session(entry):
    session = decode(read_pin(entry))
    need(type(session) is dict and set(session) == {'schema', 'task', 'profile', 'package_lock_sha256',
         'configuration_anchor', 'configuration_sources', 'root', 'arm', 'policy', 'runtime_policy', 'prepared',
         'authoring', 'scope', 'candidate_language', 'execution_selected'}, 'session_keys')
    cfg, fixed = configuration(session['configuration_anchor'])
    need(session['schema'] == 'nider_owner_package_session_v1' and session['task'] == fixed['task'] and
         session['profile'] == fixed['profile'] and session['package_lock_sha256'] == LOCK_SHA256 and
         session['candidate_language'] == 'R' and session['scope'] == fixed['scope'] and
         session['execution_selected'] is False, 'session_identity')
    need(session['configuration_sources'] == source_identity(session['configuration_anchor'], fixed), 'session_sources')
    root = plain(session['root'])
    need(plain(entry['path']) == root / 'OWNER_SESSION.json', 'session_location')
    modules, runtime, prepared = cfg.admit_prepared(session['prepared'])
    c = modules['custody']
    need(session['runtime_policy'] == prepared['runtime_policy'], 'session_runtime_join')
    cfg.authoring_policy(session['policy'])
    need(session['arm'] in ('A', 'B'), 'session_arm')
    authoring = session['authoring']
    need(set(authoring) == {'plan', 'argv', 'execution_selected'} and authoring['execution_selected'] is False,
         'authoring_descriptor')
    need(Path(authoring['plan']['path']) == root / 'authoring_plan/AUTHORING_PLAN.json', 'authoring_plan_location')
    plan = c.decode(c.read_pin(authoring['plan']))
    need(plan == {'schema': 'nider_local_authoring_plan_v1', 'prepared': session['prepared'],
                  'arm': session['arm'], 'policy': session['policy'], 'runtime_policy': session['runtime_policy'], 'owner_root': str(root / 'authoring')},
         'authoring_plan_join')
    need(authoring['argv'] == ['python3', '-B', str(Path(session['configuration_anchor']) / 'authoring_gateway.py'),
                              authoring['plan']['path'], authoring['plan']['sha256']], 'authoring_argv_join')
    return cfg, fixed, session, modules, runtime, prepared


def completion(session, cfg, modules, runtime, prepared):
    c = modules['custody']; root = plain(session['root']) / 'authoring'
    completed_pin = observed_pin(root / 'AUTHORING_RESULT.json')
    completed = c.decode(c.read_pin(completed_pin))
    need(type(completed) is dict and set(completed) == {'schema', 'successful_handoff', 'handoff', 'issuer_key'},
         'completion_shape')
    need(completed['schema'] == 'nider_local_authoring_result_v1' and completed['successful_handoff'] is True,
         'completion_success')
    need(Path(completed['handoff']['path']) == root / 'HANDOFF.json' and
         Path(completed['issuer_key']['path']) == root / 'ISSUER_KEY.bin', 'issuer_owned_siblings')
    hand = cfg.admit_handoff(completed['handoff'], completed['issuer_key'], session['prepared'],
                             prepared, modules, runtime, completed_pin)
    need(hand['arm'] == session['arm'] and hand['policy'] == session['policy'] and hand['runtime_policy'] == session['runtime_policy'], 'handoff_session_join')
    return completed_pin, completed, hand


def prepare_assessment(request):
    need(set(request) == {'operation', 'session'}, 'assessment_keys')
    cfg, fixed, session, modules, runtime, prepared = admit_session(request['session'])
    c = modules['custody']; root = plain(session['root'])
    completed_pin, completed, hand = completion(session, cfg, modules, runtime, prepared)
    invocation = cfg.prepare_assessment(session['prepared'], completed['handoff'], completed['issuer_key'],
                                        completed_pin, root / 'assessment', session['arm'])
    value = c.decode(c.read_pin(invocation))
    ready = c.write_new(root / 'ASSESSMENT_READY.json', c.encoded({
        'schema': 'nider_owner_package_assessment_v1', 'session': request['session'],
        'invocation': invocation, 'program': hand['program'], 'deviations': hand['deviations'],
        'execution_selected': False}))
    return {'assessment': ready, 'assessment_argv': value['argv'], 'execution_selected': False}


def admitted_assessment_graph(ready, session, cfg, modules, runtime, prepared):
    """Check existing producer metadata exactly; no second producer/scorer."""
    c = modules['custody']; root = plain(session['root'])
    completed_pin, completed, hand = completion(session, cfg, modules, runtime, prepared)
    need(ready['program'] == hand['program'] and ready['deviations'] == hand['deviations'], 'assessment_frozen_submission')
    need(Path(ready['invocation']['path']) == root / 'assessment/INVOCATION.json', 'assessment_invocation_location')
    invocation = c.decode(c.read_pin(ready['invocation']))
    need(Path(invocation['owner_plan']['path']) == root / 'assessment/OWNER_PLAN.json' and
         Path(invocation['outer_plan']['path']) == root / 'assessment/OUTER_PLAN.json', 'assessment_plan_locations')
    neutral = cfg.neutral_finalization_pin(completed['handoff'])
    expected_invocation = {'schema': 'nider_prepared_assessment_invocation_v1', 'handoff': completed['handoff'],
        'authoring_completion': completed_pin, 'neutral_finalization': neutral,
        'provenance_sidecar': hand['deviations'], 'owner_plan': invocation['owner_plan'],
        'outer_plan': invocation['outer_plan'], 'observer': prepared['observer'],
        'argv': ['python3', prepared['observer']['path'], invocation['outer_plan']['path'], invocation['outer_plan']['sha256']],
        'execution_selected': False}
    need(invocation == expected_invocation, 'complete_invocation_provenance')
    owner_plan = c.decode(c.read_pin(invocation['owner_plan']))
    expected_owner = {'schema': 'nider_protected_runner_plan_v1',
        'selection_id': 'NIDER-LOCAL-HANDOFF-' + completed['handoff']['sha256'][:24],
        'owner_root': str(root / 'assessment/owner'), 'catalogue': prepared['catalogue'],
        'materials': prepared['materials'], 'program': hand['program'], 'arm': session['arm'], 'sources': prepared['sources'], 'runtime_policy': prepared['runtime_policy']}
    need(owner_plan == expected_owner, 'complete_owner_plan_join')
    pins = [invocation['owner_plan'], session['prepared'], completed['handoff'], completed_pin, neutral,
            hand['deviations'], hand['lifecycle'], prepared['observer'], prepared['catalogue'], prepared['materials'],
            hand['program'], *prepared['sources'].values(), *prepared['assets'].values(), prepared['asset_manifest'], *cfg.runtime_pins(prepared)]
    need(len({item['path'] for item in pins}) == len(pins), 'complete_outer_unique_pins')
    outer_plan = c.decode(c.read_pin(invocation['outer_plan']))
    expected_outer = {'schema': 'nider_protected_outer_plan_v1', 'owner_root': str(root / 'assessment'),
        'wall_seconds': 240, 'maximum_attempts': 1, 'whole_private_limit_bytes': 16777216,
        'argv': ['python3', '-B', str(Path(prepared['source_anchor']) / 'protected_runner.py'),
                 invocation['owner_plan']['path'], invocation['owner_plan']['sha256']], 'pins': pins}
    need(outer_plan == expected_outer, 'complete_outer_plan_and_pins')
    return hand, invocation, owner_plan, outer_plan


def summarize(request):
    """Present saved trusted-owner outcomes; no scientific reclassification."""
    need(set(request) == {'operation', 'assessment'}, 'summary_keys')
    ready = decode(read_pin(request['assessment']))
    need(type(ready) is dict and set(ready) == {'schema', 'session', 'invocation', 'program', 'deviations',
                                               'execution_selected'}, 'assessment_ready_keys')
    need(ready['schema'] == 'nider_owner_package_assessment_v1' and ready['execution_selected'] is False,
         'assessment_ready_identity')
    cfg, fixed, session, modules, runtime, prepared = admit_session(ready['session'])
    c = modules['custody']; root = plain(session['root'])
    need(Path(request['assessment']['path']) == root / 'ASSESSMENT_READY.json', 'assessment_ready_location')
    hand, invocation, owner_plan, outer_plan = admitted_assessment_graph(ready, session, cfg, modules, runtime, prepared)
    owner = root / 'assessment/owner'; outer = root / 'assessment/execution'
    result = {'schema': 'nider_participant_outcome_v1', 'task': fixed['task'], 'profile': fixed['profile'],
              'arm': session['arm'], 'program_sha256': hand['program']['sha256'], 'execution_valid': False,
              'status': 'INCOMPLETE', 'original_agreement': None, 'procedure_agreement': None,
              'original_fields_agree': None, 'original_fields_total': 12,
              'procedure_fields_agree': None, 'procedure_fields_total': 36,
              'resource_cleanup_verified': False,
              'scope': 'Method-specified12-quantity reproduction;3hypothetical procedure controls are not empirical benchmarks.'}
    # An outer record is written only at observer finalization. A recorded early
    # child/preflight failure need not have produced an owner lifecycle at all.
    outer_life = outer / 'LIFECYCLE.json'
    if outer_life.exists():
        out = c.decode(c.read_pin(observed_pin(outer_life)))
        need(out['schema'] == 'nider_protected_outer_lifecycle_v1' and
             out['plan_sha256'] == invocation['outer_plan']['sha256'] and out['argv'] == outer_plan['argv'],
             'outer_actual_plan_join')
        result['status'] = 'EXECUTION_FAILURE'
        outer_closed = (out.get('exit_code') == 0 and out['termination_reason'] is None and out['reaped'] is True and
                        type(out['attempts']) is int and out['attempts'] == 1 and out['original_streams_complete'] is True and
                        set(out['pipe_EOF']) == {'stdout', 'stderr'} and
                        out['owned_container_cleanup_verified'] is True and out['all_four_cases_closed'] is True)
        owner_life = owner / 'LIFECYCLE.json'
        if owner_life.exists():
            own_pin = observed_pin(owner_life); own = c.decode(c.read_pin(own_pin))
            need(own['schema'] == 'nider_protected_runner_lifecycle_v1' and own['plan'] == invocation['owner_plan'] and
                 own['selection_id'] == owner_plan['selection_id'] and own['runtime_policy'] == prepared['runtime_policy'] and own_pin in out['files'], 'owner_actual_plan_and_custody_join')
            cleanup = own['cleanup']; created = own['created_CIDs']
            resource_closed = (own['all_owned_containers_removed'] is True and
                len(set(created)) == len(created) and len(cleanup) == len(created) and
                {v['cid'] for v in cleanup} == set(created) and
                all(v['removed_and_absence_verified'] is True for v in cleanup))
            result['resource_cleanup_verified'] = resource_closed and out['owned_container_cleanup_verified'] is True
            closed = (outer_closed and resource_closed and own['failure'] is None and own['all_four_closed'] is True and
                      own['score_written'] is True and len(created) == len(own['cases']) == 4)
            if closed:
                admission = c.decode(c.read_pin(own['runtime_admission']))
                need(own['runtime_admission'] in own['retained_file_pins'] and own['runtime_admission'] in out['files'] and admission['runtime_policy_sha256'] == modules['runtime_policy'].digest(prepared['runtime']), 'actual_runtime_admission_join')
                for number, (case, expected) in enumerate(zip(own['cases'], runtime['cases'])):
                    need(set(case) == {'case_id','workbook_sha256','program_sha256','response_sha256','container','closed'} and
                         case['case_id'] == expected['case_id'] and
                         case['workbook_sha256'] == prepared['assets'][expected['workbook_key']]['sha256'] and
                         case['program_sha256'] == hand['program']['sha256'] and case['closed'] is True and
                         case['container'] == created[number], 'actual_four_ordered_case_bindings')
                    need(type(case['response_sha256']) is str and len(case['response_sha256']) == 64 and
                         all(c in '0123456789abcdef' for c in case['response_sha256']), 'response_identity_shape')
                    name = 'nider-protected-' + hashlib.sha256((str(owner) + ':' + str(number)).encode()).hexdigest()[:24]
                    need(cleanup[number] == {'cid': created[number], 'name': name, 'removed_and_absence_verified': True},
                         'actual_cleanup_case_coverage')
                score_pin = observed_pin(owner / 'PRIVATE_SCORE.json')
                submission_pin = observed_pin(owner / 'CANDIDATE_SUBMISSION.json')
                need(all(entry in own['retained_file_pins'] and entry in out['files']
                         for entry in (score_pin, submission_pin)), 'retained_score_submission_identities')
                score = c.decode(c.read_pin(score_pin))
                need(score['schema'] == 'nider_scientific_reporting_score_v1' and score['policy'] == runtime['policy'] and
                     score['submission_sha256'] == submission_pin['sha256'] and score['arm'] == session['arm'] and
                     score['candidate_execution_verified'] is True and score['same_program_all_four_cases'] is True and
                     score['original_published_quantities'] == 12 and score['hypothetical_control_cases'] == 3, 'score_support')
                need([v['case_id'] for v in score['per_case']] == [v['case_id'] for v in runtime['cases']], 'score_case_universe')
                numeric = {'REPORTING_AGREEMENT', 'REPORTING_DISAGREEMENT', 'INDETERMINATE_REPORTING_BOUNDARY',
                           'INDETERMINATE_REFERENCE_REPORTING_BOUNDARY'}
                count = {'EXACT_COUNT_AGREEMENT', 'EXACT_COUNT_DISAGREEMENT'}
                counts = []
                for item, expected in zip(score['per_case'], runtime['cases']):
                    need(item['role'] == expected['kind'] and item['evaluated_fields'] == 12 and len(item['fields']) == 12,
                         'score_case_support')
                    pairs = {(v['contrast'], v['metric']) for v in item['fields']}
                    need(pairs == {(a,b) for a in ('amy_self','quest_self','amy_quest')
                                   for b in ('pearson_r','p_two_sided','k','N')}, 'score_field_support')
                    need(all(v['status'] in (count if v['metric'] in ('k','N') else numeric) for v in item['fields']),
                         'metric_specific_score_status')
                    counts.append(sum(v['status'] in ('REPORTING_AGREEMENT','EXACT_COUNT_AGREEMENT') for v in item['fields']))
                need(type(score['original_reporting_agreement']) is bool and type(score['coarse_procedure_agreement']) is bool and
                     type(score['complete_original_and_procedure_agreement']) is bool and
                     score['original_reporting_agreement'] == (counts[0] == 12) and
                     score['coarse_procedure_agreement'] == (sum(counts[1:]) == 36) and
                     score['complete_original_and_procedure_agreement'] == (sum(counts) == 48), 'score_summary_join')
                result.update(execution_valid=True, status='COMPLETE', original_agreement=score['original_reporting_agreement'],
                              procedure_agreement=score['coarse_procedure_agreement'], original_fields_agree=counts[0],
                              procedure_fields_agree=sum(counts[1:]))
    # A premature query is nonterminal and consumes no final publication slot.
    if result['status'] == 'INCOMPLETE':
        return {'public_result': None, 'candidate_feedback': result, 'publication_final': False, 'execution_selected': False}
    path = root / 'PUBLIC_RESULT.json'; raw = c.encoded(result)
    if path.exists():
        public = observed_pin(path)
        need(c.read_pin(public) == raw, 'existing_final_result_changed')
    else:
        public = c.write_new(path, raw)
    # Only candidate_feedback / file bytes are public; enclosing path metadata
    # belongs to the operator. No target values/private IDs/keys are disclosed.
    return {'public_result': public, 'candidate_feedback': result, 'publication_final': True, 'execution_selected': False}


def main():
    os.umask(0o077)
    need(len(sys.argv) == 3, 'request_path_and_sha256_required')
    path = plain(sys.argv[1])
    entry = {'path': str(path), 'bytes': path.stat().st_size, 'sha256': sys.argv[2]}
    request = decode(read_pin(entry, maximum=65536))
    need(type(request) is dict, 'request_object')
    op = request.get('operation')
    if op == 'prepare':
        result = prepare(request, entry)
    elif op == 'prepare_assessment':
        result = prepare_assessment(request)
    elif op == 'summarize':
        result = summarize(request)
    else:
        raise ValueError('unknown_operation')
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
