"""Trusted reference worker; reuse unchanged custody markers and release helper."""
import hashlib
import importlib.util
import os
from pathlib import Path
import resource
import runpy
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reference_core import ACCESS, ARMS, OUTCOME, PHASES, ROUTE, need, validate_profile

RETAINED = Path('/runner/retained_worker.py')
RETAINED_SHA = '2fc10bb2b608e7f1e4a803588cff1123add5aa7c6fbb92eb6b22cea028a9b473'


def retained():
    raw = RETAINED.read_bytes()
    need(len(raw) == 11424 and hashlib.sha256(raw).hexdigest() == RETAINED_SHA,
         'Exact original custody/release helper')
    spec = importlib.util.spec_from_file_location('_smc_reference_retained_worker', RETAINED)
    module = importlib.util.module_from_spec(spec)
    exec(compile(raw, str(RETAINED), 'exec'), module.__dict__)
    return module


def authenticated(old):
    _, job = old.metadata(old.JOB)
    request_raw, request = old.metadata(old.REQUEST)
    need(request_raw == old.compact(request), 'Exact retained wire encoding')
    need(job['schema'] == 'smc_author_reference_execution_job_v2' and job['route'] == ROUTE
         and job['outcome'] == OUTCOME and job['access_condition'] == ACCESS
         and job['condition'] == job['phase_id'] in PHASES
         and request['phase_id'] == job['phase_id'] and request['role'] == 'B'
         and request['schema'] == 'smc_aggregate_phase_request_v1'
         and request['source'] == job['source'], 'Reference model arm with genuine assisted B exposure')
    profile = validate_profile(job['resource_profile'])
    need(all(type(request['resources'][key]) is int for key in
             ('cpu_seconds', 'producer_seconds', 'memory_bytes', 'cpu_nanos', 'pids'))
         and job['submission_keys'] == ['offline']
         and request['resources']['cpu_seconds'] == profile['cpu_seconds']
         and request['resources']['producer_seconds'] == profile['wall_seconds']
         and request['resources']['memory_bytes'] == profile['memory_bytes']
         and request['resources']['cpu_nanos'] == 6000000000
         and type(request['resources']['pids']) is int and request['resources']['pids'] > 0,
         'Unchanged reference producer resources and complete output')
    old.before_deadline(request)
    return job, request_raw, request


def main():
    need(sys.argv[1:] in ([], ['--release']), 'Fixed trusted worker or owned release only')
    old = retained()
    job, raw, request = authenticated(old)
    if sys.argv[1:] == ['--release']:
        return old.release(job, raw, request)
    profile = validate_profile(job['resource_profile'])
    resource.setrlimit(resource.RLIMIT_CPU, (profile['cpu_seconds'], profile['cpu_seconds']))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'OMP_THREAD_LIMIT',
                'MKL_NUM_THREADS', 'NUMBA_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
        os.environ[key] = '6'
    need(not old.READY.exists() and not old.RELEASE.exists(), 'Fresh owned worker handshake')
    old.publish_marker(old.READY, old.marker(raw, request, 'ready'), request)
    old.wait_marker(old.RELEASE, old.marker(raw, request, 'release'), request)
    old.before_deadline(request)
    import site
    site.main()
    sys.argv = ['/program/program.py', '--input', '/materials', '--out', '/output',
                '--outcome', OUTCOME, '--declaration', '/declaration.json',
                '--selected-artifacts', '/selected_artifacts']
    try:
        runpy.run_path('/program/program.py', run_name='__main__')
    except SystemExit as exc:
        if exc.code not in (None, 0):
            raise
    old.before_deadline(request)
    root = Path('/output')
    need({p.name for p in root.iterdir()} == {'offline.h5', 'actual_declaration.json'},
         'Exact original predictions and reference actual-use evidence')
    files = {name: old.pin_file(root / name, 1024**2 if name == 'actual_declaration.json'
             else job['max_file_bytes']) for name in ('offline.h5', 'actual_declaration.json')}
    _, actual = old.metadata(root / 'actual_declaration.json')
    need(actual['schema'] == 'smc_author_reference_actual_v2' and actual['route'] == ROUTE
         and actual['phase_id'] == job['phase_id'] and actual['access_condition'] == ACCESS
         and validate_profile(actual['resource_profile']) == profile
         and actual['role'] == 'author_calibration'
         and actual['program_sha256'] == job['program_sha256']
         and actual['method_freeze_sha256'] == job['method_freeze_sha256'],
         'Reference output joins actually selected method')
    result = {'schema': 'smc_author_reference_program_result_v2', 'route': ROUTE,
              'phase_id': job['phase_id'], 'access_condition': ACCESS, 'outcome': OUTCOME,
              'resource_profile': profile,
              'program_sha256': job['program_sha256'], 'declaration_sha256': job['declaration_sha256'],
              'method_freeze_sha256': job['method_freeze_sha256'], 'submission_keys': ['offline']}
    result_raw = old.encode(result)
    with (root / 'RESULT.json').open('xb') as stream:
        stream.write(result_raw)
    files['RESULT.json'] = {'bytes': len(result_raw), 'sha256': hashlib.sha256(result_raw).hexdigest()}
    with (root / 'OUTPUTS.json').open('xb') as stream:
        stream.write(old.encode({'schema': 'osl_transport_output_manifest_v1',
            'phase_id': request['phase_id'], 'request_sha256': hashlib.sha256(raw).hexdigest(), 'files': files}))


if __name__ == '__main__':
    main()
