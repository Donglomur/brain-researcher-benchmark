"""Mechanical protocol control, not a solver: consumes PNG and always submits 0.5.

Provider bridges may reuse this framing. A real bridge must turn PNG bytes into
image content, disable other tools, supply fresh context, and capture provider
requests/results. This script does none of those provider-specific operations.
"""
import json
import struct
import sys

PREFIX = struct.Struct('!II')


def read_exact(size):
    result = bytearray()
    while len(result) < size:
        part = sys.stdin.buffer.read(size - len(result))
        if not part:
            raise EOFError('Closed transport')
        result.extend(part)
    return bytes(result)


def receive():
    header_bytes, image_bytes = PREFIX.unpack(read_exact(PREFIX.size))
    if not 0 < header_bytes <= 32768 or image_bytes > 4 * 1024 * 1024:
        raise ValueError('Frame bound')
    header = json.loads(read_exact(header_bytes))
    image = read_exact(image_bytes)
    if image and not image.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('PNG required')
    return header, image


def send(action):
    body = json.dumps(action, separators=(',', ':'), allow_nan=False).encode()
    sys.stdout.buffer.write(PREFIX.pack(len(body), 0) + body)
    sys.stdout.buffer.flush()


def control():
    ready, image = receive()
    if ready['status'] != 'ready' or not image:
        raise ValueError('Initial authentic image required')
    send({'action': 'finalize', 'response': json.dumps({'trial_id': ready['trial_id'], 'target_probability': 0.5})})
    terminal, image = receive()
    if terminal['status'] != 'valid_unscored' or image:
        raise ValueError('Terminal receipt required')


if __name__ == '__main__':
    control()
