"""Trusted N077 image-provider client using the unchanged bounded HTTPS Sender.

Credentials arrive by inherited pipe. Every request repeats the complete local
query history. Oversize histories fail; no image or earlier turn is dropped.
"""
from pathlib import Path
import hashlib
import http.client
import importlib.util
import json
import math
import os
import re
import selectors
import stat
import sys
import time

HERE = Path(__file__).resolve().parent
ORIGINAL_SENDER = {'bytes': 19747, 'sha256': '299d3effae6db940cf2dcd8498a2b43af0b36978e9f892cdd3b8af39391d9aef'}
CONFIG_CAP = 32768
CONFIG_KEYS = {'schema', 'model', 'max_output_tokens', 'deadline', 'trial_id',
               'implementations_root', 'source_bindings', 'bridge_path', 'bridge_pin',
               'sender_path', 'sender_pin', 'codec_path', 'codec_pin',
               'max_request_bytes', 'max_requests', 'max_query_request_bytes', 'max_query_response_bytes'}


def need(value, message):
    if not value:
        raise ValueError(message)


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def pairs(items):
    result = {}
    for key, value in items:
        need(key not in result, 'Duplicate configuration key')
        result[key] = value
    return result


def decode(raw):
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite configuration')))


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def arguments(argv):
    need(len(argv) == 6, 'Three explicit inherited descriptors required')
    result = {}
    for name, value in zip(argv[::2], argv[1::2]):
        need(name in ('--credential-fd', '--config-fd', '--custody-fd') and name not in result
             and value.isascii() and value.isdecimal(), 'Descriptor argument refused')
        result[name] = int(value)
    need(len(set(result.values())) == 3 and all(3 <= item <= 1048576 for item in result.values()), 'Distinct descriptors required')
    return result


def bootstrap_config(fd, deadline):
    """Finite bootstrap before the authenticated existing helper is available."""
    info = os.fstat(fd)
    need(stat.S_ISFIFO(info.st_mode) and info.st_uid == os.geteuid(), 'Owned configuration pipe required')
    body = bytearray()
    with selectors.DefaultSelector() as selector:
        selector.register(fd, selectors.EVENT_READ)
        while True:
            remaining = deadline - time.monotonic()
            need(remaining > 0 and selector.select(remaining), 'Configuration bootstrap deadline')
            piece = os.read(fd, min(4096, CONFIG_CAP + 1 - len(body)))
            if not piece:
                return bytes(body)
            body.extend(piece)
            need(len(body) <= CONFIG_CAP, 'Configuration exceeds bound')


