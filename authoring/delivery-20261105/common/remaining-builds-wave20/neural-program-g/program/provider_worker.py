"""Owned-container Ollama service and concrete captured local HTTP client.

Requires the separately qualified donor-specific debug-render capability. Stock
Ollama compatibility, model capacity and tokenizer parity are not presumed.
No user Python runs in this service container. External networking is disabled
by the host transport, and all HTTP peers are verified owned loopback listeners.
"""
import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from .common import capture, decode, encoded, need, pin, publish

PORT = 18473
LOG_CAP = 1048576


def process(pid):
    p = Path('/proc') / str(pid)
    raw = (p / 'stat').read_text(); fields = raw[raw.rfind(')') + 2:].split()
    need(fields[0] not in ('Z', 'X'), 'Owned process remains live')
    return {'pid': pid, 'ppid': int(fields[1]), 'start': int(fields[19]),
            'cmdline': (p / 'cmdline').read_bytes().replace(b'\0', b' ').decode('utf-8')}


def listener(port, pid):
    need(0 < port < 65536, 'Bound loopback port')
    sockets = set()
    for fd in (Path('/proc') / str(pid) / 'fd').iterdir():
        try: target = os.readlink(fd)
        except FileNotFoundError: continue
        if target.startswith('socket:['): sockets.add(target[8:-1])
    found = []
    for line in Path('/proc/net/tcp').read_text().splitlines()[1:]:
        f = line.split(); addr, p = f[1].split(':')
        if int(p, 16) == port and f[3] == '0A':
            need(addr == '0100007F' and f[9] in sockets, 'Listener belongs to exact owned process on IPv4 loopback')
            found.append(f[9])
    need(len(found) == 1, 'Exactly one admitted owned listener')


def owned_runner(server, profile):
    candidates = []
    for p in Path('/proc').iterdir():
        if not p.name.isdecimal(): continue
        try: item = process(int(p.name))
        except (FileNotFoundError, ProcessLookupError): continue
        if item['ppid'] != server['pid']: continue
        match = re.search(r'--port\s+(\d+)', item['cmdline'])
        if match:
            need(all(fragment in item['cmdline'] for fragment in profile['runner_required_arguments']), 'Exact qualified runner options')
            item['port'] = int(match.group(1)); need(item['port'] not in (PORT, 11434), 'Owned nonambient runner port')
            listener(item['port'], item['pid']); candidates.append(item)
    need(len(candidates) == 1, 'Exactly one current server child runner')
    return candidates[0]


def http_call(path, payload, peer, end, wire, cap=2097152):
    allowed = ('/api/version', '/api/tags', '/api/show', '/api/ps', '/api/generate', '/tokenize')
    need(path in allowed, 'No general HTTP tool')
    current = process(peer['pid']); need(current['start'] == peer['start'], 'Unrecycled owned HTTP peer')
    listener(peer['port'], peer['pid'])
    raw = None if payload is None else encoded(payload)
    need(raw is None or len(raw) <= 2097152, 'Bound HTTP request')
    remaining = end - time.monotonic(); need(remaining > 0, 'Original HTTP deadline')
    c = http.client.HTTPConnection('127.0.0.1', peer['port'], timeout=remaining)
    try:
        c.connect(); active_socket = c.sock
        c.request('GET' if raw is None else 'POST', path, raw, {} if raw is None else {'Content-Type': 'application/json'})
        response = c.getresponse(); need(response.status == 200 and response.getheader('Location') is None, 'Exact nonredirected HTTP success')
        need(response.getheader('Content-Encoding') in (None, 'identity'), 'No hidden compression')
        blocks, total = [], 0
        while True:
            need(time.monotonic() < end, 'Response inside original deadline')
            need(active_socket is not None, 'Owned HTTP socket')
            active_socket.settimeout(max(.001, end - time.monotonic()))
            b = response.read(min(65536, cap + 1 - total)); total += len(b)
            need(total <= cap, 'Complete response bound, no truncation')
            if not b: break
            blocks.append(b)
        body = b''.join(blocks)
    finally: c.close()
    value = decode(body, cap)
    need(not value.get('remote_host') and not value.get('remote_model') and not value.get('thinking'), 'No remote model or unadmitted thinking channel')
    wire.append({'path': path, 'peer': peer, 'request_base64': None if raw is None else base64.b64encode(raw).decode(),
                 'response_base64': base64.b64encode(body).decode(), 'status': response.status, 'headers': response.getheaders(), 'request': None if raw is None else pin(raw), 'response': pin(body)})
    return value


