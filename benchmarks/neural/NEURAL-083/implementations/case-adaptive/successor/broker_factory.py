"""Fixed captured broker dependencies and one OpenBMI adaptive context budget.

No candidate code is loaded here. Source construction does not admit native
execution, provider state, token semantics or expenditure.
"""
import hashlib
import json
from pathlib import Path
import stat
import sys
import types

PINS = {
 'morse_protocol.py': (6507,'7845ec91aaefe7907aa40066d397e98f92ef71c1725de0a419d62a32ba832ee6'),
 'morse_broker.py': (18715,'663077edcef0d84f1fa0e57cbd9f414d38e07629a260dfa4ca0316a03e776d90'),
 'morse_docker.py': (21053,'03e1287315cc0d4c90d161b39a6846f71e4f1c738d8bbbeba136fb5a85c3babd'),
 'morse_bootstrap.py': (10322,'4adf52f99621f01fa67dd4c4cbaa22bc8a72eeb832f2b5034b68c48f89067dd9'),
}
MODEL_LIMITS = ('max_calls','input_tokens','output_tokens','max_input_bytes',
                'max_messages','frame_bytes','call_seconds')
EXTRA_LIMITS = ('stdout_bytes','stderr_bytes','native_receipt_bytes')

def need(ok, message):
    if not ok:
        raise ValueError(message)

def storage_digest(value):
    """Semantic JSON digest stable under sorted native receipt serialization.

    UTF-8 encoding of sort_keys=True, compact separators, allow_nan=False and
    default ensure_ascii=True, with no trailing newline. This is distinct from
    the unchanged Morse transport's insertion-order digests.
    """
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),
                         allow_nan=False).encode('utf-8')).hexdigest()

def load_dependencies():
    """Authenticate only these captured project modules; no sys.path search."""
    root=Path(__file__).absolute().parent/'dependencies'
    bodies={}
    for name,(size,sha) in PINS.items():
        path=root/name
        need(not any(p.is_symlink() for p in (path,*path.parents)), 'Unlinked broker dependency')
        info=path.stat()
        need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_size==size,
             'Exact ordinary broker dependency')
        with path.open('rb') as stream:
            body=stream.read(size+1)
        need(len(body)==size and hashlib.sha256(body).hexdigest()==sha, 'Broker dependency pin')
        bodies[name]=body
    modules={}
    names=('morse_protocol','morse_broker','morse_docker')
    absent=object()
    prior={name:sys.modules.get(name,absent) for name in names}
    try:
        for name in names:
            path=root/(name+'.py')
            module=types.ModuleType(name)
            module.__file__=str(path)
            sys.modules[name]=module
            exec(compile(bodies[name+'.py'],str(path),'exec'),module.__dict__)
            modules[name]=module
    finally:
        # Fresh captured definitions bind each other's fresh objects. A matching
        # __file__ is never accepted as authentication of prior module globals.
        # The selected controller constructs contexts sequentially, after prior
        # workers/broker threads have closed.
        for name,old in prior.items():
            if old is absent:
                sys.modules.pop(name,None)
            else:
                sys.modules[name]=old
    return modules

