"""Concrete F/I controller. All native/provider calls remain separately gated.

This module never reads source datasets, keys or credentials. Its explicit
prepared operands are trusted-host typed products. Candidate actions are only
argv/path JSON; neither model output nor candidate code runs in this process.
"""
from dataclasses import dataclass,asdict
import hashlib,io,os,stat,time,json
from ..core.custody import CustodyError,canonical,digest,require_digest
from ..core.outcomes import ProcessOutcome,AggregateOutcome
from ..core.artifact_outcomes import CandidateArtifactFailure
from ..core.inference import require_applied_inference,validate_generation_record
from ..core.plan import CandidateContext
from ..core.phase_v2 import ContextStateV2
from ..core.resources import ResourceLedger,CandidateCaps,BudgetExceeded
from ..context_io import CapsuleReceipt,SnapshotReceipt
from ..context_io.snapshot import snapshot_io_bindings,snapshot_program
from ..context_io.native_seal_v1 import seal_bindings,seal_public_trees
from ..process_guard.contracts import validate_mounts
from ..admission.export import ExportPlan
from ..private_store import PrivateRunStore
from .. import scoring
from .authority import RoleIssuer
from .policy import Policy,parse_action
from .public_tools import IssuedReferenceTools

class InfrastructureIncident(RuntimeError):
    pass

class CandidateFailure(RuntimeError):
    pass

def consume_process_outcome(outcome,context_id):
    """Actual runner consumer: typed diagnostics must qualify before capture use."""
    if type(outcome) is not ProcessOutcome:raise InfrastructureIncident('typed process outcome required')
    outcome.require_scoreable()
    row=outcome.original_receipt
    if row['context_id']!=context_id:raise InfrastructureIncident('process outcome context mismatch')
    return row


def consume_aggregate_outcome(outcome,context_id):
    """Actual runner consumer; no scoreable closure from a diagnostic mapping."""
    if type(outcome) is not AggregateOutcome:raise InfrastructureIncident('typed aggregate outcome required')
    outcome.require_scoreable()
    row=outcome.original_receipt
    if row['context_id']!=context_id:raise InfrastructureIncident('aggregate outcome context mismatch')
    return row,outcome.classification=='candidate_failure'


def context_inference_records(context,policy,records,*,seen_draw_ids=()):
    """Rejoin actual recorded settings and globally unique independent draws.

    Pure validation does not prove provider behavior. Actual adapter admission and
    original records remain required; callers never manufacture missing records.
    """
    if type(records) is not list:raise CustodyError('original generation record list required')
    expected=policy.inference_policy.binding_for(context.repetition)
    seen=set(seen_draw_ids);request_ids=set();actual=[]
    for row in records:
        if type(row) is not dict or set(row)!={'request_id','request_digest','applied_inference','generation_inference','failed'}:
            raise CustodyError('closed actual generation inference record')
        rid=row['request_id']
        if type(rid) is not str or not rid or rid in request_ids:raise CustodyError('unique original context request required')
        request_ids.add(rid);require_digest(row['request_digest'])
        require_applied_inference(row['applied_inference'],expected)
        record=validate_generation_record(row['generation_inference'],binding=expected,
            context_id=context.context_id,request_id=rid,failed=row['failed'],seen_draw_ids=seen)
        if record['draw_id'] is not None:seen.add(record['draw_id'])
        actual.append(json.loads(canonical(row)))
    return actual,seen


