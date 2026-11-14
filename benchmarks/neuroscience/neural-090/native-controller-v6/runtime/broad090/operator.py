"""Original-source -> complete paired Broad campaign host.

This is the concrete source caller. NativeOwner.obtain is intentionally absent:
no data/rights/native/process/capacity authority is implemented or fabricated.
An admitted external owner must implement every method below. A dictionary,
manifest, success boolean or copied descriptor is not a native owner.
"""
from pathlib import Path
from typing import Protocol
import hashlib
from programme.contracts import need,Pin,Asset,fields
from .protocol import cases,jobs,PROTECTED,EXPOSED,MODES,ARMS
from .planning import case_plan,event_id
from .store import load_originals
from .views import Compiler
from .capture import CaptureBook,TRACKS,invocation_key
from .custody import Ledger,Accounting,encoded,write_fresh,open_pinned,stable
from .catalogue import exact_json
import os
from .scoring import report

class NativeOwner(Protocol):
    def admit_originals(self,source_operands,limits):...
    def admit_runtime(self,runtime_root,runtime_manifest):...
    def admit_programs(self,programs,modes,arms):...
    def new_isolation(self,job,track,program,limits):...
    def independent_projection_key(self,invocation):...
    def publish_arm_view(self,isolation,view_root,manifest):...
    def seal_prediction(self,path,pin,invocation):...
    def seal_protected_set(self,path,pin,invocations):...
    def seal_complete_set(self,path,pin):...
    def resource_receipt(self,isolation):...
    def close(self):...
    def drain_close_errors(self):...

class Isolation(Protocol):
    def run_reference(self,entry,source_root,runtime_manifest,view_root,manifest_asset,seed,limits):...
    def run_candidate(self,view_root,manifest_asset,seed,limits):...
    def close(self):...
    def drain_close_errors(self):...

REQUIRED=('admit_originals','admit_runtime','admit_programs','new_isolation','independent_projection_key','publish_arm_view','seal_prediction',
          'seal_protected_set','seal_complete_set','resource_receipt','close','drain_close_errors')

def retire(ledger,name,owner):
    # Contract: drain returns pending, not already surfaced, occurrences in order.
    # Same raw object may represent distinct occurrences; never deduplicate it.
    # Independent close and drain preserve a throwing close plus pending errors.
    ledger.attempt(name+':close',owner.close)
    try:
        events=owner.drain_close_errors()
        for event in events:
            need(type(event) is tuple and len(event)==2 and isinstance(event[1],BaseException),'raw retirement occurrence')
            ledger.record(name+':'+str(event[0]),event[1])
    except BaseException as e:ledger.record(name+':drain',e)

