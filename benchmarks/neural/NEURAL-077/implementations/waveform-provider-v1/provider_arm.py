"""Trusted provider-specific N077 arm and protected pairing; no local-arm relabeling.

Only an explicit run with an operator-supplied credential pipe can contact a
provider. Tests inject generated clients. The original macOS programme route,
complete collector, private targets, six references and metrics stay unchanged.
"""
from pathlib import Path
import argparse
import io
import math
import os
import platform
import stat
import subprocess
import sys
import time

import support as s

HERE = Path(__file__).resolve().parent
ARM_SCHEMA = 'neural077_trusted_provider_arm_v1'
CONFIG_SCHEMA = 'neural077_openai_client_v1'
MAX_LEDGER = 400 * 16384


def limits(query_seconds, campaign_seconds, max_prompt_bytes):
    for value, minimum, maximum in ((query_seconds, 5, 3600), (campaign_seconds, query_seconds, 86400)):
        s.need(type(value) in (int, float) and math.isfinite(value) and minimum <= value <= maximum,
               'Finite query/campaign budget required')
    s.need(type(max_prompt_bytes) is int and 1 <= max_prompt_bytes <= 2097152, 'Prompt byte budget')
    return {'query_seconds': query_seconds, 'campaign_seconds': campaign_seconds,
            'max_prompt_bytes': max_prompt_bytes, 'maximum_requests': 400}


def contexts(deps, delivery_root, budgets):
    rows = deps['transport'].contexts(delivery_root, s.CONDITION)
    s.need(len(rows) == 400 and [row['ordinal'] for row in rows] == list(range(400))
           and len({row['trial_id'] for row in rows}) == 400, 'Exact complete ordered 400 queries')
    control = deps['transport'].Limits(max_prompt_bytes=budgets['max_prompt_bytes'])
    for row in rows:
        deps['transport'].row_prompt(row, s.CONDITION, control)
        s.need(deps['bridge'].query_identity(row['prompt']) == row['trial_id'], 'Query/request identity mismatch')
    return rows


def credential(fd, transport):
    """Consume only the explicitly supplied anonymous operator pipe; never log it."""
    s.need(type(fd) is int and fd >= 3, 'Explicit operator credential descriptor required')
    result = bytearray()
    deadline = time.monotonic() + 5
    try:
        info = os.fstat(fd)
        s.need(stat.S_ISFIFO(info.st_mode) and info.st_uid == os.getuid(), 'Operator-owned credential pipe required')
        while True:
            transport.wait_fd(fd, transport.selectors.EVENT_READ, deadline)
            part = os.read(fd, 4097 - len(result))
            if not part:
                break
            result.extend(part)
            s.need(len(result) <= 4096, 'Credential channel exceeds bound')
        s.need(1 <= len(result) <= 4096 and all(33 <= item <= 126 for item in result), 'Bounded ASCII credential required')
        return result
    except BaseException:
        result[:] = b'\0' * len(result)
        raise ValueError('Operator credential channel refused') from None
    finally:
        os.close(fd)


def config_for(row, deps, model, max_output_tokens, deadline):
    deps['bridge'].request_body(row['prompt'], model, max_output_tokens)
    return {'schema': CONFIG_SCHEMA, 'model': model, 'max_output_tokens': max_output_tokens,
            'deadline': deadline, 'trial_id': row['trial_id'], 'context_sha256': row['context_sha256'],
            'bridge_path': str(deps['root'] / 'waveform-transport-v1/provider_bridge.py'),
            'bridge_pin': deps['bindings']['waveform-transport-v1/provider_bridge.py']}


