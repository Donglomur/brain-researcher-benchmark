"""Task-specific original host enclosure for FIND032; native work is explicit only."""
import os
import selectors
import signal
import struct
import time

from .n071_linux.capacity import Capacity
from .n071_linux.cgroup import Cgroup
from .n071_linux.custody import Owner, require
from .n071_linux.filesystem import Directory, OwnedFD, acquire_fd, own_returned_fd
from .resource_channel import decode, encode

STREAM_CAP = 65536
REQUEST_CAP = 1024


class OriginalChildFailure(RuntimeError):
    def __init__(self, child, reason):
        super().__init__(reason)
        self.original_child = child


class RecoveryGroup(Cgroup):
    """Pre-created owned recovery capacity remains usable after an earlier failure."""
    def _read(self, name, *, cleanup=False):
        return super()._read(name, cleanup=True)

    def _write(self, name, value, *, cleanup=False):
        return super()._write(name, value, cleanup=True)


class OwnedSelector:
    """One actual selector FD retained before any child observation uses it."""
    cleanup_priority = 40
    def __init__(self, parent, cleanup=False):
        self.parent = parent
        self.capacity = parent.recovery_capacity if cleanup else parent.capacity
        self.selector = None
        self.accounted = self.close_attempted = False
        self.attempt = parent.owner.begin("find032-original-selector", cleanup=cleanup)
        parent.owner.retain(self)
        self.token = self.capacity.reserve("live_fds", 1, "find032-selector", cleanup=cleanup)
        mask = signal.pthread_sigmask(signal.SIG_BLOCK,
                                     {signal.SIGALRM, signal.SIGTERM, signal.SIGINT})
        try:
            self.selector = selectors.DefaultSelector()
        except BaseException as error:
            self.attempt.fail(error, "selector-acquisition")
            self.attempt.uncertain("selector-constructor-return-unavailable", None)
            parent.fail(error, "selector-acquisition")
            raise
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, mask)
        self.capacity.settle(self.token, 1)
        self.accounted = True
        self.attempt.returned.append(self.selector)
        self.attempt.finish()

    def register(self, *args):
        return self.selector.register(*args)

    def unregister(self, *args):
        return self.selector.unregister(*args)

    def modify(self, *args):
        return self.selector.modify(*args)

    def select(self, *args):
        return self.selector.select(*args)

    def get_map(self):
        return self.selector.get_map()

    def close(self):
        if self.close_attempted:
            return
        self.close_attempted = True
        known = self.selector is None
        try:
            if self.selector is not None:
                self.selector.close()
                known = True
        except BaseException as error:
            self.parent.fail(error, "selector-retirement")
        if self.accounted:
            try:
                self.capacity.release_live("live_fds", 1, known=known)
            except BaseException as error:
                self.parent.fail(error, "selector-retirement-accounting")


