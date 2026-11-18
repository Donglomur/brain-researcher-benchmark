"""Trusted restricted-viewer provider arm, full public admission and protected pairing.

The original numerical programme, targets, references and metrics are unchanged.
Only an explicit operator credential pipe permits provider execution. Source
controls and receipt admission do not establish remote policy or model ability.
"""
from pathlib import Path
import argparse
import base64
import io
import math
import os
import platform
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict

import support as v

HERE = Path(__file__).resolve().parent
ARM = 'neural077_visual_provider_pair_arm_v1'
ROUTE = 'trusted_image_history_provider_and_numerical_programme_v1'
CONDITION = 'four_demo'


def budgets(transport, query_seconds, campaign_seconds, max_request_bytes,
            max_query_request_bytes, max_query_response_bytes,
            max_campaign_request_bytes, max_campaign_response_bytes):
    for value, lo, hi in ((query_seconds, 5, 3600), (campaign_seconds, query_seconds, 86400)):
        v.need(type(value) in (int, float) and math.isfinite(value) and lo <= value <= hi, 'Finite wall allocation')
    for value, hi in ((max_request_bytes, 8 * 1024**2), (max_query_request_bytes, 512 * 1024**2),
                      (max_query_response_bytes, 128 * 1024**2),
                      (max_campaign_request_bytes, 1024**4), (max_campaign_response_bytes, 1024**4)):
        v.need(type(value) is int and 0 < value <= hi, 'Finite cumulative byte allocation')
    t = transport.Limits(wall_seconds=query_seconds)
    t.validate()
    return {'query_seconds': query_seconds, 'campaign_seconds': campaign_seconds,
            'max_request_bytes': max_request_bytes, 'max_query_request_bytes': max_query_request_bytes,
            'max_query_response_bytes': max_query_response_bytes,
            'max_campaign_request_bytes': max_campaign_request_bytes,
            'max_campaign_response_bytes': max_campaign_response_bytes,
            'transport': asdict(t), 'maximum_provider_requests': 400 * (t.max_actions - 1)}


def dataset_for(deps, packet):
    data = deps['transport'].v.source(packet, deps['root'])
    rows = data['rows']
    v.need(len(rows) == 400 and len({r['trial_id'] for r in rows}) == 400, 'Complete 400 query roster')
    cases = deps['original']['pair'].CASES
    deps['original']['comparator'].roster({c: [r['trial_id'] for r in rows if r['trial_id'].startswith(c + '-')] for c in cases})
    v.need([r['trial_id'] for r in rows] == [r['trial_id'] for r in data['roster']], 'Exact ordered public packet')
    return data


def configuration(deps, trial_id, model, max_output_tokens, deadline, limits):
    s = deps['s']
    return {'schema': 'neural077_visual_provider_client_v1', 'model': model,
            'max_output_tokens': max_output_tokens, 'deadline': deadline, 'trial_id': trial_id,
            'implementations_root': str(deps['root']), 'source_bindings': deps['bindings'],
            'max_request_bytes': limits['max_request_bytes'], 'max_requests': limits['transport']['max_actions'] - 1,
            'max_query_request_bytes': limits['max_query_request_bytes'],
            'max_query_response_bytes': limits['max_query_response_bytes'],
            'bridge_path': str(HERE / 'visual_bridge.py'), 'bridge_pin': v.pin(s.read(HERE / 'visual_bridge.py')),
            'sender_path': str(deps['root'] / 'waveform-provider-v1/client.py'),
            'sender_pin': deps['bindings']['waveform-provider-v1/client.py'],
            'codec_path': str(HERE / 'transfer_png.py'), 'codec_pin': v.pin(s.read(HERE / 'transfer_png.py'))}