def episode(row, deps, output, model, max_output_tokens, token, python, query_seconds, campaign_deadline,
            client_path=None):
    """One trusted broker process, original framing, one bounded first answer."""
    t = deps['transport']
    output = s.path(output)
    output.mkdir(mode=0o700)
    custody = output / 'custody'
    custody.mkdir(mode=0o700)
    started = time.monotonic()
    close_end = min(started + query_seconds, campaign_deadline)
    deadline = close_end - 2
    cfg = config_for(row, deps, model, max_output_tokens, deadline)
    cfg_body = s.encode(cfg)
    s.need(len(cfg_body) <= 16384, 'Bounded child configuration')
    s.write(output / 'CONFIG.json', cfg_body)
    frame = t.PREFIX.pack(len(row['prompt'].encode())) + row['prompt'].encode()
    sent = received = b''
    child = None
    owned = set()
    error = None
    forced = False
    reaped = True
    try:
        s.need(time.monotonic() < deadline, 'Campaign budget expired before query')
        ar, aw = os.pipe(); owned.update((ar, aw))
        cr, cw = os.pipe(); owned.update((cr, cw))
        directory = os.open(custody, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        owned.add(directory)
        argv = [str(python), '-I', '-S', '-B', str(client_path or HERE / 'client.py'),
                '--credential-fd', str(ar), '--config-fd', str(cr), '--custody-fd', str(directory)]
        child = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                 cwd=custody, env={'LANG': 'C', 'LC_ALL': 'C'}, close_fds=True,
                                 pass_fds=(ar, cr, directory), start_new_session=True)
        reaped = False
        for fd in (ar, cr, directory):
            os.close(fd); owned.remove(fd)
        for fd, body in ((cw, cfg_body), (aw, token)):
            os.set_blocking(fd, False)
            t.write_frame(fd, body, deadline)
            os.close(fd); owned.remove(fd)
        os.set_blocking(child.stdin.fileno(), False)
        os.set_blocking(child.stdout.fileno(), False)
        try:
            t.write_frame(child.stdin.fileno(), frame, deadline)
            sent = frame
        except t.WireFailure as failure:
            sent = failure.captured
            raise
        child.stdin.close()
        try:
            received = t.read_frame(child.stdout.fileno(), deadline)
        except t.WireFailure as failure:
            received = failure.captured
            raise
        child.stdout.close()
        child.wait(timeout=max(0.001, deadline - time.monotonic()))
        reaped = True
        s.need(child.returncode == 0, 'Trusted provider child failed')
        deps['parser'].parse(received[t.PREFIX.size:], row['trial_id'])
    except BaseException as failure:
        error = type(failure).__name__  # Never retain exception text or headers.
    finally:
        for fd in owned:
            os.close(fd)
        if child is not None:
            for stream in (child.stdin, child.stdout):
                if stream is not None and not stream.closed:
                    stream.close()
            if child.poll() is None:
                forced = True
                child.kill()
            try:
                child.wait(timeout=max(0.001, close_end - time.monotonic()))
                reaped = True
            except subprocess.TimeoutExpired:
                reaped = False
                error = 'ChildClosureUnverified'
        s.write(output / 'INPUT.bin', sent)
        s.write(output / 'OUTPUT.bin', received)
        finished = time.monotonic()
        end = {'schema': 'neural077_trusted_provider_episode_end_v1',
               'status': 'closed_first_answer' if error is None and reaped and not forced else 'failed_no_admission',
               'error_type': error, 'config': s.pin(cfg_body), 'input': s.pin(sent), 'output': s.pin(received),
               'child_pid': child.pid if child is not None else None,
               'child_exit_code': child.returncode if child is not None else None,
               'direct_child_reaped': reaped, 'forced_stop': forced, 'descendant_absence_verified': False,
               'started_monotonic': started, 'finished_monotonic': finished,
               'elapsed_seconds': finished - started, 'credential_persisted': False,
               'provider_context_qualified': False, 'provider_capacity_qualified': False,
               'scoring_performed': False}
        s.write(output / 'END.json', s.encode(end))
    s.need(end['status'] == 'closed_first_answer', 'Provider query failed; retained output is unscoreable')
    return end


