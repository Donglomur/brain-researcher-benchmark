"""Pure consistency check of one admitted, closed viewer grading operation.

No process probe, Docker call, private-target read or programme replay occurs.
The caller supplies an admitted request and its authenticated original API.
The existing pure absence parser and comparison arithmetic are reused. This
does not independently attest Engine state, participant isolation or a model.
"""
import math
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).absolute().parent
sys.path.insert(0, str(HERE))
import run as shared

METRICS = {'balanced_accuracy', 'log_loss'}
OPERATOR_FILES = {
    'outer_intent.json', 'child_ownership.json', 'invocation.json',
    'ownership.json', 'create_attempt.json', 'create_result.json',
    'inspection.json', 'terminal_inspection.json', 'child_receipt.json',
    'cleanup-00.json', 'cleanup-01.json',
}
CONTROLLER_FIELDS = {
    'schema', 'status', 'request', 'controller', 'owner_token', 'pid', 'pgid',
    'snapshot', 'collection_authority', 'grade_attempted', 'grade', 'returncode', 'error',
}
OUTER_FIELDS = {
    'schema', 'status', 'request', 'snapshot', 'collection_authority',
    'controller_result', 'process_completion', 'process_cleanup', 'grader_cleanup',
    'controller_direct_handle_reaped', 'all_owned_absent', 'private_grade_dispatched',
    'costs', 'scientific_qualification', 'provider_qualification', 'wall_seconds_before_receipt',
}


def need(value, message):
    if not value:
        raise ValueError(message)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def same(value, expected):
    """JSON identity includes numeric/boolean types, not Python's True == 1."""
    if type(value) is not type(expected):
        return False
    if type(value) is dict:
        return set(value) == set(expected) and all(same(value[k], expected[k]) for k in value)
    if type(value) is list:
        return len(value) == len(expected) and all(same(a, b) for a, b in zip(value, expected))
    return value == expected


def macro_score(score, comparisons):
    """Original exact equal-mouse reduction and six-reference arithmetic."""
    need(score.get('status') == 'scored' and score.get('private_targets_decoded') is True and
         score.get('candidate_program_replayed') is False and score.get('candidate_code_executed') is False,
         'Actual protected static score, no invented programme execution')
    need(score.get('full_contract_qualified') is False and
         score.get('scientific_success_threshold') is None and score.get('scientific_success') is None,
         'Protected scorer has not granted scientific qualification')
    rows = score['per_mouse']
    need(type(rows) is list and len(rows) == 7, 'All seven mouse scores')
    folds = []
    for row in rows:
        need(type(row) is dict and set(row) == {'fold', *METRICS} and
             integer(row['fold']) and row['fold'] < 7, 'Exact typed mouse score fields')
        folds.append(row['fold'])
        need(all(type(row[k]) in (int, float) and math.isfinite(row[k]) for k in METRICS) and
             0 <= row['balanced_accuracy'] <= 1 and row['log_loss'] >= 0,
             'Finite nonboolean mouse score domains')
    need(sorted(folds) == list(range(7)), 'Each original held mouse appears exactly once')
    expected = {k: math.fsum(row[k] for row in rows) / 7 for k in METRICS}
    need(score['co_primary_metrics'] == expected, 'Exact original equal-mouse reduction')
    comparisons.comparisons(score)
    return {'co_primary_metrics': score['co_primary_metrics'],
            'per_mouse': sorted(rows, key=lambda row: row['fold']),
            'reference_metrics': score['reference_metrics'],
            'signed_candidate_minus_reference': score['signed_candidate_minus_reference']}