def credential(fd, deps):
    old = sys.modules.get('support')
    try:
        sys.modules['support'] = deps['s']
        arm = v.module('n077_original_credential_reader', deps['root'] / 'waveform-provider-v1/provider_arm.py',
                       deps['original_bodies']['waveform-provider-v1/provider_arm.py'])
    finally:
        if old is None:
            sys.modules.pop('support', None)
        else:
            sys.modules['support'] = old
    return arm.credential(fd, deps['original']['transport'])


def launch_client(command, cwd, token, config_body, provider_root, deps):
    """Trusted launcher only: no dataset paths or targets reach the provider child."""
    t = deps['transport']; s = deps['s']; cfg = s.decode(config_body)
    owned, child = set(), None
    try:
        ar, aw = os.pipe(); owned.update((ar, aw))
        cr, cw = os.pipe(); owned.update((cr, cw))
        directory = os.open(provider_root / 'custody', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        owned.add(directory)
        argv = command + ['--credential-fd', str(ar), '--config-fd', str(cr), '--custody-fd', str(directory)]
        child = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                 cwd=cwd, env={'LANG': 'C', 'LC_ALL': 'C'}, close_fds=True,
                                 pass_fds=(ar, cr, directory), start_new_session=True)
        for fd in (ar, cr, directory):
            os.close(fd); owned.remove(fd)
        for fd, raw in ((cw, config_body), (aw, token)):
            os.set_blocking(fd, False)
            t.write_frame(fd, raw, cfg['deadline'])
            os.close(fd); owned.remove(fd)
        return child
    except BaseException:
        if child is not None:
            try:
                os.killpg(child.pid, 9)
            except ProcessLookupError:
                pass
            child.wait()
            child.stdin.close(); child.stdout.close()
        raise
    finally:
        for fd in owned:
            os.close(fd)


def _http(http, config_pin, request, response, deadline):
    fixed = {'schema': 'neural077_https_binding_v1', 'config_pin': config_pin,
             'endpoint': 'https://api.openai.com/v1/responses', 'request': v.pin(request), 'response': v.pin(response),
             'status_code': 200, 'request_complete': True, 'response_complete': True, 'body_overflow': False,
             'requests_attempted': 1, 'redirects_followed': 0, 'retries': 0, 'connection_closed': True,
             'credential_retained': False, 'failure': None, 'deadline': deadline}
    v.need(set(http) == set(fixed) | {'started_monotonic', 'finished_monotonic'}, 'Exact HTTP receipt')
    for key, expected in fixed.items():
        v.need(type(http[key]) is type(expected) and http[key] == expected, 'HTTP policy/custody mismatch')
    v.need(all(type(http[k]) in (int, float) and math.isfinite(http[k]) for k in ('started_monotonic', 'finished_monotonic'))
           and http['started_monotonic'] <= http['finished_monotonic'] <= deadline, 'HTTP deadline exceeded')


