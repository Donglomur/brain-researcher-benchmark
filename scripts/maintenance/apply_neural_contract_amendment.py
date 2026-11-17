#!/usr/bin/env python3
"""Stage an explicitly reviewed source-backed wording amendment, with provenance.

This cannot promote readiness or edit an implemented/frozen benchmark package.
"""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Load this sibling explicitly so the maintained command also works with Python -I -S.
import importlib.util as _importlib_util
_construction_spec = _importlib_util.spec_from_file_location('_neurobench_construction', Path(__file__).with_name('_construction.py'))
construction = _importlib_util.module_from_spec(_construction_spec)
_construction_spec.loader.exec_module(construction)

ROSTER = ROOT / 'docs/neuroscience-benchmarks/build/neural_100.json'
ALLOWED = {'biological_unit', 'controls', 'primary_metric.definition',
           'reference.role', 'scientific_question', 'split.policy',
           'target_output', 'title', 'neural_role'}


def sha(body):
    return hashlib.sha256(body).hexdigest()


def main():
    global ROOT, ROSTER
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proposal', required=True)
    construction.arguments(parser)
    args = parser.parse_args()
    ROOT, record = construction.paths(args, parser)
    ROSTER = ROOT / 'docs/neuroscience-benchmarks/build/neural_100.json'
    proposal_path = (ROOT / args.proposal).resolve()
    if not proposal_path.is_relative_to(ROOT):
        raise ValueError('Repository paths only')
    proposal_body = proposal_path.read_bytes()
    proposal = json.loads(proposal_body)
    before = ROSTER.read_bytes()
    if sha(before) != proposal['source_roster']['sha256']:
        raise ValueError('Roster changed since proposal; review before application')
    original = json.loads(before)
    changed = copy.deepcopy(original)
    tasks = {r['id']: r for r in changed['tasks']}
    expected = {r['id'] for r in changed['tasks'] if r['status'] == 'discovery_candidate'}
    reviews = proposal['tasks']
    if len(reviews) != 32 or {r['task_id'] for r in reviews} != expected:
        raise ValueError('Expected exactly the existing 32 discovery assignments')
    count = 0
    for review in reviews:
        task = tasks[review['task_id']]
        if task['source_ids'] != review['source_ids'] or review['current_status'] != task['status']:
            raise ValueError('Source/status mismatch')
        for evidence in review['evidence']:
            if sha((ROOT / evidence['path']).read_bytes()) != evidence['sha256']:
                raise ValueError('Source evidence changed')
        seen = set()
        for correction in review['corrections']:
            field = correction['field']
            if field not in ALLOWED or field in seen:
                raise ValueError('Disallowed or repeated field')
            seen.add(field)
            obj = task
            parts = field.split('.')
            for key in parts[:-1]:
                obj = obj[key]
            old = obj[parts[-1]]
            new = correction['replace_with']
            if old != correction['old_claim'] or type(old) is not type(new):
                raise ValueError('Old value/type mismatch')
            if field == 'neural_role' and new not in {'input', 'target', 'both'}:
                raise ValueError('Invalid neural role')
            obj[parts[-1]] = new
            count += 1
        task['construction_review'] = {
            'checked_on': proposal['checked_on'], 'disposition': review['disposition'],
            'reason': review['disposition_reason'], 'remaining_gates': review['remaining_gates'],
            'proposal': str(proposal_path.relative_to(ROOT)), 'proposal_sha256': sha(proposal_body),
            'source_evidence': review['evidence'], 'readiness_promoted': False,
        }
    if count != proposal['application_contract']['changes']:
        raise ValueError('Unexpected replacement count')
    for old, new in zip(original['tasks'], changed['tasks']):
        for key in ('id', 'status', 'source_ids', 'task_type', 'task_family'):
            if old[key] != new[key]:
                raise ValueError('Identity/readiness taxonomy changed')
        if old['reference']['reference_executed_for_this_contract'] != new['reference']['reference_executed_for_this_contract']:
            raise ValueError('Execution flag changed')
    changed['summary']['by_neural_role'] = dict(sorted(Counter(r['neural_role'] for r in changed['tasks']).items()))
    changed.setdefault('construction_amendments', []).append({
        'date': proposal['checked_on'], 'proposal': str(proposal_path.relative_to(ROOT)),
        'proposal_sha256': sha(proposal_body), 'prior_roster_sha256': sha(before),
        'assignments': 32, 'field_replacements': count,
        'dispositions': proposal['disposition_counts'], 'readiness_promotions': 0,
        'record': 'receipt.json',
    })
    after = (json.dumps(changed, indent=2, ensure_ascii=False) + '\n').encode()
    record.mkdir(parents=True, exist_ok=False)
    (record / 'roster-before.json').write_bytes(before)
    receipt = {'status': 'prepared', 'proposal_sha256': sha(proposal_body),
        'before_sha256': sha(before), 'after_sha256': sha(after),
        'assignments': 32, 'field_replacements': count, 'readiness_promotions': 0,
        'scientific_executions': 0, 'dispositions': proposal['disposition_counts'],
        'before_roles': original['summary']['by_neural_role'],
        'after_roles': changed['summary']['by_neural_role']}
    (record / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    temporary = record / 'neural_100.amendment.tmp'
    with temporary.open('xb') as f:
        f.write(after)
    temporary.replace(record / 'neural_100.json')
    receipt['status'] = 'staged_for_review'
    receipt['source_roster_modified'] = False
    receipt['generator'] = construction.generator(__file__)
    (record / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
