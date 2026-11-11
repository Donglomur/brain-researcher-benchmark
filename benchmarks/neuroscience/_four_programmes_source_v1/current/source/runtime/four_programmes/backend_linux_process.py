"""Concrete fixed server argv, subprocess, pidfd signal/wait and pipe ownership.

The live H/worker context and selected artifact-root resolver are independent
admission prerequisites. These operations are implemented behind that gate;
there is no actual process launch during source construction or import.
"""
import os
import signal
import subprocess
import time
import select
from pathlib import PurePosixPath
from .common import need,integer
from .backend_linux_io import NativeIOCustody

_SPEC=object()


class FixedServerSpec:
    __slots__=('handle','argv','environment','cwd','executable_identity','model_identity')
    def __init__(self,token,handle,argv,environment,cwd,executable_identity,model_identity):
        need(token is _SPEC,'fixed server specification compiler only')
        self.handle=handle;self.argv=tuple(argv);self.environment=dict(environment);self.cwd=cwd
        self.executable_identity=executable_identity;self.model_identity=model_identity


def compile_fixed_server_spec(handle,executable,model,workspace,environment,executable_identity,model_identity):
    """Pure fixed argv compiler, not an artifact-root or execution admission.

    Only the native context owner may call this after opening/authenticating the
    selected artifact roots. Paths cannot be taken from participant/JSON inputs
    or guessed by joining a Pin to the metadata Store's root.
    """
    from .backend_lifecycle import BackendAttemptHandle
    need(type(handle) is BackendAttemptHandle and handle.base is not None,'actual earlier backend base')
    for path in (executable,model,workspace):
        need(type(path) is str and path.startswith('/') and '\0' not in path and
             '..' not in PurePosixPath(path).parts and str(PurePosixPath(path))==path,'exact selected local absolute path')
    need(type(environment) is dict and all(type(k) is str and type(v) is str and '\0' not in k+v
        for k,v in environment.items()),'exact closed source-selected environment values')
    forbidden=('LLAMA_ARG_','HF_','AIP_','LD_','DYLD_')
    need(not any(k.startswith(forbidden) or 'proxy' in k.lower() for k in environment),'no ambient loaders/model/config/proxy overrides')
    f=handle.profile_body;l=f['limits'];s=f['sampling'];alias=handle.artifact_selection['model_alias']
    argv=[executable,'--offline','--host',workspace+'/backend.sock','--model',model,'--alias',alias,
        '--parallel','1','--threads-http','1','--cache-ram','0','--ctx-checkpoints','0','--no-cache-idle-slots',
        '--no-cache-prompt','--no-warmup','--no-context-shift','--no-cont-batching','--no-webui','--no-ui-mcp-proxy',
        '--no-mmproj','--device','none','--gpu-layers','0','--slots','--sleep-idle-seconds','-1',
        '--ctx-size',str(l['context_tokens']),'--batch-size',str(l['batch_tokens']),
        '--ubatch-size',str(l['microbatch_tokens']),'--threads',str(l['threads']),
        '--threads-batch',str(l['threads_batch']),'--seed',str(s['seed'])]
    need(len(argv)<=128 and all(len(x)<=4096 for x in argv),'fixed bounded argv without shell or extra options')
    handle.meter.charge('retained_bytes',sum(len(x.encode('utf8')) for x in argv)+4096)
    handle.meter.charge('work_units',8192)
    return FixedServerSpec(_SPEC,handle,argv,environment,workspace,executable_identity,model_identity)


