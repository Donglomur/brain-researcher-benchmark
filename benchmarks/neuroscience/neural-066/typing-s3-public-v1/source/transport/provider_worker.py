"""Trusted owned-container Ollama lifecycle. No ambient/public HTTP service.

Host absolute time is never compared with this guest's monotonic epoch. Every
call has a local elapsed ceiling; the independent host retains its cutoff.
"""
import failures
import base64, http.client, os, re, signal, subprocess, sys, time
from pathlib import Path
from .io import capture, publish, encoded, parse, pin, need, Clock, failure
from .vendor.engine import BOOTSTRAP, process_identity, cleanup_all, finish_cleanup
PORT = 18473

def proc_bytes(path, cap):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    primary = None
    try:
        out = bytearray()
        while True:
            raw = os.read(fd, min(4096, cap + 1 - len(out)))
            if not raw:
                break
            out.extend(raw)
            need(len(out) <= cap, 'Bounded proc metadata')
        return bytes(out)
    except BaseException as exc:
        failures.hold(exc, 'caught')
        primary = exc
        raise
    finally:
        finish_cleanup([('proc.close', lambda: os.close(fd))], primary)

def process(pid):
    p = Path('/proc') / str(pid)
    raw = proc_bytes(p / 'stat', 4096)
    f = raw[raw.rfind(b')') + 2:].split()
    need(f[0] not in (b'Z', b'X', b'x'), 'Live owned peer')
    return {'pid': pid, 'ppid': int(f[1]), 'start': int(f[19]), 'cmdline': proc_bytes(p / 'cmdline', 16384).replace(b'\x00', b' ').decode()}

def listener(port, pid):
    need(type(port) is int and 0 < port < 65536, 'Explicit owned port')
    sockets = set()
    count = 0
    for fd in (Path('/proc') / str(pid) / 'fd').iterdir():
        count += 1
        need(count <= 256, 'Bounded owned fd set')
        try:
            target = os.readlink(fd)
        except FileNotFoundError:
            continue
        if target.startswith('socket:['):
            sockets.add(target[8:-1])
    found = []
    for line in proc_bytes('/proc/net/tcp', 262144).decode().splitlines()[1:]:
        f = line.split()
        addr, p = f[1].split(':')
        if int(p, 16) == port and f[3] == '0A':
            need(addr == '0100007F' and f[9] in sockets, 'Only exact process-owned IPv4 loopback listener')
            found.append(f[9])
    need(len(found) == 1, 'Exactly one owned loopback listener')
    for line in proc_bytes('/proc/net/tcp6', 262144).decode().splitlines()[1:]:
        f = line.split()
        need(not (int(f[1].rsplit(':', 1)[1], 16) == port and f[3] == '0A'), 'No unadmitted IPv6 listener')

def owned_runner(server, p):
    rows = []
    count = 0
    for directory in Path('/proc').iterdir():
        if not directory.name.isdecimal():
            continue
        count += 1
        need(count <= p['process_inventory_cap'], 'Bounded private process inventory')
        try:
            row = process(int(directory.name))
        except (FileNotFoundError, ProcessLookupError, ValueError):
            continue
        if row['ppid'] != server['pid']:
            continue
        match = re.search('--port\\s+(\\d+)', row['cmdline'])
        if match:
            need(all((x in row['cmdline'] for x in p['runner_required_arguments'])), 'Qualified offline runner options')
            row['port'] = int(match.group(1))
            need(row['port'] not in (PORT, 11434), 'Nonambient runner endpoint')
            listener(row['port'], row['pid'])
            rows.append(row)
    need(len(rows) == 1, 'One current owned child model runner')
    return rows[0]

