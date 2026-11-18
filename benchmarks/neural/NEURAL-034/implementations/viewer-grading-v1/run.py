"""Grade one separately admitted, already closed combined-view collection.

This owns a new grading controller only. It neither runs a participant nor
replays or supervises historical viewer processes. Root admission is external.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time
import types

HERE = Path(__file__).resolve().parent
PREFIX = 'benchmarks/neural/NEURAL-034/implementations/'
STAGED = 'authoring/neural034-viewer-grading-v1/'
LOCAL = 'authoring/glial-context-v1/ordinary-completion-v1/'
MODE = 'active_fold_calcium_behavior_viewer'
SOURCE_COMMIT = '557488918361fbe19aa24ce7ec7236dc7f8bc9b2'
MANIFEST = {'bytes': 10889, 'sha256': '498cd4c28ab36142ca5c5efa9398ae6c0f8b6b9a8c31c608166be176f69436ee'}
FREEZE = {'path': LOCAL + 'SOURCE_FREEZE.json', 'bytes': 7753,
          'sha256': 'e8de862941afe85c8904d85f52aed816c2a654ca717eecbb7ad828b700167a7c'}
RETAINED = {
    'receipt': {'bytes': 6992, 'sha256': '8a2a848dea45e8d881cc50ad81f05c5b29472355b726d3be1b1b6ec1da5b5005'},
    'independent_review': {'bytes': 36111, 'sha256': '5304764e7f7c680b9a12f9dcf16139acfaf4f9d115f413602ef0f2ac1957936b'},
    'submission': {'bytes': 9419, 'sha256': 'c55e9f9482c0bd0eb20651a0b0755f8ea92d4bf82434a3cbf67a25e6038f111c'},
}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def literal(path):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts and
         all(not x.is_symlink() for x in (path, *path.parents)), 'Literal unlinked path')
    return path


def capture(path, cap=262144):
    path = literal(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             0 < before.st_size <= cap, 'Bounded ordinary single-link bytes')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(cap + 1)
        after, linked = os.fstat(fd), path.lstat()
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        need(len(body) == before.st_size and all(getattr(before, key) == getattr(after, key) ==
             getattr(linked, key) for key in fields), 'Stable complete captured bytes')
        return body
    finally:
        os.close(fd)


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def decode(body):
    def pairs(rows):
        value = {}
        for key, item in rows:
            need(key not in value, 'Duplicate JSON key'); value[key] = item
        return value
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'Nonfinite JSON'))


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def descriptor(value, *, absolute=True):
    need(type(value) is dict and set(value) == {'path', 'bytes', 'sha256'}, 'Exact descriptor')
    name = value['path']; path = Path(name)
    need(type(name) is str and len(name) <= 4096 and '..' not in path.parts and
         path.is_absolute() == absolute and path.as_posix() == name and
         not any(c in name for c in '\0\r\n'), 'Canonical descriptor path')
    need(type(value['bytes']) is int and 0 < value['bytes'] <= 1048576 and
         type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']),
         'Typed bounded descriptor')
    return {key: value[key] for key in ('bytes', 'sha256')}


def checked(value, cap=262144, root=None):
    expected = descriptor(value, absolute=root is None)
    path = Path(value['path']) if root is None else literal(root) / value['path']
    body = capture(path, cap)
    need(pin(body) == expected, 'Exact pinned bytes')
    return body


def publish(path, body, budget, mode=0o400):
    need(type(body) is bytes and 0 < len(body) <= 262144 and mode in (0o400, 0o444),
         'Bounded explicit publication')
    path = budget.safe_destination(literal(path)); budget.check(len(body), receipt=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(body); stream.flush(); os.fchmod(fd, mode); os.fsync(fd)
    finally:
        os.close(fd)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def write(path, value, budget):
    publish(path, encode(value), budget)


def module(name, path, body):
    result = types.ModuleType(name); result.__file__ = str(path)
    sys.modules[name] = result
    exec(compile(body, str(path), 'exec'), result.__dict__)
    return result


def package(source, repository, staged=HERE):
    body = checked(source, 32768); value = decode(body)
    need(value.get('schema') == 'neural034-viewer-grading-source/v1' and
         value.get('execution_authority') is False, 'Non-authorizing source descriptor')
    need(set(value['members']) == {'run.py', 'controller.py', 'check_result.py',
         'README.md', 'tests/test_viewer_grading.py'}, 'Exact six-file additive package')
    need(pin(capture(staged / 'SOURCE.json', 32768)) == pin(body), 'Same staged source descriptor')
    for name, expected in value['members'].items():
        checked({'path': name, **expected}, root=staged)
    dependencies = {}
    for name, expected in value['dependencies'].items():
        dependencies[name] = checked({'path': name, **expected}, root=repository)
    return value, dependencies


def expected_ids(cases_body):
    value = decode(cases_body)
    need(set(value) == {'schema_version', 'cases'} and type(value['schema_version']) is int and
         value['schema_version'] == 1 and len(value['cases']) == 140, 'Original complete public cases')
    result = [[] for _ in range(7)]
    for index, row in enumerate(value['cases']):
        need(set(row) == {'fold', 'query_id'} and type(row['fold']) is int and
             row['fold'] == index // 20 and type(row['query_id']) is str and
             re.fullmatch('[0-9a-f]{24}', row['query_id']), 'Ordered public fold identity')
        result[row['fold']].append(row['query_id'])
    need(all(len(set(ids)) == 20 for ids in result), 'Distinct public case identity')
    return result


def validate_probabilities(body, identities):
    need(type(body) is bytes and 0 < len(body) <= 100000 and type(identities) is list and
         len(identities) == 7 and all(type(ids) is list and len(ids) == 20 and
         len(set(ids)) == 20 for ids in identities), 'Seven complete original case lists')
    value = decode(body)
    need(set(value) == {'schema_version', 'probabilities'} and type(value['schema_version']) is int
         and value['schema_version'] == 1 and type(value['probabilities']) is list and
         len(value['probabilities']) == 140, 'Complete 140-row submission')
    for index, row in enumerate(value['probabilities']):
        fold, query = divmod(index, 20)
        need(type(row) is dict and set(row) == {'fold', 'query_id', 'probability'} and
             type(row['fold']) is int and row['fold'] == fold and
             row['query_id'] == identities[fold][query], 'Exact ordered original query identity')
        number = row['probability']
        need(type(number) in (int, float) and math.isfinite(number) and 0 <= number <= 1,
             'Finite nonboolean probability')
    return value


def closed_authority(value, collection):
    """Pure schema check; caller MUST first authenticate separately admitted bytes.

    The authority records a trusted review of the closed collector, not a
    participant-written claim. Checking this shape alone establishes no trust.
    """
    need(value.get('schema') == 'neural034-closed-viewer-collection-authority/v1' and
         value.get('reviewer') == 'root' and value.get('decision') == 'accept_closed_combined_viewer_collection',
         'Separate root acceptance of closed collection')
    need(value.get('task_id') == 'NEURAL-034' and value.get('mode') == MODE and
         value.get('source_commit') == SOURCE_COMMIT and value.get('folds') == 7 and
         type(value.get('folds')) is int and value.get('queries') == 140 and
         type(value.get('queries')) is int, 'Original combined seven-fold scope')
    need(value.get('all_participant_groups_closed') is True and value.get('all_workspaces_removed') is True
         and value.get('owner_controlled_collection_reviewed') is True and
         value.get('protocol_only') is False and value.get('status') == 'complete_unscored',
         'Actual closed producer and collector acceptance')
    for key in ('submission', 'transport_receipt', 'independent_review'):
        need(value.get(key) == collection.get(key), 'Same admitted ' + key)
    need(value.get('source_bindings') == collection.get('source_bindings') and
         value.get('execution_identity') == collection.get('execution_identity') and
         type(value.get('execution_identity')) is str and value['execution_identity'],
         'Same source/client/condition and actual execution identity')
    return value


def closed_receipt(receipt, collection):
    """Join already reviewed closure metadata; never replay or probe old PIDs."""
    need(receipt.get('schema') == 'neural034-viewer-transport-collection/v1' and
         receipt.get('mode') == MODE and receipt.get('folds') == 7 and receipt.get('queries') == 140 and
         receipt.get('status') == 'complete_unscored' and
         receipt.get('submission') == descriptor(collection['submission']) and
         receipt.get('restricted_local_process_transport') is True and
         receipt.get('source') == collection['source_bindings'], 'Complete original collector receipt')
    sessions = receipt.get('sessions')
    need(type(sessions) is dict and set(sessions) == {str(i) for i in range(7)},
         'Seven closed viewer session records')
    shared_fields = ('schema', 'mode', 'limits', 'sandbox', 'client_sha256', 'python', 'source')
    common = None; episodes = []; workspaces = []
    for fold in range(7):
        boundary = sessions[str(fold)]['boundary']; result = sessions[str(fold)]['result']
        need(type(boundary['fold']) is int and boundary['fold'] == fold and boundary['mode'] == MODE and
             boundary['sandbox'] == 'macos' and boundary['source'] == receipt['source'],
             'Same restricted original source and active fold')
        selected = {key: boundary[key] for key in shared_fields}
        need(common is None or selected == common, 'Matched client/source/presentation conditions')
        common = selected; episodes.append(boundary['episode_id']); workspaces.append(boundary['workspace'])
        need(result.get('schema') == 'neural034-viewer-transport-result/v1' and
             result.get('status') == 'complete_unscored' and type(result.get('fold')) is int and
             result['fold'] == fold and result.get('episode_id') == boundary['episode_id'] and
             type(result.get('client_exit_code')) is int and result['client_exit_code'] == 0 and
             result.get('forced_stop') is False and result.get('workspace_destroyed') is True and
             result.get('process_group_cleanup') == 'absent', 'Actual closed active-fold metadata')
    need(all(type(value) is str and value for value in episodes + workspaces) and
         len(set(episodes)) == len(set(workspaces)) == 7, 'Seven distinct removed viewer contexts')
    return receipt


def admit_collection(collection):
    need(type(collection) is dict and collection.get('route') in
         ('retained_20261117', 'separately_admitted_closed_collection'), 'Explicit collection provenance route')
    if collection['route'] == 'retained_20261117':
        for key in ('receipt', 'independent_review', 'submission'):
            need(descriptor(collection[key]) == RETAINED[key], 'Exact accepted retained ' + key)
        receipt = decode(checked(collection['receipt']))
        checked(collection['independent_review'])
        need(receipt['source_commit'] == SOURCE_COMMIT and
             receipt['result'] == 'complete_local_scripted_transport_control' and
             receipt['evidence']['collected_submission_sha256'] == RETAINED['submission']['sha256'] and
             receipt['evidence']['independent_final_review_sha256'] == RETAINED['independent_review']['sha256'],
             'Retained receipt and review join')
        return collection['receipt']
    authority = decode(checked(collection['authority']))
    closed_authority(authority, collection)
    receipt = decode(checked(collection['transport_receipt']))
    checked(collection['independent_review'])
    closed_receipt(receipt, collection)
    return collection['authority']


def validate_snapshot(request, out):
    expected = request['snapshot']
    need(expected['path'] == 'submission.json', 'Single frozen output snapshot')
    body = checked(expected, 100000, root=out)
    need(stat.S_IMODE((Path(out) / expected['path']).stat().st_mode) == 0o444, 'Immutable snapshot publication mode')
    validate_probabilities(body, request['expected_ids'])
    return body


def freeze_submission(submission, identities, out, budget):
    body = checked(submission, 100000)
    validate_probabilities(body, identities)
    publish(Path(out) / 'submission.json', body, budget, mode=0o444)
    result = {'path': 'submission.json', **pin(body)}
    validate_snapshot({'snapshot': result, 'expected_ids': identities}, out)
    return result


def make_budget(api, out, request):
    return api.HostBudget(out, limit=request['artifact_limit_bytes'], reserve=65536)


def review_context(review_path, review_sha256):
    body = capture(review_path, 65536)
    need(pin(body)['sha256'] == review_sha256, 'External exact root admission pin')
    review = decode(body)
    need(review.get('schema') == 'neural034-viewer-grading-admission/v1' and
         review.get('decision') == 'go_closed_viewer_protected_grading' and
         review.get('reviewer') == 'root' and review.get('task_id') == 'NEURAL-034' and
         review.get('execution_authorized') is True and review.get('protected_grading_authorized') is True,
         'Explicit separately admitted protected viewer grade')
    need(review.get('latest_cost_confirmed') is True and review.get('no_active_same_family_stage') is True and
         review.get('prior_costs_reset') is False and review.get('historical_lifetime_complete') is False,
         'Current root-owned finite cost admission, no reset or lifetime invention')
    need(review.get('scientific_qualification') is False and review.get('provider_qualification') is False,
         'No prospective scientific/provider qualification')
    need(type(review['stage_seconds']) is int and 60 <= review['stage_seconds'] <= 180 and
         type(review['artifact_limit_bytes']) is int and 2097152 <= review['artifact_limit_bytes'] <= 16777216,
         'Bounded new grading stage, not an ordinary programme480 allowance')
    before = review['known_family_before']
    need(type(before) in (int, float) and math.isfinite(before) and before >= 3789.932040249051,
         'Preserved known ordinary family subtotal; root reconciles later work')
    for field in ('allocation', 'independent_source_review', 'capacity_admission'):
        checked(review[field], 262144)
    root, repository = literal(review['configured_root']), literal(review['repository_root'])
    need(HERE == root / STAGED, 'Selected controller package staged inside configured authoring root')
    spec, dependencies = package(review['source'], repository)
    need(pin(capture(root / 'SOURCE_MANIFEST.json', 16384)) == MANIFEST and
         pin(checked(FREEZE, root=root)) == {k: FREEZE[k] for k in ('bytes', 'sha256')},
         'Accepted permission/cost successor, never unpatched templates')
    config_path = PREFIX + 'authentic-programme-v1/configure.py'
    config = module('_viewer_grading_configure', repository / config_path, dependencies[config_path])
    configured = config.load(root)
    need(configured['manifest'] == {'path': 'SOURCE_MANIFEST.json', **MANIFEST} and
         configured['source_freeze'] == FREEZE, 'Whole preserved configured source closure')
    support_path = PREFIX + 'runtime-prerequisite-v1/support.py'
    support = module('_viewer_grading_support', repository / support_path, dependencies[support_path])
    api, _ = support.runtime(root, FREEZE)
    admission = sys.modules['admission']
    admission.runtime_environment(review)
    qualification = decode(checked(review['portable_runtime']['qualification'], root=root))
    need(qualification.get('allowed_use') == 'separately_admitted_closed_viewer_protected_grading' and
         qualification.get('protected_grader_qualified') is True,
         'Candidate-only prerequisite qualification cannot authorize this grader')
    identities = expected_ids(dependencies[PREFIX + 'registered-runtime/public/cases.json'])
    collection_authority = admit_collection(review['collection'])
    return review, api, identities, collection_authority, {'path': str(review_path), **pin(body)}, spec


def request_value(review, identities, authority, root_pin, snapshot, out, controller, argv):
    return {'schema': 'neural034-viewer-grading-request/v1', 'output_root': str(out),
            'repository_root': review['repository_root'], 'configured_root': review['configured_root'],
            'root_review': root_pin, 'source': review['source'], 'source_freeze': FREEZE,
            'collection_authority': authority, 'collection': review['collection'],
            'expected_ids': identities, 'snapshot': snapshot, 'controller': controller,
            'controller_argv': argv, 'artifact_limit_bytes': review['artifact_limit_bytes'],
            'stage_seconds': review['stage_seconds'], 'known_family_before': review['known_family_before']}


def load_context(request_path, request_sha256):
    body = capture(request_path, 65536)
    need(pin(body)['sha256'] == request_sha256, 'Owner-pinned exact request')
    request = decode(body)
    need(request.get('schema') == 'neural034-viewer-grading-request/v1', 'Exact viewer grading request')
    root_pin = request['root_review']; checked(root_pin, 65536)
    review, api, identities, authority, observed_pin, _ = review_context(root_pin['path'], root_pin['sha256'])
    out = literal(review['output_path'])
    need(request['output_root'] == str(out) and Path(request_path) == out / 'request.json', 'Exact request location')
    controller = {'path': STAGED + 'controller.py', **pin(capture(HERE / 'controller.py'))}
    # The hash is in argv but not the serialized request: the owner pins request
    # bytes, and its argv binds that hash without a self-referential JSON hash.
    argv = [sys.executable, str(HERE / 'controller.py'), '--request', str(request_path)]
    expected = request_value(review, identities, authority, observed_pin, request['snapshot'], out, controller, argv)
    need(request == expected, 'No mutable request selection outside root admission')
    need(descriptor(review['collection']['submission']) == descriptor(request['snapshot'], absolute=False),
         'Snapshot equals accepted complete collection')
    validate_snapshot(request, out)
    request['request_pin'] = pin(body); request['request_path'] = str(request_path)
    request['controller_argv'] = argv + ['--request-sha256', request_sha256]
    return request, api


def load_comparisons(request):
    source = decode(checked(request['source'], 32768))
    name = PREFIX + 'result-integrity-v2/check_result.py'
    repository = literal(request['repository_root'])
    body = checked({'path': name, **source['dependencies'][name]}, root=repository)
    return module('_viewer_grading_comparisons', repository / name, body)


def own_grade(api, request, out):
    """Existing launch/stop/recover sequence; injectable only for generated tests.

    Dispatch is unknown until group closure permits a stable intent-marker
    check. The resolved Boolean is not independent observation of private I/O.
    """
    out = literal(out); budget = make_budget(api, out, request)
    start = time.monotonic(); end = start + request['stage_seconds']; proc = None
    result = {'schema': 'neural034-viewer-grading-result/v1', 'status': 'execution_failed_preserved',
              'request': request['request_pin'], 'snapshot': request['snapshot'],
              'collection_authority': request['collection_authority'], 'controller_result': None,
              'process_completion': None, 'controller_direct_handle_reaped': False,
              'all_owned_absent': False, 'private_grade_dispatched': None,
              'scientific_qualification': False, 'provider_qualification': False,
              'costs': {'stage_allowance_seconds': request['stage_seconds'], 'prior_costs_reset': False,
                        'known_family_before': request['known_family_before'], 'historical_lifetime_complete': False}}
    try:
        validate_snapshot(request, out)
        proc = api.owner.launch(request['controller_argv'], out, request['stage_seconds'] - 5, request['controller'])
        while not (out / 'process_completion.json').exists():
            need(time.monotonic() < end - 20, 'New grading work deadline leaves cleanup reserve')
            need(proc.poll() is None, 'Original group leader must survive until owned stop')
            time.sleep(.01)
        completion = capture(out / 'process_completion.json', 16384)
        result['process_completion'] = pin(completion)
    except BaseException as error:
        result['error'] = repr(error)
    finally:
        try:
            result['process_cleanup'] = api.owner.stop(out, end - 10, proc)
            result['controller_direct_handle_reaped'] = proc is not None and proc.returncode is not None
        except BaseException as error:
            result['process_cleanup'] = {'absence_verified': False, 'error': repr(error)}
        # Recovery is forbidden until the NEW controller is gone. Never inspect
        # or signal any PID from the accepted historical viewer proof.
        if result['process_cleanup']['absence_verified'] and result['controller_direct_handle_reaped']:
            try:
                result['private_grade_dispatched'] = (out / 'grade_attempted.json').exists()
                need(not result['private_grade_dispatched'] or (out / 'grader').is_dir(),
                     'Attempted grader without directory is unresolved')
                result['grader_cleanup'] = api.grader.recover_grade(out / 'grader', end - 2)
            except BaseException as error:
                result['grader_cleanup'] = {'absence_verified': False, 'error': repr(error)}
        else:
            result['grader_cleanup'] = {'absence_verified': False, 'not_attempted_before_group_absence': True}
        result['all_owned_absent'] = (result['process_cleanup']['absence_verified'] is True and
                                     result['controller_direct_handle_reaped'] is True and
                                     result['grader_cleanup']['absence_verified'] is True)
        try:
            if (out / 'controller-result.json').exists():
                controller_body = capture(out / 'controller-result.json', 32768)
                result['controller_result'] = pin(controller_body)
            if result['all_owned_absent'] and 'error' not in result and result['controller_result'] is not None:
                controller = decode(controller_body)
                completion = decode(capture(out / 'process_completion.json', 16384))
                owner, _ = api.owner.expected(out)
                need(completion['token'] == owner['token'] == controller['owner_token'] and
                     completion['child_pid'] == controller['pid'] and completion['returncode'] == controller['returncode'] and
                     completion['group_leader_waits_for_owner_stop'] is True, 'New controller completion joins actual owned child')
                if controller['status'] == 'scored' and completion['returncode'] == 0:
                    result['status'] = 'viewer_scored'
        except BaseException as error:
            result['status'] = 'execution_failed_preserved'
            result['finalization_error'] = repr(error)
        result['wall_seconds_before_receipt'] = time.monotonic() - start
        write(out / 'outer-result.json', result, budget)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--review-sha256', required=True)
    args = parser.parse_args()
    review, api, identities, authority, root_pin, spec = review_context(args.review, args.review_sha256)
    out = literal(review['output_path']); root = literal(review['configured_root'])
    need(out.is_relative_to(root / 'artifacts-build') and not out.exists() and out.parent.is_dir(),
         'Fresh exact admitted grading output')
    out.mkdir(mode=0o700)
    budget = make_budget(api, out, review)
    snapshot = freeze_submission(review['collection']['submission'], identities, out, budget)
    controller = {'path': STAGED + 'controller.py', **spec['members']['controller.py']}
    request_path = out / 'request.json'
    argv = [sys.executable, str(root / controller['path']), '--request', str(request_path)]
    request = request_value(review, identities, authority, root_pin, snapshot, out, controller, argv)
    write(request_path, request, budget)
    request, api = load_context(request_path, pin(capture(request_path, 65536))['sha256'])
    result = own_grade(api, request, out)
    if result['status'] != 'viewer_scored':
        return 2
    inspector = module('_viewer_grading_check', HERE / 'check_result.py', capture(HERE / 'check_result.py'))
    checked_result = inspector.check(out, request, api)
    write(out / 'checked-result.json', checked_result, budget)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
