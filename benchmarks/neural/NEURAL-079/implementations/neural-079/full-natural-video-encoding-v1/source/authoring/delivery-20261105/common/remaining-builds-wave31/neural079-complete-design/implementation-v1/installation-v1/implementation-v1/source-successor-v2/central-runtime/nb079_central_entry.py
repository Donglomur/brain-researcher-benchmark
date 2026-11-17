"""Captured central/prelude source entry. Imports have no filesystem effects."""
import argparse
import hashlib
import importlib.abc
import importlib.util
import json
import os
import stat
import sys
import time
from pathlib import PurePosixPath

DIMS=('source_read_bytes','data_read_bytes','write_bytes','log_bytes','process_starts','validation_calls','logical_float_slots')
MODULES={'nb079_observation_'+n for n in ('common','io','capture','physical','readback','observer')}|{'nb079_launch_contract','nb079_entry_contract'}

def require(ok,message):
    if not ok:raise ValueError(message)

def fields(x,names):require(type(x) is dict and set(x)==set(names),'exact entry metadata fields')
def integer(x,minimum=0):require(type(x) is int and x>=minimum,'finite non-Boolean integer');return x
def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')
def desc(x):
    fields(x,('path','pin'));fields(x['pin'],('bytes','sha256'));integer(x['pin']['bytes'])
    p=x['path'];require(type(p) is str and p.startswith('/') and str(PurePosixPath(p))==p and '..' not in PurePosixPath(p).parts and '\x00' not in p,'canonical entry descriptor')
    h=x['pin']['sha256'];require(type(h) is str and len(h)==64 and all(c in '0123456789abcdef' for c in h),'exact entry digest');return x