def validate_profile(p):
    need(p['schema'] == 'neural066_owned_ollama_profile_v1', 'Qualified N066 provider profile')
    for k in ('max_turns', 'max_prompt_bytes', 'max_action_bytes', 'http_request_bytes', 'http_response_bytes', 'wire_bytes', 'max_prompt_tokens', 'max_completion_tokens', 'max_total_tokens', 'service_log_bytes', 'process_inventory_cap', 'setup_seconds', 'close_seconds', 'turn_seconds'):
        need(type(p[k]) is int and p[k] > 0, 'Prospective finite provider bound ' + k)
    required = {'seed', 'num_ctx', 'num_predict', 'temperature', 'top_k', 'top_p', 'min_p', 'repeat_last_n', 'repeat_penalty', 'num_thread', 'num_batch', 'num_gpu', 'use_mmap', 'presence_penalty', 'frequency_penalty', 'stop'}
    o = p['options']
    need(set(o) == required, 'No hidden sampling defaults')
    for k in ('seed', 'num_ctx', 'num_predict', 'num_thread', 'num_batch', 'num_gpu', 'top_k', 'repeat_last_n'):
        need(type(o[k]) is int, 'Explicit integer sampler field')
    need(o['seed'] >= 0 and o['num_ctx'] > 0 and (o['num_predict'] == p['max_completion_tokens']) and (o['num_thread'] > 0) and (o['num_batch'] > 0) and (o['num_gpu'] == 0), 'Selected reproducible offline CPU policy; no guessed model')
    need(type(o['use_mmap']) is bool and type(o['stop']) is list and all((type(x) is str for x in o['stop'])), 'Explicit sampler types')
    import math
    for k in ('temperature', 'top_p', 'min_p', 'repeat_penalty', 'presence_penalty', 'frequency_penalty'):
        need(type(o[k]) in (int, float) and math.isfinite(o[k]), 'Finite explicit sampler field')
    need(p['max_prompt_tokens'] + p['max_completion_tokens'] <= o['num_ctx'], 'Full untruncated context reservation')
    need(p['wire_bytes'] >= 16 * (p['http_request_bytes'] + p['http_response_bytes'] + 24576), 'Complete bounded eight-call wire capture reservation')
    need(type(p['runner_required_arguments']) is list and {'--offline', '--host 127.0.0.1', '--no-webui', '--no-jinja', '-c ' + str(o['num_ctx']), '-np 1'} <= set(p['runner_required_arguments']), 'Exact qualified offline/debug-render capability')
    need(type(p['prefix']) is str and type(p['suffix']) is str and (type(p['model']) is str) and p['model'] and p['binary'].startswith('/'), 'Explicit model/template/binary')
    need(re.fullmatch('sha256:[a-f0-9]{64}', p['model_digest']) and p['render_capability'] == 'qualified_debug_render_only_v1', 'No stock-provider compatibility assumption')
    for k in ('template', 'parameters', 'tokenizer'):
        need(type(p[k]) is dict and set(p[k]) == {'bytes', 'sha256'} and re.fullmatch('[a-f0-9]{64}', p[k]['sha256']), 'Bound exact ' + k)
    return p

