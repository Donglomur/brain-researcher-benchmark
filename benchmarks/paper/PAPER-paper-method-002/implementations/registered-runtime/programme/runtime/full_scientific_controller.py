"""Concrete future full-family source launcher; not a benchmark qualification issuer.

A real external operator/native qualification owner is still required. CPU-only
sandbox support cannot silently stand in for the required A100/GPU experiments.
Legacy per-unit/source-only2MiB admission remains unchanged.
"""
import os
from .strict import Root,Clock,require,canonical_bytes,digest
from .full_scientific_authority import FullAuthority
from .full_scientific_bindings import Captures,Failures
from .views import verify_tree
from .dataflow import materialize
from .sandbox import Cgroup
from .full_scientific_command import command
from .process import launch_observe
from .costs import Ledger
from .full_scientific_collection import collect_full
from scientific.campaign import compile_campaign

class SourceLedger(Ledger):
    """Retain raw exceptions before diagnostics; never invoke their formatting."""
    def __init__(self,clock,limits):
        super().__init__(clock,limits);self.raw_failures=[]
    def finish(self,key,status,observation=None,error=None):
        if error is not None:self.raw_failures.append(error)
        row=super().finish(key,status,observation,None)
        if error is not None:row['error_type']=type(error).__name__
        return row
    def retain(self,root,name):
        record=self.record()
        record['interval_includes_preparation_collection_scoring_and_failures']=False
        record['scope']='full scientific source reference capture; scoring not performed'
        record['native_whole_lifecycle_qualification']='external; declared metadata is not proof'
        return root.write_new(name,canonical_bytes(record),self.ceiling['cost_record_bytes'],clock=self.clock,cleanup=True)

def _publish_failure(evidence,owner,captures,global_limits,clock):
    # Projection itself can fail; the caller catches it after retaining the
    # original body error rather than evaluating this as an attempt argument.
    body=canonical_bytes({'status':'failed','error_types':[type(e).__name__ for e in owner.errors],
                          'complete_captured_prefix':list(captures.summary())})
    return evidence.write_new('full-scientific-source-failure.json',body,global_limits['report_bytes'],clock=clock,cleanup=True)

def _execute(authority,stage,job,upstream,edges,generated,evidence,ledger,clock):
    require(type(authority)is FullAuthority,'original protected full-route operator owner')
    producer=authority.producer(stage['producer_id'])
    require(producer['kind']=='native_reference'and producer['source']==stage['source_pin'],'actual selected reference source')
    require(stage['source_pin']['sha256']==job['producer_source_sha256'],'fixed complete driver source')
    require(stage['output_contract']==job['output_contract']and producer['output_contract']==job['output_contract'],'full output contract before launch')
    require(stage['route']==job['route']=='prospective_full_scientific_source_v1','explicit separate route')
    rootspec=stage['roots'];require(set(rootspec)=={'rootfs','program','inputs','output'},'actual mount roles')
    paths=list(rootspec.values())+[authority.receipt['target_root'],evidence.path]
    require(len(set(paths))==len(paths),'source/target/output root collision')
    for a in paths:
        for b in paths:require(a==b or not b.startswith(a+'/'),'nested private/public native roots')
    deployment=authority.receipt['deployment'];require(rootspec['rootfs']==deployment['rootfs'],'qualified dependency image')
    key=job['job_id'];observation=None;result=None;owner=Failures();ledger.begin(key,'full source family reference')
    try:
        roots={}
        for k,path in rootspec.items():roots[k]=owner.own(Root(path,private=k in('inputs','output')))
        require(not os.listdir(roots['output'].fd),'exclusive empty whole-family output root')
        # The controller derives every dynamic edge from its original capture
        # registry. Operator stage metadata cannot substitute another parent.
        require(stage['actual_parent_keys']==list(upstream),'exact actual predecessor set/order')
        derived_stage={**stage,'role':'native_reference','upstream_inputs':edges}
        dynamic=materialize(derived_stage,upstream,roots['inputs'],clock=clock,ledger=ledger,cap=deployment['mount_byte_cap'])
        for path,body in generated:
            row=roots['inputs'].write_new(path,body,job['producer_limits']['input_member_bytes'],clock=clock)
            dynamic.append(row);ledger.charge(output_bytes=row['bytes'])
        external=[{k:r[k]for k in('path','bytes','sha256')}for r in job['native_inputs']if r['origin']=='external_sealed_input']
        require(stage['input_manifest']==external,'only complete original external inputs before generated artifacts')
        invocation={'schema':'jaxley_full_scientific_invocation_v1','kind':'native_reference','scientific_job':job,'source':stage['source_pin']}
        body=canonical_bytes(invocation)
        invocation_pin=roots['inputs'].write_new('invocation.json',body,job['metadata_limits']['invocation_bytes'],clock=clock)
        ledger.charge(output_bytes=invocation_pin['bytes'])
        for role in('program','inputs'):
            manifest=stage['program_manifest']if role=='program'else[ *external,*dynamic,invocation_pin]
            inv=verify_tree(roots[role],manifest,byte_cap=deployment['mount_byte_cap'],file_cap=deployment['mount_file_cap'],clock=clock)
            ledger.charge(read_bytes=inv['authenticated_bytes'])
        require(stage['program_manifest']==authority.receipt['full_scientific_program_tree'],'whole fixed native source tree')
        limits=job['resource_limits'];require(limits==stage['resource_limits'],'same complete resource grant')
        args,fds=command({**deployment['sandbox'],**producer['sandbox_binding']},roots,job,stage['source_pin'],clock)
        # FD numbers vary at runtime; exact argv is derived above from the held
        # descriptors and closed immutable binding, never a precomputed FD list.
        parent=owner.own(Root(deployment['cgroup_parent']));group=owner.own(Cgroup(parent,key,limits,clock))
        observation=launch_observe(args,fds,group,limits,clock,evidence,key)
        require(observation.get('status')=='complete','actual scientific producer failed; no partial success')
        collection=collect_full(roots['output'],job,job['condition'],observation,clock=clock)
        ledger.charge(read_bytes=collection['read_bytes'],output_bytes=collection['output_bytes'])
        result={'collection':collection,'output_root':rootspec['output'],'original_native_observation':observation}
    except BaseException as error:owner.catch(error)
    owner.close_all()
    # Closing a resource is part of success. All failures remain owned even if
    # ledger publication/formatting itself fails; first error remains first.
    if owner.errors:
        ledger.raw_failures.extend(owner.errors)
        owner.attempt(ledger.finish,key,'failed',observation,owner.errors[0])
    else:owner.attempt(ledger.finish,key,'complete',observation)
    owner.raise_first();return result

