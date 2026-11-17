"""Run generated fixtures only; no native imports, real NWBs or model calls.

Run from any working directory: python3 -I -S -B /path/to/package/run_generated_tests.py
Subdirectories are discovered separately with isolated module namespaces.
"""
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent


def main():
    for directory in ('preparation','paired'):
        source=HERE/directory
        # Separate short children prevent same-named helper modules in the two
        # package sections from sharing test state. The outer pool owns deadline.
        command=[sys.executable,'-I','-S','-B','-m','unittest','discover',
                 '-s',str(source),'-p','test_*.py','-v']
        result=subprocess.run(command,cwd=source,check=False)
        if result.returncode:
            return result.returncode
    return 0


if __name__=='__main__':raise SystemExit(main())