def source(path, expected):
    """Capture source before execution, without ambient sys.path imports."""
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts and not any(item.is_symlink() for item in (path, *path.parents)),
         'Ordinary absolute source path required')
    need(type(expected) is dict and set(expected) == {'bytes', 'sha256'}
         and type(expected['bytes']) is int and 0 < expected['bytes'] <= 131072
         and type(expected['sha256']) is str and re.fullmatch(r'[0-9a-f]{64}', expected['sha256']), 'Bounded source pin required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == expected['bytes'], 'Exact ordinary source extent')
        body = stream.read(expected['bytes'] + 1)
        need(fields(before) == fields(os.fstat(stream.fileno())) == fields(path.lstat()) and pin(body) == expected,
             'Source changed or identity mismatched')
    spec = importlib.util.spec_from_loader('neural077_visual_' + expected['sha256'][:16], loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


def configuration(raw):
    need(type(raw) is bytes and 0 < len(raw) <= CONFIG_CAP, 'Bounded configuration required')
    value = decode(raw)
    need(type(value) is dict and set(value) == CONFIG_KEYS and value['schema'] == 'neural077_visual_provider_client_v1',
         'Exact visual provider configuration required')
    need(type(value['model']) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}', value['model']), 'Explicit model identity')
    need(type(value['max_output_tokens']) is int and 1 <= value['max_output_tokens'] <= 32768, 'Token allocation')
    need(type(value['deadline']) in (int, float) and math.isfinite(value['deadline'])
         and 2 < value['deadline'] - time.monotonic() <= 3600, 'Finite original query deadline')
    need(type(value['trial_id']) is str and re.fullmatch(r'development-00[12]-[0-9a-f]{24}', value['trial_id']), 'Exact original query identity')
    for name, maximum in (('max_request_bytes', 8388608), ('max_requests', 127),
                          ('max_query_request_bytes', 512 * 1024 * 1024), ('max_query_response_bytes', 128 * 1024 * 1024)):
        need(type(value[name]) is int and 1 <= value[name] <= maximum, 'Finite configured byte/action cap')
    need(value['max_query_request_bytes'] >= value['max_request_bytes'], 'Cumulative request cap smaller than single request cap')
    root = Path(value['implementations_root'])
    need(root.is_absolute() and '..' not in root.parts, 'Explicit original implementations root')
    need(type(value['source_bindings']) is dict
         and value['source_bindings'].get('waveform-provider-v1/client.py') == ORIGINAL_SENDER
         and value['sender_pin'] == ORIGINAL_SENDER
         and Path(value['sender_path']) == root / 'waveform-provider-v1/client.py', 'Unchanged original sender required')
    need(Path(value['bridge_path']) == HERE / 'visual_bridge.py' and Path(value['codec_path']) == HERE / 'transfer_png.py',
         'This component owns the only bridge and lossless codec paths')
    return value


def write_end(directory, value):
    raw = encoded(value)
    need(len(raw) <= 32768, 'Bounded final custody receipt')
    fd = os.open('CLIENT_END.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.fsync(directory)


def decoded_echo(value, credential):
    """Check JSON-decoded strings, including a finalize's decoded response."""
    if type(value) is str:
        return credential in value
    if type(value) is list:
        return any(decoded_echo(item, credential) for item in value)
    if type(value) is dict:
        return any(decoded_echo(key, credential) or decoded_echo(item, credential)
                   for key, item in value.items())
    return False


def serve(config, config_pin, credential, directory, original, bridge, codec, alarm,
          input_stream, output_stream, *, http_factory=http.client.HTTPSConnection):
    """One query, one complete history, a fresh original Sender per action."""
    info = os.fstat(directory)
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o700
         and os.listdir(directory) == [], 'Fresh private query custody required')
    turns = request_bytes = response_bytes = 0
    response_upper = False
    ids = []
    totals = {name: 0 for name in ('input_tokens', 'output_tokens', 'total_tokens')}
    initial = terminal = final_response = None
    finalized = success = False
    error_type = None
    try:
        alarm.arm(config['deadline'] - original.CUSTODY_SECONDS)
        header, png, frame = bridge.read_frame(input_stream)
        initial = bridge.pin(frame)
        history, mapping = bridge.first_frame(header, png, config['trial_id'], codec.encode_transport_image)
        declared = header['limits']
        need(type(declared.get('max_actions')) is int and 2 <= declared['max_actions'] <= 128
             and config['max_requests'] <= declared['max_actions'] - 1, 'Viewer/provider action allocation mismatch')
        prompt = history[0]['content'][0]['text']
        while True:
            original.remaining(config['deadline'] - original.CUSTODY_SECONDS)
            need(turns < config['max_requests'] and not finalized, 'Query request limit or terminal finalize')
            adapter = bridge.SenderAdapter(history, config['model'], config['max_output_tokens'],
                                            config['max_request_bytes'], config['trial_id'])
            request = adapter.request
            need(request_bytes + len(request) <= config['max_query_request_bytes'], 'Cumulative query request cap; no history truncation')
            remaining_response = config['max_query_response_bytes'] - response_bytes
            need(remaining_response > 1, 'Cumulative query response cap')
            # Failed sends can discard a literal credential-echo suffix, so
            # reserve the complete bounded read, including its overflow byte.
            response_cap = min(original.RESPONSE_CAP, remaining_response - 1)
            name = f'{turns:03d}'
            os.mkdir(name, 0o700, dir_fd=directory)
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            try:
                custody = original.Custody(fd, config_pin, config['deadline'])
                sender_cfg = {'model': config['model'], 'max_output_tokens': config['max_output_tokens'],
                              'deadline': config['deadline'], 'trial_id': config['trial_id'],
                              'context_sha256': bridge.pin(prompt.encode())['sha256']}
                sender = original.Sender(sender_cfg, config_pin, credential, custody, adapter, alarm,
                                         http_factory=http_factory, response_cap=response_cap)
                receipt = {'schema': 'neural077_visual_provider_bridge_v1', 'condition': 'four_demo',
                           'config_pin': config_pin, 'turn': turns, 'status': 'failed_no_action',
                           'frame': bridge.pin(frame), 'history': bridge.pin(bridge.encode(history)), 'image_mapping': mapping,
                           'request': bridge.pin(request), 'response': None, 'action': None,
                           'provider_response_id': None, 'model': config['model'], 'usage': None,
                           'request_bytes_total': request_bytes + len(request), 'response_bytes_total': response_bytes,
                           'response_charge_is_upper_bound': False,
                           'retry_count': 0, 'provider_context_qualified': False, 'provider_capacity_qualified': False,
                           'scientific_qualification': False}
                request_bytes += len(request)
                turns += 1
                send_complete = False
            except BaseException:
                os.close(fd)
                raise
            try:
                raw = sender(request)
                send_complete = True
                response_bytes += len(raw)
                receipt['response'] = bridge.pin(raw)
                receipt['response_bytes_total'] = response_bytes
                action, metadata = bridge.completed_action(raw, config['model'], config['max_output_tokens'])
                # Guard decoded values before retaining/outputting any new
                # action or metadata. Inherited raw capture is literal-only.
                secret = credential.encode('ascii')
                need(secret not in action and secret not in bridge.encode(metadata), 'Decoded provider credential echo')
                try:
                    action_value = bridge.decode(action)
                except (ValueError, UnicodeError, TypeError, RecursionError, OverflowError):
                    action_value = None  # The original viewer records this malformed action.
                need(not decoded_echo(action_value, credential), 'Nested decoded action credential echo')
                need(metadata['provider_response_id'] not in ids, 'Provider response identity reused within query')
                ids.append(metadata['provider_response_id'])
                for key in totals:
                    totals[key] += metadata['usage'][key]
                receipt.update(status='complete_unscored_action', action=bridge.pin(action), **metadata)
            except BaseException:
                if not send_complete:
                    response_bytes += response_cap + 1
                    response_upper = True
                    receipt['response_bytes_total'] = response_bytes
                    receipt['response_charge_is_upper_bound'] = True
                    if 'HTTP.json' in custody.created:
                        hfd = os.open('HTTP.json', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
                        with os.fdopen(hfd, 'rb') as handle:
                            http = original.decode(handle.read(16385))
                        receipt['response'] = http['response']
                raise
            finally:
                alarm.arm(config['deadline'])
                sender.credential = None
                try:
                    need(credential.encode('ascii') not in bridge.encode(receipt), 'Custody credential echo')
                    custody.json('BRIDGE.json', receipt)
                finally:
                    os.close(fd)
            alarm.arm(config['deadline'] - original.CUSTODY_SECONDS)
            final = bridge.typed_finalize(action)
            if final is not None:
                finalized = True
                final_response = bridge.pin(final)
            bridge.write_action(output_stream, action)
            header, png, frame = bridge.read_frame(input_stream)
            bridge.projection(header, png)
            if finalized:
                terminal = bridge.pin(frame)
                need(header['status'] in ('valid_unscored', 'invalid_response')
                     and header['response_sha256'] == final_response['sha256'] and header['terminal'] is True,
                     'First finalize was not bound to the exact terminal viewer response')
                need(header['status'] == 'valid_unscored', 'Original first scalar response was invalid')
                success = True
                break
            need(header['status'] in ('rendered', 'rejected'), 'Unexpected terminal viewer state')
            history, mapping = bridge.append_frame(history, action, header, png, codec.encode_transport_image)
    except BaseException as error:
        error_type = type(error).__name__
    finally:
        alarm.arm(config['deadline'])
        value = {'schema': 'neural077_visual_provider_client_end_v1', 'condition': 'four_demo', 'config_pin': config_pin,
                 'status': 'closed_first_final' if success else 'failed_no_admission', 'turns': turns,
                 'request_bytes': request_bytes, 'response_bytes': response_bytes,
                 'response_charge_contains_upper_bound': response_upper,
                 'provider_response_ids': ids, 'usage': totals,
                 'initial_frame': initial, 'terminal_frame': terminal, 'final_response': final_response,
                 'first_finalize_terminal': finalized, 'no_further_request_after_finalize': True,
                 'decoded_credential_persisted': False, 'raw_response_literal_guard_only': True,
                 'remote_context_qualified': False, 'provider_capacity_qualified': False,
                 'scientific_qualification': False, 'error_type': error_type}
        write_end(directory, value)
    return success


def main(argv=None, *, http_factory=http.client.HTTPSConnection, input_stream=None, output_stream=None):
    started = time.monotonic()
    fds = {}
    alarm = None
    token = None
    success = False
    try:
        fds = arguments(sys.argv[1:] if argv is None else argv)
        raw = bootstrap_config(fds['--config-fd'], started + 5)
        os.close(fds.pop('--config-fd'))
        config = configuration(raw)
        original = source(config['sender_path'], config['sender_pin'])
        bridge = source(config['bridge_path'], config['bridge_pin'])
        codec = source(config['codec_path'], config['codec_pin'])
        alarm = original.Alarm(config['deadline'] - original.CUSTODY_SECONDS)
        token = original.pipe_body(fds['--credential-fd'], original.CREDENTIAL_CAP,
                                   config['deadline'] - original.CUSTODY_SECONDS)
        os.close(fds.pop('--credential-fd'))
        need(1 <= len(token) <= original.CREDENTIAL_CAP and all(33 <= byte <= 126 for byte in token), 'Credential pipe refused')
        success = serve(config, pin(raw), token.decode('ascii'), fds['--custody-fd'], original, bridge, codec, alarm,
                        sys.stdin.buffer if input_stream is None else input_stream,
                        sys.stdout.buffer if output_stream is None else output_stream, http_factory=http_factory)
    except BaseException:
        success = False
    finally:
        token = None
        if alarm is not None:
            alarm.close()
        for fd in fds.values():
            try:
                os.close(fd)
            except OSError:
                success = False
    return 0 if success else 3


if __name__ == '__main__':
    raise SystemExit(main())
