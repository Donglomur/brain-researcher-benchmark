"""Invented RAM-only controls of production execute/capture; no Docker or data access."""
import base64,copy,hashlib,importlib.util,io,json,stat,unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('isttc_engine_native_controls',HERE/'native.py')
n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n)
IMAGE='sha256:'+'a'*64
SOURCE={'bytes':17,'sha256':'b'*64}
NATURAL={'Status':'exited','Running':False,'Dead':False,'Pid':0,'ExitCode':0,'OOMKilled':False}

class Executor:
    def __init__(self):self.reads=0;self.writes=0
    def tick(self):pass
    def read(self,x):self.reads+=x
    def write(self,x):self.writes+=x

class Scan:
    def __enter__(self):return iter(())
    def __exit__(self,*a):pass

class FakeDocker:
    instances=[];names=[];fail=None
    def __init__(self,binary,socket,**kw):
        self.records=[];self.reaped=True;self.items={};self.count=0;self.kw=kw;self.requested=[];self.reserved=0;self.__class__.instances.append(self)
    def __call__(self,a,end,phase,cap=131072):
        self.requested.append((a,phase,cap));n.need(cap==n.cli_cap(phase),'actual exact CLI cap')
        n.need(len(self.records)<self.kw['max_calls'],'finite CLI calls');self.reserved+=cap;n.need(self.reserved<=self.kw['reply_budget'],'cumulative replybound')
        if self.fail==phase:raise ValueError('invented phase failure')
        out=self.route(a,phase)
        self.records.append(dict(phase=phase,returncode=0,error_type=None,observed_retained_bytes=len(out),seconds=0.,client_reaped=True,cleanup_complete=True,cleanup_before_original_cutoff=True,owned_group_absence_observed=True,leader_exited_with_group_alive=False,group_probe_or_cleanup_error=None))
        return out
    def route(self,a,phase):
        if a[:2]==['image','inspect']:return n.encoded({'Id':IMAGE,'Config':{}})
        kind,action=a[:2]
        if action=='ls':
            selector=a[a.index('--filter')+1]
            def match(v):
                if selector.startswith('label='):return v['Labels' if kind=='volume' else 'Config'].get('Labels',v.get('Labels',{})).get(n.LABEL)==selector.split('=',2)[2] if kind=='container' else v['Labels'].get(n.LABEL)==selector.split('=',2)[2]
                return v['Name'].lstrip('/')==selector.split('=',1)[1].strip('^$').lstrip('/')
            rows=[v['Name'] if kind=='volume' else v['Id'] for v in self.items.values() if v['kind']==kind and match(v)]
            return ('\n'.join(rows)+'\n' if rows else '').encode()
        if kind=='volume' and action=='create':
            name=a[-1];opts=dict(x.split('=',1) for i,x in enumerate(a) if i and a[i-1]=='--opt');lab=a[a.index('--label')+1].split('=',1)
            self.items[name]={'kind':'volume','Name':name,'Labels':dict([lab]),'Driver':'local','Options':opts};return (name+'\n').encode()
        if kind=='container' and action=='create':
            name=a[a.index('--name')+1];self.count+=1;ident=('%064x'%self.count);label=a[a.index('--label')+1].split('=',1)
            mounts=[]
            for i,x in enumerate(a):
                if i and a[i-1]=='--mount':
                    fields={z.split('=',1)[0]:z.split('=',1)[1] for z in x.split(',') if '=' in z}
                    mounts.append({'Destination':fields['dst'],'Type':fields['type'],'Name':fields['src'],'Source':fields['src'],'RW':'readonly' not in x.split(',')})
            at=a.index('--entrypoint');cmd=a[at+3:];limits=[]
            for i,x in enumerate(a):
                if i and a[i-1]=='--ulimit':
                    k,y=x.split('=');s,h=map(int,y.split(':'));limits.append({'Name':k,'Soft':s,'Hard':h})
            tmp={}
            for i,x in enumerate(a):
                if i and a[i-1]=='--tmpfs':k,v=x.split(':',1);tmp[k]=v
            h={'Memory':int(a[a.index('--memory')+1]),'MemorySwap':int(a[a.index('--memory-swap')+1]),'NanoCpus':int(float(a[a.index('--cpus')+1])*1000000000),'PidsLimit':64,'ShmSize':16777216,'NetworkMode':'none','ReadonlyRootfs':True,'CgroupnsMode':'private','LogConfig':{'Type':'none'},'Privileged':False,'PidMode':'','IpcMode':'private','CapDrop':['ALL'],'SecurityOpt':['no-new-privileges'],'RestartPolicy':{'Name':'no'},'AutoRemove':False,'Tmpfs':tmp,'Ulimits':limits,'Init':False if '--init=false' in a else None}
            self.items[ident]={'kind':'container','Id':ident,'Name':'/'+name,'Image':IMAGE,'Config':{'Image':IMAGE,'User':'65534:65534','Entrypoint':['python'],'Cmd':cmd,'Labels':dict([label])},'HostConfig':h,'Mounts':mounts,'State':dict(NATURAL)}
            return (ident+'\n').encode()
        if action=='inspect':return n.encoded([self.items[a[2]]])
        if kind=='container' and action in ('start','kill','wait'):
            self.items[a[-1]]['State']['Running']=action=='start'
            return b'0\n' if action=='wait' else (a[-1]+'\n').encode()
        if action=='rm':self.items.pop(a[2]);return (a[2]+'\n').encode()
        if kind=='exec':
            if 'ready' in a:return b'{"ready":true}\n'
            owner=a[a.index('--owner-token')+1];role=a[a.index('--role')+1]
            files=[{'name':name,'bytes':len(b'INVENTED'),'stamp':[1,i+2,stat.S_IFREG|0o400,len(b'INVENTED'),1,65534,65534,1,1]} for i,name in enumerate(self.names)]
            if 'inventory' in a:
                dirs=sorted({str(p) for name in self.names for p in Path(name).parents if str(p)!='.'})
                return n.encoded(dict(schema='isttc_capture_inventory_v1',owner=owner,role=role,root_stamp=[1,1,stat.S_IFDIR|0o700,1,1,65534,65534,1,1],directories=[{'name':name,'stamp':[1,1000+i,stat.S_IFDIR|0o700,1,1,65534,65534,1,1]} for i,name in enumerate(dirs)],files=files,total_bytes=sum(x['bytes'] for x in files)))
            name=a[a.index('--name')+1];offset=int(a[a.index('--offset')+1]);length=int(a[a.index('--length')+1]);item=next(x for x in files if x['name']==name);body=b'INVENTED'[offset:offset+length]
            return n.encoded(dict(schema='isttc_capture_chunk_v1',owner=owner,role=role,name=name,offset=offset,bytes=len(body),stamp=item['stamp'],eof=offset+len(body)==item['bytes'],sha256=hashlib.sha256(body).hexdigest(),base64=base64.b64encode(body).decode()))
        raise AssertionError((phase,a))

