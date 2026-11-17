"""Protocol example only: consumes every generated/delivered view and replies uniformly."""
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
    sys.stdout.buffer.write(PREFIX.pack(len(body), 0) + body)
    sys.stdout.buffer.flush()


def main():
    ready, png = receive()
    if ready['kind'] != 'instructions' or png:
        raise ValueError('Expected instructions without a preselected observation')
    for ordinal in range(ready['epochs']):
        send({'action': 'epoch', 'index': ordinal})
        view, png = receive()
        if view['kind'] != 'view' or not png.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('Expected raw PNG image frame')
        # A provider bridge must attach these bytes as image content. This fixed
        # control neither calls a model nor claims to understand the waveform.
        send({'action': 'respond', 'epoch_id': view['epoch_id'], 'probabilities': [0.2] * 5})
        response, png = receive()
        if response['kind'] != 'response_accepted' or png:
            raise ValueError('Expected unscored response acknowledgment')
    send({'action': 'finish'})
    finished, png = receive()
    if finished['kind'] != 'complete' or png:
        raise ValueError('Complete person acknowledgment required')


if __name__ == '__main__':
    main()
