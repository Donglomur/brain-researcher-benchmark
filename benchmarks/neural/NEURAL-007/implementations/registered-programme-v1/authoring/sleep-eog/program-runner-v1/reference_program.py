"""Qualification control only: validate all training joins, reuse cached YASA."""
import argparse
import json
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--input', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
sys.path[:0] = ['/training/tools', str(args.input)]
import numpy as np
import cache_core
from public_validation import validate_manifest

marker = Path('/tmp/sleep-fresh-state')
assert not marker.exists()
marker.write_text('created in this fresh process')
manifest = json.loads((args.input / 'case.json').read_text())
cache, evidence = validate_manifest(manifest)
case_id, n = manifest['case_id'], manifest['epochs']
probability = cache_core.resolve_view(cache, case_id, n, 'EEG_EOG_ensemble')['probabilities']
np.savez(args.out / 'predictions.npz', class_order=cache['class_order'],
         **{case_id + '__epoch_id': cache['epoch_id'], case_id + '__probabilities': probability})
print(json.dumps({**evidence, 'fresh_marker_absent_before_start': True, 'cached_view': 'EEG_EOG_ensemble'}), flush=True)
