"""Non-learning lifecycle control: only ordered IDs enter constant0.5 responses."""
import argparse
import json
from pathlib import Path
import re
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    with np.load(args.input / 'public.npz', allow_pickle=False) as packet:
        ids = packet['query_ids'].tolist()
    if (type(ids) is not list or len(ids) != 20 or len(set(ids)) != 20 or
            any(type(q) is not str or re.fullmatch('[0-9a-f]{24}', q) is None for q in ids)):
        raise ValueError('Complete20 unique opaque query IDs required')
    result = {'schema_version': 1, 'probabilities': [
        {'query_id': q, 'probability': 0.5} for q in ids]}
    with (args.out / 'probabilities.json').open('x') as output:
        json.dump(result, output, separators=(',', ':'), allow_nan=False)
        output.write('\n')


if __name__ == '__main__':
    main()