def run_scientific_sources(authority_root,receipt_path,receipt_pin,authority_limits,selection,global_limits):
    """Run all36 complete source families in all4 conditions after real admission.

This source route has no candidate grading or all-gates issuer. Unsupported GPU
birth/accounting remains a real deployment gap; it cannot be qualified by JSON.
"""
    plan=compile_campaign(selection)
    clock=Clock.begin(global_limits['wall_ns'],global_limits['cleanup_ns']);ledger=SourceLedger(clock,global_limits)
    owner=Failures();evidence=None;outcome=None;captures=Captures()
    try:
        custody=owner.own(Root(authority_root,private=True))
        authority=FullAuthority(custody,receipt_path,receipt_pin,authority_limits,clock=clock)
        authority.bind(plan['source_tree_sha256'],digest(canonical_bytes(selection)))
        require(authority.receipt['full_scientific_route']=='prospective_full_scientific_source_v1','explicit full-route external selection')
        require(authority.receipt['full_scientific_program_tree']==plan['source_tree'],'whole source closure before any child')
        stages=authority.receipt['full_scientific_stages'];require(set(stages)=={j['job_id']for j in plan['plans']},'all144 full family caller stages')
        require(authority.receipt['deployment']['whole_controller_resource_observer']and authority.receipt['deployment']['immutable_sealed_mount_evidence'],'whole native lifecycle evidence absent')
        evidence=owner.own(Root(authority.receipt['evidence_root'],private=True))
        for template in plan['plans']:
            stage=stages[template['job_id']];job,parents,edges,generated=captures.resolve(template)
            job.update(route='prospective_full_scientific_source_v1',native_deadline_ns=stage['original_deadline_ns'])
            require(clock.start_ns<job['native_deadline_ns']<=clock.end_ns,'child deadline extends original grant')
            value=_execute(authority,stage,job,parents,edges,generated,evidence,ledger,clock)
            captures.add(job,value)
        outcome={'status':'complete_scientific_source_capture','collections':captures.summary(),
                 'scientifically_qualified':False,'benchmark_scoring_performed':False,'task_id':plan['task_id'],
                 'full_source_demand':plan['demand'],'native_evidence_remains_external':True}
        evidence.write_new('full-scientific-source-captures.json',canonical_bytes(outcome),global_limits['report_bytes'],clock=clock)
    except BaseException as error:owner.catch(error)
    if evidence is not None:
        if owner.errors:
            owner.attempt(_publish_failure,evidence,owner,captures,global_limits,clock)
        owner.attempt(ledger.retain,evidence,'full-scientific-source-costs.json')
    owner.close_all();ledger.raw_failures.extend(owner.errors);owner.raise_first()
    return outcome
