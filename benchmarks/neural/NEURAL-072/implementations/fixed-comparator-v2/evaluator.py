#!/usr/bin/env python3
"""Operator-owned comparator freezing and contextual-only NEURAL-072 scoring.

The expected reference digest is trusted operator configuration, never a field
obtained from the candidate. This module supplies no process sandbox or native
Narratives admission. The predecessor remains available for historical replay.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import types


LEGACY_PATH = Path(__file__).resolve().parents[1] / 'initial-evaluator-v1' / 'evaluator.py'
LEGACY_SHA256 = '66acc703b7f169d87d0d6e334e30588e03af4e41409ecc48e975d213051e375f'
REFERENCE_SCHEMA = 'neural072-fixed-comparators/v2'
CANDIDATE_SCHEMA = 'neural072-contextual-predictions/v2'
COMPARATORS = ('nuisance', 'lexical')


def sha256(data):
    return hashlib.sha256(data).hexdigest()


# Execute exactly the authenticated bytes; do not re-open through an importer.
_legacy_bytes = LEGACY_PATH.read_bytes()
if sha256(_legacy_bytes) != LEGACY_SHA256:
    raise RuntimeError('NEURAL-072 predecessor source pin mismatch')
legacy = types.ModuleType('neural072_pinned_matrix_evaluator')
legacy.__file__ = str(LEGACY_PATH)
exec(compile(_legacy_bytes, str(LEGACY_PATH), 'exec'), legacy.__dict__)
ContractError = legacy.ContractError
require = legacy.require


def decode(data):
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result

    def bad_constant(value):
        raise ContractError('nonfinite JSON number: ' + value)

    return json.loads(data, object_pairs_hook=unique_keys, parse_constant=bad_constant)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def source_identity():
    return {'matrix_evaluator_sha256': LEGACY_SHA256,
            'fixed_comparator_evaluator_sha256': sha256(Path(__file__).read_bytes())}


def freeze_reference(protocol, cases, evaluator_features, training_targets):
    """Fit references with operator inputs only, before accepting submissions.

    Uses the preserved prospective recipe, including its fixed-reference
    contextual arm for shared alpha selection. No candidate inputs or test
    responses enter this function. It is not an author-model reproduction.
    """
    fitted = legacy.fit_predict(protocol, cases, evaluator_features, training_targets)
    return {
        'schema': REFERENCE_SCHEMA,
        'task_id': 'NEURAL-072',
        'protocol_sha256': legacy.digest(protocol),
        'cases_sha256': legacy.digest(cases),
        'source': source_identity(),
        'fit_inputs': {
            'evaluator_features_sha256': legacy.digest(evaluator_features),
            'train_dev_targets_sha256': legacy.digest(training_targets),
        },
        'method': 'operator-fixed-prospective-whitened-ridge-v1',
        'selection': 'Shared alpha selected with evaluator-owned lexical and contextual features before candidate submission.',
        'fit_ledger': fitted['fit_ledger'],
        'predictions': {rid: {arm: values[arm] for arm in COMPARATORS}
                        for rid, values in fitted['predictions'].items()},
    }


def authenticated_reference(protocol, cases, reference_bytes, expected_sha256):
    """The caller must supply expected_sha256 from its protected freeze record."""
    require(isinstance(expected_sha256, str) and re.fullmatch('[0-9a-f]{64}', expected_sha256),
            'trusted reference SHA-256 is required')
    require(isinstance(reference_bytes, bytes), 'reference must be exact frozen bytes')
    require(sha256(reference_bytes) == expected_sha256, 'fixed comparator commitment mismatch')
    ref = decode(reference_bytes)
    expected_fields = {'schema', 'task_id', 'protocol_sha256', 'cases_sha256', 'source',
                       'fit_inputs', 'method', 'selection', 'fit_ledger', 'predictions'}
    require(isinstance(ref, dict) and set(ref) == expected_fields, 'reference fields differ')
    require(ref['schema'] == REFERENCE_SCHEMA and ref['task_id'] == 'NEURAL-072', 'reference schema/task differs')
    require(ref['protocol_sha256'] == legacy.digest(protocol) and ref['cases_sha256'] == legacy.digest(cases),
            'reference protocol/cases differ')
    require(ref['source'] == source_identity(), 'reference fitting source differs')
    require(ref['method'] == 'operator-fixed-prospective-whitened-ridge-v1', 'reference method differs')
    require(isinstance(ref['fit_inputs'], dict) and set(ref['fit_inputs']) ==
            {'evaluator_features_sha256', 'train_dev_targets_sha256'}, 'reference fit input identities missing')
    require(all(isinstance(v, str) and re.fullmatch('[0-9a-f]{64}', v)
                for v in ref['fit_inputs'].values()), 'reference fit input identities invalid')
    listeners = sorted({r['listener'] for r in cases['runs']})
    ledger = ref['fit_ledger']
    require(isinstance(ledger, list) and all(isinstance(row, dict) for row in ledger)
            and [row.get('listener') for row in ledger] == listeners, 'reference fit ledger incomplete')
    return ref


def joined_prediction(protocol, cases, reference, candidate):
    """Strict candidate schema makes comparator substitution an input error."""
    fields = {'schema', 'task_id', 'protocol_sha256', 'cases_sha256', 'contextual'}
    require(isinstance(candidate, dict) and set(candidate) == fields,
            'candidate must contain contextual predictions only; comparator/ledger fields are forbidden')
    require(candidate['schema'] == CANDIDATE_SCHEMA and candidate['task_id'] == 'NEURAL-072',
            'candidate schema/task differs')
    require(candidate['protocol_sha256'] == legacy.digest(protocol) and candidate['cases_sha256'] == legacy.digest(cases),
            'candidate protocol/cases differ')
    contextual, refs = candidate['contextual'], reference['predictions']
    ids = {r['id'] for r in cases['runs'] if r['split'] == 'test'}
    require(isinstance(contextual, dict) and set(contextual) == ids, 'candidate test inventory differs')
    require(isinstance(refs, dict) and set(refs) == ids, 'reference test inventory differs')
    joined = {}
    for rid in ids:
        require(isinstance(refs[rid], dict) and set(refs[rid]) == set(COMPARATORS), 'reference comparator arms differ')
        joined[rid] = {**refs[rid], 'contextual': contextual[rid]}
    prediction = {'task_id': 'NEURAL-072', 'protocol_sha256': legacy.digest(protocol),
                  'cases_sha256': legacy.digest(cases), 'predictions': joined}
    legacy.prediction_arrays(protocol, cases, prediction)
    return prediction


def score(protocol, cases, test_targets, candidate, reference_bytes, expected_reference_sha256):
    legacy.validate(protocol, cases)
    reference = authenticated_reference(protocol, cases, reference_bytes, expected_reference_sha256)
    prediction = joined_prediction(protocol, cases, reference, candidate)
    report = legacy.score(protocol, cases, test_targets, prediction)
    # The preserved helper rounds its acceptance count down for small panels.
    # Apply the declared strict >10% empty-draw failure rule without rounding.
    uncertainty = report['uncertainty']
    require(10 * uncertainty['empty'] <= uncertainty['requested'],
            'too many empty crossed-cluster bootstrap draws')
    arrays = legacy.prediction_arrays(protocol, cases, prediction)
    ys = legacy.targets(cases, test_targets, {'test'})
    # Expose absolute prediction errors as well as signed increments. Preserve
    # the predecessor's exact within-run SST, cell pooling and listener macro.
    for cell in report['cells']:
        sst = None
        sse = {arm: None for arm in legacy.ARMS}
        for rid in cell['runs']:
            y = ys[rid]
            run_sst = ((y - y.mean(axis=0)) ** 2).sum(axis=0)
            sst = run_sst if sst is None else sst + run_sst
            for arm in legacy.ARMS:
                run_sse = ((y - arrays[rid][arm]) ** 2).sum(axis=0)
                sse[arm] = run_sse if sse[arm] is None else sse[arm] + run_sse
        cell['sst_by_target'] = sst.tolist()
        cell['sse_by_target'] = {arm: value.tolist() for arm, value in sse.items()}
        cell['scored_rows_by_run'] = {rid: len(ys[rid]) for rid in cell['runs']}
    absolute_cells = [{'listener': cell['listener'], 'story_family': cell['story_family'],
                       'contrasts': {arm: float(legacy.np.mean(values)) for arm, values in cell['r2_by_target'].items()}}
                      for cell in report['cells']]
    report['listener_macro_r2'] = legacy.summarize(absolute_cells)
    report['comparator_authentication'] = {
        'reference_file_sha256': expected_reference_sha256,
        'source': reference['source'],
        'fit_inputs': reference['fit_inputs'],
        'fit_ledger_sha256': legacy.digest(reference['fit_ledger']),
        'predictions_sha256': legacy.digest(reference['predictions']),
        'method': reference['method'],
        'trust_boundary': 'Expected reference digest supplied by operator outside candidate control; OS isolation and authentic source admission remain external.',
    }
    report['candidate_sha256'] = legacy.digest(candidate)
    report['comparator_fit_ledger'] = reference['fit_ledger']
    return report


def write_new(path, data):
    # A freeze or report must not replace an existing operator artifact.
    with Path(path).open('xb') as stream:
        stream.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='mode', required=True)
    freeze = subs.add_parser('freeze-reference')
    grade = subs.add_parser('score')
    for command in (freeze, grade):
        for key in ('protocol', 'cases', 'targets', 'output'):
            command.add_argument('--' + key, required=True)
    freeze.add_argument('--features', required=True)
    grade.add_argument('--candidate', required=True)
    grade.add_argument('--reference', required=True)
    grade.add_argument('--expected-reference-sha256', required=True)
    args = parser.parse_args()
    try:
        # Read each file once; all hashes and parsed values bind those same bytes.
        names = ('protocol', 'cases', 'targets', 'features') if args.mode == 'freeze-reference' else ('protocol', 'cases', 'candidate', 'reference')
        raw = {name: Path(getattr(args, name)).read_bytes() for name in names}
        protocol, cases = decode(raw['protocol']), decode(raw['cases'])
        if args.mode == 'freeze-reference':
            result = freeze_reference(protocol, cases, decode(raw['features']), decode(raw['targets']))
        else:
            # Reject substituted comparators or malformed candidate support
            # before the protected target file is opened.
            legacy.validate(protocol, cases)
            ref = authenticated_reference(protocol, cases, raw['reference'], args.expected_reference_sha256)
            candidate = decode(raw['candidate'])
            joined_prediction(protocol, cases, ref, candidate)
            raw['targets'] = Path(args.targets).read_bytes()
            result = score(protocol, cases, decode(raw['targets']), candidate,
                           raw['reference'], args.expected_reference_sha256)
            result['input_file_sha256'] = {name: sha256(data) for name, data in raw.items()}
        encoded = encode(result)
        write_new(args.output, encoded)
        print(json.dumps({'task_id': 'NEURAL-072', 'artifact_sha256': sha256(encoded),
                          'mode': args.mode, 'scientific_qualified': False}))
    except (ContractError, OSError, ValueError, TypeError, legacy.np.linalg.LinAlgError) as exc:
        parser.exit(2, 'NEURAL-072 rejected input: ' + str(exc) + '\n')


if __name__ == '__main__':
    main()
