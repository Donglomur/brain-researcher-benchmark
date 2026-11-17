"""Prospective container entry: cgroup check, then fixed two-phase candidate ABI."""
import os
import sys
from pathlib import Path


def observed(memory):
    c = Path('/sys/fs/cgroup')
    if not (os.getuid() == 65534 and
            (c / 'memory.max').read_text().strip() == str(memory) and
            (c / 'memory.swap.max').read_text().strip() == '0' and
            (c / 'pids.max').read_text().strip() == '64'):
        raise ValueError('candidate cgroup identity')
    quota, period = map(int, (c / 'cpu.max').read_text().split())
    if quota != period or period <= 0:
        raise ValueError('one CPU')


def main():
    if len(sys.argv) != 3 or sys.argv[2] not in ('train', 'predict'):
        raise ValueError('phase ABI')
    observed(int(sys.argv[1]))
    args = [sys.executable, '-I', '-B', '/program/program.py',
            '--phase', sys.argv[2], '--input', '/input', '--out', '/output']
    if sys.argv[2] == 'predict':
        args += ['--model', '/model']
    os.execv(sys.executable, args)


if __name__ == '__main__':
    main()
