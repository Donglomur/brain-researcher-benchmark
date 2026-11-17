"""Trusted two-part adapter; candidate bytes are never imported as Python."""
import hashlib
import io
import json
from pathlib import Path
import sys
sys.path.insert(0, '/source')
import numpy as np
import candidate_adapter as adapter
from integration_helper import target_headers


def main():
    plan = json.loads(Path('/source/operator_assets.json').read_text())
    invocation = json.loads(Path('/source/invocation.json').read_text())
    spec = adapter.Specification(tuple(adapter.Case(c['case_id'], c['epochs']) for c in plan['cases']), ('YASA', 'RF'))
    calls = 0
    phase = 'operator'
    try:
        adapter.require(set(invocation) == {'parts', 'producer_resources_absent', 'same_program_sha256'} and
                        invocation['producer_resources_absent'] is True and
                        set(invocation['parts']) == {c.case_id for c in spec.cases}, 'Exact frozen two-case invocation')
        bundle = {'class_order': np.asarray(adapter.CLASS_ORDER)}
        phase = 'candidate'
        for case in spec.cases:
            validated = adapter.validate_submission(Path('/submission') / (case.case_id + '.npz'),
                invocation['parts'][case.case_id], adapter.Specification((case,), ()))
            for key in ('epoch_id', 'probabilities'):
                bundle[case.case_id + '__' + key] = validated['people'][case.case_id][key]
        phase = 'operator'
        # Pure layout assembly; no prediction values are normalized or transformed.
        buffer = io.BytesIO()
        np.savez(buffer, **bundle)
        body = buffer.getvalue()
        adapter.require(0 < len(body) <= 1_000_000, 'Bounded aggregate artifact')
        path = Path('/tmp/predictions.npz')
        with path.open('xb') as output:
            output.write(body)
        lock = {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}
        phase = 'operator'
        refs = {name: (Path('/comparators') / (name + '.npz'), {k: pin[k] for k in ('bytes', 'sha256')})
                for name, pin in plan['comparators'].items()}
        # Frozen comparator failure is an operator problem, never candidate invalidity.
        for reference, pin in refs.values():
            adapter.validate_submission(reference, pin, spec)

        def private_once():
            nonlocal calls
            calls += 1
            adapter.require(calls == 1, 'One private target-loader invocation')
            root = Path('/private')
            adapter.require({p.name for p in root.iterdir()} == set(plan['private_files']), 'Exact development target files')
            plain = lambda pin: {k: pin[k] for k in ('bytes', 'sha256')}
            manifest = json.loads(adapter._locked_bytes(root / 'manifest.json', plain(plan['private_files']['manifest.json'])))
            adapter.require(manifest == plan['private_manifest_expected'], 'Exact target lineage')
            targets = {}
            for case in spec.cases:
                name = case.case_id + '_labels.npz'
                data = adapter._locked_bytes(root / name, plain(plan['private_files'][name]))
                target_headers(data, case)
                with np.load(io.BytesIO(data), allow_pickle=False, max_header_size=4096) as arrays:
                    targets[case.case_id] = {k: arrays[k] for k in ('epoch_id', 'stage', 'score_mask')}
            return targets

        result = adapter.evaluate(path, lock, spec, private_once, refs)
        report = {'status': 'scored', 'id': 'NEURAL-007', 'primary_metric': 'person_mean_macro_f1',
                  'score': result['candidate']['person_mean_macro_f1'], 'result': result,
                  'private_loader_calls': calls, 'scientific_success': None, 'binary_reward': None,
                  'aggregate_bytes': len(body), 'scope': plan['scope']}
    except Exception as error:
        report = {'status': 'invalid_submission' if phase == 'candidate' and calls == 0 else 'operator_error',
                  'id': 'NEURAL-007', 'score': None, 'private_loader_calls': calls,
                  'scientific_success': None, 'binary_reward': None,
                  'error_type': type(error).__name__, 'error': str(error)[:1024]}
    body = json.dumps(report, allow_nan=False, separators=(',', ':'))
    adapter.require(len(body.encode()) <= 32_768, 'Bounded complete scoring report')
    print(body, flush=True)
    return int(report['status'] == 'operator_error')


if __name__ == '__main__':
    raise SystemExit(main())