def parse(raw):
    def pairs(rows):
        result={}
        for k,v in rows:require(k not in result,'duplicate entry JSON key');result[k]=v
        return result
    def constant(x):raise ValueError('nonfinite entry JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=constant)

def errors(actions,primary=None):
    first=primary
    for name,action in actions:
        try:action()
        except BaseException as error:
            if first is None:first=error
            else:
                old=list(getattr(first,'nb079_entry_secondary',[]));old.append({'phase':name,'type':type(error).__name__});first.nb079_entry_secondary=old
    return first

class EntryClock:
    def __init__(self,value):
        fields(value,('origin','scientific','closeout','outer'));values=[integer(value[k]) for k in ('origin','scientific','closeout','outer')]
        require(all(a<b for a,b in zip(values,values[1:])),'original increasing clock');self.original=dict(value)
        for k,v in value.items():setattr(self,k,v)
    def tick(self,phase):
        require(phase in ('scientific','closeout','outer'),'original named cutoff');now=time.monotonic_ns()
        require(self.origin<=now<getattr(self,phase),'original entry cutoff');return now

class EntryLedger:
    def __init__(self,selection,clock):
        fields(selection['allocation'],DIMS);self.limits={k:integer(v) for k,v in selection['allocation'].items()}
        self.clock=clock;self.maximum_attempts=integer(selection['maximum_attempts'],1);self.counts={k:0 for k in DIMS};self.attempts=[];self.positive={}
    def charge(self,delta,reason,phase='scientific'):
        require(type(delta) is dict and set(delta)<=set(DIMS),'selected additive entry dimension')
        row={'delta':{k:integer(v) for k,v in delta.items()},'reason':reason,'status':'attempted'}
        require(len(self.attempts)<self.maximum_attempts,'bounded entry attempt count');self.attempts.append(row)
        for k,v in row['delta'].items():self.counts[k]+=v
        try:self.clock.tick(phase);require(all(self.counts[k]<=self.limits[k] for k in DIMS),'entry allocation exhausted')
        except BaseException:row['status']='refused';raise
        row['status']='charged'
    def returned(self,name,count):self.positive[name]=self.positive.get(name,0)+integer(count)
    def snapshot(self):return {'allocation':self.limits,'attempted':dict(self.counts),'positive_returns':dict(self.positive),'attempts':list(self.attempts),'physical_total_claim':False}

class EntryCapture:
    def __init__(self,selection):
        fields(selection,('schema','role','original_clock','source_pin','owners','roots','allocation','encoding','limits','maximum_attempts'))
        require(selection['schema']=='nb079_entry_bootstrap_v2' and selection['role'] in ('central_preparation','prelude'),'earlier exact entry selection without own/future descriptor hashes')
        fields(selection['owners'],('policy','request','orchestration_allocation'));[integer(x) for x in selection['owners'].values()]
        fields(selection['roots'],('policy','request','orchestration_allocation'))
        for kind,root in selection['roots'].items():
            fields(root,('path','identity','owner_uid','mode'));fields(root['identity'],('device','inode'))
            require(root['owner_uid']==selection['owners'][kind] and type(root['mode']) is int and root['mode']&0o022==0,'same earlier protected namespace/owner')
        self.selection=selection;self.clock=EntryClock(selection['original_clock']);self.ledger=EntryLedger(selection,self.clock);self.reads=[]
        for k in ('metadata_bytes','source_bytes','live_buffer_bytes','block_bytes','maximum_files'):integer(selection['limits'][k],1)
        require(selection['limits']['block_bytes']<=selection['limits']['live_buffer_bytes'],'bounded initial read buffer')
    def initial(self,kind,path,expected=None):
        """Capture an earlier-fixed protected path. Prelude has no future pin."""
        root=self.selection['roots'][kind]
        require(str(PurePosixPath(path).parent)==root['path'] and str(PurePosixPath(path))==path and '..' not in PurePosixPath(path).parts,'fixed direct child of admitted bootstrap namespace')
        self.ledger.charge({'source_read_bytes':self.selection['limits']['metadata_bytes']+1},'complete bounded initial namespace capture before read')
        parent=None;fd=None;first=None;count=0;digest=hashlib.sha256();parts=[]
        try:
            parent=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            for part in PurePosixPath(root['path']).parts[1:]:
                child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent);old,parent=parent,child;os.close(old)
            st=os.fstat(parent)
            require(stat.S_ISDIR(st.st_mode) and {'device':st.st_dev,'inode':st.st_ino}==root['identity'] and st.st_uid==root['owner_uid'] and stat.S_IMODE(st.st_mode)==root['mode'],'actual earlier protected namespace identity')
            self.clock.tick('scientific');fd=os.open(PurePosixPath(path).name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent);before=os.fstat(fd)
            limit=self.selection['limits'];require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_uid==root['owner_uid'] and not(stat.S_IMODE(before.st_mode)&0o022) and before.st_size<=limit['metadata_bytes'] and 4*before.st_size<=limit['live_buffer_bytes'],'bounded ordinary immutable initial body')
            if expected is not None:require(before.st_size==expected['bytes'],'external selected initial extent')
            while True:
                self.clock.tick('scientific');block=os.read(fd,min(limit['block_bytes'],before.st_size-count+1));self.ledger.returned('source_read_bytes',len(block))
                if not block:break
                count+=len(block);digest.update(block);require(count<=before.st_size,'initial immutable body grew');parts.append(block)
            after=os.fstat(fd);signature=lambda x:(x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns,x.st_nlink,x.st_uid,x.st_gid,x.st_mode)
            named=os.stat(PurePosixPath(path).name,dir_fd=parent,follow_symlinks=False)
            require(count==before.st_size and signature(before)==signature(after)==signature(named),'complete stable named initial body')
            raw=b''.join(parts);item={'path':path,'pin':pin(raw)}
            if expected is not None:require(item['pin']==expected,'complete externally pinned central operand')
            require(len(self.reads)<limit['maximum_files'],'bounded initial capture metadata')
            self.reads.append({'descriptor':item,'namespace':root,'bytes':count,'phase':'scientific'})
            return item,raw
        except BaseException as error:first=error;error.nb079_initial_prefix={'path':path,'namespace':root,'bytes':count,'sha256':digest.hexdigest()};raise
        finally:
            failed=errors(([('initial file close',lambda:os.close(fd))] if fd is not None else [])+([('initial namespace close',lambda:os.close(parent))] if parent is not None else []),first)
            if first is None and failed is not None:raise failed
    def read(self,item,owner,source=False,phase='scientific'):
        desc(item);integer(owner);lim=self.selection['limits'];maximum=lim['source_bytes'] if source else lim['metadata_bytes']
        require(item['pin']['bytes']<=maximum and 4*item['pin']['bytes']<=lim['live_buffer_bytes'],'complete entry capture extent before allocation')
        require(len(self.reads)<lim['maximum_files'],'finite entry capture roster')
        self.ledger.charge({'source_read_bytes':item['pin']['bytes']+1},'entry capture before ordinary read',phase)
        parent=None;fd=None;first=None;count=0;digest=hashlib.sha256();pieces=[]
        try:
            parent=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            for name in PurePosixPath(item['path']).parts[1:-1]:
                child=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent);old,parent=parent,child;os.close(old)
            self.clock.tick(phase);fd=os.open(PurePosixPath(item['path']).name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent);before=os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_uid==owner and before.st_size==item['pin']['bytes'] and not(stat.S_IMODE(before.st_mode)&0o022),'protected ordinary exact source body')
            while True:
                self.clock.tick(phase);block=os.read(fd,min(lim['block_bytes'],item['pin']['bytes']-count+1));self.ledger.returned('source_read_bytes',len(block))
                if not block:break
                count+=len(block);digest.update(block);require(count<=item['pin']['bytes'],'growing captured source');pieces.append(block)
            after=os.fstat(fd);signature=lambda x:(x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns,x.st_nlink,x.st_uid,x.st_gid,x.st_mode)
            named=os.stat(PurePosixPath(item['path']).name,dir_fd=parent,follow_symlinks=False)
            require(signature(before)==signature(after)==signature(named) and count==item['pin']['bytes'] and digest.hexdigest()==item['pin']['sha256'],'whole stable exact entry capture')
            raw=b''.join(pieces);self.reads.append({'descriptor':item,'bytes':count,'phase':phase});return raw
        except BaseException as error:first=error;error.nb079_entry_read_prefix={'descriptor':item,'bytes':count,'sha256':digest.hexdigest()};raise
        finally:
            failed=errors(([('entry captured file close',lambda:os.close(fd))] if fd is not None else [])+([('entry traversal close',lambda:os.close(parent))] if parent is not None else []),first)
            if first is None and failed is not None:raise failed

class CapturedModules(importlib.abc.MetaPathFinder,importlib.abc.Loader):
    def __init__(self,rows,bodies):
        self.rows=rows;self.bodies=bodies;self.loaded=[]
        require(set(rows)==MODULES,'only closed non-parent module set')
        require(all(name not in sys.modules for name in rows),'fresh central helper module namespaces')
    def find_spec(self,fullname,path=None,target=None):
        if fullname in self.rows:return importlib.util.spec_from_loader(fullname,self)
        require(not fullname.startswith(('nb079_observation_','nb079_launch_contract','nb079_entry_contract')),'no ambient helper fallback');return None
    def create_module(self,spec):return None
    def exec_module(self,module):
        name=module.__name__;require(name not in self.loaded,'once-only captured helper execution');self.loaded.append(name)
        module.__file__=self.rows[name]['path'];exec(compile(self.bodies[module.__file__],module.__file__,'exec'),module.__dict__)

