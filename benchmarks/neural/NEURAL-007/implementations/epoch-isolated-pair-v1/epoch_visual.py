"""Portable target-isolated N007 waveform views; no work occurs on import."""
from pathlib import Path
import hashlib
import importlib.util
import json
import math
import os
import re
import secrets
import stat
import sys

CONDITION = 'epoch_isolated_raw_viewer_zero_shot_v1'
MEMORY_POLICY = 'immutable_complete_epoch_overview_plus_current_detail_no_history_v1'
BASE_CLIENT_PIN = {'bytes': 19772, 'sha256': 'f7a09de138c8144d0aba9d0668a7507248f5d3aec57b131d8222d13ee59602aa'}
COMMON_PIN = {'bytes': 7532, 'sha256': 'ac596c1592ac853c58dc13a5f9b0607cf39822f301ad2d99c8d915316a362fc6'}
FRESH_PIN = {'bytes': 18270, 'sha256': '09e375031d024dd18cb57ed1666e594aaabfc2c9065edb4113b98c2348937a22'}
CONTRACT_PIN = {'bytes': 13307, 'sha256': '1458d314982f129614948cc267c43a4292e2036729d5104f5014b92eac93d033'}

def need(ok, message):
    if not ok:
        raise ValueError(message)

def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()

def capture(path, expected):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts
         and not any(p.is_symlink() for p in (path, *path.parents)), 'Ordinary absolute source path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
        need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size == expected['bytes'],
             'Exact ordinary source extent')
        raw = stream.read(expected['bytes'] + 1)
        need(identity(info) == identity(os.fstat(stream.fileno())) == identity(path.lstat())
             and pin(raw) == expected, 'Source identity changed')
    return raw

def module(path, raw, name):
    value = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    value.__file__ = str(path)
    sys.modules[name] = value
    exec(compile(raw, str(path), 'exec'), value.__dict__)
    return value

def load_runtime(root, whole_history_integration_root=None, whole_history_admission_root=None,
                 contract_path=None):
    """Authenticate existing mechanisms and the new common epoch contract.

    Source preparation passes explicit authenticated dependency locations. Once
    published, defaults are sibling installed implementations, never private paths.
    """
    root = Path(root)
    implementations = root / 'benchmarks/neural/NEURAL-007/implementations'
    base_root = implementations / 'viewer-provider-integration-v1' if whole_history_integration_root is None else Path(whole_history_integration_root)
    admission_root = implementations / 'finite-workflow-v1' if whole_history_admission_root is None else Path(whole_history_admission_root)
    contract_path = Path(__file__).with_name('contract.py') if contract_path is None else Path(contract_path)
    need(CONTRACT_PIN is not None, 'Epoch contract source not frozen')
    base = module(base_root / 'client.py', capture(base_root / 'client.py', BASE_CLIENT_PIN), 'n007_epoch_base_client')
    runtime = base.load_runtime(root, base_root)
    common_path = implementations / 'finite-workflow-v1/common.py'
    common = module(common_path, base.source_bytes(common_path, COMMON_PIN), 'n007_epoch_common')
    old_common = sys.modules.get('common')
    sys.modules['common'] = common
    try:
        fresh = module(admission_root / 'fresh_viewer.py',
                       base.source_bytes(admission_root / 'fresh_viewer.py', FRESH_PIN),
                       'n007_epoch_prior_admission')
    finally:
        if old_common is None:
            sys.modules.pop('common', None)
        else:
            sys.modules['common'] = old_common
    contract_raw = base.source_bytes(contract_path, CONTRACT_PIN)
    contract = sys.modules.get('contract')
    if contract is None:
        contract = module(contract_path, contract_raw, 'contract')
    else:
        need(Path(contract.__file__).resolve() == contract_path.resolve(), 'One authenticated shared epoch contract module')
    need(contract.VISUAL_CONDITION == CONDITION and contract.TOTAL == 5450
         and contract.CASES == (('development-001', 2780), ('development-002', 2670)),
         'Unchanged original two-person target roster')
    viewer = runtime['transport'].v
    raster, _, renderer = viewer.dependencies()
    local = {name: pin(Path(__file__).with_name(name).read_bytes())
             for name in ('epoch_visual.py', 'epoch_provider.py')}
    runtime.update(base_client=base, common=common, prior_admission=fresh, contract=contract,
                   viewer=viewer, raster=raster, renderer=renderer)
    runtime['source'] = {'base': runtime['source'], 'base_client': BASE_CLIENT_PIN,
                         'prior_common': COMMON_PIN, 'prior_admission': FRESH_PIN,
                         'contract': CONTRACT_PIN, 'epoch_modules': local}
    runtime['runtime_identity'] = viewer.runtime_identity()
    return runtime

