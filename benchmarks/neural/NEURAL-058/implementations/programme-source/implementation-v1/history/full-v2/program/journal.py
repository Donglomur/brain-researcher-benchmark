"""Durable append-only host journal and independent exact event-chain admission."""
import hashlib
import os
from pathlib import Path
from core import encoded, parse, need, pin, integer, parent_chain, sync_dir, close_preserving


class Journal:
    def __init__(self,path,budget,cap,event_cap=1<<20):
        self.path=parent_chain(path);self.budget=budget;self.cap=integer(cap,1);self.event_cap=integer(event_cap,1)
        self.fd=os.open(self.path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            sync_dir(self.path.parent)
        except BaseException:
            fd=self.fd;self.fd=None;close_preserving(fd);raise
        self.sequence=0;self.total=0;self.chain='0'*64;self.pending=None
    def reserve_event(self):
        need(self.pending is None,'no outstanding event reservation')
        # Both encoding and file publication are reserved before serialization.
        # Conservative unused reservation is retained, never refunded/relabelled
        # actual physical I/O. Panel-owned events use the panel budget itself.
        self.budget.reserve_write(2*self.event_cap)
        token=object();self.pending=(token,self.budget,self.sequence)
        return token
    def append_reserved(self,event,token):
        need(self.pending is not None and self.pending[0] is token
             and self.pending[1] is self.budget and self.pending[2]==self.sequence,
             'exact single-use source-owned prepaid event')
        charged_budget=self.pending[1];self.pending=None
        charged_budget.tick()
        need(type(event) is dict and 'kind' in event,'typed journal event')
        body=encoded({'sequence':self.sequence,'previous':self.chain,'event':event})
        need(len(body)+1<=self.event_cap and self.total+len(body)+1<=self.cap,'journal reservation ceiling')
        data=memoryview(body+b'\n')
        while data:
            charged_budget.tick()
            n=os.write(self.fd,data);need(n>0,'short durable event write');data=data[n:]
        os.fsync(self.fd)
        self.chain=hashlib.sha256(body).hexdigest();self.total+=len(body)+1;self.sequence+=1
        charged_budget.tick()
        return {'sequence':self.sequence-1,'chain':self.chain,'reserved_encoding_and_publication_bytes':2*self.event_cap}
    def append(self,event):
        return self.append_reserved(event,self.reserve_event())
    def close(self):
        fd=self.fd;self.fd=None
        try:
            os.fsync(fd)
        finally:
            close_preserving(fd)
        os.chmod(self.path,0o444,follow_symlinks=False);sync_dir(self.path.parent)


def decode(raw, allow_partial=False, event_cap=1<<20):
    need(type(raw) is bytes,'captured journal body')
    integer(event_cap,1,64<<20)
    rows=raw.split(b'\n');tail=rows.pop()
    need(not tail or allow_partial,'complete newline-terminated event journal')
    chain='0'*64;events=[]
    for i,body in enumerate(rows):
        need(0<len(body)<=event_cap,'bounded complete event under exact selected journal cap')
        row=parse(body)
        need(set(row)=={'sequence','previous','event'} and type(row['sequence']) is int
             and row['sequence']==i and row['previous']==chain,'exact ordered hash chain')
        need(type(row['event']) is dict and type(row['event'].get('kind')) is str,'typed event body')
        chain=hashlib.sha256(body).hexdigest();events.append(row['event'])
    return events,{'complete_events':len(events),'last_chain':chain,'partial_tail':pin(tail) if tail else None}


def closure(events, expected_episodes, expected_operations, origin, deadline):
    """Exact identity/configuration/origin joins; event counts alone are insufficient."""
    episodes={};native={};providers={};phases={}
    for index,event in enumerate(events):
        kind=event['kind']
        if kind=='phase_entered':
            op=event['identity'];need(op not in phases,'phase entered once');phases[op]={'entered':index}
        elif kind=='phase_completed':
            op=event['identity'];need(op in phases and 'completed' not in phases[op],'phase completed after exact entry')
            phases[op]['completed']=index
        elif kind=='episode_completed':
            identity=event['identity'];need(identity not in episodes,'no duplicate episode completion')
            episodes[identity]=event
        elif kind=='provider_attempted':
            key=(tuple(event['episode']),event['ordinal']);need(key not in providers,'unique provider request')
            need(event['original_origin']==origin and event['cutoff']<=deadline,'provider original clock')
            providers[key]={'attempt':event}
        elif kind in ('provider_usage_observed','provider_completed'):
            key=(tuple(event['episode']),event['ordinal']);need(key in providers,'provider response without request')
            name='usage' if kind=='provider_usage_observed' else 'complete'
            need(name not in providers[key],'one provider usage/completion');providers[key][name]=event
        elif kind=='native_intent':
            op=event['operation'];need(op not in native,'unique native intention')
            need(event['original_origin']==origin and event['started']>=origin and event['cutoff']<=deadline,'native original clock')
            native[op]={'intent':event}
        elif kind in ('native_created','native_started','native_completed'):
            op=event['operation'];need(op in native,'native event without intention')
            name=kind.removeprefix('native_');row=native[op]
            need(name not in row and event['config']==row['intent']['config'],'native exact config chain')
            if name!='created':
                need('created' in row and event['container']==row['created']['container'],'same immutable container chain')
            if name=='completed':
                need('started' in row and event['source']==row['intent']['source']
                     and event['output']==row['intent']['output'] and event['original_origin']==origin
                     and event['cutoff']==row['intent']['cutoff'] and event['observed_end']<event['cutoff']
                     and event['natural_exit'] is True and type(event['exit_code']) is int and event['exit_code']==0,
                     'complete natural native/source/output/origin closure')
                need(set(event['artifacts'])==set(row['intent']['expected_artifacts']),'complete intended artifact set')
            row[name]=event
        elif kind in ('provider_failed','native_failed','phase_failed','study_failed'):
            raise ValueError('failed or uncertain operation cannot become complete closure')
    need(set(episodes)==set(expected_episodes),'complete exact author episode membership')
    need(set(phases)==set(expected_operations) and all('completed' in x for x in phases.values()),'full exact top-level schedule closure')
    for key,row in providers.items():
        need(set(row)=={'attempt','usage','complete'} and row['usage']['response']==row['complete']['response'],
             'all provider attempts have natural complete response and usage')
    ids=[]
    for op,row in native.items():
        need(set(row)=={'intent','created','started','completed'},'all native attempts complete')
        ids.append(row['created']['container'])
    need(len(ids)==len(set(ids)),'native resources not silently reused across phases')
    # Each native operation is either a declared fixed phase or an explicitly
    # journalled child of an author/query phase; producer admission checks that
    # parent identity and actual artifact consumers before any target read.
    return {'episodes':episodes,'native':native,'providers':providers,'phases':phases,
            'native_count':len(native),'provider_count':len(providers)}