def prepare(args,capture=None):
    require(args.independently_enabled,'inactive source entry')
    integer(args.entry_bootstrap_bytes,1);raw=args.entry_bootstrap.encode('ascii')
    require(len(raw)==args.entry_bootstrap_bytes,'exact earlier bootstrap argument extent')
    selection=parse(raw)
    if capture is None:capture=EntryCapture(selection)
    else:require(capture.selection==selection,'same existing pre-placement ledger, no reset')
    require(selection['role']==('central_preparation' if args.mode=='central' else 'prelude'),'source-owned entry mode allocation')
    require(globals().get('_CAPTURED_ENTRY_PIN') is not None and globals().get('_CAPTURED_ENTRY_CLOCK')==[selection['original_clock'][k] for k in ('origin','scientific','closeout','outer')],'genuine captured entry under same original clock')
    wrapper=globals().get('_WRAPPER_PREFIX')
    if wrapper is None:
        capture.ledger.charge({'source_read_bytes':integer(globals().get('_CAPTURED_ENTRY_READ_BYTES'),1)},'actual preceding capture-stub read retained once')
    else:
        require(args.mode=='central' and globals().get('_CAPTURED_ENTRY_READ_BYTES')==0 and
                wrapper['schema']=='nb079_actual_wrapper_prefix_v1' and wrapper['same_process_dispatch'] is True and
                wrapper['actual_argv']==list(sys.orig_argv) and wrapper['original_clock']==selection['original_clock'],
                'actual same-process shared wrapper before central, not another source launch')
        prior=wrapper['reader']
        capture.ledger.charge({'source_read_bytes':integer(prior['read_reserved']),
            'write_bytes':integer(prior['write_reserved'])},'all original wrapper source/qualification/campaign/operand attempts transferred once')
        capture.ledger.returned('source_read_bytes',integer(prior['read_observed']))
        capture.ledger.returned('write_bytes',integer(prior['write_observed']))
        capture.wrapper_prefix=wrapper
    supplied=(args.policy_bytes,args.policy_sha256,args.request_bytes,args.request_sha256)
    require(all(x is None for x in supplied) if args.mode=='prelude' else all(x is not None for x in supplied),'prelude earlier paths contain no own/future pin; central has both external pins')
    qexpected=None if args.mode=='prelude' else {'bytes':integer(args.policy_bytes),'sha256':args.policy_sha256}
    rexpected=None if args.mode=='prelude' else {'bytes':integer(args.request_bytes),'sha256':args.request_sha256}
    qd,qraw=capture.initial('policy',args.policy,qexpected);q=parse(qraw)
    require(q['source_pin']==selection['source_pin'] and q['original_clock']==selection['original_clock'],'earlier source/clock matched before helper loading')
    require(q['prelude']['path']==__file__ and q['prelude']['pin']==globals()['_CAPTURED_ENTRY_PIN'],'actual captured entry bytes selected')
    require(pin(canonical(q['sources']))==q['source_pin'],'closed exact source manifest')
    if wrapper is not None:
        prior_source=wrapper['source_manifest']
        require({'path':prior_source['path'],'pin':{k:prior_source[k]for k in ('bytes','sha256')}} in q['sources'],'same actual wrapper manifest in central source closure')
    total=sum(desc(row)['pin']['bytes']+1 for row in q['sources']);require(total<=selection['allocation']['source_read_bytes'],'complete source capacity before loading')
    require(sum(row['pin']['bytes'] for row in q['sources'])*4<=selection['limits']['live_buffer_bytes'],'all captured source bodies admitted live')
    bodies={}
    for row in q['sources']:
        require(row['path'] not in bodies and row['path'] in q['descriptor_owners'],'unique exactly owned source');bodies[row['path']]=capture.read(row,q['descriptor_owners'][row['path']],True)
    loader=CapturedModules(q['source_modules'],bodies);sys.meta_path.insert(0,loader)
    try:
        from nb079_observation_observer import validate_policy
        from nb079_observation_common import bounded_decode,bounded_encode
        from nb079_entry_contract import validate_orchestration,selected_row
        validate_policy(q);bounded_encode(selection,selection['encoding'])
        rd,rraw=capture.initial('request',args.request,rexpected);r=bounded_decode(rraw,selection['encoding'])
        fields(r,('schema','canonical_task_id','condition','run_nonce','effective_parent_selection','parent_template','profile','module_manifest','source_closure','original_clock','prepared_namespace_receipt','credential_route','external_authority','central_source_selection','central_output_path','central_limits','orchestration_allocation','deployment_and_spend_selection'))
        require(r['schema']=='n079_central_launch_request_v1' and r['canonical_task_id']=='NEURAL-079' and r['condition']=='full_natural_video_encoding_v1','exact complete named request')
        require(r['central_source_selection']==qd and r['original_clock']==selection['original_clock'],'actual immutable R distinct from earlier Qc')
        _,araw=capture.initial('orchestration_allocation',r['orchestration_allocation']['path'],r['orchestration_allocation']['pin']);allocation=bounded_decode(araw,selection['encoding'])
        validate_orchestration(allocation,q['source_pin'],q['original_clock']);selected_row(allocation,selection['role'],selection)
        require(dict(os.environ)==q['environment'],'literal clean entry environment')
        from nb079_observation_io import ProtectedIO,LinuxIdentity
        io=ProtectedIO(capture.clock,capture.ledger,selection['limits'],selection['encoding'],selection['owners']['policy'])
        identity=LinuxIdentity(capture.clock,capture.ledger,selection['limits']['proc_bytes'])
        return {'args':args,'selection':selection,'capture':capture,'clock':capture.clock,'ledger':capture.ledger,'io':io,'identity':identity,'q':q,'r':r,'qd':qd,'rd':rd,'loader':loader,'source_bodies':bodies,'allocation':allocation}
    except BaseException as primary:
        errors([('remove acquired source loader',lambda:sys.meta_path.remove(loader))],primary)
        raise