@dataclass(frozen=True)
class PreparedCandidate:
    context:CandidateContext
    export_plan:ExportPlan
    capsule:CapsuleReceipt
    readonly_mounts:tuple
    reference_tools:IssuedReferenceTools
    guard_admission:object
    monitor_runtime:object
    provider_admission:object
    snapshot_parent:str
    snapshot_name:str
    snapshot_limits:object
    snapshot_seal_admission:object

    @property
    def tools_digest(self):return self.reference_tools.files_digest

    def validate(self):
        if type(self.context) is not CandidateContext or type(self.export_plan) is not ExportPlan or type(self.capsule) is not CapsuleReceipt:
            raise CustodyError('exact context/export/capsule products required')
        self.export_plan.require_issued()
        from ..process_guard.aggregate_v3 import MonitorRuntime
        if type(self.monitor_runtime) is not MonitorRuntime:raise CustodyError('exact monitor runtime and OOM witness admission required')
        self.monitor_runtime.validate()
        c=self.context;e=self.export_plan.context
        if (c.outer_person,c.arm,c.condition,c.repetition)!=(e.outer_person,e.arm,e.condition,e.repetition):
            raise CustodyError('prepared context mismatch')
        if self.export_plan.authority_domain!='authentic' or self.capsule.domain!='authentic':
            raise CustodyError('native candidate requires complete authentic admission')
        if self.capsule.context_digest!=e.fingerprint or dict(self.capsule.plan_bindings)!=self.export_plan.bindings:
            raise CustodyError('capsule differs from issued source export')
        if self.guard_admission.context_id!=c.context_id or self.guard_admission.arm!=c.arm or self.provider_admission.context_id!=c.context_id:
            raise CustodyError('native/provider context identity mismatch')
        if type(self.reference_tools) is not IssuedReferenceTools:raise CustodyError('actual issued reference tools required')
        self.reference_tools.require_context(c)
        capsule_members=dict(self.capsule.role_members)
        for mount in self.readonly_mounts:
            if mount.role=='reference_tools':
                if mount!=self.reference_tools.mount:raise CustodyError('mounted tools differ from issued outer/condition tools')
            elif mount.role not in capsule_members or mount.members!=capsule_members[mount.role]:
                raise CustodyError('sealed public input members differ from this exact capsule')
        roles=[m.role for m in self.readonly_mounts]
        if sorted(roles)!=sorted(('knowledge','training','query','reference_tools')):
            raise CustodyError('exact prepared public role set required')
        validate_mounts(self.mounts('prequery'),phase='prequery',arm=c.arm)
        if tuple(self.guard_admission.initial_phase_mounts)!=self.mounts('prequery'):
            raise CustodyError('guard admission must bind exact prepared prequery mounts')

    def mounts(self,phase,program=None):
        result=tuple(m for m in self.readonly_mounts if phase=='query' or m.role!='query')
        if program is not None:result+=(program,)
        return result


