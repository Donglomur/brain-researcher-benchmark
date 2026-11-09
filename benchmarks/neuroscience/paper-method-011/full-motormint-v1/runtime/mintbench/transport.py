"""Prospective owned Docker JSON-line transport; source only, runtime unqualified.

No data directory, socket, credentials or output directory is mounted. A qualified
root-selected immutable image and an owned immutable source/context directory are
required. Its caller must independently observe this supervisor's natural exit.
"""
import json
import math
import os
import re
import selectors
import signal
import subprocess
import time
import uuid
from pathlib import Path
from .validation import MAX_FRAME, encoded, need


def absent_group(pid):
    try:
        os.killpg(pid, 0)
        return False
    except ProcessLookupError:
        return True


def gpu_arguments(devices):
    """Exact admitted physical-device UUIDs; never exposes all host GPUs.

    Docker's --gpus value is CSV; the device list needs double quotes inside the
    argv element. Shell quoting is not used because subprocess receives argv.
    Device exclusivity/custody and drivers remain independently qualified gates.
    """
    need(type(devices) in (list, tuple) and len(devices) <= 64, 'finite GPU allocation')
    need(len(set(devices)) == len(devices), 'unique allocated physical GPUs')
    for device in devices:
        need(type(device) is str and re.fullmatch(r'GPU-[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}', device), 'exact GPU UUID; indices/all/MIG aliases disallowed')
    return ['--gpus', '"device=' + ','.join(devices) + '"'] if devices else []


