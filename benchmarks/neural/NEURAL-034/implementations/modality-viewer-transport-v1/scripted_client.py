"""Same fixed0.5 image-consuming control for all three modality conditions.

This is a transport test client, not an inference method or scientific score.
"""
import json
import struct
import sys

PREFIX = struct.Struct('!II')
CONDITIONS = {'combined_calcium_behavior_v1': ['calcium', 'behavior'],
              'calcium_only_v1': ['calcium'], 'behavior_only_v1': ['behavior']}


def exact(size):
    result = bytearray()
    while len(result) < size:
        block = sys.stdin.buffer.read(size - len(result))
        if not block:
            raise EOFError('Incomplete operator frame')
        result.extend(block)
    return bytes(result)


def receive():
    hs, ps = PREFIX.unpack(exact(8))
    if not (0 < hs <= 32768 and 0 <= ps <= 4 * 1024**2):
        raise ValueError('Unbounded operator frame')
    return json.loads(exact(hs)), exact(ps)


def send(action):
    body = (json.dumps(action, separators=(',', ':'), allow_nan=False) + '\n').encode()
    if not 0 < len(body) <= 4096:
        raise ValueError('Unbounded request')
    sys.stdout.buffer.write(PREFIX.pack(len(body), 0) + body)
    sys.stdout.buffer.flush()


def bind(header, condition):
    if header.get('condition') != condition or header.get('visible_modalities') != CONDITIONS[condition]:
        raise ValueError('Changed condition or modality permissions')


def view(role, index, condition):
    send({'action': role, 'index': index})
    header, png = receive()
    bind(header, condition)
    cells = 0 if condition == 'behavior_only_v1' else 12
    mode = 'active_fold_calcium_behavior_viewer' if condition == 'combined_calcium_behavior_v1' else 'active_fold_' + condition
    fields = {'kind', 'condition', 'visible_modalities', 'mode', 'role', 'index', 'gain_units_per_division',
              'clipped_cells', 'samples', 'cells', 'sample_rate_hz', 'window_seconds', 'first_sample_seconds',
              'last_sample_seconds', 'image'} | ({'context_label'} if role == 'training' else {'query_id'})
    if (set(header) != fields or header['kind'] != 'view' or header['role'] != role or header['index'] != index
            or header['mode'] != mode or header['samples'] != 300 or header['cells'] != cells
            or header['sample_rate_hz'] != 10 or header['window_seconds'] != 30
            or header['first_sample_seconds'] != 0.05 or header['last_sample_seconds'] != 29.95
            or not png.startswith(b'\x89PNG\r\n\x1a\n')
            or header['image'] != {'mime_type': 'image/png', 'bytes': len(png)}):
        raise ValueError('Expected exact requested observation projection')
    if condition == 'behavior_only_v1' and header['clipped_cells']:
        raise ValueError('Excluded calcium statistics')
    if role == 'training' and (type(header['context_label']) is not int or header['context_label'] not in (0, 1)):
        raise ValueError('Allowed training label missing')
    return header


def main():
    ready, png = receive()
    condition = ready.get('condition')
    if condition not in CONDITIONS:
        raise ValueError('Unknown condition')
    bind(ready, condition)
    if ready.get('kind') != 'instructions' or png or (ready.get('training_windows'), ready.get('query_windows')) != (120, 20):
        raise ValueError('Incomplete active-fold instructions')
    for index in range(120):
        view('training', index, condition)
    for index in range(20):
        observation = view('query', index, condition)
        send({'action': 'respond', 'query_id': observation['query_id'], 'probability': 0.5})
        accepted, png = receive()
        bind(accepted, condition)
        if accepted.get('kind') != 'response_accepted' or png or accepted.get('query_id') != observation['query_id'] or accepted.get('completed_queries') != index + 1:
            raise ValueError('Immutable unscored answer acknowledgment required')
    send({'action': 'finish'})
    finished, png = receive()
    bind(finished, condition)
    if finished.get('kind') != 'complete' or finished.get('queries') != 20 or png:
        raise ValueError('Complete active-fold acknowledgment required')


if __name__ == '__main__':
    main()
