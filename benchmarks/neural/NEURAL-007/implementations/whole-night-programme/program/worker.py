"""Isolated numerical producer entry point. Never run during construction.

The host gives this worker only the exact phase mounts. Candidate Python is a
separate bounded process; reference code is a distinct operator-only action.
"""
from pathlib import Path
import hashlib
import json
import os
import selectors
import signal
import subprocess
import sys
import time
from .common import capture, decode, encoded, need, pin, publish, relative


def run_child(argv, end, stdout_cap=65536, stderr_cap=65536):
    need(time.monotonic() < end, 'Original worker deadline')
    p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, start_new_session=True, close_fds=True,
                         env={'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/work', 'TMPDIR': '/work',
                              'PYTHONDONTWRITEBYTECODE': '1', 'OPENBLAS_NUM_THREADS': '1',
                              'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'NUMEXPR_NUM_THREADS': '1'})
    selector = selectors.DefaultSelector(); output = {'stdout': bytearray(), 'stderr': bytearray()}
    selector.register(p.stdout, selectors.EVENT_READ, 'stdout'); selector.register(p.stderr, selectors.EVENT_READ, 'stderr')
    caps = {'stdout': stdout_cap, 'stderr': stderr_cap}
    try:
        while selector.get_map():
            need(time.monotonic() < end, 'Child deadline cannot renew')
            for event, _ in selector.select(min(.05, max(0, end - time.monotonic()))):
                name = event.data; b = os.read(event.fileobj.fileno(), 4096)
                if not b:
                    selector.unregister(event.fileobj); event.fileobj.close(); continue
                need(len(output[name]) + len(b) <= caps[name], 'Complete child stream byte ceiling, no truncation')
                output[name].extend(b)
        need(p.wait(timeout=max(.001, end - time.monotonic())) == 0, 'Natural successful child exit')
        # A daemon surviving the child leader invalidates completion, even when
        # the outer container would eventually kill it during retirement.
        try:
            os.killpg(p.pid, 0)
        except ProcessLookupError:
            pass
        else:
            raise ValueError('Candidate process group remains after leader exit')
        return {k: bytes(v) for k, v in output.items()}
    finally:
        selector.close()
        try: os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        p.wait(timeout=2)
        for f in (p.stdout, p.stderr):
            if not f.closed: f.close()


def inventory(root, excluded=()):
    result = {}
    for path in sorted(root.rglob('*')):
        need(not path.is_symlink(), 'No output links')
        if path.is_dir(): continue
        name = relative(path.relative_to(root).as_posix())
        if name in excluded: continue
        st = path.stat(); need(st.st_nlink == 1 and path.is_file(), 'Ordinary output member')
        h = hashlib.sha256()
        with path.open('rb') as f:
            for b in iter(lambda: f.read(65536), b''): h.update(b)
        result[name] = {'bytes': st.st_size, 'sha256': h.hexdigest()}
    return result


def main():
    request_raw = capture('/request.json'); request = decode(request_raw)
    job = decode(capture('/job.json')); output = Path('/output')
    need(job['schema'] == 'neural007_worker_job_v1', 'Exact worker job')
    end = min(request['clock']['phase_deadline'] - request['resources']['capture_seconds'] - request['resources']['cleanup_seconds'],
              time.monotonic() + request['resources']['producer_seconds'])
    action = job['action']
    if action in ('probe', 'policy', 'fit', 'infer'):
        # Fixed script ABI: --view contains only permitted inputs; --output is
        # the sole export root. Recipe/history/model are separately mounted.
        argv = ['/usr/local/bin/python', '-I', '-B', '/candidate/main.py',
                '--view', '/view/VIEW.json', '--output', '/output/artifacts']
        for key in ('recipe', 'history', 'model'):
            if key in job: argv += ['--' + key, '/' + key]
        (output / 'artifacts').mkdir()
        streams = run_child(argv, end)
        for name, body in streams.items(): publish(output / (name.upper() + '.txt'), body)
        if action == 'probe':
            observation = decode(capture(output / 'artifacts' / 'OBSERVATION.json', cap=65536))
            need(type(observation) is dict, 'Complete JSON probe observation')
        elif action == 'policy':
            decode(capture(output / 'artifacts' / 'ACTION.json', cap=1048576))
        elif action == 'fit':
            need(inventory(output / 'artifacts'), 'Nonempty sealed final model')
        else:
            manifest = decode(capture(output / 'artifacts' / 'PREDICTIONS.json'))
            need(manifest['schema'] == 'neural007_predictions_v1', 'Candidate prediction envelope')
    else:
        from . import references as ref
        import numpy as np
        view = decode(capture('/view/VIEW.json')); rows = [{**r, 'root': str(Path('/view') / r['directory'])} for r in view['nights']]
        if job.get('cache'):
            rows = [{**r, 'cache': str(Path('/cache') / r['directory'])} for r in rows]
        if action == 'reference_cache':
            need(len(rows) == 1, 'One full-night cache producer')
            ref.cache_night(rows[0], rows[0]['root'], output / 'cache')
        elif action == 'reference_fit':
            import pickle
            state = ref.fit(rows, job['family'], view['view'], job.get('parameter'), job.get('association_control', False))
            with (output / 'MODEL.pkl').open('xb') as f: pickle.dump(state, f, protocol=5)
        elif action == 'reference_infer':
            import pickle
            with open('/model/MODEL.pkl', 'rb') as f: state = pickle.load(f)
            result = []
            for i, row in enumerate(rows):
                p = ref.predict(state, row, job.get('shifted', False), job.get('power'), job.get('alpha'))
                name = f'probabilities-{i}.npy'; np.save(output / name, p, allow_pickle=False)
                result.append({'person': row['person'], 'night': row['night'], 'epochs': row['epochs'], 'path': name})
            publish(output / 'PREDICTIONS.json', encoded({'schema': 'neural007_predictions_v1', 'nights': result}))
        else:
            raise ValueError('Unknown concrete worker action')
    finish_output(request_raw, request, output, end)

def finish_output(request_raw, request, output, end):
    need(time.monotonic() < end, 'Producer completed inside original clock')
    publish(output / 'RESULT.json', encoded({'schema': 'neural007_trusted_worker_completion_v1',
            'phase_id': request['phase_id'], 'request_sha256': pin(request_raw)['sha256'],
            'producer_completed': True, 'scientific_qualification': False}))
    files = inventory(output, ('OUTPUTS.json',))
    publish(output / 'OUTPUTS.json', encoded({'schema': 'osl_transport_output_manifest_v1',
            'phase_id': request['phase_id'], 'request_sha256': pin(request_raw)['sha256'], 'files': files}))


if __name__ == '__main__': main()
