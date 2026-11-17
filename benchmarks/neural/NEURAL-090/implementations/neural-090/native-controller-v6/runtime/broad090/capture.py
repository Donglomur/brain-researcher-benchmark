"""Immutable evaluator prediction admission and protected-before-diagnostic gate.

No capability is issued by Python types or success booleans. External native
owner supplies isolated process/UID/mount/history admission and capture sealing.
This owner verifies exact returned bytes and full query identity before targets.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib,math,os
from programme.contracts import need,fields,Asset,Pin
from .protocol import ARMS,PROTECTED,EXPOSED,jobs,work_key
from .catalogue import exact_json
from .custody import open_pinned,stable,encoded,write_fresh
from .features import DiagnosticRelease

from .probability import normalize_probability

TRACKS=('candidate','reference')

def invocation_key(job,track):
    need(track in TRACKS,'candidate/reference complete paired tracks');return work_key(job)+'|'+track

def admit_result(value,expected_ids):
    fields(value,('schema','predictions','source_checkpoint','final_checkpoint','resource_receipt'))
    need(value['schema']=='n090-prediction-v1','fixed actor output contract')
    for key in ('source_checkpoint','final_checkpoint','resource_receipt'):Pin.parse(value[key])
    rows=value['predictions'];need(type(rows) is list and len(rows)==len(expected_ids),'whole query population output')
    seen={}
    for row in rows:
        fields(row,('query_id','probabilities'));key=row['query_id'];need(key in expected_ids and key not in seen,'exact unique arm-private query support')
        seen[key]=normalize_probability(row['probabilities'])
    need(set(seen)==set(expected_ids),'no partial capture');return seen

class CaptureBook:
    def __init__(self,root,accounting,ledger,native_owner):
        self.root=Path(root);need(not self.root.exists(),'fresh private capture prefix');self.root.mkdir(mode=0o700)
        self.accounting,self.ledger,self.native_owner=accounting,ledger,native_owner
        self.expected={invocation_key(j,t) for j in jobs() for t in TRACKS};self.records={};self.attempted=set();self.seal=None;self.completed=False;self.release_attempted=False;self.finish_attempted=False;self.supports={}
    def capture(self,job,track,output_root,output_asset,query_map,private_work):
        key=invocation_key(job,track);need(key in self.expected and key not in self.attempted and not self.finish_attempted,'fixed one-shot invocation; no rewrite/retry')
        if job['arm'] in EXPOSED:need(self.seal is not None,'all protected captures sealed before exposed actor results')
        else:need(self.seal is None,'protected capture set cannot change after diagnostic release')
        self.attempted.add(key)
        f=None;body=None
        try:
            f,before=open_pinned(output_root,output_asset,self.accounting,self.ledger)
            self.accounting.charge('read',output_asset.pin.bytes+1);body=f.read(output_asset.pin.bytes+1)
            need(len(body)==output_asset.pin.bytes and stable(before,os.fstat(f.fileno())),'stable full actual actor output')
            admitted=admit_result(exact_json(body),set(query_map))
        except BaseException as e:self.ledger.propagated('prediction-admission',e)
        finally:
            if f is not None:self.ledger.attempt('prediction-stream-close',f.close)
        self.ledger.raise_first()
        # Private mapping remains outside actor output and outside public reports.
        mapped={query_map[k]:p for k,p in admitted.items()};need(len(mapped)==len(query_map),'one exact original query row per opaque capture')
        name=hashlib.sha256(key.encode()).hexdigest()+'.json';pin=write_fresh(self.root/name,body,self.accounting,self.ledger)
        self.native_owner.seal_prediction(self.root/name,pin,key)
        support_key=(job['person'],job['chapter'])
        support=frozenset(mapped)
        if support_key in self.supports:need(self.supports[support_key]==support,'all conditions/arms/tracks preserve exact full original query support')
        else:self.supports[support_key]=support
        mapped_name='mapped-'+name
        mapped_pin=write_fresh(self.root/mapped_name,encoded(mapped),self.accounting,self.ledger)
        # Large private maps/projection audits are persisted once per invocation, not retained for all76,800 in RAM.
        audit_name='audit-'+name
        audit_pin=write_fresh(self.root/audit_name,encoded(private_work),self.accounting,self.ledger)
        self.records[key]={'job':dict(job),'track':track,'asset':Asset(name,pin),'mapped':Asset(mapped_name,mapped_pin),
                           'support_key':support_key,'private_audit':Asset(audit_name,audit_pin)}
        return pin
    def protected_release(self):
        need(not self.release_attempted,'one immutable global diagnostic release')
        required={invocation_key(j,t) for j in jobs() if j['arm'] in PROTECTED for t in TRACKS}
        need(set(self.records)==required,'every protected arm/mode/seed/case/track complete before diagnostics')
        self.release_attempted=True
        pins={k:{name:r[name].pin.json() for name in ('asset','mapped','private_audit')} for k,r in sorted(self.records.items())}
        body=encoded({'schema':'n090-protected-capture-set-v1','captures':pins})
        pin=write_fresh(self.root/'protected.json',body,self.accounting,self.ledger)
        self.native_owner.seal_protected_set(self.root/'protected.json',pin,tuple(sorted(required)))
        self.seal=pin
        return DiagnosticRelease('whole-broad-programme',pin.sha256,tuple((arm,pin.sha256) for arm in PROTECTED))
    def finish(self):
        need(set(self.records)==self.expected and self.seal is not None,'all76800 invocations for38400 pairedslots, no arm omitted')
        need(not self.finish_attempted,'one complete-set sealing attempt');self.finish_attempted=True
        body=encoded({'schema':'n090-full-capture-set-v1','protected':self.seal.json(),'captures':{k:{name:r[name].pin.json() for name in ('asset','mapped','private_audit')} for k,r in sorted(self.records.items())}})
        pin=write_fresh(self.root/'complete.json',body,self.accounting,self.ledger)
        self.native_owner.seal_complete_set(self.root/'complete.json',pin)
        self.completed=True
        return pin
    def targets(self,private_labels):
        need(self.completed and set(self.records)==self.expected,'target scoring only after complete sealed campaign')
        needed={event for support in self.supports.values() for event in support}
        need(set(private_labels)==needed and all(type(x) is int and 0<=x<39 for x in private_labels.values()),'complete original private target support')
        return dict(private_labels)

    def probabilities(self,record):
        need(self.completed,'score reads only after complete campaign seal')
        asset=record['mapped'];f=None;value=None
        try:
            f,before=open_pinned(self.root,asset,self.accounting,self.ledger);self.accounting.charge('read',asset.pin.bytes+1)
            body=f.read(asset.pin.bytes+1);need(len(body)==asset.pin.bytes and stable(before,os.fstat(f.fileno())),'stable private mapped prediction bytes')
            value=exact_json(body);need(set(value)==self.supports[record['support_key']],'all original support after sealed readback')
        except BaseException as e:self.ledger.propagated('mapped-capture-readback',e)
        finally:
            if f is not None:self.ledger.attempt('mapped-capture-close',f.close)
        self.ledger.raise_first();return value
