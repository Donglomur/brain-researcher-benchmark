"""One framed image prediction through the versioned, source-pinned CLI.

Only the declared source, frozen four-demo model and current PNG are readable
in the production sandbox. The wrapper adds framing, never changes the method.
"""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import types

ALGORITHM = {'bytes': 16220, 'sha256': 'c4024cbc5cd2283f1246ff2c99008a212a70689de9e3d410d7ff7f4a49e5cf64'}
PROFILE = 'neural077-initial-cz-pz-gain20-v1'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def capture(row, cap):
    need(set(row) == {'path', 'file'} and Path(row['path']).is_absolute(), 'Exact operand')
    with Path(row['path']).open('rb') as stream:
        body = stream.read(cap + 1)
    need(0 < len(body) <= cap and pin(body) == row['file'], 'Frozen operand changed')
    return body


def unique(items):
    value = {}
    for key, item in items:
        need(key not in value, 'Duplicate JSON field')
        value[key] = item
    return value


def run():
    header = sys.stdin.buffer.read(4)
    need(len(header) == 4, 'Complete frame header')
    size = struct.unpack('>I', header)[0]
    need(0 < size <= 16384, 'Bounded input frame')
    body = sys.stdin.buffer.read(size)
    need(len(body) == size and not sys.stdin.buffer.read(1), 'One complete input frame')
    value = json.loads(body, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    need(set(value) == {'schema', 'trial_id', 'profile', 'algorithm', 'model', 'image'} and
         value['schema'] == 'erp-full32-image-uncertainty-input-v1' and value['profile'] == PROFILE and
         value['algorithm']['file'] == ALGORITHM, 'Exact fixed image programme')
    source = capture(value['algorithm'], 65536)
    model = capture(value['model'], 65536)
    module = types.ModuleType('image_uncertainty_reference')
    module.__file__ = value['algorithm']['path']
    exec(compile(source, module.__file__, 'exec'), module.__dict__)
    module.validate_model(module.json_no_duplicates(model))
    image = capture(value['image'], 65536)
    # Use precisely the supplied CLI, including its model-before-query checks.
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = module.main(['predict', '--profile', PROFILE, '--model', value['model']['path'],
            '--model-sha256', value['model']['file']['sha256'], '--query', value['image']['path'],
            '--trial-id', value['trial_id']])
    need(code == 0, 'Uncertainty reference refused invalid input')
    for row, expected, cap in ((value['algorithm'], source, 65536),
                               (value['model'], model, 65536), (value['image'], image, 65536)):
        need(capture(row, cap) == expected, 'Operand changed during prediction')
    response = output.getvalue().encode('utf-8')
    need(0 < len(response) <= 4096, 'One bounded CLI response')
    sys.stdout.buffer.write(struct.pack('>I', len(response)) + response)
    sys.stdout.buffer.flush()


if __name__ == '__main__':
    try:
        run()
    except Exception as error:
        print('image_reference_failed: ' + type(error).__name__ + ': ' + str(error), file=sys.stderr)
        raise SystemExit(2)
