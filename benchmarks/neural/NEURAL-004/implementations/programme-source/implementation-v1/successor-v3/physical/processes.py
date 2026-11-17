"""Real small Python process controls; no authentic operation or sandbox claim."""
import os
import selectors
import subprocess
import time
from pathlib import Path
from .wire import need, integer, body_pin, Refusal

class ProcessFailure(Refusal):
    def __init__(self, message, receipt):super().__init__(message);self.receipt=receipt

def capture_process(argv, cwd, ledger, origin, deadline, stdout_cap, stderr_cap, *, env=None, stdin=None):
    """Capture bounded actual pipes, preserving failures and original cutoffs.

    Caller supplies source-bound argv and ownership. This never certifies an
    arbitrary executable, full process group, sandbox, RSS or all I/O. It kills
    only an unreaped owned direct child; no post-reap process-group signal.
    """
    need(origin==ledger.origin and deadline==ledger.scientific,'original process clock identity')
    integer(stdout_cap,1);integer(stderr_cap,1)
    need(type(argv) is list and argv and all(type(x) is str and '\0' not in x for x in argv),'concrete argv')
    ledger.reserve({'processes':1},'process launch')
    lease=ledger.acquire_live(2*(stdout_cap+stderr_cap+2),'bounded stream buffers')
    process=None;selector=selectors.DefaultSelector();buffers={'stdout':bytearray(),'stderr':bytearray()}
    caps={'stdout':stdout_cap,'stderr':stderr_cap};forced=False;error=None;eof=set();began=None
    try:
        ledger.tick();began=ledger.clock()
        process=subprocess.Popen(argv,cwd=cwd,env=env,stdin=subprocess.DEVNULL if stdin is None else stdin,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,close_fds=True)
        for name in buffers:
            stream=getattr(process,name);os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,name)
        while selector.get_map() or process.poll() is None:
            ledger.tick()
            for key,_ in selector.select(min(.05,max(0,(deadline-ledger.clock())/1e9))):
                name=key.data;remaining=caps[name]-len(buffers[name])
                extent=min(65536,remaining+1)
                ledger.reserve({'read_bytes':extent,'retained_bytes':extent},'attempted bounded '+name+' read')
                block=os.read(key.fileobj.fileno(),extent)
                if not block:
                    selector.unregister(key.fileobj);eof.add(name);continue
                buffers[name].extend(block)
                need(len(block)<=remaining,name+' output cap')
        exit_code=process.wait();ledger.tick()
        need(exit_code==0,'nonzero child exit')
    except BaseException as exc:
        error=exc;ledger.fail('process',exc)
        if process is not None and process.poll() is None:
            # Popen owns an unreaped child PID; never signal a reaped group.
            try:process.kill();forced=True
            except BaseException as cleanup:ledger.fail('direct child kill',cleanup)
        if process is not None:
            try:
                while process.poll() is None:
                    ledger.tick('closeout');time.sleep(.005)
            except BaseException as cleanup:ledger.fail('direct child closeout',cleanup)
    finally:
        for key in list(selector.get_map().values()):
            try:key.fileobj.close()
            except BaseException as cleanup:ledger.fail('stream close',cleanup)
        selector.close()
        if process is not None:
            for name in buffers:
                try:getattr(process,name).close()
                except BaseException as cleanup:ledger.fail('stream close',cleanup)
    receipt={'argv':argv,'started_ns':began,'finished_ns':ledger.clock(),'origin_ns':origin,'deadline_ns':deadline,
        'exit_code':None if process is None else process.returncode,'natural_exit':process is not None and
        process.returncode is not None and not forced,'forced_stop':forced,'stream_eof':eof==set(buffers),
        'stdout':bytes(buffers['stdout']),'stderr':bytes(buffers['stderr']),
        'all_descendants_closed':False,'unknown_foreign_custody':True,'view_isolation_verified':False,
        'resources_complete':False,'resource_report':ledger.report(),'physical_or_scientific_qualified':False}
    ledger.release_live(lease)
    if error is not None:raise ProcessFailure(type(error).__name__+': '+str(error),receipt) from error
    return receipt

class ControlHarness:
    def __init__(self, store, ledger, *, stdout_cap=65536, stderr_cap=65536):
        need(store.ledger is ledger,'same control ledger');self.store=store;self.ledger=ledger
        self.stdout_cap=integer(stdout_cap,1);self.stderr_cap=integer(stderr_cap,1)

    def run(self, context, source, python_executable, origin, deadline, *, files=None):
        need(type(source) is bytes and len(source)<=65536,'small invented control source')
        need(Path(python_executable).is_absolute(),'explicit Python executable')
        files={} if files is None else files
        need(type(files) is dict and 'control.py' not in files and sum(len(v) for v in files.values())<=65536,
             'small invented auxiliary files')
        self.store.stage(context,{**files,'control.py':source});self.store.seal(context)
        before=self.store.contexts[context]['control.py']
        result=capture_process([python_executable,'-I','-S','-B','control.py'],str(self.store.context_path(context)),
            self.ledger,origin,deadline,self.stdout_cap,self.stderr_cap,env={})
        self.store.seal(context)
        result.update(control_only=True,source_pin=before,context=context,
                      native_closure_acceptable=False,authentic_execution_acceptable=False)
        return result
