"""Portable single-program boundary; private references load after closed capture."""
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import stat
import time
import common as C
import schema as S
import bundle
import numeric_score

ID = 'PAPER-FIND-REP-013'
IMAGE = 'sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'
MIB = 1024 ** 2


def fields(value, expected, reason):
    C.need(type(value) is dict and set(value) == set(expected), reason)


def locator(value, cap):
    fields(value, ('path', 'bytes', 'sha256'), 'exact_locator')
    C.plain(value['path']); C.admit_pin({k: value[k] for k in ('bytes', 'sha256')}, cap)
    return {k: value[k] for k in ('bytes', 'sha256')}


def evidence(entry, budget):
    return C.decode(C.read(entry['path'], locator(entry, MIB), budget), MIB)


def admit(request, package_pins, source_sha, budget):
    fields(request, ('schema', 'task_id', 'selected', 'attempt_id', 'source_lock_sha256',
                     'program', 'public_inputs', 'references', 'runtime', 'reviews',
                     'capacity', 'history', 'output_root'), 'request_fields')
    C.need(request['schema'] == 'purkinje-portable-program-request/v1' and
           request['task_id'] == ID and request['selected'] is True and
           request['source_lock_sha256'] == source_sha, 'root_selected_request')
    name = request['attempt_id']
    C.need(type(name) is str and 1 <= len(name) <= 64 and
           name[0] in 'abcdefghijklmnopqrstuvwxyz0123456789' and
           all(c in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in name), 'attempt_name')
    locator(request['program'], 131072)
    for role in ('public_inputs', 'references'):
        values = request[role]
        C.need(type(values) is dict and set(values) == set(package_pins[role]), 'complete_' + role)
        for leaf, entry in values.items():
            C.need(locator(entry, 5000000) == package_pins[role][leaf], 'exact_' + role + '_' + leaf)
    paths = [v['path'] for role in ('public_inputs', 'references') for v in request[role].values()]
    C.need(len(set(paths)) == len(paths), 'disjoint_public_private_files')
    runtime = request['runtime']
    fields(runtime, ('image', 'docker', 'docker_physical', 'daemon_socket', 'daemon_guard'), 'runtime_fields')
    C.need(runtime['image'] == IMAGE, 'fixed_original_image')
    C.plain(runtime['docker']); C.plain(runtime['daemon_socket'])
    C.need(type(runtime['docker_physical']) is list and len(runtime['docker_physical']) == 7 and
           all(type(x) is int for x in runtime['docker_physical']), 'physical_docker_identity')
    fields(request['reviews'], ('source', 'runtime'), 'review_roles')
    source = evidence(request['reviews']['source'], budget)
    native = evidence(request['reviews']['runtime'], budget)
    C.need(source.get('status') == 'passed' and source.get('source_lock_sha256') == source_sha and
           source.get('task_id') == ID and source.get('independent_whole_source') is True and
           source.get('public_leak_review') is True and source.get('findings') == [], 'exact_source_review')
    C.need(native.get('status') == 'passed' and native.get('image') == IMAGE and
           native.get('task_id') == ID and native.get('profile') == 'purkinje-portable-program-v1' and
           native.get('source_lock_sha256') == source_sha and native.get('runtime') == runtime and
           native.get('candidate_boundary_verified') is True and native.get('findings') == [], 'exact_native_qualification')
    cap = evidence(request['capacity'], budget)
    fields(cap, ('schema', 'observed_utc', 'normal_pressure', 'available_bytes', 'host_reserved_bytes',
                 'VM_reserved_bytes', 'other_reserved_bytes', 'margin_bytes', 'swap_growth_bytes',
                 'pageout_growth_bytes', 'complete_roster', 'free_disk_bytes', 'evidence_pins'), 'capacity_fields')
    age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(cap['observed_utc'])).total_seconds()
    C.need(cap['schema'] == 'purkinje-root-admitted-capacity/v1' and 0 <= age <= 60 and
           cap['normal_pressure'] is True and cap['complete_roster'] is True, 'fresh_root_capacity')
    numeric = ('available_bytes', 'host_reserved_bytes', 'VM_reserved_bytes', 'other_reserved_bytes',
               'margin_bytes', 'swap_growth_bytes', 'pageout_growth_bytes', 'free_disk_bytes')
    C.need(all(type(cap[k]) is int and cap[k] >= 0 for k in numeric), 'typed_capacity')
    C.need(cap['host_reserved_bytes'] >= 512 * MIB and cap['VM_reserved_bytes'] >= 3 * 1024 ** 3 and
           cap['margin_bytes'] >= 1024 ** 3 and cap['swap_growth_bytes'] == cap['pageout_growth_bytes'] == 0 and
           cap['available_bytes'] >= sum(cap[k] for k in ('host_reserved_bytes', 'VM_reserved_bytes', 'other_reserved_bytes', 'margin_bytes')) and
           cap['free_disk_bytes'] >= 15000000000 + 128 * MIB, 'adequate_preserved_reserves')
    C.need(type(cap['evidence_pins']) is list and 1 <= len(cap['evidence_pins']) <= 16, 'capacity_originals')
    for entry in cap['evidence_pins']:
        C.read(entry['path'], locator(entry, MIB), budget)
    history = evidence(request['history'], budget)
    C.need(history.get('schema') == 'purkinje-root-admitted-history/v1' and
           history.get('task_id') == ID and history.get('closed') is True and
           type(history.get('known_charged_seconds')) in (int, float) and
           math.isfinite(history['known_charged_seconds']) and history['known_charged_seconds'] >= 1167.2520854590086 and
           type(history.get('consumed_attempt_ids')) is list and
           all(type(x) is str for x in history['consumed_attempt_ids']) and
           len(set(history['consumed_attempt_ids'])) == len(history['consumed_attempt_ids']) and
           name not in history['consumed_attempt_ids'], 'root_admitted_unconsumed_history')
    out = C.plain(request['output_root'])
    C.need(not out.exists() and out.parent.is_dir() and
           shutil.disk_usage(out.parent).free >= 15000000000 + 128 * MIB, 'fresh_output_and_storage')
    return cap, history