def audit_episode(root, row, deps, manifest):
    """Rejoin exact original context, first answer and provider custody before score."""
    root = s.path(root)
    s.need({item.name for item in root.iterdir()} == {'CONFIG.json', 'INPUT.bin', 'OUTPUT.bin', 'END.json', 'custody'},
           'Exact provider episode membership')
    cfg_body = s.read(root / 'CONFIG.json', 16384)
    cfg = s.decode(cfg_body)
    s.need(type(cfg.get('deadline')) in (int, float) and math.isfinite(cfg['deadline']), 'Recorded finite deadline')
    expected_cfg = config_for(row, deps, manifest['model'], manifest['max_output_tokens'], cfg['deadline'])
    s.need(cfg == expected_cfg, 'Provider configuration/context mismatch')
    t = deps['transport']; bridge = deps['bridge']
    incoming = s.read(root / 'INPUT.bin', manifest['limits']['max_prompt_bytes'] + 4)
    expected_input = row['prompt'].encode()
    s.need(incoming == t.PREFIX.pack(len(expected_input)) + expected_input, 'Complete original prompt required')
    outgoing = s.read(root / 'OUTPUT.bin', 4100)
    s.need(len(outgoing) > 4 and t.PREFIX.unpack(outgoing[:4])[0] == len(outgoing) - 4, 'One complete first answer')
    answer = outgoing[4:]
    deps['parser'].parse(answer, row['trial_id'])
    end = s.decode(s.read(root / 'END.json', 16384))
    s.need(end['schema'] == 'neural077_trusted_provider_episode_end_v1' and end['status'] == 'closed_first_answer'
           and end['error_type'] is None and type(end['child_pid']) is int and end['child_pid'] > 0
           and type(end['child_exit_code']) is int and end['child_exit_code'] == 0
           and end['direct_child_reaped'] is True and end['forced_stop'] is False
           and end['descendant_absence_verified'] is False and end['credential_persisted'] is False
           and end['scoring_performed'] is False and end['provider_context_qualified'] is False
           and end['provider_capacity_qualified'] is False, 'Provider process did not close successfully')
    s.need(end['config'] == s.pin(cfg_body) and end['input'] == s.pin(incoming) and end['output'] == s.pin(outgoing),
           'Recorded episode custody mismatch')
    s.need(type(end['elapsed_seconds']) in (int, float) and math.isfinite(end['elapsed_seconds'])
           and 0 <= end['elapsed_seconds'] <= manifest['limits']['query_seconds'], 'Query wall allocation exceeded')
    s.need(all(type(end[name]) in (int, float) and math.isfinite(end[name])
               for name in ('started_monotonic', 'finished_monotonic'))
           and manifest['started_monotonic'] <= end['started_monotonic'] <= end['finished_monotonic']
           <= cfg['deadline'] + 2 <= manifest['deadline']
           and end['elapsed_seconds'] == end['finished_monotonic'] - end['started_monotonic'],
           'One recorded campaign clock and query closure required')
    custody = root / 'custody'
    s.need({item.name for item in custody.iterdir()} == {'REQUEST.bin', 'RESPONSE.bin', 'HTTP.json', 'BRIDGE.json'},
           'Complete provider request/response custody required')
    request = s.read(custody / 'REQUEST.bin', 8 * 1024 * 1024)
    response = s.read(custody / 'RESPONSE.bin', bridge.PROVIDER_RESPONSE_CAP)
    s.need(request == bridge.request_body(row['prompt'], manifest['model'], manifest['max_output_tokens']),
           'Provider request differs from original complete no-tools context')
    decoded_answer, metadata = bridge.completed_text(response, row['trial_id'], manifest['model'],
                                                     manifest['max_output_tokens'])
    s.need(answer == decoded_answer, 'First emitted answer differs from provider response')
    expected_receipt = {'schema': 'neural077_responses_bridge_v1', 'condition': s.CONDITION,
                        'prompt': s.pin(expected_input), 'request': s.pin(request),
                        'requested_model': manifest['model'], 'max_output_tokens': manifest['max_output_tokens'],
                        'sender_calls_attempted': 1, 'status': 'complete_unscored_answer',
                        'response': s.pin(response), 'answer': s.pin(answer), 'retry_count': 0,
                        'provider_execution_qualified': False, 'provider_capacity_qualified': False,
                        'scientific_qualification': False, **metadata}
    bridge_receipt = s.decode(s.read(custody / 'BRIDGE.json', 16384))
    s.need(bridge_receipt == {'schema': 'neural077_provider_binding_bridge_v1', 'config_pin': s.pin(cfg_body),
                            'status': 'recorded', 'receipt': expected_receipt, 'failure': None},
           'Durable bridge receipt differs from delivered answer')
    http = s.decode(s.read(custody / 'HTTP.json', 16384))
    # The sender owns HTTP-specific enforcement; this admission joins its exact
    # fixed profile and complete bytes to the separately parsed provider body.
    s.need(set(http) == {'schema', 'config_pin', 'endpoint', 'request', 'response', 'status_code',
                        'request_complete', 'response_complete', 'body_overflow', 'requests_attempted',
                        'redirects_followed', 'retries', 'connection_closed', 'credential_retained', 'failure',
                        'started_monotonic', 'finished_monotonic', 'deadline'}, 'Exact bounded HTTP receipt schema')
    s.need(http['schema'] == 'neural077_https_binding_v1' and http['config_pin'] == s.pin(cfg_body)
           and http['endpoint'] == 'https://api.openai.com/v1/responses'
           and http['request'] == s.pin(request) and http['response'] == s.pin(response)
           and type(http['status_code']) is int and http['status_code'] == 200
           and http['request_complete'] is True and http['response_complete'] is True and http['body_overflow'] is False
           and type(http['requests_attempted']) is int and http['requests_attempted'] == 1
           and type(http['redirects_followed']) is int and http['redirects_followed'] == 0
           and type(http['retries']) is int and http['retries'] == 0 and http['connection_closed'] is True
           and http['credential_retained'] is False and http['failure'] is None,
           'Complete fixed-provider HTTP custody required')
    s.need(http['deadline'] == cfg['deadline']
           and all(type(http[name]) in (int, float) and math.isfinite(http[name])
                   for name in ('started_monotonic', 'finished_monotonic'))
           and http['started_monotonic'] <= http['finished_monotonic'] <= http['deadline'],
           'Recorded provider deadline/closure mismatch')
    s.need(end['started_monotonic'] <= http['started_monotonic'] <= http['finished_monotonic']
           <= end['finished_monotonic'], 'Provider HTTP timing outside enclosing episode')
    envelope = {key: row[key] for key in ('ordinal', 'trial_id', 'context_sha256')}
    envelope.update(status='ok', response=answer.decode(), error=None)
    return envelope, metadata['provider_response_id'], metadata['usage']


