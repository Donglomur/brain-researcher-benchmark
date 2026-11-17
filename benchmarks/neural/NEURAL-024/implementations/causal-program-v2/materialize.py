"""Write only recovered source into a fresh external operator root."""
import argparse
from pathlib import Path
import types

HERE = Path(__file__).absolute().parent
recovery = types.ModuleType('_neural024_source_recovery')
recovery.__file__ = str(HERE / 'recovery.py')
exec(compile((HERE / 'recovery.py').read_bytes(), recovery.__file__, 'exec'), recovery.__dict__)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(__import__('json').dumps(recovery.materialize(args.output), sort_keys=True))
