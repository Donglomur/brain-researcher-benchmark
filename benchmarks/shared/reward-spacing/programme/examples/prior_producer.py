"""Fixed invented producer: arithmetic-only zero arrays or unfitted P; no fitting."""
import json
import hashlib
import sys
from pathlib import Path

def digest(x):
    return hashlib.sha256((json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False) + '\n').encode()).hexdigest()

public = json.loads(Path(sys.argv[1]).read_text()); output = Path(sys.argv[2])
assert public['synthetic'] is True
if public['task'] == 'NEURAL-045':
    prediction = {r['id']: [0.0] * len(r['times']) for r in public['query']}; pins = {}
else:
    model = {'schema': 'unfitted_prior_v1', 'training_labels_seen': False, 'constant': 0.0}
    prediction = {'P': {r['id']: 0.0 for r in public['query']}}; pins = {'P': digest(model)}
    (output.parent / 'model_P.json').write_text(json.dumps(model))
    analysis = {'model_class': 'unfitted_prior', 'identifiability': {'status': 'no_neural_training_evidence'},
                'sensitivity_predictions': {}, 'scientific_qualification': False}
    (output.parent / 'analysis.json').write_text(json.dumps(analysis))
output.write_text(json.dumps({'schema': 'sealed_neural_predictions_v1', 'task': public['task'],
    'cell_id': public['cell_id'], 'input_digest': digest(public), 'predictions': prediction,
    'model_artifact_digests': pins}))