class Session:
    """One target only. The original full three-channel epoch is always available."""
    def __init__(self, packet, runtime, max_actions, session_id=None):
        need(type(packet) is runtime['contract'].EpochPacket, 'Authenticated epoch projection type')
        need(type(max_actions) is int and 1 <= max_actions <= 100000, 'Explicit finite epoch action budget')
        self.packet, self.runtime, self.max_actions = packet, runtime, max_actions
        self.session_id = secrets.token_hex(16) if session_id is None else session_id
        need(type(self.session_id) is str and re.fullmatch('[0-9a-f]{32}', self.session_id),
             'Explicit fresh target session identity')
        self.actions, self.started, self.closed = 0, False, False
        self.answer, self.overview, self.current = None, None, None
        self.state = {'start_sample': 0, 'stop_sample': 3000, 'gain_uv': 50,
                      'channels': list(runtime['viewer'].CHANNELS)}

    def _render(self):
        packet, state = self.packet, self.state
        png = self.runtime['renderer'].render(
            packet.epoch_id, packet.start_sample + state['start_sample'],
            state['channels'], packet.samples(state['start_sample'], state['stop_sample'], state['channels']),
            state['gain_uv'], packet.clock_features, self.runtime['raster'],
            target_start_sample=packet.start_sample)
        need(type(png) is bytes and 0 < len(png) <= self.runtime['transport'].PNG_MAX,
             'Bounded original encoded PNG')
        header = {'kind': 'view', 'condition': CONDITION, 'session_id': self.session_id,
                  'target': packet.metadata(), 'state': dict(state, channels=state['channels'][:]),
                  'absolute_window': [packet.start_sample + state['start_sample'],
                                      packet.start_sample + state['stop_sample']],
                  'image': pin(png)}
        return header, png

    def initial(self):
        need(not self.started and not self.closed, 'One initial complete epoch view')
        self.started = True
        self.overview = self.current = self._render()
        return self.observation()

    def observation(self):
        need(self.started and self.overview is not None and self.current is not None and not self.closed,
             'Live complete epoch overview required')
        images = [self.overview[1]]
        roles = [{'role': 'complete_epoch_overview', 'image': pin(images[0])}]
        if self.current[1] != self.overview[1]:
            images.append(self.current[1])
            roles.append({'role': 'current_detail', 'image': pin(images[-1])})
        header = {'schema': 'n007_epoch_visual_observation_v1', 'condition': CONDITION,
                  'memory_policy': MEMORY_POLICY, 'session_id': self.session_id,
                  'target': self.packet.metadata(), 'overview': self.overview[0],
                  'current': self.current[0], 'images': roles,
                  'actions_used': self.actions, 'actions_available': self.max_actions - self.actions}
        return header, tuple(images)

    def validate_action(self, request):
        need(self.started and not self.closed and self.actions < self.max_actions, 'Epoch closed or action budget exhausted')
        fields = {'inspect': set(), 'window': {'start_sample', 'stop_sample'},
                  'gain': {'microvolts_per_division'}, 'channels': {'channels'},
                  'respond': {'epoch_id', 'probabilities'}}
        need(type(request) is dict and type(request.get('action')) is str, 'Typed epoch action')
        action = request['action']
        need(action in fields and set(request) == fields[action] | {'action'}, 'Unknown action or fields')
        value = dict(request)
        if action == 'window':
            start, stop = request['start_sample'], request['stop_sample']
            need(type(start) is int and type(stop) is int and 0 <= start < stop <= 3000
                 and stop - start >= 100, 'Window restricted to the same complete target epoch')
        elif action == 'gain':
            need(type(request['microvolts_per_division']) is int
                 and request['microvolts_per_division'] in self.runtime['viewer'].GAINS, 'Original display gain')
        elif action == 'channels':
            channels = request['channels']
            need(type(channels) is list and channels
                 and channels == [name for name in self.runtime['viewer'].CHANNELS if name in channels],
                 'Original ordered channel selection')
            value['channels'] = channels[:]
        elif action == 'respond':
            need(request['epoch_id'] == self.packet.epoch_id and self.overview is not None
                 and self.answer is None, 'Exact target and irreversible first answer')
            value['probabilities'] = self.runtime['viewer'].probabilities(request['probabilities'])
        return value

    def handle(self, request):
        value = self.validate_action(request)
        self.actions += 1
        action = value['action']
        if action == 'respond':
            self.answer = value['probabilities']
            self.closed = True
            return {'kind': 'response_accepted', 'condition': CONDITION, 'session_id': self.session_id,
                    'epoch_id': self.packet.epoch_id, 'probabilities': self.answer[:],
                    'full_three_channel_epoch_available': True}
        if action == 'window':
            self.state.update(start_sample=value['start_sample'], stop_sample=value['stop_sample'])
        elif action == 'gain':
            self.state['gain_uv'] = value['microvolts_per_division']
        elif action == 'channels':
            self.state['channels'] = value['channels']
        self.current = self._render()
        return self.observation()

