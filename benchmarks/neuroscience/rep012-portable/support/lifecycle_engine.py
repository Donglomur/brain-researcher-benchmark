"""Exact selected capture definitions; globals supplied only by controller.engine_class.
The constructor environment is inert until the paired controller replaces it.
"""

def need(ok, message):
    if not ok:
        raise ValueError(message)

def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()

def short(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}

class Engine:
    """Bounded selectors retain command prefixes before semantic assertions.

    Children inherit the v4 controller group. They never create an escaping
    session/group. The direct child is waited; outer shared-v4 proves the group.
    """
    def __init__(self, out, budget, end, recovery=False, final_recovery=False):
        self.out = Path(out); self.budget = budget; self.end = end; self.recovery = recovery
        self.final_recovery = final_recovery
        self.sequence = 0; self.raw = 0; self.metadata = 0; self.active = None
        self.all_cli_reaped = True
        self.env = {}  # Paired Condition replaces this before any command.

    def write(self, name, value, cap=131072):
        body = encode(value)
        return self.write_bytes(name, body, cap)

    def write_bytes(self, name, body, cap):
        ceiling = FINAL_RECOVERY_METADATA_LIMIT if self.final_recovery else (METADATA_LIMIT if self.recovery else WORK_METADATA_LIMIT)
        need(type(body) is bytes and len(body) <= cap and self.metadata + len(body) <= ceiling, 'Metadata evidence preserves normal cleanup reserve')
        path = self.out / name; self.budget.write(path, body, receipt=True, mode=0o444)
        self.metadata += len(body)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        fd = os.open(self.out, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return {'path': str(path.relative_to(ROOT)), **short(body)}

    def run(self, argv, timeout=3, cap=65536):
        need(self.active is None and self.all_cli_reaped, 'No unresolved prior CLI child')
        calls = FINAL_RECOVERY_COMMAND_LIMIT if self.final_recovery else (COMMAND_LIMIT if self.recovery else WORK_COMMAND_LIMIT)
        need(self.sequence < calls, 'Finite command count')
        need(type(cap) is int and 0 < cap <= CAPTURE_LIMIT, 'Bounded command reply cap')
        started = time.monotonic(); until = min(self.end - 1.25, started + timeout)
        need(until > started, 'Positive raw remaining deadline, retaining child-reap time')
        self.sequence += 1; number = self.sequence
        caps = {'stdout': cap, 'stderr': min(cap, 65536)}
        raw_ceiling = FINAL_RECOVERY_RAW_LIMIT if self.final_recovery else (RAW_LIMIT if self.recovery else WORK_RAW_LIMIT)
        need(self.raw + sum(caps.values()) <= raw_ceiling, 'Raw retained command cap')
        self.budget.check(sum(caps.values()) + 32768, receipt=True)
        self.write(f'command-{number:03d}-intent.json', {'argv': [DOCKER, *argv],
                   'deadline_monotonic': until, 'stream_caps': caps, 'shared_owned_host_group': os.getpgrp()})
        event = {'argv': [DOCKER, *argv], 'returncode': None, 'cli_reaped': False,
                 'capture_complete': False, 'truncated': False, 'error': None, 'streams': {}}
        buffers = {key: bytearray() for key in caps}; handles = {}; selector = selectors.DefaultSelector(); failure = None
        try:
            for key in caps:
                fd = os.open(self.out / f'command-{number:03d}-{key}.bin', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                handles[key] = os.fdopen(fd, 'wb')
            need(time.monotonic() < until, 'Command time remains after intent publication')
            self.all_cli_reaped = False
            self.active = subprocess.Popen([DOCKER, *argv], env=self.env, stdin=subprocess.DEVNULL,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=False)
            event['pid'] = self.active.pid
            self.write(f'command-{number:03d}-owner.json', {'pid': self.active.pid, 'shared_owned_host_group': os.getpgrp(), 'direct_child_handle': True})
            for key, stream in (('stdout', self.active.stdout), ('stderr', self.active.stderr)):
                os.set_blocking(stream.fileno(), False); selector.register(stream, selectors.EVENT_READ, key)
            while selector.get_map():
                remaining = until - time.monotonic(); need(remaining > 0, 'Bounded CLI stream deadline')
                for selected, _ in selector.select(min(.05, remaining)):
                    body = os.read(selected.fileobj.fileno(), 65536)
                    if not body:
                        selector.unregister(selected.fileobj); continue
                    key = selected.data; room = caps[key] - len(buffers[key]); prefix = body[:room]
                    if prefix:
                        buffers[key].extend(prefix); handles[key].write(prefix); handles[key].flush(); os.fsync(handles[key].fileno())
                    if len(body) > room:
                        event['truncated'] = True; raise ValueError('CLI stream exceeded retained prefix cap')
            remaining = until - time.monotonic(); need(remaining > 0, 'Remaining wait deadline')
            event['returncode'] = self.active.wait(timeout=remaining)
            event['cli_reaped'] = True; event['capture_complete'] = True
        except BaseException as error:
            failure = error; event['error'] = type(error).__name__ + ': ' + str(error)[:512]
        finally:
            selector.close()
            if self.active is not None:
                try:
                    if self.active.poll() is None:
                        self.active.kill()
                    remaining = self.end - time.monotonic(); need(remaining > 0, 'Child cleanup remains within phase deadline')
                    event['returncode'] = self.active.wait(timeout=min(1, remaining))
                    event['cli_reaped'] = True; self.all_cli_reaped = True
                except BaseException as error:
                    event['reap_error'] = type(error).__name__ + ': ' + str(error)[:256]
                for stream in (self.active.stdout, self.active.stderr):
                    stream.close()
                if event['cli_reaped']:
                    self.active = None
            # A Popen exception after launch was attempted has no retained child
            # handle. Leave all_cli_reaped false; the outer owned-group proof is
            # required before a fresh final-recovery Engine may run.
            for key, stream in handles.items():
                stream.flush(); os.fsync(stream.fileno()); os.fchmod(stream.fileno(), 0o444); stream.close()
                body = bytes(buffers[key]); self.raw += len(body)
                event['streams'][key] = {'path': str((self.out / f'command-{number:03d}-{key}.bin').relative_to(ROOT)), **short(body)}
            self.write(f'command-{number:03d}-result.json', event)
        if failure is not None:
            raise failure
        need(event['cli_reaped'] and event['capture_complete'] and not event['truncated'], 'Complete reaped bounded CLI result')
        return subprocess.CompletedProcess([DOCKER, *argv], event['returncode'], bytes(buffers['stdout']), bytes(buffers['stderr']))
