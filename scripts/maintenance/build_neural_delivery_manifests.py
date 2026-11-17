#!/usr/bin/env python3
"""Build 100 source-bound delivery specifications; never promote execution status."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/neuroscience-benchmarks'
ROSTER = BASE / 'build/neural_100.json'
AUDITS = BASE / 'build/construction_audit_index.json'
OUT = ROOT / 'benchmarks/manifests/neural'


def read(path):
    return json.loads(path.read_text())


def pin(path):
    data = path.read_bytes()
    return {'path': path.relative_to(ROOT).as_posix(), 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()}


def record_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def exact_assets(value, location=''):
    """Retain explicitly recorded asset identities, never infer a payload checksum."""
    found = []
    if isinstance(value, dict):
        if 'asset_id' in value or ('path' in value and any(k in value for k in ('sha256', 'md5', 'digest'))):
            found.append({'source_json_pointer': location or '/', 'record': value,
                          'local_payload_verified_by_this_builder': False})
        else:
            for key, item in value.items():
                found.extend(exact_assets(item, location + '/' + key.replace('~', '~0').replace('/', '~1')))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            found.extend(exact_assets(item, location + '/' + str(i)))
    return found


def generate():
    roster, overlay = read(ROSTER), read(AUDITS)
    tasks = roster['tasks']
    expected = {f'NEURAL-{i:03d}' for i in range(1, 101)}
    if len(tasks) != 100 or {t['id'] for t in tasks} != expected:
        raise ValueError('The canonical neural roster must contain each of its 100 IDs exactly once')
    by_id = {}
    for source in overlay['collections']:
        for task_id in source['assignment_ids']:
            by_id.setdefault(task_id, []).append(source)
    documents = {}
    for task in tasks:
        evidence = [pin(ROSTER), pin(AUDITS)]
        source_records = []
        ledger = task.get('source_audit', {}).get('ledger')
        missing = []
        if ledger:
            path = BASE / ledger
            if path.is_file():
                evidence.append(pin(path))
                document = read(path)
                records = document if isinstance(document, list) else document.get('sources', [])
                for item in records:
                    if not isinstance(item, dict):
                        continue
                    if item.get('id') in task['source_ids']:
                        source_records.append({'source_id': item['id'], 'ledger': ledger,
                                               'record_sha256': record_hash(item),
                                               'data_manifest': item.get('data_manifest'),
                                               'recording_contract': item.get('recording_contract'),
                                               'status': item.get('status')})
            else:
                missing.append('Referenced source ledger is absent locally: ' + ledger)
        audits = by_id.get(task['id'], [])
        for audit in audits:
            path = ROOT / audit['audit_path']
            if not path.is_file():
                raise ValueError('Construction audit missing: ' + str(path))
            evidence.append(pin(path))
        assets = []
        for record in source_records:
            for asset in exact_assets(record.get('data_manifest'), '/data_manifest'):
                assets.append({'source_id': record['source_id'], 'ledger': record['ledger'], **asset})
        if not assets:
            missing.append('No exact input asset record was extracted from the linked readiness manifest; inspect the pinned source audit before acquisition.')
        missing.append('This specification does not establish a local public/private packet, payload equality or an executed task adapter.')
        holds = list(task['exact_remaining_gates'])
        holds.extend({'source_id': a['source_id'], 'construction_gates': a['remaining_gates']} for a in audits)
        actions = [a['construction_implication'] for a in audits if a.get('construction_implication')]
        if not actions:
            actions = [g['requirement'] for g in task['exact_remaining_gates'] if g.get('id') == 'task_specific']
        if not actions:
            actions = [task['exact_remaining_gates'][0]['requirement']]
        documents[task['id']] = {
            'schema_version': 1, 'id': task['id'], 'track': 'neural', 'title': task['title'],
            'status': 'specification_only',
            'source_identity': {'ids': task['source_ids'], 'titles': task['source_titles'],
                                'overlap_groups': task['overlap_group'], 'task_family': task['task_family']},
            'scientific_question': task['scientific_question'], 'task_type': task['task_type'],
            'neural_role': task['neural_role'], 'primary_outputs': [task['target_output']],
            'input_assets': {'routes': task['evidence_urls'], 'readiness_records': source_records,
                             'exact_asset_records': assets, 'missing_or_unverified': missing},
            'allowed_inputs': task['inputs'], 'biological_unit': task['biological_unit'],
            'case_definition': task['case_definition'], 'split': task['split'],
            'reference': task['reference'], 'controls': task['controls'],
            'access_conditions': {'agent_modes': task['agent_modes'],
                                  'common_policy': roster['common_access_policy']},
            'evaluation': {'observable_endpoints': task['primary_metric'],
                           'comparability': task['dependency_note'],
                           'unresolved_grading': [g for g in holds if g.get('id') in ('scorer', 'reference', 'replication', 'protocol')],
                           'executor_ref': None, 'scorer_ref': None},
            'resources': task['proposed_resource_class'], 'holds': holds,
            'next_implementation_action': actions,
            'construction_review': task.get('construction_review'),
            'source_audit_overlays': audits,
            'provenance': {'canonical_record_sha256': record_hash(task),
                           'source_files': list({p['path']: p for p in evidence}.values()),
                           'builder': pin(Path(__file__).resolve()),
                           'new_payload_reads': 0, 'scientific_execution': False},
            'admission': {'runnable': False, 'research_qualified': False,
                          'submission_ready': False,
                          'reason': 'A source specification is not an executed benchmark; runtime adapters are registered separately.'}}
    return documents


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    docs = generate()
    if args.check:
        if {p.stem for p in OUT.glob('*.json')} != set(docs):
            raise ValueError('Generated ID set differs from canonical roster')
        for task_id, value in docs.items():
            if read(OUT / (task_id + '.json')) != value:
                raise ValueError('Stale generated specification: ' + task_id)
    else:
        OUT.mkdir(parents=True, exist_ok=True)
        unexpected = {p.stem for p in OUT.glob('*.json')} - set(docs)
        if unexpected:
            raise ValueError('Unexpected existing specifications: ' + repr(sorted(unexpected)))
        for task_id, value in docs.items():
            (OUT / (task_id + '.json')).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'neural_specifications': len(docs), 'runnable_promotions': 0,
                      'mode': 'checked' if args.check else 'written'}))


if __name__ == '__main__':
    main()
