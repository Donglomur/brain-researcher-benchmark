"""Observe the declared host NumPy runtime before the unchanged private CLI."""
import runpy
import sys


def main():
    if sys.version_info[:3] != (3, 12, 8):
        raise ValueError('declared Python3.12.8 required')
    import numpy
    if numpy.__version__ != '2.2.6':
        raise ValueError('declared NumPy2.2.6 required')
    if len(sys.argv) < 2:
        raise ValueError('trusted scientific source path')
    sys.argv = sys.argv[1:]
    runpy.run_path(sys.argv[0], run_name='__main__')


if __name__ == '__main__':
    main()
