"""Full-panel candidate entry; actual-use reporting is captured after execution.

Unchanged retained helpers install the release barrier and native limits. The
candidate's actual-use declaration is a claim, not proof of its internal method.
"""
import hashlib
import importlib.util
import os
from pathlib import Path
import resource
import runpy
import sys

RETAINED = Path('/runner/retained_worker.py')
RETAINED_SHA = '2fc10bb2b608e7f1e4a803588cff1123add5aa7c6fbb92eb6b22cea028a9b473'
INFERENCE_CONDITION = 'full_panel_offline_transductive_v1'


def retained():
    raw = RETAINED.read_bytes()
    if len(raw) != 11424 or hashlib.sha256(raw).hexdigest() != RETAINED_SHA:
        raise ValueError('Exact source-bound retained worker helpers')
    spec = importlib.util.spec_from_file_location('_smc_full_panel_worker_helpers', RETAINED)
    module = importlib.util.module_from_spec(spec)
    exec(compile(raw, str(RETAINED), 'exec'), module.__dict__)
    return module


def main():
    if sys.argv[1:] not in ([], ['--release']):
        raise ValueError('Fixed entry or trusted release helper only')
    old = retained()
    spec, request_raw, request = old.authenticated_inputs()
    if (spec.get('inference_condition_id') != INFERENCE_CONDITION or spec['outcome'] != 'improvement'
            or not isinstance(spec.get('method_freeze_sha256'), str)
            or len(spec['method_freeze_sha256']) != 64
            or any(c not in '0123456789abcdef' for c in spec['method_freeze_sha256'])):
        raise ValueError('New method-frozen improvement condition required')
    if sys.argv[1:] == ['--release']:
        return old.release(spec, request_raw, request)
    cpu = 7200
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    if resource.getrlimit(resource.RLIMIT_CPU) != (cpu, cpu):
        raise ValueError('Hard process CPU limit installed before scientific imports')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'OMP_THREAD_LIMIT', 'MKL_NUM_THREADS',
                'NUMBA_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
        os.environ[key] = '6'
    if old.READY.exists() or old.RELEASE.exists():
        raise ValueError('Fresh worker handshake only')
    old.publish_marker(old.READY, old.marker(request_raw, request, 'ready'), request)
    old.wait_marker(old.RELEASE, old.marker(request_raw, request, 'release'), request)
    old.before_deadline(request)
    import site
    site.main()
    sys.argv = ['/program/program.py', '--input', '/materials', '--out', '/output',
                '--outcome', 'improvement', '--declaration', '/declaration.json',
                '--selected-artifacts', '/selected_artifacts']
    try:
        old.before_deadline(request)
        runpy.run_path('/program/program.py', run_name='__main__')
    except SystemExit as exc:
        if exc.code not in (None, 0):
            raise
    root = Path('/output')
    if {p.name for p in root.iterdir()} != {'offline.h5', 'actual_declaration.json'}:
        raise ValueError('Complete predictions and separate post-run actual-use declaration only')
    files = {name: old.pin_file(root / name, 1024**2 if name == 'actual_declaration.json' else spec['max_file_bytes'])
             for name in ('offline.h5', 'actual_declaration.json')}
    _, actual = old.metadata(root / 'actual_declaration.json')
    if (actual.get('schema') != 'smc_full_panel_actual_use_v1'
            or actual.get('inference_condition_id') != INFERENCE_CONDITION
            or actual.get('condition') != spec['condition']
            or actual.get('source_sha256') != spec['program_sha256']
            or actual.get('method_freeze_sha256') != spec['method_freeze_sha256']):
        raise ValueError('Post-run report must join the actually selected frozen method')
    old.before_deadline(request)
    result = old.encode({'schema': 'smc_full_panel_program_result_v1',
        'inference_condition_id': INFERENCE_CONDITION, 'outcome': 'improvement',
        'condition': spec['condition'], 'program_sha256': spec['program_sha256'],
        'declaration_sha256': spec['declaration_sha256'], 'method_freeze_sha256': spec['method_freeze_sha256'],
        'submission_keys': ['offline']})
    with (root / 'RESULT.json').open('xb') as handle:
        handle.write(result)
    files['RESULT.json'] = {'bytes': len(result), 'sha256': hashlib.sha256(result).hexdigest()}
    with (root / 'OUTPUTS.json').open('xb') as handle:
        handle.write(old.encode({'schema': 'osl_transport_output_manifest_v1', 'phase_id': request['phase_id'],
            'request_sha256': hashlib.sha256(request_raw).hexdigest(), 'files': files}))


if __name__ == '__main__':
    main()
