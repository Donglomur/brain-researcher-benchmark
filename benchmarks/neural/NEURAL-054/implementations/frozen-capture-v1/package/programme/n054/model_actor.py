"""Concrete offline local-model D/R actor. Source only, never imported or executed here.
No API/network, executable tools, code execution, hidden PCA state or other-query history.
Model/tokenizer identity, rights, capacities, no-tools semantics and exposure remain gates.
"""
import argparse
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(); p.add_argument('--request', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True); p.add_argument('--state'); p.add_argument('--build')
    a = p.parse_args(); request = json.loads(a.request.read_text()); out = a.output
    policy = json.loads(Path(__file__).with_name('policy.json').read_text())
    if request['phase'] == 'build':
        (out / 'result.json').write_text(json.dumps({'status': 'built', 'policy': policy['identity']}))
        (out / 'usage.json').write_text(json.dumps({'scope': 'TRUSTED_OFFLINE_MODEL_ADAPTER', 'model_calls': 0, 'input_tokens': 0, 'output_tokens': 0, 'model_identity': policy['identity']}))
        return
    if request['phase'] not in ('diagnose', 'interpret'):
        raise ValueError('This actor is the no-tools D/R route, not a P/I training shortcut')
    if request['tools']:
        raise ValueError('No tools permitted')
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    # Exact local model files live in the independently pinned image; no download fallback.
    model_path = policy['local_model_path']
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(model_path, local_files_only=True, trust_remote_code=False)
    model.eval(); torch.manual_seed(policy['seed'])
    instruction = policy['D_instruction'] if request['phase'] == 'diagnose' else policy['R_instruction']
    payload = json.dumps(request['payload'] if request['phase'] == 'diagnose' else request['report'],
                         sort_keys=True, separators=(',', ':'))
    text = instruction + '\n' + payload
    inputs = tokenizer(text, return_tensors='pt', truncation=False)
    n = int(inputs['input_ids'].shape[1]); limit = policy['max_new_tokens']
    if n + limit > policy['qualified_context_tokens']:
        raise ValueError('Full prompt exceeds qualified context; no truncation')
    with torch.inference_mode():
        response = model.generate(**inputs, max_new_tokens=limit, do_sample=False)
    generated = response[0, n:]; decoded = tokenizer.decode(generated, skip_special_tokens=True)
    value = json.loads(decoded)  # Strict whole answer, no invented parser repair or numeric fallback.
    if request['phase'] == 'diagnose':
        if not (set(value) == {'status', 'probabilities'} and value['status'] == 'complete' and
                isinstance(value['probabilities'], list) and len(value['probabilities']) == 27):
            raise ValueError('Complete 27-probability response required')
    else:
        if not (set(value) == {'status', 'claims'} and value['status'] == 'interpreted'):
            raise ValueError('Typed interpretation response required')
    (out / 'result.json').write_text(json.dumps(value, allow_nan=False))
    (out / 'usage.json').write_text(json.dumps({'scope': 'TRUSTED_OFFLINE_MODEL_ADAPTER', 'model_calls': 1,
                                               'input_tokens': n, 'output_tokens': len(generated),
                                               'model_identity': policy['identity']}))

if __name__ == '__main__': main()
