"""Complete N031 direct-provider preparation, owned dispatch and public admission.

No target path, grader, automatic retry, partial arm or import-time execution.
Trusted local custody does not attest a remote provider's hidden state or tools.
"""
import argparse
import math
import os
from pathlib import Path
import selectors
import stat
import struct
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).absolute().parent))
import common as c

PREFIX = struct.Struct('!I')
EPISODE_FILES = {'CONFIG.json', 'INPUT.bin', 'OUTPUT.bin', 'STDERR.bin', 'END.json', 'custody'}


def contract(value, source_sha):
    c.need(type(value) is dict and set(value) == {'schema', 'source_sha256', 'condition',
           'provider', 'interpreter', 'limits', 'authoring_exposure', 'selection', 'support', 'contexts'} and
           value['schema'] == 'neural031_provider_contract_v1' and value['source_sha256'] == source_sha and
           value['condition'] == c.CONDITION, 'exact_frozen_contract')
    c.policy(value['provider'], value['limits'], value['interpreter'])
    c.need(type(value['authoring_exposure']) is str and 0 < len(value['authoring_exposure'].encode()) <= 8192,
           'bounded_exposure_declaration')
    c.descriptor(value['selection'], c.META_CAP)
    c.descriptor(value['support'], c.ANSWER_CAP)
    c.need(type(value['contexts']) is list and len(value['contexts']) == 40, 'complete_frozen_roster')
    for row, (fold, view) in zip(value['contexts'], c.ROSTER):
        c.need(type(row) is dict and set(row) == {'fold', 'view', 'presentation', 'observation'} and
               type(row['fold']) is int and row['fold'] == fold and row['view'] == view, 'ordered_frozen_roster')
        c.descriptor(row['presentation'], 16384)
        c.descriptor(row['observation'], c.OBS_CAP)
    return value


def prepare(spec, output, source_sha, *, modules=None):
    c.need(type(spec) is dict and set(spec) == {'schema', 'input_root', 'support_path', 'provider',
           'interpreter', 'limits', 'authoring_exposure'} and spec['schema'] == 'neural031_provider_spec_v1',
           'exact_preparation_spec')
    c.policy(spec['provider'], spec['limits'], spec['interpreter'])
    c.need(type(spec['authoring_exposure']) is str and 0 < len(spec['authoring_exposure'].encode()) <= 8192,
           'bounded_exposure_declaration')
    modules = c.load(source_sha) if modules is None else modules
    engine = modules['engine']
    inputs, support = c.ordinary(spec['input_root']), c.ordinary(spec['support_path'])
    budget = c.Budget(spec['limits'])
    budget.input(2 * 1024**2)  # Finite source/metadata bootstrap reservation.
    output = c.fresh(output, (inputs, support.parent, c.HERE.parents[4]))
    # Source/model/resource selection is durable before any query-export read.
    selected = c.write(output / 'SELECTION.json', c.encode({'source_sha256': source_sha, **spec}), budget)
    contexts = []
    try:
        c.read(spec['interpreter']['path'], 64 * 1024**2,
               {k: spec['interpreter'][k] for k in ('bytes', 'sha256')}, budget)
        support_body = c.read(support, c.ANSWER_CAP, engine.source_inputs()['support'], budget)
        engine.endpoint.validate_support(engine.io.decode(support_body))
        c.write(output / 'support.json', support_body, budget)
        presents = output / 'presentations'
        presents.mkdir()
        for fold, view in c.ROSTER:
            directory = presents / f'fold{fold:02d}' / view
            directory.parent.mkdir(exist_ok=True)
            budget.input(262144 + 16384)
            budget.output(c.OBS_CAP + 16384)
            result = engine.present(inputs / f'fold{fold:02d}' / view, fold, view, directory)
            receipt, obs = engine.load_presentation(directory, result['presentation'], fold, view)
            contexts.append({'fold': fold, 'view': view, 'presentation': result['presentation'],
                             'observation': receipt['observation']})
        value = {'schema': 'neural031_provider_contract_v1', 'source_sha256': source_sha, 'condition': c.CONDITION,
                 **{k: spec[k] for k in ('provider', 'interpreter', 'limits', 'authoring_exposure')},
                 'selection': selected, 'support': c.pin(support_body), 'contexts': contexts}
        contract(value, source_sha)
        result = c.write(output / 'CONTRACT.json', c.encode(value), budget)
        return {'contract': result, 'contexts': 40, 'source_sha256': source_sha,
                'named_read_bytes_reserved': budget.read, 'artifact_bytes_reserved': budget.written}
    except BaseException as error:
        c.write(output / 'FAILED.json', c.encode({'schema': 'neural031_provider_preparation_failure_v1',
                'error_type': type(error).__name__, 'presented': len(contexts), 'model_requests': 0}))
        raise


