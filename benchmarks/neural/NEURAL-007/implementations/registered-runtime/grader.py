"""Trusted numerical worker. No candidate code is imported or executed."""
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
    spec = adapter.Specification(tuple(adapter.Case(c['case_id'], c['epochs'])
                                       for c in plan['cases']), ('YASA', 'RF'))
    calls = 0

    def private_once():
        nonlocal calls
        calls += 1
        adapter.require(calls == 1, 'one private target-loader invocation')
        root = Path('/private')
        adapter.require({p.name for p in root.iterdir()} == set(plan['private_files']),
                        'exact three private files')
        plain = lambda p: {k: p[k] for k in ('bytes', 'sha256')}
        manifest = json.loads(adapter._locked_bytes(root / 'manifest.json',
                              plain(plan['private_files']['manifest.json'])))
        adapter.require(manifest == plan['private_manifest_expected'], 'private lineage manifest')
        result = {}
        for case in spec.cases:
            name = case.case_id + '_labels.npz'
            body = adapter._locked_bytes(root / name, plain(plan['private_files'][name]))
            target_headers(body, case)
            with np.load(io.BytesIO(body), allow_pickle=False, max_header_size=4096) as arrays:
                result[case.case_id] = {k: arrays[k] for k in ('epoch_id', 'stage', 'score_mask')}
        return result

    refs = {name: (Path('/comparators') / (name + '.npz'),
                  {k: pin[k] for k in ('bytes', 'sha256')})
            for name, pin in plan['comparators'].items()}
    try:
        # Complete candidate and comparator validation occurs before private_once.
        result = adapter.evaluate(Path('/submission/predictions.npz'), invocation['submission'],
                                  spec, private_once, refs)
        report = {'status': 'scored', 'id': 'NEURAL-007',
                  'primary_metric': 'person_mean_macro_f1',
                  'score': result['candidate']['person_mean_macro_f1'],
                  'scientific_success': None, 'binary_reward': None,
                  'private_loader_calls': calls, 'result': result,
                  'numpy_version': np.__version__,
                  'scope': plan['scope']}
        code = 0
    except Exception as exc:
        # A public validation failure has zero private-loader invocations. A private
        # contract failure is an operator error, not a candidate zero score.
        report = {'status': 'invalid_submission' if calls == 0 else 'operator_error',
                  'id': 'NEURAL-007', 'score': None, 'scientific_success': None,
                  'private_loader_calls': calls, 'error_type': type(exc).__name__,
                  'error': str(exc)[:2000]}
        code = 2 if calls == 0 else 1
    body = json.dumps(report, allow_nan=False, separators=(',', ':'))
    adapter.require(len(body.encode()) <= plan['report_bytes'], 'bounded scoring report')
    print(body, flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