def run_arm(implementations_root, delivery_root, output, model, max_output_tokens, credential_fd, python,
            query_seconds, campaign_seconds, max_prompt_bytes):
    budgets = limits(query_seconds, campaign_seconds, max_prompt_bytes)
    deps = s.sources(implementations_root)
    before = s.identity()
    rows = contexts(deps, delivery_root, budgets)
    for row in rows:
        deps['bridge'].request_body(row['prompt'], model, max_output_tokens)
    executable = Path(python).resolve(strict=True)
    executable_pin = s.pin(s.read(executable, 64 * 1024 * 1024))
    token = credential(credential_fd, deps['transport'])
    output = s.path(output)
    completed = 0
    output_owned = False
    try:
        output.mkdir(mode=0o700)
        output_owned = True
        (output / 'episodes').mkdir(mode=0o700)
        start = time.monotonic()
        manifest = {'schema': 'neural077_trusted_provider_campaign_v1', 'route': s.ROUTE,
                    'condition': s.CONDITION, 'queries': 400, 'demonstrations': 4,
                    'model': model, 'max_output_tokens': max_output_tokens, 'limits': budgets,
                    'source': deps['bindings'], 'operator': before,
                    'client_interpreter': {'path': str(executable), 'pin': executable_pin},
                    'retry_policy': 'none', 'credentials_channel': 'operator_owned_inherited_pipe',
                    'remote_context_qualified': False, 'provider_capacity_qualified': False,
                    'local_participant_sandbox': None, 'participant_code_executed_locally': False,
                    'started_monotonic': start, 'deadline': start + campaign_seconds}
        s.write(output / 'MANIFEST.json', s.encode(manifest))
        ledger = bytearray(); response_ids = set(); ends = []
        totals = {name: 0 for name in ('input_tokens', 'output_tokens', 'total_tokens')}
        for row in rows:
            directory = output / 'episodes' / f"{row['ordinal']:03d}"
            episode(row, deps, directory, model, max_output_tokens, token, executable,
                    query_seconds, start + campaign_seconds)
            envelope, response_id, usage = audit_episode(directory, row, deps, manifest)
            s.need(response_id not in response_ids, 'Provider response identity reused across queries')
            response_ids.add(response_id)
            ledger.extend(s.encode(envelope))
            for name in totals:
                totals[name] += usage[name]
            ends.append(s.pin(s.read(directory / 'END.json', 16384)))
            completed += 1
        s.write(output / 'attempts.jsonl', bytes(ledger))
        s.need(time.monotonic() <= start + campaign_seconds, 'Campaign allocation expired')
        collection = deps['delivery'].collect(delivery_root, s.CONDITION, output / 'attempts.jsonl', output / 'collection')
        s.need(s.identity() == before and s.sources(implementations_root)['bindings'] == deps['bindings']
               and s.pin(s.read(executable, 64 * 1024 * 1024)) == executable_pin, 'Operator/runtime source drift')
        s.need(time.monotonic() <= start + campaign_seconds, 'Whole campaign including collection exceeded allocation')
        receipt = {'schema': ARM_SCHEMA, 'status': 'closed_unscored_provider_arm', 'route': s.ROUTE,
                   'condition': s.CONDITION, 'queries': 400, 'demonstrations': 4,
                   'source': deps['bindings'], 'operator': before,
                   'manifest': s.pin(s.read(output / 'MANIFEST.json', 32768)),
                   'episode_ends': ends, 'attempts': s.pin(bytes(ledger)),
                   'collection': s.pin(s.read(output / 'collection/COMPLETE.json', 16384)),
                   'submission': collection['submission'], 'usage': totals,
                   'all_direct_children_reaped': True, 'descendant_absence_verified': False,
                   'local_participant_sandbox': None, 'remote_context_qualified': False,
                   'provider_capacity_qualified': False, 'scientific_qualification': False,
                   'private_target_reads': 0, 'scoring_performed': False}
        s.write(output / 'ARM.json', s.encode(receipt))
        return receipt
    except BaseException as error:
        if output_owned:
            s.write(output / 'FAILED.json', s.encode({'status': 'unscoreable_provider_campaign',
                    'completed_queries': completed, 'required_queries': 400, 'error_type': type(error).__name__,
                    'retry_allowed': False, 'private_target_reads': 0, 'scoring_performed': False}))
        raise ValueError('Trusted provider campaign failed; retained partial evidence is unscoreable') from None
    finally:
        token[:] = b'\0' * len(token)


