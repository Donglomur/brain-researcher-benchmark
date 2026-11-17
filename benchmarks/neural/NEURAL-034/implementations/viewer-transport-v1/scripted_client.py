"""Complete transport control only: inspect all windows and return fixed 0.5.

This client consumes image bytes but performs no inference or scientific fitting.
The participant process is recreated for every held-mouse fold by the operator.
"""
import json
import struct
import sys

PREFIX = struct.Struct('!II')


def exact(size):
    result = bytearray()
    while len(result) < size:
        block = sys.stdin.buffer.read(size - len(result))
        if not block:
            raise EOFError('Incomplete operator frame')
        result.extend(block)
    return bytes(result)


def receive():
    hs, ps = PREFIX.unpack(exact(PREFIX.size))
    if not (0 < hs <= 32768 and 0 <= ps <= 4 * 1024**2):
        raise ValueError('Unbounded operator frame')
    return json.loads(exact(hs)), exact(ps)


def send(action):
    body = (json.dumps(action, separators=(',', ':'), allow_nan=False) + '\n').encode()
    if not 0 < len(body) <= 4096:
        raise ValueError('Unbounded client request')
    sys.stdout.buffer.write(PREFIX.pack(len(body), 0) + body)
    sys.stdout.buffer.flush()


def view(role, ordinal):
    send({'action': role, 'index': ordinal})
    header, png = receive()
    if (header.get('kind') != 'view' or header.get('role') != role or header.get('index') != ordinal
            or not png.startswith(b'\x89PNG\r\n\x1a\n')):
        raise ValueError('Expected the requested complete-window PNG frame')
    if header.get('samples') != 300 or header.get('cells') != 12:
        raise ValueError('Complete original observation geometry required')
    if role == 'training':
        if type(header.get('context_label')) is not int or header['context_label'] not in (0, 1):
            raise ValueError('Allowed training label missing')
    elif 'context_label' in header or not isinstance(header.get('query_id'), str):
        raise ValueError('Query must have its public identity and no target')
    return header


def main():
    ready, png = receive()
    if (ready.get('kind') != 'instructions' or png or ready.get('training_windows') != 120
            or ready.get('query_windows') != 20):
        raise ValueError('Complete active-fold instructions required')
    for ordinal in range(120):
        view('training', ordinal)
    for ordinal in range(20):
        observation = view('query', ordinal)
        # Fixed response is an I/O control, not an interpretation attempt.
        send({'action': 'respond', 'query_id': observation['query_id'], 'probability': 0.5})
        accepted, png = receive()
        if (accepted.get('kind') != 'response_accepted' or png
                or accepted.get('query_id') != observation['query_id']
                or accepted.get('completed_queries') != ordinal + 1):
            raise ValueError('Expected immutable unscored answer acknowledgment')
    send({'action': 'finish'})
    finished, png = receive()
    if finished.get('kind') != 'complete' or finished.get('queries') != 20 or png:
        raise ValueError('Complete active-fold acknowledgment required')


if __name__ == '__main__':
    main()