def audit_episode(root, provider_root, dataset, ordinal, deps, manifest):
    """Rebuild every full image-history request from audited exact viewer frames."""
    s, t, b = deps['s'], deps['transport'], deps['bridge']
    root, provider_root = s.path(root), s.path(provider_root)
    v.need({p.name for p in provider_root.iterdir()} == {'CONFIG.json', 'custody', 'OPERATOR_END.json'},
           'Exact provider episode inventory')
    end = t.audit_transport(root, dataset, ordinal, CONDITION)
    transport_manifest = s.decode(s.read(root / 'transport/MANIFEST.json', 32768))
    v.need(transport_manifest == t.boundary_manifest(t.Limits(**manifest['limits']['transport']),
            'protocol_only', HERE / 'visual_client.py', transport_manifest['episode_id'], None),
            'Exact trusted transport boundary manifest')
    v.need(transport_manifest['sandbox'] == 'protocol_only'
           and transport_manifest['client_sha256'] == manifest['operator']['visual_client.py']['sha256']
           and transport_manifest['limits'] == manifest['limits']['transport'], 'Trusted visual transport profile')
    config_body = s.read(provider_root / 'CONFIG.json', 32768); cfg = s.decode(config_body)
    v.need(type(cfg['deadline']) in (int, float) and math.isfinite(cfg['deadline'])
           and cfg == configuration(deps, dataset['rows'][ordinal]['trial_id'], manifest['model'],
                                    manifest['max_output_tokens'], cfg['deadline'], manifest['limits']),
           'Exact query/source configuration')
    operator_end = s.decode(s.read(provider_root / 'OPERATOR_END.json', 16384))
    v.need(set(operator_end) == {'started_monotonic', 'finished_monotonic', 'config', 'transport_end'}
           and all(type(operator_end[k]) in (int, float) and math.isfinite(operator_end[k])
                   for k in ('started_monotonic', 'finished_monotonic'))
           and manifest['started_monotonic'] <= operator_end['started_monotonic']
           <= operator_end['finished_monotonic'] <= manifest['deadline']
           and operator_end['finished_monotonic'] - operator_end['started_monotonic'] <= manifest['limits']['query_seconds']
           and cfg['deadline'] == min(operator_end['started_monotonic'] + manifest['limits']['query_seconds'], manifest['deadline']) - 2
           and operator_end['config'] == v.pin(config_body)
           and operator_end['transport_end'] == v.pin(s.read(root / 'transport/END.json', 32768)), 'Query clock/closure mismatch')
    turns = (end['messages'] - 1) // 2
    v.need(1 <= turns <= cfg['max_requests'], 'Finite actual provider turn count')
    custody = provider_root / 'custody'
    v.need({p.name for p in custody.iterdir()} == {f'{i:03d}' for i in range(turns)} | {'CLIENT_END.json'},
           'Exact complete provider turns')
    codec = v.module('n077_visual_lossless_auditor', HERE / 'transfer_png.py', s.read(HERE / 'transfer_png.py'))
    history = None; provider_ids = []; requests = responses = 0
    usage = {k: 0 for k in ('input_tokens', 'output_tokens', 'total_tokens')}
    prior_action = None; first_frame_pin = None; final_response = None
    previous_http_end = operator_end['started_monotonic']
    for i in range(turns):
        row = custody / f'{i:03d}'
        v.need({p.name for p in row.iterdir()} == {'REQUEST.bin', 'RESPONSE.bin', 'HTTP.json', 'BRIDGE.json'}, 'Complete turn custody')
        frame = s.read(root / f'transport/{2*i:04d}-out.bin', t.PNG_MAX + t.HEADER_MAX + 8)
        header, original_png = t.unpack(frame)
        wire_action = s.read(root / f'transport/{2*i+1:04d}-in.bin', t.v.MAX_REQUEST + 8)
        action_header, no_png = t.unpack(wire_action, inbound=True)
        action = wire_action[8:]
        request = s.read(row / 'REQUEST.bin', cfg['max_request_bytes'])
        response = s.read(row / 'RESPONSE.bin', 524288)
        binding = s.decode(s.read(row / 'BRIDGE.json', 32768))
        parsed_request = b.decode(request)
        def delivered_png(raw):
            content = parsed_request['input'][-1]['content']
            images = [x for x in content if x.get('type') == 'input_image']
            v.need(len(images) == 1 and images[0]['image_url'].startswith('data:image/png;base64,'), 'One delivered image for frame')
            delivered = base64.b64decode(images[0]['image_url'].split(',', 1)[1], validate=True)
            mapping = binding['image_mapping']
            codec.verify_equivalence(raw, delivered, mapping)
            return delivered, mapping
        if i == 0:
            history, mapping = b.first_frame(header, original_png, cfg['trial_id'], delivered_png)
            first_frame_pin = v.pin(frame)
        else:
            v.need(final_response is None, 'No provider request after first typed finalize')
            history, mapping = b.append_frame(history, prior_action, header, original_png, delivered_png)
        v.need(request == b.request_body(history, cfg['model'], cfg['max_output_tokens'], cap=cfg['max_request_bytes']),
               'Full exact current-query image history required')
        actual_action, metadata = b.completed_action(response, cfg['model'], cfg['max_output_tokens'])
        v.need(actual_action == action and metadata['provider_response_id'] not in provider_ids,
               'Exact first action and unique provider response')
        provider_ids.append(metadata['provider_response_id']); prior_action = action
        final_response = b.typed_finalize(action)
        requests += len(request); responses += len(response)
        v.need(requests <= cfg['max_query_request_bytes'] and responses <= cfg['max_query_response_bytes'], 'Query cumulative bytes')
        for key in usage:
            usage[key] += metadata['usage'][key]
        expected = {'schema': 'neural077_visual_provider_bridge_v1', 'condition': CONDITION,
                    'config_pin': v.pin(config_body), 'turn': i, 'status': 'complete_unscored_action',
                    'frame': v.pin(frame), 'history': v.pin(b.encode(history)), 'image_mapping': mapping,
                    'request': v.pin(request), 'response': v.pin(response), 'action': v.pin(action),
                    **metadata, 'request_bytes_total': requests, 'response_bytes_total': responses,
                    'retry_count': 0, 'response_charge_is_upper_bound': False, 'provider_context_qualified': False, 'provider_capacity_qualified': False,
                    'scientific_qualification': False}
        v.need(binding == expected, 'Exact provider bridge receipt')
        http = s.decode(s.read(row / 'HTTP.json', 16384))
        _http(http, v.pin(config_body), request, response, cfg['deadline'])
        v.need(previous_http_end <= http['started_monotonic'] <= http['finished_monotonic'] <= operator_end['finished_monotonic'],
               'Provider turn order/clock mismatch')
        previous_http_end = http['finished_monotonic']
    terminal = s.read(root / f'transport/{2*turns:04d}-out.bin', t.HEADER_MAX + 8)
    v.need(final_response is not None and final_response == s.read(root / 'response.txt', 4096), 'First final response binding')
    client_end = s.decode(s.read(custody / 'CLIENT_END.json', 65536))
    expected_end = {'schema': 'neural077_visual_provider_client_end_v1', 'condition': CONDITION,
                    'config_pin': v.pin(config_body), 'status': 'closed_first_final', 'turns': turns,
                    'request_bytes': requests, 'response_bytes': responses, 'provider_response_ids': provider_ids,
                    'usage': usage, 'initial_frame': first_frame_pin, 'terminal_frame': v.pin(terminal),
                    'final_response': v.pin(final_response), 'first_finalize_terminal': True,
                    'no_further_request_after_finalize': True, 'decoded_credential_persisted': False,
                    'raw_response_literal_guard_only': True, 'response_charge_contains_upper_bound': False,
                    'remote_context_qualified': False, 'provider_capacity_qualified': False,
                    'scientific_qualification': False, 'error_type': None}
    v.need(client_end == expected_end, 'Complete first-final provider closure')
    probability = dataset['parser'].parse(final_response, cfg['trial_id'])
    return {'turns': turns, 'request_bytes': requests, 'response_bytes': responses,
            'episode_id': transport_manifest['episode_id'],
            'started_monotonic': operator_end['started_monotonic'],
            'finished_monotonic': operator_end['finished_monotonic'],
            'provider_response_ids': provider_ids, 'usage': usage, 'probability': probability,
            'transport_end': v.pin(s.read(root / 'transport/END.json', 32768)),
            'client_end': v.pin(s.read(custody / 'CLIENT_END.json', 65536))}