def validate_profile(p):
    need(all(type(p['options'].get(k)) is int for k in ('seed','num_ctx','num_predict','num_thread','num_batch','num_gpu','top_k','repeat_last_n')), 'Literal integer engine and seed fields')
    need(p['schema'] == 'neural007_owned_ollama_profile_v1' and p['options']['seed'] == 0
         and p['options']['num_ctx'] == 32768 and p['options']['num_predict'] == 4096, 'Explicit pre-query seed/context/output profile')
    required = {'seed','num_ctx','num_predict','temperature','top_k','top_p','min_p','repeat_last_n','repeat_penalty','num_thread','num_batch','num_gpu','use_mmap','presence_penalty','frequency_penalty','stop'}
    need(required == set(p['options']) and p['options']['num_thread'] == 4 and p['options']['num_gpu'] == 0 and type(p['options']['use_mmap']) is bool, 'No omitted sampling/thread defaults')
    need(type(p['runner_required_arguments']) is list and {'--offline','--host 127.0.0.1','--no-webui','--no-jinja','-c 32768','-np 1'} <= set(p['runner_required_arguments']), 'Complete qualified owned offline runner profile')
    need(type(p['prefix']) is str and type(p['suffix']) is str and p['model'], 'Explicit template route')
    return p


def turn(request):
    profile = validate_profile(decode(capture('/profile.json')))
    ready = decode(capture('/work/READY.json')); server = ready['server']; server['port'] = PORT
    need(request['context'] == ready['context'] and 1 <= request['turn'] <= 8, 'One owned context/turn')
    end = request['deadline']; need(end <= ready['deadline'], 'Original provider clock')
    prompt = request['prompt']; need(type(prompt) is str, 'Exact full current-context prompt')
    wire = []
    payload = {'model': profile['model'], 'prompt': prompt, 'raw': False, 'stream': False,
               'truncate': False, 'shift': False, 'format': request['format'], 'keep_alive': '1h', 'options': profile['options']}
    rendered = http_call('/api/generate', {**payload, '_debug_render_only': True}, server, end, wire)
    text = profile['prefix'] + prompt + profile['suffix']
    need(rendered.get('_debug_info', {}).get('rendered_template') == text
         and rendered['_debug_info'].get('image_count', 0) == 0, 'Exact donor-qualified rendering, no hidden template/image')
    runner = owned_runner(server, profile)
    loaded = http_call('/api/ps', None, server, end, wire)['models']
    need(len(loaded) == 1 and loaded[0]['digest'] == profile['model_digest'] and loaded[0]['context_length'] == 32768, 'Exact effective loaded model/context')
    tokens = http_call('/tokenize', {'content': text, 'add_special': True, 'parse_special': True, 'with_pieces': False}, runner, end, wire)['tokens']
    need(type(tokens) is list and all(type(x) is int and x >= 0 for x in tokens)
         and len(tokens) + 4096 <= 32768, 'Token-proved full history; no truncation')
    response = http_call('/api/generate', payload, server, end, wire)
    need(response.get('done') is True and response.get('done_reason') == 'stop'
         and response.get('prompt_eval_count') == len(tokens) and type(response.get('eval_count')) is int
         and 0 <= response['eval_count'] <= 4096 and type(response.get('response')) is str, 'Untruncated generation and tokenizer parity')
    need(owned_runner(server, profile) == runner, 'Same model runner through generation')
    action = decode(response['response'].encode(), 1048576)
    return {'schema': 'neural007_model_turn_v1', 'context': request['context'], 'turn': request['turn'],
            'request': pin(encoded(request)), 'profile': pin(encoded(profile)), 'wire': wire, 'action': action,
            'prompt_tokens': len(tokens), 'completion_tokens': response['eval_count'], 'finished': time.monotonic()}


