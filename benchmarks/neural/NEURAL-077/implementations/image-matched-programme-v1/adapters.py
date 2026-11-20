"""Source-bound image-programme permissions and explicit comparison conditions.

Donor modules and their globals are never patched. Transport functions receive
fresh private globals dictionaries; comparison sources have two counted literal
changes. No provider, participant, private loader, or source import runs here at
module import. The trusted caller authenticates the surrounding dependency tree.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import stat
import os
import types

PROGRAMME_CONDITION = 'matched_image_programme'
NATIVE_PERMISSION = ('Do not use code execution, raw arrays, files, external retrieval, '
                     'other tools or memory from other query trials.')
PROGRAMME_PERMISSION = ('You may use the frozen programme to compute on the trace images and metadata '
                        'returned by the declared viewer actions. Do not access original raw arrays, '
                        'other files, external retrieval, other tools or memory from other query trials.')
DONOR_COMMIT = 'e261d08ad5d940d97e4a44665a9c5e828f89f899'
TRANSPORT_PIN = {'bytes': 25985,
                 'sha256': 'e7bffc6d8444478a2440bf3b0b16134d03652fab4ced57bc455307795192fb8f'}
PROTECTED_PIN = {'bytes': 4642,
                 'sha256': 'dcedb10bba955c01ef149316289e6c64edc299d8bef3aef51e3a8ddaa24c8750'}
COMPARATOR_PIN = {'bytes': 10963,
                  'sha256': '3affaa375aaed06844735a85e8b7a7ab03215368758588d83fa0747d88cd25bd'}
MANIFEST_KEY = 'participant_permission_adapter'
TRANSPORT_COMPONENT = 'visual-provider-pair-v1'
COMPARATOR_COMPONENT = 'paired-condition-v1'
PROTECTED_OLD = b'("four_demo", "matched_waveform_programme")'
PROTECTED_NEW = b'("four_demo", "matched_image_programme")'
COMPARATOR_ENTRY = b'    "matched_waveform_programme": ("frozen_program", "numerical_waveform", 4),\n'
IMAGE_ENTRY = b'    "matched_image_programme": ("frozen_program", "visual_waveform", 4),\n'


def need(value, message):
    if not value:
        raise ValueError(message)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def descriptor(value, cap=65536):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'} and
         type(value['bytes']) is int and 0 < value['bytes'] <= cap and
         type(value['sha256']) is str and len(value['sha256']) == 64 and
         all(char in '0123456789abcdef' for char in value['sha256']), 'Exact bounded source descriptor')
    return dict(value)


def ordinary(path):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts and
         all(not part.is_symlink() for part in (path, *path.parents)), 'Ordinary absolute source path')
    return path


def authenticate_self(expected):
    """The operator freezes this source descriptor before any participant query."""
    expected = descriptor(expected)
    path = ordinary(Path(__file__).absolute())
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as handle:
        before = os.fstat(handle.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == expected['bytes'],
             'Exact ordinary adapter source')
        body = handle.read(expected['bytes'] + 1)
        after = os.fstat(handle.fileno())
    fields = lambda row: (row.st_dev, row.st_ino, row.st_size, row.st_mtime_ns, row.st_ctime_ns, row.st_nlink)
    need(fields(before) == fields(after) == fields(path.lstat()) and pin(body) == expected,
         'Frozen adapter source changed')
    return expected


def programme_prompt(prompt):
    """Change exactly the permission sentence; preserve all other prompt bytes."""
    need(type(prompt) is str and prompt.count(NATIVE_PERMISSION) == 1 and
         PROGRAMME_PERMISSION not in prompt, 'Exactly one original permission sentence required')
    return prompt.replace(NATIVE_PERMISSION, PROGRAMME_PERMISSION, 1)


def transport_donor(deps):
    need(type(deps) is dict and type(deps.get('donor_transport_body')) is bytes and
         pin(deps['donor_transport_body']) == TRANSPORT_PIN and
         deps['operator']['transport.py'] == TRANSPORT_PIN, 'Exact authenticated donor transport body')
    donor = deps['transport']
    need(isinstance(donor, types.ModuleType), 'Trusted loaded transport module required')
    path = ordinary(donor.__file__)
    need(path.name == 'transport.py' and path.parent.name == TRANSPORT_COMPONENT,
         'Canonical donor transport directory required')
    # Compile only the authenticated source to compare selected code objects;
    # no donor top-level imports or dependency loaders execute a second time.
    root_code = compile(deps['donor_transport_body'], str(path), 'exec', dont_inherit=True)
    code = {item.co_name: item for item in root_code.co_consts if isinstance(item, types.CodeType)}
    for name in ('run_episode', 'ready_header', 'boundary_manifest', 'audit_transport', 'collect'):
        function = getattr(donor, name, None)
        need(isinstance(function, types.FunctionType) and function.__globals__ is donor.__dict__ and
             function.__code__ == code[name], 'Loaded donor function differs from its frozen source')
    return donor, path


def clone(function, namespace):
    need(namespace is not function.__globals__, 'Private globals dictionary required')
    result = types.FunctionType(function.__code__, namespace, function.__name__,
                                function.__defaults__, function.__closure__)
    result.__kwdefaults__ = None if function.__kwdefaults__ is None else dict(function.__kwdefaults__)
    result.__annotations__ = dict(function.__annotations__)
    result.__doc__ = function.__doc__
    return result


def make_transport(deps, adapter_pin):
    """A four-demo programme binding; preserve original sandbox/limit semantics.

    The caller must independently require the selected production sandbox and
    frozen client. Protocol-only fixtures cannot qualify that boundary.
    """
    donor, donor_path = transport_donor(deps)
    selected_adapter = authenticate_self(adapter_pin)
    permission = {'schema': 'neural077_image_programme_permission_adapter_v1',
        'condition': PROGRAMME_CONDITION, 'donor_transport': dict(TRANSPORT_PIN),
        'adapter_source': selected_adapter,
        'native_permission_sha256': pin(NATIVE_PERMISSION.encode('utf-8'))['sha256'],
        'programme_permission_sha256': pin(PROGRAMME_PERMISSION.encode('utf-8'))['sha256'],
        'scope': 'Only the first-header permission sentence changes; scientific text, image projection, four demonstrations and limits are unchanged.'}
    private = dict(donor.__dict__)

    def ready_header(session, limits, episode_id):
        header = donor.ready_header(session, limits, episode_id)
        replacement = dict(header)
        replacement['prompt'] = programme_prompt(header['prompt'])
        return replacement

    def boundary_manifest(limits, sandbox, client, episode_id, profile):
        manifest = donor.boundary_manifest(limits, sandbox, client, episode_id, profile)
        need(MANIFEST_KEY not in manifest, 'Donor manifest unexpectedly defines adapter metadata')
        # Use the donor's strict JSON round-trip for an independent nested value.
        manifest[MANIFEST_KEY] = donor.v.decode(donor.v.encode(permission))
        return manifest

    private.update(ready_header=ready_header, boundary_manifest=boundary_manifest)
    bound_run = clone(donor.run_episode, dict(private))
    bound_audit = clone(donor.audit_transport, dict(private))

    def run_episode(dataset, ordinal, mode, output, client, python=donor.sys.executable,
                    sandbox='macos', limits=None, client_launcher=None):
        need(mode == 'four_demo', 'Matched image programme requires exactly four demonstrations')
        return bound_run(dataset, ordinal, mode, output, client, python, sandbox, limits, client_launcher)

    def audit_transport(path, dataset, ordinal, mode):
        need(mode == 'four_demo', 'Matched image programme audit requires four demonstrations')
        manifest = donor.v.decode(donor.v.read_regular(Path(path) / 'transport/MANIFEST.json', donor.HEADER_MAX))
        need(manifest.get(MANIFEST_KEY) == permission, 'Frozen participant permission adapter mismatch')
        return bound_audit(path, dataset, ordinal, mode)

    private.update(run_episode=run_episode, audit_transport=audit_transport)
    bound_collect = clone(donor.collect, dict(private))

    def collect(packet, sessions, mode, output, implementation_root=None):
        need(mode == 'four_demo', 'Matched image programme collection requires four demonstrations')
        return bound_collect(packet, sessions, mode, output, implementation_root)

    public = {name: value for name, value in vars(donor).items()
              if not name.startswith('__') and name != 'main'}
    public.update(run_episode=run_episode, audit_transport=audit_transport, collect=collect,
                  ready_header=ready_header, boundary_manifest=boundary_manifest,
                  participant_permission_adapter=donor.v.decode(donor.v.encode(permission)),
                  derivation={'schema': 'neural077_image_programme_transport_binding_v1',
                    'donor_commit': DONOR_COMMIT, 'donor_path': str(donor_path),
                    'donor_transport': dict(TRANSPORT_PIN), 'adapter_source': dict(selected_adapter),
                    'effective_binding': 'Private globals for donor run_episode/audit_transport/collect; static permission manifest and first-header replacement.',
                    'condition': PROGRAMME_CONDITION, 'shared_donor_globals_modified': False,
                    'provider_context_qualified': False, 'provider_tool_policy_qualified': False,
                    'scientific_qualification': False})
    return types.SimpleNamespace(**public)


def derived_module(name, path, body, donor_pin):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__source_pin__ = pin(body)
    module.__donor_source_pin__ = dict(donor_pin)
    exec(compile(body, str(path), 'exec', dont_inherit=True), module.__dict__)
    return module


def make_compare(deps, protected_body, comparator_body):
    """Load precisely derived conditions; leave public gating and all metrics intact."""
    _, transport_path = transport_donor(deps)
    need(type(protected_body) is bytes and pin(protected_body) == PROTECTED_PIN and
         type(comparator_body) is bytes and pin(comparator_body) == COMPARATOR_PIN,
         'Exact protected/comparator donor source bodies required')
    need(protected_body.count(PROTECTED_OLD) == 1 and protected_body.count(PROTECTED_NEW) == 0,
         'One explicit protected condition tuple required')
    need(comparator_body.count(COMPARATOR_ENTRY) == 1 and comparator_body.count(IMAGE_ENTRY) == 0 and
         b'"matched_image_programme"' not in comparator_body,
         'One original numerical registry entry and no image entry required')
    effective_protected = protected_body.replace(PROTECTED_OLD, PROTECTED_NEW, 1)
    effective_comparator = comparator_body.replace(COMPARATOR_ENTRY, COMPARATOR_ENTRY + IMAGE_ENTRY, 1)
    protected_path = transport_path.parent / 'protected_compare.py'
    comparator_path = transport_path.parent.parent / COMPARATOR_COMPONENT / 'compare.py'
    derivation = {'schema': 'neural077_image_programme_comparison_derivation_v1',
        'donor_commit': DONOR_COMMIT,
        'donor_sources': {'protected_compare': {'path': str(protected_path), **PROTECTED_PIN},
                          'comparator': {'path': str(comparator_path), **COMPARATOR_PIN}},
        'effective_sources': {'protected_compare': {'path': str(protected_path), **pin(effective_protected)},
                              'comparator': {'path': str(comparator_path), **pin(effective_comparator)}},
        'replacements': {'protected_condition_tuple': 1, 'comparator_registry_addition': 1},
        'conditions': ['four_demo', PROGRAMME_CONDITION], 'metrics_unchanged': True,
        'source_scope': 'Counted in-memory derivation at canonical donor paths; effective source hashes differ and must accompany any resulting receipt.',
        'qualification': False}
    protected = derived_module('neural077_image_programme_protected_compare', protected_path,
                               effective_protected, PROTECTED_PIN)
    comparator = derived_module('neural077_image_programme_comparator', comparator_path,
                                effective_comparator, COMPARATOR_PIN)
    need(comparator.CONDITIONS[PROGRAMME_CONDITION] == ('frozen_program', 'visual_waveform', 4) and
         comparator.CONDITIONS['matched_waveform_programme'] == ('frozen_program', 'numerical_waveform', 4),
         'Distinct image and original numerical conditions required')
    return protected, comparator, derivation