def frozen(root, expected, source_sha, modules, budget):
    root = c.ordinary(root)
    value = contract(c.decode(c.read(root / 'CONTRACT.json', c.META_CAP, expected, budget)), source_sha)
    selection = c.decode(c.read(root / 'SELECTION.json', c.META_CAP, value['selection'], budget))
    c.need(selection.get('source_sha256') == source_sha and
           all(selection.get(k) == value[k] for k in ('provider', 'interpreter', 'limits', 'authoring_exposure')),
           'selection_precedes_presentation')
    c.need(value['support'] == modules['engine'].source_inputs()['support'], 'original_support_pin')
    return value


def context(root, row, engine, budget):
    directory = c.ordinary(root) / 'presentations' / f"fold{row['fold']:02d}" / row['view']
    budget.input(c.OBS_CAP + 16384)
    receipt, obs = engine.load_presentation(directory, row['presentation'], row['fold'], row['view'])
    c.need(receipt['observation'] == row['observation'], 'frozen_observation_identity')
    raw = c.read(directory / 'OBSERVATION.json', c.OBS_CAP, row['observation'], budget)
    return raw.decode(), obs, directory


def config_for(prompt, value, deadline):
    return {'schema': 'neural031_provider_client_v1', **value['provider'], 'deadline': deadline,
            'trial_id': c.decode(prompt)['request_id'], 'context_sha256': c.pin(prompt.encode())['sha256'],
            'source_sha256': value['source_sha256']}