def minimum_receipt_bytes(limits):
    # Native CLI receipt allowance + full model frames and hash summaries +
    # base64 stderr. 6x conservatively covers ensure_ascii JSON serialization;
    # this is a byte reservation, never a claim of actual use.
    return (262144+limits['max_calls']*(12*limits['frame_bytes']+8192)
            +4*((limits['stderr_bytes']+2)//3))

class ContextBroker:
    """Shared context allocation, fresh phase-bound broker/engine per worker.

    The optional engineering engine factory is only for explicitly invented
    controls and is refused by the native phase. Production has no default
    model, endpoint, token limit or stream/receipt budget.
    """
    mode='case_adaptive'

    def __init__(self, model_spec, context_id, limits, token_admission, *,
                 engineering_engine_factory=None):
        self.modules=load_dependencies()
        m=self.modules['morse_broker']
        m.exact(limits, MODEL_LIMITS+EXTRA_LIMITS, 'OpenBMI adaptive context limits')
        m.validate_broker_limits({k:limits[k] for k in MODEL_LIMITS})
        for k in EXTRA_LIMITS:
            m.integer(limits[k],k)
        need(limits['native_receipt_bytes']>=minimum_receipt_bytes(limits),
             'Full transcript/stderr/native receipt reservation')
        need(type(context_id)is str and bool(context_id), 'Explicit context identity')
        self.spec=json.loads(m.canonical(m.validate_model_spec(model_spec)))
        self.context_id=context_id
        self.limits=dict(limits)
        self.token_admission=token_admission
        self._engineering=engineering_engine_factory
        self.path='engineering_injected_engine' if engineering_engine_factory else 'real_future_https_child'
        self._used={k:0 for k in ('max_calls','input_tokens','output_tokens')}
        self._active=None
        self._phases=[]
        self._failed=False
        self._unresolved=[]
        self._unobserved_threads=set()

    def begin_phase(self, kind):
        expected='fit' if not self._phases else 'infer'
        need(kind in ('fit','infer') and kind==expected and len(self._phases)<2
             and self._active is None and not self._failed, 'Fresh ordered adaptive stage')
        m=self.modules['morse_broker']
        remaining={k:self.limits[k] for k in MODEL_LIMITS}
        for key,used in self._used.items():
            remaining[key]-=used
            need(remaining[key]>0, 'Context model reservation exhausted before next stage')
        if self._engineering is None:
            engine=m.HttpsJsonEngine(self.spec,token_admission=self.token_admission)
        else:
            engine=self._engineering(kind)
            need(getattr(engine,'kind',None)=='engineering_injected_engine', 'Explicit invented engine')
        phase={'fit':'train','infer':'query'}[kind]
        active=m.ModelBroker(engine,self.context_id,phase,remaining,self.spec)
        self._active=(kind,active)
        return active

    def finish_phase(self, kind, *, successful, broker_thread_terminal=None):
        need(type(successful)is bool and self._active is not None and self._active[0]==kind,
             'Exact active adaptive stage closure')
        need(broker_thread_terminal is None or type(broker_thread_terminal)is bool,
             "Typed observed broker-thread terminal state")
        active=self._active[1]
        thread_terminal=broker_thread_terminal is True
        if not thread_terminal:
            # A thread can be alive before generate assigns a child handle.
            # The pump exposes no joinable thread handle after returning; this
            # uncertainty stays sticky until the external supervisor terminates
            # the owning worker. Child-terminal alone cannot settle it.
            self._unobserved_threads.add(kind)
        cancel_error=None
        try:
            active.cancel()
        except Exception as error:
            cancel_error=type(error).__name__
        usage=active.receipt()
        transcript=active.private_transcript()
        for key,field in (('max_calls','calls'),('input_tokens','input_tokens_reserved'),
                          ('output_tokens','output_tokens_reserved')):
            self._used[key]+=usage[field]
            need(self._used[key]<=self.limits[key], 'Shared context budget exceeded')
        terminal=usage['model_child_terminal'] is True if self._engineering is None else None
        if not thread_terminal or self._engineering is None and terminal is not True:
            # Preserve actual owned handles for further cancellation; a failed
            # terminal observation must never turn into a discarded resource.
            self._unresolved.append((kind,active))
        good=successful and thread_terminal and cancel_error is None and not usage['failed'] and (terminal is True or self._engineering is not None)
        m=self.modules['morse_broker']
        summary={'kind':kind,'phase':usage['phase'],'context_id':self.context_id,
                 'successful':bool(good),'usage':usage,'transcript_sha256':m.digest(transcript),
                 'transcript_storage_sha256':storage_digest(transcript),
                 'transport_digest_semantics':'Morse insertion-order JSON; not recomputable from sorted stored objects',
                 'model_child_terminal':terminal,'broker_thread_terminal':thread_terminal,'cancel_error':cancel_error}
        self._phases.append(summary)
        self._failed=not good
        self._active=None
        return dict(summary,private_transcript=transcript,transcript_custody='host-private; never publish by default')

    def final_receipt(self):
        need(self._active is None, 'Active model stage has not closed')
        return {'context_id':self.context_id,'mode':self.mode,'engine_path':self.path,
                'model_spec_sha256':self.modules['morse_broker'].digest(self.spec),
                'model_spec_storage_sha256':storage_digest(self.spec),
                'transport_digest_semantics':'Morse insertion-order JSON; not recomputable from sorted stored objects',
                'limits':dict(self.limits),'reserved':dict(self._used),
                'phases':json.loads(self.modules['morse_broker'].canonical({'items':self._phases}))['items'],
                'complete':len(self._phases)==2 and not self._failed and not self._unresolved and not self._unobserved_threads,
                'unresolved_model_children':len(self._unresolved),
                'unobserved_broker_thread_phases':sorted(self._unobserved_threads),
                'native_qualification':False,'provider_state_qualification':False,
                'scientific_qualification':False}

    def retry_unresolved_cleanup(self):
        """Retry only retained owned model handles; never changes failed status."""
        retained=[]
        observations=[]
        for kind,active in self._unresolved:
            error=None
            try:
                active.cancel()
            except Exception as exc:
                error=type(exc).__name__
            terminal=active.engine.terminal_observed()
            observations.append({'kind':kind,'terminal_observed':terminal,
                                 'broker_thread_terminal_unobserved':kind in self._unobserved_threads,
                                 'cancel_error':error})
            if terminal is not True or kind in self._unobserved_threads:
                retained.append((kind,active))
        self._unresolved=retained
        return observations

    def invalidate_native_phase(self, kind):
        """Trusted lifecycle failure after model closure still poisons context."""
        need(self._active is None and self._phases and self._phases[-1]['kind']==kind,
             'Exact closed stage for native failure')
        self._phases[-1]['successful']=False
        self._phases[-1]['native_lifecycle_failed']=True
        self._failed=True

    def stream_read_reservation(self):
        # Captured pump reads at most one 64KiB overshoot chunk before refusal.
        return self.limits['stdout_bytes']+self.limits['stderr_bytes']+131072

    def model_child_read_reservation(self):
        """Conservative per-stage provider-child bytes; shared calls may use less."""
        return self.limits['max_calls']*(self.spec['response_max_bytes']+
               self.spec['stderr_max_bytes']+131072)

    def pump_limits(self, wall_seconds):
        self.modules['morse_broker'].positive(wall_seconds,'remaining producer wall')
        return {'frame_bytes':self.limits['frame_bytes'],'wall_seconds':wall_seconds,
                'stdout_bytes':self.limits['stdout_bytes'],'stderr_bytes':self.limits['stderr_bytes']}
