"""Trusted collection bootstrap for isolated Python; no cached local imports."""
from pathlib import Path
import types


def main():
    path = Path(__file__).absolute().with_name('source.py')
    module = types.ModuleType('_neural037_source_bootstrap')
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    module.load().local('collect').main()


if __name__ == '__main__':
    main()
