"""Full concrete public-input/tool preparation; no runtime backend callbacks."""
from dataclasses import dataclass,replace,asdict
from ..core.custody import CustodyError,digest
from ..admission import ContextSpec,prepare_context,CandidateExport
from ..context_io import capsule_io_bindings,materialize_capsules
from ..context_io.native_seal_v1 import seal_bindings,seal_public_trees,ToolTreeReceipt
from .reference import ReferenceEngine
from .public_tools import build_tool_set,tool_io_bindings,materialize_tools,IssuedReferenceTools,tool_issue_bindings,issue_reference_tools
from .candidate import PreparedCandidate

@dataclass(frozen=True)
class HostPreparation:
    """Exact future-qualified native locations/contracts for one fresh context.

    These are inputs selected by the execution operator, not discovered defaults.
    Runtime, cgroup, read-only namespace, capacity, provider and monitor evidence
    all remain independently checked by their concrete component before effects.
    """
    context_id:str
    capsule_parent:str
    capsule_name:str
    capsule_limits:object
    capsule_seal_admission:object
    guard_admission:object
    monitor_runtime:object
    provider_admission:object
    snapshot_parent:str
    snapshot_name:str
    snapshot_limits:object
    snapshot_seal_admission:object

@dataclass(frozen=True)
class ToolPreparation:
    parent:str
    name:str
    limits:object
    seal_admission:object
    model_limits:object
    public_sources:tuple


def prepare_outer_tools(engine:ReferenceEngine,outer_person,condition,*,issuer,tool_spec:ToolPreparation):
    if type(engine) is not ReferenceEngine or outer_person not in engine.outer_done:
        raise CustodyError('all required references for this outer person must complete first')
    results=tuple(r for k,r in engine.results.items() if k[0]==outer_person and k[1]==condition)
    completion=digest({'outer':outer_person,'condition':condition,'results':[r.private_descriptor() for r in results],
                       'reference_work':engine.work.receipt()})
    sources=tool_spec.public_sources
    bindings={'reference_completion_digest':completion,
        'selected_fits_digest':digest([r.private_descriptor() for r in results]),
        'public_sources_digest':digest([{'name':s.name,'sha256':s.sha256,'mode':s.mode} for s in sources]),
        'public_model_limits_digest':digest(asdict(tool_spec.model_limits))}
    token=engine.data.plan._opaque(['reference',outer_person,condition])
    tools=build_tool_set(results,condition=condition,outer_person=outer_person,source_files=sources,
        model_limits=tool_spec.model_limits,numeric_limits=engine.limits,
        authority=issuer.capability('reference_predict',token,bindings),reference_completion_digest=completion)
    io=tool_io_bindings(tools,tool_spec.parent,tool_spec.name,tool_spec.limits)
    mount,receipt=materialize_tools(tools,authority=issuer.capability('export',token,io),
        parent_path=tool_spec.parent,name=tool_spec.name,limits=tool_spec.limits)
    wrapped=ToolTreeReceipt(mount,digest(token),completion,tools.files_digest,bindings['public_sources_digest'])
    sealed=seal_public_trees(wrapped,tool_spec.seal_admission,
        authority=issuer.capability('export',token,seal_bindings(wrapped,tool_spec.seal_admission)))
    if len(sealed.mounts)!=1:raise CustodyError('single complete public reference-tool tree required')
    engine.store.append_event('public_tools_prepared',{'outer_person':outer_person,'condition':condition,
        'tool_files_digest':tools.files_digest,'materialization':receipt,'native_seal':sealed.to_dict()})
    ib=tool_issue_bindings(tools,sealed,token)
    return issue_reference_tools(tools,sealed,token,authority=issuer.capability("export",token,ib))


def prepare_candidate(engine:ReferenceEngine,context,*,issuer,export_key,host:HostPreparation,reference_tools:IssuedReferenceTools):
    if type(host) is not HostPreparation or host.context_id!=context.context_id or context not in engine.data.plan.contexts():
        raise CustodyError('one selected full-plan host context required')
    if context.outer_person not in engine.outer_done:raise CustodyError('references must complete before candidate input release')
    if type(reference_tools) is not IssuedReferenceTools:raise CustodyError("issued reference tools required")
    reference_tools.require_context(context)
    data=engine.data
    bank=data.bank(context.outer_person,engine.capacity) if context.condition=='spatial_scrambled' else None
    spec=ContextSpec(context.outer_person,context.arm,context.condition,context.repetition,context.context_id)
    plan=prepare_context(data.catalogue,data.assessment,spec,export_key,data.descriptors,
                         scramble_bank_commitment=None if bank is None else bank.commitment)
    authority=issuer.capability('export',context.context_id,plan.bindings)
    export=CandidateExport(plan=plan,assessment=data.assessment,observations=data.observations,
        original_descriptors=data.descriptors,values_by_id=None if context.condition=='C_only' else data.values_by_id,
        authority=authority,scramble_bank=bank,work=data.work)
    io=capsule_io_bindings(plan,host.capsule_parent,host.capsule_name,host.capsule_limits)
    capsule=materialize_capsules(export,plan,authority=issuer.capability('export',context.context_id,io),
        parent_path=host.capsule_parent,name=host.capsule_name,limits=host.capsule_limits)
    seal=seal_public_trees(capsule,host.capsule_seal_admission,
        authority=issuer.capability('export',context.context_id,seal_bindings(capsule,host.capsule_seal_admission)))
    mounts=tuple(seal.mounts)+(reference_tools.mount,)
    prequery=tuple(m for m in mounts if m.role!='query')
    guard=replace(host.guard_admission,context_id=context.context_id,arm=context.arm,
        initial_phase_mounts=prequery,export_allowlist_digest=digest([asdict(m) for m in prequery]))
    prepared=PreparedCandidate(context,plan,capsule,mounts,reference_tools,guard,host.monitor_runtime,
        host.provider_admission,host.snapshot_parent,host.snapshot_name,host.snapshot_limits,host.snapshot_seal_admission)
    prepared.validate()
    engine.store.append_event('candidate_prepared',{'context':context.private_dict(),'capsule':capsule.to_dict(),
        'native_seal':seal.to_dict(),'tools_digest':reference_tools.files_digest,'export_bindings':plan.bindings})
    return prepared