def http_call(route, payload, peer, clock, wire, p):
    need(route in ('/api/version', '/api/tags', '/api/show', '/api/ps', '/api/generate', '/tokenize'), 'No general URL tool')
    current = process(peer['pid'])
    need(current['start'] == peer['start'], 'Unrecycled owned peer')
    listener(peer['port'], peer['pid'])
    raw = None if payload is None else encoded(payload)
    need(raw is None or len(raw) <= p['http_request_bytes'], 'Complete HTTP request bound')
    row = {'route': route, 'peer': peer, 'request_base64': None if raw is None else base64.b64encode(raw).decode(), 'response_base64': '', 'complete': False, 'error': None}
    conn = http.client.HTTPConnection('127.0.0.1', peer['port'], timeout=clock.left())
    parts = []
    total = 0
    primary = None
    try:
        conn.connect()
        sock = conn.sock
        conn.request('GET' if raw is None else 'POST', route, raw, {} if raw is None else {'Content-Type': 'application/json'})
        response = conn.getresponse()
        row['status'] = response.status
        row['headers'] = response.getheaders()
        need(len(encoded(row['headers'])) <= 16384, 'Bounded complete HTTP headers')
        need(response.status == 200 and response.getheader('Location') is None and (response.getheader('Content-Encoding') in (None, 'identity')), 'Nonredirected uncompressed owned response')
        while True:
            sock.settimeout(clock.left())
            chunk = response.read(min(65536, p['http_response_bytes'] + 1 - total))
            total += len(chunk)
            if chunk:
                parts.append(chunk)
            need(total <= p['http_response_bytes'], 'No truncated response admission')
            if not chunk:
                break
        body = b''.join(parts)
        value = parse(body)
        need(type(value) is dict and (not value.get('remote_host')) and (not value.get('remote_model')) and (not value.get('thinking')), 'No cloud/hidden thinking route')
        need(process(peer['pid'])['start'] == peer['start'], 'Same peer after response')
        listener(peer['port'], peer['pid'])
        clock.tick()
        row['complete'] = True
        return value
    except BaseException as exc:
        failures.hold(exc, 'caught')
        primary = exc
        row['error'] = failure(exc)
        raise
    finally:
        row['response_base64'] = base64.b64encode(b''.join(parts)).decode()
        row['response_bytes_observed'] = total
        wire.append(row)
        if len(encoded(wire)) > p['wire_bytes']:
            exc = ValueError('Complete wire evidence exceeds allowance')
            if primary is None:
                primary = exc
            else:
                failures.note(primary, failures.describe(exc))
        cleanup = cleanup_all([('http.close', conn.close)], primary)
        if primary is None and cleanup is not None:
            raise cleanup
        if primary is not None and row['error'] is None:
            raise primary

def turn(request):
    started = time.monotonic()
    p = validate_profile(parse(capture('/profile.json')))
    ready = parse(capture('/work/READY.json'))
    life = parse(capture('/lifecycle.json'))
    need(request['context'] == ready['context'] == life['context'] and type(request['turn']) is int and (1 <= request['turn'] <= p['max_turns']), 'Exact owned context/turn')
    need(type(request['duration_seconds']) in (int, float) and 0 < request['duration_seconds'] <= p['turn_seconds'], 'Guest-local elapsed allowance')
    clock = Clock(started, min(started + request['duration_seconds'], ready['guest_deadline']))
    server = {**ready['server'], 'port': PORT}
    wire = []
    error = None
    action = None
    prompt_tokens = None
    completion = None
    try:
        prompt = request['prompt']
        need(type(prompt) is str and len(prompt.encode()) <= p['max_prompt_bytes'], 'Complete current-context prompt bound')
        payload = {'model': p['model'], 'prompt': prompt, 'raw': False, 'stream': False, 'truncate': False, 'shift': False, 'format': request['format'], 'keep_alive': '1h', 'options': p['options']}
        rendered = http_call('/api/generate', {**payload, '_debug_render_only': True}, server, clock, wire, p)
        text = p['prefix'] + prompt + p['suffix']
        need(rendered.get('_debug_info', {}).get('rendered_template') == text and rendered['_debug_info'].get('image_count', 0) == 0, 'Exact full qualified template render')
        runner = owned_runner(server, p)
        loaded = http_call('/api/ps', None, server, clock, wire, p)['models']
        need(len(loaded) == 1 and loaded[0]['digest'] == p['model_digest'] and (loaded[0]['context_length'] == p['options']['num_ctx']), 'Exact loaded model/context')
        tokens = http_call('/tokenize', {'content': text, 'add_special': True, 'parse_special': True, 'with_pieces': False}, runner, clock, wire, p)['tokens']
        need(type(tokens) is list and all((type(x) is int and x >= 0 for x in tokens)) and (len(tokens) <= p['max_prompt_tokens']) and (len(tokens) + p['max_completion_tokens'] <= p['options']['num_ctx']), 'Token-proved untruncated history')
        prompt_tokens = len(tokens)
        need(type(request['remaining_tokens']) is int and prompt_tokens + p['max_completion_tokens'] <= request['remaining_tokens'] <= p['max_total_tokens'], 'Pre-generation whole-context token reservation')
        response = http_call('/api/generate', payload, server, clock, wire, p)
        completion = response.get('eval_count')
        need(response.get('done') is True and response.get('done_reason') == 'stop' and (response.get('prompt_eval_count') == prompt_tokens) and (type(completion) is int) and (0 <= completion <= p['max_completion_tokens']), 'Complete generation/tokenizer parity')
        need(type(response.get('response')) is str and len(response['response'].encode()) <= p['max_action_bytes'], 'Bounded complete action')
        action = parse(response['response'].encode())
        need(type(action) is dict and action.get('action') in ('inspect', 'train_validate', 'finalize'), 'Typed declared provider action only')
        need(owned_runner(server, p) == runner, 'Same owned runner through turn')
        clock.tick()
    except BaseException as exc:
        failures.hold(exc, 'caught')
        error = failure(exc)
    return {'schema': 'neural066_model_turn_v1', 'context': request['context'], 'turn': request['turn'], 'request': pin(encoded(request)), 'profile': pin(encoded(p)), 'wire': wire, 'action': action if error is None else None, 'unadmitted_action': action if error else None, 'error': error, 'prompt_tokens': prompt_tokens, 'completion_tokens': completion, 'guest_elapsed_seconds': time.monotonic() - started, 'guest_duration_limit': request['duration_seconds'], 'status': 'completed' if error is None else 'failed'}