def serve():
    profile = validate_profile(decode(capture('/profile.json')))
    lifecycle = decode(capture('/lifecycle.json')); end = lifecycle['deadline']
    log = open('/work/server.log', 'xb', buffering=0)
    env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/work', 'OLLAMA_HOST': f'127.0.0.1:{PORT}',
           'OLLAMA_MODELS': '/models', 'OLLAMA_NO_CLOUD': '1', 'OLLAMA_NUM_PARALLEL': '1', 'OLLAMA_MAX_LOADED_MODELS': '1'}
    p = subprocess.Popen([profile['binary'], 'serve'], stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                         env=env, close_fds=True, start_new_session=True)
    successful = False
    try:
        server = process(p.pid); server['port'] = PORT
        setup_end = min(end, time.monotonic() + 180)
        while True:
            need(p.poll() is None and time.monotonic() < setup_end, 'Owned service startup deadline')
            need(Path('/work/server.log').stat().st_size <= LOG_CAP, 'Bound complete server log')
            try: listener(PORT, p.pid); break
            except ValueError: time.sleep(.05)
        wire = []
        need(http_call('/api/version', None, server, setup_end, wire)['version'] == profile['version'], 'Exact installed version')
        tags = http_call('/api/tags', None, server, setup_end, wire)['models']
        need(len(tags) == 1 and tags[0]['name'] == profile['model'] and tags[0]['digest'] == profile['model_digest'], 'Only admitted model registry')
        show = http_call('/api/show', {'model': profile['model'], 'verbose': False}, server, setup_end, wire)
        for key in ('template', 'parameters'):
            need(pin(show[key].encode()) == profile[key], 'Exact installed model ' + key)
        need(not show.get('system') and not show.get('messages'), 'No embedded conversation')
        need(http_call('/api/ps', None, server, setup_end, wire)['models'] == [], 'Fresh service with no inherited model state')
        publish(Path('/work/READY.json'), encoded({'context': lifecycle['context'], 'deadline': end, 'server': server, 'wire': wire}))
        while not Path('/requests/CLOSE.json').exists():
            need(p.poll() is None and time.monotonic() < end - 20, 'Provider original clock/no unexpected death')
            need(Path('/work/server.log').stat().st_size <= LOG_CAP, 'Complete log ceiling')
            time.sleep(.05)
        close = decode(capture('/requests/CLOSE.json'))
        need(close['context'] == lifecycle['context'], 'Exact context retirement')
        unload = http_call('/api/generate', {'model': profile['model'], 'keep_alive': 0}, server, end, wire)
        need(http_call('/api/ps', None, server, end, wire)['models'] == [], 'No loaded model remains')
        p.terminate(); need(p.wait(timeout=min(10, max(.001, end - time.monotonic()))) in (0, -signal.SIGTERM), 'Owned server reaped after explicit retirement')
        publish(Path('/work/CLOSED.json'), encoded({'context': lifecycle['context'], 'server_reaped': True, 'model_unloaded': True,
                'wire': wire, 'log': pin(capture('/work/server.log', cap=LOG_CAP)),
                'log_base64': base64.b64encode(capture('/work/server.log', cap=LOG_CAP)).decode(), 'finished': time.monotonic()}))
        # Host captures CLOSED before releasing this trusted idle process.
        while not Path('/requests/ACK.json').exists():
            need(time.monotonic() < end, 'Close observation within original deadline'); time.sleep(.05)
        need(decode(capture('/requests/ACK.json'))['context'] == lifecycle['context'], 'Exact retirement acknowledgment')
        successful = True
    finally:
        if p.poll() is None:
            p.kill(); p.wait(timeout=2)
        log.close()
    need(successful, 'Provider lifecycle complete')


def main():
    # The persistent PID1 entry has no externally selected Python actions.
    serve()


if __name__ == '__main__': main()