def owner_for(env,path):
    q=env['q']
    if path in q['descriptor_owners']:return q['descriptor_owners'][path]
    choices=[root['owner_uid'] for root in q['roots'].values() if str(PurePosixPath(path).parent)==root['path']]
    require(len(choices)==1,'one explicitly selected protected owner for late descriptor');return choices[0]

def read_json(env,item,phase='scientific'):
    return env['io'].json(item,phase,owner_for(env,item['path']))

def fifo_observation(env,fd):
    import fcntl
    integer(fd,3);route=env['r']['credential_route']['fifo'];before=os.fstat(fd);flags=fcntl.fcntl(fd,fcntl.F_GETFL)
    require(stat.S_ISFIFO(before.st_mode) and {'device':before.st_dev,'inode':before.st_ino}==route['identity'] and before.st_uid==route['owner_uid'] and stat.S_IMODE(before.st_mode)==route['mode'],'actual inherited protected FIFO')
    require(flags&os.O_ACCMODE==os.O_RDONLY and flags&os.O_NONBLOCK,'read-only nonblocking opaque FIFO descriptor')
    return {'fd':fd,'device':before.st_dev,'inode':before.st_ino,'owner_uid':before.st_uid,'mode':stat.S_IMODE(before.st_mode),'access_mode':os.O_RDONLY,'nonblocking':True,'observed_ns':env['clock'].tick('scientific')}

def read_release(env,fd):
    from nb079_observation_common import bounded_decode
    integer(fd,3);require(stat.S_ISFIFO(os.fstat(fd).st_mode),'actual owned release pipe');os.set_blocking(fd,False)
    maximum=env['selection']['limits']['release_bytes'];pieces=[];count=0
    while True:
        env['clock'].tick('scientific');env['ledger'].charge({'data_read_bytes':min(65536,maximum-count+1)},'bounded actual prelude release read')
        try:block=os.read(fd,min(65536,maximum-count+1))
        except BlockingIOError:time.sleep(min(env['selection']['limits']['poll_ns'],env['clock'].scientific-env['clock'].tick('scientific'))/1e9);continue
        env['ledger'].returned('release_read_bytes',len(block))
        if not block:break
        count+=len(block);require(count<=maximum,'whole immutable release descriptor');pieces.append(block)
    item=bounded_decode(b''.join(pieces),env['selection']['encoding']);desc(item);return item

def logical_argv(env,L,Q):
    bootstrap=Q['bootstrap_program'];argv=[bootstrap['bootstrap']['path'],'--entry-mode','outer','--independently-enabled']
    for flag,item in (('role-config',L['K']),('source-manifest',env['r']['module_manifest']),('outer-profile',env['r']['profile']),('configuration-admission',L['B0'])):
        argv+=['--'+flag,item['path'],'--'+flag+'-bytes',str(item['pin']['bytes']),'--'+flag+'-sha256',item['pin']['sha256']]
    argv+=['--max-source-bytes',str(bootstrap['max_source_bytes']),'--max-bootstrap-metadata-bytes',str(bootstrap['max_bootstrap_metadata_bytes'])]
    require(L['logical_bootstrap_argv']==argv,'exact constructed logical bootstrap invocation');return argv,bootstrap['bootstrap']

def atomic_returns(env,prefix):
    if prefix is None:return
    prior=env.setdefault('atomic_observed',{'source_read_bytes':0,'write_bytes':0})
    for category,key in (('source_read_bytes','returned_source_bytes'),('write_bytes','returned_write_bytes')):
        observed=integer(prefix[key]);require(observed>=prior[category],'monotone actual atomic returns')
        delta=observed-prior[category]
        if delta:env['ledger'].returned(category,delta)
        prior[category]=observed

def atomic_publisher(env):
    if 'publisher' in env:return env['publisher']
    Q=read_json(env,env['r']['external_authority'])
    require(all(Q['earlier'][k]==env['r'][k] for k in Q['earlier']) and Q['run_nonce']==env['r']['run_nonce'],'earlier authority and later request joins')
    selection=Q['publication'];implementation=selection['implementation'];desc(implementation)
    require(implementation in env['q']['sources'] and implementation['path'] in env['source_bodies'] and pin(env['source_bodies'][implementation['path']])==implementation['pin'],'exact standalone atomic source in captured central closure')
    namespace={'__name__':'nb079_atomic_publication_central','__file__':implementation['path'],'__package__':None}
    exec(compile(env['source_bodies'][implementation['path']],implementation['path'],'exec'),namespace)
    limits=env['selection']['limits']
    selected={'maximum_source_bytes':limits['source_bytes'],'maximum_publication_bytes':limits['publication_bytes'],
        'block_bytes':limits['block_bytes'],'maximum_publications':limits['maximum_files'],
        'maximum_total_write_bytes':env['selection']['allocation']['write_bytes'],
        'maximum_path_chars':env['selection']['encoding']['string_chars']}
    env['ledger'].charge({'source_read_bytes':implementation['pin']['bytes']+selection['libc']['pin']['bytes']+2},'exact atomic implementation/libc capture before native-library loading')
    try:publisher=namespace['AtomicPublication'](selection,env['q']['original_clock'],selected,execution_enabled=True)
    except BaseException as error:
        env['atomic_constructor_failure']=getattr(error,'atomic_prefix',None)
        raise errors([('retain atomic constructor returns',lambda:atomic_returns(env,env['atomic_constructor_failure']))],error)
    env['publisher']=publisher;env['authority_policy']=Q;atomic_returns(env,publisher.prefix())
    return publisher