def serve():
    origin = time.monotonic()
    p = validate_profile(parse(capture('/profile.json')))
    life = parse(capture('/lifecycle.json'))
    clock = Clock(origin, origin + life['duration_seconds'])
    wire = []
    server = None
    child = None
    pidfd = None
    log = None
    error = None
    closed = None
    try:
        need(type(life['duration_seconds']) in (int, float) and life['duration_seconds'] > p['setup_seconds'] + p['close_seconds'], 'Complete local lifecycle allowance')
        log = open('/work/server.log', 'xb', buffering=0)
        env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/work', 'OLLAMA_HOST': '127.0.0.1:' + str(PORT), 'OLLAMA_MODELS': '/models', 'OLLAMA_NO_CLOUD': '1', 'OLLAMA_NUM_PARALLEL': '1', 'OLLAMA_MAX_LOADED_MODELS': '1'}

        def limits():
            import resource
            resource.setrlimit(resource.RLIMIT_FSIZE, (p['service_log_bytes'], p['service_log_bytes']))
        child = subprocess.Popen([sys.executable, '-I', '-S', '-B', '-c', BOOTSTRAP, p['binary'], 'serve'], stdin=subprocess.PIPE, stdout=log, stderr=log, env=env, close_fds=True, start_new_session=True, preexec_fn=limits)
        need(hasattr(os, 'pidfd_open') and hasattr(signal, 'pidfd_send_signal'), 'Qualified identity-bound Linux lifecycle')
        pidfd = os.pidfd_open(child.pid, 0)
        identity = process_identity(child.pid, clock.deadline, lambda n: None, lambda n: clock.tick())
        publish(Path('/work/SERVER_IDENTITY.json'), encoded({'context': life['context'], 'identity': identity, 'gated': True}))
        clock.tick()
        need(os.write(child.stdin.fileno(), b'G') == 1, 'Single release byte after custody publication')
        closing_stdin, child.stdin = child.stdin, None
        closing_stdin.close()
        server = process(child.pid)
        server['port'] = PORT
        setup = Clock(origin, min(clock.deadline, origin + p['setup_seconds']))
        while True:
            setup.tick()
            need(child.poll() is None, 'Owned server remains live')
            try:
                listener(PORT, child.pid)
                break
            except ValueError:
                time.sleep(min(0.05, setup.left()))
        need(http_call('/api/version', None, server, setup, wire, p)['version'] == p['version'], 'Exact provider binary version')
        tags = http_call('/api/tags', None, server, setup, wire, p)['models']
        need(len(tags) == 1 and tags[0]['name'] == p['model'] and (tags[0]['digest'] == p['model_digest']), 'Only preinstalled admitted model')
        show = http_call('/api/show', {'model': p['model'], 'verbose': False}, server, setup, wire, p)
        for key in ('template', 'parameters'):
            need(pin(show[key].encode()) == p[key], 'Exact installed ' + key)
        need(not show.get('system') and (not show.get('messages')) and (http_call('/api/ps', None, server, setup, wire, p)['models'] == []), 'Fresh empty model context')
        publish(Path('/work/READY.json'), encoded({'context': life['context'], 'server': server, 'guest_origin': origin, 'guest_deadline': clock.deadline, 'guest_duration_limit': life['duration_seconds'], 'wire': wire}))
        clock.tick()
        while not Path('/requests/CLOSE.json').exists():
            need(clock.tick() < clock.deadline - p['close_seconds'] and child.poll() is None, 'Original local lifecycle and healthy server')
            time.sleep(min(0.05, clock.left()))
        close = parse(capture('/requests/CLOSE.json'))
        need(close['context'] == life['context'], 'Exact retirement request')
        http_call('/api/generate', {'model': p['model'], 'keep_alive': 0}, server, clock, wire, p)
        need(http_call('/api/ps', None, server, clock, wire, p)['models'] == [], 'No loaded model remains')
        signal.pidfd_send_signal(pidfd, signal.SIGTERM, None, 0)
        rc = child.wait(timeout=min(p['close_seconds'], clock.left()))
        need(rc in (0, -signal.SIGTERM), 'Explicit owned server retirement/reap')
        for name in ('/proc/net/tcp', '/proc/net/tcp6'):
            for line in proc_bytes(name, 262144).decode().splitlines()[1:]:
                f = line.split()
                need(not (int(f[1].rsplit(':', 1)[1], 16) == PORT and f[3] == '0A'), 'No listener remains after retirement')
        raw = capture('/work/server.log', cap=p['service_log_bytes'])
        closed = {'context': life['context'], 'server_reaped': True, 'model_unloaded': True, 'server_controlled_stop': rc, 'wire': wire, 'log': pin(raw), 'log_base64': base64.b64encode(raw).decode(), 'guest_elapsed_seconds': clock.tick() - origin, 'guest_duration_limit': life['duration_seconds']}
        publish(Path('/work/CLOSED.json'), encoded(closed))
        clock.tick()
        while not Path('/requests/ACK.json').exists():
            clock.tick()
            time.sleep(min(0.05, clock.left()))
        need(parse(capture('/requests/ACK.json'))['context'] == life['context'], 'Exact close acknowledgment')
        clock.tick()
    except BaseException as exc:
        failures.hold(exc, 'caught')
        error = exc
    finally:
        actions = []
        if child is not None and child.returncode is None:
            if pidfd is not None:

                def kill():
                    try:
                        signal.pidfd_send_signal(pidfd, signal.SIGKILL, None, 0)
                    except ProcessLookupError:
                        pass
                actions.append(('server.pidfd_kill', kill))
            actions.append(('server.reap', lambda: child.wait(timeout=max(0, clock.deadline - time.monotonic()))))
        if child is not None and child.stdin is not None:
            actions.append(('server.stdin.close', child.stdin.close))
        if pidfd is not None:
            actions.append(('server.pidfd.close', lambda: os.close(pidfd)))
        if log is not None:
            actions.append(('server.log.close', log.close))
        error = cleanup_all(actions, error)
    if error is not None:
        try:
            publish(Path('/work/FAILED.json'), encoded({'context': life.get('context'), 'error': failure(error), 'wire': wire, 'unadmitted_closed': closed, 'custody': 'unknown', 'guest_elapsed_seconds': time.monotonic() - origin}))
        except BaseException as secondary:
            failures.hold(secondary, 'caught')
            failures.note(error, 'Failure publication: ' + failures.kind(secondary))
        raise error
    clock.tick()
if __name__ == '__main__':
    serve()
