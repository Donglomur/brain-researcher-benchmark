"""Fixed isolated case-program ABI; executed only after actual selection."""
import os
import runpy
import importlib.metadata
import sys
from pathlib import Path

def main():
    for name, version in [('numpy','2.2.6'),('h5py','3.13.0')]:
        if importlib.metadata.version(name) != version:
            raise ValueError('Selected task dependency version')
    if len(sys.argv) != 2:
        raise ValueError('memory operand')
    memory = int(sys.argv[1]); root = Path('/sys/fs/cgroup')
    quota, period = map(int, (root/'cpu.max').read_text().split())
    if not (os.getuid() == 65534 and (root/'memory.max').read_text().strip() == str(memory)
            and (root/'memory.swap.max').read_text().strip() == '0'
            and quota == period and period > 0 and (root/'pids.max').read_text().strip() == '64'):
        raise ValueError('observed guest resources')
    sys.path.insert(0, '/case/public')
    sys.argv = ['/submission/program.py', '--input', '/case', '--output', '/output/prediction.json']
    runpy.run_path('/submission/program.py', run_name='__main__')

if __name__ == '__main__':
    main()
