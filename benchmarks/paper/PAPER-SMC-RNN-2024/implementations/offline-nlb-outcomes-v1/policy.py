"""Bounded metadata for the primary offline SMC/NLB participant interface.

This validates declared identities. Only a trusted operator can authenticate the
underlying reviews, execution, source calibration and pre-candidate freezing.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK = HERE.parent.parent
SOURCE = HERE.parent / 'source-matched-nlb-v1'
SOURCE_HASHES = {
    'scorer.py': '48638a595755138b32ff9c228804fd8c19c9ff874cd254f135fc5245ee9a25f8',
    'delivery.py': 'bf63171f9737e6be6a0c6c7d575c727505f07208cfae6a460876746959a51cf8',
}
CONDITIONS = ('paper_data', 'paper_data_author_code')
PRIMARY_CONTRACT = TASK / 'improvement.temporal-scope.v1.json'
REPRODUCTION_CONTRACT = TASK / 'reproduction.v1.json'
PRIMARY_SHA256 = '5f9aac50d4550908d0cca1ccc704d08e1d423f337ed4cf66a65963617171894d'
REPRODUCTION_SHA256 = 'd616c5c185d9affe390e9818a534d84071b4ae5f54e3cd407edcb777a1161856'
TASK_ID = 'PAPER-SMC-RNN-2024'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def loads_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('nonfinite JSON number: ' + value)
    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid)


def read_json(path):
    return loads_json(Path(path).read_bytes())


def load_source(filename):
    path = SOURCE / filename
    require(sha256(path) == SOURCE_HASHES[filename], 'retained source changed: ' + filename)
    # delivery imports its sibling scorer; pin that dependency before import too.
    require(sha256(SOURCE / 'scorer.py') == SOURCE_HASHES['scorer.py'], 'retained scorer changed')
    spec = importlib.util.spec_from_file_location('_smc_offline_retained_' + filename.replace('.', '_'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def contracts():
    require(sha256(PRIMARY_CONTRACT) == PRIMARY_SHA256, 'primary successor contract changed or not adopted')
    require(sha256(REPRODUCTION_CONTRACT) == REPRODUCTION_SHA256, 'reproduction contract changed or not adopted')
    return {'improvement': PRIMARY_SHA256, 'reproduction': REPRODUCTION_SHA256}


def validate_episode(document, *, primary_hash=PRIMARY_SHA256, reference_hash):
    """Validate a trusted operator's frozen policy; never certify its provenance."""
    require(isinstance(document, dict), 'episode policy must be an object')
    required = {'schema', 'task_id', 'comparison_scope', 'primary_contract_sha256', 'current_task_sha256',
        'reference_panel_sha256', 'paired_delivery_sha256', 'condition_manifest_sha256',
        'materials_policy_sha256', 'selection_adaptation_policy_sha256',
        'resource_budget_policy_sha256', 'scientific_comparison_policy_sha256',
        'trusted_operator_review_sha256', 'author_calibration_receipt_sha256',
        'references', 'selected_reference_id'}
    require(set(document) == required, 'episode policy fields differ from the explicit schema')
    require(document['schema'] == 'smc_offline_episode_policy_v1'
            and document['task_id'] == TASK_ID
            and document['comparison_scope'] == 'original_offline_mc_maze_20ms', 'wrong task or policy scope')
    require(document['primary_contract_sha256'] == primary_hash, 'wrong primary contract')
    require(document['reference_panel_sha256'] == reference_hash, 'wrong complete source panel')
    for key in required:
        if key.endswith('_sha256') and key not in {'condition_manifest_sha256', 'author_calibration_receipt_sha256'}:
            require(digest(document[key]), 'missing/invalid frozen identity: ' + key)
    require(isinstance(document['condition_manifest_sha256'], dict)
            and set(document['condition_manifest_sha256']) == set(CONDITIONS)
            and all(digest(v) for v in document['condition_manifest_sha256'].values()), 'both delivered conditions must be frozen')
    receipts = document['author_calibration_receipt_sha256']
    require(isinstance(receipts, dict) and set(receipts) == {'causal', 'noncausal'}
            and all(digest(v) for v in receipts.values()), 'both source calibration receipts required')
    refs = document['references']
    require(isinstance(refs, list) and len(refs) == 4, 'retain both published and both qualified reproduced references')
    seen, ids = set(), set()
    published = {'causal': 0.3225, 'noncausal': 0.3407}
    for ref in refs:
        require(isinstance(ref, dict) and set(ref) == {'id', 'role', 'arm', 'co_bps', 'source_receipt_sha256'}, 'invalid comparator fields')
        require(isinstance(ref['id'], str) and 0 < len(ref['id']) <= 200 and ref['id'] not in ids, 'duplicate/invalid comparator ID')
        ids.add(ref['id'])
        identity = (ref['role'], ref['arm'])
        require(ref['role'] in {'published', 'qualified_reproduced'} and ref['arm'] in published
                and identity not in seen, 'wrong/duplicate source comparator role')
        seen.add(identity)
        require(type(ref['co_bps']) in (float, int) and math.isfinite(ref['co_bps']), 'invalid comparator value')
        require(digest(ref['source_receipt_sha256']), 'missing comparator evidence')
        if ref['role'] == 'published':
            require(ref['co_bps'] == published[ref['arm']], 'changed published 20-ms anchor')
        else:
            require(ref['source_receipt_sha256'] == receipts[ref['arm']], 'author qualification receipt mismatch')
    selected = [ref for ref in refs if ref['id'] == document['selected_reference_id']]
    require(len(selected) == 1 and selected[0]['co_bps'] == max(ref['co_bps'] for ref in refs),
            'selected comparator is not strongest retained published/reproduced anchor')
    return selected[0]


def load_episode(path, expected_sha256, reference_hash):
    data = Path(path).read_bytes()
    require(digest(expected_sha256) and hashlib.sha256(data).hexdigest() == expected_sha256,
            'episode policy differs from operator-frozen identity')
    document = loads_json(data)
    validate_episode(document, reference_hash=reference_hash)
    return document