def _sum(rows, limits):
    v.need(len(rows) == 400, 'All 400 episodes required')
    v.need(len({row['episode_id'] for row in rows}) == 400
           and all(rows[i]['finished_monotonic'] <= rows[i+1]['started_monotonic'] for i in range(399)),
           'Independent fresh ordered query episodes required')
    ids = [p for row in rows for p in row['provider_response_ids']]
    v.need(len(ids) == len(set(ids)), 'No provider response reused across queries')
    result = {key: sum(row[key] for row in rows) for key in ('turns', 'request_bytes', 'response_bytes')}
    v.need(result['turns'] <= limits['maximum_provider_requests']
           and result['request_bytes'] <= limits['max_campaign_request_bytes']
           and result['response_bytes'] <= limits['max_campaign_response_bytes'], 'Whole-campaign request/byte allocation')
    result['usage'] = {k: sum(row['usage'][k] for row in rows) for k in ('input_tokens', 'output_tokens', 'total_tokens')}
    return result


def run_arm(implementations_root, packet, output, model, max_output_tokens, credential_fd, python, **allocations):
    deps = v.load(implementations_root); s, t = deps['s'], deps['transport']
    limits = budgets(t, **allocations); before = deps['operator']
    data = dataset_for(deps, packet)
    executable = Path(python).resolve(strict=True)
    executable_pin = v.pin(s.read(executable, 64*1024**2))
    token = credential(credential_fd, deps)
    output = s.path(output); owned = False; rows = []
    try:
        output.mkdir(mode=0o700); owned = True
        (output / 'sessions').mkdir(mode=0o700); (output / 'providers').mkdir(mode=0o700)
        started = time.monotonic()
        manifest = {'schema': 'neural077_visual_provider_campaign_v1', 'route': ROUTE, 'condition': CONDITION,
                    'queries': 400, 'demonstrations': 4, 'source': deps['bindings'], 'operator': before,
                    'packet': data['packet'], 'model': model, 'max_output_tokens': max_output_tokens, 'limits': limits,
                    'client_interpreter': {'path': str(executable), 'pin': executable_pin},
                    'started_monotonic': started, 'deadline': started + limits['campaign_seconds'],
                    'retry_policy': 'none', 'local_participant_sandbox': None,
                    'participant_code_executed_locally': False, 'remote_context_qualified': False,
                    'provider_capacity_qualified': False, 'scientific_qualification': False}
        s.write(output / 'MANIFEST.json', s.encode(manifest))
        for i in range(400):
            provider = output / 'providers' / f'{i:03d}'; provider.mkdir(mode=0o700)
            (provider / 'custody').mkdir(mode=0o700)
            start = time.monotonic()
            cfg = configuration(deps, data['rows'][i]['trial_id'], model, max_output_tokens,
                                min(start + limits['query_seconds'], manifest['deadline']) - 2, limits)
            # Future query caps never consume more than the remaining campaign allocation.
            remaining_request = limits['max_campaign_request_bytes'] - sum(r['request_bytes'] for r in rows)
            remaining_response = limits['max_campaign_response_bytes'] - sum(r['response_bytes'] for r in rows)
            v.need(remaining_request >= limits['max_query_request_bytes']
                   and remaining_response >= limits['max_query_response_bytes'],
                   'Reserve the declared full query cap before starting; never silently narrow it')
            v.need(time.monotonic() < cfg['deadline'], 'Campaign deadline before query')
            raw = s.encode(cfg); s.write(provider / 'CONFIG.json', raw)
            end = t.run_episode(data, i, CONDITION, output / 'sessions' / f'{i:03d}', HERE / 'visual_client.py',
                                executable, 'protocol_only', t.Limits(**limits['transport']),
                                client_launcher=lambda command,cwd: launch_client(command,cwd,token,raw,provider,deps))
            s.write(provider / 'OPERATOR_END.json', s.encode({'started_monotonic': start,
                    'finished_monotonic': time.monotonic(), 'config': v.pin(raw),
                    'transport_end': v.pin(s.read(output / 'sessions' / f'{i:03d}/transport/END.json', 32768))}))
            v.need(end['status'] == 'valid_unscored', 'Failed first-final query makes campaign unscoreable')
            rows.append(audit_episode(output / 'sessions' / f'{i:03d}', provider, data, i, deps, manifest))
        totals = _sum(rows, limits)
        collection = t.collect(packet, output / 'sessions', CONDITION, output / 'collection', deps['root'])
        v.need(v.identity(s) == before and v.load(implementations_root)['bindings'] == deps['bindings']
               and v.pin(s.read(executable, 64*1024**2)) == executable_pin, 'Source/runtime drift')
        v.need(time.monotonic() <= manifest['deadline'], 'Whole campaign including collection deadline')
        receipt = {'schema': ARM, 'status': 'closed_unscored_visual_provider_arm', 'route': ROUTE,
                   'condition': CONDITION, 'queries': 400, 'demonstrations': 4, 'source': deps['bindings'],
                   'operator': before, 'manifest': v.pin(s.read(output / 'MANIFEST.json', 65536)),
                   'episodes': [{k: row[k] for k in ('transport_end','client_end')} for row in rows],
                   'totals': totals, 'collection': v.pin(s.read(output / 'collection/TRANSPORT_COMPLETE.json', 16384)),
                   'submission': v.pin(s.read(output / 'collection/submission.npz', 1048576)),
                   'local_participant_sandbox': None, 'remote_context_qualified': False,
                   'provider_capacity_qualified': False, 'scientific_qualification': False,
                   'private_target_reads': 0, 'scoring_performed': False}
        s.write(output / 'ARM.json', s.encode(receipt))
        return receipt
    except BaseException as error:
        if owned:
            s.write(output / 'FAILED.json', s.encode({'status': 'unscoreable_visual_provider_campaign',
                    'completed_queries': len(rows), 'error_type': type(error).__name__, 'retry_allowed': False,
                    'private_target_reads': 0, 'scoring_performed': False}))
        raise
    finally:
        token[:] = b'\0' * len(token)