def publish(env,root,name,value,phase='scientific'):
    from nb079_observation_common import bounded_encode
    raw=bounded_encode(value,env['selection']['encoding'])
    publisher=atomic_publisher(env)
    env['ledger'].charge({'write_bytes':len(raw)},'whole atomic metadata publication before write',phase)
    attempt={'root':root,'name':name,'body_pin':pin(raw),'status':'attempted'}
    env.setdefault('atomic_attempts',[]).append(attempt)
    try:
        result=publisher.publish(root,name,raw,phase=phase);desc(result['descriptor'])
        require(result['descriptor']=={'path':root['path']+'/'+name,'pin':pin(raw)},'actual complete atomic publication descriptor')
        attempt.update(status='complete',record=result['record']);atomic_returns(env,publisher.prefix())
        env['clock'].tick(phase);return result['descriptor']
    except BaseException as error:
        attempt.update(status='failed',failure_type=type(error).__name__,prefix=getattr(error,'atomic_prefix',None))
        raise errors([('retain failed atomic returns',lambda:atomic_returns(env,publisher.prefix()))],error)

def discover(env,root,name,phase='scientific'):
    """Only atomically published final names are visible protocol operands."""
    from nb079_observation_io import open_directory,verify_root,signature
    from nb079_observation_common import bounded_decode
    require(type(name) is str and name and '/' not in name and name not in ('.','..'),'fixed one-leaf protocol path')
    directory=None;fd=None;first=None;raw=None;count=0;h=hashlib.sha256()
    try:
        directory=open_directory(root['path']);verify_root(directory,root);env['clock'].tick(phase)
        try:fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=directory)
        except FileNotFoundError:return None
        before=os.fstat(fd);limits=env['selection']['limits']
        require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_uid==root['owner_uid'] and not(stat.S_IMODE(before.st_mode)&0o022) and before.st_size<=limits['metadata_bytes'] and 4*before.st_size<=limits['live_buffer_bytes'],'whole protected ordinary protocol body')
        env['ledger'].charge({'source_read_bytes':before.st_size+1},'complete newly atomically published metadata read',phase);parts=[]
        while True:
            env['clock'].tick(phase);block=os.read(fd,min(limits['block_bytes'],before.st_size-count+1));env['ledger'].returned('source_read_bytes',len(block))
            if not block:break
            count+=len(block);h.update(block);require(count<=before.st_size,'growing protocol body');parts.append(block)
        require(count==before.st_size and signature(before)==signature(os.fstat(fd)),'whole unchanged published protocol body')
        raw=b''.join(parts);body=bounded_decode(raw,env['selection']['encoding'])
        require(canonical(body)==raw,'canonical complete source-owned protocol artifact')
        item={'path':root['path']+'/'+name,'pin':pin(raw)}
        env.setdefault('protocol_captures',[]).append({'descriptor':item,'root':root,'phase':phase})
        return {'descriptor':item,'body':body}
    except BaseException as error:
        first=error;error.nb079_protocol_prefix={'root':root,'name':name,'bytes':count,'sha256':h.hexdigest(),'raw_received':raw};raise
    finally:
        failed=errors(([('protocol file close',lambda:os.close(fd))] if fd is not None else [])+([('protocol root close',lambda:os.close(directory))] if directory is not None else []),first)
        if first is None and failed is not None:raise failed

def await_protocol(env,root,name):
    while True:
        env['ledger'].charge({'validation_calls':1},'bounded protected protocol discovery attempt')
        result=discover(env,root,name)
        if result is not None:return result
        remaining=env['clock'].scientific-env['clock'].tick('scientific')
        time.sleep(min(env['selection']['limits']['poll_ns'],remaining)/1e9)

def initial_exchange(env,Q,kind,body):
    require(kind in ('central_start','reader_ready','blocked_finalizer'),'source-owned initial request kind')
    request=publish(env,Q['roots']['request'],Q['protocol']['initial_requests'][kind],body)
    response=await_protocol(env,Q['roots']['response'],Q['protocol']['initial_responses'][kind])
    return request,response