def admit_arm(root, expected_receipt, delivery_root, deps):
    root = s.path(root)
    s.need({item.name for item in root.iterdir()} == {'MANIFEST.json', 'episodes', 'attempts.jsonl', 'collection', 'ARM.json'},
           'Complete provider arm membership')
    raw = s.read(root / 'ARM.json', 262144, expected_receipt)
    arm = s.decode(raw)
    s.need(arm['schema'] == ARM_SCHEMA and arm['status'] == 'closed_unscored_provider_arm'
           and arm['route'] == s.ROUTE and arm['condition'] == s.CONDITION
           and arm['queries'] == 400 and arm['demonstrations'] == 4 and arm['source'] == deps['bindings']
           and arm['operator'] == s.identity() and arm['all_direct_children_reaped'] is True
           and arm['descendant_absence_verified'] is False and arm['local_participant_sandbox'] is None
           and arm['remote_context_qualified'] is False and arm['provider_capacity_qualified'] is False
           and arm['scientific_qualification'] is False and arm['private_target_reads'] == 0
           and arm['scoring_performed'] is False, 'Exact trusted provider arm required')
    manifest = s.decode(s.read(root / 'MANIFEST.json', 32768, arm['manifest']))
    s.need(manifest['schema'] == 'neural077_trusted_provider_campaign_v1' and manifest['route'] == s.ROUTE
           and manifest['condition'] == s.CONDITION and manifest['queries'] == 400 and manifest['demonstrations'] == 4
           and manifest['source'] == deps['bindings'] and manifest['operator'] == s.identity()
           and manifest['retry_policy'] == 'none' and manifest['local_participant_sandbox'] is None
           and manifest['participant_code_executed_locally'] is False
           and manifest['credentials_channel'] == 'operator_owned_inherited_pipe'
           and manifest['remote_context_qualified'] is False and manifest['provider_capacity_qualified'] is False,
           'Provider campaign source/access mismatch')
    budgets = manifest['limits']
    s.need(budgets == limits(budgets['query_seconds'], budgets['campaign_seconds'], budgets['max_prompt_bytes']),
           'Exact campaign budget profile')
    s.need(all(type(manifest[name]) in (int, float) and math.isfinite(manifest[name])
               for name in ('started_monotonic', 'deadline'))
           and manifest['deadline'] == manifest['started_monotonic'] + budgets['campaign_seconds'],
           'Exact original campaign clock')
    rows = contexts(deps, delivery_root, budgets)
    s.need({item.name for item in (root / 'episodes').iterdir()} == {f'{i:03d}' for i in range(400)}
           and len(arm['episode_ends']) == 400, 'Complete provider episode inventory')
    attempts = []; response_ids = set()
    totals = {name: 0 for name in ('input_tokens', 'output_tokens', 'total_tokens')}
    for row in rows:
        directory = root / 'episodes' / f"{row['ordinal']:03d}"
        s.read(directory / 'END.json', 16384, arm['episode_ends'][row['ordinal']])
        envelope, response_id, usage = audit_episode(directory, row, deps, manifest)
        s.need(response_id not in response_ids, 'Reused provider response identity')
        response_ids.add(response_id); attempts.append(envelope)
        for name in totals:
            totals[name] += usage[name]
    ledger = s.read(root / 'attempts.jsonl', MAX_LEDGER, arm['attempts'])
    s.need(ledger == b''.join(s.encode(item) for item in attempts) and arm['usage'] == totals,
           'Provider ledger/token custody mismatch')
    receipt = s.decode(s.read(root / 'collection/COMPLETE.json', 16384, arm['collection']))
    s.need(receipt['schema'] == 'neural077_complete_response_admission_v1'
           and receipt['status'] == 'complete_unscored_submission' and receipt['condition'] == s.CONDITION
           and receipt['responses'] == 400 and receipt['attempts'] == arm['attempts']
           and receipt['submission'] == arm['submission'] and receipt['private_target_reads'] == 0
           and receipt['scoring_performed'] is False and receipt['transport_enforcement_qualified'] is False,
           'Unchanged complete collector receipt required')
    s.read(root / 'collection/attempts.jsonl', MAX_LEDGER, arm['attempts'])
    prediction = s.read(root / 'collection/submission.npz', 1048576, arm['submission'])
    # This is public output-to-response custody, not another scoring metric.
    import numpy as np
    with np.load(io.BytesIO(prediction), allow_pickle=False) as arrays:
        s.need(set(arrays.files) == {'trial_ids', 'target_probability'}
               and arrays['trial_ids'].tolist() == [row['trial_id'] for row in rows]
               and np.array_equal(arrays['target_probability'], np.asarray(
                   [deps['parser'].parse(item['response'].encode(), item['trial_id']) for item in attempts], dtype=np.float64)),
               'Submission differs from all first provider answers')
    return root / 'collection/submission.npz', arm['submission'], s.pin(raw)


