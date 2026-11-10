"""Untrusted candidate code runs only inside separately admitted offline realms.

This wrapper is public. It carries no original identities, answers or reference
implementation. Outer capture/custody/content admission does not trust this process.
"""
import importlib.util
import json
import sys
from pathlib import Path
from core import encoded, exact, need
from safe_io import capture, child, new_json, pin, strict

def load_source(root, entry, files, cap):
    need(entry in files and entry.endswith('.py'), 'Declared candidate Python entry')
    for relative, desc in files.items():
        body = capture(child(root, relative), cap, desc)
        need(relative.endswith('.py') and b'\x00' not in body, 'Only captured UTF8 candidate source')
        body.decode('utf-8')
    need('/' not in entry, 'Root Python entry; package helpers may use absolute imports')
    sys.path.insert(0, str(root))
    path = child(root, entry)
    spec = importlib.util.spec_from_file_location('neural066_candidate', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def run(request, inputroot, outputroot):
    """Actual container entry; caller must never execute this on the host."""
    limits = request['limits']
    submitted = Path('/submitted')
    source = request['submitted']
    module = load_source(submitted, source['entry'], source['files'], limits['source_bytes'])
    out = Path(outputroot)
    need(out.is_dir(), 'Outer owned output volume')
    action = request['action']
    scope = request['scope']
    recipe = request['recipe']
    model_pin = None
    prediction_pin = None
    need(scope['other_cases'] is False and scope['private_labels'] is False, 'No private/cross-case source realm')
    if action == 'candidate_policy':
        need(request['role'] in ('A', 'B'), 'Candidate policy role')
        result = module.run(str(inputroot), str(out), {'stage': request['policy_stage'], 'recipe': recipe})
        need(type(result) is dict and result.get('action') in ('inspect', 'train_validate', 'select', 'finalize'), 'Typed bounded policy/tool result')
        body = encoded(result)
        need(len(body) <= limits['response_bytes'], 'Complete response allowance')
        new_json(out / 'OBSERVATION.json', result)
    elif action == 'candidate_fit':
        need(scope['query_access'] is False and scope['fit_training_only'] is True and (scope['preliminary_fitted_state'] is False), 'Fresh final training-only realm')
        result = module.fit(str(inputroot), str(out), recipe)
        need(type(result) is dict and result.get('schema') == 'neural066_candidate_model_v1', 'Typed inert model declaration')
        need(type(result.get('arrays')) is dict and type(result.get('configuration')) is dict and (type(result.get('stateless')) is bool), 'Explicit final model/config/state policy')
        need(not result['stateless'] or not result['arrays'], 'Stateless means no fitted arrays; semantic content admission still required')
        body = encoded(result)
        need(len(body) <= limits['model_json_bytes'], 'Bounded model metadata')
        need(result.get('context') == request['model_context'], 'Exact own mode/arm/source/recipe/FIT context, not a previous model')
        model_pin = new_json(out / 'MODEL.json', result)
    elif action == 'candidate_infer':
        need(scope['training_access'] is False and scope['query_access'] is True and (scope['provider_after_seal'] is False), 'Only fresh-model/current-query inference realm')
        model = strict(capture('/model/MODEL.json', limits['model_json_bytes'], request['model_pin']))
        need(model.get('context') == request['model_context'], 'Inference accepts only the exact own original final model')
        before = {name: pin(capture(child('/model', name), limits['model_bytes'])) for name in request['model_files']}
        result = module.predict(str(inputroot), '/model', model, recipe)
        after = {name: pin(capture(child('/model', name), limits['model_bytes'])) for name in request['model_files']}
        need(before == after == request['model_files'], 'No query-dependent state mutation; exact sealed pre/post state')
        need(type(result) is dict and result.get('format') == 'typing_predictions_v1', 'Typed full predictions')
        body = encoded(result)
        need(len(body) <= limits['response_bytes'], 'Full prediction byte bound, no prefix truncation')
        prediction_pin = new_json(out / 'PREDICTIONS.json', result)
    else:
        raise ValueError('Unsupported candidate action')
    answer = {'schema': 'neural066_candidate_result_v1', 'status': 'complete', 'action': action, 'case': request['case'], 'mode': request['mode'], 'condition': request['condition'], 'model_context': request.get('model_context'), 'model': model_pin, 'predictions': prediction_pin, 'output_status_not_content_or_custody_attestation': True}
    new_json(out / 'RESULT.json', answer)
    return answer