def run(native_owner,source_root,source_operands,runtime_root,runtime_manifest,programs,limits,output):
    """Complete source implementation, never executed during construction.

    Per-arm/per-track fresh UID/mount/tool/history contexts are mandatory. Actor
    mounts exclude the evaluator's source roots, original labels/maps, prior
    actor outputs and every other arm. No retry or partial programme scoring.
    Program F is fixed before inputs; I receives identical arm-only inputs and
    tools/resources. The native owner must enforce these original obligations.
    """
    need(native_owner is not None and not isinstance(native_owner,dict) and all(callable(getattr(native_owner,x,None)) for x in REQUIRED),'unissued full native owner required; no descriptor substitute')
    need(set(programs)==set(MODES),'both frozen and interactive candidate programs')
    for p in programs.values():need(type(p) is Asset,'exact candidate source identity')
    need(set(limits)=={'evaluator','actor'} and all(type(x) is dict for x in limits.values()),'finite evaluator/actor budgets')
    fields(limits['evaluator'],('read_bytes','write_bytes'))
    fields(limits['actor'],('read_bytes','write_bytes','cpu_seconds','wall_seconds','rss_bytes','pids','threads','tool_calls','model_tokens','toolset'))
    for scope in ('evaluator','actor'):
        for name,value in limits[scope].items():
            if name=='toolset':Pin.parse(value)
            else:need(type(value) is int and value>=(0 if name in ('tool_calls','model_tokens') else 1),'finite preselected full resource allowance')
    ledger=Ledger();account=Accounting(limits['evaluator']['read_bytes'],limits['evaluator']['write_bytes']);store=None;result=None
    output=Path(output);need(not output.exists(),'fresh evaluator-owned programme root');output.mkdir(mode=0o700)
    try:
        from .runtime_source import verify_runtime,prepare_capsule
        need(Path(source_root).resolve()!=Path(runtime_root).resolve(),'original-data root cannot be the worker-code root')
        runtime_root=prepare_capsule(runtime_root,runtime_manifest,output/'reference-code',account,ledger)
        verify_runtime(runtime_root,runtime_manifest,account,ledger)
        native_owner.admit_runtime(runtime_root,runtime_manifest)
        native_owner.admit_originals(source_operands,limits);native_owner.admit_programs(programs,MODES,ARMS)
        store,events,words,support,provenance=load_originals(source_root,**source_operands,accounting=account,ledger=ledger)
        compiler=Compiler(store,events,words);plans={}
        for c in cases():
            plan=case_plan(c,events,store.index);name='plan-'+hashlib.sha256(c.key.encode()).hexdigest()+'.json'
            plans[c.key]=Asset(name,write_fresh(output/name,encoded(plan),account,ledger))
        write_fresh(output/'private-source-support.json',encoded({'support':support,'provenance':provenance}),account,ledger)
        book=CaptureBook(output/'captures',account,ledger,native_owner);release=None
        work=jobs();keys=set();isolations=set();closed_owner_references=[]
        for armset in (PROTECTED,EXPOSED):
            if armset==EXPOSED:release=book.protected_release()
            cached_case=None;plan=None
            for job in work:
                if job['arm'] not in armset:continue
                if job['case']!=cached_case:
                    asset=plans[job['case']];f=None
                    try:
                        f,before=open_pinned(output,asset,account,ledger);account.charge('read',asset.pin.bytes+1)
                        body=f.read(asset.pin.bytes+1);need(len(body)==asset.pin.bytes and stable(before,os.fstat(f.fileno())),'exact private selected case plan')
                        plan=exact_json(body);cached_case=job['case']
                    except BaseException as e:ledger.propagated('case-plan-readback',e)
                    finally:
                        if f is not None:ledger.attempt('case-plan-close',f.close)
                    ledger.raise_first()
                for track in TRACKS:
                    invocation=invocation_key(job,track);digest=hashlib.sha256(invocation.encode()).hexdigest();isolation=None
                    try:
                        # Reference uses the literal implemented worker; candidate source is independently fixed by mode.
                        program=None if track=='reference' else programs[job['mode']]
                        isolation=native_owner.new_isolation(job,track,program,limits['actor'])
                        need(isolation is not None and id(isolation) not in isolations,'fresh physical actor/history owner for each invocation')
                        isolations.add(id(isolation));closed_owner_references.append(isolation)
                        secret=native_owner.independent_projection_key(invocation);need(type(secret) is bytes and len(secret)==32 and secret not in keys,'independent arm/track row-order key')
                        keys.add(secret);view_root=output/('view-'+digest)
                        view=compiler.prepare(plan,job['arm'],secret,view_root,release)
                        native_owner.publish_arm_view(isolation,view_root,view['manifest'])
                        asset=Asset.parse(view['manifest'])
                        if track=='reference':returned=isolation.run_reference('broad090.worker:reference',runtime_root,runtime_manifest,view_root,asset,job['seed'],limits['actor'])
                        else:returned=isolation.run_candidate(view_root,asset,job['seed'],limits['actor'])
                        need(type(returned) is tuple and len(returned)==2 and type(returned[1]) is Asset,'actual captured output root and pin')
                    except BaseException as e:ledger.propagated('invocation:'+invocation,e)
                    finally:
                        if isolation is not None:retire(ledger,'actor:'+invocation,isolation)
                    ledger.raise_first()
                    resources=native_owner.resource_receipt(isolation)
                    # Actual retired descendants/counters are external evidence, never synthesized from logical reads.
                    need(type(resources) is Asset,'owned native resource receipt identity required')
                    book.capture(job,track,returned[0],returned[1],view['private']['roles']['final/query'],{'projection':view['private'],'native_resources':{'path':resources.path,**resources.pin.json()}})
        complete=book.finish()
        targets={event_id(r):r['label'] for rs in events.values() for r in rs}
        result=report(book,targets)
        result['complete_capture']=complete.json();result['logical_cost']=account.report()
        result['calibration_policy']='source unique labels and1024 CAL retained per case; no query-label optimization'
    except BaseException as e:ledger.propagated('broad-programme',e)
    finally:
        if store is not None:store.close()
        retire(ledger,'native-owner',native_owner)
    if ledger.first is not None:
        diagnostics=Ledger()
        try:
            write_fresh(output/'UNAVAILABLE.json',encoded({'schema':'n090-incomplete-campaign-v1','status':'whole_programme_unavailable',
                'required_paired_slots':38400,'required_invocations':76800,'partial_score':None,'first_and_secondary_occurrences':ledger.summary(),
                'all_gates_open':True,'qualification':False}),account,diagnostics)
        except BaseException as e:diagnostics.propagated('unavailable-record',e)
        for where,error in diagnostics.events:ledger.record('diagnostic:'+where,error)
        ledger.raise_first()
    # Publish only after original source and native owners fully retire.
    write_fresh(output/'point-report.json',encoded(result),account,ledger)
    ledger.raise_first();return result

def main():
    raise RuntimeError('Broad source only: no authentic original/clock/rights/native issuer installed; generic execution remains inactive')
