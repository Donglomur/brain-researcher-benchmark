"""Static probability scoring; all public fields validate before private labels."""
import hashlib
import json
import math
import os
from pathlib import Path
import stat


def need(ok, message):
    if not ok:
        raise ValueError(message)


def unique(pairs):
    obj = {}
    for key, value in pairs:
        need(key not in obj, 'Duplicate JSON field')
        obj[key] = value
    return obj


def invalid_constant(value):
    raise ValueError('Nonfinite JSON constant: ' + value)


def decode(body):
    return json.loads(body, object_pairs_hook=unique, parse_constant=invalid_constant)


def read_pinned(path, pin):
    need(type(pin['bytes']) is int and 0 <= pin['bytes'] <= 1000000, 'Bounded asset')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == pin['bytes'], 'Exact ordinary asset')
        blocks = []
        remaining = before.st_size
        while remaining:
            block = os.read(fd, min(65536, remaining))
            need(bool(block), 'Truncated asset')
            blocks.append(block)
            remaining -= len(block)
        after = os.fstat(fd)
        need(not os.read(fd, 1) and all(getattr(before, k) == getattr(after, k)
             for k in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink')), 'Asset changed')
        body = b''.join(blocks)
        need(hashlib.sha256(body).hexdigest() == pin['sha256'], 'Asset checksum')
        return body
    finally:
        os.close(fd)


def main():
    private = False
    try:
        assets = decode(Path('/source/operator_assets.json').read_bytes())
        invocation = decode(Path('/source/invocation.json').read_bytes())
        panel = decode(read_pinned('/public/cases.json', assets['public_panel']))
        ids = [(r['fold'], r['query_id']) for r in panel['cases']]
        need(len(ids) == len(set(ids)) == 140 and {a for a, _ in ids} == set(range(7)), 'Canonical panel')
        try:
            obj = decode(read_pinned('/submission/probabilities.json', invocation['submission']))
            need(type(obj) is dict and set(obj) == {'schema_version', 'probabilities'}
                 and type(obj['schema_version']) is int and obj['schema_version'] == 1, 'Exact top-level schema')
            rows = obj['probabilities']
            need(type(rows) is list and len(rows) == 140, 'Exactly140 case probabilities required')
            got = {}
            for row in rows:
                need(type(row) is dict and set(row) == {'fold', 'query_id', 'probability'}, 'Probability fields')
                need(type(row['fold']) is int and 0 <= row['fold'] < 7
                     and type(row['query_id']) is str and len(row['query_id']) == 24, 'Typed identifiers')
                key = row['fold'], row['query_id']
                probability = row['probability']
                need(key not in got, 'Duplicate case')
                need(type(probability) in (int, float) and math.isfinite(probability)
                     and 0 <= probability <= 1, 'Finite probability in[0,1]')
                got[key] = probability
            need(set(got) == set(ids), 'Exact public case coverage')
        except Exception as exc:
            print(json.dumps({'status': 'invalid_submission', 'score': None, 'reason': str(exc),
                              'private_targets_decoded': False, 'candidate_program_replayed': False}))
            return 2
        truth = decode(read_pinned('/private/targets.json', assets['private_targets']))
        private = True
        reference = decode(read_pinned('/private/reference_grade.json', assets['private_references']))
        per_mouse = []
        covered = set()
        for fold in truth['folds']:
            keys = [(fold['fold'], i) for i in fold['query_ids']]
            labels = fold['query_labels']
            need(len(keys) == 20 and len(labels) == 20 and labels.count(0) == labels.count(1) == 10, 'Balanced private fold')
            need(not covered.intersection(keys), 'Disjoint private folds')
            covered.update(keys)
            probabilities = [got[k] for k in keys]
            accuracy = (sum(p < .5 for p, y in zip(probabilities, labels) if y == 0) / 10
                      + sum(p >= .5 for p, y in zip(probabilities, labels) if y == 1) / 10) / 2
            clipped = [max(1e-15, min(1 - 1e-15, p)) for p in probabilities]
            loss = -math.fsum(y * math.log(p) + (1-y) * math.log1p(-p)
                              for p, y in zip(clipped, labels)) / 20
            per_mouse.append({'fold': fold['fold'], 'balanced_accuracy': accuracy, 'log_loss': loss})
        need(covered == set(ids) and len(per_mouse) == 7, 'Complete private join')
        metrics = {k: math.fsum(r[k] for r in per_mouse) / 7 for k in ('balanced_accuracy', 'log_loss')}
        differences = {name: {k: metrics[k] - value[k] for k in metrics}
                       for name, value in reference['summary'].items()}
        result = {'status': 'scored', 'score': metrics, 'co_primary_metrics': metrics,
                  'directions': {'balanced_accuracy': 'higher', 'log_loss': 'lower'},
                  'per_mouse': per_mouse, 'signed_candidate_minus_reference': differences,
                  'reference_metrics': reference['summary'], 'private_targets_decoded': True,
                  'candidate_program_replayed': False, 'candidate_code_executed': False,
                  'scientific_success_threshold': None, 'scientific_success': None,
                  'full_contract_qualified': False,
                  'scope': 'Static probability-file scoring; it does not attest fold isolation, program behavior, or unexposed assessment.'}
        print(json.dumps(result, allow_nan=False))
        return 0
    except Exception as exc:
        print(json.dumps({'status': 'operator_error', 'score': None, 'reason': str(exc),
                          'private_targets_decoded': private}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
