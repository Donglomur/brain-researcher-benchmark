"""Full32 provider/programme producer and separate protected admission.

No operation runs at import. Source controls are generated fixtures, never
provider qualification. A selected study and external resource/custody approval
are required before run-arm. Raw HTTP records demonstrate consistency conditional
on the trusted capture host; they cannot prove a provider's hidden state/policy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import stat
import struct
import sys
import time
import types

HERE = Path(__file__).resolve().parent
RELATIVE = 'benchmarks/neural/NEURAL-077/implementations/full32-provider-pair-v1'
CORE = 'benchmarks/neural/NEURAL-077/implementations/full32-paired-benchmark-v1'
RUNTIME = 'benchmarks/neural/NEURAL-077/implementations/full32-paired-runtime-v1'
EXPECTED = {
    'pair': RELATIVE + '/pair.py', 'bridge': RELATIVE + '/bridge.py',
    'client': RELATIVE + '/client.py', 'broker': RELATIVE + '/broker.py',
    'http_client': 'benchmarks/neural/NEURAL-077/implementations/waveform-provider-v1/client.py',
    'core': CORE + '/evaluator.py', 'consumer': CORE + '/consumer.py',
    'bundle': CORE + '/bundle.py', 'core_bindings': CORE + '/SOURCE_BINDINGS.json',
    'runtime': RUNTIME + '/runtime.py', 'profile': RUNTIME + '/profile_successor.py',
    'episode': RUNTIME + '/diagnostic_episode.py',
    'wire': 'benchmarks/neural/NEURAL-077/implementations/waveform-transport-v1/transport.py',
    'owned': 'benchmarks/shared/viewer-process-ownership-v1/owned_exit.py',
}
CONDITIONS = ('numeric_direct_four_demo', 'numeric_program_four_demo')
COUNT = 6400
PREFIX = struct.Struct('!I')
PROMPT_CAP = 196608
RESPONSE_CAP = 4096
PROVIDER_CAP = 524288
CONTRACT_CAP = 65536
ARM_CAP = 4 * 1024**2
SESSION_RESERVE = 384000000 + 4 * 1024**2
POLICY = {
    'same_four_demonstrations': True, 'single_query_only': True,
    'no_other_query_or_pooled_learning': True, 'no_private_answers': True,
    'no_six_person_training_or_fitted_coefficients': True,
    'no_natural_class_prior': True, 'both_bundles_frozen_before_query_access': True,
    'old_negative_baselines_preserved': True, 'no_feedback_until_pair_closed': True,
}
CAPTURE_NAMES = {'CONFIG.json', 'INPUT.bin', 'OUTPUT.bin', 'END.json', 'STDERR.bin',
                 'REQUEST.bin', 'RESPONSE.bin', 'HTTP.json', 'BRIDGE.json'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def decode(body):
    def unique(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'Duplicate JSON field')
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def descriptor(value, cap=1048576):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'} and
         type(value['bytes']) is int and 0 < value['bytes'] <= cap and
         type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']),
         'Exact bounded byte/hash descriptor')


def ordinary_path(path):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts and
         all(not p.is_symlink() for p in (path, *path.parents)), 'Absolute ordinary path required')
    return path


def disjoint_output(output, modules, roots=()):
    """An output may neither contain nor be inside any selected source/input tree."""
    output = ordinary_path(output)
    protected = {ordinary_path(modules['root'] / row['path']).parent
                 for row in modules['bindings'].values()}
    protected.update(ordinary_path(p) for p in roots)
    need(not output.exists() and all(not output.is_relative_to(p) and not p.is_relative_to(output)
                                    for p in protected), 'Fresh output must be disjoint from all source/input trees')
    need(output.parent.is_dir(), 'Existing ordinary output parent required')
    return output


def study_roots(contract):
    return (Path(contract['public_root']).parent, Path(contract['programme']['path']).parent,
            Path(contract['authoring_exposure']['path']).parent)


class Budget:
    def __init__(self, read_bytes, write_bytes, deadline):
        self.read_limit, self.write_limit, self.deadline = read_bytes, write_bytes, deadline
        self.read = self.written = 0

    def input(self, size):
        need(type(size) is int and size >= 0 and self.read + size <= self.read_limit, 'Study read ceiling')
        need(time.monotonic() < self.deadline, 'Study deadline')
        self.read += size

    def output(self, size):
        need(type(size) is int and size >= 0 and self.written + size <= self.write_limit, 'Study write ceiling')
        need(time.monotonic() < self.deadline, 'Study deadline')
        self.written += size


def read(path, cap, expected=None, budget=None, empty=False):
    path = ordinary_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             (0 if empty else 1) <= before.st_size <= cap, 'Bounded ordinary file required')
        if budget is not None:
            budget.input(before.st_size)
        body = stream.read(before.st_size + 1)
        after = os.fstat(stream.fileno())
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
    need(len(body) == before.st_size and identity(before) == identity(after) == identity(path.lstat()),
         'Retained input changed')
    need(expected is None or pin(body) == expected, 'Committed input changed')
    return body


def write(path, body, budget=None):
    if budget is not None:
        budget.output(len(body))
    path = ordinary_path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body); stream.flush(); os.fsync(stream.fileno())
    return pin(body)


def dependencies(expected=None):
    body = read(HERE / 'SOURCE_BINDINGS.json', 16384, expected)
    bindings = decode(body)
    need(set(bindings) == {'schema', 'members'} and
         bindings['schema'] == 'erp-full32-provider-pair-sources-v1' and
         set(bindings['members']) == set(EXPECTED), 'Exact source closure required')
    root = HERE.parents[4]
    need(root / RELATIVE == HERE, 'Public component repository layout required')
    result = {'root': root, 'bindings': bindings['members'], 'binding_pin': pin(body)}
    for name, row in bindings['members'].items():
        need(set(row) == {'path', 'bytes', 'sha256'} and row['path'] == EXPECTED[name],
             'Exact selected dependency path')
        selected = {key: row[key] for key in ('bytes', 'sha256')}
        descriptor(selected, 131072)
        source = read(root / row['path'], 131072, selected)
        if name in ('pair', 'client', 'core_bindings'):
            result[name + '_body'] = source
        else:
            module = types.ModuleType('erp_full32_pair_' + name)
            module.__file__ = str(root / row['path']); sys.modules[module.__name__] = module
            exec(compile(source, module.__file__, 'exec'), module.__dict__)
            result[name] = module
    need(decode(result['core_bindings_body']) == {
        'schema': 'erp-full32-portable-evaluator-sources-v1',
        'members': {name: {'path': name + '.py', **{k: result['bindings'][name][k]
                                                  for k in ('bytes', 'sha256')}}
                    for name in ('bundle', 'consumer')}}, 'Original grader dependencies changed')
    result['wire'] = result['profile'].wrap_wire(result['wire'])
    return result


def validate_contract(contract):
    fields = {'schema', 'selected', 'condition_id', 'public_root', 'public_manifest', 'provider',
              'programme', 'authoring_exposure', 'interpreter', 'sandbox', 'limits',
              'information_policy', 'source_bindings', 'adapter_sources', 'freeze_stage'}
    need(type(contract) is dict and set(contract) == fields, 'Exact full32 study contract')
    need(contract['schema'] == 'erp-full32-provider-pair-contract-v1' and contract['selected'] is True and
         contract['condition_id'] == 'erp-core-remaining-persons-released-marker-v1', 'Selected full32 identity')
    ordinary_path(contract['public_root']); descriptor(contract['public_manifest'], 131072)
    descriptor(contract['source_bindings'], 16384)
    need(contract['information_policy'] == POLICY and contract['freeze_stage'] == {
        'query_records_opened': 0, 'authoring_exposure_is_declaration': True}, 'Pre-query information policy')
    provider = contract['provider']
    need(type(provider) is dict and set(provider) == {'model', 'max_output_tokens'} and
         type(provider['model']) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}', provider['model']) and
         type(provider['max_output_tokens']) is int and 1 <= provider['max_output_tokens'] <= 32768,
         'Exact model and output allocation')
    for name in ('programme', 'authoring_exposure'):
        row = contract[name]
        need(type(row) is dict and set(row) == ({'path', 'file', 'bundle_identity'} if name == 'programme'
                                               else {'path', 'file'}), 'Frozen programme/exposure descriptors')
        ordinary_path(row['path']); descriptor(row['file'], 1048576 if name == 'programme' else 16384)
    descriptor(contract['programme']['bundle_identity'], 1048576)
    for name in ('interpreter', 'sandbox'):
        row = contract[name]
        need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}, 'Pinned execution operand')
        ordinary_path(row['path']); descriptor({k: row[k] for k in ('bytes', 'sha256')}, 64 * 1024**2)
    need(contract['sandbox']['path'] == '/usr/bin/sandbox-exec', 'Supported programme substrate is macOS')
    limits = contract['limits']
    need(type(limits) is dict and set(limits) == {'episode_work_seconds', 'episode_cleanup_seconds',
         'campaign_seconds', 'read_bytes', 'write_bytes'}, 'Explicit finite study resource limits')
    for name in ('episode_work_seconds', 'episode_cleanup_seconds', 'campaign_seconds'):
        need(type(limits[name]) in (int, float) and math.isfinite(limits[name]) and limits[name] > 0,
             'Positive finite selected clocks')
    need(limits['episode_work_seconds'] <= 3600 and limits['episode_cleanup_seconds'] <= 30 and
         limits['campaign_seconds'] <= 2**31 and limits['campaign_seconds'] >
         limits['episode_work_seconds'] + limits['episode_cleanup_seconds'], 'Coherent finite episode/campaign clocks')
    for name in ('read_bytes', 'write_bytes'):
        need(type(limits[name]) is int and 0 < limits[name] <= 1024**4, 'Explicit finite byte budget')
    sources = contract['adapter_sources']
    need(type(sources) is dict and set(sources) == set(EXPECTED), 'Frozen complete adapter source set')
    for name, row in sources.items():
        need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'} and row['path'] == EXPECTED[name],
             'Frozen dependency identity')
        descriptor({k: row[k] for k in ('bytes', 'sha256')}, 131072)
    return contract


def validate_exposure(value):
    need(type(value) is dict and set(value) == {'schema', 'declared_authoring_inputs',
        'remaining32_query_or_answer_tuning_declared', 'six_person_feature_training_declared',
        'pretraining_exposure', 'notes'}, 'Explicit bounded authoring exposure declaration')
    need(value['schema'] == 'erp-full32-authoring-exposure-v1' and
         type(value['declared_authoring_inputs']) is list and 1 <= len(value['declared_authoring_inputs']) <= 64 and
         all(type(x) is str and 0 < len(x) <= 512 for x in value['declared_authoring_inputs']) and
         value['remaining32_query_or_answer_tuning_declared'] is False and
         value['six_person_feature_training_declared'] is False and value['pretraining_exposure'] == 'unknown' and
         type(value['notes']) is str and 0 < len(value['notes']) <= 4096,
         'No local held-out tuning declared; hidden/pretraining exposure remains unknown')
    return value


def verify_frozen(contract, modules, budget=None):
    validate_contract(contract)
    need(contract['source_bindings'] == modules['binding_pin'] and
         contract['adapter_sources'] == modules['bindings'], 'Adapter changed since pre-query freeze')
    programme = read(contract['programme']['path'], 1048576, contract['programme']['file'], budget)
    frozen = decode(programme); client = modules['bundle'].verify(frozen)
    need(frozen['bundle_identity'] == contract['programme']['bundle_identity'], 'Programme/config changed after freeze')
    exposure = read(contract['authoring_exposure']['path'], 16384, contract['authoring_exposure']['file'], budget)
    validate_exposure(decode(exposure))
    return {'programme': programme, 'client': client, 'exposure': exposure}


def freeze(spec, output, modules=None):
    """Only authoring source/config and declarations are opened; no PacketSession."""
    need(type(spec) is dict and set(spec) == {'schema', 'public_root', 'public_manifest', 'provider',
        'programme_root', 'programme_manifest', 'authoring_exposure', 'interpreter', 'sandbox', 'limits'},
        'Exact pre-query freeze specification')
    need(spec['schema'] == 'erp-full32-provider-pair-freeze-spec-v1', 'Freeze specification version')
    modules = dependencies() if modules is None else modules
    packet = ordinary_path(spec['public_root']); output = ordinary_path(output)
    authoring = ordinary_path(spec['programme_root'])
    need(not output.exists() and not output.is_relative_to(packet.parent) and
         not authoring.is_relative_to(packet.parent), 'Fresh authoring/output outside packet tree')
    for name in ('programme_manifest', 'authoring_exposure'):
        row = spec[name]
        need(set(row) == {'path', 'bytes', 'sha256'}, 'Exact authoring operand')
        ordinary_path(row['path']); descriptor({k: row[k] for k in ('bytes', 'sha256')}, 65536)
        need(not Path(row['path']).is_relative_to(packet.parent), 'Authoring operand outside packet tree')
    output = disjoint_output(output, modules, (packet.parent, authoring,
        Path(spec['programme_manifest']['path']).parent, Path(spec['authoring_exposure']['path']).parent))
    manifest = decode(read(spec['programme_manifest']['path'], 65536,
                           {k: spec['programme_manifest'][k] for k in ('bytes', 'sha256')}))
    captured = modules['bundle'].capture(authoring, manifest)
    programme = modules['bundle'].encoded(captured)
    exposure = read(spec['authoring_exposure']['path'], 16384,
                    {k: spec['authoring_exposure'][k] for k in ('bytes', 'sha256')})
    validate_exposure(decode(exposure))
    contract = {'schema': 'erp-full32-provider-pair-contract-v1', 'selected': True,
        'condition_id': 'erp-core-remaining-persons-released-marker-v1',
        **{k: spec[k] for k in ('public_root', 'public_manifest', 'provider', 'interpreter', 'sandbox', 'limits')},
        'programme': {'path': str(output / 'PROGRAMME.json'), 'file': pin(programme),
                      'bundle_identity': captured['bundle_identity']},
        'authoring_exposure': {'path': str(output / 'EXPOSURE.json'), 'file': pin(exposure)},
        'information_policy': POLICY, 'source_bindings': modules['binding_pin'],
        'adapter_sources': modules['bindings'],
        'freeze_stage': {'query_records_opened': 0, 'authoring_exposure_is_declaration': True}}
    validate_contract(contract)
    output.mkdir(mode=0o700)
    write(output / 'PROGRAMME.json', programme); write(output / 'EXPOSURE.json', exposure)
    commitment = write(output / 'CONTRACT.json', encode(contract))
    return {'status': 'study_frozen_before_query_access', 'contract': commitment,
            'programme_identity': captured['bundle_identity'], 'query_records_opened': 0,
            'exposure_is_operator_declaration': True, 'provider_context_qualified': False}


def provider_configuration(context, contract, bridge, deadline):
    provider = contract['provider']
    bridge.request_body(context['prompt'], provider['model'], provider['max_output_tokens'])
    return {'schema': 'erp_full32_openai_client_v1', **provider, 'deadline': deadline,
            'trial_id': context['trial_id'], 'context_sha256': context['context_sha256'],
            'bridge_path': str(Path(bridge.__file__).resolve()),
            'bridge_pin': {k: contract['adapter_sources']['bridge'][k] for k in ('bytes', 'sha256')}}


def validate_provider_capture(context, contract, capture, bridge):
    """Consistency of exact raw custody, not an attestation of hidden provider state."""
    need(type(capture) is dict and set(capture) == CAPTURE_NAMES and
         all(type(v) is bytes for v in capture.values()), 'Complete provider capture file set')
    need(type(context) is dict and set(context) == {'trial_id', 'condition', 'prompt', 'context_sha256'} and
         context['condition'] == CONDITIONS[0] and
         bridge.query_identity(context['prompt']) == context['trial_id'], 'Full32 direct context only')
    prompt = context['prompt'].encode(); need(0 < len(prompt) <= PROMPT_CAP, 'Complete prompt capacity')
    need(pin(prompt)['sha256'] == context['context_sha256'], 'Context hash changed')
    cfg = decode(capture['CONFIG.json'])
    need(type(cfg.get('deadline')) in (int, float) and math.isfinite(cfg['deadline']) and
         cfg == provider_configuration(context, contract, bridge, cfg['deadline']), 'Frozen provider configuration changed')
    need(capture['INPUT.bin'] == PREFIX.pack(len(prompt)) + prompt, 'Complete first input frame required')
    outgoing = capture['OUTPUT.bin']
    need(4 < len(outgoing) <= RESPONSE_CAP + 4 and PREFIX.unpack(outgoing[:4])[0] == len(outgoing) - 4,
         'One complete original output frame')
    request, response = capture['REQUEST.bin'], capture['RESPONSE.bin']
    provider = contract['provider']
    need(request == bridge.request_body(context['prompt'], provider['model'], provider['max_output_tokens']),
         'Raw request changed/truncated or requested different policy')
    answer, metadata = bridge.completed_text(response, context['trial_id'], provider['model'], provider['max_output_tokens'])
    need(outgoing[4:] == answer, 'First emitted response differs from provider body')
    end = decode(capture['END.json']); cleanup = end.get('owned_cleanup', {}); stderr = end.get('stderr_capture', {})
    need(end.get('schema') == 'erp_full32_provider_owned_episode_v1' and end.get('status') == 'closed_first_answer' and
         end.get('error_type') is None and type(end.get('pid')) is int and end['pid'] > 1 and
         all(end.get(k) == context[k] for k in ('trial_id', 'condition', 'context_sha256')) and
         type(end.get('returncode')) is int and end['returncode'] == 0 and
         end.get('first_response_immutable') is True and end.get('automatic_retry') is False and
         end.get('trailing_byte') == pin(b'') and end.get('trailing_byte_hex') == '' and
         end.get('provider_context_qualified') is False and end.get('provider_tool_policy_qualified') is False and
         type(end.get('private_target_reads')) is int and end['private_target_reads'] == 0 and
         end.get('scoring_performed') is False and
         cleanup.get('pid') == end['pid'] and cleanup.get('cleanup_complete') is True and
         cleanup.get('reaped') is True and cleanup.get('group_absence_observed') is True and
         type(cleanup.get('returncode')) is int and cleanup['returncode'] == 0 and end.get('normal_exit_observed') is True and
         end.get('stdout_EOF_observed') is True, 'Genuine owned broker closure records required')
    need(stderr.get('eof_observed') is True and stderr.get('reader_joined') is True and
         stderr.get('closed') is True and stderr.get('overflow') is False and stderr.get('error') is None and
         type(stderr.get('observed_bytes')) is int and type(stderr.get('retained_bytes')) is int and
         stderr['observed_bytes'] == stderr['retained_bytes'] == len(capture['STDERR.bin']) <= 16384,
         'Complete bounded stderr custody')
    for field, name in (('config', 'CONFIG.json'), ('input', 'INPUT.bin'), ('output', 'OUTPUT.bin'), ('stderr', 'STDERR.bin')):
        need(end.get(field) == pin(capture[name]), 'Owned broker capture changed')
    need(all(type(end.get(k)) in (int, float) and math.isfinite(end[k])
             for k in ('started_monotonic', 'finished_monotonic', 'elapsed_seconds')) and
         end['elapsed_seconds'] == end['finished_monotonic'] - end['started_monotonic'] and
         0 <= end['elapsed_seconds'] <= contract['limits']['episode_work_seconds'] + contract['limits']['episode_cleanup_seconds'],
         'Finite selected broker episode clock')
    expected_receipt = {'schema': 'erp_full32_responses_bridge_v1', 'condition': CONDITIONS[0],
        'prompt': pin(prompt), 'request': pin(request), 'requested_model': provider['model'],
        'max_output_tokens': provider['max_output_tokens'], 'sender_calls_attempted': 1,
        'status': 'complete_unscored_answer', 'response': pin(response), 'answer': pin(answer),
        'retry_count': 0, 'provider_execution_qualified': False, 'provider_capacity_qualified': False,
        'provider_context_qualified': False, 'provider_tool_policy_qualified': False,
        'scientific_qualification': False, **metadata}
    need(decode(capture['BRIDGE.json']) == {'schema': 'erp_full32_provider_binding_bridge_v1',
        'config_pin': pin(capture['CONFIG.json']), 'status': 'recorded', 'receipt': expected_receipt, 'failure': None},
        'Captured bridge first response/retry/policy mismatch')
    http = decode(capture['HTTP.json'])
    need(set(http) == {'schema', 'config_pin', 'endpoint', 'request', 'response', 'status_code',
         'request_complete', 'response_complete', 'body_overflow', 'requests_attempted',
         'redirects_followed', 'retries', 'connection_closed', 'credential_retained', 'failure',
         'started_monotonic', 'finished_monotonic', 'deadline'}, 'Exact sender custody fields')
    need(http['schema'] == 'neural077_https_binding_v1' and http['config_pin'] == pin(capture['CONFIG.json']) and
         http['endpoint'] == 'https://api.openai.com/v1/responses' and
         http['request'] == pin(request) and http['response'] == pin(response) and
         type(http['status_code']) is int and http['status_code'] == 200 and
         http['request_complete'] is True and http['response_complete'] is True and
         http['body_overflow'] is False and type(http['requests_attempted']) is int and http['requests_attempted'] == 1 and
         type(http['redirects_followed']) is int and http['redirects_followed'] == 0 and
         type(http['retries']) is int and http['retries'] == 0 and http['connection_closed'] is True and
         http['credential_retained'] is False and http['failure'] is None, 'One complete nonretried HTTP exchange')
    need(all(type(http[k]) in (int, float) and math.isfinite(http[k])
             for k in ('started_monotonic', 'finished_monotonic', 'deadline')) and
         http['deadline'] == cfg['deadline'] and end['started_monotonic'] <= http['started_monotonic'] <=
         http['finished_monotonic'] <= cfg['deadline'] <= end['started_monotonic'] +
         contract['limits']['episode_work_seconds'] and
         http['finished_monotonic'] <= end['finished_monotonic'], 'HTTP custody outside its owned clock')
    return {'answer': answer, **metadata, 'captured_request_policy_verified': True,
            'provider_context_qualified': False, 'provider_tool_policy_qualified': False}


def verify_arm_header(receipt, condition, contract_pin, contract):
    schema = 'erp-full32-provider-arm-v1' if condition == CONDITIONS[0] else 'erp-full6400-numeric-arm-v1'
    need(type(receipt) is dict and receipt.get('schema') == schema and receipt.get('status') == 'closed_unscored_arm' and
         receipt.get('condition') == condition and receipt.get('contract') == contract_pin and
         receipt.get('public_manifest') == contract['public_manifest'] and
         receipt.get('study_source_bindings') == contract['source_bindings'] and
         receipt.get('programme_identity') == contract['programme']['bundle_identity'] and
         receipt.get('authoring_exposure') == contract['authoring_exposure']['file'] and
         type(receipt.get('query_count')) is int and receipt['query_count'] == COUNT and
         type(receipt.get('attempt_inventory_count')) is int and receipt['attempt_inventory_count'] == COUNT and
         type(receipt.get('private_target_reads')) is int and receipt['private_target_reads'] == 0 and
         receipt.get('scoring_performed') is False, 'Complete aligned arm under the unchanged frozen study required')
    need(type(receipt.get('episodes')) is list and len(receipt['episodes']) == COUNT,
         'Incomplete attempt inventory cannot open labels')
    return receipt


def program_contract(contract, modules):
    """Only shared programme-admission fields; never relabel direct/provider evidence."""
    return {'public_manifest': contract['public_manifest'], 'source_bindings': pin(modules['core_bindings_body']),
            'bundles': {CONDITIONS[1]: contract['programme']}}


def capture_paths(root):
    return {name: root / ('custody/' + name if name in ('REQUEST.bin', 'RESPONSE.bin', 'HTTP.json', 'BRIDGE.json')
                         else name) for name in CAPTURE_NAMES}


def read_provider_capture(root, budget):
    limits = {'INPUT.bin': PROMPT_CAP + 4, 'OUTPUT.bin': RESPONSE_CAP + 4,
              'REQUEST.bin': 8 * 1024**2, 'RESPONSE.bin': PROVIDER_CAP, 'STDERR.bin': 16384}
    need({x.name for x in root.iterdir()} == {'CONFIG.json', 'INPUT.bin', 'OUTPUT.bin', 'END.json', 'STDERR.bin', 'custody'} and
         {x.name for x in (root / 'custody').iterdir()} == {'REQUEST.bin', 'RESPONSE.bin', 'HTTP.json', 'BRIDGE.json'},
         'Exact provider custody membership')
    return {name: read(path, limits.get(name, 16384), budget=budget, empty=name == 'STDERR.bin')
            for name, path in capture_paths(root).items()}


def admit_direct_arm(desc, contract, contract_pin, session, modules, budget, deadline):
    need(type(desc) is dict and set(desc) == {'root', 'receipt'}, 'Exact direct arm descriptor')
    root = ordinary_path(desc['root'])
    receipt = verify_arm_header(decode(read(root / 'ARM.json', ARM_CAP, desc['receipt'], budget)),
                                CONDITIONS[0], contract_pin, contract)
    need(receipt.get('provider') == contract['provider'] and
         receipt.get('captured_request_policy_verified') is True and
         receipt.get('provider_context_qualified') is False and receipt.get('provider_tool_policy_qualified') is False,
         'Separate captured-provider scope; no hidden-policy attestation')
    predictions_body = read(root / 'collection/predictions.jsonl', 2 * 1024**2, receipt['predictions'], budget)
    predictions = modules['core'].parse_prediction_rows(predictions_body, session.trial_ids)
    complete = decode(read(root / 'collection/COMPLETE.json', 131072, receipt['collection'], budget))
    need(complete.get('status') == 'complete_unscored_submission' and complete.get('condition') == CONDITIONS[0] and
         complete.get('responses') == COUNT and complete.get('predictions') == receipt['predictions'] and
         complete.get('manifest_pin') == contract['public_manifest'], 'Complete target-blind direct collection')
    seen = set()
    for ordinal, (identifier, episode) in enumerate(zip(session.trial_ids, receipt['episodes'], strict=True)):
        need(time.monotonic() < deadline and episode['trial_id'] == identifier and episode['status'] == 'ok',
             'Aligned complete first-response inventory')
        context = session.context(identifier, CONDITIONS[0]); budget.input(PROMPT_CAP)
        capture = read_provider_capture(root / f'{ordinal:04d}', budget)
        need(pin(capture['END.json']) == episode['end'], 'Episode changed after arm commitment')
        observed = validate_provider_capture(context, contract, capture, modules['bridge'])
        need(observed['provider_response_id'] not in seen, 'Reused provider response identity')
        seen.add(observed['provider_response_id'])
        need(modules['consumer'].parse_response(observed['answer'].decode(), identifier) == predictions[identifier],
             'Collected prediction differs from first provider answer')
    return predictions


def admit_program_arm(desc, contract, contract_pin, session, modules, budget, deadline):
    root = ordinary_path(desc['root'])
    receipt = verify_arm_header(decode(read(root / 'ARM.json', ARM_CAP, desc['receipt'], budget)), CONDITIONS[1], contract_pin, contract)
    # The unchanged helper has an8GiB internal read cap; account its exact charged
    # amount after execution and reserve its full possible spend beforehand.
    need(budget.read + modules['core'].EVALUATOR_READ_CAP <= budget.read_limit,
         'Selected read allowance cannot cover original programme admission')
    old_budget = {'read': 0}
    try:
        predictions = modules['core']._admit_public_arm(desc, CONDITIONS[1], program_contract(contract, modules),
                                                        contract_pin, session, modules, old_budget, deadline)
    finally:
        budget.input(old_budget['read'])
    profile = modules['wire'].sandbox_profile(root / 'CLIENT.py').encode()
    for ordinal, item in enumerate(receipt['episodes']):
        path = root / f'{ordinal:04d}'
        end = decode(read(path / 'END.json', 16384, item['end'], budget))
        envelope = decode(read(path / 'ATTEMPT.json', 16384, end['attempt'], budget))
        # The original helper already authenticated each complete context/frame.
        context = {k: end[k] for k in ('trial_id', 'condition', 'context_sha256')}
        accept_programme(envelope, end, context, modules)
        stderr = read(path / 'STDERR.bin', 16384, end['stderr_capture']['file'], budget, empty=True)
        need(len(stderr) == end['stderr_capture']['observed_bytes'] == end['stderr_capture']['retained_bytes'],
             'Programme diagnostic bytes incomplete')
        need(read(path / 'sandbox.sb', 8192, budget=budget) == profile, 'Programme sandbox capture changed')
        need(modules['consumer'].parse_response(envelope['response'], item['trial_id']) == predictions[item['trial_id']],
             'Programme attempt differs from original first frame')
    return predictions


def paired_metrics(core, a, b, people, conditions=CONDITIONS):
    """Shared participant metrics, after complete public custody and protected join.

    This helper does not open private data, execute candidates or implement a
    bootstrap. Both existing numeric and explicit visual routes call the same
    original core.metric_rows kernel and participant difference calculation.
    """
    need(tuple(conditions) in (CONDITIONS, ('visual_direct_four_demo', 'visual_program_four_demo')),
         'Explicit paired numeric or visual condition identity')
    need(len(people) == 32 and sum(len(rows) for rows in people.values()) == COUNT,
         'Complete finite full32 cohort required')
    expected = {identifier for rows in people.values() for identifier, _ in rows}
    need(len(expected) == COUNT and set(a) == set(b) == expected, 'Both complete6400 prediction maps')
    scores = {conditions[0]: core.metric_rows(a, people), conditions[1]: core.metric_rows(b, people)}
    differences = [{'participant_id': x['participant_id'],
        'direct_minus_program_balanced_accuracy': x['balanced_accuracy'] - y['balanced_accuracy'],
        'direct_minus_program_natural_log_loss': x['natural_log_loss'] - y['natural_log_loss']}
        for x, y in zip(scores[conditions[0]]['participants'], scores[conditions[1]]['participants'], strict=True)]
    return {'scores': scores, 'paired_person_differences': differences,
            'primary_direct_minus_program_macro_BA': sum(x['direct_minus_program_balanced_accuracy'] for x in differences) / 32}


def evaluate_pair(contract, contract_pin, arms, private_material_descriptor, output, *,
                  modules=None, deadline=None, session_factory=None):
    validate_contract(contract)
    need(pin(encode(contract)) == contract_pin, 'Canonical frozen contract commitment changed')
    modules = dependencies(contract['source_bindings']) if modules is None else modules
    need(type(arms) is dict and set(arms) == set(CONDITIONS), 'Both paired arms required')
    started = time.monotonic()
    deadline = started + contract['limits']['campaign_seconds'] if deadline is None else deadline
    need(type(deadline) in (int, float) and math.isfinite(deadline) and
         started < deadline <= started + contract['limits']['campaign_seconds'], 'Selected evaluation deadline')
    budget = Budget(contract['limits']['read_bytes'], contract['limits']['write_bytes'], deadline)
    budget.input(3 * 384000000 + 16 * 1024**2)
    verify_frozen(contract, modules, budget)
    output = disjoint_output(output, modules, (*study_roots(contract),
        *(ordinary_path(arms[c]['root']) for c in CONDITIONS)))
    # Both compact headers are checked before packet construction or any private path.
    for condition in CONDITIONS:
        desc = arms[condition]
        need(type(desc) is dict and set(desc) == {'root', 'receipt'}, 'Exact arm descriptor')
        verify_arm_header(decode(read(ordinary_path(desc['root']) / 'ARM.json', ARM_CAP, desc['receipt'], budget)),
                          condition, contract_pin, contract)
    factory = modules['consumer'].PacketSession if session_factory is None else session_factory
    with factory(contract['public_root'], contract['public_manifest']) as session:
        need(len(session.trial_ids) == COUNT and len(set(session.trial_ids)) == COUNT and
             tuple(session.trial_ids) == tuple(sorted(session.trial_ids)), 'Complete sorted full32 roster')
        a = admit_direct_arm(arms[CONDITIONS[0]], contract, contract_pin, session, modules, budget, deadline)
        b = admit_program_arm(arms[CONDITIONS[1]], contract, contract_pin, session, modules, budget, deadline)
        # An external private descriptor can be lazy. It is called only here.
        need(budget.read + 16 * 1024**2 <= budget.read_limit, 'Private join finite read headroom required')
        private = private_material_descriptor() if callable(private_material_descriptor) else private_material_descriptor
        private_root = ordinary_path(private['root'])
        need(not output.is_relative_to(private_root) and not private_root.is_relative_to(output),
             'Evaluation output must be disjoint from protected material')
        private_budget = {'read': 0}
        try:
            people = modules['core'].load_private_people(private, contract['public_manifest'], set(session.trial_ids), private_budget)
        finally:
            budget.input(private_budget['read'])
    metrics = paired_metrics(modules['core'], a, b, people)
    result = {'schema': 'erp-full32-protected-pair-evaluation-v1', 'status': 'complete_finite_cohort_pair',
        'people': 32, 'queries': COUNT, **metrics,
        'both_public_arms_and_owned_closures_validated_before_private': True, 'contract': contract_pin,
        'public_arm_receipts': [arms[c]['receipt'] for c in CONDITIONS], 'read_bytes_charged': budget.read,
        'read_charge_scope': 'Conservative source/session reservations plus explicit retained-file reads; not physical I/O.',
        'outer_campaign_and_resource_qualification_required': True, 'new_benchmarks': 0,
        'provider_context_qualified': False, 'provider_tool_policy_qualified': False,
        'captured_request_policy_verified': True,
        'capture_provenance': 'Conditional on trusted broker/custody host; raw policy echoes do not prove hidden provider state.',
        'source_evidence': {'study_source_bindings': contract['source_bindings'],
                            'original_grader_source': contract['adapter_sources']['core']},
        'interpretation': 'Event-label classification in the finite remaining32 cohort. No physiological P3-presence or pretrained-source-unseen claim.',
        'bootstrap_interval': 'Use the separately frozen full32 paired-participant bootstrap; none computed here.'}
    output.mkdir(mode=0o700); write(output / 'RESULT.json', encode(result), budget)
    return result


def append_row(stream, value, budget):
    body = encode(value); need(len(body) <= 16384, 'Bounded inventory row')
    budget.output(len(body)); stream.write(body); stream.flush(); os.fsync(stream.fileno())


def executable(row, budget):
    read(row['path'], 64 * 1024**2, {k: row[k] for k in ('bytes', 'sha256')}, budget)
    need(os.access(row['path'], os.X_OK), 'Selected executable permission required')


def read_credential(fd, deadline):
    """The later selected operator supplies a private pipe; no environment/file key lookup."""
    need(type(fd) is int and fd >= 3 and stat.S_ISFIFO(os.fstat(fd).st_mode), 'Private credential pipe required')
    result = bytearray()
    try:
        os.set_blocking(fd, False)
        with selectors.DefaultSelector() as selector:
            selector.register(fd, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                need(remaining > 0 and selector.select(remaining), 'Credential pipe deadline')
                try:
                    body = os.read(fd, 4097 - len(result))
                except BlockingIOError:
                    continue
                if not body:
                    break
                result.extend(body); need(len(result) <= 4096, 'Credential pipe byte cap')
        need(1 <= len(result) <= 4096 and all(33 <= b <= 126 for b in result), 'Bounded ASCII credential required')
        return result
    except BaseException:
        result[:] = b'\0' * len(result)
        raise
    finally:
        os.close(fd)


def accept_programme(envelope, end, context, modules):
    """Admit any valid first probability from the selected bundle; no fixed-canary override."""
    need(type(envelope) is dict and set(envelope) == {'trial_id', 'condition', 'context_sha256',
         'status', 'response', 'error'} and envelope['status'] == 'ok' and envelope['error'] is None and
         all(envelope[k] == context[k] for k in ('trial_id', 'condition', 'context_sha256')),
         'Selected programme first response failed')
    modules['consumer'].parse_response(envelope['response'], context['trial_id'])
    need(modules['runtime'].end_closed(end) and end.get('status') == 'ok' and
         type(end.get('returncode')) is int and end['returncode'] == 0 and
         end.get('normal_exit_observed') is True and
         all(end.get(k) == context[k] for k in ('trial_id', 'condition', 'context_sha256')),
         'Complete real programme episode closure required')
    stderr = end.get('stderr_capture') or {}
    need(stderr.get('eof_observed') is True and stderr.get('overflow') is False and stderr.get('error') is None,
         'Clean complete programme stderr custody required')


def run_arm(contract, contract_pin, condition, output, *, credential_fd=None, modules=None):
    """Later explicit invocation only. No target descriptor or grader exists in this path."""
    validate_contract(contract)
    need(pin(encode(contract)) == contract_pin, 'Canonical frozen contract commitment changed')
    need(condition in CONDITIONS, 'One selected full32 condition required')
    need((condition == CONDITIONS[0] and type(credential_fd) is int and credential_fd >= 3) or
         (condition == CONDITIONS[1] and credential_fd is None), 'Credential pipe only for selected direct arm')
    started = time.monotonic(); limits = contract['limits']; deadline = started + limits['campaign_seconds']
    budget = Budget(limits['read_bytes'], limits['write_bytes'], deadline)
    budget.input(4 * 1024**2)  # Named source closure/configuration admission reservation.
    modules = dependencies(contract['source_bindings']) if modules is None else modules
    frozen = verify_frozen(contract, modules, budget)
    output = disjoint_output(output, modules, study_roots(contract))
    need(not any(output.is_relative_to(Path(p)) for p in ('/System', '/usr', '/Library/Frameworks')),
         'Arm output must not be visible through programme runtime roots')
    executable(contract['interpreter'], budget)
    if condition == CONDITIONS[1]:
        need(sys.platform == 'darwin' and any(Path(contract['interpreter']['path']).is_relative_to(Path(p))
             for p in ('/System', '/usr', '/Library/Frameworks')), 'Pinned interpreter outside accepted macOS sandbox roots')
        executable(contract['sandbox'], budget)
    else:
        need(limits['episode_work_seconds'] > modules['http_client'].CUSTODY_SECONDS + 2,
             'Provider episode must leave bootstrap and custody time')
    need(limits['campaign_seconds'] > limits['episode_work_seconds'] + limits['episode_cleanup_seconds'] + 5,
         'Campaign must retain failure-finalization time')
    output.mkdir(mode=0o700)
    write(output / 'CONTRACT.json', encode(contract), budget)
    write(output / 'EXPOSURE.json', frozen['exposure'], budget)
    if condition == CONDITIONS[1]:
        write(output / 'FROZEN.json', frozen['programme'], budget)
        client = output / 'CLIENT.py'; client_pin = write(client, frozen['client'], budget)
    else:
        client = None; client_pin = None
    journal = attempts = None; credential = bytearray(); episodes = []; response_ids = set()
    identifiers = (); attempted = succeeded = 0; last_closed = True
    try:
        journal = (output / 'STATUS.jsonl').open('xb', buffering=0)
        attempts = (output / 'ATTEMPTS.jsonl').open('xb', buffering=0)
        if condition == CONDITIONS[0]:
            credential = read_credential(credential_fd, min(deadline - 5, time.monotonic() + 5))
        budget.input(SESSION_RESERVE)
        with modules['consumer'].PacketSession(contract['public_root'], contract['public_manifest']) as session:
            identifiers = tuple(session.trial_ids)
            need(len(identifiers) == COUNT and len(set(identifiers)) == COUNT and
                 identifiers == tuple(sorted(identifiers)), 'Complete original 6400 roster required')
            write(output / 'INITIAL.jsonl', b''.join(encode({'ordinal': n, 'trial_id': i, 'status': 'unattempted'})
                                                    for n, i in enumerate(identifiers)), budget)
            facade = types.SimpleNamespace(ordinary_path=ordinary_path, context_frame=modules['core'].context_frame,
                        PREFIX=PREFIX, need=need, pin=pin, encode=encode, write=write)
            for ordinal, identifier in enumerate(identifiers):
                need(time.monotonic() + limits['episode_work_seconds'] + limits['episode_cleanup_seconds'] + 5 < deadline,
                     'Insufficient selected time for another complete episode; no retry')
                need(budget.written + 2 * 1024**2 <= budget.write_limit,
                     'Insufficient selected artifact headroom for another episode')
                budget.input(2 * PROMPT_CAP + 65536)
                direct = session.context(identifier, CONDITIONS[0]); programme = session.context(identifier, CONDITIONS[1])
                modules['runtime'].matched_commitment(direct, programme, modules['consumer'].NO_TOOLS,
                                                      modules['consumer'].PROGRAMME_TOOLS)
                context = direct if condition == CONDITIONS[0] else programme
                path = output / f'{ordinal:04d}'
                append_row(journal, {'ordinal': ordinal, 'trial_id': identifier, 'status': 'dispatch_started'}, budget)
                attempted += 1; last_closed = False
                if condition == CONDITIONS[0]:
                    envelope, end = modules['broker'].provider_episode(sys.modules[__name__], context, path,
                        contract, modules, budget, deadline - 5, credential)
                    cleanup = end.get('owned_cleanup') or {}
                    last_closed = (cleanup.get('cleanup_complete') is True and cleanup.get('reaped') is True and
                                   cleanup.get('group_absence_observed') is True and end.get('stdout_EOF_observed') is True and
                                   (end.get('stderr_capture') or {}).get('reader_joined') is True)
                else:
                    read(client, 1048576, client_pin, budget)
                    envelope, end = modules['episode'].episode(facade, context, condition, path, client,
                        contract['interpreter']['path'], limits, deadline - 5, modules, budget,
                        generated_protocol_only=False)
                    last_closed = modules['runtime'].end_closed(end)
                append_row(attempts, envelope, budget)
                append_row(journal, {'ordinal': ordinal, 'trial_id': identifier, 'status': envelope['status'],
                                    'known_scope_closed': last_closed, 'end': pin(encode(end))}, budget)
                if condition == CONDITIONS[0]:
                    observed = validate_provider_capture(context, contract, read_provider_capture(path, budget), modules['bridge'])
                    need(observed['provider_response_id'] not in response_ids, 'Provider response reused across queries')
                    response_ids.add(observed['provider_response_id'])
                    need(envelope.get('status') == 'ok' and envelope.get('response') == observed['answer'].decode(),
                         'Provider first answer envelope mismatch')
                else:
                    accept_programme(envelope, end, context, modules)
                episodes.append({'trial_id': identifier, 'status': 'ok', 'end': pin(encode(end))}); succeeded += 1
            verify_frozen(contract, modules, budget)
            # Original collector preserves raw envelopes and recomputes every public context.
            # Its original finite read/write maxima are reserved before entering it.
            budget.input(2 * modules['consumer'].LEDGER_LIMIT + COUNT * PROMPT_CAP)
            budget.output(modules['consumer'].LEDGER_LIMIT + 2 * 1024**2 + 131072)
            modules['consumer'].collect(session, condition, output / 'ATTEMPTS.jsonl', output / 'collection', deadline - 2)
        predictions = pin(read(output / 'collection/predictions.jsonl', 2 * 1024**2, budget=budget))
        collection = pin(read(output / 'collection/COMPLETE.json', 131072, budget=budget))
        receipt = {'schema': 'erp-full32-provider-arm-v1' if condition == CONDITIONS[0] else 'erp-full6400-numeric-arm-v1',
            'status': 'closed_unscored_arm', 'condition': condition, 'contract': contract_pin,
            'public_manifest': contract['public_manifest'], 'study_source_bindings': contract['source_bindings'],
            'programme_identity': contract['programme']['bundle_identity'],
            'authoring_exposure': contract['authoring_exposure']['file'], 'query_count': COUNT,
            'attempt_inventory_count': attempted, 'private_target_reads': 0, 'scoring_performed': False,
            'episodes': episodes, 'predictions': predictions, 'collection': collection,
            'read_bytes_charged': budget.read, 'written_bytes_charged_before_arm': budget.written,
            'resource_charge_scope': 'Conservative source/session/collector/custody reservations plus exact retained I/O.',
            'provider_context_qualified': False, 'provider_tool_policy_qualified': False,
            'outer_campaign_and_resource_qualification_required': True,
            'escaped_descendant_containment_qualified': False, 'new_benchmarks': 0}
        if condition == CONDITIONS[0]:
            receipt.update(provider=contract['provider'], captured_request_policy_verified=True,
                           provider_requests_admitted=COUNT, capture_provenance='Trusted operator custody; hidden provider state unqualified.')
        else:
            receipt.update(source_bindings=pin(modules['core_bindings_body']),
                           bundle_identity=contract['programme']['bundle_identity'], model_calls=0,
                           programme_selection='Explicit captured programme; no automatic canary or scientific baseline qualification.')
        write(output / 'ARM.json', encode(receipt), budget)
        return receipt
    except BaseException as exc:
        failure = {'schema': 'erp-full32-provider-pair-failure-v1', 'status': 'failed_no_partial_admission',
            'condition': condition, 'contract': contract_pin, 'error_type': type(exc).__name__,
            'attempted': attempted, 'succeeded': succeeded, 'failed_or_unresolved': attempted - succeeded,
            'unattempted': COUNT - attempted, 'initial_roster_retained': bool(identifiers),
            'last_known_scope_closed': last_closed, 'automatic_retry': False,
            'private_target_reads': 0, 'scoring_performed': False,
            'read_bytes_charged': budget.read, 'written_bytes_charged': budget.written}
        # Even if the outer clock/OS prevents this final record, the create-only
        # INITIAL and dispatch journal remain; such a directory has no ARM admission.
        write(output / 'FAILED.json', encode(failure), budget)
        raise
    finally:
        credential[:] = b'\0' * len(credential)
        for stream in (journal, attempts):
            if stream is not None:
                stream.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    freeze_parser = commands.add_parser('freeze')
    freeze_parser.add_argument('--spec', required=True)
    freeze_parser.add_argument('--spec-bytes', required=True, type=int)
    freeze_parser.add_argument('--spec-sha256', required=True)
    freeze_parser.add_argument('--output', required=True)
    for command in ('run-arm', 'evaluate'):
        p = commands.add_parser(command)
        p.add_argument('--contract', required=True); p.add_argument('--contract-bytes', required=True, type=int)
        p.add_argument('--contract-sha256', required=True); p.add_argument('--output', required=True)
        if command == 'run-arm':
            p.add_argument('--condition', choices=CONDITIONS, required=True)
            p.add_argument('--credential-fd', type=int)
        else:
            p.add_argument('--arms', required=True)
            p.add_argument('--private-material', required=True)
    args = parser.parse_args(argv)
    if args.command == 'freeze':
        selected = {'bytes': args.spec_bytes, 'sha256': args.spec_sha256}; descriptor(selected, CONTRACT_CAP)
        result = freeze(decode(read(args.spec, CONTRACT_CAP, selected)), args.output)
    else:
        selected = {'bytes': args.contract_bytes, 'sha256': args.contract_sha256}; descriptor(selected, CONTRACT_CAP)
        contract = decode(read(args.contract, CONTRACT_CAP, selected))
        if args.command == 'run-arm':
            result = run_arm(contract, selected, args.condition, args.output, credential_fd=args.credential_fd)
        else:
            arms = decode(read(args.arms, CONTRACT_CAP))
            # Do not even resolve/stat this private descriptor until both arms pass.
            result = evaluate_pair(contract, selected, arms,
                lambda: decode(read(args.private_material, CONTRACT_CAP)), args.output)
    print(json.dumps({'status': result['status'], 'output': args.output}, sort_keys=True))


if __name__ == '__main__':
    main()
