#!/usr/bin/env python3
"""Build 100 source-qualified paper delivery specifications, not runnable tasks.

Metadata only: no network, scientific imports, payload reads or subprocesses.
The canonical roster remains unchanged. --check compares deterministic bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
ROSTER = 'docs/neuroscience-benchmarks/build/paper_100.json'
AUDIT = 'docs/neuroscience-benchmarks/build/paper_construction_audit.json'
DESTINATION = 'benchmarks/manifests/paper'
INDEX = 'benchmarks/manifests/paper_index.json'
SAFE_ID = re.compile(r'PAPER-[A-Za-z0-9_-]+\Z')
DATA_KEYS = ('data_inputs', 'input_inventory', 'input_assets', 'data_manifest',
             'data_metadata', 'input_version', 'input_code_bridge', 'archive_directory_inspection')
ASSET_FIELDS = {'name', 'path', 'filename', 'key', 'id', 'asset_id', 'identifier',
                'url', 'download_url', 'contentUrl', 'bytes', 'size', 'file_size',
                'content_length', 'observed_content_length_bytes', 'checksum',
                'sha256', 'md5', 'computed_md5', 'digest', 'etag', 'sha', 'version',
                'mimeType', 'mimetype', 'role', 'is_link_only', 'links', 'encodingFormat',
                'payload_sha256', 'actual_schema_verified', 'files_downloaded'}
CODE_KEYS = {'official_code', 'code', 'code_files', 'entrypoints', 'source_files',
             'file_tree', 'dependencies', 'code_inspection', 'official_reference_code'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode()


def record_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def file_pin(root, relative):
    p = Path(relative)
    require(not p.is_absolute() and '..' not in p.parts, 'repository-relative provenance path')
    path = root / p
    require(path.is_file() and not path.is_symlink(), 'missing/linked provenance: ' + relative)
    # Only metadata/source evidence files are hashed; never recording payloads.
    require(path.suffix.lower() not in {'.npz', '.npy', '.mat', '.h5', '.hdf5', '.nwb', '.pdf', '.zip'},
            'payload is not a metadata provenance source')
    body = path.read_bytes()
    return {'path': relative, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def load(root, relative):
    return json.loads((root / relative).read_text(),
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def records(value):
    if isinstance(value, list):
        return value
    require(isinstance(value, dict), 'record document must be object or list')
    for key in ('records', 'tasks', 'papers', 'projects', 'sources'):
        if isinstance(value.get(key), list):
            return value[key]
    raise ValueError('no record list in source document')


def pointer(part):
    return str(part).replace('~', '~0').replace('/', '~1')


def asset_records(value, location='', in_files=False):
    """Retain exact saved asset fields; never reinterpret an ETag/digest as SHA.

    The input is restricted to data sections. Some archives mix code, outputs and
    empirical inputs: each emitted row remains an inventory item, not an admitted
    input. Its role must be resolved against the scientific scope.
    """
    result = []
    if isinstance(value, dict):
        ident = any(k in value for k in ('name', 'path', 'filename', 'key', 'asset_id'))
        detail = any(k in value for k in ('bytes', 'size', 'file_size', 'checksum', 'digest',
                                         'sha256', 'md5', 'computed_md5', 'url', 'download_url',
                                         'asset_id', 'observed_content_length_bytes'))
        if ident and (detail or in_files):
            fields = {k: v for k, v in value.items() if k in ASSET_FIELDS}
            if fields:
                checksums = {k: value[k] for k in ('sha256', 'payload_sha256', 'md5',
                    'computed_md5', 'checksum', 'digest', 'etag') if k in value}
                result.append({'json_pointer': location or '/', 'recorded_fields': fields,
                    'checksum_fields_as_recorded': checksums,
                    'content_sha256_explicit': value.get('sha256', value.get('payload_sha256')),
                    'role': 'saved_inventory_item_not_automatically_selected_empirical_input'})
        for key, child in value.items():
            if key in CODE_KEYS:
                continue
            if isinstance(child, (dict, list)):
                result.extend(asset_records(child, location + '/' + pointer(key),
                    in_files or key in ('files', 'assets', 'file_metadata_examples', 'representative_files', 'inventory')))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.extend(asset_records(child, location + '/' + str(index), in_files))
    return result


def distinct(values):
    seen = set(); out = []
    for value in values:
        key = record_hash(value)
        if key not in seen:
            out.append(value); seen.add(key)
    return out


def source_sections(record):
    return {k: record[k] for k in DATA_KEYS if k in record}


def scalar_sections(record, keys):
    return {k: record[k] for k in keys if k in record}


def next_action(value):
    if isinstance(value, str):
        return value
    require(isinstance(value, dict) and isinstance(value.get('action'), str), 'concrete next action missing')
    return value['action']


def build_documents(root=ROOT, expected_count=100):
    roster_doc, audit = load(root, ROSTER), load(root, AUDIT)
    roster, audited = records(roster_doc), records(audit)
    ids = [r['id'] for r in roster]
    require(len(ids) == expected_count and len(set(ids)) == expected_count, 'canonical count/uniqueness')
    require(all(isinstance(i, str) and SAFE_ID.fullmatch(i) for i in ids), 'unsafe canonical ID')
    require([r['id'] for r in audited] == ids, 'audit must cover canonical IDs in exact order')
    common_pins = {'canonical_roster': file_pin(root, ROSTER), 'construction_audit': file_pin(root, AUDIT)}
    cache = {}; pin_cache = {}; docs = {}
    def pinned_evidence(path):
        if path not in pin_cache:
            current_pin = file_pin(root, path)
            declared = audit.get('source_pins', {}).get(path)
            if declared:
                require(all(current_pin[k] == declared[k] for k in ('bytes', 'sha256')),
                        'construction audit source pin is stale: ' + path)
            pin_cache[path] = current_pin
        return pin_cache[path]
    current = audit.get('current_reference_summary', {})
    empirical = set(current.get('bounded_empirical_reference_ids', []))
    generated = set(current.get('generated_diagnostics_only_ids', []))
    require(not (empirical & generated) and empirical | generated <= set(ids), 'reference classification IDs')
    for index, (row, item) in enumerate(zip(roster, audited)):
        identifier = row['id']
        require(item['source_id'] == row['source_id'] and item['title'] == row['title'], 'paper identity drift')
        primary = row.get('central_reproduction_outputs')
        require(isinstance(primary, list) and primary and all(isinstance(x, str) and x.strip() for x in primary),
                'missing task-specific central outputs: ' + identifier)
        sources = []; asset_rows = []; source_details = []; code_details = []; metrics = []; pins = []
        for evidence in item.get('evidence', []):
            path = evidence['path']
            loc = {'file': pinned_evidence(path), 'record_id': evidence.get('record_id'),
                   'declared_record_sha256': evidence.get('record_sha256'), 'role': evidence.get('role')}
            # Readiness JSON is source metadata. Other evidence is hash-linked,
            # never parsed for numerical outputs or counted as new execution.
            if '/readiness/' in path and path.endswith('.json') and evidence.get('record_id'):
                if path not in cache: cache[path] = records(load(root, path))
                matches = [(i, r) for i, r in enumerate(cache[path]) if r.get('id') == evidence['record_id']]
                if not matches and evidence['record_id'] == row['source_id'] + ' source_provenance':
                    matches = [(i, r) for i, r in enumerate(cache[path])
                        if r.get('source_provenance', {}).get('paper_record_id') == row['source_id']]
                    loc['resolution'] = 'explicit source_provenance.paper_record_id cross-reference'
                require(len(matches) == 1, 'unique source record missing: ' + path + '#' + str(evidence['record_id']))
                source_index, rec = matches[0]
                loc.update(record_index=source_index, record_sha256=record_hash(rec))
                if evidence.get('record_sha256'):
                    require(loc['record_sha256'] == evidence['record_sha256'], 'construction audit source record is stale')
                sections = source_sections(rec)
                for key, value in sections.items():
                    for asset in asset_records(value, '/' + pointer(key)):
                        asset_rows.append({**asset, 'source_file': path, 'source_record_id': rec['id']})
                source_details.append({'source_file': path, 'record_id': rec['id'],
                    'versions_and_loader_contract': scalar_sections(rec, ('input_version', 'input_code_bridge', 'data_contract',
                        'scope_description', 'readiness_scope', 'declared_scope', 'missing_core_inputs', 'unresolved_coverage')),
                    'data_section_locators': list(sections)})
                code_details.append({'source_file': path, 'record_id': rec['id'],
                    'recorded': scalar_sections(rec, ('official_code', 'code_url', 'code_revision', 'code_revision_or_archive_version',
                        'entrypoints', 'dependencies', 'official_reference_code'))})
                if 'metrics' in rec:
                    metrics.append({'source_file': path, 'record_id': rec['id'], 'recorded_metrics': rec['metrics']})
            sources.append(loc)
        # The integrated audit often contains a smaller, reconciled manifest not
        # present in the original readiness entry. Preserve its role explicitly.
        lineage = item['input_and_code_lineage']
        for asset in asset_records(lineage, '/input_and_code_lineage'):
            asset_rows.append({**asset, 'source_file': AUDIT, 'source_record_id': identifier})
        followups = [x for x in audit.get('subsequent_work_overlays', []) if x.get('id') == identifier]
        for overlay in followups:
            path = overlay['path']
            pins.append({**overlay, 'source_pin': pinned_evidence(path)})
        holds = [x for x in audit.get('current_construction_holds', []) if x.get('id') == identifier]
        reconciliations = [x for x in audit.get('conflicts_and_reconciliations', []) if x.get('id') == identifier]
        reconciliation_refs = []
        for rec in reconciliations:
            path = rec['path']
            detail = rec.get('detail', {})
            reconciliation_refs.append({'type': rec['type'], 'source_pin': pinned_evidence(path),
                'conclusion': detail.get('conclusion'), 'remaining_gates': detail.get('remaining_gates', [])})
            if 'older_source_route' in detail:
                for asset in asset_records(detail['older_source_route'].get('files', []), '/older_source_route/files', True):
                    asset_rows.append({**asset, 'source_file': path, 'source_record_id': identifier})
        ref_current = ('bounded_empirical_reference_linked_scope_only' if identifier in empirical else
                       'generated_diagnostics_only' if identifier in generated else 'no_empirical_reference_established')
        historical_action = next_action(item['next_action'])
        plan_action = historical_action
        action_basis = 'integrated task-specific audit action'
        if holds:
            current_gates = [gate for hold in holds for gate in hold.get('remaining_gates', [])]
            if current_gates:
                plan_action = 'Resolve the current scientific hold before a reference run: ' + ' '.join(current_gates)
                action_basis = 'current_construction_holds overrides a historical intake action'
        if identifier == 'PAPER-paper-signal-add-020' and identifier in empirical:
            plan_action = ('Validate independent participant/trial alignment of the row-ordered ERP feature tables, '
                'then construct a sanitized conditional mixed-effects reproduction packet and an independent coefficient/contrast scorer. '
                'Reuse the linked three-fit reference and arithmetic audit; do not repeat intake as if no reference existed. '
                'Keep raw-to-ERP extraction and an independent improvement panel as separate unresolved scopes.')
            action_basis = 'completed ERP reference overlay plus unchanged source-specific alignment/full-contract gates'
        require(plan_action.strip(), 'empty implementation action')
        rights = item.get('exposure_and_rights', item.get('rights_and_exposure', {}))
        document = {
            'schema_version': 1, 'id': identifier, 'source_id': row['source_id'], 'track': 'paper',
            'title': row['title'], 'status': 'specification_only', 'canonical_position_one_based': index + 1,
            'paper_identity': {'url': row['paper_url'], 'publication_year': row.get('publication_year'), 'venue': row.get('venue')},
            'primary_outputs': primary,
            'input_assets': {'routes': row.get('data_urls', []), 'exact_asset_records': distinct(asset_rows),
                'lineage_and_loader_evidence': lineage, 'source_contract_locators': source_details,
                'selection_status': 'inventory_items_require_claim_specific_selection_not_all_are_inputs',
                'checksum_interpretation': 'Explicit sha256 fields retained; checksum/digest/ETag names are not silently reinterpreted. None means unrecorded, not verified.',
                'acquired_or_schema_validated_by_this_generator': False},
            'official_code': {'url': row.get('code_url'), 'revision_or_archive_version': row.get('code_revision_or_archive_version'),
                'entrypoints': row.get('entrypoints', []), 'source_details': code_details,
                'lineage_limit': 'Author/source code meaning is preserved. A loader, demo, figure script and complete-paper implementation are not interchangeable.'},
            'access_conditions': {'conditions': row.get('paired_access_conditions', []),
                'common': ['the same versioned paper and approved empirical inputs', 'the same task/assessment and declared noncode resources'],
                'code_condition_extra': 'Only the approved official-code snapshot. Dependencies and noncode resources must be declared equally. No operator verifier, private labels, reference answers or other-attempt history.',
                'release_status': 'candidate-specific_public_packets_not_registered',
                'source_specific_rights_and_exposure': rights,
                'comparison_limit': 'Public paper/results and data exposure are retained. No blind, causal code-benefit or compute-equivalence claim is established.'},
            'evaluation': {'observable_endpoints': item['documented_endpoint'], 'source_recorded_metrics': metrics,
                'comparability': item['comparability_gates'],
                'unresolved_grading': {'task_specific_gates': item['remaining_gates'],
                    'meaning': 'Endpoint documentation is not a frozen numeric target, tolerance, independently verified grader or difficulty qualification.'},
                'executor_ref': None, 'scorer_ref': None, 'binary_reward_registered': False},
            'reproduction_evidence': {'historical': item['reference_execution_status'],
                'historical_integration_classification': item.get('integration_classification'),
                'current_classification': ref_current, 'current_followups': pins,
                'reconciliations': reconciliation_refs,
                'scope': 'Existing bounded evidence only; no new runtime and no whole-paper qualification inferred.'},
            'improvement': {'proposal': row.get('improvement_outputs', []),
                'independent_panel_and_evaluation_status': item['improvement_evaluation_status'], 'qualified': False},
            'resources': item['resource_evidence'],
            'holds': {'task_specific': item['remaining_gates'], 'current_construction_holds': holds,
                'source_route_reconciliations': reconciliation_refs},
            'next_implementation_action': {'action': plan_action, 'basis': action_basis,
                'historical_audit_action': historical_action, 'execution_authorized_by_manifest': False,
                'when_prior_action_has_completed': 'Consult linked current followups and holds before repeating a historical action; no automatic retry or source-state overwrite.'},
            'provenance': {**common_pins, 'canonical_record_sha256': record_hash(row),
                'audit_record_sha256': record_hash(item), 'source_records_and_files': sources,
                'historical_pin_exceptions': [],
                'interpretation': 'Pins bind saved local evidence. Asset hashes are source-reported unless an explicit acquisition receipt says otherwise.'},
            'admission': {'runnable': False, 'research_qualified': False, 'full_contract_complete': False,
                'delivery_unit': 'one_canonical_paper_source_specification', 'new_scientific_runs': 0}}
        # Exceptions concern specific historical global exposure pins; preserve
        # their compact declarations, not the full multi-page reconciliation.
        document['provenance']['historical_pin_exceptions'] = [x for x in audit.get('conflicts_and_reconciliations', [])
            if x.get('type') == 'historical_pin_superseded' and item.get('origin_batch', {}).get('name') == x.get('origin_batch')]
        validate_document(document)
        docs[identifier] = document
    return docs


def validate_document(doc):
    require(doc.get('schema_version') == 1 and SAFE_ID.fullmatch(doc.get('id', '')), 'schema/id')
    require(doc.get('track') == 'paper' and doc.get('status') == 'specification_only', 'source specification only')
    require(isinstance(doc.get('title'), str) and doc['title'].strip(), 'title')
    for key in ('input_assets', 'evaluation', 'resources', 'holds', 'next_implementation_action', 'provenance', 'admission'):
        require(isinstance(doc.get(key), dict), 'object required: ' + key)
    require(isinstance(doc.get('primary_outputs'), list) and doc['primary_outputs'], 'central outputs')
    require(doc['evaluation'].get('executor_ref') is None and doc['evaluation'].get('scorer_ref') is None,
            'cannot register unqualified executor/scorer')
    require(doc['admission'].get('runnable') is False and doc['admission'].get('research_qualified') is False,
            'no readiness promotion')
    require(bool(doc['next_implementation_action'].get('action')), 'task-specific next action')


def write_or_check(root=ROOT, check=False):
    docs = build_documents(root)
    directory = root / DESTINATION
    expected = {identifier + '.json' for identifier in docs}
    if directory.exists():
        extra = {p.name for p in directory.iterdir()} - expected
        require(not extra, 'unexpected output entries; do not delete automatically: ' + str(sorted(extra)))
    outputs = {DESTINATION + '/' + identifier + '.json': encode(doc) for identifier, doc in docs.items()}
    index = {'schema_version': 1, 'track': 'paper', 'status': 'specification_only', 'count': len(docs),
        'runnable_count': 0, 'research_qualified_count': 0,
        'meaning': '100 canonical source/asset/reproduction specifications; not 100 executable benchmarks.',
        'generator': file_pin(root, 'tools/build_paper_delivery_manifests.py'),
        'documents': [{'id': identifier, 'path': DESTINATION + '/' + identifier + '.json',
                       'bytes': len(outputs[DESTINATION + '/' + identifier + '.json']),
                       'sha256': hashlib.sha256(outputs[DESTINATION + '/' + identifier + '.json']).hexdigest()}
                      for identifier in docs]}
    outputs[INDEX] = encode(index)
    stale = []
    for name, body in outputs.items():
        path = root / name
        if check:
            if not path.is_file() or path.read_bytes() != body: stale.append(name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
    require(not stale, 'generated manifests stale or missing: ' + ', '.join(stale))
    return {'status': 'current' if check else 'written', 'paper_specifications': len(docs),
            'runnable': 0, 'research_qualified': 0, 'bytes': sum(len(b) for b in outputs.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(write_or_check(check=args.check), indent=2))
    except (ValueError, KeyError, TypeError, OSError) as error:
        print('paper delivery validation failed: ' + str(error), file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__': main()