def central(env):
    from nb079_observation_io import open_directory,verify_root
    from nb079_observation_observer import CentralObserver
    from nb079_observation_common import bounded_encode
    args=env['args'];q=env['q'];r=env['r'];first=None;observer=None;credential_fd=None;root_fd=None;result=None;state={'phase':'entry_prepared'}
    try:
        require(args.output==q['central_output']['path']==r['central_output_path'],'exact shared-CLI selected fresh output path')
        require(all(getattr(args,n) is None for n in ('release_fd','ready_fd','credential_fd')),'central has no pre-CLI inherited descriptor assumption')
        require(r['schema']=='n079_central_launch_request_v1' and r['canonical_task_id']=='NEURAL-079' and r['condition']=='full_natural_video_encoding_v1','named complete inactive route request')
        own=env['identity'].observe(os.getpid());require({k:own[k] for k in q['central_expected']}==q['central_expected'],'actual selected central runtime')
        env['ledger'].charge({'process_starts':1},'current central original process observed; not a second observer process')
        intended=q['central_output'];parent=None;error=None
        try:
            parent=open_directory(intended['parent']['path']);verify_root(parent,intended['parent']);env['clock'].tick('scientific')
            os.mkdir(PurePosixPath(intended['path']).name,intended['mode'],dir_fd=parent);os.fsync(parent)
            root_fd=open_directory(intended['path']);st=os.fstat(root_fd)
            output={'path':intended['path'],'identity':{'device':st.st_dev,'inode':st.st_ino},'owner_uid':st.st_uid,'mode':stat.S_IMODE(st.st_mode)}
            require(output['owner_uid']==intended['owner_uid'] and output['mode']==intended['mode'],'actual newly created protected output identity')
            state.update(phase='actual_output_created',actual_central_identity=own,central_output_root=output)
        except BaseException as exc:error=exc;raise
        finally:
            failed=errors([] if parent is None else [('created-output namespace parent close',lambda:os.close(parent))],error)
            if error is None and failed is not None:raise failed
        Q=read_json(env,r['external_authority'])
        fields(Q['protocol']['initial_requests'],('central_start','reader_ready','writer_open','blocked_finalizer'))
        fields(Q['protocol']['initial_responses'],('central_start','reader_ready','writer_open','blocked_finalizer'))
        require(Q['central_observer_policy']==env['qd'] and Q['run_nonce']==r['run_nonce'],'same earlier source-selected external authority')
        central_request={'schema':'nb079_central_start_request_v1','run_nonce':r['run_nonce'],'policy':env['qd'],'request':env['rd'],'source_pin':q['source_pin'],'profile_pin':q['profile']['pin'],'study_pin':q['study_pin'],'original_clock':q['original_clock'],'actual_central_identity':own,'central_output_root':output,'prepared_roots_pin':pin(canonical(q['roots']))}
        request,accepted=initial_exchange(env,Q,'central_start',central_request)
        require(accepted['descriptor']['path']==q['detached_admission']['path'] and accepted['body']['central_start_request_pin']==request['pin'],'exact later Ac admission binds published actual request')
        state['central_admission']=accepted
        observer=CentralObserver({'schema':'nb079_central_observer_config_v1','execution_enabled':True,'policy':env['qd'],'request':env['rd'],'admission':accepted['descriptor'],'bootstrap':q['bootstrap']})
        # Observer independently verifies all Ac fields and actual source/root facts.
        route=r['credential_route'];fifo=route['fifo'];parent=None;error=None
        try:
            parent=open_directory(str(PurePosixPath(fifo['path']).parent));env['clock'].tick('scientific')
            credential_fd=os.open(PurePosixPath(fifo['path']).name,os.O_RDONLY|os.O_NONBLOCK|os.O_CLOEXEC|os.O_NOFOLLOW,dir_fd=parent)
        except BaseException as exc:error=exc;raise
        finally:
            failed=errors([] if parent is None else [('opaque FIFO namespace close',lambda:os.close(parent))],error)
            if error is None and failed is not None:raise failed
        fifo_meta=fifo_observation(env,credential_fd)
        reader={'schema':'n079_opaque_reader_ready_request_v1','run_nonce':r['run_nonce'],'request_pin':env['rd']['pin'],'central_source_pin':q['source_pin'],'original_clock':q['original_clock'],'fifo_identity':fifo['identity'],'reader_fd_observation':fifo_meta,'feeder_selection_pin':route['feeder_selection']['pin']}
        reader_request,reader_admission=initial_exchange(env,Q,'reader_ready',reader)
        require(reader_admission['body']['reader_ready_request_pin']==reader_request['pin'] and reader_admission['body']['request_pin']==env['rd']['pin'] and reader_admission['body']['decision']=='verified_actual_read_only_fifo','actual independently observed reader admission')
        writer=await_protocol(env,Q['roots']['request'],Q['protocol']['initial_requests']['writer_open'])
        writer_admission=await_protocol(env,Q['roots']['response'],Q['protocol']['initial_responses']['writer_open'])
        require(writer['body']['reader_ready_request_pin']==reader_request['pin'] and writer['body']['fifo_identity']==fifo['identity'] and writer_admission['body']['writer_open_ack']==writer['descriptor'] and writer_admission['body']['request_pin']==env['rd']['pin'] and writer_admission['body']['decision']=='verified_live_sole_writer','actual selected writer and independently authenticated open acknowledgment')
        state.update(phase='opaque_fifo_handshake',reader=reader_request,writer=writer,writer_admission=writer_admission)
        blocked=observer.launch(q['argv_template'],q['environment'],credential_fd)
        # Successful pass_fds/readiness is the handoff; parent copy is detached
        # before close, never retained until the credential EOF boundary.
        old,credential_fd=credential_fd,None;os.close(old)
        launch_request={'schema':'n079_blocked_finalizer_request_v1','run_nonce':r['run_nonce'],'request_pin':env['rd']['pin'],'source_pin':q['parent_source_pin'],'template_pin':r['parent_template']['pin'],'profile_pin':q['profile']['pin'],'original_clock':q['original_clock'],'reader_ready_request_pin':reader_request['pin'],'writer_open_ack_pin':writer['descriptor']['pin'],'actual_blocked_identity':blocked['identity'],'actual_initial_argv':observer.actual_argv,'inherited_fifo_observation':fifo_meta,'blocked_observation':blocked}
        launch,release=initial_exchange(env,Q,'blocked_finalizer',launch_request)
        require(release['body']['launch_request_pin']==launch['pin'],'original actual blocked launch issued before L')
        state.update(phase='released',blocked=blocked,release=release['descriptor'])
        observer.release(release['descriptor']);original=observer.finish();readback=observer.readback(original)
        fields(readback,('path','bytes','sha256'),'actual complete readback artifact descriptor')
        require(readback['path']==output['path'].rstrip('/')+'/CENTRAL_READBACK.json','distinct fixed actual readback artifact before complete result publication')
        prelude_closed=discover(env,q['roots']['parent_report'],'PRELUDE_CLOSED.json','outer')
        require(prelude_closed is not None,'actual successful prelude closeout after original parent return')
        pc=prelude_closed['body']
        require(pc['schema']=='nb079_prelude_closed_v1' and pc['status']=='complete' and pc['source_pin']==q['source_pin'] and pc['request_pin']==env['rd']['pin'] and pc['policy_pin']==env['qd']['pin'] and pc['original_clock']==q['original_clock'] and pc['initial_identity']==blocked['identity'] and pc['inherited_descriptors_closed'] is True,'same original process/source/clock with complete inherited-descriptor cleanup')
        atomic_parent=discover(env,q['roots']['parent_report'],'ATOMIC_AUTHORITY_CLOSED.json','outer')
        require(atomic_parent is not None and atomic_parent['body']['schema']=='n079_atomic_authority_closed_v1' and atomic_parent['body']['source_pin']==q['parent_source_pin'] and atomic_parent['body']['original_clock']==q['original_clock'],'same source-owned original parent metadata publication closure')
        result={'schema':'nb079_complete_central_result_v1','status':'complete_source_route_return','canonical_task_id':'NEURAL-079','condition':'full_natural_video_encoding_v1','request':env['rd'],'policy':env['qd'],'central_admission':accepted['descriptor'],'original_finalizer_return':original,'readback':readback,'prelude_closeout':prelude_closed,'atomic_parent_closeout':atomic_parent,'source_pin':q['source_pin'],'parent_source_pin':q['parent_source_pin'],'original_clock':q['original_clock'],'orchestration_allocation':r['orchestration_allocation'],'wrapper_prefix':getattr(env['capture'],'wrapper_prefix',None),'preparation_ledger_before_result':env['ledger'].snapshot(),'observer_prefix':observer.snapshot(),'atomic_prefix':env['publisher'].prefix(),'boundaries':{'central_natural_completion':'must be independently observed outside this still-running process','authority_feeder_waits':'external original observations required; not supplied by this process','scientific_qualification':False,'physical_total_claim':False,'parent_inventory_precedes_prelude_artifact':True}}
        observer.close();observer=None
        state['phase']='original_finalizer_and_observer_closed'
        artifact=publish(env,output,'CENTRAL_RESULT.json',result,'outer')
        frame=bounded_encode({'schema':'nb079_complete_central_terminal_v1','status':'complete','result':artifact,'boundary':'whole stdout frame and original central natural completion require independent external observation'},env['selection']['encoding'])+b'\n'
        require(len(frame)<=env['selection']['limits']['stream_bytes'],'complete central terminal cap');env['ledger'].charge({'write_bytes':len(frame),'log_bytes':len(frame)},'whole central stdout frame before write','outer')
        done=0
        while done<len(frame):
            env['clock'].tick('outer');n=os.write(1,memoryview(frame)[done:]);require(type(n) is int and 0<n<=len(frame)-done,'positive full central terminal write');done+=n;env['ledger'].returned('write_bytes',n)
        result={'artifact':artifact,'stdout_bytes':done,'ledger':env['ledger'].snapshot()};env['clock'].tick('outer')
    except BaseException as error:first=error
    finally:
        actions=[]
        if credential_fd is not None:fd,credential_fd=credential_fd,None;actions.append(('central opaque reader copy close',lambda fd=fd:os.close(fd)))
        if observer is not None:actions.append(('actual observer owned close',lambda:observer.close(first)))
        if root_fd is not None:fd,root_fd=root_fd,None;actions.append(('central output descriptor close',lambda fd=fd:os.close(fd)))
        first=errors(actions,first)
        if first is not None:
            first.nb079_complete_central_prefix={'state':state,'ledger':env['ledger'].snapshot(),'protocol_captures':env.get('protocol_captures',[]),'atomic_attempts':env.get('atomic_attempts',[]),'atomic_prefix':None if 'publisher' not in env else env['publisher'].prefix(),'result':result,'complete':False}
    if first is not None:raise first
    env['clock'].tick('outer');return result