def admit_arm(root, expected_receipt, packet, deps):
    s, t = deps['s'], deps['transport']; root = s.path(root)
    v.need({p.name for p in root.iterdir()} == {'MANIFEST.json','sessions','providers','collection','ARM.json'},
           'Exact complete arm inventory; failed campaigns cannot be admitted')
    raw = s.read(root / 'ARM.json', 262144, expected_receipt); arm = s.decode(raw)
    fixed = {'schema': ARM, 'status': 'closed_unscored_visual_provider_arm', 'route': ROUTE,
             'condition': CONDITION, 'queries': 400, 'demonstrations': 4, 'source': deps['bindings'],
             'operator': v.identity(s), 'local_participant_sandbox': None, 'remote_context_qualified': False,
             'provider_capacity_qualified': False, 'scientific_qualification': False, 'private_target_reads': 0,
             'scoring_performed': False}
    v.need(all(type(arm.get(k)) is type(x) and arm[k] == x for k,x in fixed.items()), 'Exact visual provider arm')
    manifest = s.decode(s.read(root / 'MANIFEST.json', 65536, arm['manifest']))
    v.need(manifest['schema'] == 'neural077_visual_provider_campaign_v1'
           and all(manifest[k] == arm[k] for k in ('route','condition','queries','demonstrations','source','operator'))
           and manifest['retry_policy'] == 'none' and manifest['local_participant_sandbox'] is None
           and manifest['participant_code_executed_locally'] is False
           and manifest['remote_context_qualified'] is False and manifest['provider_capacity_qualified'] is False
           and manifest['scientific_qualification'] is False, 'Exact source and access profile')
    limits = manifest['limits']
    keys = ('query_seconds','campaign_seconds','max_request_bytes','max_query_request_bytes','max_query_response_bytes',
            'max_campaign_request_bytes','max_campaign_response_bytes')
    v.need(limits == budgets(t, **{k:limits[k] for k in keys})
           and all(type(manifest[k]) in (int,float) and math.isfinite(manifest[k]) for k in ('started_monotonic','deadline'))
           and manifest['deadline'] == manifest['started_monotonic'] + limits['campaign_seconds'], 'Exact finite campaign')
    data = dataset_for(deps, packet)
    v.need(data['packet'] == manifest['packet'], 'Original public packet changed')
    expected_names = {f'{i:03d}' for i in range(400)}
    v.need({p.name for p in (root/'sessions').iterdir()} == expected_names
           and {p.name for p in (root/'providers').iterdir()} == expected_names
           and len(arm['episodes']) == 400, 'All 400 independent complete episodes required')
    rows = [audit_episode(root/'sessions'/f'{i:03d}',root/'providers'/f'{i:03d}',data,i,deps,manifest) for i in range(400)]
    v.need(arm['episodes'] == [{k:r[k] for k in ('transport_end','client_end')} for r in rows]
           and arm['totals'] == _sum(rows,limits), 'Every query/turn bound to arm')
    collection = s.decode(s.read(root/'collection/TRANSPORT_COMPLETE.json',16384,arm['collection']))
    v.need(collection['schema'] == 'neural077_transport_collection_v1'
           and collection['status'] == 'complete_unscored_transport_collection' and collection['condition'] == CONDITION
           and type(collection['queries']) is int and collection['queries'] == 400
           and collection['submission_sha256'] == arm['submission']['sha256']
           and collection['scoring_performed'] is False and collection['provider_qualification'] == 'not_established',
           'Original complete transport collection')
    predicted = s.read(root/'collection/submission.npz',1048576,arm['submission'])
    import numpy as np
    # Preserve the original ZIP/NPY expanded-length checks before materializing
    # even public prediction arrays. Snapshot bytes cannot be swapped later.
    ids = {case: [r['trial_id'] for r in data['rows'] if r['trial_id'].startswith(case+'-')]
           for case in deps['original']['pair'].CASES}
    with tempfile.TemporaryDirectory(prefix='neural077-visual-public-') as folder:
        snapshot = Path(folder).resolve()/'submission.npz'
        s.write(snapshot,predicted)
        data['validator'].validate(snapshot,ids)
        with np.load(io.BytesIO(predicted),allow_pickle=False) as arrays:
            v.need(set(arrays.files) == {'trial_ids','target_probability'}
                   and arrays['trial_ids'].tolist() == [r['trial_id'] for r in data['rows']]
                   and np.array_equal(arrays['target_probability'],np.asarray([r['probability'] for r in rows],dtype=np.float64)),
                   'Submission must equal every first-final response')
    return root/'collection/submission.npz',arm['submission'],v.pin(raw)


