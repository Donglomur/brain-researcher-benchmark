"""Immutable bounded-stderr successor of the selected pair.episode only.

Framing, prompt, sandbox, candidate and owned-child cleanup remain unchanged.
The concurrent reader never retains more than 16 KiB or reads more than 64 KiB.
No source/import-time execution occurs; generated controls use harmless stubs.
"""
from __future__ import annotations

import os
import selectors
import subprocess
import tempfile
import threading
import time

MODE = 'concurrent_bounded_stderr_v1'
RETAIN = 16384
READ = 65536


class StderrCapture:
    def __init__(self, stream, deadline):
        self.stream = stream
        self.deadline = deadline
        self.retained = bytearray()
        self.observed = 0
        self.eof = False
        self.closed = False
        self.overflow = False
        self.error = None
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._drain, name='bounded-episode-stderr', daemon=True)
        self.started = False

    def start(self):
        os.set_blocking(self.stream.fileno(), False)
        self.thread.start()
        self.started = True

    def _drain(self):
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(self.stream.fileno(), selectors.EVENT_READ)
                while not self.stop.is_set():
                    remaining = self.deadline - time.monotonic()
                    if remaining <= 0:
                        self.error = 'stderr_deadline'
                        break
                    if self.observed >= READ:
                        self.error = 'stderr_read_limit'
                        self.overflow = True
                        break
                    if not selector.select(min(0.05, remaining)):
                        continue
                    try:
                        block = os.read(self.stream.fileno(), min(4096, READ - self.observed))
                    except BlockingIOError:
                        continue
                    if not block:
                        self.eof = True
                        break
                    self.observed += len(block)
                    self.retained.extend(block[:max(0, RETAIN - len(self.retained))])
                    if self.observed > RETAIN:
                        self.overflow = True
                        self.error = 'stderr_byte_limit'
                if self.stop.is_set() and not self.eof and self.error is None:
                    self.error = 'stderr_stopped_before_EOF'
        except BaseException as error:
            self.error = 'stderr_reader_' + type(error).__name__
        finally:
            try:
                self.stream.close()
                self.closed = True
            except BaseException as error:
                self.error = 'stderr_close_' + type(error).__name__

    def finish(self, deadline):
        if self.started:
            self.thread.join(max(0, deadline - time.monotonic()))
        if self.started and self.thread.is_alive():
            self.stop.set()
            self.thread.join(max(0, deadline - time.monotonic()))
        if not self.started:
            try:
                self.stream.close()
                self.closed = True
            except OSError:
                pass
            self.error = self.error or 'stderr_reader_not_started'
        joined = self.started and not self.thread.is_alive()
        # An unjoined daemon is explicitly unresolved, never treated as closed.
        return {'eof_observed': self.eof, 'reader_joined': joined, 'closed': self.closed,
                'overflow': self.overflow, 'error': self.error,
                'observed_bytes': self.observed, 'retained_bytes': len(self.retained)}


def capture_closed(value):
    # Resource custody is separate from complete diagnostic evidence. A known
    # capped prefix may close safely without EOF and must still fail delivery.
    return value.get('reader_joined') is True and value.get('closed') is True


