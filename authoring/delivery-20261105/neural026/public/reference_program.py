"""Executable supplied solution: only its single public case is an operand.

Model execution is a future action, not part of source construction checks.
The packet is trusted operator-prepared; no private/reference inputs exist.
"""
import argparse
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import protocol


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    protocol.need(not a.output.exists(), 'Fresh prediction destination')
    # Operator constructs this numeric packet. The grader separately uses
    # bounded primitive-header admission for untrusted candidate predictions.
    with np.load(a.input, allow_pickle=False) as f:
        v = {name: f[name] for name in f.files}
    out = protocol.fit_predict(v)
    with a.output.open('xb') as f:
        np.savez(f, **out)


if __name__ == '__main__':
    main()
