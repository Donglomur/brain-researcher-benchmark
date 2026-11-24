"""Offline local-model D/R actor. Authentic/model execution remains unqualified.
No API/network, executable tools, code execution, hidden PCA state or other-query history.
Model/tokenizer identity, rights, capacities, no-tools semantics and exposure remain gates.
"""
import argparse
import json
import math
from pathlib import Path


def prompt_text(request, policy):
    """Render the permitted observation with its controller-supplied semantics.

    Class summaries are positional; omitting their label order leaves the model
    unable to associate them with the required 27 outputs. No source identity,
    other-query history, reference predictions or protected target is added.
    """
    phase = request['phase']
    if phase not in ('diagnose', 'interpret'):
        raise ValueError('This actor is the no-tools D/R route, not a P/I training shortcut')
    if request['tools']:
        raise ValueError('No tools permitted')
    if phase == 'diagnose':
        context = request['context']
        observation = {'label_order': context['labels'], 'window': context['window'],
                       'arm': context['arm'], 'information_profile': context['profile'],
                       'payload': request['payload']}
        instruction = policy['D_instruction']
    else:
        observation = request['report']
        instruction = policy['R_instruction']
    return instruction + '\n' + json.dumps(observation, sort_keys=True, separators=(',', ':'), allow_nan=False)


def response_value(decoded, phase):
    """Validate a whole model answer against the existing participant protocol."""
    value = json.loads(decoded)  # No parser repair or fallback predictions.
    if type(value) is not dict:
        raise ValueError('Typed model response required')
    if phase == 'diagnose':
        if value == {'status': 'abstain'}:
            return value
        if not (set(value) == {'status', 'probabilities'} and value['status'] == 'complete' and
                type(value['probabilities']) is list and len(value['probabilities']) == 27 and
                all(type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1
                    for p in value['probabilities'])):
            raise ValueError('Exactly 27 finite independent probabilities or explicit abstention required')
    elif phase == 'interpret':
        if not (set(value) == {'status', 'claims'} and value['status'] == 'interpreted' and
                type(value['claims']) is list):
            raise ValueError('Typed interpretation response required')
    else:
        raise ValueError('Unsupported model response phase')
    return value


def main():
    p = argparse.ArgumentParser(); p.add_argument('--request', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True); p.add_argument('--state'); p.add_argument('--build')
    a = p.parse_args(); request = json.loads(a.request.read_text()); out = a.output
    policy = json.loads(Path(__file__).with_name('policy.json').read_text())
    if request['phase'] == 'build':
        (out / 'result.json').write_text(json.dumps({'status': 'built', 'policy': policy['identity']}))
        (out / 'usage.json').write_text(json.dumps({'scope': 'TRUSTED_OFFLINE_MODEL_ADAPTER', 'model_calls': 0, 'input_tokens': 0, 'output_tokens': 0, 'model_identity': policy['identity']}))
        return
    text = prompt_text(request, policy)
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    # Exact local model files live in the independently pinned image; no download fallback.
    model_path = policy['local_model_path']
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(model_path, local_files_only=True, trust_remote_code=False)
    model.eval(); torch.manual_seed(policy['seed'])
    inputs = tokenizer(text, return_tensors='pt', truncation=False)
    n = int(inputs['input_ids'].shape[1]); limit = policy['max_new_tokens']
    if n + limit > policy['qualified_context_tokens']:
        raise ValueError('Full prompt exceeds qualified context; no truncation')
    with torch.inference_mode():
        response = model.generate(**inputs, max_new_tokens=limit, do_sample=False)
    generated = response[0, n:]; decoded = tokenizer.decode(generated, skip_special_tokens=True)
    value = response_value(decoded, request['phase'])
    (out / 'result.json').write_text(json.dumps(value, allow_nan=False))
    (out / 'usage.json').write_text(json.dumps({'scope': 'TRUSTED_OFFLINE_MODEL_ADAPTER', 'model_calls': 1,
                                               'input_tokens': n, 'output_tokens': len(generated),
                                               'model_identity': policy['identity']}))

if __name__ == '__main__': main()
