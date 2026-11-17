"""Owner-only bounded local authoring gateway. Source only until selected.

Candidate traffic is JSON lines on stdin/stdout, exclusively exec and submit.
Shell text executes only inside the owned offline container. Candidate text
never supplies host paths, evaluator plans, expected targets, or issuer keys.
"""
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import stat
import sys
import time
import traceback

import configuration as cfg

PRIVATE_LIMIT = 16777216
LOG_LIMIT = 2097152


def container_argv(name, stage, paper, task, runtime):
    return ['docker', 'create', '--pull=never', '--name', name,
            '--network=none', '--read-only', '--cpus=1', '--memory=2g', '--memory-swap=2g',
            '--pids-limit=64', '--log-driver=none', '--cap-drop=ALL',
            '--security-opt=no-new-privileges', '--user=' + str(runtime['uid']) + ':' + str(runtime['gid']), '--workdir=/work',
            '--tmpfs=/work:rw,nosuid,nodev,size=134217728,mode=1777',
            '--tmpfs=/tmp:rw,nosuid,nodev,size=134217728,mode=1777',
            '--ulimit=nofile=1024:1024', '--ulimit=fsize=1048576:1048576',
            '--mount', f'type=bind,src={stage},dst=/input,readonly',
            '--mount', f'type=bind,src={paper},dst=/paper/article.pdf,readonly',
            '--mount', f'type=bind,src={task},dst=/task,readonly',
            '--label', 'nider.owner=' + name,
            '--entrypoint=/bin/sh', runtime['image'], '-c', 'exec sleep 3600']


def validate_inspection(obj, cid, mounts, name, runtime, running):
    """A distinct shell-session policy; never relabel an Rscript inspection."""
    cfg.require(type(obj) is list and len(obj) == 1, 'authoring_inspection')
    item = obj[0]; host = item['HostConfig']; state = item['State']; config = item['Config']
    cfg.require(item['Id'] == cid and item['Image'] == runtime['image'] and item['RestartCount'] == 0 and
                item['Name'] == '/' + name and config['Labels'].get('nider.owner') == name,
                'authoring_container_identity')
    cfg.require(config['Entrypoint'] == ['/bin/sh'] and config['Cmd'] == ['-c', 'exec sleep 3600'] and
                config['User'] == str(runtime['uid']) + ':' + str(runtime['gid']) and config['WorkingDir'] == '/work', 'authoring_process')
    cfg.require(host['NetworkMode'] == 'none' and host['ReadonlyRootfs'] is True and
                host['Memory'] == host['MemorySwap'] == 2147483648 and host['NanoCpus'] == 1000000000 and
                host['PidsLimit'] == 64 and host['LogConfig']['Type'] == 'none' and
                host['CapDrop'] == ['ALL'] and host['SecurityOpt'] == ['no-new-privileges'] and host['UsernsMode']=='' and host['Privileged'] is False, 'authoring_resources')
    cfg.require(host['Tmpfs'] == {'/work': 'rw,nosuid,nodev,size=134217728,mode=1777',
                                 '/tmp': 'rw,nosuid,nodev,size=134217728,mode=1777'}, 'authoring_tmpfs')
    cfg.require(len(host['Ulimits']) == 2 and
                {(x['Name'], x['Soft'], x['Hard']) for x in host['Ulimits']} ==
                {('nofile', 1024, 1024), ('fsize', 1048576, 1048576)}, 'authoring_ulimits')
    binds = [x for x in item['Mounts'] if x['Type'] == 'bind']
    cfg.require(len(binds) == 3 and {(x['Source'], x['Destination'], x['RW']) for x in binds} == mounts and
                all(x['Type'] in ('bind', 'tmpfs') for x in item['Mounts']), 'authoring_mounts')
    cfg.require(state['Status'] == ('running' if running else 'created') and state['Running'] is running and
                not state['OOMKilled'] and not state['Error'] and not state['Paused'] and not state['Restarting'],
                'authoring_state')
    return item


def retained_bytes(root):
    total = 0
    for p in root.rglob('*'):
        info = p.lstat()
        cfg.require(stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode), 'private_special_file')
        if stat.S_ISREG(info.st_mode):
            total += info.st_size
    return total