class NativeOwner:
    def __init__(self, selection, origin, final_endpoint):
        require(type(selection) is dict and set(selection) == {
            "schema", "capacity", "recovery_capacity", "cgroup_parent", "group_prefix",
            "memory_bytes", "pids", "cpu_quota", "cpu_period", "cleanup_seconds"},
            "exact-find032-host-selection")
        require(selection["schema"] == "find032_original_host_owner_v1" and
                type(origin) in (int, float) and origin < final_endpoint and
                time.monotonic() < final_endpoint, "original-host-interval")
        prefix = selection["group_prefix"]
        require(type(prefix) is str and 1 <= len(prefix) <= 80 and
                all(c in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in prefix),
                "fixed-original-cgroup-prefix")
        self.owner = Owner()
        self.capacity = Capacity(self.owner, selection["capacity"])
        self.recovery_capacity = Capacity(self.owner, selection["recovery_capacity"])
        require(self.capacity.limits["child_attempts"] >= 1 and
                self.recovery_capacity.limits["child_attempts"] >= 1,
                "separately-selected-original-recovery-reserve")
        self.origin, self.final_endpoint = origin, final_endpoint
        self.cpu_origin = time.process_time()
        self.children, self.errors = [], []
        self.first = None
        self.raw_returns = []
        self.owner_pid = os.getpid()
        self.last_sample = origin
        self.selection = selection
        self.prefix = prefix
        self.parent = None
        self.recovery_parent = None
        self.controller_group = self.recovery_group = None
        self.groups = []

    def prepare(self):
        require(self.parent is None, "original-host-prepare-once")
        selection = self.selection
        self.parent = Directory.open_absolute(self.owner, self.capacity, selection["cgroup_parent"])
        self.recovery_parent = Directory.open_absolute(self.owner, self.recovery_capacity,
                                                       selection["cgroup_parent"])
        args = tuple(selection[k] for k in
                     ("memory_bytes", "pids", "cpu_quota", "cpu_period", "cleanup_seconds"))
        # Both original namespace/capacity owners exist before controller effects.
        self.controller_group = Cgroup(self.parent, self.prefix + "-controller", *args)
        self.recovery_group = RecoveryGroup(self.recovery_parent, self.prefix + "-recovery", *args)
        self.groups = (self.controller_group, self.recovery_group)
        self.tick()

    def fail(self, error, stage):
        if self.first is None:
            self.first = error
        self.errors.append((stage, error))

    def tick(self, *, cleanup=False):
        require(os.getpid() == self.owner_pid, "same-original-native-parent")
        require(time.monotonic() < self.final_endpoint, "original-final-endpoint")
        now = time.monotonic()
        if now - self.last_sample >= 1:
            self.last_sample = now
            for group in self.groups:
                if not group.close_attempted and any(child.group is group and child.activated
                        and not child.waited for child in self.children):
                    group.sample(cleanup=cleanup)
        cpu = time.process_time() - self.cpu_origin
        for group in getattr(self, "groups", ()):
            if group.samples:
                cpu += group.samples[-1].cpu_usec / 1000000
        capacity = self.recovery_capacity if cleanup else self.capacity
        capacity.observe_clock(time.monotonic() - self.origin, cpu)

    def pipe(self, label, *, cleanup=False):
        capacity = self.recovery_capacity if cleanup else self.capacity
        attempt = self.owner.begin(label, cleanup=cleanup)
        tokens = [capacity.reserve("live_fds", 1, label, cleanup=cleanup) for _ in range(2)]
        pair = None
        handles = []
        try:
            pair = os.pipe2(os.O_CLOEXEC)
            attempt.returned.append(pair)
            # Retain both acquired numbers before accounting either descriptor.
            for fd, token in zip(pair, tokens):
                handles.append(own_returned_fd(self.owner, capacity, fd, attempt, token))
            attempt.finish()
            return handles
        except BaseException as error:
            attempt.fail(error, label)
            self.fail(error, label)
            # own_returned_fd retains its actual owner before accounting/fstat.
            # A failed return can already have attempted that owner's close;
            # it must not be mistaken for a raw never-owned descriptor.
            owned = {h.fd for h in self.owner.resources if type(h) is OwnedFD and h.attempt is attempt}
            for fd in pair or ():
                if fd not in owned:
                    try:
                        os.close(fd)
                    except BaseException as later:
                        attempt.uncertain("unowned-pipe-close", {"fd": fd})
                        self.fail(later, label + "-unaccounted-close")
            raise

    def spawn(self, argv, env, group, startup_end, *, inherited=(), cleanup=False):
        require(group in self.groups and not group.close_attempted and
                type(argv) is list and argv and all(type(x) is str and "\0" not in x for x in argv) and
                type(env) is dict and all(type(k) is str and type(v) is str for k,v in env.items()),
                "fixed-original-child-operands")
        require(sum(len(x.encode()) + 1 for x in argv) <= 65536 and
                time.monotonic() < startup_end <= self.final_endpoint,
                "finite-original-child-start")
        child = Child(self, group, cleanup)
        capacity = child.capacity
        self.children.append(child)  # Owner exists before any child/pipe acquisition.
        attempt = self.owner.begin("find032-original-child-birth", cleanup=cleanup)
        child.birth = attempt
        token = capacity.reserve("child_attempts", 1, "find032-fork", cleanup=cleanup)
        capacity.settle(token, 1)  # Attempt is cumulative, including failed fork.
        try:
            child.out_read, child.out_write = self.pipe("find032-stdout-pipe", cleanup=cleanup)
            child.err_read, child.err_write = self.pipe("find032-stderr-pipe", cleanup=cleanup)
            child.devnull = acquire_fd(self.owner, capacity, "/dev/null", os.O_RDONLY,
                                       cleanup=cleanup)
            memory = capacity.reserve("rss_bytes", STREAM_CAP + 1, "find032-original-streams",
                                           cleanup=cleanup)
            capacity.settle(memory, memory.capacity)
            child.read_token = capacity.reserve("read_bytes", STREAM_CAP + 1,
                                                     "find032-original-streams", cleanup=cleanup)
            mask = signal.pthread_sigmask(signal.SIG_BLOCK,
                                          {signal.SIGALRM, signal.SIGTERM, signal.SIGINT})
            try:
                pid = os.fork()
                if pid == 0:
                    try:
                        os.setsid()
                        os.dup2(child.devnull.fd, 0, inheritable=True)
                        os.dup2(child.out_write.fd, 1, inheritable=True)
                        os.dup2(child.err_write.fd, 2, inheritable=True)
                        allow = {0, 1, 2, *inherited}
                        # Fixed trusted fork branch only; no candidate code before enclosure.
                        descriptors = os.listdir("/proc/self/fd")
                        if len(descriptors) > 4096:
                            os._exit(126)
                        for name in descriptors:
                            fd = int(name)
                            if fd not in allow:
                                try:
                                    os.close(fd)
                                except OSError:
                                    pass
                        for fd in inherited:
                            os.set_inheritable(fd, True)
                        os.kill(os.getpid(), signal.SIGSTOP)
                        signal.pthread_sigmask(signal.SIG_SETMASK, mask)
                        os.execve(argv[0], argv, env)
                    except BaseException:
                        try:
                            os.write(2, b"find032_owned_exec_failed\n")
                        except BaseException:
                            pass
                        os._exit(127)
                child.pid = pid
                attempt.returned.append(child)  # PID retained before signals are restored.
            finally:
                if os.getpid() == self.owner_pid:
                    signal.pthread_sigmask(signal.SIG_SETMASK, mask)
            child.out_write.close()
            child.err_write.close()
            child.devnull.close()
            while True:
                require(time.monotonic() < startup_end, "original-stopped-child-deadline")
                pid, status, usage = os.wait4(child.pid, os.WUNTRACED | os.WNOHANG)
                if pid:
                    child.wait_events.append((pid, status, usage))
                    if pid == child.pid and (os.WIFEXITED(status) or os.WIFSIGNALED(status)):
                        # This original wait already reaped the PID. Admission
                        # failure must never signal a potentially reused number.
                        child.waited = True
                        child.exit_code = os.waitstatus_to_exitcode(status)
                    require(pid == child.pid and os.WIFSTOPPED(status) and
                            os.WSTOPSIG(status) == signal.SIGSTOP,
                            "original-child-stopped-before-activation")
                    break
                time.sleep(0.005)
            group.attach_stopped_pid(child.pid)
            child.attached = True
            os.set_blocking(child.out_read.fd, False)
            os.set_blocking(child.err_read.fd, False)
            attempt.finish()
            return child
        except BaseException as error:
            attempt.fail(error, "original-child-birth")
            self.fail(error, "original-child-birth")
            raise

    def activate(self, child):
        require(child in self.children and child.attached and not child.activated and
                not child.waited and time.monotonic() < self.final_endpoint,
                "actual-once-enclosed-activation")
        child.activated = True  # Unknown signal completion never permits a retry.
        os.kill(child.pid, signal.SIGCONT)

    def close_group(self, group, deadline):
        if group.close_attempted:
            return
        group.close_attempted = True
        # This is a once-only transition into already-selected recovery custody.
        # Existing descriptors keep their own original acquisition capacities;
        # only subsequent kill/read acquisitions use the independent reserve.
        errors = []
        try:
            require(group.owner is self.owner and group.capacity in
                    (self.capacity, self.recovery_capacity), "same-original-group-cost-owner")
            group.find032_active_capacity = group.capacity
            group.capacity = self.recovery_capacity
            require(group.created and group.directory is not None and
                    time.monotonic() < deadline <= self.final_endpoint,
                    "original-owned-cgroup-retirement")
            for child in self.children:
                if child.group is group and child.pid is not None and not child.waited:
                    child.kill_sent = True
            group._write("cgroup.kill", "1", cleanup=True)
        except BaseException as error:
            errors.append(error)
            self.fail(error, "cgroup-kill")
        try:
            while True:
                require(time.monotonic() < deadline, "same-original-cgroup-cleanup-cutoff")
                current = group.sample(cleanup=True)
                if not current.populated:
                    group.final, group.closed = current, True
                    break
                time.sleep(0.01)
        except BaseException as error:
            errors.append(error)
            group.attempt.uncertain("original-cgroup-retirement", group.name)
            self.fail(error, "cgroup-empty-observation")
        # Remaining original child waits and resources are attempted independently.
        return not errors and group.closed

    def finish(self):
        # Partial constructors are also retained by the existing original Owner.
        for resource in self.owner.resources:
            if isinstance(resource, Cgroup) and not resource.close_attempted:
                try:
                    self.close_group(resource, self.final_endpoint)
                except BaseException as error:
                    self.fail(error, "partial-cgroup-retirement")
        for child in self.children:
            try:
                child.retire(self.final_endpoint)
            except BaseException as error:
                self.fail(error, "final-original-child-wait")
            try:
                drain_original_streams(child, self.final_endpoint)
            except BaseException as error:
                self.fail(error, "final-original-stream-drain")
            try:
                child.close_streams()
            except BaseException as error:
                self.fail(error, "final-stream-retirement")
        try:
            self.owner.cleanup()
        except BaseException as error:
            self.fail(error, "original-native-owner-cleanup")
        if self.first is not None:
            raise self.first


