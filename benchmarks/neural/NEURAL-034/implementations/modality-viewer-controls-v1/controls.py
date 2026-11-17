"""Matched modality projections and operator replay; no participant transport.

Only the selected modality reaches the renderer. Source packets, fold identity
and histories remain trusted-operator objects. The existing combined transport
does not accept these new condition histories, and is not modified here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib.util
import math
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CONDITIONS = {
    'combined_calcium_behavior_v1': ('calcium', 'behavior'),
    'calcium_only_v1': ('calcium',),
    'behavior_only_v1': ('behavior',),
}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def dependencies():
    import hashlib
    import json
    bindings = json.loads((HERE / 'SOURCE_BINDINGS.json').read_text())
    expected = {
        'benchmarks/neural/NEURAL-034/implementations/viewer-transport-v1/transport.py',
        'benchmarks/neural/NEURAL-034/implementations/viewer-transport-v1/SOURCE_BINDINGS.json',
    }
    need(set(bindings) == {'schema', 'members'} and
         bindings['schema'] == 'neural034-modality-control-dependencies/v1' and
         set(bindings['members']) == expected, 'Exact prior transport dependency closure')
    for relative, pin in bindings['members'].items():
        body = (ROOT / relative).read_bytes()
        need(set(pin) == {'bytes', 'sha256'} and type(pin['bytes']) is int and
             len(body) == pin['bytes'] and hashlib.sha256(body).hexdigest() == pin['sha256'],
             'Prior transport source changed')
    transport = load('neural034_modality_prior_transport', HERE.parent / 'viewer-transport-v1' / 'transport.py')
    raster, renderer, _inputs, ids = transport.v.dependencies()
    return transport, raster, renderer, ids


T, RASTER, BASE_RENDERER, IDS = dependencies()
V = T.v
RENDERER = load('neural034_modality_renderer', HERE / 'render.py')


def select(condition):
    need(type(condition) is str and condition in CONDITIONS, 'Explicit known modality condition required')
    return CONDITIONS[condition]


def source_identity():
    return {name: {'bytes': len(body), 'sha256': T.digest(body)}
            for name in ('controls.py', 'render.py', 'SOURCE_BINDINGS.json')
            for body in (T.read_body(HERE / name, 256 * 1024),)}


def prompt(condition):
    modalities = select(condition)
    old = 'Each image shows all 300 samples of 12 selected author-processed calcium traces plus aligned binary behavior.'
    new = {
        ('calcium', 'behavior'): old,
        ('calcium',): 'Each image shows all 300 samples of 12 selected author-processed calcium traces. The behavior lane is unavailable in this condition.',
        ('behavior',): 'Each image shows all 300 samples of aligned binary behavior. The 12 calcium lanes are unavailable in this condition.',
    }[modalities]
    return V.PROMPT.replace(old, new)


def mode(condition):
    return V.MODE if condition == 'combined_calcium_behavior_v1' else 'active_fold_' + condition


@dataclass(frozen=True)
class Selection:
    condition: str
    limits: T.Limits

    def __post_init__(self):
        select(self.condition)
        need(type(self.limits) is T.Limits, 'Existing explicit matched Limits required')
        self.limits.validate()


class ProjectedPacket:
    """Operator-only view: never call Packet.observation, which reads both arms."""

    def __init__(self, packet, condition):
        self._packet, self._modalities = packet, select(condition)
        need(type(packet.fold) is int and packet.fold in IDS and packet.ids == IDS[packet.fold],
             'Exact complete original active-fold identities required')
        self.fold, self.ids = packet.fold, list(packet.ids)

    def observation(self, role, index):
        need(role in ('training', 'query') and type(index) is int and
             0 <= index < (V.TRAIN if role == 'training' else V.QUERIES), 'Active observation outside support')
        prefix = 'train' if role == 'training' else 'query'
        record = {'role': role, 'index': index}
        arrays = self._packet.arrays
        if 'calcium' in self._modalities:
            record['windows'] = arrays[prefix + '_windows'][index]
        if 'behavior' in self._modalities:
            record['behavior'] = arrays[prefix + '_behavior'][index]
        if role == 'training':
            record['label'] = int(arrays['train_labels'][index])
        return record


def ready_header(selection, episode):
    need(type(selection) is Selection and type(episode) is str and
         re.fullmatch('[0-9a-f]{32}', episode), 'Exact selection and opaque episode identity required')
    # The prior function does not inspect its packet argument.
    header = T.ready_header(None, selection.limits, episode)
    header.update(condition=selection.condition, mode=mode(selection.condition),
                  visible_modalities=list(select(selection.condition)), prompt=prompt(selection.condition))
    return header


def projection(response, expected_condition):
    modalities = select(expected_condition)
    need(type(response) is dict and response.get('condition') == expected_condition and
         response.get('visible_modalities') == list(modalities), 'Response condition mismatch')
    original = {key: value for key, value in response.items()
                if key not in ('condition', 'visible_modalities')}
    if original.get('kind') == 'view':
        need(original.get('mode') == mode(expected_condition), 'View mode differs from condition')
        constants = {'samples': 300, 'cells': 12 if 'calcium' in modalities else 0,
                     'sample_rate_hz': 10, 'window_seconds': 30,
                     'first_sample_seconds': 0.05, 'last_sample_seconds': 29.95}
        need(all(type(original.get(k)) is type(v) and original[k] == v for k, v in constants.items()),
             'Matched observation geometry required')
        flags = original.get('clipped_cells')
        need(type(flags) is list and all(type(i) is int and 1 <= i <= 12 for i in flags) and
             flags == sorted(set(flags)), 'Exact visible calcium clipping flags required')
        need('calcium' in modalities or flags == [], 'Excluded calcium statistics refused')
        gain = original.get('gain_units_per_division')
        need(type(gain) in (int, float) and math.isfinite(gain) and 2**-20 <= gain <= 2**60,
             'Declared display gain required')
        role = original.get('role')
        need(role in ('training', 'query') and type(original.get('index')) is int and
             0 <= original['index'] < (120 if role == 'training' else 20), 'Exact active index required')
        if role == 'training':
            need(type(original.get('context_label')) is int and original['context_label'] in (0, 1),
                 'Exact training label required')
        else:
            need(type(original.get('query_id')) is str and re.fullmatch('[0-9a-f]{24}', original['query_id']),
                 'Opaque query identity required')
    header, image = T.projection(original)
    header.update(condition=expected_condition, visible_modalities=list(modalities))
    return header, image


class Session:
    """Fresh in-memory operator state; this does not attest a model/OS reset."""

    def __init__(self, packet, selection, episode):
        need(type(selection) is Selection, 'Frozen condition selection required')
        self._selection = selection
        self._ready = ready_header(selection, episode)
        self._packet = ProjectedPacket(packet, selection.condition)
        condition = selection.condition

        class SelectedRenderer:
            @staticmethod
            def render(record, gain, raster):
                return RENDERER.render(record, gain, raster, BASE_RENDERER, condition)

        self._session = V.Session(self._packet, selection.limits.max_actions, RASTER, SelectedRenderer)
        self._manifest = {
            'schema': 'neural034-modality-viewer-history/v1', 'condition': condition,
            'mode': mode(condition), 'fold': packet.fold, 'query_ids': list(packet.ids),
            'input': dict(packet.pin), 'source': source_identity(), 'episode_id': episode,
            'limits': asdict(selection.limits), 'prompt': prompt(condition),
            'boundary': 'operator_only; participant_process_and_model_context_reset_unqualified',
        }
        self._history = []
        self._failed = False
        self._chain = T.digest(T.encode(self._manifest))
        self._images = 0
        self._outbound = len(T.wire(self._ready))

    @property
    def condition(self):
        return self._selection.condition

    @property
    def ready(self):
        return T.decode(T.encode(self._ready))

    def handle(self, request):
        need(not self._failed, 'Failed operator session cannot continue')
        try:
            return self._handle(request)
        except Exception:
            self._failed = True
            raise

    def _handle(self, request):
        limits = self._selection.limits
        is_view = type(request) is dict and request.get('action') in ('training', 'query', 'inspect', 'gain')
        if is_view:
            need(self._images < limits.max_images and
                 self._outbound + T.PNG_MAX + T.HEADER_MAX + T.PREFIX.size + T.RESERVE <= limits.max_output_bytes,
                 'Matched image or byte budget exhausted')
        response = self._session.handle(request)
        response.update(condition=self.condition, visible_modalities=list(select(self.condition)))
        if response['kind'] == 'view':
            response['mode'] = mode(self.condition)
            response['cells'] = 12 if 'calcium' in select(self.condition) else 0
        header, image = projection(response, self.condition)
        encoded = T.wire(header, image)
        need(self._outbound + len(encoded) <= limits.max_output_bytes, 'Matched byte budget exhausted')
        self._outbound += len(encoded)
        self._images += bool(image)
        row = {'ordinal': len(self._history) + 1, 'previous': self._chain,
               'request': T.decode(T.encode(request)), 'response_sha256': T.digest(T.encode(response))}
        self._history.append(row)
        self._chain = T.digest(T.encode(row))
        return response

    def finish_record(self):
        need(not self._failed and self._session.finished and set(self._session.answers) == set(self._packet.ids),
             'Complete first-final responses and finish required')
        return T.decode(T.encode({'manifest': self._manifest, 'actions': self._history,
                                 'last': self._chain, 'probabilities': self._session.answers,
                                 'images': self._images, 'outbound_bytes': self._outbound}))


def collect(condition, records, packets, limits):
    """Replay seven same-condition operator histories; not transport attestation.

    Each call produces one original-format140-probability submission. Other
    condition records, old combined history formats and different budgets fail.
    Authentic replay needs its own reviewed execution admission.
    """
    selection = Selection(condition, limits)
    need(type(records) is list and len(records) == 7 and type(packets) is dict and set(packets) == set(IDS),
         'All seven exact held-mouse folds required')
    by_fold, episodes = {}, set()
    for record in records:
        need(type(record) is dict and set(record) == {'manifest', 'actions', 'last', 'probabilities', 'images', 'outbound_bytes'},
             'Exact new condition history required; legacy histories are not relabelable')
        manifest = record['manifest']
        need(type(manifest) is dict and manifest.get('condition') == condition and
             type(manifest.get('fold')) is int and manifest['fold'] in IDS and
             manifest['fold'] not in by_fold, 'Mixed conditions or duplicate/invalid fold refused')
        episode = manifest.get('episode_id')
        need(type(episode) is str and episode not in episodes and re.fullmatch('[0-9a-f]{32}', episode),
             'Fresh distinct episode identity per fold required')
        need(type(record['actions']) is list and len(record['actions']) <= limits.max_actions,
             'Bounded complete action history required')
        episodes.add(episode)
        by_fold[manifest['fold']] = record
    need(set(by_fold) == set(IDS), 'No missing held-mouse folds')
    rows = []
    for fold in V.FOLDS:
        original = by_fold[fold]
        need(packets[fold].fold == fold, 'Packet and collected fold differ')
        replay = Session(packets[fold], selection, original['manifest']['episode_id'])
        need(replay._manifest == original['manifest'], 'Exact source/input/condition/prompt/budget identity required')
        for row in original['actions']:
            need(type(row) is dict and set(row) == {'ordinal', 'previous', 'request', 'response_sha256'},
                 'Exact action history fields required')
            replay.handle(row['request'])
            need(replay._history[-1] == row, 'Condition-bound action or image history changed')
        need(replay.finish_record() == original, 'Completed condition history differs from replay')
        rows.extend({'fold': fold, 'query_id': query_id, 'probability': original['probabilities'][query_id]}
                    for query_id in IDS[fold])
    need(len(rows) == 140, 'Complete unchanged scoring support required')
    return {'schema_version': 1, 'probabilities': rows}, {
        'condition': condition, 'folds': 7, 'predictions': 140, 'source': source_identity(),
        'limits': asdict(limits), 'operator_replay_complete': True,
        'participant_transport_qualified': False, 'provider_context_qualified': False,
        'scientific_qualification': False, 'score': None,
    }


def collect_matched(records_by_condition, packets, limits):
    """Three observation conditions on the same140 cases, not three new tasks.

    A future participant adapter must also bind the same client/model policy
    and establish fresh contexts. This operator-only assembly cannot prove it.
    """
    need(type(records_by_condition) is dict and set(records_by_condition) == set(CONDITIONS),
         'Exactly the three declared modality conditions required')
    need(type(limits) is T.Limits, 'One explicit matched budget required')
    limits.validate()
    episodes = set()
    for condition, records in records_by_condition.items():
        need(type(records) is list and len(records) == 7, 'Complete seven-fold condition required')
        for record in records:
            need(type(record) is dict and type(record.get('manifest')) is dict and
                 record['manifest'].get('condition') == condition and
                 record['manifest'].get('limits') == asdict(limits), 'Different condition or presentation budgets refused')
            episode = record['manifest'].get('episode_id')
            need(type(episode) is str and re.fullmatch('[0-9a-f]{32}', episode) and episode not in episodes,
                 'Distinct episode identity across conditions and folds required')
            episodes.add(episode)
    return {condition: collect(condition, records_by_condition[condition], packets, limits)
            for condition in CONDITIONS}