def check(root, request, api, *, historical_viewer_authority=None):
    """Check saved journals only; context/source admission belongs to the caller.

    historical_viewer_authority, when supplied, is the independently selected
    authority descriptor. It must equal the admitted collection binding; no
    historical PID is probed and no recorded output is replayed.
    """
    root = Path(root)
    need(root.is_absolute() and '..' not in root.parts and request['output_root'] == str(root),
         'Exact admitted viewer grading root')
    need(request['schema'] == 'neural034-viewer-grading-request/v1', 'Viewer grading request')
    if historical_viewer_authority is not None:
        need(same(historical_viewer_authority, request['collection_authority']),
             'Independently selected historical viewer authority')
    cache = {}
    total = 0

    def body(path, cap=300000):
        nonlocal total
        path = Path(path)
        need(path.is_relative_to(root), 'Only current grading metadata')
        if path not in cache:
            raw = shared.capture(path, cap)
            total += len(raw)
            need(total <= 4 * 1024**2, 'Bounded saved grading metadata')
            cache[path] = raw
        need(len(cache[path]) <= cap, 'Selected saved metadata cap')
        return cache[path]

    def load(path, cap=300000):
        return shared.decode(body(path, cap))

    def pinned(path, expected, cap=300000):
        raw = body(path, cap)
        need(same(shared.pin(raw), expected), 'Exact saved receipt pin')
        return shared.decode(raw)

    snapshot = shared.validate_snapshot(request, root)
    snapshot_pin = {key: request['snapshot'][key] for key in ('bytes', 'sha256')}
    need(same(shared.pin(snapshot), snapshot_pin), 'Admitted complete viewer submission')
    outer = load(root / 'outer-result.json')
    need(type(outer) is dict and set(outer) == OUTER_FIELDS and
         outer['schema'] == 'neural034-viewer-grading-result/v1' and outer['status'] == 'viewer_scored',
         'Closed viewer grading result, not a programme receipt')
    for key, expected in (('request', request['request_pin']), ('snapshot', request['snapshot']),
                          ('collection_authority', request['collection_authority'])):
        need(same(outer[key], expected), 'Outer admitted ' + key)
    need(all(outer[key] is True for key in
             ('controller_direct_handle_reaped', 'all_owned_absent', 'private_grade_dispatched')) and
         outer['scientific_qualification'] is False and outer['provider_qualification'] is False,
         'Closed resources without invented scientific or provider qualification')
    elapsed = outer['wall_seconds_before_receipt']
    need(type(elapsed) in (int, float) and math.isfinite(elapsed) and
         0 <= elapsed <= request['stage_seconds'], 'Finite saved grading time within admitted stage')
    costs = outer['costs']
    need(type(costs) is dict and set(costs) == {'stage_allowance_seconds', 'prior_costs_reset',
         'known_family_before', 'historical_lifetime_complete'} and
         integer(costs['stage_allowance_seconds'], 60) and costs['stage_allowance_seconds'] <= 180 and
         costs['stage_allowance_seconds'] == request['stage_seconds'] and
         costs['prior_costs_reset'] is False and costs['historical_lifetime_complete'] is False and
         same(costs['known_family_before'], request['known_family_before']),
         'Explicit separate viewer-stage cost, no fabricated programme allowance')

    owner, unused = api.owner.expected(root)
    need(same(owner, load(root / 'process_owner.json', 16384)), 'Captured actual owner record')
    need(integer(owner['pid'], 2) and owner['pgid'] == owner['pid'] and
         type(owner['token']) is str and re.fullmatch('[0-9a-f]{32}', owner['token']) and
         same(owner['controller'], request['controller']) and
         same(owner['child_argv'], request['controller_argv']), 'Exact current controller ownership')
    need(type(owner['seconds']) in (int, float) and math.isfinite(owner['seconds']) and
         owner['seconds'] == request['stage_seconds'] - 5, 'Exact selected original group lifetime')
    ready = load(root / 'process_ready.json', 16384)
    gate = load(root / 'process_gate.json', 16384)
    need(same(ready, {'token': owner['token'], 'pid': owner['pid'], 'pgid': owner['pid'],
                     'python_initialized_before_identity_snapshot': True}) and
         same(gate, {'token': owner['token'], 'activate': True}), 'Actual durable activation barriers')
    controller = pinned(root / 'controller-result.json', outer['controller_result'])
    need(type(controller) is dict and set(controller) == CONTROLLER_FIELDS and
         controller['schema'] == 'neural034-viewer-grading-controller/v1' and
         controller['status'] == 'scored' and type(controller['returncode']) is int and
         controller['returncode'] == 0 and controller['error'] is None and
         controller['grade_attempted'] is True, 'Successful exact controller result')
    for key, expected in (('request', request['request_pin']), ('controller', request['controller']),
                          ('snapshot', request['snapshot']), ('collection_authority', request['collection_authority'])):
        need(same(controller[key], expected), 'Controller admitted ' + key)
    need(controller['owner_token'] == owner['token'] and integer(controller['pid'], 2) and
         controller['pid'] != owner['pid'] and type(controller['pgid']) is int and
         controller['pgid'] == owner['pid'], 'Actual child PID and owned group')
    completion = pinned(root / 'process_completion.json', outer['process_completion'], 16384)
    need(same(completion, {'token': owner['token'], 'returncode': 0, 'child_pid': controller['pid'],
                          'group_leader_waits_for_owner_stop': True}), 'Original owned-child completion')
    process = outer['process_cleanup']
    need(process['status'] == 'owned_group_absent' and process['absence_verified'] is True and
         type(process['pid']) is int and process['pid'] == process['pgid'] == owner['pid'] and
         type(process['bootstrap_returncode']) is int and process['stderr'] == '',
         'Recorded original group stop and retained-handle reaping')
    acknowledgment = shared.decode(process['stdout'].encode())
    need(same(acknowledgment, {'status': 'scored', 'returncode': 0,
                             'controller_result': outer['controller_result']}),
         'Stopped controller stdout joins the same durable result')
    intent = load(root / 'grade_attempted.json', 16384)
    grade_root = root / 'grader'
    need(same(intent, {'schema': 'neural034-viewer-grade-intent/v1', 'request': request['request_pin'],
                      'controller': request['controller'], 'owner_token': owner['token'],
                      'snapshot': request['snapshot'], 'grade_output': str(grade_root)}),
         'One durable protected-grade intent')

    operator = grade_root / 'operator'
    need({item.name for item in operator.iterdir()} == OPERATOR_FILES and
         {item.name for item in grade_root.iterdir()} == {'operator', 'score.json'},
         'Exact one-call grader journal set and two real cleanup passes')
    owned_body = body(operator / 'ownership.json', 65536)
    owned = shared.decode(owned_body)
    attempted = load(operator / 'create_attempt.json', 16384)
    created = load(operator / 'create_result.json', 32768)
    child = load(operator / 'child_receipt.json')
    grade = controller['grade']
    name, identity = grade['container'], grade['immutable_id']
    need(type(name) is str and re.fullmatch('neural034-score-[0-9a-f]{16}', name) and
         type(identity) is str and re.fullmatch('[0-9a-f]{64}', identity), 'Typed actual grader identities')
    need(owned['container'] == name and owned['intent_before_create'] is True and
         attempted['container'] == name and attempted['create_attempted'] is True and
         same(attempted['ownership_pin'], shared.pin(owned_body)) and
         owned['mounts']['/submission/probabilities.json'] == str(root / request['snapshot']['path']),
         'Durable exact grader create and viewer submission binding')
    need(created['container'] == name and created['create_returned'] is True and
         same(created['result'], child['create']) and child['created_id'] == identity and
         type(child['create']['returncode']) is int and child['create']['returncode'] == 0 and
         child['create']['stdout'] in (identity, identity + '\n') and child['create']['stderr'] == '',
         'Successful create returned the same immutable grader ID')
    need(api.recovery.absence(child['precreate_absence']['returncode'],
         child['precreate_absence']['stdout'], child['precreate_absence']['stderr'], 'container', name),
         'Exact saved grader precreate absence')
    child_owner = load(operator / 'child_ownership.json', 16384)
    need(same(child_owner, {'pid': controller['pid'], 'process_group': controller['pgid'],
                           'container': name, 'journal_before_child_resource_dispatch': True}),
         'Protected grader ran in this actual controller group')
    outer_intent = load(operator / 'outer_intent.json', 16384)
    need(same(outer_intent, {'container': name, 'same_shared_controller_group': True,
                            'bridge_source': 'ordinary-completion-v1/grader/grade_bridge.py',
                            'no_new_host_process_group': True, 'grader_retained_cap_bytes': 1813840}),
         'Original protected grade bridge intent')
    invocation = load(operator / 'invocation.json', 16384)
    need(same(invocation, {'submission': snapshot_pin, 'producer_stopped_attested': False,
                          'scope': 'Static numerical-file scoring, not candidate-program replay.'}),
         'Original static scoring scope and exact frozen submission')
    initial = load(operator / 'inspection.json', 150000)
    terminal = load(operator / 'terminal_inspection.json', 150000)
    need(initial['Id'] == terminal['Id'] == identity and initial['Name'] == terminal['Name'] == '/' + name and
         initial['Image'] == terminal['Image'] and same(initial['Config'], terminal['Config']),
         'Saved initial and terminal immutable grader identities')
    need(initial['State']['Status'] == 'created' and initial['State']['Running'] is False and
         type(initial['State']['Pid']) is int and initial['State']['Pid'] == 0 and
         terminal['State']['Status'] == 'exited' and terminal['State']['Running'] is False and
         type(terminal['State']['Pid']) is int and terminal['State']['Pid'] == 0 and
         type(terminal['State']['ExitCode']) is int and terminal['State']['ExitCode'] == 0 and
         terminal['State']['OOMKilled'] is False, 'Saved created-to-successfully-exited grader states')
    score_body = body(grade_root / 'score.json', 150000)
    score = shared.decode(score_body)
    need(child['status'] == 'scored' and child['container'] == name and child['candidate_code_executed'] is False and
         'error' not in child and same(child['result'], score) and
         type(child['worker']['returncode']) is int and child['worker']['returncode'] == 0 and
         child['worker']['stderr'] == '' and same(shared.decode(child['worker']['stdout'].encode()), score),
         'Actual saved attached-worker output equals retained score')
    need(same(grade, {'status': 'scored', 'container': name, 'immutable_id': identity,
                     'absence_verified': True, 'id_absent': True, 'name_absent': True,
                     'score_sha256': shared.pin(score_body)['sha256'],
                     'submission_sha256': snapshot_pin['sha256'], 'private_targets_decoded': True,
                     'same_shared_controller_group': True, 'no_new_host_process_group': True}),
         'Exact original grade return pins')
    cleanup = [load(operator / ('cleanup-%02d.json' % i)) for i in range(2)]
    for row in cleanup:
        need(row['name'] == name and row['immutable_id'] == identity and
             all(row[key] is True for key in ('absence_verified', 'absent', 'id_absent', 'name_absent')) and
             row['create_extent_unknown'] is False, 'Saved ID and name absence for each real cleanup')
        for key, selected in (('id_inspect', identity), ('name_inspect', name)):
            reply = row[key]
            need(api.recovery.absence(reply['returncode'], reply['stdout'], reply['stderr'], 'container', selected),
                 'Original strict missing-resource parser accepts exact resource absence')
    recovered = outer['grader_cleanup']
    need(same(child['cleanup'], cleanup[0]) and recovered['container'] == name and
         recovered['absence_verified'] is True and recovered['create_extent_unknown'] is False and
         same(recovered['evidence'], cleanup[1]), 'Normal cleanup and post-group outer recovery join')
    metrics = macro_score(score, shared.load_comparisons(request))
    return {'schema': 'neural034-viewer-grade-consistency/v1',
            'status': 'consistent_closed_viewer_score', 'request': request['request_pin'],
            'collection_authority': request['collection_authority'], 'snapshot': request['snapshot'],
            'controller_result': outer['controller_result'], 'process_completion': outer['process_completion'],
            'score': shared.pin(score_body), 'cases': 140, 'mice': 7,
            'cleanup_receipts': 2, 'costs': costs, **metrics,
            'cached_journal_bytes': total,
            'runtime_qualified': False, 'scientific_qualification': False, 'provider_qualification': False,
            'scope': 'Consistency of admitted viewer collection, current owned grading journals and original score arithmetic; no programme replay, private-target recomputation, live Engine observation or general containment attestation.'}