def grade(request_path, expected_sha):
    # Only trusted fixed source is loaded; no participant code enters evaluator.
    import json
    request_path = Path(request_path)
    raw = v.capture(request_path, 65536)
    v.need(v.pin(raw)['sha256'] == expected_sha, 'Frozen grade request')
    preliminary = v.decode(raw)
    deps = v.load(preliminary['implementations_root']); s = deps['s']
    request=s.decode(raw); output=s.path(request['output']); output.mkdir(mode=0o700)
    accounting={'both_public_validated_before_private':False,'private_reference_attempts':0,
                'target_loader_attempts':0,'temporary_submission_bytes_created':0}
    try:
        v.need(request['schema']=='neural077_visual_provider_pair_request_v1'
               and request['operator']==deps['operator'] and request['source']==deps['bindings'],'Frozen visual evaluator identity')
        a=admit_arm(request['a']['root'],request['a']['receipt'],request['packet'],deps)
        pair=deps['original']['pair']
        b=pair._admit_arm(request['b'],'matched_waveform_programme',deps['original']['original_bindings'],pair.operator_identity())
        ids=pair.public_roster(request['delivery_root'],deps['original']['comparator'])
        result=deps['protected'].protected_compare(pair,deps['original']['comparator'],deps['original']['original_bodies'],
                                                  (a,b),ids,request['private_locations'],accounting,v.CONDITIONS)
        result.update(operator_route=ROUTE,participant_code_executed_in_evaluator=False,
                      remote_context_qualified=False,provider_capacity_qualified=False,scientific_qualification=False,
                      paired_scores_computed=True,source=deps['bindings'],operator=v.identity(s),accounting=accounting,
                      evaluator_runtime={'python':platform.python_version(),'executable':sys.executable})
        s.write(output/'RESULT.json',s.encode(result));return result
    except BaseException as error:
        s.write(output/'FAILED.json',s.encode({'status':'unscored_failure','error_type':type(error).__name__,
                                             'accounting':accounting,'retry_allowed':False}));raise


