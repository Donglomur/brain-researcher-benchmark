"""Owner-only expected export windows from accepted metadata, before any loader.

Importing this module imports stdlib only. Public construction requires separately
qualified genuine source libraries; this file does not install or qualify them.
It neither opens neural arrays/HDF5 nor observes a model or an existing sampler.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).resolve().parent
OBSERVER_SHA256 = '83ed7d713b11935fb04b6a6d68b6b2f4271e6325a8209064098977fe24016ba3'
SOURCE_CLOSURE_SHA256 = '7b7e5e4ddf00dac9f8d3c7dbe1072488265cdbe4068b7b18db59c28f37164571'
INPUT_MANIFEST_SHA256 = '4d743c1bb4ae91ff73535b22bb45560205741cfcb71ec9d68e859f78f0b0f727'
INPUT_ACCEPTANCE_SHA256 = 'a6b7c7c6871dba74d830e58d9529e599c35624efe3718d9c818b93232fa08d50'
BRAINSET = 'bugeon_transcriptomic_2022'
MODULE_HASHES = {
    'temporaldata.irregular_ts': '1ea8f95435a7be06a974326e6176e9dd6bc3d975ebd0471369e09d2556873adc',
    'temporaldata.interval': 'ec73166b641854246f4b6d91ca44d7f148f3cec41a7a1372473b57c8d1281d6f',
    'torch_brain.data.sampler': '0a21d992b18d223253697451b50687cee2e63c7cbc28bb0b6920d8a96701e0f3',
    'torch_brain.data.dataset': '25350b4b3f54c2729449c65ab3d7d88e8d302250e23e2d8c8e92e5a2024a3532',
}
FULL_SELECTION = [{'selection': [{'brainset': BRAINSET}], 'config': {}}]


class PlanError(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise PlanError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _observer():
    path = HERE.parent / 'export-observer-v1' / 'observer.py'
    body = path.read_bytes()
    need(hashlib.sha256(body).hexdigest() == OBSERVER_SHA256, 'frozen observer differs')
    module = ModuleType('_nuclr_expected_window_observer')
    module.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


def _number(value):
    need(type(value) in (int, float) and math.isfinite(value), 'finite literal clock required')
    return float(value)


def _positive(value, description):
    need(type(value) is int and value > 0, description)
    return value


def _configuration(configuration):
    need(type(configuration) is dict and set(configuration) == {
        'world_size', 'rank', 'context_seconds', 'limit_observation_time', 'dataset_config', 'split',
        'batch_size', 'num_workers', 'checkpoint_epochs'},
        'explicit complete forward configuration required')
    need(type(configuration['world_size']) is int and configuration['world_size'] == 1,
         'only original complete single-rank export supported')
    need(type(configuration['rank']) is int and configuration['rank'] == 0, 'rank zero required')
    need(type(configuration['context_seconds']) in (int, float) and
         configuration['context_seconds'] == 30.0, 'original thirty-second context required')
    need(configuration['limit_observation_time'] is None and configuration['split'] is None,
         'observation crops and split-restricted domains are refused')
    need(configuration['dataset_config'] == FULL_SELECTION,
         'exact whole-brainset selection without modifiers or filters required')
    _positive(configuration['batch_size'], 'explicit positive export batch size required')
    need(type(configuration['num_workers']) is int and configuration['num_workers'] >= 0,
         'explicit nonnegative worker count required')
    need(type(configuration['checkpoint_epochs']) is list and
         all(type(epoch) is int for epoch in configuration['checkpoint_epochs']) and
         configuration['checkpoint_epochs'] == list(range(30)),
         'all default30 checkpoints required; no checkpoint subselection')


def _project_sessions(manifest):
    """Keep source-exported shifted scalars; never redo float32 clock + offset."""
    need(type(manifest) is dict and type(manifest.get('sessions')) is list and manifest['sessions'],
         'complete prepared session metadata required')
    projected = {}
    for session in manifest['sessions']:
        sid = session['session_id']
        need(type(sid) is str and sid and '/' not in sid and sid not in projected,
             'unique ordinary source session identity required')
        count = _positive(session['neurons'], 'positive native column count required')
        frames = _positive(session['frames'], 'positive complete frame count required')
        blocks, previous, cursor, ids = [], None, 0, set()
        need(type(session['experiments']) is list and session['experiments'], 'complete blocks required')
        for index, row in enumerate(session['experiments']):
            eid = row['experiment_id']
            need(type(eid) is str and eid and eid not in ids, 'unique source experiment required')
            ids.add(eid)
            size = _positive(row['frames'], 'positive native block frame count required')
            need(type(row['row_start']) is int and type(row['row_stop']) is int and
                 row['row_start'] == cursor and row['row_stop'] == cursor + size,
                 'source block frame accounting differs')
            need(type(row['source_offset_seconds']) is int and row['source_offset_seconds'] == index * 3600,
                 'original current-release experiment offset differs')
            start, end = _number(row['shifted_first_second']), _number(row['shifted_last_second'])
            need(start <= end and (previous is None or previous <= start),
                 'shifted source clock order differs; no sorting or gap repair')
            gap = None if previous is None else start - previous
            need(row['gap_from_previous_seconds'] == gap and
                 (gap is None or type(row['gap_from_previous_seconds']) in (int, float)),
                 'recorded source gap differs')
            blocks.append({'experiment_id': eid, 'start': start, 'end': end,
                           'frames': size, 'row_start': cursor, 'row_stop': cursor + size})
            previous, cursor = end, cursor + size
        need(cursor == frames, 'all source frames must remain accounted for')
        projected[sid] = {'session_id': sid, 'neurons': count, 'frames': frames, 'blocks': blocks}
    # Official Dataset sorts matching HDF5 stems before inserting recording IDs.
    return [projected[sid] for sid in sorted(projected)]


def _construct(manifest, configuration, runtime, *, max_windows):
    """Private structural-control seam; caller authenticates actual source runtime."""
    _configuration(configuration)
    max_windows = _positive(max_windows, 'finite positive prospective window allowance required')
    sessions = _project_sessions(manifest)
    intervals, units, domains = {}, {}, []
    upper_bound = 0
    for session in sessions:
        rid = BRAINSET + '/' + session['session_id']
        blocks = session['blocks']
        domain = runtime.Interval(blocks[0]['start'], blocks[0]['end'])
        for block in blocks[1:]:
            domain = domain | runtime.Interval(block['start'], block['end'])
        spans = [(float(start), float(end)) for start, end in zip(domain.start, domain.end)]
        need(len(domain.start) == len(domain.end) and spans, 'original union produced no domains')
        need(all(math.isfinite(a) and math.isfinite(b) and a <= b for a, b in spans),
             'original union produced invalid clock domains')
        need(all(spans[i - 1][1] < spans[i][0] for i in range(1, len(spans))),
             'original union is not ordered and disjoint')
        # Bound materialization before calling the original sampler. The original
        # implementation remains authoritative for floating-point enumeration.
        upper_bound += sum(math.ceil((b - a) / 30.0) + 1 for a, b in spans if b - a >= 30.0)
        need(upper_bound <= max_windows, 'prospective window allowance insufficient; no truncation')
        intervals[rid] = domain
        units[rid] = [f"{session['session_id']}_u{i}" for i in range(session['neurons'])]
        domains.append({'recording_id': rid, 'intervals': [[a, b] for a, b in spans]})
    # This is a NEW independent sampler over metadata-derived domains. Neither
    # observed Dataset/sampler/cache nor model/loader state is an input.
    sampler = runtime.SequentialFixedWindowSampler(
        sampling_intervals=intervals, window_length=30.0, step=None, drop_short=True)
    windows = []
    counts = Counter()
    for index in sampler:
        need(len(windows) < max_windows, 'source sampler exceeded prospective window allowance')
        rid, start, end = index.recording_id, float(index.start), float(index.end)
        need(rid in units and math.isfinite(start) and math.isfinite(end) and start < end,
             'source sampler returned an invalid window')
        windows.append({'recording_id': rid, 'start': start, 'end': end})
        counts[rid] += 1
    need(set(counts) == set(units), 'at least one original window per recording required; no exclusions')
    need(len({(r['recording_id'], r['start'].hex(), r['end'].hex()) for r in windows}) == len(windows),
         'source sampler produced duplicate windows')
    return sessions, units, domains, windows, upper_bound


def build_owner_plan(manifest, configuration, runtime, *, runtime_attestation_sha256,
                     max_windows):
    """Return plan/proof in memory, requiring later independent freeze/readback.

    The outer admitted operation must supply qualified installed modules and
    authenticate this receipt's runtime attestation. A caller-supplied hash alone
    is not runtime qualification. No authentic operation is authorized here.
    """
    observer = _observer()
    need(digest(manifest) == INPUT_MANIFEST_SHA256, 'exact accepted complete input manifest required')
    need(_sha(runtime_attestation_sha256), 'separate genuine runtime attestation required')
    need(type(runtime.modules) is dict and set(runtime.modules) == set(MODULE_HASHES),
         'complete actual runtime source modules required')
    for name, expected in MODULE_HASHES.items():
        module = runtime.modules[name]
        need(isinstance(module, ModuleType) and module.__name__ == name, 'loaded module identity differs')
        observer.read_source(module.__file__, expected)
    need(runtime.Interval is runtime.modules['temporaldata.interval'].Interval and
         runtime.SequentialFixedWindowSampler is
         runtime.modules['torch_brain.data.sampler'].SequentialFixedWindowSampler,
         'runtime constructors differ from authenticated source modules')
    sessions, units, domains, windows, upper_bound = _construct(
        manifest, configuration, runtime, max_windows=max_windows)
    totals = {'sessions': len(sessions), 'blocks': sum(len(s['blocks']) for s in sessions),
              'frames': sum(s['frames'] for s in sessions),
              'neuron_observations': sum(s['neurons'] for s in sessions)}
    need(totals == {'sessions': 17, 'blocks': 69, 'frames': 500491, 'neuron_observations': 10153},
         'complete original population required')
    proof = {
        'schema': 'nuclr-metadata-derived-forward-window-proof-v1',
        'input_manifest_sha256': INPUT_MANIFEST_SHA256,
        'input_acceptance_sha256': INPUT_ACCEPTANCE_SHA256,
        'source_closure_sha256': SOURCE_CLOSURE_SHA256,
        'runtime_source_bindings': dict(MODULE_HASHES),
        'runtime_attestation_sha256': runtime_attestation_sha256,
        'configuration': deepcopy(configuration),
        'ordered_endpoint_projection': sessions,
        'original_union_domains': domains,
        'expected_windows_sha256': digest(windows),
        'expected_window_count': len(windows),
        'expected_windows_by_recording': dict(Counter(row['recording_id'] for row in windows)),
        'expected_batches_per_checkpoint': math.ceil(len(windows) / configuration['batch_size']),
        'source_short_intervals': [
            {'recording_id': row['recording_id'], 'start': start, 'end': end}
            for row in domains for start, end in row['intervals'] if end - start < 30.0],
        'prospective_window_upper_bound': upper_bound,
        'totals': totals,
        'observed_sampler_or_model_used': False,
        'all_frames_or_tokenizer_membership_proved': False,
        'independent_saved_review_required': True,
    }
    plan = {
        'schema': 'nuclr-complete-forward-window-plan-v1',
        'source_commit': observer.SOURCE_COMMIT,
        'source_bindings': dict(observer.SOURCE_HASHES),
        'world_size': 1, 'context_seconds': 30.0,
        'input_manifest_sha256': INPUT_MANIFEST_SHA256,
        'input_acceptance_sha256': INPUT_ACCEPTANCE_SHA256,
        'units_by_recording': units, 'windows': windows,
        'independent_roster_proof_sha256': digest(proof),
    }
    observer._full_plan(plan, digest(plan))
    return plan, proof