class ServerProcessOwner:
    """Retained before Popen; every stream and pidfd belongs to this attempt."""
    def __init__(self,handle,io):
        need(type(io) is NativeIOCustody and io.handle is handle,'same original native resource owner')
        self.handle=handle;self.io=io;self.spec=None;self.child=None;self.pidfd=None
        self.stdout=None;self.stderr=None;self.pipe_objects={};self.pipe_close_entered=set()
        self.spawn_entered=False;self.spawn_returned=False;self.signal_entered=False;self.signal_sent=False
        self.signal_time=None;self.signal_purpose=None;self.wait_entered=False;self.wait_result=None
        self.wait_start=None;self.wait_end=None;self.streams_entered=False
        self.eof={'stdout':False,'stderr':False};self.stream_bytes={'stdout':0,'stderr':0}
        self.stream_parts={'stdout':[],'stderr':[]};self.raw_first=None;self.raw_secondaries=[]
        self.unknown_spawn=False;self.unknown_wait=False;self.identity=None
        need(handle.native.process is None,'one retained server owner before spawn')
        handle.native.process=self

    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.raw_secondaries.append(error)
        self.io.retain(error,'server_'+site)

    def spawn(self,spec):
        need(type(spec) is FixedServerSpec and spec.handle is self.handle and not self.spawn_entered,
             'one fixed same-attempt server specification')
        self.spec=spec;self.spawn_entered=True
        try:
            self.io.now(self.handle.J)
            # Lifecycle owns/debits the one process-start slot before this call.
            # No preexec callback, shell, pass_fds or new session/group is added.
            # Server inherits the independently admitted original worker group.
            self.child=subprocess.Popen(list(spec.argv),cwd=spec.cwd,env=spec.environment,
                stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                close_fds=True,start_new_session=False,shell=False)
            self.spawn_returned=True # Returned Popen retained before any access.
            for name in ('stdout','stderr'):
                stream=getattr(self.child,name);self.pipe_objects[name]=stream
                slot=self.io.slot(name);setattr(self,name,slot)
                slot.acquire_entered=True;slot.fd=stream.fileno()
                slot.set_nonblocking()
            self.pidfd=self.io.slot('pidfd');self.pidfd.acquire_entered=True
            self.pidfd.fd=os.pidfd_open(self.child.pid,0)
            self.io.now(self.handle.J)
            return self.child
        except BaseException as error:
            self.unknown_spawn=not self.spawn_returned;self.retain(error,'spawn');raise

    def signal_once(self,purpose):
        need(not self.signal_entered and purpose in ('planned_protocol_shutdown','failure_cleanup'),
             'one source-latched signal purpose')
        self.signal_entered=True;self.signal_purpose=purpose
        try:
            self.io.now(self.handle.R)
            need(self.child is not None and self.pidfd is not None and self.pidfd.fd is not None,
                 'retained actual pidfd; never signal an unverified/reused integer PID')
            self.io.work();signal.pidfd_send_signal(self.pidfd.fd,signal.SIGTERM,None,0)
            self.signal_sent=True;self.signal_time=self.io.now(self.handle.R)
            return self.signal_time
        except BaseException as error:self.retain(error,'signal');raise

    def _drain_one(self,name):
        slot=getattr(self,name)
        need(slot is not None and slot.nonblocking and slot.fd is not None,'confirmed owned nonblocking pipe')
        if self.eof[name]:return
        remaining=self.handle.profile_body['limits']['maximum_server_stream_bytes']-self.stream_bytes[name]
        need(remaining>0,'no server stream EOF probe after original stream cap')
        data=self.io.recv(slot,min(4096,remaining),self.handle.R)
        if data is None:return
        if not data:self.eof[name]=True;return
        self.stream_parts[name].append(data);self.stream_bytes[name]+=len(data)

    def wait_once(self):
        need(not self.wait_entered,'one actual original server wait')
        self.wait_entered=True
        try:
            need(self.child is not None,'actual returned original child')
            self.wait_start=self.io.now(self.handle.R)
            while True:
                for name in ('stdout','stderr'):
                    slot=getattr(self,name)
                    if slot is not None and slot.nonblocking and slot.fd is not None:self._drain_one(name)
                code=self.child.poll()
                if code is not None:
                    need(type(code) is int,'actual integer original wait status')
                    self.wait_result=code;self.wait_end=self.io.now(self.handle.R);return code
                now=self.io.now(self.handle.R);need(now<self.handle.R,'original bounded wait deadline')
                # Waiting on the actual original pidfd prevents a busy loop and
                # does not consume/read a pipe whose setup is unknown.
                need(self.pidfd is not None and self.pidfd.fd is not None,'retained pidfd for bounded wait')
                self.io.work();select.select([self.pidfd.fd],[],[],min(.01,(self.handle.R-now)/1000000000))
        except BaseException as error:self.unknown_wait=True;self.retain(error,'wait');raise

    def close_streams_once(self):
        if self.streams_entered:return all(self.eof.values()) and not self.raw_first
        self.streams_entered=True;first=None
        for name in ('stdout','stderr'):
            slot=getattr(self,name)
            try:
                if slot is not None and slot.nonblocking and self.wait_result is not None:
                    while not self.eof[name]:
                        before=self.stream_bytes[name];self._drain_one(name)
                        if self.stream_bytes[name]==before and not self.eof[name]:break
                need(self.eof[name],'actual pipe EOF required; unknown setup/quiescence is not EOF')
            except BaseException as error:
                if first is None:first=error
                self.retain(error,'stream_drain_'+name)
            # Popen's file object owns this fd. Clear the numeric slot first and
            # close the file object once; never double-close through DescriptorSlot.
            if name not in self.pipe_close_entered:
                self.pipe_close_entered.add(name)
                try:
                    stream=self.pipe_objects.pop(name,None)
                    # Popen is the immediate owner of BOTH pipe objects even
                    # if setup failed before the second local slot existed.
                    if stream is None and self.child is not None:stream=getattr(self.child,name)
                    if slot is not None:slot.close_entered=True;slot.fd=None
                    if stream is not None:stream.close()
                    if slot is not None:slot.closed=stream is not None
                except BaseException as error:
                    if slot is not None:slot.unknown=True
                    if first is None:first=error
                    self.retain(error,'stream_close_'+name)
        if self.pidfd is not None and not self.pidfd.close():
            error=self.pidfd.raw_first
            if error is not None:
                if first is None:first=error
                self.retain(error,'pidfd_close')
        if first is not None:raise first
        return True
