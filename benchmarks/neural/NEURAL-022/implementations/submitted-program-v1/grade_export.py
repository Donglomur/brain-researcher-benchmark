"""Stdlib-only wrapper; original grade clock starts before scientific imports."""
import contextlib
import io
from pathlib import Path
import runpy
import sys


class BoundedLog(io.StringIO):
    def write(self, value):
        if self.tell() + len(value) > 16384:
            raise ValueError('Bounded original worker metadata stdout')
        return super().write(value)


def main():
    # No scientific module is imported before the unchanged grade.py starts.
    sys.argv = ['/source/grade.py', *sys.argv[1:], '--out', '/tmp']
    with contextlib.redirect_stdout(BoundedLog()):
        try:
            runpy.run_path('/source/grade.py',run_name='__main__')
        except SystemExit as error:
            if error.code not in (None, 0):
                raise
    path = Path('/tmp/score.json')
    with path.open('rb') as stream:
        body = stream.read(65537)
    if not 0 < len(body) <= 65536:
        raise ValueError('Bounded original scalar report')
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()


if __name__ == '__main__':
    main()