class Child:
    def __init__(self, parent, group, cleanup):
        self.parent, self.group, self.cleanup = parent, group, cleanup
        self.capacity = parent.recovery_capacity if cleanup else parent.capacity
        self.pid = None
        self.attached = self.activated = self.waited = self.kill_sent = False
        self.exit_code = None
        self.wait_events = []
        self.out_read = self.out_write = self.err_read = self.err_write = self.devnull = None
        self.read_token = None
        self.read_settled = False
        self.read_pending = False
        self.stdout, self.stderr = bytearray(), bytearray()
        self.stream_eof = set()
        self.streams_closed = False
        self.stream_close_failed = False
        self.group_absence_observed = False
        self.closed_handles = set()
        self.start = time.monotonic()
        self.birth = None

    def poll(self):
        if self.pid is None or self.waited:
            return self.waited
        pid, status, usage = os.wait4(self.pid, os.WNOHANG)
        if pid:
            self.wait_events.append((pid, status, usage))
            require(pid == self.pid and (os.WIFEXITED(status) or os.WIFSIGNALED(status)),
                    "original-terminal-child-wait")
            self.waited = True
            self.exit_code = os.waitstatus_to_exitcode(status)
        return self.waited

    def read_stream(self, which):
        handle = self.out_read if which == "stdout" else self.err_read
        total = len(self.stdout) + len(self.stderr)
        require(total <= STREAM_CAP and which not in self.stream_eof, "bounded-original-stream")
        self.read_pending = True
        try:
            raw = os.read(handle.require_live(), min(8192, STREAM_CAP + 1 - total))
        except BlockingIOError:
            self.read_pending = False
            return
        self.read_pending = False
        if raw:
            (self.stdout if which == "stdout" else self.stderr).extend(raw)
            require(len(self.stdout) + len(self.stderr) <= STREAM_CAP, "original-combined-stream-cap")
        else:
            self.stream_eof.add(which)

    def retire(self, deadline):
        if self.pid is None:
            return
        if not self.waited:
            # Group closure is performed first for all admitted descendants.
            if not self.attached:
                try:
                    require(time.monotonic() < deadline <= self.parent.final_endpoint,
                            "original-unattached-child-kill-cutoff")
                    os.kill(self.pid, signal.SIGKILL)
                    self.kill_sent = True
                except ProcessLookupError:
                    pass
                except BaseException as error:
                    self.parent.fail(error, "unattached-original-child-kill")
            while not self.waited:
                try:
                    self.poll()
                    if self.waited:
                        break
                    require(time.monotonic() < deadline, "original-child-final-wait")
                    time.sleep(0.005)
                except BaseException as error:
                    self.parent.fail(error, "original-child-final-wait")
                    break
        try:
            os.killpg(self.pid, 0)
        except ProcessLookupError:
            self.group_absence_observed = True
        except BaseException as error:
            self.parent.fail(error, "original-process-group-observation")

    def close_parent_writers(self):
        # A partial birth can return control before these ends were closed.
        # Retire them before waiting for read-side EOF that they would prevent.
        for handle in (self.out_write, self.err_write, self.devnull):
            if handle is not None and id(handle) not in self.closed_handles:
                self.closed_handles.add(id(handle))
                try:
                    if not handle.close_attempted:
                        handle.close()
                    require(handle.closed, "original-parent-writer-actually-closed")
                except BaseException as error:
                    self.stream_close_failed = True
                    self.parent.fail(error, "original-parent-writer-close")

    def close_streams(self):
        if self.streams_closed:
            return
        self.streams_closed = not self.stream_close_failed
        for handle in (self.out_read, self.out_write, self.err_read, self.err_write, self.devnull):
            if handle is not None and id(handle) not in self.closed_handles:
                self.closed_handles.add(id(handle))
                try:
                    if not handle.close_attempted:
                        handle.close()
                    require(handle.closed, "original-stream-actually-closed")
                except BaseException as error:
                    self.stream_close_failed = True
                    self.streams_closed = False
                    self.parent.fail(error, "original-stream-close")
        if self.read_token is not None and not self.read_settled:
            self.read_settled = True
            try:
                self.capacity.settle(self.read_token, len(self.stdout) + len(self.stderr),
                                             unknown=self.read_pending)
            except BaseException as error:
                self.parent.fail(error, "original-stream-accounting")

    def projection(self):
        return {"pid": self.pid, "natural_exit": self.waited and self.activated and
                type(self.exit_code) is int and self.exit_code >= 0 and not self.kill_sent,
                "exit_code": self.exit_code, "process_reaped": self.waited,
                "process_group_absent": self.group_absence_observed,
                "streams_closed": self.streams_closed,
                "combined_stream_bytes": len(self.stdout) + len(self.stderr),
                "stdout_bytes": len(self.stdout), "timed_out": False,
                "stdout_eof": "stdout" in self.stream_eof,
                "stderr_eof": "stderr" in self.stream_eof,
                "captured_prefix_only": self.stream_eof != {"stdout", "stderr"},
                "kill_sent": self.kill_sent, "error_type": None,
                "descendant_cgroup": self.group.report(),
                "actual_wait_events": len(self.wait_events),
                "earlier_host_and_outer_future_exit_qualified": False}