def grade(request_path, expected_sha):
    request_raw = s.read(request_path, 65536)
    s.need(s.pin(request_raw)['sha256'] == expected_sha, 'Frozen evaluator request changed')
    request = s.decode(request_raw)
    output = s.path(request['output']); output.mkdir(mode=0o700)
    accounting = {'both_public_validated_before_private': False, 'private_reference_attempts': 0,
                  'target_loader_attempts': 0, 'temporary_submission_bytes_created': 0}
    try:
        deps = s.sources(request['implementations_root'])
        s.need(request['schema'] == 'neural077_trusted_provider_pair_request_v1'
               and request['operator'] == s.identity() and request['source'] == deps['bindings'],
               'Exact trusted-provider evaluator source')
        a = admit_arm(request['a']['root'], request['a']['receipt'], request['delivery_root'], deps)
        pair = deps['pair']
        b = pair._admit_arm(request['b'], 'matched_waveform_programme', deps['original_bindings'], pair.operator_identity())
        ids = pair.public_roster(request['delivery_root'], deps['comparator'])
        result = pair.protected_compare(deps['comparator'], deps['original_bodies'], (a, b), ids,
                                        request['private_locations'], accounting)
        result.update(operator_route='trusted_provider_and_macos_programme_pair_v1',
                      participant_code_executed_in_evaluator=False, provider_context_qualified=False,
                      provider_capacity_qualified=False, scientific_qualification=False,
                      source=deps['bindings'], operator=s.identity(), accounting=accounting,
                      evaluator_runtime={'python': platform.python_version(), 'executable': sys.executable})
        s.write(output / 'RESULT.json', s.encode(result))
        return result
    except BaseException as error:
        s.write(output / 'FAILED.json', s.encode({'status': 'unscored_failure', 'error_type': type(error).__name__,
                                                'accounting': accounting, 'retry_allowed': False}))
        raise