def episode(prompt, value, output, modules, budget, credential):
    """One fresh trusted client, one selector, one owned stop/reap, no retry."""
    started = time.monotonic()
    limits = value['limits']
    work_end = min(started + limits['episode_seconds'], budget.deadline - limits['cleanup_seconds'] - 5)
    cleanup_end = min(work_end + limits['cleanup_seconds'], budget.deadline - 5)
    c.need(work_end > started + 5, 'complete_episode_time')
    bridge, donor, owned = modules['bridge'], modules['http'], modules['owned']
    config = config_for(prompt, value, work_end)
    config_body = c.encode(config)
    request = bridge.request_body(prompt, **value['provider'])
    c.need(len(request) <= c.REQUEST_CAP, 'complete_request_capacity')
    frame = PREFIX.pack(len(prompt.encode())) + prompt.encode()
    # Reserve child writes/reads and failure finalization before any effects.
    budget.output(len(request) + c.RAW_CAP + 1 + 32768 + len(frame) + c.ANSWER_CAP + 4 + 32768)
    budget.input(2 * 1024**2 + len(frame) + c.RAW_CAP + c.ANSWER_CAP)
    output = c.fresh(output)
    custody = output / 'custody'
    custody.mkdir(mode=0o700)
    c.write(output / 'CONFIG.json', config_body)
    proc = observer = None
    cleanup = None
    reason = None
    normal = stdout_eof = stderr_eof = False
    outgoing, stderr = bytearray(), bytearray()
    sent = 0
    fds = set()
    selector = selectors.DefaultSelector()
    try:
        owned.preflight()
        pairs = [os.pipe() for _ in range(2)]
        for pair in pairs:
            fds.update(pair)
        config_read, config_write = pairs[0]
        secret_read, secret_write = pairs[1]
        custody_fd = os.open(custody, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        fds.add(custody_fd)
        cmd = [value['interpreter']['path'], '-I', '-S', '-B', str(c.HERE / 'client.py'),
               '--source-sha256', value['source_sha256'], '--config-fd', str(config_read),
               '--credential-fd', str(secret_read), '--custody-fd', str(custody_fd)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                cwd=output, env={'LANG': 'C', 'LC_ALL': 'C'}, close_fds=True,
                                pass_fds=(config_read, secret_read, custody_fd), start_new_session=True)
        observer = owned.ExitObserver(proc)
        for fd in (config_read, secret_read, custody_fd):
            os.close(fd)
            fds.remove(fd)
        stdin_fd = proc.stdin.fileno()
        writes = {config_write: memoryview(config_body), secret_write: memoryview(credential),
                  stdin_fd: memoryview(frame)}
        offsets = {fd: 0 for fd in writes}
        for fd in writes:
            os.set_blocking(fd, False)
            selector.register(fd, selectors.EVENT_WRITE, 'write')
        for stream, name in ((proc.stdout, 'stdout'), (proc.stderr, 'stderr')):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream.fileno(), selectors.EVENT_READ, name)
        while selector.get_map():
            c.need(time.monotonic() < work_end, 'provider_episode_deadline')
            for key, _ in selector.select(max(0, work_end - time.monotonic())):
                fd = key.fd
                if key.data == 'write':
                    try:
                        count = os.write(fd, writes[fd][offsets[fd]:])
                    except BlockingIOError:
                        continue
                    c.need(count > 0, 'pipe_write')
                    offsets[fd] += count
                    if fd == stdin_fd:
                        sent = offsets[fd]
                    if offsets[fd] == len(writes[fd]):
                        selector.unregister(fd)
                        if fd == stdin_fd:
                            proc.stdin.close()
                        else:
                            os.close(fd)
                            fds.remove(fd)
                else:
                    target, cap = (outgoing, c.ANSWER_CAP + 4) if key.data == 'stdout' else (stderr, 16384)
                    try:
                        part = os.read(fd, min(65536, cap + 1 - len(target)))
                    except BlockingIOError:
                        continue
                    if not part:
                        selector.unregister(fd)
                        if key.data == 'stdout':
                            stdout_eof = True
                        else:
                            stderr_eof = True
                    else:
                        target.extend(part)
                        c.need(len(target) <= cap, key.data + '_overflow')
        normal = observer.wait(work_end)
        c.need(normal, 'provider_child_no_normal_exit')
    except BaseException as error:
        reason = type(error).__name__
    finally:
        selector.close()
        if proc is not None:
            try:
                cleanup = owned.stop_and_reap(proc, observer, cleanup_end)
            except BaseException:
                reason = 'owned_cleanup_exception'
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                try:
                    stream.close()
                except OSError:
                    reason = 'pipe_close_failure'
        for fd in fds:
            try:
                os.close(fd)
            except OSError:
                reason = 'descriptor_close_failure'
        if not (proc and normal and proc.returncode == 0 and stdout_eof and stderr_eof and
                cleanup and cleanup.get('cleanup_complete') is True and cleanup.get('reaped') is True and
                cleanup.get('group_absence_observed') is True and time.monotonic() <= cleanup_end):
            reason = reason or 'owned_closure_unverified'
        raw_custody = {}
        try:
            c.need({x.name for x in custody.iterdir()} == donor.FILES, 'complete_raw_custody')
            for name, cap in {'REQUEST.bin': c.REQUEST_CAP, 'RESPONSE.bin': c.RAW_CAP + 1,
                              'HTTP.json': 16384, 'BRIDGE.json': 16384}.items():
                raw_custody[name] = c.pin(c.read(custody / name, cap, empty=True))
        except (OSError, ValueError):
            reason = reason or 'raw_custody_unverified'
        end = {'schema': 'neural031_owned_provider_episode_v1', 'status': 'closed' if reason is None else 'failed',
               'failure': reason, 'pid': proc.pid if proc else None, 'returncode': proc.returncode if proc else None,
               'normal_exit_observed': normal, 'stdout_eof': stdout_eof, 'stderr_eof': stderr_eof,
               'cleanup': cleanup, 'input': c.pin(frame[:sent]), 'output': c.pin(bytes(outgoing)),
               'stderr': c.pin(bytes(stderr)), 'config': c.pin(config_body), 'raw_custody': raw_custody,
               'started': started, 'finished': time.monotonic(), 'deadline': work_end,
               'automatic_retry': False, 'remote_context_qualified': False, 'remote_tool_policy_qualified': False}
        c.write(output / 'INPUT.bin', frame[:sent])
        c.write(output / 'OUTPUT.bin', bytes(outgoing))
        c.write(output / 'STDERR.bin', bytes(stderr))
        c.write(output / 'END.json', c.encode(end))
    return end


