"""One explicitly selected provider episode with owned, bounded raw custody.

The trusted study operator supplies already authenticated sources, configuration,
and a private credential bytearray. There is no import-time execution, retry,
target access, provider qualification, or process-containment claim. A completed
receipt is evidence for the separate raw-capture admission, not its replacement.
"""
from __future__ import annotations

import os
from pathlib import Path
import selectors
import subprocess
import time

STDERR_RETAIN = 16384
STDERR_READ = 65536
METADATA_CAP = 16384
CREDENTIAL_CAP = 4096


def provider_episode(pair, context, output, contract, modules, budget,
                     campaign_deadline, credential: bytearray):
    """Launch one pinned client; retain its first frame and close before EOF.

    Child custody allocation is charged before launch. Parent-owned captures are
    charged by exact create-only writes. Failure prefixes remain in place and
    cannot be admitted as a completed episode. Credentials enter only a private
    inherited pipe; the caller retains responsibility for clearing the campaign
    bytearray after its last explicitly selected episode.
    """
    started = time.monotonic()
    limits = contract['limits']
    work_end = min(started + limits['episode_work_seconds'],
                   campaign_deadline - limits['episode_cleanup_seconds'])
    cleanup_end = min(started + limits['episode_work_seconds'] +
                      limits['episode_cleanup_seconds'], campaign_deadline)
    output = pair.ordinary_path(output)
    pair.need(not output.exists() and output.parent.is_dir(), 'Fresh provider episode output')
    output.mkdir(mode=0o700)
    custody_path = output / 'custody'
    custody_path.mkdir(mode=0o700)
    os.chmod(custody_path, 0o700)

    proc = observer = capture = None
    cleanup = stderr_state = None
    owned_fds = set()
    incoming = outgoing = config_body = b''
    extra = b''
    response = None
    reason = None
    normal_exit = eof = False
    child_write_reserve = child_read_reserve = 0

    def close_fd(fd):
        if fd in owned_fds:
            owned_fds.remove(fd)
            os.close(fd)

    try:
        pair.need(type(context) is dict and set(context) == {
            'trial_id', 'condition', 'prompt', 'context_sha256'} and
            context['condition'] == pair.CONDITIONS[0], 'One full32 direct context required')
        pair.need(type(credential) is bytearray and 1 <= len(credential) <= CREDENTIAL_CAP and
                  all(33 <= value <= 126 for value in credential), 'Private bounded credential required')
        prompt = context['prompt'].encode('utf-8')
        pair.need(0 < len(prompt) <= pair.PROMPT_CAP and
                  pair.pin(prompt)['sha256'] == context['context_sha256'] and
                  modules['bridge'].query_identity(context['prompt']) == context['trial_id'],
                  'Complete frozen full32 context required')
        frame = pair.PREFIX.pack(len(prompt)) + prompt
        config = pair.provider_configuration(context, contract, modules['bridge'], work_end)
        config_body = pair.encode(config)
        pair.need(len(config_body) <= METADATA_CAP, 'Bounded provider configuration')
        request = modules['bridge'].request_body(context['prompt'], contract['provider']['model'],
                                                  contract['provider']['max_output_tokens'])
        pair.need(0 < len(request) <= modules['http_client'].REQUEST_CAP,
                  'Bounded canonical provider request')
        source = contract['adapter_sources']['client']
        client = pair.ordinary_path(modules['root'] / source['path'])
        pair.read(client, 131072, {key: source[key] for key in ('bytes', 'sha256')}, budget)
        pair.need(client.parent == Path(modules['bridge'].__file__).parent,
                  'Client and bridge must be frozen siblings')
        # The pinned child emits exactly the canonical request (or its prefix),
        # at most RESPONSE_CAP+1 bytes, and two <=16KiB metadata records.
        child_write_reserve = len(request) + pair.PROVIDER_CAP + 1 + 2 * METADATA_CAP
        child_read_reserve = (sum(contract['adapter_sources'][name]['bytes']
                                  for name in ('client', 'http_client', 'bridge', 'consumer')) +
                              len(config_body) + len(credential) + len(frame) +
                              pair.PROVIDER_CAP + 1 + pair.RESPONSE_CAP + 5 + STDERR_READ)
        budget.output(child_write_reserve)
        budget.input(child_read_reserve)
        pair.need(budget.written + len(config_body) + len(frame) + pair.RESPONSE_CAP + 4 +
                  STDERR_RETAIN + METADATA_CAP <= budget.write_limit,
                  'Parent capture allocation before provider launch')
        pair.write(output / 'CONFIG.json', config_body, budget)
        modules['owned'].preflight()
        pair.need(time.monotonic() + modules['http_client'].CUSTODY_SECONDS < work_end,
                  'Selected provider deadline before dispatch')
        config_read, config_write = os.pipe()
        owned_fds.update((config_read, config_write))
        token_read, token_write = os.pipe()
        owned_fds.update((token_read, token_write))
        custody_fd = os.open(custody_path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        owned_fds.add(custody_fd)
        # Only descriptor numbers enter argv; the environment is replaced. No
        # participant code or private-label paths are passed to the trusted client.
        command = [contract['interpreter']['path'], '-I', '-S', '-B', str(client),
                   '--config-fd', str(config_read), '--credential-fd', str(token_read),
                   '--custody-fd', str(custody_fd)]
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, cwd=output,
                                env={'LANG': 'C', 'LC_ALL': 'C'}, close_fds=True,
                                pass_fds=(config_read, token_read, custody_fd),
                                start_new_session=True)
        # Construct the non-reaping observer before any other process operation.
        observer = modules['owned'].ExitObserver(proc)
        for fd in (config_read, token_read, custody_fd):
            close_fd(fd)
        capture = modules['episode'].StderrCapture(proc.stderr, cleanup_end)
        capture.start()
        for fd in (config_write, token_write, proc.stdin.fileno(), proc.stdout.fileno()):
            os.set_blocking(fd, False)
        modules['wire'].write_frame(config_write, config_body, work_end)
        close_fd(config_write)
        # Do not retain WireFailure.captured from the credential/config pipes.
        modules['wire'].write_frame(token_write, credential, work_end)
        close_fd(token_write)
        try:
            modules['wire'].write_frame(proc.stdin.fileno(), frame, work_end)
            incoming = frame
        except modules['wire'].WireFailure as error:
            incoming = error.captured
            raise
        proc.stdin.close()
        try:
            outgoing = modules['wire'].read_frame(proc.stdout.fileno(), work_end)
        except modules['wire'].WireFailure as error:
            outgoing = error.captured
            raise
        response = outgoing[pair.PREFIX.size:].decode('utf-8')
        modules['consumer'].parse_response(response, context['trial_id'])
        normal_exit = observer.wait(min(work_end, time.monotonic() + 2))
        pair.need(normal_exit, 'Provider child did not exit after its first response')
    except BaseException as error:
        # Exception text may contain credential/network data; never retain it.
        reason = getattr(error, 'reason', type(error).__name__)
    finally:
        if proc is not None:
            try:
                cleanup = modules['owned'].stop_and_reap(proc, observer, cleanup_end)
            except BaseException as error:
                cleanup = {'pid': proc.pid, 'cleanup_complete': False, 'reaped': False,
                           'group_absence_observed': False, 'returncode': proc.returncode,
                           'error': type(error).__name__}
                reason = 'owned_cleanup_exception'
            # Read trailing data only after the sole owned stop/reap attempt.
            # The original first frame remains untouched, including on failure.
            try:
                os.set_blocking(proc.stdout.fileno(), False)
                with selectors.DefaultSelector() as selector:
                    selector.register(proc.stdout.fileno(), selectors.EVENT_READ)
                    if selector.select(max(0, cleanup_end - time.monotonic())):
                        extra = os.read(proc.stdout.fileno(), 1)
                        eof = extra == b''
            except (OSError, ValueError):
                eof = False
            for stream in (proc.stdin, proc.stdout):
                try:
                    if stream is not None and not stream.closed:
                        stream.close()
                except OSError:
                    reason = 'owned_pipe_close_failure'
            try:
                if capture is not None:
                    stderr_state = capture.finish(cleanup_end)
                else:
                    proc.stderr.close()
                    stderr_state = {'eof_observed': False, 'reader_joined': False, 'closed': True,
                                    'overflow': False, 'error': 'stderr_reader_not_started',
                                    'observed_bytes': 0, 'retained_bytes': 0}
            except BaseException as error:
                stderr_state = {'eof_observed': False, 'reader_joined': False, 'closed': False,
                                'overflow': False, 'error': 'stderr_finish_' + type(error).__name__,
                                'observed_bytes': 0, 'retained_bytes': 0}
            if (not cleanup.get('cleanup_complete') or not eof or
                    not modules['episode'].capture_closed(stderr_state)):
                reason = 'owned_closure_or_capture_unverified'
            elif (stderr_state['overflow'] or stderr_state['error'] is not None or
                  stderr_state['eof_observed'] is not True):
                reason = stderr_state['error'] or 'stderr_incomplete'
            if proc.returncode != 0:
                reason = reason or 'provider_child_exit_failure'
        else:
            reason = reason or 'not_launched'
        for fd in tuple(owned_fds):
            try:
                close_fd(fd)
            except OSError:
                reason = 'owned_descriptor_close_failure'
        if extra:
            reason = 'extra_stdout_after_first_response'
        retained = bytes(capture.retained[:STDERR_RETAIN]) if capture is not None else b''
        if stderr_state is not None:
            stderr_state['retained_bytes'] = len(retained)
            stderr_state['file'] = pair.pin(retained)
            stderr_state['retained_limit'] = STDERR_RETAIN
            stderr_state['read_limit'] = STDERR_READ
        # A pre-launch failure may occur before the configuration write. Keep a
        # bounded prefix/empty capture; separate admission will reject it.
        if not (output / 'CONFIG.json').exists():
            pair.write(output / 'CONFIG.json', config_body, budget)
        pair.write(output / 'INPUT.bin', incoming, budget)
        pair.write(output / 'OUTPUT.bin', outgoing, budget)
        pair.write(output / 'STDERR.bin', retained, budget)
        finished = time.monotonic()
        if finished > cleanup_end:
            reason = reason or 'selected_episode_deadline'
        envelope = {key: context[key] for key in ('trial_id', 'condition', 'context_sha256')}
        envelope.update(status='ok' if reason is None else 'error',
                        response=response if reason is None else None, error=reason)
        end = {'schema': 'erp_full32_provider_owned_episode_v1',
               'status': 'closed_first_answer' if reason is None else 'failed_unadmitted_episode',
               'error_type': reason, 'trial_id': context['trial_id'], 'condition': context['condition'],
               'context_sha256': context['context_sha256'], 'pid': proc.pid if proc else None,
               'returncode': proc.returncode if proc else None, 'owned_cleanup': cleanup,
               'normal_exit_observed': normal_exit, 'stdout_EOF_observed': eof,
               'stderr_capture': stderr_state, 'config': pair.pin(config_body),
               'input': pair.pin(incoming), 'output': pair.pin(outgoing), 'stderr': pair.pin(retained),
               'trailing_byte': pair.pin(extra), 'trailing_byte_hex': extra.hex(),
               'first_response_immutable': True, 'automatic_retry': False,
               'started_monotonic': started, 'finished_monotonic': finished,
               'elapsed_seconds': finished - started,
               'child_custody_write_bytes_reserved': child_write_reserve,
               'child_and_pipe_read_bytes_reserved': child_read_reserve,
               'provider_context_qualified': False, 'provider_tool_policy_qualified': False,
               'escaped_descendant_containment_qualified': False,
               'outer_campaign_and_resource_qualification_required': True,
               'private_target_reads': 0, 'scoring_performed': False}
        end_body = pair.encode(end)
        pair.need(len(end_body) <= METADATA_CAP, 'Bounded provider closure receipt')
        pair.write(output / 'END.json', end_body, budget)
    return envelope, end
