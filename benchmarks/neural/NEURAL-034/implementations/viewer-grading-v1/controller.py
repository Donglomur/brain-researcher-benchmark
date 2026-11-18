"""One existing protected grade in an independently owned viewer-grade group.

The caller authenticates source, authority and the closed viewer collection.
This controller creates no process group and performs no outer recovery. Its
owner must stop/reap the group before calling the existing recover_grade API.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).absolute().parent
sys.path.insert(0, str(HERE))
import run as shared


def need(value, message):
    if not value:
        raise ValueError(message)


def execute(api, request, out, *, pid=None, pgid=None, argv=None):
    """Use only the admitted snapshot and actual original-owner identity.

    Explicit process values permit generated controls. The CLI never supplies
    them; production obtains all three directly from this running process.
    """
    out = Path(out)
    need(out.is_absolute() and '..' not in out.parts and
         request['output_root'] == str(out), 'Exact admitted output root')
    need(request['schema'] == 'neural034-viewer-grading-request/v1', 'Viewer grading request')
    pid = os.getpid() if pid is None else pid
    pgid = os.getpgrp() if pgid is None else pgid
    argv = [sys.executable, *sys.argv] if argv is None else argv
    owner, unused = api.owner.expected(out)
    need(type(pid) is int and pid > 1 and type(pgid) is int and pgid > 1 and
         pid != owner['pid'] and pgid == owner['pgid'] == owner['pid'],
         'Controller is a child in the exact owned group')
    need(type(owner['token']) is str and re.fullmatch('[0-9a-f]{32}', owner['token']),
         'Exact owner activation token')
    need(type(argv) is list and owner['child_argv'] == request['controller_argv'] == argv and
         owner['controller'] == request['controller'], 'Exact activated controller source and argv')
    need(type(owner['seconds']) in (int, float) and math.isfinite(owner['seconds']) and
         owner['seconds'] == request['stage_seconds'] - 5, 'Exact admitted owner lifetime')
    # Recheck the immutable snapshot immediately before any grading intent.
    shared.validate_snapshot(request, out)
    budget = shared.make_budget(api, out, request)
    grade_path = out / 'grader'
    need(not grade_path.exists(), 'Fresh one-shot protected grade directory')
    result = {
        'schema': 'neural034-viewer-grading-controller/v1',
        'status': 'execution_failed_preserved',
        'request': request['request_pin'],
        'controller': request['controller'],
        'owner_token': owner['token'],
        'pid': pid,
        'pgid': pgid,
        'snapshot': request['snapshot'],
        'collection_authority': request['collection_authority'],
        'grade_attempted': False,
        'grade': None,
        'returncode': 2,
        'error': None,
    }
    try:
        shared.write(out / 'grade_attempted.json', {
            'schema': 'neural034-viewer-grade-intent/v1',
            'request': request['request_pin'],
            'controller': request['controller'],
            'owner_token': owner['token'],
            'snapshot': request['snapshot'],
            'grade_output': str(grade_path),
        }, budget)
        result['grade_attempted'] = True
        result['grade'] = api.grader.grade(out / request['snapshot']['path'], grade_path, budget)
        need(result['grade']['status'] == 'scored', 'Complete protected numerical score required')
        need(result['grade']['absence_verified'] is True and
             result['grade']['id_absent'] is True and result['grade']['name_absent'] is True,
             'Normal grader cleanup must verify ID and name absence')
        need(result['grade']['submission_sha256'] == request['snapshot']['sha256'],
             'Protected grade binds the admitted viewer snapshot')
        result.update(status='scored', returncode=0)
    except BaseException as error:
        result['error'] = type(error).__name__ + ': ' + str(error)[:2048]
    # A failed durable result write is itself a controller failure. Do not print
    # success or suppress it; the outer owner still closes its retained group.
    shared.write(out / 'controller-result.json', result, budget)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True)
    parser.add_argument('--request-sha256', required=True)
    args = parser.parse_args()
    request, api = shared.load_context(args.request, args.request_sha256)
    result = execute(api, request, Path(request['output_root']))
    body = shared.capture(Path(request['output_root']) / 'controller-result.json')
    print(json.dumps({'status': result['status'], 'returncode': result['returncode'],
                      'controller_result': shared.pin(body)}, sort_keys=True, allow_nan=False), flush=True)
    return result['returncode']


if __name__ == '__main__':
    raise SystemExit(main())
