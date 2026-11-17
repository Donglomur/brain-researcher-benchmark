"""Controller-side descriptor-only IPC and exact current projection cleanup."""
import os,socket,stat,threading,time
from pathlib import Path
import common as c
import fd_protocol as f
import projection_engine as engine
from transport.process import ProcessObserver

def stamp(s):return tuple(getattr(s,k)for k in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns'))

def lifetime(method):
    def guarded(self,*args,**kwargs):
        try:return method(self,*args,**kwargs)
        except BaseException as error:
            # Closeout is observational only and cannot replace the original
            # exception, remove current artifacts, or certify successful closure.
            try:self.failure_close(error)
            except BaseException as close_error:
                self.closeout_error={'type':type(close_error).__name__,'message':str(close_error)}
            raise
    return guarded

class Broker:
    @lifetime
    def __init__(self,selected,config,config_desc,source,access,bridge,root):
        self.channel=None;self.child=None;self.thread=None;self.launch_attempted=False;self.closeout_attempted=False;self.failure_budget=None
        c.exact(selected,('argv','cwd','env','normal_seconds','cleanup_seconds','stream_cap','fd_argument'))
        c.need(type(selected['argv'])is list and '{ISSUER_FD}'in selected['argv']and selected['fd_argument']=='{ISSUER_FD}','literal source-owned inherited socket argument')
        self.config=config;self.source=source;self.access=access;self.budget=access.budget;self.root=c.new_directory(root,self.budget);self.ordinal=0;self.current=None;self.current_end=None;self.result=None;self.failure=None;self.events=[];self.bridge=bridge
        c.need(config['origin']==self.budget.origin and config['limits']['seconds']==self.budget.end-self.budget.origin,'original issuer origin and whole endpoint')
        # Reserve the complete persistent worker envelope before launch. No refund
        # on partial input, unknown survivor, quota/clock or receipt failure.
        c.need(all(value==0 for key,value in config['limits'].items()if key not in('seconds','read_bytes','write_bytes')),'issuer worker numeric/provider/process counters absent; one host launch charged separately')
        for key in('read_bytes','write_bytes'):self.budget.charge(key,config['limits'][key])
        # Fixed source-owned failure publication allowance is reserved before
        # launch and never refunded. Its deadline is the original whole endpoint
        # plus the already selected 120-second inspection interval.
        self.budget.charge('write_bytes',2*2**20)
        failure_limits={k:0 for k in self.budget.limits};failure_limits.update(seconds=self.budget.end-self.budget.origin+120,write_bytes=2*2**20)
        self.failure_budget=c.Budget(self.budget.origin,failure_limits,clock=self.budget.clock)
        self.budget.charge('host_processes',1)
        self.channel,child=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET);self.child=child
        argv=[str(child.fileno())if x=='{ISSUER_FD}'else x for x in selected['argv']]
        self.intent=c.publish_json(self.root/'INTENT.json',{'schema':'neural081_issuer_launch_v1','argv':argv,'config':config_desc,'source':source,'origin':self.budget.origin,'end':self.budget.end,'worker_reservation':config['limits'],'refunded':False},self.budget)
        def observe():
            try:self.result=ProcessObserver().run(argv,cwd=selected['cwd'],env=selected['env'],budget=bridge,seconds=selected['normal_seconds'],cleanup_seconds=selected['cleanup_seconds'],stream_cap=selected['stream_cap'],pass_fds=(child.fileno(),))
            except BaseException as error:self.failure={'type':type(error).__name__,'evidence':getattr(error,'evidence',None)}
        self.thread=threading.Thread(target=observe,name='neural081-issuer-observer',daemon=False);self.launch_attempted=True;self.thread.start()
        ready,fd=f.receive(self.channel,deadline=min(self._deadline(),self.budget.clock()+120),budget=self.budget)
        if fd is not None:os.close(fd);c.need(False,'no issuer readiness operand')
        c.exact(ready,('kind','source','restriction','original_endpoint'));c.need(ready['kind']=='ready'and c.typed_equal(ready['source'],source)and ready['original_endpoint']==self.budget.end,'actual isolated current source readiness')
        self.readiness=c.publish_json(self.root/'READY.json',ready,self.budget)
        child.close()
    def failure_close(self,error):
        if self.closeout_attempted:return
        self.closeout_attempted=True
        original={'type':type(error).__name__,'message':str(error)};errors=[];socket_states={}
        for name in('channel','child'):
            owned=getattr(self,name,None)
            if owned is None:socket_states[name]='not_created';continue
            try:
                if owned.fileno()>=0:
                    try:owned.shutdown(socket.SHUT_RDWR)
                    except OSError:pass
                owned.close();socket_states[name]='closed'
            except BaseException as close_error:
                socket_states[name]='unknown';errors.append({'operation':name,'type':type(close_error).__name__,'message':str(close_error)})
        thread=getattr(self,'thread',None);joined=thread is None
        if thread is not None:
            try:
                # Bounded observation of our own thread, never a child signal.
                remaining=min(120,max(0,self.budget.end+120-self.budget.clock()))
                thread.join(remaining);joined=not thread.is_alive()
            except BaseException as close_error:
                errors.append({'operation':'observer_join','type':type(close_error).__name__,'message':str(close_error)})
        observed=getattr(self,'result',None)
        record={'schema':'neural081_failed_projection_issuer_v1','status':'failed','original_failure':original,'launch_attempted':self.launch_attempted,'observer_thread_joined':joined,'owned_ipc':socket_states,'observer_failure':getattr(self,'failure',None),'observer_success_record':None if observed is None else observed['observation'],'unknown_survivors':any(v=='unknown'for v in socket_states.values())or(self.launch_attempted and (not joined or observed is None)),'current_artifacts_retained':getattr(self,'current',None)is not None,'completed_contexts':getattr(self,'ordinal',0),'child_mutating_signals':0,'automatic_retry':False,'closeout_errors':errors,'publication_uncertain':True}
        self.failure_record=record
        if self.failure_budget is not None and hasattr(self,'root'):
            record['publication_uncertain']=False
            try:self.failure_descriptor=c.publish_json(self.root/'FAILURE.json',record,self.failure_budget)
            except BaseException as publication_error:
                record['publication_uncertain']=True
                record['publication_error']={'type':type(publication_error).__name__,'message':str(publication_error)}
    def _deadline(self):return self.budget.end if self.current_end is None else min(self.budget.end,self.current_end)
    def _input(self,desc,sequence):
        self.access.admit(desc);path=c.within(desc['path'],[Path(desc['path']).parent]);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            s=os.fstat(fd);c.need(stat.S_ISREG(s.st_mode)and s.st_nlink==1 and s.st_size==desc['bytes'],'exact ordinary current operand without reading its body')
            f.send(self.channel,{'kind':'input','sequence':sequence,'descriptor':desc},fd,deadline=self._deadline(),budget=self.budget)
        finally:os.close(fd)
    @lifetime
    def project(self,request):
        c.need(self.current is None and self.failure is None and self.thread.is_alive(),'one currently isolated projection and live observed issuer')
        c.need(request['ordinal']==self.ordinal and request['original_endpoint']==self.budget.end and c.typed_equal({k:request[k]for k in self.config['request_roster'][self.ordinal]},self.config['request_roster'][self.ordinal]),'exact source-owned next identity')
        self.current_end=c.finite(request['case_endpoint']);c.need(self.budget.clock()<self.current_end<=self.budget.end,'original current context endpoint before any projection')
        context=self.access.json(request['context']);role=self.access.json(request['role'])
        c.need(c.typed_equal(context['training_role'],request['role']),'actual context selected role')
        current=c.new_directory(self.root/('%08d'%self.ordinal),self.budget);self.current={'root':current,'files':{},'reply':None}
        f.send(self.channel,request,deadline=self._deadline(),budget=self.budget)
        self._input(request['context'],0);self._input(request['role'],1);self._input(role['labels'],2)
        n=len(role['ids']);maximum={'train.npy':n*64*512*4+65536,'train_labels.npy':n*8+65536,'train_rows.json':n*128+65536,'query.npy':64*512*4+65536}
        for name in engine.OUTPUTS:
            path=current/name;fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            try:
                self.current['files'][name]={'path':path,'created':stamp(os.fstat(fd))}
                f.send(self.channel,{'kind':'output','ordinal':self.ordinal,'name':name,'maximum':maximum[name]},fd,deadline=self._deadline(),budget=self.budget)
            finally:os.close(fd)
        if context['view']=='EEG':
            windows=dict(zip(role['ids'],role['windows']))
            for j,row in enumerate(context['training_permutation']):self._input(windows[row['canonical_id']],3+j)
            self._input(context['query_window'],3+n)
        message,extra=f.receive(self.channel,deadline=self._deadline(),budget=self.budget)
        if extra is not None:os.close(extra);c.need(False,'no descriptor returned from issuer')
        c.exact(message,('kind','reply'));reply=message['reply'];c.need(message['kind']=='projection'and type(reply['ordinal'])is int and reply['ordinal']==self.ordinal and c.typed_equal(reply['context'],request['context'])and c.typed_equal(reply['role'],request['role'])and reply['n_train']==n,'exact complete issuer output/role identity')
        c.need(reply['global_label_opens']==0 and type(reply['global_label_opens'])is int and reply['generation']==request['generation'],'current trusted preparation generation')
        c.exact(reply['outputs'],engine.OUTPUTS);descriptors={}
        for name,pin in reply['outputs'].items():
            c.exact(pin,('bytes','sha256'));c.integer(pin['bytes'],1,maximum[name]);c.digest(pin['sha256']);item=self.current['files'][name];s=item['path'].stat()
            c.need(s.st_dev==item['created'][0]and s.st_ino==item['created'][1]and stat.S_ISREG(s.st_mode)and s.st_nlink==1 and s.st_size==pin['bytes'],'same issuer-created ordinary complete output')
            item['sealed']=stamp(s);descriptors[name]={'path':str(item['path']),**pin}
        c.sync_directory(current);c.sync_directory(current.parent);self.budget.check_clock()
        self.current['reply']=c.pin(c.encoded(reply));self.current['descriptors']=descriptors
        self.events.append(c.publish_json(self.root/('REPLY-%08d.json'%self.ordinal),reply,self.budget))
        return descriptors,reply
    @lifetime
    def cleanup(self,candidate_closure):
        c.need(self.current is not None and self.current['reply']is not None,'one fully materialized current context')
        from runtime import admit_closure
        c.need(type(candidate_closure)is dict and candidate_closure.get('schema')=='neural081_candidate_episode_v1'and type(candidate_closure.get('native_actions'))is list,'actual candidate episode before projection cleanup')
        c.need(candidate_closure.get('mode')in('F','I')and ((candidate_closure['mode']=='F'and len(candidate_closure['native_actions'])==1)or(candidate_closure['mode']=='I'and len(candidate_closure['native_actions'])<=8)),'exact candidate action count including legitimate direct I prediction')
        for action in candidate_closure['native_actions']:admit_closure(action)
        c.need(candidate_closure.get('source_admitted_natural_closure')is True,'complete source-admitted episode')
        for item in self.current['files'].values():
            c.need(stamp(item['path'].lstat())==item['sealed'],'readonly projection unchanged before exact cleanup');item['path'].unlink()
        directory=self.current['root'];c.sync_directory(directory);directory.rmdir();c.sync_directory(directory.parent)
        cleanup={'files_absent':all(not x['path'].exists()for x in self.current['files'].values()),'directory_absent':not directory.exists(),'parent_directory_synced':True,'candidate_closed':True}
        f.send(self.channel,{'kind':'cleaned','ordinal':self.ordinal,'reply':self.current['reply'],'cleanup':cleanup},deadline=self._deadline(),budget=self.budget)
        self.events.append(c.publish_json(self.root/('CLEANUP-%08d.json'%self.ordinal),{'ordinal':self.ordinal,'reply':self.current['reply'],'cleanup':cleanup,'candidate_closure':candidate_closure},self.budget));self.current=None;self.current_end=None;self.ordinal+=1
    @lifetime
    def finish(self):
        c.need(self.current is None and self.ordinal==self.config['maximum_requests'],'complete all12N issuer contexts')
        f.send(self.channel,{'kind':'finish','completed':self.ordinal},deadline=self._deadline(),budget=self.budget)
        message,fd=f.receive(self.channel,deadline=self._deadline(),budget=self.budget)
        if fd is not None:os.close(fd);c.need(False,'no final issuer descriptor')
        c.exact(message,('kind','completed','last_reply','budget'));c.need(message['kind']=='finished'and type(message['completed'])is int and message['completed']==self.ordinal,'complete final issuer counter')
        self.channel.close();remaining=self.budget.end-time.monotonic();c.need(remaining>0,'issuer closure inside original endpoint');self.thread.join(remaining)
        c.need(not self.thread.is_alive()and self.failure is None and self.result is not None,'original natural issuer wait/streams/group observed')
        receipt={'schema':'neural081_complete_projection_issuer_v1','intent':self.intent,'ready':self.readiness,'events':self.events,'final':message,'observation':self.result['observation'],'stdout':c.publish(self.root/'STDOUT.txt',self.result['stdout'],self.budget),'stderr':c.publish(self.root/'STDERR.txt',self.result['stderr'],self.budget),'source':self.source,'completed':self.ordinal,'normal_endpoint':self.budget.end}
        return c.publish_json(self.root/'CLOSED.json',receipt,self.budget)