def dispatch_grade(implementations_root,packet,delivery_root,a,b,private_locations,output,timeout):
    v.need(type(timeout) in (int,float) and math.isfinite(timeout) and 0<timeout<=180,'Bounded grading deadline')
    deps=v.load(implementations_root);s=deps['s'];pair=deps['original']['pair']
    aa={'root':str(s.path(a)),'receipt':v.pin(s.read(Path(a)/'ARM.json',262144))};bb=pair._arm_descriptor(b)
    admit_arm(aa['root'],aa['receipt'],packet,deps)
    pair._admit_arm(bb,'matched_waveform_programme',deps['original']['original_bindings'],pair.operator_identity())
    output=s.path(output);output.mkdir(mode=0o700)
    request={'schema':'neural077_visual_provider_pair_request_v1','implementations_root':str(s.path(implementations_root)),
             'operator':v.identity(s),'source':deps['bindings'],'packet':str(s.path(packet)),
             'delivery_root':str(s.path(delivery_root)),'a':aa,'b':bb,
             'private_locations':str(Path(private_locations).absolute()),'output':str(output/'grade')}
    request_pin=s.write(output/'REQUEST.json',s.encode(request))
    environment={'LANG':'C','LC_ALL':'C','PYTHONDONTWRITEBYTECODE':'1','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'}
    with (output/'evaluator.log').open('xb') as log:
        try:
            child=subprocess.run([sys.executable,'-B',str(HERE/'provider_arm.py'),'_grade','--request',str(output/'REQUEST.json'),
                                  '--sha256',request_pin['sha256']],cwd=output,env=environment,stdin=subprocess.DEVNULL,
                                 stdout=log,stderr=log,timeout=timeout,close_fds=True,check=False)
            v.need(child.returncode==0,'Protected evaluator failed')
        except BaseException as error:
            s.write(output/'FAILED.json',s.encode({'status':'evaluation_dispatch_failed',
                    'error_type':type(error).__name__,'retry_allowed':False}))
            raise
    return {'status':'visual_provider_pair_evaluation_closed','request':request_pin,
            'result':v.pin(s.read(output/'grade/RESULT.json')),'private_inputs_opened_in_dispatcher':False}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    r=sub.add_parser('run')
    for name in ('implementations-root','packet','output','model','python'):r.add_argument('--'+name,required=True)
    for name in ('credential-fd','max-output-tokens','max-request-bytes','max-query-request-bytes',
                 'max-query-response-bytes','max-campaign-request-bytes','max-campaign-response-bytes'):
        r.add_argument('--'+name,type=int,required=True)
    for name in ('query-seconds','campaign-seconds'):r.add_argument('--'+name,type=float,required=True)
    c=sub.add_parser('compare')
    for name in ('implementations-root','packet','delivery-root','a','b','private-locations','output'):
        c.add_argument('--'+name,required=True)
    c.add_argument('--timeout',type=float,default=60)
    g=sub.add_parser('_grade');g.add_argument('--request',required=True);g.add_argument('--sha256',required=True)
    args=vars(p.parse_args(argv));action=args.pop('action')
    try:
        result=run_arm(**args) if action=='run' else dispatch_grade(**args) if action=='compare' else grade(args['request'],args['sha256'])
        print(result['status']);return 0
    except Exception as error:
        print('Refused: '+type(error).__name__);return 2


if __name__=='__main__':
    raise SystemExit(main())