def dispatch_grade(implementations_root, delivery_root, a, b, private_locations, output, timeout):
    s.need(type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= 180, 'Bounded grading timeout')
    deps = s.sources(implementations_root); pair = deps['pair']
    a_descriptor = {'root': str(s.path(a)), 'receipt': s.pin(s.read(Path(a) / 'ARM.json', 262144))}
    b_descriptor = pair._arm_descriptor(b)
    admit_arm(a_descriptor['root'], a_descriptor['receipt'], delivery_root, deps)
    pair._admit_arm(b_descriptor, 'matched_waveform_programme', deps['original_bindings'], pair.operator_identity())
    output = s.path(output); output.mkdir(mode=0o700)
    request = {'schema': 'neural077_trusted_provider_pair_request_v1', 'operator': s.identity(),
               'source': deps['bindings'], 'implementations_root': str(s.path(implementations_root)),
               'delivery_root': str(s.path(delivery_root)), 'a': a_descriptor, 'b': b_descriptor,
               'private_locations': str(Path(private_locations).absolute()), 'output': str(output / 'grade')}
    request_pin = s.write(output / 'REQUEST.json', s.encode(request))
    environment = {'LANG': 'C', 'LC_ALL': 'C', 'PYTHONDONTWRITEBYTECODE': '1',
                   'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}
    with (output / 'evaluator.log').open('xb') as log:
        try:
            child = subprocess.run([sys.executable, '-B', str(HERE / 'provider_arm.py'), '_grade',
                                    '--request', str(output / 'REQUEST.json'), '--sha256', request_pin['sha256']],
                                   cwd=output, env=environment, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                   timeout=timeout, check=False, close_fds=True)
            s.need(child.returncode == 0, 'Trusted paired evaluator failed')
        except BaseException as error:
            s.write(output / 'FAILED.json', s.encode({'status': 'evaluation_dispatch_failed',
                    'error_type': type(error).__name__, 'retry_allowed': False}))
            raise
    return {'status': 'trusted_provider_pair_evaluation_closed', 'request': request_pin,
            'result': s.pin(s.read(output / 'grade/RESULT.json')), 'private_inputs_opened_in_dispatcher': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    run = commands.add_parser('run')
    for name in ('implementations-root', 'delivery-root', 'output', 'model', 'python'):
        run.add_argument('--' + name, required=True)
    run.add_argument('--credential-fd', type=int, required=True)
    run.add_argument('--max-output-tokens', type=int, required=True)
    run.add_argument('--query-seconds', type=float, required=True)
    run.add_argument('--campaign-seconds', type=float, required=True)
    run.add_argument('--max-prompt-bytes', type=int, default=262144)
    compare = commands.add_parser('compare')
    for name in ('implementations-root', 'delivery-root', 'a', 'b', 'private-locations', 'output'):
        compare.add_argument('--' + name, required=True)
    compare.add_argument('--timeout', type=float, default=60)
    internal = commands.add_parser('_grade', help=argparse.SUPPRESS)
    internal.add_argument('--request', required=True); internal.add_argument('--sha256', required=True)
    args = vars(parser.parse_args(argv)); action = args.pop('action')
    try:
        result = run_arm(**args) if action == 'run' else dispatch_grade(**args) if action == 'compare' else grade(args['request'], args['sha256'])
        print(s.encode({'status': result['status']}).decode(), end='')
        return 0
    except Exception as error:
        print(s.encode({'status': 'refused', 'error_type': type(error).__name__}).decode(), end='')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
