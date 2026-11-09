"""Bounded protected operator metadata transport; never a statistical reviewer."""
import os,stat,time
from pathlib import Path
import common as c
import authority

class Channel:
    def __init__(self,config,budget,source,source_files,run,protected_roots):
        c.exact(config,('request_root','response_root','maximum_response_bytes','poll_seconds','registry','source','run'))
        c.need(c.typed_equal(config['source'],source)and c.typed_equal(config['run'],run),'same immutable source/run channel')
        self.request_root,self.response_root=authority.disjoint_roots([config['request_root'],config['response_root']])
        for root in(self.request_root,self.response_root):c.need(root.is_dir(),'preselected metadata namespace exists')
        self.maximum=c.integer(config['maximum_response_bytes'],1,2**20);self.poll=c.finite(config['poll_seconds'],.001)
        c.need(self.poll<=1,'bounded metadata polling interval')
        self.config=config;self.budget=budget;self.source=source;self.source_files=source_files;self.run=run;self.protected_roots=protected_roots;self.sequence=0;self.records=[]
    def acquire(self,request,phase,actor):
        c.need(phase in authority.PHASES and actor in authority.ACTORS,'source-owned phase/actor')
        c.descriptor(request);sequence=self.sequence;self.sequence+=1
        name='%06d-%s-%s.json'%(sequence,phase,actor)
        intent={'schema':'neural081_operator_metadata_request_v1','sequence':sequence,'source':self.source,'source_files':self.source_files,'run':self.run,'request':request,'phase':phase,'actor':actor,'registry':self.config['registry'],'statistical_semantic_verdict_requested':False}
        issued=c.publish_json(self.request_root/name,intent,self.budget);path=self.response_root/name
        while True:
            self.budget.check_clock()
            try:before=path.lstat()
            except FileNotFoundError:
                time.sleep(min(self.poll,max(0,self.budget.end-self.budget.clock())));continue
            c.need(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and 0<before.st_size<=self.maximum,'ordinary bounded protected response')
            self.budget.charge('read_bytes',before.st_size+1)
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            try:
                first=os.fstat(fd)
                with os.fdopen(fd,'rb',closefd=False)as stream:raw=stream.read(before.st_size+1)
                last=os.fstat(fd);named=path.lstat();fields=('st_dev','st_ino','st_size','st_mode','st_nlink','st_mtime_ns','st_ctime_ns')
                c.need(len(raw)==before.st_size and all(getattr(before,k)==getattr(first,k)==getattr(last,k)==getattr(named,k)for k in fields),'complete immutable protected response')
            finally:os.close(fd)
            response=c.parse(raw);c.exact(response,('schema','sequence','intent','authority'))
            c.need(response['schema']=='neural081_operator_metadata_response_v1'and type(response['sequence'])is int and response['sequence']==sequence and c.typed_equal(response['intent'],issued),'exact one-shot metadata response, no alternate request')
            selected=response['authority'];c.need(c.typed_equal(selected['registry'],self.config['registry'])and c.typed_equal(selected['run'],self.run),'same preselected protected registry and run')
            run,conditions=authority.admit(selected,self.source,request,phase,actor,self.budget,self.source_files,protected_roots=self.protected_roots)
            self.records.append({'sequence':sequence,'intent':issued,'response':{'path':str(path),**c.pin(raw)},'phase':phase,'actor':actor,'request':request,'authority':selected})
            self.budget.check_clock();return selected,run,conditions

def selected_descriptor(conditions,role,key,descriptor):
    c.descriptor(descriptor);c.need(c.typed_equal(conditions[role].get(key),descriptor),'actual independent qualification pins selected '+role+'/'+key)
