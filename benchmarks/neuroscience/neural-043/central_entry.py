"""Inactive task metadata entry. No data/provider/scientific execution route."""
import json
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent/'source'))
from alm.contracts import readiness

def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv != ['status']:
        raise RuntimeError('ALM native/provider/source/target/resource qualification remains unissued; no central run or score')
    return readiness()

if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
