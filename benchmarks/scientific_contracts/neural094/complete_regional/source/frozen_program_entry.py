"""Fixed capsule adapter; invoked only inside the isolated candidate container.

The original candidate fit/infer executable body is unchanged. This adapter
never calls the model tool; global authoring is charged by the trusted policy.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def _run(public, phase):
    cfg = public['payload']
    program = Path('/capsule/program.py')
    sha = hashlib.sha256(program.read_bytes()).hexdigest()
    if sha != cfg['program_sha256']:
        raise ValueError('Frozen program identity changed')
    output = '/output/model.bin' if phase == 'fit' else '/output/legacy_predictions.json'
    packet = '/training/MANIFEST.json' if phase == 'fit' else '/query/MANIFEST.json'
    command = [sys.executable, '-I', '-B', str(program), phase, '--packet', packet, '--output', output]
    if phase == 'infer':
        command += ['--model', '/fit/model.bin', '--candidate-sha256', sha]
    # These are isolated-container child processes. No host command facility or
    # URL is exposed. Outer process ownership bounds the entire container.
    result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=sys.stderr, stderr=sys.stderr,
                            timeout=cfg['program_seconds'], check=False)
    if result.returncode != 0:
        raise ValueError('Frozen numerical program failed')
    return Path(output)


def train(public, tools):
    _run(public, 'fit')
    return {'fit_files': ['model.bin']}


def predict(public, tools):
    path = _run(public, 'infer')
    cap = public['payload']['prediction_bytes']
    if type(cap) is not int or cap <= 0 or path.stat().st_size > cap:
        raise ValueError('Prediction artifact cap')
    value = json.loads(path.read_bytes())
    if (value['schema'] != 'neural094-candidate-predictions-v1'
            or value['candidate_sha256'] != public['payload']['program_sha256']
            or value['class_order'] != ['right', 'NoGo', 'left']):
        raise ValueError('Original prediction identity')
    return value['predictions']
