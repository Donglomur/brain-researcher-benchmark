"""Trusted SMC controller, entered only through the durable task owner barrier."""
from pathlib import Path
import argparse
import os
import socket
import sys
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import Channel, body, need, pin, read
import legacy
import owned_episode
import process_owner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--invocation', type=Path, required=True)
    parser.add_argument('--invocation-sha256', required=True)
    parser.add_argument('--channel-fd', type=int, required=True)
    args = parser.parse_args()
    raw = body(args.invocation)
    invocation_pin = pin(raw)
    need(invocation_pin['sha256'] == args.invocation_sha256, 'Exact launched invocation')
    invocation = read(args.invocation, invocation_pin)
    owner, _ = process_owner.expected(args.invocation.parent / 'process')
    source = legacy.source_identity()
    need(owner['child_argv'] == [sys.executable, '-I', '-B', *sys.argv]
         and os.getppid() == owner['pid'] and os.getpgrp() == owner['pgid']
         and owner['grant']['invocation_pin'] == invocation_pin
         and {k: owner['grant'][k] for k in invocation['clock']} == invocation['clock']
         and invocation['source'] == source, 'Actual owned invocation and exact frozen source')
    need(process_owner.clock_identity() == invocation['clock']['clock_identity'],
         'Same boot retains monotonic clock')
    with socket.socket(fileno=args.channel_fd) as sock:
        channel = Channel(sock, invocation_pin, invocation['clock']['controller_deadline'])
        channel('CONTROLLER-READY', {'pid': os.getpid(), 'parent_pid': os.getppid(),
            'pgid': os.getpgrp(), 'owner_token': owner['token'],
            'clock_identity': invocation['clock']['clock_identity'], 'source': source})
        owned_episode.execute(invocation, invocation_pin, source, channel, legacy.load())


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        print(type(exc).__name__, file=sys.stderr)
        raise SystemExit(1)
