"""Frozen NEURAL-034 grading inside the already owned completion controller group.

No extra session or candidate execution is introduced. Acceptance follows exact
created-ID cleanup; the outer owner repeats cleanup after the group is stopped.
"""
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import uuid

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
RUNTIME_PIN = {'bytes': 12696, 'sha256': '83413b3058da6a95cc6d9a41ffc8cb0cd7dd1dd4d9839d619bbbb197bf2e7636'}
_RUNTIME = None


def need(ok, message):
    if not ok:
        raise ValueError(message)


def runtime():
    global _RUNTIME
    if _RUNTIME is not None:
        return _RUNTIME
    path = HERE / 'grader_runtime.py'
    need(path == path.resolve() and path.is_file() and path.stat().st_nlink == 1,
         'Ordinary exact grader lifecycle source')
    body = path.read_bytes()
    need({'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()} == RUNTIME_PIN,
         'Pinned grader lifecycle source before loading')
    name = '_neural034_ordinary_completion_grade_runtime'
    need(name not in sys.modules, 'Fresh private grade bridge namespace')
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); sys.modules[name] = value
    exec(compile(body, str(path), 'exec'), value.__dict__)
    _RUNTIME = value
    return value


def grade(submission, out, budget):
    r = runtime(); out = Path(out); submission = Path(submission)
    need(out.is_absolute() and all(not p.is_symlink() for p in (out, *out.parents)) and not out.exists(),
         'Fresh literal grader output directory')
    budget.check(r.TOTAL_BYTES, receipt=True)
    out.mkdir(mode=0o700); run = out / 'operator'; run.mkdir(mode=0o700)
    held = r.scorer(); name = 'neural034-score-' + uuid.uuid4().hex[:16]
    r.write(run / 'outer_intent.json', {'container': name, 'same_shared_controller_group': True,
            'bridge_source': 'ordinary-completion-v1/grader/grade_bridge.py',
            'no_new_host_process_group': True, 'grader_retained_cap_bytes': r.TOTAL_BYTES})
    r.write(run / 'child_ownership.json', {'pid': os.getpid(), 'process_group': os.getpgrp(),
            'container': name, 'journal_before_child_resource_dispatch': True})
    held.run_child(submission, run, name)
    receipt = r.metadata(run / 'child_receipt.json'); cleanup = receipt['cleanup']
    created_id = r.ownership(run, name)
    need(receipt.get('created_id') == created_id and cleanup.get('immutable_id') == created_id
         and cleanup.get('absent') is True and cleanup.get('id_absent') is True
         and cleanup.get('name_absent') is True and cleanup.get('create_extent_unknown') is False,
         'Exact created grader ID and name absent before accepting result')
    need(receipt['status'] in ('scored', 'invalid_submission'), 'Grader completed or public rejection')
    invocation = r.metadata(run / 'invocation.json')
    need(invocation['submission'] == held.lock(submission, 100000),
         'Grader received exact committed aggregate')
    r.write(out / 'score.json', receipt['result'])
    return {'status': receipt['status'], 'container': name, 'immutable_id': created_id,
            'absence_verified': True, 'id_absent': True, 'name_absent': True,
            'score_sha256': held.lock(out / 'score.json')['sha256'],
            'submission_sha256': invocation['submission']['sha256'],
            'private_targets_decoded': receipt['result']['private_targets_decoded'],
            'same_shared_controller_group': True, 'no_new_host_process_group': True}


def recover_grade(out, end):
    """Call only after the owner has stopped/reaped the controller group."""
    r = runtime(); out = Path(out); run = out / 'operator'
    if not out.exists():
        return {'not_dispatched': True, 'absence_verified': True, 'grade_directory_absent': True}
    result = {'absence_verified': False, 'create_extent_unknown': True}
    try:
        need(out.is_absolute() and all(not p.is_symlink() for p in (out, *out.parents)),
             'Literal grader recovery root')
        intent = r.metadata(run / 'outer_intent.json'); name = intent['container']; r.valid_name(name)
        result['container'] = name
        # Only a completed trusted pre-dispatch receipt can close the no-create
        # branch. Missing/torn ownership, attempt or return journals never do.
        if not any((run / item).exists() for item in ('ownership.json', 'create_attempt.json', 'create_result.json')):
            receipt = r.metadata(run / 'child_receipt.json')
            need(receipt.get('container') == name and receipt.get('status') == 'operator_error'
                 and receipt.get('cleanup') == {'absent': True, 'resource_create_not_dispatched': True},
                 'Explicit completed no-dispatch grader receipt')
            return {'not_dispatched': True, 'absence_verified': True, 'container': name,
                    'completed_precreate_failure': True}
        evidence = r.cleanup(run, name, end)
        result.update(absence_verified=evidence['absence_verified'],
                      create_extent_unknown=evidence['create_extent_unknown'], evidence=evidence)
    except Exception as error:
        result['recovery_error'] = repr(error)[:2000]
    return result
