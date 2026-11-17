"""Full numerical report programme, frozen before the bank; no P-policy language."""
import json
import hashlib
import sys
from pathlib import Path

packet = json.loads(Path(sys.argv[1]).read_text())
assert packet['synthetic'] is True and packet['schema'] == 'closed_aggregate_interpretation_evidence_v1'
if packet['task'] == 'NEURAL-045':
    loss = packet['metrics']['animal_macro']['mse']
    claim = 'Prebank numerical routine: native mean squared error is ' + format(loss, '.8g') + '.'
else:
    loss = packet['metrics']['models']['P']['animal_macro_mse']
    claim = 'Prebank numerical routine: unfitted-prior mean squared error is ' + format(loss, '.8g') + '; no time/count comparison is available.'
digest = hashlib.sha256((json.dumps(packet, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False) + '\n').encode()).hexdigest()
Path(sys.argv[2]).write_text(json.dumps({'schema': 'neural_scientific_interpretation_v1',
    'closed_result_digest': digest, 'claims': [claim],
    'limitations': ['Invented engineering arithmetic only. No biological or scientific qualification.']}))
