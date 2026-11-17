"""Shared inclusive output ceiling, private original streams and stage witnesses."""
import contextlib,fcntl,hashlib,os,time
from pathlib import Path
from .validation import need,integer,encoded
from .artifacts import owned


class SharedBudget:
    def __init__(self,root,total,reserve,*,create=False):
        self.root=Path(root);self.path=self.root/'.shared-output-budget'
        integer(total,1);integer(reserve,1,total-1);self.total,self.reserve=total,reserve
        if create:
            with self.path.open('xb') as h:h.write(b'0\n')
    def charge(self,count,*,final=False):
        integer(count)
        with self.path.open('r+b',buffering=0) as h:
            fcntl.flock(h,fcntl.LOCK_EX)
            raw=h.read(64);need(len(raw)<64,'bounded shared output ledger');used=int(raw)
            need(used+count<=self.total-(0 if final else self.reserve),'inclusive whole-campaign output ceiling')
            h.seek(0);h.write(str(used+count).encode()+b'\n');h.truncate();os.fsync(h.fileno())
            return used+count
    def persist(self,root,name,value,*,final=False):
        raw=encoded(value)+b'\n';self.charge(len(raw),final=final)
        path=owned(root,name)
        with path.open('xb') as h:h.write(raw);h.flush();os.fsync(h.fileno())
        return {'path':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


class DiagnosticCapture:
    """Retains original private prefixes; hashes/counts all observed bytes."""
    def __init__(self,root,prefix,cap,budget):
        self.root,self.prefix,self.cap,self.budget=Path(root),prefix,integer(cap,1),budget
        self.streams={};self.closed=False;self.errors=[]
        for name in ('out','err'):
            path=owned(root,prefix+'.'+name)
            self.streams[name]={'handle':path.open('xb'),'path':path.name,'observed':0,'retained':0,'observed_hash':hashlib.sha256(),'retained_hash':hashlib.sha256(),'eof':False}
    def feed(self,kind,block):
        state=self.streams[kind];need(not self.closed,'diagnostic capture active')
        state['observed']+=len(block);state['observed_hash'].update(block)
        prefix=block[:max(0,self.cap-state['retained'])]
        if prefix:
            try:
                self.budget.charge(len(prefix));written=state['handle'].write(prefix)
                state['retained']+=written;state['retained_hash'].update(prefix[:written]);need(written==len(prefix),'complete private stream write')
            except Exception as error:
                self.errors.append(type(error).__name__+': '+str(error));raise
    def eof(self,kind):self.streams[kind]['eof']=True
    def child(self,label):return DiagnosticCapture(self.root,self.prefix+'.'+label,self.cap,self.budget)
    def snapshot(self):
        return {'streams':{name:{'path':s['path'],'observed_bytes':s['observed'],'retained_bytes':s['retained'],'observed_sha256':s['observed_hash'].hexdigest(),'retained_sha256':s['retained_hash'].hexdigest(),'eof':s['eof'],'truncated':s['observed']>s['retained'],'complete_original_stream':s['eof'] and s['observed']==s['retained']} for name,s in self.streams.items()},'persistence_errors':list(self.errors),'closed':self.closed}
    def close(self):
        if not self.closed:
            for s in self.streams.values():
                try:s['handle'].flush();os.fsync(s['handle'].fileno())
                except Exception as error:self.errors.append(type(error).__name__+': '+str(error))
                finally:s['handle'].close()
            self.closed=True
        return self.snapshot()


class Session:
    """One outer-selected clock; stage costs are nested attribution, not totals."""
    def __init__(self,root,budget,origin,end,cleanup_end,observer_factory,now=time.monotonic):
        need(origin<end<cleanup_end,'original whole-campaign deadlines')
        self.root,self.budget,self.origin,self.end,self.cleanup_end=Path(root),budget,origin,end,cleanup_end
        self.now,self.observer_factory=now,observer_factory;self.events=[]
    def clock(self):need(self.origin<=self.now()<self.end,'unchanged whole-campaign deadline')
    def persist(self,name,value,*,final=False):
        if not final:self.clock()
        return self.budget.persist(self.root,name,value,final=final)
    @contextlib.contextmanager
    def stage(self,name):
        event={'stage':name,'start':self.now(),'status':'started','cost_semantics':'nested attribution; never added to inclusive outer total'}
        observer=self.observer_factory();begun=False
        try:
            self.clock();observer.begin(name,self.origin,self.end);begun=True
            yield
            self.clock();event['status']='success'
        except BaseException as error:
            event['status']='failure';event['reason']=type(error).__name__+': '+str(error);raise
        finally:
            event['end']=self.now()
            try:
                need(begun,'stage observer did not start');event['cost']=observer.finish(name)
            except Exception as error:event['cost']=None;event['resource_error']=str(error)
            self.events.append(event)
            # Preserve the event even after normal deadline/normal output expiry.
            self.persist('stage-'+str(len(self.events))+'.json',event,final=True)