def observe_controller(parent, child, endpoint, registry, normal_end):
    """Original child and ownership endpoint are observed concurrently."""
    selector = None
    incoming, outgoing = bytearray(), bytearray()
    expected = 0
    eof = False
    original_error = None
    io_attempt = None
    read_token = write_token = None
    read_count = write_count = 0
    read_pending = write_pending = False
    parent.raw_returns.append((incoming, outgoing))  # Retain partial protocol streams.
    try:
        io_attempt = parent.owner.begin("find032-original-lifecycle-channel")
        read_token = parent.capacity.reserve("read_bytes", REQUEST_CAP + 4 + 28 * 2052 + 1,
                                             "find032-complete-channel-requests")
        write_token = parent.capacity.reserve("write_bytes", 29 * 2052,
                                              "find032-complete-channel-replies")
        memory = parent.capacity.reserve("rss_bytes", 2 * REQUEST_CAP + 65536 + 4104,
                                         "find032-bounded-channel-byte-buffers")
        parent.capacity.settle(memory, memory.capacity)
        selector = OwnedSelector(parent)
        endpoint.setblocking(False)
        selector.register(endpoint, selectors.EVENT_READ, "channel")
        for which, handle in (("stdout", child.out_read), ("stderr", child.err_read)):
            selector.register(handle.fd, selectors.EVENT_READ, which)
        parent.activate(child)
        while True:
            require(time.monotonic() < normal_end, "original-controller-normal-cutoff")
            if child.poll() and child.exit_code != 0:
                raise OriginalChildFailure(child, "original-controller-nonzero")
            if child.waited and child.stream_eof == {"stdout", "stderr"} and eof:
                require(not incoming and not outgoing, "complete-terminal-channel")
                require(registry.natural_complete(), "complete-original-resource-lifecycle")
                break
            for key, mask in selector.select(min(0.1, max(0, normal_end - time.monotonic()))):
                if key.data != "channel":
                    child.read_stream(key.data)
                    if key.data in child.stream_eof:
                        selector.unregister(key.fileobj)
                    continue
                if mask & selectors.EVENT_READ and not eof:
                    remaining = read_token.capacity - read_count
                    require(remaining > 0, "channel-read-reservation-before-recv")
                    if expected == 29:
                        wanted = 1  # Only the reserved final EOF probe is legal.
                    elif len(incoming) < 4:
                        wanted = 4 - len(incoming)
                    else:
                        size = struct.unpack("!I", incoming[:4])[0]
                        maximum = REQUEST_CAP if expected == 0 else 2048
                        require(0 < size <= maximum, "phase-frame-cap-before-body")
                        wanted = size + 4 - len(incoming)
                    require(wanted > 0, "positive-original-request-extent")
                    read_pending = True
                    raw = endpoint.recv(min(65536, wanted, remaining))
                    read_count += len(raw)
                    read_pending = False
                    if not raw:
                        eof = True
                        require(not incoming, "no-partial-request-at-eof")
                    else:
                        require(expected < 29, "no-request-after-complete-programme")
                        incoming.extend(raw)
                        require(len(incoming) <= REQUEST_CAP + 4, "bounded-original-request-prefix")
                    if len(incoming) >= 4:
                        size = struct.unpack("!I", incoming[:4])[0]
                        require(0 < size <= (REQUEST_CAP if expected == 0 else 2048),
                                "request-size-before-body")
                        if len(incoming) >= size + 4:
                            require(not outgoing and len(incoming) == size + 4,
                                    "one-original-outstanding-request")
                            request = decode(bytes(incoming[4:]))
                            require(set(request) == {"sequence", "request"} and
                                    request["sequence"] == expected, "no-request-replay")
                            result = registry.dispatch(request["request"])
                            reply = encode({"sequence": expected, "result": result})
                            require(len(reply) <= 2052, "finite-original-reply-extent")
                            outgoing.extend(reply)
                            expected += 1
                            incoming.clear()
                if mask & selectors.EVENT_WRITE and outgoing:
                    require(len(outgoing) <= write_token.capacity - write_count,
                            "channel-write-reservation-before-send")
                    write_pending = True
                    sent = endpoint.send(outgoing)
                    write_count += sent
                    write_pending = False
                    require(sent > 0, "parent-reply-progress")
                    del outgoing[:sent]
                if eof and not outgoing:
                    selector.unregister(endpoint)
                else:
                    selector.modify(endpoint, (0 if eof else selectors.EVENT_READ) |
                                    (selectors.EVENT_WRITE if outgoing else 0), "channel")
            parent.tick(cleanup=child.cleanup)
    except BaseException as error:
        original_error = error
        parent.fail(error, "original-controller-observation")
    finally:
        try:
            if selector is not None:
                selector.close()
        except BaseException as error:
            parent.fail(error, "original-observer-selector-close")
        try:
            endpoint.close()
        except BaseException as error:
            parent.fail(error, "original-channel-close")
        for token, count, pending in ((read_token, read_count, read_pending),
                                      (write_token, write_count, write_pending)):
            if token is None:
                continue
            try:
                parent.capacity.settle(token, count, unknown=pending)
            except BaseException as error:
                parent.fail(error, "original-channel-accounting")
        if original_error is None and io_attempt is not None:
            io_attempt.finish()
    return original_error


