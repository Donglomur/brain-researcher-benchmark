"""Fixed zero trajectories for transport qualification, not a scientific model.

Self-contained pipe participant: no operator module, input files, targets, model
API or scoring. This file does not prove that arbitrary local clients are isolated.
"""
import argparse
import json
import struct
import sys

MAX_RESPONSE = 512 * 1024


def read_exact(size):
    out = bytearray()
    while len(out) < size:
        block = sys.stdin.buffer.read(size - len(out))
        if not block:
            raise ValueError('unexpected operator EOF')
        out.extend(block)
    return bytes(out)


def receive():
    size = struct.unpack('!I', read_exact(4))[0]
    if not 0 < size <= MAX_RESPONSE:
        raise ValueError('operator frame size')
    return json.loads(read_exact(size).decode())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--calibration', choices=('all', 'none'), default='all')
    parser.add_argument('--crop-first', action='store_true')
    args = parser.parse_args(argv)
    hello = receive()
    if (hello.get('schema') != 'neural021_participant_messages_v1'
            or hello.get('calibration_count') != 272 or len(hello.get('queries', [])) != 92
            or hello.get('response_shape') != [30, 2]):
        raise ValueError('complete declared task required')
    sequence = 0
    def request(operation, **fields):
        nonlocal sequence
        body = (json.dumps({'seq': sequence, 'op': operation, **fields},
                          sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
        if len(body) > 8192:
            raise ValueError('client request cap')
        sys.stdout.buffer.write(struct.pack('!I', len(body)) + body)
        sys.stdout.buffer.flush()
        answer = receive()
        if answer.get('seq') != sequence:
            raise ValueError('response sequence')
        sequence += 1
        return answer
    if args.calibration == 'all':
        for index in range(272):
            if request('calibration', index=index).get('type') != 'svg':
                raise ValueError('calibration response')
    for index, row in enumerate(hello['queries']):
        key = row['trial_id']
        if request('view', trial_id=key).get('type') != 'svg':
            raise ValueError('query response')
        if index == 0 and args.crop_first and hello['mode'] == 'typed_viewer':
            request('crop', trial_id=key, unit_start=0, unit_stop=5, bin_start=0, bin_stop=6)
        if request('answer', trial_id=key, velocity_m_s=[[0.0, 0.0] for _ in range(30)]).get('accepted') is not True:
            raise ValueError('answer acknowledgment')
    if request('finish').get('type') != 'complete':
        raise ValueError('completion acknowledgment')
    if sys.stdin.buffer.read(1):
        raise ValueError('unexpected post-completion operator bytes')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
