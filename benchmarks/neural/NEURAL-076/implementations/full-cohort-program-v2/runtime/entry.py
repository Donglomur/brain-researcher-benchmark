"""Fixed isolated neural076 one-context program ABI; executed only after actual selection."""
import os
import importlib.metadata
import sys
from pathlib import Path

def main():
    if len(sys.argv) != 2:
        raise ValueError('memory operand')
    if sys.version_info[:3]!=(3,11,13) or any(importlib.metadata.version(k)!=v for k,v in {'numpy':'2.2.6','h5py':'3.14.0','jsonschema':'4.25.1'}.items()):
        raise ValueError('fixed candidate runtime')
    memory = int(sys.argv[1]); root = Path('/sys/fs/cgroup')
    quota, period = map(int, (root/'cpu.max').read_text().split())
    if not (os.getuid() == 65534 and (root/'memory.max').read_text().strip() == str(memory)
            and (root/'memory.swap.max').read_text().strip() == '0'
            and quota == period and period > 0 and (root/'pids.max').read_text().strip() == '64'):
        raise ValueError('observed guest resources')
    os.execv(sys.executable, [sys.executable, '-I', '-B', '/submission/program.py',
                             '--input', '/case', '--output', '/output'])

if __name__ == '__main__':
    main()