class RAM:
    def __init__(self):self.next=10;self.files={};self.names={}
    def open(self,p,flags,mode=0o777):
        self.next+=1;self.names[self.next]=str(p);self.files[self.next]=bytearray();return self.next
    def write(self,fd,v):self.files[fd].extend(v);return len(v)
    def fstat(self,fd):return SimpleNamespace(st_size=len(self.files[fd]))


def req(phase,files):return dict(schema='isttc_owned_phase_request_v1',phase_id='invented-A-full',image=IMAGE,source=SOURCE,expected_files=sorted(files),entry=phase+'_entry.py',entry_support=dict(n.SUPPORT[phase]),**n.TIMES[phase])

class NativeControls(unittest.TestCase):
    def setUp(self):FakeDocker.instances=[];FakeDocker.fail=None
    def run_phase(self,phase='reproduction',files=None,fail=None):
        files=files or sorted(n.OUTPUTS[phase])
        FakeDocker.names=sorted(files);FakeDocker.fail=fail;ex=Executor();events=[];ram=RAM()
        source={'manifest':SOURCE,'members':4,'read_bytes':100,'files':{x:SOURCE for x in ('engine/native.py','engine/holder.py','reproduction_entry.py','improvement_entry.py','reference_entry.py','entry_common.py','baseline/baseline.py','baseline/read_inputs.py',*[x for x in n.SUPPORT[phase].values() if x not in ('entry_common.py','baseline/baseline.py','baseline/read_inputs.py')])}}
        with ExitStack() as st:
            st.enter_context(patch.object(n,'Docker',FakeDocker));st.enter_context(patch.object(n,'source_auth',return_value=source));st.enter_context(patch.object(n,'checked_mounts',return_value={'/request.json':('bind',Path('/request'),False)}));st.enter_context(patch.object(n,'path',side_effect=lambda p:Path(p)))
            st.enter_context(patch.object(n.time,'monotonic',return_value=100.));st.enter_context(patch.object(Path,'is_dir',return_value=True));st.enter_context(patch.object(Path,'stat',return_value=SimpleNamespace(st_mode=stat.S_IFSOCK)))
            st.enter_context(patch.object(n.os,'scandir',return_value=Scan()));st.enter_context(patch.object(Path,'mkdir'));st.enter_context(patch.object(n.os,'open',side_effect=ram.open));st.enter_context(patch.object(n.os,'write',side_effect=ram.write));st.enter_context(patch.object(n.os,'fstat',side_effect=ram.fstat));st.enter_context(patch.object(n.os,'fsync'));st.enter_context(patch.object(n.os,'close'));st.enter_context(patch.object(n,'fsync_dir'))
            result=n.execute(ex,{'binary':'/docker','socket':'/socket'},phase=phase,request=req(phase,files),program=Path('/program') if phase!='reference' else None,readonly_mounts={},output_dir=Path('/output'),source_dir=Path('/source'),original_deadline=900100.,publish=lambda name,value:events.append((name,copy.deepcopy(value))))
        return result,ex,events,ram
    def test_complete_reproduction_route_and_capture(self):
        r,ex,ev,ram=self.run_phase();self.assertEqual(set(r['artifacts']['files']),{'estimates.csv','methods.json'});self.assertEqual(r['artifacts']['total_bytes'],16);self.assertEqual(ex.writes,16);self.assertTrue(r['all_native_resources_closed']);self.assertFalse(r['failure_custody_complete']);self.assertEqual(len(r['closures']),3)
        d=FakeDocker.instances[-1];self.assertEqual(d.items,{});self.assertLess(d.reserved,d.kw['reply_budget']);self.assertEqual(sum(p=='artifact_chunk' for _,p,_ in d.requested),4)
        producer_remove=next(i for i,(a,p,c) in enumerate(d.requested) if p=='cleanup_remove' and a[1]=='rm');firstcapture=next(i for i,(_,p,_) in enumerate(d.requested) if p=='artifact_inventory');self.assertLess(producer_remove,firstcapture)
        self.assertEqual(ev[-1][1]['status'],'captured');n.validate_cli_records(r['command_metadata'])
    def test_complete_improvement_route(self):
        r,_,_,_=self.run_phase('improvement');self.assertEqual(set(r['artifacts']['files']),{'estimates.csv','methods.json'})
    def test_complete_reference_route(self):
        r,_,_,_=self.run_phase('reference');self.assertEqual(set(r['artifacts']['files']),{'estimates.csv','methods.json'})
    def test_late_capture_failure_never_success(self):
        with self.assertRaises(ValueError):self.run_phase(fail='artifact_chunk')
        self.assertEqual(FakeDocker.instances[-1].items,{})
    def test_retirement_failure_never_success_and_other_cleanup_attempted(self):
        with self.assertRaises(ValueError):self.run_phase(fail='cleanup_remove')
        d=FakeDocker.instances[-1];self.assertTrue(any(p=='cleanup_volume_owner' for _,p,_ in d.requested))
    def test_typed_natural_flags(self):
        for k,value in [('ExitCode',False),('Pid',False),('Running',0),('OOMKilled',0)]:
            v=dict(NATURAL);v[k]=value
            with self.assertRaises(ValueError):n.validate_natural_exit(v)
    def test_strict_phase_caps_and_eleven_fields(self):
        r,_,_,_=self.run_phase();rows=r['command_metadata'];v=copy.deepcopy(rows);v[0]['observed_retained_bytes']=n.cli_cap(v[0]['phase'])+1
        with self.assertRaises(ValueError):n.validate_cli_records(v)
        for key,value in [('returncode',False),('client_reaped',1),('seconds',True)]:
            v=copy.deepcopy(rows);v[0][key]=value
            with self.assertRaises(ValueError):n.validate_cli_records(v)
    def test_budget_uses_exact_role_output_domain(self):
        for role,total,count in [(role,100020000,2) for role in n.PROFILES]:
            b=n.phase_budget(role,count);self.assertEqual(b['host_artifact_bytes'],total);self.assertLess(b['max_calls'],160);self.assertEqual(b['reply_budget'],174003616)
    def test_request_rejects_bool_clock_and_private_candidate_support(self):
        r=req('reproduction',['estimates.csv','methods.json']);r['setup_seconds']=True
        with self.assertRaises(ValueError):n.validate_request('reproduction',r)
        r=req('reproduction',['estimates.csv','methods.json']);r['entry_support']={'/trusted/BOUND_INPUT_PLAN.json':'BOUND_INPUT_PLAN.json'}
        with self.assertRaises(ValueError):n.validate_request('reproduction',r)
    def test_chunk_bool_fields_and_bad_digest_refused(self):
        holder={'owner':'isttc-'+'a'*24+'/holder'};item={'name':'estimates.csv','bytes':1,'stamp':[1]*9}
        v=dict(schema='isttc_capture_chunk_v1',owner=holder['owner'],role='reproduction',name='estimates.csv',offset=0,bytes=1,stamp=[1]*9,eof=True,sha256=hashlib.sha256(b'x').hexdigest(),base64='eA==')
        self.assertEqual(n.chunk_reply(n.encoded(v),holder,'reproduction',item,0,1),b'x')
        for k,x in [('bytes',True),('offset',False),('eof',1),('sha256','0'*64),('stamp',[True]*9)]:
            bad=copy.deepcopy(v);bad[k]=x
            with self.assertRaises(ValueError):n.chunk_reply(n.encoded(bad),holder,'reproduction',item,0,1)

if __name__=='__main__':unittest.main(verbosity=2)