def episode(pair, context, condition, output, client, interpreter, limits, campaign_deadline,
            modules, budget, *, generated_protocol_only=False):
    """Same selected episode seam, with concurrent bounded stderr custody."""
    started = time.monotonic(); output = pair.ordinary_path(output); output.mkdir(mode=0o700)
    frame = pair.context_frame(context, condition)
    work_end = min(started + limits['episode_work_seconds'], campaign_deadline - limits['episode_cleanup_seconds'])
    cleanup_end = min(started + limits['episode_work_seconds'] + limits['episode_cleanup_seconds'], campaign_deadline)
    proc = observer = capture = None; cleanup = stderr_state = None
    incoming = outgoing = b''; response = None
    eof = False; extra = b''; reason = None; normal_exit = False
    profile = None if generated_protocol_only else modules['wire'].sandbox_profile(client)
    if profile is not None:
        pair.write(output / 'sandbox.sb', profile.encode(), budget)
    try:
        pair.need(time.monotonic() < work_end, 'Campaign deadline before dispatch')
        modules['owned'].preflight()
        with tempfile.TemporaryDirectory(prefix='erp-full6400-episode-') as cwd:
            command = [str(interpreter), '-I', '-S', '-B', str(client)]
            if profile is not None:
                command = ['/usr/bin/sandbox-exec', '-p', profile, *command]
            proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, cwd=cwd, env={'LANG': 'C', 'LC_ALL': 'C'},
                                    close_fds=True, start_new_session=True)
            observer = modules['owned'].ExitObserver(proc)
            capture = StderrCapture(proc.stderr, cleanup_end)
            capture.start()
            os.set_blocking(proc.stdin.fileno(), False); os.set_blocking(proc.stdout.fileno(), False)
            try:
                modules['wire'].write_frame(proc.stdin.fileno(), frame, work_end); incoming = frame
            except modules['wire'].WireFailure as exc:
                incoming = exc.captured; raise
            proc.stdin.close()
            try:
                outgoing = modules['wire'].read_frame(proc.stdout.fileno(), work_end)
            except modules['wire'].WireFailure as exc:
                outgoing = exc.captured; raise
            response = outgoing[pair.PREFIX.size:].decode('utf-8')
            modules['consumer'].parse_response(response, context['trial_id'])
            normal_exit = observer.wait(min(work_end, time.monotonic() + 2))
            pair.need(normal_exit, 'Participant did not exit after first response')
    except BaseException as exc:
        reason = getattr(exc, 'reason', type(exc).__name__)
    finally:
        if proc is not None:
            try:
                cleanup = modules['owned'].stop_and_reap(proc, observer, cleanup_end)
            except BaseException as cleanup_error:
                cleanup = {'cleanup_complete': False, 'reaped': False,
                           'group_absence_observed': False, 'pid': proc.pid,
                           'error': type(cleanup_error).__name__, 'returncode': proc.returncode}
                reason = 'owned_cleanup_exception'
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(proc.stdout.fileno(), selectors.EVENT_READ)
                    ready = selector.select(max(0, cleanup_end - time.monotonic()))
                    if ready:
                        extra = os.read(proc.stdout.fileno(), 1); eof = extra == b''
            except (OSError, ValueError):
                eof = False
            for stream in (proc.stdin, proc.stdout):
                try:
                    if not stream.closed:
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
            except BaseException as capture_error:
                stderr_state = {'eof_observed': False, 'reader_joined': False, 'closed': False,
                                'overflow': False, 'error': 'stderr_finish_' + type(capture_error).__name__,
                                'observed_bytes': 0, 'retained_bytes': 0}
            if not cleanup.get('cleanup_complete') or not eof or not capture_closed(stderr_state):
                reason = 'owned_closure_or_capture_unverified'
            elif (stderr_state['overflow'] or stderr_state['error'] is not None or
                  stderr_state['eof_observed'] is not True):
                reason = stderr_state['error'] or 'stderr_incomplete'
            if proc.returncode != 0:
                reason = reason or 'participant_exit_failure'
        if proc is None:
            reason = reason or 'not_launched'
        if extra:
            reason = 'extra_stdout_after_first_response'
        retained = bytes(capture.retained[:RETAIN]) if capture is not None else b''
        if stderr_state is not None:
            stderr_state['retained_bytes'] = len(retained)
            stderr_state['file'] = pair.pin(retained)
            stderr_state['retained_limit'] = RETAIN
            stderr_state['read_limit'] = READ
        envelope = {key: context[key] for key in ('trial_id', 'condition', 'context_sha256')}
        envelope.update(status='ok' if reason is None else 'error',
                        response=response if reason is None else None, error=reason)
        receipt = {'schema': 'erp-full6400-owned-episode-v1', 'status': envelope['status'],
                   'trial_id': context['trial_id'], 'condition': condition,
                   'context_sha256': context['context_sha256'], 'pid': proc.pid if proc else None,
                   'returncode': proc.returncode if proc else None, 'owned_cleanup': cleanup,
                   'stdout_EOF_observed': eof, 'trailing_byte': pair.pin(extra),
                   'first_response_immutable': True, 'normal_exit_observed': normal_exit,
                   'generated_protocol_only': generated_protocol_only,
                   'input': pair.pin(incoming), 'output': pair.pin(outgoing), 'attempt': pair.pin(pair.encode(envelope)),
                   'elapsed_seconds': time.monotonic() - started,
                   'provider_context_qualified': False, 'provider_tool_policy_qualified': False,
                   'escaped_descendant_containment_qualified': False, 'private_target_reads': 0,
                   'diagnostic_mode': MODE, 'stderr_capture': stderr_state}
        pair.write(output / 'INPUT.bin', incoming, budget); pair.write(output / 'OUTPUT.bin', outgoing, budget)
        pair.write(output / 'STDERR.bin', retained, budget)
        pair.write(output / 'ATTEMPT.json', pair.encode(envelope), budget)
        pair.write(output / 'END.json', pair.encode(receipt), budget)
    return envelope, receipt