class DockerTransport:
    def __init__(self, *, docker, image, python, source_directory, source_sha, worker_sha,
                 context_directory, memory_bytes, scratch_bytes, origin, normal_end,
                 cleanup_end, wire_cap_bytes, cgroup_parent=None, gpu_devices=(), diagnostics=None, ownership_token=None):
        need(diagnostics is not None,'private bounded stream custody before launch')
        self.diagnostics=diagnostics
        self.process = None
        self.selector = None
        self.record = {'natural_exit': False, 'exit_code': None, 'streams_closed': False,
                       'container_absent': False, 'client_group_absent': False,
                       'stdout_eof': False, 'stderr_eof': False}
        self.origin, self.end, self.cleanup_end = origin, normal_end, cleanup_end
        need(all(type(x) in (int, float) and math.isfinite(x) for x in (origin, normal_end, cleanup_end)), 'finite original absolute deadlines')
        need(origin <= time.monotonic() < normal_end < cleanup_end, 'original absolute deadlines')
        need(0 < normal_end - origin <= 172800 and cleanup_end - normal_end <= 60, 'finite prospective whole/cleanup ceilings')
        need(Path(docker).is_absolute() and Path(python).is_absolute(), 'explicit executable paths')
        need(re.fullmatch(r'sha256:[a-f0-9]{64}', image) is not None, 'immutable image ID')
        need(type(memory_bytes) is int and 134217728 <= memory_bytes <= 34359738368, 'finite prospective memory ceiling')
        need(type(scratch_bytes) is int and 1048576 <= scratch_bytes <= 8589934592, 'finite prospective scratch ceiling')
        need(type(wire_cap_bytes) is int and 1 <= wire_cap_bytes <= 1000000000000, 'finite whole wire ceiling')
        self.docker, self.image = docker, image
        self.name = 'mint-program-' + uuid.uuid4().hex
        self.cap, self.count = wire_cap_bytes, 0
        self.stderr_bytes, self.buffer = 0, bytearray()
        self.finished = False
        self.closed = False
        self.record['lifecycle_commands'] = []
        self.record['diagnostics']=self.diagnostics.snapshot()
        self.record['launch_attempted']=False
        self.record['forced_termination']=False
        source = Path(source_directory)
        context = Path(context_directory)
        # Both directories are owned captures authenticated by the root admission.
        for directory in (source, context):
            need(directory.is_absolute() and directory.is_dir() and not any(p.is_symlink() for p in (directory, *directory.parents)), 'owned source/context paths')
        import hashlib
        for name, expected in [('candidate.py', source_sha), ('worker.py', worker_sha)]:
            path = source / name
            need(not path.is_symlink(), 'regular captured code')
            with path.open('rb') as stream:
                raw = stream.read(262145)
            need(len(raw) <= 262144 and hashlib.sha256(raw).hexdigest() == expected, 'captured code pin')
        need(set(p.name for p in source.iterdir()) == {'candidate.py', 'worker.py'}, 'source mount exact members')
        argv = [docker, 'run', '--rm', '-i', '--name', self.name, '--network=none',
                '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                '--pids-limit=128', '--memory=' + str(memory_bytes), '--memory-swap=' + str(memory_bytes),
                '--cpus=2', '--user=65534:65534', '--ipc=private', '--shm-size=16777216',
                '--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=' + str(scratch_bytes),
                '--mount=type=bind,src=' + str(source) + ',dst=/source,readonly',
                '--mount=type=bind,src=' + str(context) + ',dst=/context,readonly',
                '--env=PYTHONDONTWRITEBYTECODE=1', '--env=OMP_NUM_THREADS=1',
                '--entrypoint=' + python, image, '-I', '-B', '/source/worker.py',
                '/source/candidate.py', source_sha]
        need(all(',' not in str(p) for p in (source, context)), 'unambiguous mount paths')
        need(type(ownership_token) is str and re.fullmatch('[a-f0-9]{32}',ownership_token),'outer-owned container identity')
        argv[2:2]=['--label=motormint.owner='+ownership_token]
        self.argv = argv
        devices = gpu_arguments(gpu_devices)
        if devices:
            self.argv[2:2] = devices
        if cgroup_parent is not None:
            need(type(cgroup_parent) is str and re.fullmatch(r'/[A-Za-z0-9_./-]+', cgroup_parent)
                 and '..' not in cgroup_parent.split('/'), 'operator-owned cgroup parent')
            self.argv[2:2] = ['--cgroup-parent=' + cgroup_parent]

    def __enter__(self):
        try:
            need(time.monotonic() < self.end, 'start within original clock')
            self.record['launch_attempted']=True
            self.process = subprocess.Popen(self.argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE, bufsize=0, start_new_session=True,
                                            env={'PATH': '/usr/bin:/bin', 'HOME': '/var/empty'})
            self.selector = selectors.DefaultSelector()
            for stream, tag in ((self.process.stdout, 'out'), (self.process.stderr, 'err')):
                os.set_blocking(stream.fileno(), False)
                self.selector.register(stream, selectors.EVENT_READ, tag)
            os.set_blocking(self.process.stdin.fileno(), False)
            return self
        except BaseException as primary:
            try:
                self.close()
            except BaseException as cleanup:
                message=type(cleanup).__name__+': '+str(cleanup)[:300]
                self.record['entry_cleanup_error']=message
                primary.add_note('Transport entry cleanup: '+message)
            raise

    def _before(self):
        need(time.monotonic() < self.end, 'original session deadline')

    def _charge(self, count):
        self.count += count
        self.record.update(protocol_bytes=self.count,stderr_bytes=self.stderr_bytes,diagnostics=self.diagnostics.snapshot())
        need(self.count <= self.cap, 'cumulative protocol byte cap')

    def _drain(self, timeout=.05):
        self._before()
        for key, _ in self.selector.select(min(timeout, self.end - time.monotonic())):
            block = os.read(key.fileobj.fileno(), 65536)
            if not block:
                self.diagnostics.eof(key.data)
                self.record['stdout_eof' if key.data == 'out' else 'stderr_eof'] = True
                self.selector.unregister(key.fileobj)
            elif key.data == 'out':
                self.diagnostics.feed('out',block)
                self._charge(len(block))
                self.buffer.extend(block)
                need(len(self.buffer) <= MAX_FRAME, 'one bounded response')
            else:
                self.diagnostics.feed('err',block)
                self._charge(len(block))
                self.stderr_bytes += len(block)
                need(self.stderr_bytes <= 1048576, 'bounded diagnostic stream')

    def exchange(self, value):
        self._before()
        need(not self.finished and not self.buffer, 'no unsolicited responses')
        raw = encoded(value) + b'\n'
        need(len(raw) <= MAX_FRAME, 'bounded request')
        self._charge(len(raw))
        cursor = 0
        while cursor < len(raw):
            self._before()
            try:
                cursor += os.write(self.process.stdin.fileno(), raw[cursor:])
            except BlockingIOError:
                self._drain()
        while b'\n' not in self.buffer:
            need(self.selector.get_map(), 'response EOF')
            self._drain()
        line, _, trailing = self.buffer.partition(b'\n')
        need(not trailing, 'single response per request')
        self.buffer.clear()
        return json.loads(line, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite response')))

    def _cli(self, argv, end):
        need(end-time.monotonic()>0,'bounded Docker lifecycle deadline')
        capture=self.diagnostics.child('cli'+str(len(self.record['lifecycle_commands'])))
        observed={'arguments':argv,'natural_exit':False,'exit_code':None,'forced_termination':False,
                  'process_reaped':False,'group_absent':False,'streams_closed':False,'stdout_eof':False,'stderr_eof':False}
        self.record['lifecycle_commands'].append(observed)
        child=None;sel=selectors.DefaultSelector();output=bytearray();count=0
        try:
            child=subprocess.Popen([self.docker,*argv],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,env={'PATH':'/usr/bin:/bin','HOME':'/var/empty'})
            for stream,tag in ((child.stdout,'out'),(child.stderr,'err')):
                os.set_blocking(stream.fileno(),False);sel.register(stream,selectors.EVENT_READ,tag)
            while sel.get_map():
                need(time.monotonic()<end,'Docker lifecycle deadline')
                for key,_ in sel.select(min(.05,max(0,end-time.monotonic()))):
                    block=os.read(key.fileobj.fileno(),8192)
                    if not block:
                        capture.eof(key.data);observed['stdout_eof' if key.data=='out' else 'stderr_eof']=True;sel.unregister(key.fileobj)
                    else:
                        capture.feed(key.data,block);count+=len(block);need(count<=65536,'Docker lifecycle stream cap')
                        if key.data=='out':output.extend(block)
            code=child.wait(timeout=max(.001,end-time.monotonic()))
            observed.update(natural_exit=True,exit_code=code,process_reaped=True)
            need(absent_group(child.pid),'Docker lifecycle group absence');return code,bytes(output)
        except BaseException as error:
            observed['reason']=type(error).__name__+': '+str(error);raise
        finally:
            if child is not None:
                if child.poll() is None or not absent_group(child.pid):
                    observed['forced_termination']=True
                    try:os.killpg(child.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    try:child.wait(timeout=max(.001,end-time.monotonic()))
                    except subprocess.TimeoutExpired:pass
                observed.update(process_reaped=child.poll() is not None,group_absent=absent_group(child.pid))
                child.stdout.close();child.stderr.close()
            sel.close();observed.update(streams_closed=True,combined_bytes=count,diagnostics=capture.close())

    def _container_absent(self, end):
        code, out = self._cli(['ps', '-a', '--filter', 'name=^/' + self.name + '$', '--format', '{{.ID}}'], end)
        return code == 0 and out.strip() == b''

    def finish(self):
        self._before()
        self.process.stdin.close()
        while self.selector.get_map():
            self._drain()
        need(not self.buffer, 'no post-finish protocol output')
        self.record['exit_code'] = self.process.wait(timeout=max(.001, self.end - time.monotonic()))
        self.record['natural_exit'] = True
        self.record['client_group_absent'] = absent_group(self.process.pid)
        self.record['container_absent'] = self._container_absent(self.end)
        need(self.record['exit_code'] == 0 and self.record['client_group_absent'] and self.record['container_absent'] and self.record['stdout_eof'] and self.record['stderr_eof'], 'natural zero, EOF and owned absence')
        self.finished = True
        self.close()
        self._before()
        self.record.update(protocol_bytes=self.count, stderr_bytes=self.stderr_bytes,
                           elapsed_seconds=time.monotonic() - self.origin, container_name=self.name)
        return dict(self.record)

    def _drain_cleanup(self):
        """Preserve already-buffered original bytes after failure, within cleanup."""
        if self.selector is None:return
        try:
            while self.selector.get_map() and time.monotonic()<self.cleanup_end:
                for key,_ in self.selector.select(min(.01,max(0,self.cleanup_end-time.monotonic()))):
                    block=os.read(key.fileobj.fileno(),65536)
                    if not block:
                        self.diagnostics.eof(key.data)
                        self.record['stdout_eof' if key.data=='out' else 'stderr_eof']=True
                        self.selector.unregister(key.fileobj)
                    else:
                        self.diagnostics.feed(key.data,block)
                        self.count+=len(block)
                        if key.data=='err':self.stderr_bytes+=len(block)
                        need(self.count<=self.cap,'cleanup observed-stream cap')
        except BaseException as error:
            self.record['diagnostic_cleanup_error']=type(error).__name__+': '+str(error)

    def close(self):
        if self.closed:
            return
        if self.process is not None:
            if not self.finished:
                # Stop/reap the client that could still create the named
                # container BEFORE final removal and absence observation.
                if self.process.poll() is None or not absent_group(self.process.pid):
                    self.record['forced_termination']=True
                    try:
                        os.killpg(self.process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                try:
                    self.process.wait(timeout=max(.001, min(3, self.cleanup_end - time.monotonic())))
                except subprocess.TimeoutExpired:
                    pass
                self.record['client_group_absent'] = absent_group(self.process.pid)
                self.record['client_reaped'] = self.process.poll() is not None
                try:
                    self._cli(['rm', '--force', self.name], self.cleanup_end)
                    self.record['container_absent'] = self._container_absent(self.cleanup_end)
                except BaseException:
                    self.record['container_absent'] = False
            self._drain_cleanup()
            for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                stream.close()
            if self.selector is not None:
                self.selector.close()
            self.record['streams_closed'] = True
        self.record.update(protocol_bytes=self.count,stderr_bytes=self.stderr_bytes,diagnostics=self.diagnostics.close())
        self.closed = True

    def __exit__(self, kind, value, traceback):
        self.close()
