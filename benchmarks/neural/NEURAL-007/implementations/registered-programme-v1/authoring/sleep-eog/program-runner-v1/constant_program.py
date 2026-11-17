"""Valid weak control: uniform probabilities, hence first-index wake on ties."""
import argparse
import json
from pathlib import Path
import numpy as np
parser = argparse.ArgumentParser()
parser.add_argument('--input', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
manifest = json.loads((args.input / 'case.json').read_text())
case_id, n = manifest['case_id'], manifest['epochs']
np.savez(args.out / 'predictions.npz', class_order=np.asarray(['W', 'N1', 'N2', 'N3', 'R']),
         **{case_id + '__epoch_id': np.asarray([case_id + '/' + f'{i:05d}' for i in range(n)]),
            case_id + '__probabilities': np.full((n, 5), .2)})