def prelude(env,owned):
    args=env['args'];require(len(set(owned.values()))==3,'three distinct owned inherited pipes')
    first=None;answer=None;original_argv=list(sys.argv);initial_identity=None
    try:
        fifo=fifo_observation(env,owned['credential_fd']);initial_identity=env['identity'].observe(os.getpid())
        expected=env['q']['finalizer_expected'];require({k:initial_identity[k] for k in expected}==expected,'actual original selected finalizer identity before readiness')
        st=os.fstat(owned['ready_fd']);require(stat.S_ISFIFO(st.st_mode),'actual private readiness pipe')
        env['ledger'].charge({'write_bytes':1},'one readiness byte');require(os.write(owned['ready_fd'],b'R')==1,'complete ready byte');env['ledger'].returned('write_bytes',1)
        fd=owned.pop('ready_fd');os.close(fd)
        Ld=read_release(env,owned['release_fd']);fd=owned.pop('release_fd');os.close(fd)
        L=read_json(env,Ld);fields(L,('schema','run_nonce','launch_request_pin','request_pin','source_pin','original_clock','actual_blocked_identity','initial_argv','logical_bootstrap_argv','template_pin','profile_pin','reader_ready_request_pin','writer_open_ack_pin','inherited_fifo_observation','I0','A0','K','B0','output_bindings','decision'))
        require(L['schema']=='n079_blocked_finalizer_release_v1' and L['decision']=='issued_exact_source_owned_release' and L['request_pin']==env['rd']['pin'] and L['run_nonce']==env['r']['run_nonce'] and L['source_pin']==env['q']['parent_source_pin'] and L['original_clock']==env['q']['original_clock'] and L['actual_blocked_identity']==initial_identity and L['template_pin']==env['r']['parent_template']['pin'] and L['profile_pin']==env['q']['profile']['pin'],'complete actual source-owned finalizer release')
        env['identity'].argv_environment(os.getpid(),L['initial_argv'],env['q']['environment'])
        actual_fifo=fifo_observation(env,owned['credential_fd'])
        require(all(actual_fifo[k]==L['inherited_fifo_observation'][k] for k in actual_fifo if k!='observed_ns') and actual_fifo['inode']==fifo['inode'],'same entire actual opaque descriptor at release')
        objects={name:read_json(env,L[name]) for name in ('I0','A0','K','B0')};T=read_json(env,env['r']['parent_template'])
        from nb079_launch_contract import validate_pre_k
        validate_pre_k(T,objects['K'],objects['A0'],owned['credential_fd'])
        A,K,B,I=objects['A0'],objects['K'],objects['B0'],objects['I0']
        require(A['role_identity']==initial_identity and I['roles']=={'finalizer':initial_identity} and A['issuer_receipt']==L['I0'],'actual separate initial finalizer issuer')
        require(B['configuration_pin']==pin(canonical(K)) and B['clock']==env['q']['original_clock'] and B['source_pin']==env['q']['parent_source_pin'] and B['profile_pin']==env['q']['profile']['pin'] and B['base_source_admission_pin']==pin(canonical(A)),'detached whole K/source/profile/clock binding')
        require(L['output_bindings']=={k:K[k] for k in ('stream_root','report_root','output_roots')},'all original output bindings')
        Q=read_json(env,env['r']['external_authority']);argv,bootstrap=logical_argv(env,L,Q)
        require(bootstrap in A['sources'],'genuine parent bootstrap in actual admitted closure')
        body=env['io'].capture(bootstrap,'scientific',maximum=env['selection']['limits']['source_bytes'],owner_uid=owner_for(env,bootstrap['path']))
        manifest=read_json(env,env['r']['module_manifest']);require(all(name not in sys.modules for name in manifest['modules']),'no parent namespace preloaded by prelude')
        require(env['identity'].observe(os.getpid())==initial_identity,'stable original PID/start/executable/namespaces/cgroup before parent')
        env['ledger'].charge({'validation_calls':1},'captured genuine parent bootstrap invocation')
        # No execve: original sys.orig_argv is retained; genuine argparse gets K.
        sys.argv=argv;namespace={'__name__':'__main__','__file__':bootstrap['path'],'__package__':None}
        exec(compile(body,bootstrap['path'],'exec'),namespace)
        require(env['identity'].observe(os.getpid(),'outer')==initial_identity,'same original process after complete parent return')
        env['clock'].tick('outer');answer={'status':'parent_returned','entry_ledger':env['ledger'].snapshot(),'initial_identity':initial_identity,'captured_parent':bootstrap}
    except BaseException as error:first=error
    finally:
        sys.argv=original_argv;actions=[]
        for name,fd in list(owned.items()):del owned[name];actions.append((name+' close',lambda fd=fd:os.close(fd)))
        first=errors(actions,first)
        if first is not None:first.nb079_prelude_prefix={'entry_ledger':env['ledger'].snapshot(),'initial_identity':initial_identity,'complete':False}
    if first is not None:raise first
    env['clock'].tick('outer')
    root=env['q']['roots']['parent_report']
    record={'schema':'nb079_prelude_closed_v1','source_pin':env['q']['source_pin'],'request_pin':env['rd']['pin'],'policy_pin':env['qd']['pin'],'original_clock':env['q']['original_clock'],'status':'complete','initial_identity':initial_identity,'captured_parent':answer['captured_parent'],'entry_ledger_before_this_publication':env['ledger'].snapshot(),'capture_reads':env['capture'].reads,'inherited_descriptors_closed':True,'parent_terminal_unchanged':True,'boundary':'logical prefix before this additive artifact publication; whole framing separately observed by central, no physical total'}
    publish(env,root,'PRELUDE_CLOSED.json',record,'outer')
    env['clock'].tick('outer');return answer

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--independently-enabled',action='store_true');parser.add_argument('--mode',choices=('central','prelude'),required=True)
    parser.add_argument('--entry-bootstrap',required=True);parser.add_argument('--entry-bootstrap-bytes',type=int,required=True)
    for key in ('policy','request'):
        parser.add_argument('--'+key,required=True);parser.add_argument('--'+key+'-bytes',type=int);parser.add_argument('--'+key+'-sha256')
    for name in ('release-fd','ready-fd','credential-fd'):parser.add_argument('--'+name,type=int)
    parser.add_argument('--output')
    args=parser.parse_args();env=None;first=None;result=None;inherited={};early_capture=None
    try:
        require(args.independently_enabled,'inactive source entry before FD/clock effects')
        integer(args.entry_bootstrap_bytes,1)
        require(len(args.entry_bootstrap.encode('ascii'))==args.entry_bootstrap_bytes,'exact earlier bootstrap extent before parsing')
        selected=parse(args.entry_bootstrap);early_capture=EntryCapture(selected)
        if args.mode=='prelude':
            inherited={k:integer(getattr(args,k),3) for k in ('release_fd','ready_fd','credential_fd')}
            require(len(set(inherited.values()))==3,'unique inherited ownership')
            # This fixed one-byte first gate permits actual owned-child cgroup
            # placement before process identity/source policy preparation.
            clock=early_capture.clock
            fd=inherited['release_fd'];os.set_blocking(fd,False)
            while True:
                early_capture.ledger.charge({'data_read_bytes':1},'bounded placement-pipe read attempted before effect')
                try:placed=os.read(fd,1)
                except BlockingIOError:time.sleep(min(selected['limits']['poll_ns'],clock.scientific-clock.tick('scientific'))/1e9);continue
                early_capture.ledger.returned('placement_read_bytes',len(placed))
                require(placed==b'P','actual source-owned placement gate before prelude preparation');break
        env=prepare(args,early_capture)
        if args.mode=='prelude':
            owned,inherited=inherited,{};result=prelude(env,owned)
        else:result=central(env)
    except BaseException as error:first=error
    finally:
        actions=[]
        for name,fd in list(inherited.items()):del inherited[name];actions.append((name+' pre-prepare close',lambda fd=fd:os.close(fd)))
        if env is not None:actions.append(('captured helper import finder removal',lambda:sys.meta_path.remove(env['loader'])))
        first=errors(actions,first)
        if first is not None:
            capture=env['capture'] if env is not None else early_capture
            first.nb079_entry_prefix={'ledger':None if capture is None else capture.ledger.snapshot(),'capture_reads':[] if capture is None else capture.reads,'complete':False}
    if first is not None:raise first
    return result

if __name__=='__main__':main()