def _capture_open(guard,outcome,index):
    """Read only an actual guard-owned unmounted capture, never a model path."""
    if (index not in (0,1) or type(outcome) is not dict or
        sum(canonical(outcome)==canonical(row) for row in guard.receipts)!=1):
        raise InfrastructureIncident('original owned process outcome required')
    path=outcome['captures'][index]
    expected_root=str(guard.root/'capture')
    if os.path.dirname(path)!=expected_root or not outcome['capture_complete']:
        raise InfrastructureIncident('complete owned capture required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    st=os.fstat(fd)
    name=('stdout','stderr')[index]
    if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1 or st.st_uid!=os.geteuid() or st.st_size!=outcome['capture_bytes'][name]:
        os.close(fd);raise InfrastructureIncident('owned capture identity/extent')
    return os.fdopen(fd,'rb')


def observation(guard,outcome,offset,maximum,frame_cap):
    if type(offset) is not int or offset<0 or type(maximum) is not int or not 1<=maximum<=frame_cap:
        raise CandidateFailure('observation window exceeds the qualified framing capacity')
    result={'returncode':outcome['returncode'],'termination':outcome['termination'],
            'capture_complete':outcome['capture_complete'],'streams':{}}
    for i,name in enumerate(('stdout','stderr')):
        with _capture_open(guard,outcome,i) as stream:
            stream.seek(offset);body=stream.read(maximum)
        result['streams'][name]={'offset':offset,'bytes':len(body),'total_bytes':outcome['capture_bytes'][name],
            'text_utf8_replacement':body.decode('utf-8',errors='replace'),
            'complete_window':offset+len(body)>=outcome['capture_bytes'][name]}
    return result


class CandidateRunner:
    def __init__(self,*,prepared:PreparedCandidate,issuer:RoleIssuer,policy:Policy,store:PrivateRunStore):
        if type(prepared) is not PreparedCandidate or type(issuer) is not RoleIssuer or type(policy) is not Policy or type(store) is not PrivateRunStore:
            raise CustodyError('concrete prepared products, issuer, policy and private store required')
        prepared.validate()
        policy.require_adapter(prepared.provider_admission,prepared.context)
        if issuer.domain!='authentic' or store.domain!='authentic':raise CustodyError('authentic candidate execution selection required')
        store.assert_private_boundary([m.source for m in prepared.readonly_mounts]+[prepared.snapshot_parent])
        self.p,self.issuer,self.policy,self.store=prepared,issuer,policy,store
        self.context=prepared.context;self.state=ContextStateV2(self.context)
        self.ledger=None;self.guard=None;self.adapter=None;self.closed=False;self.started=False
        self.original_incidents=[];self.broker_closure=None

    def cap(self,role,bindings):
        return self.issuer.capability(role,self.context.context_id,bindings)

    def _guard_cap(self,role,*,mounts=None,argv=None,snapshot=None):
        bindings=dict(self.guard.bindings)
        if mounts is not None:bindings['phase_mounts_digest']=digest([asdict(m) for m in mounts])
        if argv is not None:bindings['argv_digest']=digest(list(argv))
        if self.state.state=='query_open':
            bindings['freeze_barrier_digest']=self.guard.freeze_receipt['receipt_digest']
        if snapshot is not None:bindings.update({k:v for k,v in snapshot.to_dict().items()
            if k in ('snapshot_digest','program_manifest_digest','entry_digest','runtime_digest')})
        return self.cap(role,bindings)

    def _provider_cap(self,role):return self.cap(role,self.adapter.bindings)

    def _run(self,argv,phase,mounts,*,snapshot=None):
        request=self.context.context_id+':tool:'+str(self.ledger.tool_calls+1)
        role='candidate_author' if phase=='prequery' else 'candidate_query'
        outcome=self.guard.run(authority=self._guard_cap(role,mounts=mounts,argv=argv,snapshot=snapshot),
            phase=phase,mounts=mounts,argv=tuple(argv),request_id=request)
        self.store.append_event('candidate_process_original',outcome.to_dict())
        return consume_process_outcome(outcome,self.context.context_id)

    def _empty(self):
        return scoring.parse_jsonl(io.BytesIO(b''),tuple(row[0] for row in self.p.export_plan.query_map))

    def _parse(self,outcome):
        with _capture_open(self.guard,outcome,0) as stream:
            parsed=scoring.parse_jsonl(stream,tuple(row[0] for row in self.p.export_plan.query_map))
        parsed['original_process_outcome_digest']=outcome['receipt_digest']
        return parsed

    def _close_broker(self):
        if self.adapter is None or self.broker_closure is not None:return
        # Concrete guard evidence, not an exception string, determines whether a
        # live protocol goodbye is possible. Settled exhaustion uses owned drain.
        if self.guard.exhaustion_pending() or self.adapter.lifecycle=='exhausted':
            self.broker_closure=self.adapter.close_exhausted(authority=self._provider_cap('close'))
        elif self.adapter.lifecycle=='open':
            self.broker_closure=self.adapter.close(authority=self._provider_cap('close'))
        else:
            raise InfrastructureIncident('unstarted/failed broker lacks qualified closure')
        self.store.append_event('broker_original_close',self.broker_closure.to_dict())

    def run(self):
        if self.started:raise CustodyError('candidate invocation is single-use, including failures')
        self.started=True
        # Imports are concrete source modules, never caller-provided launchers.
        from ..process_guard.aggregate_v3 import AggregateGuardContextV3,guard_required_bindings
        from ..provider_transport.cgroup_v2 import CgroupModelAdapterSessionV2,provider_required_bindings
        self.ledger=ResourceLedger(context_id=self.context.context_id,started_monotonic_ns=time.monotonic_ns())
        self.state.prepare(self.p.capsule.receipt_digest,self.p.tools_digest)
        self.state.begin_authoring(self.policy.binding_digest)
        payload=self.policy.initial(self.context.public_dict())
        parsed=None;candidate_failure=None;snapshot_binding=None;program_mount=None
        try:
            gb=guard_required_bindings(self.p.guard_admission,self.p.monitor_runtime,self.ledger.caps)
            self.guard=AggregateGuardContextV3(self.p.guard_admission,monitor_runtime=self.p.monitor_runtime,
                authority=self.cap('candidate_author',gb),ledger=self.ledger)
            self.guard.prepare()
            pb=provider_required_bindings(self.p.provider_admission,self.state,self.ledger)
            pa=self.cap('candidate_author',pb)
            lease=self.guard.issue_broker_lease(self.p.provider_admission,self.state,pa)
            self.adapter=CgroupModelAdapterSessionV2(self.p.provider_admission,authority=pa,
                state=self.state,ledger=self.ledger,broker_lease=lease)
            self.adapter.start()
            while parsed is None:
                self.state.allow_model_call()
                role='candidate_query' if self.state.state=='query_open' else 'candidate_author'
                remaining=self.ledger.caps.output_tokens-self.ledger.output_tokens
                if remaining<=0:raise CandidateFailure('aggregate model output allowance exhausted')
                result=self.adapter.generate(payload,max_output_tokens=min(self.policy.max_response_tokens,remaining),authority=self._provider_cap(role))
                self.store.append_event('candidate_model_original',result)
                if result['failed']:raise InfrastructureIncident('original model provider failure')
                try:action=parse_action(result['response'],arm=self.context.arm,phase=self.state.state)
                except CustodyError as exc:raise CandidateFailure('invalid candidate action: '+str(exc)) from exc
                payload['messages'].append({'role':'assistant','action':action})
                if action['action']=='exec':
                    phase='query' if self.state.state=='query_open' else 'prequery'
                    out=self._run(action['argv'],phase,self.p.mounts(phase))
                    if out['termination'].startswith('candidate_'):raise CandidateFailure(out['termination'])
                    obs=observation(self.guard,out,action['observation_offset'],action['observation_bytes'],self.p.provider_admission.max_frame_bytes)
                    payload['messages'].append({'role':'tool','observation':obs})
                elif action['action']=='open_query':
                    barrier=self.guard.freeze_barrier(authority=self._guard_cap('candidate_author'))
                    self.store.append_event('i_prequery_barrier',barrier)
                    self.state.open_query(digest([asdict(m) for m in self.p.mounts('query')]))
                    payload['messages'].append({'role':'tool','query_open':True})
                elif action['action']=='seal':
                    # F closes its actual broker and every descendant before the
                    # typed candidate barrier; no model call can follow this point.
                    self._close_broker()
                    capability=self.guard.freeze_barrier(authority=self._guard_cap('candidate_author'),broker_closure=self.broker_closure)
                    lease=self.guard.begin_snapshot(capability)
                    entry='work/'+action['entry']
                    sb=snapshot_io_bindings(context_digest=lease.context_digest,runtime_digest=lease.runtime_manifest_digest,
                        parent_path=self.p.snapshot_parent,name=self.p.snapshot_name,entry_relative_path=entry,limits=self.p.snapshot_limits)
                    snap,snapshot_binding=snapshot_program(lease,authority=self.cap('candidate_author',sb),
                        parent_path=self.p.snapshot_parent,name=self.p.snapshot_name,entry_relative_path=entry,limits=self.p.snapshot_limits)
                    sealed=seal_public_trees(snap,self.p.snapshot_seal_admission,
                        authority=self.cap('candidate_author',seal_bindings(snap,self.p.snapshot_seal_admission)))
                    if len(sealed.mounts)!=1:raise InfrastructureIncident('one complete F program mount required')
                    program_mount=sealed.mounts[0]
                    self.store.append_event('f_actual_snapshot',{'snapshot':snap.to_dict(),'native_seal':sealed.to_dict(),'binding':snapshot_binding.to_dict()})
                    self.state.seal_program(snap.receipt_digest)
                    mounts=self.p.mounts('query',program_mount)
                    self.state.open_query(digest([asdict(m) for m in mounts]))
                    argv=('/program/'+entry,*action['argv_suffix'])
                    out=self._run(argv,'query',mounts,snapshot=snapshot_binding)
                    parsed=self._parse(out)
                    if out['returncode']!=0 or out['termination']!='natural':candidate_failure='frozen_program_'+out['termination']
                else:
                    # cat runs inside the same actual sandbox, keeping the
                    # untrusted output path out of the trusted host filesystem.
                    out=self._run(('/usr/bin/cat','--','/work/'+action['output']),'query',self.p.mounts('query'))
                    parsed=self._parse(out)
                    if out['returncode']!=0 or out['termination']!='natural':candidate_failure='candidate_submission_'+out['termination']
        except (CandidateFailure,BudgetExceeded,CandidateArtifactFailure) as exc:
            candidate_failure=type(exc).__name__+': '+str(exc)
            parsed=self._empty() if parsed is None else parsed
            self.store.append_event('candidate_failure',{'context':self.context.context_id,'reason':candidate_failure,
                'original_evidence':getattr(exc,'evidence',None),'full_expected_query_cases':len(self.p.export_plan.query_map)})
        except BaseException as exc:
            incident={'type':type(exc).__name__,'message':str(exc),'context':self.context.context_id,
                      'evidence':getattr(exc,'evidence',None),'classification':'qualification_invalid'}
            self.original_incidents.append(incident)
            self.store.append_event('candidate_infrastructure_incident',incident)
        finally:
            # Preserve every original close failure; no synthetic successful
            # closure can substitute for unresolved usage or native survivors.
            try:self._close_broker()
            except BaseException as exc:self.original_incidents.append({'close':'broker','type':type(exc).__name__,'message':str(exc)})
            guard_close=None
            if self.guard is not None:
                try:
                    outcome=self.guard.close(authority=self._guard_cap('close'))
                    self.store.append_event('guard_original_close',outcome.to_dict())
                    guard_close,exhausted=consume_aggregate_outcome(outcome,self.context.context_id)
                    if exhausted and candidate_failure is None:candidate_failure='qualified_aggregate_exhaustion'
                except BaseException as exc:self.original_incidents.append({'close':'guard','type':type(exc).__name__,'message':str(exc)})
            if self.original_incidents:
                self.store.append_event('context_invalid_originals',{'context':self.context.context_id,'incidents':self.original_incidents})
                raise InfrastructureIncident('context has original infrastructure/closure incidents; no qualified score')
        mapping={opaque:rid for opaque,rid,label in self.p.export_plan.query_map}
        bound=scoring.bind_submission(parsed,mapping,expected_private_ids=tuple(mapping.values()),expected_mapping_digest=digest(mapping))
        prediction_digest=digest(bound)
        resources=self.ledger.close(final_monotonic_ns=time.monotonic_ns(),final_meter_digest=guard_close['receipt_digest'])
        if resources['violation'] is not None and candidate_failure is None:candidate_failure='qualified_resource_exhaustion'
        records,_=context_inference_records(self.context,self.policy,self.adapter.generation_inference_records)
        if candidate_failure:self.state.candidate_failure(prediction_digest,candidate_failure,digest(self.guard.receipts))
        else:self.state.submit(prediction_digest)
        closure=self.state.close(resources['receipt_digest'])
        final={'schema':'n073_candidate_context_original_v1','context':self.context.private_dict(),
            'submission':bound,'resources':resources,'phase_events':self.state.events,'closure_digest':closure,
            'candidate_failure':candidate_failure,'feedback_returned_to_candidate':False,
             'inference_binding':self.p.provider_admission.inference_binding,'generation_inference_records':records}
        self.store.put_json('candidate_'+self.context.context_id,final)
        self.closed=True
        return final