def admit_episode_clock(end, config, limits):
    """Validate recorded times against the same absolute bound used by episode."""
    c.need(all(type(end.get(k)) in (int, float) and math.isfinite(end[k]) for k in ('started', 'finished', 'deadline')) and
           end['started'] <= end['finished'] <= end['deadline'] + limits['cleanup_seconds'] and
           end['deadline'] == config['deadline'] and
           end['started'] < end['deadline'] <= end['started'] + limits['episode_seconds'],
           'owned_episode_clock')


def admit_episode(prompt, value, root, expected_end, modules, budget):
    root = c.ordinary(root)
    c.need({p.name for p in root.iterdir()} == EPISODE_FILES and
           {p.name for p in (root / 'custody').iterdir()} == modules['http'].FILES, 'exact_episode_files')
    caps = {'CONFIG.json': 16384, 'INPUT.bin': c.OBS_CAP + 4, 'OUTPUT.bin': c.ANSWER_CAP + 4,
            'STDERR.bin': 16384, 'END.json': 16384}
    capture = {name: c.read(root / name, cap, expected_end if name == 'END.json' else None,
                            budget, empty=name == 'STDERR.bin') for name, cap in caps.items()}
    capture.update({name: c.read(root / 'custody' / name, cap, budget=budget) for name, cap in
                    {'REQUEST.bin': c.REQUEST_CAP, 'RESPONSE.bin': c.RAW_CAP, 'HTTP.json': 16384, 'BRIDGE.json': 16384}.items()})
    end, config = c.decode(capture['END.json']), c.decode(capture['CONFIG.json'])
    c.need(end.get('raw_custody') == {name: c.pin(capture[name]) for name in modules['http'].FILES},
           'externally_bound_original_raw_custody')
    c.need(type(config.get('deadline')) in (int, float) and math.isfinite(config['deadline']) and
           config == config_for(prompt, value, config['deadline']), 'frozen_client_configuration')
    request = modules['bridge'].request_body(prompt, **value['provider'])
    c.need(capture['REQUEST.bin'] == request and capture['INPUT.bin'] == PREFIX.pack(len(prompt.encode())) + prompt.encode(),
           'complete_original_request')
    answer, details = modules['bridge'].completed(capture['RESPONSE.bin'], prompt, **value['provider'])
    c.need(capture['OUTPUT.bin'] == PREFIX.pack(len(answer)) + answer, 'original_first_provider_answer')
    cleanup = end.get('cleanup') or {}
    c.need(end.get('schema') == 'neural031_owned_provider_episode_v1' and end.get('status') == 'closed' and
           end.get('failure') is None and type(end.get('pid')) is int and end['pid'] > 1 and
           type(end.get('returncode')) is int and end['returncode'] == 0 and end.get('normal_exit_observed') is True and
           end.get('stdout_eof') is True and end.get('stderr_eof') is True and
           cleanup.get('pid') == end['pid'] and type(cleanup.get('returncode')) is int and cleanup['returncode'] == 0 and
           cleanup.get('cleanup_complete') is True and cleanup.get('reaped') is True and
           cleanup.get('group_absence_observed') is True and end.get('automatic_retry') is False and
           end.get('remote_context_qualified') is False and end.get('remote_tool_policy_qualified') is False,
           'owned_closure_required')
    for field, name in (('config', 'CONFIG.json'), ('input', 'INPUT.bin'), ('output', 'OUTPUT.bin'), ('stderr', 'STDERR.bin')):
        c.need(end.get(field) == c.pin(capture[name]), 'captured_episode_identity')
    admit_episode_clock(end, config, value['limits'])
    http = c.decode(capture['HTTP.json'])
    c.need(type(http) is dict and set(http) == {'schema', 'config_pin', 'endpoint', 'request', 'response',
           'status_code', 'request_complete', 'response_complete', 'body_overflow', 'requests_attempted',
           'redirects_followed', 'retries', 'connection_closed', 'credential_retained', 'failure',
           'started_monotonic', 'finished_monotonic', 'deadline'} and
           all(type(http[k]) is int for k in ('status_code', 'requests_attempted', 'redirects_followed', 'retries')),
           'exact_donor_http_receipt')
    c.need(http.get('schema') == 'neural077_https_binding_v1' and http.get('config_pin') == c.pin(capture['CONFIG.json']) and
           http.get('endpoint') == modules['http'].ENDPOINT and http.get('request') == c.pin(request) and
           http.get('response') == c.pin(capture['RESPONSE.bin']) and http.get('status_code') == 200 and
           http.get('request_complete') is True and http.get('response_complete') is True and
           http.get('body_overflow') is False and type(http.get('requests_attempted')) is int and
           http['requests_attempted'] == 1 and http.get('redirects_followed') == 0 and http.get('retries') == 0 and
           http.get('connection_closed') is True and http.get('credential_retained') is False and http.get('failure') is None,
           'one_complete_original_http_exchange')
    c.need(all(type(http.get(k)) in (int, float) and math.isfinite(http[k])
               for k in ('started_monotonic', 'finished_monotonic', 'deadline')) and
           end['started'] <= http['started_monotonic'] <= http['finished_monotonic'] <= config['deadline'] and
           http['deadline'] == config['deadline'] and http['finished_monotonic'] <= end['finished'], 'http_owned_clock')
    receipt = {'schema': 'neural031_provider_exchange_v1', 'request': c.pin(request),
               'response': c.pin(capture['RESPONSE.bin']), 'answer': c.pin(answer), 'sender_calls_attempted': 1,
               'retry_count': 0, 'status': 'complete_unscored_answer', **details}
    c.need(c.decode(capture['BRIDGE.json']) == {'schema': 'neural031_provider_binding_v1',
           'config_pin': c.pin(capture['CONFIG.json']), 'receipt': receipt}, 'first_exchange_receipt')
    return answer, details