def action_schema(runtime):
    def obj(properties):
        return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}
    variants = []
    fields = {'inspect': {}, 'window': {'start_sample': {'type': 'integer'}, 'stop_sample': {'type': 'integer'}},
              'gain': {'microvolts_per_division': {'type': 'integer', 'enum': list(runtime['viewer'].GAINS)}},
              'channels': {'channels': {'type': 'array', 'items': {'type': 'string', 'enum': list(runtime['viewer'].CHANNELS)}}},
              'respond': {'epoch_id': {'type': 'string'}, 'probabilities': {'type': 'array', 'items': {'type': 'number'}, 'minItems': 5, 'maxItems': 5}}}
    for name, properties in fields.items():
        variants.append(obj(dict(action={'type': 'string', 'enum': [name]}, **properties)))
    return obj({'viewer_action': {'anyOf': variants}})

def request_bytes(session, model, budget, knowledge):
    session.runtime['contract'].checked_knowledge(knowledge)
    need(knowledge['provider'] == 'openai', 'Declared provider agrees with the reused HTTPS endpoint')
    need(model == knowledge['model'] and type(model) is str
         and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}', model), 'Model agrees with frozen shared prior policy')
    budget.validate()
    header, images = session.observation()
    need(len(images) <= 2 and len(images) <= budget.max_images, 'At most overview plus one same-target detail image')
    contract = session.runtime['contract']
    public_task = {'schema': 'sleep007_epoch_public_task_v1',
                   'information_contract': contract.PAIR_CONDITION,
                   'people': [{'case_id': case, 'epochs': epochs,
                               'epoch_index_start': 0, 'epoch_index_stop_exclusive': epochs}
                              for case, epochs in contract.CASES],
                   'roster_order': 'people_list_order_then_ascending_epoch_index',
                   'epoch_id_format': '{case_id}/{epoch_index:05d}',
                   'people_count': len(contract.CASES), 'total_epochs': contract.TOTAL,
                   'class_order': list(contract.CLASSES),
                   'epoch_geometry': {'sample_count': contract.SAMPLES,
                                      'sample_rate_hz': contract.SAMPLE_RATE,
                                      'duration_seconds': contract.SAMPLES // contract.SAMPLE_RATE,
                                      'channels': list(contract.CHANNELS),
                                      'shape': [len(contract.CHANNELS), contract.SAMPLES]}}
    first = {'schema': 'n007_epoch_visual_request_v1', 'condition': CONDITION,
             'memory_policy': MEMORY_POLICY, 'public_task': public_task,
             'knowledge': knowledge, 'observation': header}
    content = [{'type': 'input_text', 'text': encode(first).decode()}]
    import base64
    content.extend({'type': 'input_image', 'image_url': 'data:image/png;base64,' + base64.b64encode(png).decode('ascii'),
                    'detail': budget.image_detail} for png in images)
    value = {'model': model, 'input': [{'role': 'user', 'content': content}],
             'instructions': 'Score this one 30-second target as W,N1,N2,N3,R in that probability order. Use only typed waveform actions. The immutable complete three-channel target overview is always supplied, plus at most one current same-epoch detail image. There are no previous target images, answers, labels, demonstrations, tools, code, retrieval, external weights or other-session memory. Window offsets are relative sample indices within this target, from0 through3000 at100Hz. You may inspect, change gain/channels, or choose a100-to3000-sample same-target window. Return one viewer_action object. The first accepted respond action ends this target permanently. No visual history or earlier action transcript is replayed. The supplied base-agent prior declaration applies; no additional assets are supplied.',
             'tools': [], 'tool_choice': 'none', 'parallel_tool_calls': False,
             'store': False, 'stream': False, 'background': False, 'truncation': 'disabled',
             'max_output_tokens': budget.output_tokens,
             'text': {'format': {'type': 'json_schema', 'name': 'viewer_action', 'strict': True,
                                 'schema': action_schema(session.runtime)}}}
    raw = encode(value)
    need(len(encode(value['input'])) <= budget.max_history_bytes
         and len(raw) <= budget.max_request_bytes <= session.runtime['sender'].REQUEST_CAP,
         'Complete overview/detail request must fit unchanged sender/history limits')
    return raw