def drain_original_streams(child, deadline):
    """Retain available original failure prefixes before independently closing pipes."""
    selector = None
    try:
        child.close_parent_writers()
        selector = OwnedSelector(child.parent, cleanup=True)
        for which, handle in (("stdout", child.out_read), ("stderr", child.err_read)):
            if handle is not None and not handle.close_attempted and which not in child.stream_eof:
                selector.register(handle.fd, selectors.EVENT_READ, which)
        while selector.get_map() and time.monotonic() < deadline:
            for key, _ in selector.select(min(0.02, max(0, deadline - time.monotonic()))):
                child.read_stream(key.data)
                if key.data in child.stream_eof:
                    selector.unregister(key.fileobj)
        if selector.get_map():
            child.parent.fail(TimeoutError("original-failure-stream-eof-unknown"),
                              "original-failure-stream-drain")
    except BaseException as error:
        child.parent.fail(error, "original-failure-stream-drain")
    finally:
        try:
            if selector is not None:
                selector.close()
        except BaseException as error:
            child.parent.fail(error, "original-drain-selector-close")


def observe_recovery(parent, child, normal_end):
    """The one fixed recovery child has no callback or new resource request channel."""
    selector = None
    error = None
    try:
        selector = OwnedSelector(parent, cleanup=True)
        for which, handle in (("stdout", child.out_read), ("stderr", child.err_read)):
            selector.register(handle.fd, selectors.EVENT_READ, which)
        parent.activate(child)
        while True:
            require(time.monotonic() < normal_end, "same-original-recovery-cutoff")
            child.poll()
            if child.waited and child.stream_eof == {"stdout", "stderr"}:
                require(child.exit_code == 0, "original-recovery-child-natural-zero")
                break
            for key, _ in selector.select(min(0.05, max(0, normal_end - time.monotonic()))):
                child.read_stream(key.data)
                if key.data in child.stream_eof:
                    selector.unregister(key.fileobj)
            parent.tick(cleanup=True)
    except BaseException as problem:
        error = problem
        parent.fail(problem, "original-recovery-observation")
    finally:
        try:
            if selector is not None:
                selector.close()
        except BaseException as problem:
            parent.fail(problem, "original-recovery-selector-close")
    return error