def admit(freeze_root, contract_pin, arm_root, arm_pin, source_sha, *, modules=None):
    modules = c.load(source_sha) if modules is None else modules
    raw = c.read(c.ordinary(freeze_root) / 'CONTRACT.json', c.META_CAP, contract_pin)
    value = contract(c.decode(raw), source_sha)
    budget = c.Budget(value['limits'])
    budget.input(2 * 1024**2)  # Finite source/metadata bootstrap reservation.
    frozen(freeze_root, contract_pin, source_sha, modules, budget)
    arm_root = c.ordinary(arm_root)
    arm = c.decode(c.read(arm_root / 'ARM.json', c.META_CAP, arm_pin, budget))
    c.need(type(arm) is dict and set(arm) == {'schema', 'contract', 'status', 'episodes', 'inventory',
           'collection', 'submission', 'support', 'captured_request_policy_verified', 'remote_context_qualified',
           'remote_tool_policy_qualified', 'scientific_qualification'} and
           arm['schema'] == 'neural031_direct_provider_arm_v1' and arm['contract'] == contract_pin and
           arm['status'] == 'complete_unscored_arm' and type(arm['episodes']) is list and len(arm['episodes']) == 40 and
           arm['captured_request_policy_verified'] is True and all(arm[k] is False for k in
           ('remote_context_qualified', 'remote_tool_policy_qualified', 'scientific_qualification')), 'complete_arm_contract')
    c.need({p.name for p in (arm_root / 'episodes').iterdir()} == {f'{i:02d}' for i in range(40)}, 'exact_episode_roster')
    c.need({p.name for p in (arm_root / 'captures').iterdir()} == {f'fold{i:02d}' for i in range(20)},
           'exact_capture_folds')
    for fold in range(20):
        c.need({p.name for p in (arm_root / 'captures' / f'fold{fold:02d}').iterdir()} == {'baseline', 'neural'},
               'exact_capture_views')
    inventory_body = c.read(arm_root / 'INVENTORY.json', 16384, arm['inventory'], budget)
    inventory = c.decode(inventory_body)
    expected_captures, seen = [], set()
    outputs = []
    engine = modules['engine']
    for index, row in enumerate(value['contexts']):
        entry = arm['episodes'][index]
        c.need(type(entry) is dict and set(entry) == {'fold', 'view', 'end', 'capture'} and
               entry['fold'] == row['fold'] and type(entry['fold']) is int and entry['view'] == row['view'], 'ordered_episode_inventory')
        prompt, obs, directory = context(freeze_root, row, engine, budget)
        answer, details = admit_episode(prompt, value, arm_root / 'episodes' / f'{index:02d}', entry['end'], modules, budget)
        c.need(details['provider_response_id'] not in seen, 'duplicate_provider_response_id')
        seen.add(details['provider_response_id'])
        capture_dir = arm_root / 'captures' / f"fold{row['fold']:02d}" / row['view']
        c.need({p.name for p in capture_dir.iterdir()} == {'CAPTURE.json', 'FIRST_RESPONSE.bin', 'predictions.json'}, 'complete_local_capture')
        capture = c.decode(c.read(capture_dir / 'CAPTURE.json', 16384, entry['capture'], budget))
        first = c.read(capture_dir / 'FIRST_RESPONSE.bin', c.ANSWER_CAP, capture['response'], budget)
        prediction = engine.prediction(answer, obs, row['fold'], row['view'])
        c.need(first == answer and capture == {'schema': 'neural031_numeric_capture_v1', 'condition': c.CONDITION,
               'source_sha256': engine.source_sha256, 'fold': row['fold'], 'view': row['view'],
               'presentation': row['presentation'], 'observation': row['observation'],
               'response': c.pin(answer), 'prediction': c.pin(engine.io.encoded(prediction)),
               'status': 'valid_first_supplied_response', 'actual_provider_first_response_verified': False,
               'fresh_model_context_verified': False, 'no_tools_enforced': False}, 'provider_to_original_local_capture')
        c.need(c.read(capture_dir / 'predictions.json', c.ANSWER_CAP, capture['prediction'], budget) == engine.io.encoded(prediction),
               'unchanged_original_prediction')
        outputs.append(prediction)
        expected_captures.append({'fold': row['fold'], 'view': row['view'], 'capture': entry['capture']})
    c.need(inventory == {'schema': 'neural031_numeric_capture_inventory_v1', 'condition': c.CONDITION,
           'source_sha256': engine.source_sha256, 'captures': expected_captures}, 'externally_bound_complete_capture_inventory')
    collection = c.decode(c.read(arm_root / 'collection/COLLECTION.json', c.ANSWER_CAP, arm['collection'], budget))
    submission = c.read(arm_root / 'collection/submission.json', 6291456, arm['submission'], budget)
    support = c.read(arm_root / 'collection/support.json', c.ANSWER_CAP, arm['support'], budget)
    c.need(arm['support'] == value['support'] == engine.source_inputs()['support'] and
           submission == engine.io.encoded({'schema': 'neural031_ordinary_submission_bundle_v1',
           'candidate_id': 'NEURAL-031', 'outputs': outputs}), 'complete_original_submission')
    engine.endpoint.validate_all(engine.io.decode(submission), engine.io.decode(support))
    c.need(collection == {'schema': 'neural031_numeric_collection_v1', 'condition': c.CONDITION,
           'source_sha256': engine.source_sha256, 'contexts': 40, 'predictions': 1548,
           'capture_inventory': arm['inventory'], 'information_views': ['baseline', 'neural'],
           'captures': expected_captures, 'files': {'submission.json': arm['submission'], 'support.json': arm['support']},
           'private_targets_opened': 0, 'scores_computed': 0, 'actual_provider_first_responses_verified': False,
           'fresh_model_contexts_verified': False, 'no_tools_enforced': False, 'scientific_qualification': False},
           'original_collection_custody')
    return {'status': 'admitted_complete_unscored_arm', 'arm': arm_pin, 'contract': contract_pin,
            'contexts': 40, 'predictions': 1548, 'captured_request_policy_verified': True,
            'remote_context_qualified': False, 'remote_tool_policy_qualified': False,
            'scientific_qualification': False, 'private_target_reads': 0, 'scores_computed': 0}