def stage_inputs(request, root, budget):
    folder = root / 'input'; folder.mkdir(mode=0o700)
    for name, entry in sorted(request['public_inputs'].items()):
        path = folder / name
        C.need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'public_leaf')
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = C.read(entry['path'], locator(entry, 5000000), budget, cap=5000000)
        C.write(path, raw, budget, mode=0o444)
    for d in sorted((p for p in folder.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        d.chmod(0o555)
    folder.chmod(0o555)
    return folder


def render_program(bridge_source, program):
    C.need(type(bridge_source) is bytes and type(program) is bytes and 0 < len(program) <= 131072, 'program_body')
    program.decode('utf-8')
    return bridge_source + b'\nif __name__ == "__main__":\n    run(' + repr(program).encode('ascii') + b')\n'


def execute(request, package, owner, budget, root, active_deadline):
    """The owner instance is fixed by the authenticated entry, not the request."""
    program = C.read(request['program']['path'], locator(request['program'], 131072), budget, cap=131072)
    program.decode('utf-8')
    C.write(root / 'program.py', program, budget)
    C.write(root / 'PROGRAM_COMMIT.json', C.encode({'program': C.pin(program),
            'before_public_payload_read': True, 'before_candidate_creation': True}), budget)
    input_dir = stage_inputs(request, root, budget)
    task_dir = root / 'task'; task_dir.mkdir(mode=0o700)
    for name in ('TASK.md', 'SCHEMA.json'):
        C.write(task_dir / name, package[name], budget, mode=0o444)
    task_dir.chmod(0o555)
    wrapped = render_program(package['bridge.py'], program)
    wrapper = root / 'selected-wrapper.py'; C.write(wrapper, wrapped, budget, mode=0o444)
    C.write(root / 'WRAPPER_COMMIT.json', C.encode({'candidate': C.pin(program),
            'bridge': C.pin(package['bridge.py']), 'rendered': C.pin(wrapped)}), budget)
    runtime = request['runtime']
    executable = C.plain(runtime['docker']); st = executable.lstat()
    C.need(list(C.signature(st)) == runtime['docker_physical'] and stat.S_ISREG(st.st_mode) and
           st.st_nlink == 1 and os.access(executable, os.X_OK), 'unchanged_selected_docker')
    owner.DOCKER = str(executable); owner.DAEMON_SOCKET = Path(runtime['daemon_socket'])
    owner.DAEMON_GUARD = runtime['daemon_guard']
    cli = owner.configure_cli(root / 'private-cli-config', budget)
    C.write(root / 'CLI.private.json', C.encode(cli), budget)
    episode = owner.require_closed_episode(owner.run_candidate(root=root / 'candidate', input_dir=input_dir,
              task_dir=task_dir, program=wrapper, budget=budget, active_deadline=active_deadline))
    C.need(not owner.registered_clients(), 'candidate_client_closure')
    if type(episode) is owner.ClosedFailure:
        result = {'status': 'candidate_failed', 'reason': episode.reason, 'lifecycle': episode.lifecycle,
                  'private_numeric_reference_loads': 0, 'scientific_success': None}
        C.write(root / 'RESULT.json', C.encode(result), budget)
        return result
    closed = owner.require_closed(episode)
    raw = C.read(closed.submission['path'], locator(closed.submission, bundle.CAP), budget, cap=bundle.CAP)
    C.write(root / 'CANDIDATE_CLOSED_COMMIT.json', C.encode({'submission': closed.submission,
            'lifecycle': closed.lifecycle, 'before_private_reference_load': True}), budget)
    try:
        files = bundle.decode(raw)
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError) as error:
        result = {'status': 'invalid_submission', 'reason': str(error)[:300], 'private_numeric_reference_loads': 0,
                  'submission_valid': False, 'scientific_success': None, 'full_paper_reproduction': False}
    else:
        captured = root / 'submission'; captured.mkdir(mode=0o700)
        pins = {name: C.write(captured / name, body, budget) for name, body in sorted(files.items())}
        C.write(root / 'OUTPUT_FILES_COMMIT.json', C.encode(pins), budget)
        def reference():
            return {name: C.read(request['references'][name]['path'],
                    locator(request['references'][name], S.CAPS[name]), budget, cap=S.CAPS[name]) for name in S.REQUIRED}
        result = numeric_score.grade(files, reference)
    result.update(task_id=ID, program_sha256=C.pin(program)['sha256'],
                  candidate_code_executed_by_grader=False, new_benchmark_ids=0)
    C.write(root / 'RESULT.json', C.encode(result), budget)
    return result
