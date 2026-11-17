"""Public B-side canonical original-method exporter, not a scorer/reference.

An independently committed B program may choose this exact source. Only exact
full-source equality plus an independently closed immutable historical image
permits a trusted original training-history observation. A receives no OSL.
"""
import argparse
from pathlib import Path
from safe_io import capture, strict
from native_run import run


def main():
    p=argparse.ArgumentParser()
    for name in ('request','case','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();payload=strict(capture(a.case,1048576))
    run(payload['job'],payload['context'],payload['script'],payload['script_pin'],payload['wrapper_pin'],
        '/work',Path(a.output),payload['exposure'],payload['capture_cap'])


if __name__=='__main__':main()