def run(freeze_root, contract_pin, output, source_sha, credential_fd, *, modules=None):
    modules = c.load(source_sha) if modules is None else modules
    value = contract(c.decode(c.read(c.ordinary(freeze_root) / 'CONTRACT.json', c.META_CAP, contract_pin)), source_sha)
    budget = c.Budget(value['limits'])
    budget.input(2 * 1024**2)  # Finite source/metadata bootstrap reservation.
    frozen(freeze_root, contract_pin, source_sha, modules, budget)
    c.read(value['interpreter']['path'], 64 * 1024**2, {k: value['interpreter'][k] for k in ('bytes', 'sha256')}, budget)
    c.need(os.access(value['interpreter']['path'], os.X_OK), 'executable_interpreter')
    c.need(type(credential_fd) is int and credential_fd >= 3 and stat.S_ISFIFO(os.fstat(credential_fd).st_mode),
           'inherited_private_credential_pipe')
    output = c.fresh(output, (c.ordinary(freeze_root), c.HERE.parents[4]))
    c.write(output / 'INITIAL.json', c.encode({'contract': contract_pin, 'contexts': list(c.ROSTER), 'attempt_policy': 'one_no_retry'}), budget)
    for name in ('episodes', 'captures'):
        (output / name).mkdir()
    credential = bytearray()
    entries, seen = [], set()
    attempted = 0
    try:
        try:
            credential.extend(modules['http'].pipe_body(credential_fd, 4096, min(budget.deadline - 5, time.monotonic() + 5)))
        finally:
            os.close(credential_fd)
        c.need(1 <= len(credential) <= 4096 and all(33 <= x <= 126 for x in credential), 'bounded_private_credential')
        for index, row in enumerate(value['contexts']):
            c.need(time.monotonic() + value['limits']['episode_seconds'] + value['limits']['cleanup_seconds'] + 5 < budget.deadline,
                   'whole_episode_before_dispatch')
            prompt, obs, presentation = context(freeze_root, row, modules['engine'], budget)
            # Durable dispatch reservation is outside the episode result; even a
            # prelaunch failure cannot be hidden as an unassigned replacement.
            c.write(output / f'DISPATCH-{index:02d}.json', c.encode({'ordinal': index, 'context': row, 'contract': contract_pin}), budget)
            attempted += 1
            path = output / 'episodes' / f'{index:02d}'
            end = episode(prompt, value, path, modules, budget, credential)
            end_pin = c.pin(c.encode(end))
            answer, details = admit_episode(prompt, value, path, end_pin, modules, budget)
            c.need(details['provider_response_id'] not in seen, 'duplicate_provider_response_id')
            seen.add(details['provider_response_id'])
            # A temporary operator bridge into unchanged capture is kept outside
            # the episode custody set and retained as original supplied bytes.
            answer_path = output / f'FIRST-{index:02d}.bin'
            c.write(answer_path, answer, budget)
            destination = output / 'captures' / f"fold{row['fold']:02d}" / row['view']
            destination.parent.mkdir(exist_ok=True)
            budget.output(2 * c.ANSWER_CAP + 32768)
            captured = modules['engine'].capture(presentation, row['presentation'], answer_path,
                        c.pin(answer), row['fold'], row['view'], destination)
            entries.append({'fold': row['fold'], 'view': row['view'], 'end': end_pin, 'capture': captured['capture']})
        captures = [{k: row[k] for k in ('fold', 'view', 'capture')} for row in entries]
        inventory = {'schema': 'neural031_numeric_capture_inventory_v1', 'condition': c.CONDITION,
                     'source_sha256': modules['engine'].source_sha256, 'captures': captures}
        inventory_pin = c.write(output / 'INVENTORY.json', c.encode(inventory), budget)
        budget.input(40 * (2 * c.OBS_CAP + 3 * c.ANSWER_CAP + 32768) + c.ANSWER_CAP)
        budget.output(6553600)
        collected = modules['engine'].collect(Path(freeze_root) / 'support.json', Path(freeze_root) / 'presentations',
                     output / 'captures', output / 'INVENTORY.json', inventory_pin, output / 'collection')
        collection = c.decode(c.read(output / 'collection/COLLECTION.json', c.ANSWER_CAP, collected['collection'], budget))
        arm = {'schema': 'neural031_direct_provider_arm_v1', 'contract': contract_pin, 'status': 'complete_unscored_arm',
               'episodes': entries, 'inventory': inventory_pin, 'collection': collected['collection'],
               'submission': collection['files']['submission.json'], 'support': collection['files']['support.json'],
               'captured_request_policy_verified': True, 'remote_context_qualified': False,
               'remote_tool_policy_qualified': False, 'scientific_qualification': False}
        arm_pin = c.write(output / 'ARM.json', c.encode(arm), budget)
        return {'arm': arm_pin, 'contract': contract_pin, 'contexts': 40, 'predictions': 1548,
                'named_read_bytes_reserved': budget.read, 'artifact_bytes_reserved': budget.written,
                'independent_admission_required': True}
    except BaseException as error:
        c.write(output / 'FAILED.json', c.encode({'schema': 'neural031_provider_arm_failure_v1',
                'status': 'failed_no_partial_admission', 'contract': contract_pin, 'error_type': type(error).__name__,
                'attempted': attempted, 'succeeded': len(entries), 'unattempted': 40 - attempted, 'automatic_retry': False}))
        raise
    finally:
        credential[:] = b'\0' * len(credential)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-sha256', required=True)
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('--spec', required=True)
    prep.add_argument('--spec-bytes', type=int, required=True)
    prep.add_argument('--spec-sha256', required=True)
    prep.add_argument('--output', required=True)
    for name in ('run', 'admit'):
        p = commands.add_parser(name)
        p.add_argument('--freeze', required=True)
        p.add_argument('--contract-bytes', type=int, required=True)
        p.add_argument('--contract-sha256', required=True)
        if name == 'run':
            p.add_argument('--output', required=True)
            p.add_argument('--credential-fd', type=int, required=True)
        else:
            p.add_argument('--arm', required=True)
            p.add_argument('--arm-bytes', type=int, required=True)
            p.add_argument('--arm-sha256', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'prepare':
            spec = c.decode(c.read(args.spec, c.META_CAP, {'bytes': args.spec_bytes, 'sha256': args.spec_sha256}))
            result = prepare(spec, args.output, args.source_sha256)
        else:
            selected = {'bytes': args.contract_bytes, 'sha256': args.contract_sha256}
            if args.command == 'run':
                result = run(args.freeze, selected, args.output, args.source_sha256, args.credential_fd)
            else:
                result = admit(args.freeze, selected, args.arm, {'bytes': args.arm_bytes, 'sha256': args.arm_sha256}, args.source_sha256)
        print(c.encode(result).decode(), end='')
        return 0
    except (ValueError, OSError, KeyError, TypeError, OverflowError):
        print('{"status":"failed_unadmitted","detail":"retain original attempt; no retry"}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