def validate_request(value):
    cfg.require(type(value) is dict and type(value.get('op')) is str, 'request_schema')
    if value['op'] == 'exec':
        cfg.require(set(value) == {'op', 'command'} and type(value['command']) is str and
                    '\x00' not in value['command'] and 1 <= len(value['command'].encode()) <= 65536,
                    'exec_request')
    elif value['op'] == 'submit':
        cfg.require(set(value) == {'op', 'program', 'deviations'} and
                    type(value['program']) is type(value['deviations']) is str and
                    '\x00' not in value['program'] + value['deviations'] and
                    1 <= len(value['program'].encode()) <= 262144 and
                    1 <= len(value['deviations'].encode()) <= 65536, 'submit_request')
    else:
        raise ValueError('unknown_operation')
    return value


def run(plan_pin, input_fd=0, output_fd=1):
    # No candidate-supplied locator is accepted by the owner entry point.
    raw = cfg._bootstrap_read(plan_pin['path'], plan_pin, 65536)
    plan = json.loads(raw)
    cfg.require(type(plan) is dict and set(plan) == {'schema', 'prepared', 'arm', 'policy', 'runtime_policy', 'owner_root'} and
                plan['schema'] == 'nider_local_authoring_plan_v1' and plan['arm'] in ('A', 'B'), 'authoring_plan')
    cfg.authoring_policy(plan['policy'])
    modules, fixed, prepared = cfg.admit_prepared(plan['prepared'])
    c = modules['custody']; binding = modules['owner_binding']; runner = modules['protected_runner']; rp = modules['runtime_policy']
    runtime = rp.admit(plan['runtime_policy'])
    cfg.require(plan['runtime_policy'] == prepared['runtime_policy'] and runtime == prepared['runtime'], 'authoring_runtime_join')
    # Duplicate/nonfinite decoding after authenticating the trusted module.
    cfg.require(c.decode(raw) == plan, 'authoring_plan_decode')
    root = c.plain(plan['owner_root']); root.mkdir(mode=0o700)
    logs = root / 'logs'; logs.mkdir(mode=0o700)
    c.write_new(root / 'ATTEMPT_GUARD.json', c.encoded({'plan': plan_pin, 'maximum_attempts': 1}))
    policy = plan['policy']; began = time.monotonic(); deadline = began + policy['wall_seconds']
    calls = []; commands = []; cleanup = []; staged = []; cid = None; name = None
    created = []; failure = None; submitted = None; terminal = None; counter = 0; creation_dispatched = False; live_pin = None
    input_bytes = 0; output_bytes = 0; input_buffer = bytearray(); protocol_events = []
    reader = writer = protocol_input = protocol_output = None
    old_in = old_out = old_term = old_int = None
    regular_input = regular_output = False; signals_installed = False
    emergency = root / 'EMERGENCY_RESERVE.bin'
    c.write_new(emergency, bytes(65536))

    def emergency_record(error, phase, original_failure):
        # The reserved file exists before any Docker dispatch. Reuse that
        # space on preservation failure instead of requiring another inode.
        detail = traceback.format_exc()
        full = detail.encode('utf-8', errors='backslashreplace')
        event = {'schema': 'nider_authoring_emergency_v1', 'phase': phase,
                 'exception_class': type(error).__name__, 'original_exception_message': str(error),
                 'original_failure': original_failure, 'created_CIDs': created,
                 'active_CID': cid, 'cleanup': cleanup,
                 'traceback_utf8_bytes': len(full), 'traceback_sha256': hashlib.sha256(full).hexdigest(),
                 'traceback_prefix': full[:32768].decode('utf-8', errors='replace'),
                 'traceback_truncated': len(full) > 32768}
        encoded = c.encoded(event)
        if len(encoded) > 65536:
            event['original_exception_message'] = str(error)[:2048]
            event['exception_message_truncated'] = True
            event['original_failure'] = {'code': 'oversized_failure_record_see_original_streams'}
            encoded = c.encoded(event)
        cfg.require(len(encoded) <= 65536, 'emergency_record_extent')
        with emergency.open('r+b') as stream:
            stream.seek(0); stream.write(encoded); stream.truncate(); stream.flush(); os.fsync(stream.fileno())

    def cancelled(_signum, _frame):
        raise ValueError('owner_signal_cancelled')

    def within_active():
        cfg.require(time.monotonic() < deadline, 'authoring_wall_limit')
        cfg.require(retained_bytes(root) <= PRIVATE_LIMIT - 2097152, 'authoring_private_limit')

    def call(argv, seconds=5, cleanup_call=False, command=False):
        nonlocal counter
        if not cleanup_call: within_active()
        counter += 1
        duration = seconds if cleanup_call else min(seconds, max(.001, deadline - time.monotonic()))
        record = {'argv': argv, 'dispatch_attempted': True, 'outcome_observed': False,
                  'declared_seconds': duration, 'cleanup_call': cleanup_call}
        calls.append(record)
        try:
            observed = runner.bounded_process(argv, duration, logs / f'{counter:03d}.stdout', logs / f'{counter:03d}.stderr')
        except BaseException as error:
            record['dispatch_exception_class'] = type(error).__name__
            record['partial_files'] = [c.pin(p.read_bytes(), p) for p in
                (logs / f'{counter:03d}.stdout', logs / f'{counter:03d}.stderr') if p.is_file()]
            raise
        record.update(observed); record['outcome_observed'] = True
        cfg.require(cleanup_call or retained_bytes(logs) <= LOG_LIMIT, 'authoring_log_limit')
        cfg.require(record['reason'] is None and record['reaped'] and
                    record['EOF'] == ['stderr', 'stdout'] and not record['truncated'], 'command_lifecycle_failure')
        if not command: cfg.require(record['exit_code'] == 0, 'docker_control_failure')
        return record

    def body(record, stream='stdout'):
        return c.read_pin(record[stream], maximum=65536)

    def json_call(argv, cleanup_call=False):
        return c.decode(body(call(argv, cleanup_call=cleanup_call)))

    def send(value):
        nonlocal output_bytes
        data = cfg.canonical(value) + b'\n'
        cfg.require(output_bytes + len(data) <= policy['total_output_bytes'], 'protocol_output_extent')
        pos = 0
        while pos < len(data):
            within_active()
            if regular_output or writer.select(min(.05, max(0, deadline - time.monotonic()))):
                try: count = os.write(output_fd, data[pos:])
                except BlockingIOError: continue
                cfg.require(count > 0, 'protocol_output_closed')
                protocol_output.write(data[pos:pos + count]); protocol_output.flush()
                pos += count; output_bytes += count
        protocol_events.append({'direction': 'out', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})

    def receive():
        nonlocal input_bytes
        while b'\n' not in input_buffer:
            within_active()
            if not regular_input and not reader.select(min(.05, max(0, deadline - time.monotonic()))): continue
            try: chunk = os.read(input_fd, min(65536, policy['total_input_bytes'] - input_bytes + 1))
            except BlockingIOError: continue
            cfg.require(chunk, 'protocol_input_EOF_before_submit')
            protocol_input.write(chunk); protocol_input.flush()
            input_bytes += len(chunk)
            cfg.require(input_bytes <= policy['total_input_bytes'], 'protocol_input_extent')
            input_buffer.extend(chunk)
            cfg.require(len(input_buffer) <= 524288, 'protocol_line_extent')
        raw_line, _, rest = input_buffer.partition(b'\n'); input_buffer[:] = rest
        protocol_events.append({'direction': 'in', 'bytes': len(raw_line) + 1,
                                'sha256': hashlib.sha256(raw_line + b'\n').hexdigest()})
        return validate_request(c.decode(bytes(raw_line)))

    def clean():
        nonlocal cid
        if cid is None: return
        owned = cid
        call(['docker', 'rm', '-f', owned], cleanup_call=True)
        by_id = body(call(['docker', 'ps', '-aq', '--no-trunc', '--filter', f'id={owned}'], cleanup_call=True))
        by_name = body(call(['docker', 'ps', '-aq', '--no-trunc', '--filter', f'name=^/{name}$'], cleanup_call=True))
        cfg.require(not by_id.strip() and not by_name.strip(), 'owned_container_cleanup_absence')
        cleanup.append({'cid': owned, 'name': name, 'removed_and_absence_verified': True})
        cid = None

    try:
        protocol_input = (root / 'protocol.stdin.bin').open('xb')
        protocol_output = (root / 'protocol.stdout.bin').open('xb')
        old_in = os.get_blocking(input_fd); old_out = os.get_blocking(output_fd)
        regular_input = stat.S_ISREG(os.fstat(input_fd).st_mode)
        regular_output = stat.S_ISREG(os.fstat(output_fd).st_mode)
        os.set_blocking(input_fd, False); os.set_blocking(output_fd, False)
        reader = selectors.DefaultSelector(); writer = selectors.DefaultSelector()
        if not regular_input: reader.register(input_fd, selectors.EVENT_READ)
        if not regular_output: writer.register(output_fd, selectors.EVENT_WRITE)
        old_term = signal.getsignal(signal.SIGTERM); old_int = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGTERM, cancelled); signals_installed = True
        signal.signal(signal.SIGINT, cancelled)
        live = rp.observe_live(runtime, json_call)
        live_pin = c.write_new(root / 'RUNTIME_ADMISSION.json', c.encoded(live))
        catalogue, cases = binding.admit_catalogue(prepared['catalogue'])
        cfg.require(catalogue['runtime_policy'] == plan['runtime_policy'], 'authoring_catalogue_runtime_join')
        material, paper_raw = binding.admit_materials(prepared['materials'])
        cfg.require(cases[0]['kind'] == 'original', 'authoring_original_only')
        stage = root / 'input'; staged += binding.stage_exposure(stage, cases[0], catalogue, plan['arm'])
        paper = root / 'article.pdf'; staged.append(c.write_new(paper, paper_raw))
        task = root / 'task'; task.mkdir(mode=0o700)
        for key in fixed['candidate_doc_keys']:
            staged.append(c.write_new(task / key.removeprefix('doc_'), c.read_pin(prepared['assets'][key])))
        staged.append(c.write_new(task / 'ARTICLE.txt', c.read_pin(prepared['assets']['paper_text'])))
        rp.owned_files(runtime, staged)
        name = 'nider-author-' + hashlib.sha256(str(root).encode()).hexdigest()[:24]
        cfg.require(not body(call(['docker', 'ps', '-aq', '--no-trunc', '--filter', f'name=^/{name}$'])).strip(),
                    'fresh_container_name')
        creation_dispatched = True
        result = call(container_argv(name, stage, paper, task, runtime))
        returned_cid = body(result).decode().strip()
        cfg.require(len(returned_cid) == 64 and all(x in '0123456789abcdef' for x in returned_cid), 'created_container_id')
        cid = returned_cid
        created.append(cid)
        mounts = {(str(stage), '/input', False), (str(paper), '/paper/article.pdf', False), (str(task), '/task', False)}
        validate_inspection(json_call(['docker', 'inspect', cid]), cid, mounts, name, runtime, False)
        call(['docker', 'start', cid])
        validate_inspection(json_call(['docker', 'inspect', cid]), cid, mounts, name, runtime, True)
        send({'status': 'ready', 'arm': plan['arm'], 'tools': ['exec', 'submit'],
              'policy': policy, 'paths': ['/input', '/paper/article.pdf', '/task'],
              'network': 'none', 'repository_retrieval': 'forbidden', 'original_case_only': True})
        while submitted is None:
            message = receive()
            if message['op'] == 'submit':
                cfg.require(not input_buffer.strip(), 'trailing_request_after_submit')
                submitted = message; terminal = 'submitted'
                break
            cfg.require(len(commands) < policy['command_limit'], 'command_count_limit')
            record = call(['docker', 'exec', cid, '/bin/sh', '-lc', message['command']],
                          seconds=policy['command_seconds'], command=True)
            commands.append({'command_sha256': hashlib.sha256(message['command'].encode()).hexdigest(),
                             'call_index': len(calls) - 1, 'exit_code': record['exit_code']})
            send({'status': 'command_complete', 'exit_code': record['exit_code'],
                  'stdout': body(record).decode('utf-8', errors='replace'),
                  'stderr': body(record, 'stderr').decode('utf-8', errors='replace')})
        validate_inspection(json_call(['docker', 'inspect', cid]), cid, mounts, name, runtime, True)
        for entry in staged: c.read_pin(entry, maximum=8388608)
    except BaseException as error:
        detail = str(error)
        fixed_code = detail if type(error) in (ValueError, c.Invalid) and detail and all(
            x in 'abcdefghijklmnopqrstuvwxyz0123456789_' for x in detail) else 'owner_failure'
        failure = {'class': type(error).__name__, 'code': fixed_code,
                   'original_exception_message': detail, 'original_traceback': traceback.format_exc()}
        terminal = 'failed'
    finally:
        # Prevent a second cancellation from interrupting exact owned cleanup.
        if signals_installed:
            signal.signal(signal.SIGTERM, signal.SIG_IGN); signal.signal(signal.SIGINT, signal.SIG_IGN)
        if cid is None and name is not None and creation_dispatched:
            try:
                recovered = body(call(['docker', 'ps', '-aq', '--no-trunc', '--filter', f'name=^/{name}$',
                                       '--filter', 'label=nider.owner=' + name], cleanup_call=True)).decode().strip()
                if recovered:
                    cfg.require(len(recovered) == 64 and all(x in '0123456789abcdef' for x in recovered), 'recovered_CID')
                    obj = json_call(['docker', 'inspect', recovered], cleanup_call=True)
                    cfg.require(len(obj) == 1 and obj[0]['Id'] == recovered and
                                obj[0]['Config']['Labels'].get('nider.owner') == name, 'recovered_owned_identity')
                    cid = recovered; created.append(cid)
            except BaseException as error:
                failure = {'class': 'OwnedCreateRecovery', 'code': 'owned_create_recovery_unverified', 'preceding': failure,
                           'original_exception_class': type(error).__name__, 'original_exception_message': str(error),
                           'original_traceback': traceback.format_exc()}
        if cid is not None:
            try: clean()
            except BaseException as error:
                failure = {'class': 'OwnedCleanup', 'code': 'owned_cleanup_unverified', 'preceding': failure,
                           'original_exception_class': type(error).__name__, 'original_exception_message': str(error),
                           'original_traceback': traceback.format_exc()}
        try:
            for handle in (reader, writer, protocol_input, protocol_output):
                if handle is not None: handle.close()
            if old_in is not None: os.set_blocking(input_fd, old_in)
            if old_out is not None: os.set_blocking(output_fd, old_out)
        except BaseException as error:
            preceding = failure
            failure = {'class': type(error).__name__, 'code': 'protocol_resource_unwind_failed',
                       'original_exception_message': str(error), 'original_traceback': traceback.format_exc(),
                       'preceding': preceding}
        life = {'schema': 'nider_local_authoring_lifecycle_v1', 'plan': plan_pin,
                'arm': plan['arm'], 'policy_sha256': cfg.authoring_policy(policy), 'runtime_policy': plan['runtime_policy'], 'runtime_admission': live_pin,
                'terminal_event': terminal, 'failure': failure, 'calls': calls, 'commands': commands,
                'cleanup': cleanup, 'created_CIDs': created, 'staged_pins': staged,
                'cleanup_verified': bool(created) and cid is None and
                    set(created) == {x['cid'] for x in cleanup} and failure is None,
                'elapsed_seconds': time.monotonic() - began, 'input_bytes': input_bytes,
                'output_bytes': output_bytes, 'protocol_events': protocol_events,
                'deadline_scope': 'policy active wall; bounded owned subprocess reap and up to five cleanup calls follow',
                'candidate_model_executed': False, 'scientific_score_computed': False}
        # Cleanup can be verified even when candidate/protocol work failed.
        life['cleanup_verified'] = bool(created) and cid is None and set(created) == {x['cid'] for x in cleanup} and not (
            failure and failure['code'] in ('owned_create_recovery_unverified', 'owned_cleanup_unverified'))
        result = {'schema': 'nider_local_authoring_result_v1', 'successful_handoff': False}
        try:
            cfg.require(retained_bytes(root) <= PRIVATE_LIMIT - 524288, 'final_private_limit')
            if failure is None and submitted is not None and life['cleanup_verified']:
                result.update(cfg.seal_handoff(c, root, plan['prepared'], prepared, fixed, plan['arm'], policy,
                                              submitted['program'], submitted['deviations'], life))
                result['successful_handoff'] = True
            else:
                result['lifecycle'] = c.write_new(root / 'LIFECYCLE.json', c.encoded(life))
            c.write_new(root / 'AUTHORING_RESULT.json', c.encoded(result))
        except BaseException as error:
            result['preservation_failure'] = type(error).__name__
            result['successful_handoff'] = False
            emergency_record(error, 'handoff_or_receipt_preservation', failure)
        if signals_installed:
            signal.signal(signal.SIGTERM, old_term); signal.signal(signal.SIGINT, old_int)
        # No final stdout containing owner locators or issuer material.
    return 0 if result['successful_handoff'] else 1


if __name__ == '__main__':
    os.umask(0o077)
    cfg.require(len(sys.argv) == 3, 'owner_plan_and_digest_required')
    p = Path(sys.argv[1])
    raise SystemExit(run({'path': str(p), 'bytes': p.stat().st_size, 'sha256': sys.argv[2]}))
