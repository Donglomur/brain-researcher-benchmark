"""Five-seed Bugeon panel summary from complete owner-side readout outputs.

No fitting, source payload loading or execution authentication is performed.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from types import ModuleType

EVALUATOR_SHA256 = '36706ae9e37fcfeae0ed46740f3c5601c13052fe316ba164bf2d22f64aed6797'
METRICS = ('macro_f1', 'balanced_accuracy', 'accuracy')


class SummaryError(ValueError):
    """Incomplete, incompatible or internally inconsistent seed results."""


def need(condition, message):
    if not condition:
        raise SummaryError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def _sha(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _evaluator(implementation_root=None):
    root = Path(implementation_root) if implementation_root else Path(__file__).resolve().parent.parent
    path = root / 'initial-evaluator-v1' / 'evaluator.py'
    body = path.read_bytes()
    need(hashlib.sha256(body).hexdigest() == EVALUATOR_SHA256, 'frozen evaluator differs')
    module = ModuleType('_nuclr_seed_summary_evaluator')
    module.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


def _panel_identity(packet):
    # Checkpoint IDs are local to a training run; epochs and literal row order
    # still match. Feature values may differ across independently trained seeds.
    identity = {key: value for key, value in packet.items() if key != 'checkpoints'}
    identity['checkpoint_schedule'] = [
        {'epoch': row['epoch'], 'ids': row['ids'], 'width': len(row['embeddings'][0])}
        for row in packet['checkpoints']]
    return identity


def _verify_result(packet, result, evaluator):
    spec = evaluator.validate_packet(packet)
    need(type(result) is dict, 'readout result object required')
    expected = {'schema_version': 1, 'task_id': evaluator.TASK_ID,
                'source_commit': evaluator.SOURCE_COMMIT, 'component': 'initial-evaluator-v1',
                'status': 'engineering_readout_only', 'contract_sha256': evaluator.CONTRACT_SHA256,
                'input_role': packet['input_role'], 'panel': packet['panel'],
                'label_level': packet['label_level'], 'context_variant': packet['context_variant'],
                'source_label_mapping': packet['source_label_mapping'],
                'packet_sha256': digest(packet), 'provenance': packet['provenance'],
                'research_qualified': False, 'full_contract_complete': False,
                'aggregation': 'concatenated selected test predictions; repeated split appearances retain source weight'}
    need(all(key in result and digest(result[key]) == digest(value) for key, value in expected.items()),
         'result identity, packet binding or engineering status differs')
    records = result.get('records')
    need(type(records) is list and all(type(row) is dict for row in records), 'granular test records required')
    expected_rows = [(split['id'], uid) for split in spec['splits']
                     for uid in spec['ordered_ids'] if uid in split['test']]
    need([(row.get('split_id'), row.get('unit_id')) for row in records] == expected_rows,
         'complete original test records in source order required')
    for row in records:
        uid = row['unit_id']
        need(row.get('true') == spec['label_map'][uid] and
             row.get('subject_id') == spec['metadata'][uid]['subject_id'].lower(),
             'test target or subject differs from packet')
    metrics = evaluator.classification_metrics([row['true'] for row in records],
                                               [row.get('pred') for row in records], spec['vocabulary'])
    need(result.get('metrics') == metrics, 'reported pooled metrics differ from granular predictions')
    selected = result.get('selected')
    need(type(selected) is list and len(selected) == len(spec['splits']), 'one selected checkpoint per split required')
    for split, selection in zip(spec['splits'], selected):
        need(type(selection) is dict and selection.get('split_id') == split['id'], 'selected split order differs')
        cv = selection.get('cv_metrics')
        need(type(cv) is list and len(cv) == len(packet['checkpoints']) and
             all(type(row) is dict and type(row.get('macro_f1')) in (int, float) and
                 math.isfinite(row['macro_f1']) and 0 <= row['macro_f1'] <= 1 for row in cv),
             'complete finite checkpoint CV scores required')
        best = max(range(len(cv)), key=lambda index: cv[index]['macro_f1'])
        checkpoint = packet['checkpoints'][best]
        need(type(selection.get('checkpoint_index')) is int and selection['checkpoint_index'] == best and
             selection.get('checkpoint_id') == checkpoint['id'] and selection.get('epoch') == checkpoint['epoch'],
             'selected checkpoint differs from highest CV macro-F1 and earliest tie')
        subset = [row for row in records if row['split_id'] == split['id']]
        split_metrics = evaluator.classification_metrics([row['true'] for row in subset],
                                                         [row['pred'] for row in subset], spec['vocabulary'])
        need(selection.get('test_metrics') == split_metrics, 'selected split test metrics differ')
    expected_fits = sum(len(packet['checkpoints']) * len(split['cv']) + 1 for split in spec['splits'])
    need(type(result.get('resources')) is dict and
         type(result['resources'].get('readout_fits')) is int and
         result['resources']['readout_fits'] == expected_fits, 'source readout fit count differs')
    return metrics


def summarize_panel(runs, *, seed_roster, method_sha256, protocol_sha256, implementation_root=None):
    """Summarize exactly five declared seeds, preserving one complete panel.

    Each run contains seed, training_run_sha256, packet and readout_result. The
    caller retains those owner-only inputs. Hash declarations do not prove
    independent training, predeclaration, actual fits or authentic source data.
    """
    need(type(seed_roster) is list and len(seed_roster) == 5 and
         all(type(seed) is int and seed >= 0 for seed in seed_roster) and len(set(seed_roster)) == 5,
         'exactly five distinct explicit training seeds required')
    need(_sha(method_sha256) and _sha(protocol_sha256), 'declared method and protocol SHA256 required')
    need(type(runs) is list and len(runs) == 5 and all(type(run) is dict for run in runs),
         'all five complete seed runs required; no missing-run averaging')
    need(all(type(run.get('seed')) is int for run in runs) and
         len({run['seed'] for run in runs}) == 5 and {run['seed'] for run in runs} == set(seed_roster),
         'run seeds must exactly match the declared roster')
    need(all(_sha(run.get('training_run_sha256')) for run in runs) and
         len({run['training_run_sha256'] for run in runs}) == 5,
         'five distinct declared training run identities required')
    evaluator = _evaluator(implementation_root)
    by_seed = {run['seed']: run for run in runs}
    rows, shared = [], None
    for seed in seed_roster:
        run = by_seed[seed]
        packet, result = run.get('packet'), run.get('readout_result')
        metrics = _verify_result(packet, result, evaluator)
        identity = _panel_identity(packet)
        if shared is None:
            shared = identity
        need(identity == shared, 'seeds must share panel, source splits, labels, exposure and checkpoint schedule')
        rows.append({'seed': seed, 'training_run_sha256': run['training_run_sha256'],
                     'packet_sha256': digest(packet), 'readout_result_sha256': digest(result),
                     'test_record_count': metrics['n'],
                     'metrics': {key: metrics[key] for key in METRICS},
                     'selected_checkpoints': [{key: row[key] for key in
                         ('split_id', 'checkpoint_id', 'checkpoint_index', 'epoch')} for row in result['selected']]})
    summary = {}
    for metric in METRICS:
        values = [row['metrics'][metric] for row in rows]
        mean = math.fsum(values) / 5
        squares = math.fsum((value - mean) ** 2 for value in values)
        summary[metric] = {'mean': mean, 'descriptive_seed_sd_ddof0': math.sqrt(squares / 5),
                           'descriptive_seed_sd_ddof1': math.sqrt(squares / 4)}
    return {'schema': 'nuclr-five-seed-panel-summary-v1', 'task_id': evaluator.TASK_ID,
            'status': 'engineering_seed_summary_only', 'source_commit': evaluator.SOURCE_COMMIT,
            'evaluator_sha256': EVALUATOR_SHA256, 'panel': shared['panel'], 'label_level': shared['label_level'],
            'context_variant': shared['context_variant'], 'input_role': shared['input_role'],
            'method_sha256': method_sha256, 'protocol_sha256': protocol_sha256,
            'panel_identity_sha256': digest(shared), 'seed_roster': list(seed_roster), 'seed_count': 5,
            'runs': rows, 'metrics': summary, 'primary_metric': 'macro_f1',
            'aggregation': 'arithmetic mean of five seed-level pooled-test metrics; no cross-seed prediction pooling',
            'paper_dispersion_convention_verified': False, 'execution_verified': False,
            'training_independence_verified': False, 'research_qualified': False, 'full_contract_complete': False,
            'holds': list(evaluator.HOLDS) + [
                'Declared method/protocol/run hashes require separate execution and predeclaration evidence.',
                'CV predictions are not included in the legacy output; CV scores and actual fits are not recomputed.',
                'Both SD denominators are descriptive; the historical seed roster and paper dispersion convention remain unresolved.',
                'No biological confidence interval, equivalence tolerance, meaningful effect or improvement decision is calculated.']}
