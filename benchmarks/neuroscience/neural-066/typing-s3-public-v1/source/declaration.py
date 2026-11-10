"""Precommitted deterministic target-free investigation declaration builder."""
import math
from core import need
from protected_score import admit_predictions

def build(ws, predictions, policy, mode, policy_pin, methods):
    need(len(predictions) == 468 and policy['hidden_target_conclusions'] == 'deferred', 'Complete same-mode prediction seals and precommitted target-free policy')
    files = []
    total_rows = 0
    entropy = 0.0
    for context, entry in sorted(predictions.items()):
        need(entry['public']['view']['mode'] == mode, 'No other mode inputs')
        d = ws.from_capture(entry['capture'], 'PREDICTIONS.json')
        body = ws.read(d['source_path'], d)
        probabilities = admit_predictions(body, entry['public']['view'])
        rows = sum((len(v) for v in probabilities.values()))
        value = sum((-sum((p * math.log(p) for p in vector if p > 0)) for vectors in probabilities.values() for vector in vectors))
        files.append({'context': context, 'prediction': {k: d[k] for k in ('bytes', 'sha256')}, 'sentences': len(probabilities), 'token_rows': rows, 'sum_entropy_nats': value})
        total_rows += rows
        entropy += value
        ws.budget.tick()
    source = []
    for (slot, m, arm), method in sorted(methods.items()):
        if m == mode:
            source.append({'case_slot': slot, 'arm': arm, 'source_seal': {k: method['source_seal'][k] for k in ('bytes', 'sha256')}, 'recipe_seal': {k: method['recipe_seal'][k] for k in ('bytes', 'sha256')}, 'content_admission': method['independent_content_admission']})
    need(len(source) == 468 and total_rows > 0, 'All current same-mode source/recipe/method seals')
    value = {'schema': 'neural066_investigation_declaration_v1', 'mode': mode, 'policy': {k: policy_pin[k] for k in ('bytes', 'sha256')}, 'estimand': policy['estimand'], 'limitations': policy['limitations'], 'hidden_target_conclusions': 'deferred', 'source_and_recipe_seals': source, 'predictions': files, 'token_rows': total_rows, 'sum_entropy_nats': entropy, 'mean_entropy_nats': entropy / total_rows, 'entropy_is_not_accuracy_or_neural_reasoning': True, 'provider_calls': 0, 'target_reads': 0, 'prediction_mutations': 0, 'narrative_quality_scored': False}
    return ws.json('declarations/' + mode + '/investigation.json', value)
