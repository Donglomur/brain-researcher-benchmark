"""Ordinary streaming source/artifact custody; no model deserialization.

Large legacy classification artifacts retain their 8,000,000,000-byte cap.
Their bodies are streamed. JSON and headers have separate bounded transports.
This module does not establish scientific correctness or physical isolation.
"""
import ast,hashlib,json,math,os,stat,struct
from pathlib import Path


class Refusal(ValueError):
    def __init__(self,message,*,observation=None):super().__init__(message);self.observation=observation


def need(condition,message):
    if not condition:raise Refusal(message)


def fields(value,names,label):need(type(value) is dict and set(value)==set(names),'exact '+label+' fields')

def integer(value,label,minimum=0,maximum=None):
    need(type(value) is int and value>=minimum and (maximum is None or value<=maximum),label+' bounded integer');return value


def finite(value,label):
    need(type(value) in (float,int) and math.isfinite(value),label+' finite nonboolean number');return value


def digest(value):need(type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value),'SHA256 identity');return value


def relative(value):
    need(type(value) is str and value and '\x00' not in value and '\\' not in value,'ordinary relative path')
    p=Path(value);need(not p.is_absolute() and all(x not in ('','.','..') for x in p.parts) and p.as_posix()==value,'canonical contained relative path');return value


def descriptor(value):
    fields(value,('path','bytes','sha256'),'byte descriptor');relative(value['path']);integer(value['bytes'],'byte extent');digest(value['sha256']);return value


def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def encode(value):
    # Preserve existing valid-Unicode canonical bytes. A lone surrogate in an
    # original OS error is escaped as JSON's literal \\uXXXX, never dropped or
    # replaced. decode(encode(value)) retains that exact Python string.
    try:return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode('utf8','backslashreplace')
    except (ValueError,TypeError,UnicodeError) as exc:raise Refusal('finite strict UTF8 JSON') from exc


def decode(raw):
    def pairs(items):
        result={}
        for key,value in items:need(key not in result,'duplicate JSON field');result[key]=value
        return result
    def constant(_):raise Refusal('nonfinite JSON constant')
    try:result=json.loads(raw.decode('utf8'),object_pairs_hook=pairs,parse_constant=constant)
    except (UnicodeError,json.JSONDecodeError) as exc:raise Refusal('strict complete UTF8 JSON') from exc
    # Python accepts finite-looking exponent syntax that overflows to infinity.
    def visit(value):
        if type(value) is float:need(math.isfinite(value),'finite parsed JSON number')
        elif type(value) is list:
            for x in value:visit(x)
        elif type(value) is dict:
            for x in value.values():visit(x)
    visit(result);return result


def identity(value):return pin(encode(value))['sha256']

def inode(st):return [st.st_dev,st.st_ino,stat.S_IFMT(st.st_mode)]

class FailureObservation(dict):
    """JSON view retaining the actual error and failed description objects."""
    pass


def observation(exc):
    result=FailureObservation();result.original_exception=exc;result.description_exceptions=[]
    result['kind']=type(exc).__name__
    try:result['reason']=str(exc)
    except BaseException as error:
        result.description_exceptions.append(error);result['reason']='original exception description unavailable'
    try:result['observation']=getattr(exc,'observation',None)
    except BaseException as error:
        result.description_exceptions.append(error);result['observation']=None
    if result.description_exceptions:
        result['description_failures']=[{'kind':type(error).__name__,'original_exception_retained':True} for error in result.description_exceptions]
    return result


class HandleCustody:
    """Own original acquisitions and retain raw failures before description.

    Transfer and explicit close retire one handle; finalization attempts every
    remaining handle independently. An ambiguous close is never retried.
    """
    def __init__(self,label):
        self.label=label;self.handles=[];self.original_exception=None;self.secondary_exceptions=[]
        self.record={'scope':label,'primary':None,'secondary':[],'handles':[]};self.closed=False
    def own(self,handle,role):
        need(not self.closed,'original local handle owner still open')
        self.handles.append((role,handle));self.record['handles'].append({'role':role,'status':'owned'})
        return handle
    def own_fd(self,fd,role):
        need(type(fd) is int and fd>=0,'actual acquired descriptor')
        self.own(DescriptorHandle(fd),role);return fd
    def retain_failure(self,error,*,new_occurrence=False):
        # Actual objects are held before any __str__/observation access.
        if not new_occurrence:
            if error is self.original_exception:return self.record['primary']
            for i,prior in enumerate(self.secondary_exceptions):
                if error is prior:return self.record['secondary'][i]
        if self.original_exception is None:
            self.original_exception=error;view=observation(error);self.record['primary']=view
        else:
            self.secondary_exceptions.append(error);view=observation(error);self.record['secondary'].append(view)
        return view
    def _index(self,handle):
        matches=[i for i,(_,actual) in enumerate(self.handles) if actual is handle and self.record['handles'][i]['status']=='owned']
        need(len(matches)==1,'one still-owned original handle');return matches[0]
    def _descriptor(self,fd):
        matches=[h for i,(_,h) in enumerate(self.handles) if type(h) is DescriptorHandle and h.fd==fd and self.record['handles'][i]['status']=='owned']
        need(len(matches)==1,'one still-owned original descriptor');return matches[0]
    def _close_index(self,index):
        row=self.record['handles'][index]
        if row['status']!='owned':return
        handle=self.handles[index][1];row['status']='close_attempted'
        try:handle.close();row['status']='closed'
        except BaseException as error:
            view=self.retain_failure(error,new_occurrence=True)
            row['status']='failed_or_unknown';row['failure']=view;raise
    def close_owned(self,handle):
        need(not self.closed,'explicit close within original owner lifetime')
        self._close_index(self._index(handle))
    def close_fd(self,fd):self.close_owned(self._descriptor(fd))
    def release(self,handle):
        need(not self.closed,'transfer within original owner lifetime')
        self.record['handles'][self._index(handle)]['status']='transferred';return handle
    def release_fd(self,fd):
        handle=self._descriptor(fd);self.release(handle);handle.fd=None;return fd
    def __enter__(self):return self
    def __exit__(self,kind,exc,tb):
        # A clean generator.close is cancellation, not an invented I/O failure.
        # Real close errors still fail through this same original owner.
        if kind is GeneratorExit:self.record['generator_close_requested']=True;self.close()
        else:self.close(exc)
        return False
    def close(self,primary=None):
        need(not self.closed,'one original local finalization');self.closed=True
        if primary is not None:self.retain_failure(primary)
        for index in reversed(range(len(self.handles))):
            try:self._close_index(index)
            except BaseException:pass  # _close_index retained this actual error.
        if self.original_exception is not None:
            failure=Refusal('original local handle operation failed',observation=self.record)
            failure.original_handle_custody=self;raise failure from self.original_exception


class DescriptorHandle:
    """An original FD is closed once; an ambiguous close is never retried."""
    def __init__(self,fd):self.fd=fd
    def close(self):
        fd=self.fd;self.fd=None
        if fd is not None:os.close(fd)


class Directory:
    def __init__(self,path):
        self.path=Path(path);self.fd=None
        need(self.path.is_absolute() and str(self.path)==str(path),'canonical absolute root')
        with HandleCustody('directory_acquisition') as owned:
            fd=owned.own_fd(os.open('/',os.O_RDONLY|os.O_DIRECTORY),'root')
            for ordinal,part in enumerate(self.path.parts[1:]):
                new=owned.own_fd(os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd),'component:'+str(ordinal))
                owned.close_fd(fd);fd=new
            self.original=inode(os.fstat(fd));self.fd=owned.release_fd(fd)
    def verify(self):
        need(self.fd is not None and inode(os.fstat(self.fd))==self.original,'original held directory')
        need(inode(os.stat(self.path,follow_symlinks=False))==self.original,'original named directory')
    def parent(self,name):
        self.verify();parts=relative(name).split('/')
        with HandleCustody('directory_parent_traversal') as owned:
            fd=owned.own_fd(os.dup(self.fd),'parent-root')
            for ordinal,part in enumerate(parts[:-1]):
                new=owned.own_fd(os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd),'component:'+str(ordinal))
                owned.close_fd(fd);fd=new
            return owned.release_fd(fd),parts[-1]
    def close(self):
        fd=self.fd;self.fd=None
        if fd is not None:os.close(fd)  # Ambiguous close is not retried.


def _close(handles):
    failures=[]
    for handle in handles:
        if handle is not None:
            try:os.close(handle)
            except BaseException as exc:failures.append(observation(exc))
    return failures


def guard(ledger,phase):
    if ledger is not None:ledger.guard(phase)


def boundary(ledger,phase,fn,*args,**kwargs):
    """One original deadline around a blocking/source/scientific boundary."""
    guard(ledger,'before_'+phase)
    value=fn(*args,**kwargs)
    guard(ledger,'after_'+phase)
    return value


def account(ledger,dimension,amount,failures):
    try:ledger.observe(dimension,amount)
    except BaseException as exc:failures.append({'phase':'original_accounting',**observation(exc)})


def persist(root,name,raw,*,ledger=None):
    relative(name);need(type(raw) is bytes,'original output bytes');parent=fd=None;written=0;created=None;failure=None
    if ledger is not None:ledger.reserve('output_bytes',len(raw));ledger.reserve_file()
    try:
        parent,leaf=root.parent(name);fd=os.open(leaf,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent);created=inode(os.fstat(fd))
        while written<len(raw):
            guard(ledger,'before_original_publication_chunk');n=os.write(fd,memoryview(raw)[written:]);integer(n,'positive complete output write',1,len(raw)-written);written+=n;guard(ledger,'after_original_publication_chunk')
        guard(ledger,'before_original_publication_fsync');os.fsync(fd);guard(ledger,'after_original_publication_fsync');root.verify();named=os.stat(leaf,dir_fd=parent,follow_symlinks=False)
        need(inode(named)==created and named.st_size==len(raw),'complete original output identity/extent')
    except BaseException as exc:failure=exc
    finally:
        closes=_close((fd,parent))
        if ledger is not None:account(ledger,'output_bytes',written,closes)
        try:guard(ledger,'after_original_publication_close')
        except BaseException as exc:
            if failure is None:failure=exc
            else:closes.append(observation(exc))
    if failure is not None or closes:raise Refusal('publication failed',observation={'path':name,'created_inode':created,'known_written_prefix':pin(raw[:written]),'unknown_physical_tail_possible':failure is not None,'primary':None if failure is None else observation(failure),'close_failures':closes}) from failure
    return {'path':name,**pin(raw)}


def stream_capture(source,name,*,expected=None,size=None,cap,ledger,destination=None,destination_name=None):
    """Read and optionally preserve one actual ordinary file in bounded chunks.

    Actual accepted read/write counts and prefix hashes survive all failures.
    The expected pin comes from trusted source/state custody, never from an
    unverified participant result. Unknown products use actual observed size.
    """
    relative(name);integer(cap,'source cap');need((expected is None)!=(size is None),'one expected pin or original observed extent')
    if expected is not None:descriptor(expected);need(expected['path']==name,'selected source name');size=expected['bytes']
    integer(size,'complete selected extent',0,cap);need((destination is None)==(destination_name is None),'complete capture destination')
    parent=fd=outparent=outfd=None;before=created=None;read_count=written=0;read_hash=hashlib.sha256();write_hash=hashlib.sha256();failure=None
    ledger.reserve('read_bytes',size+1)
    if destination is not None:relative(destination_name);ledger.reserve('output_bytes',size);ledger.reserve_file()
    try:
        parent,leaf=source.parent(name);fd=os.open(leaf,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent);before=os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==size,'ordinary sole-link original source extent')
        if destination is not None:
            outparent,outleaf=destination.parent(destination_name);outfd=os.open(outleaf,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=outparent);created=inode(os.fstat(outfd))
        while read_count<=size:
            guard(ledger,'before_original_source_chunk');chunk=os.read(fd,min(1024*1024,size+1-read_count));read_count+=len(chunk);read_hash.update(chunk);guard(ledger,'after_original_source_chunk')
            if not chunk:break
            need(read_count<=size,'exact original EOF')
            if destination is not None:
                offset=0
                while offset<len(chunk):
                    guard(ledger,'before_original_capture_chunk');n=os.write(outfd,memoryview(chunk)[offset:]);integer(n,'positive streamed capture write',1,len(chunk)-offset);write_hash.update(chunk[offset:offset+n]);written+=n;offset+=n;guard(ledger,'after_original_capture_chunk')
        after=os.fstat(fd);named=os.stat(leaf,dir_fd=parent,follow_symlinks=False)
        need(inode(before)==inode(after)==inode(named) and before.st_mtime_ns==after.st_mtime_ns==named.st_mtime_ns and before.st_size==after.st_size==named.st_size==read_count==size,'same original file at exact EOF')
        source.verify();actual={'path':name,'bytes':read_count,'sha256':read_hash.hexdigest()}
        if expected is not None:need(actual==expected,'complete original captured pin')
        if destination is not None:
            guard(ledger,'before_original_capture_fsync');os.fsync(outfd);guard(ledger,'after_original_capture_fsync');destination.verify();named=os.stat(outleaf,dir_fd=outparent,follow_symlinks=False)
            need(inode(named)==created and named.st_size==written==read_count and write_hash.hexdigest()==read_hash.hexdigest(),'same complete destination and source bytes')
    except BaseException as exc:failure=exc
    finally:
        closes=_close((outfd,outparent,fd,parent));account(ledger,'read_bytes',read_count,closes)
        if destination is not None:account(ledger,'output_bytes',written,closes)
        try:guard(ledger,'after_original_capture_close')
        except BaseException as exc:
            if failure is None:failure=exc
            else:closes.append(observation(exc))
    custody={'source_path':name,'source_inode':None if before is None else inode(before),'known_read_prefix':{'bytes':read_count,'sha256':read_hash.hexdigest()},'destination_path':destination_name,'destination_inode':created,
      'known_written_prefix':None if destination is None else {'bytes':written,'sha256':write_hash.hexdigest()},'unknown_physical_tail_possible':failure is not None and outfd is not None,'close_failures':closes}
    if failure is not None or closes:raise Refusal('original streaming capture failed',observation={**custody,'primary':None if failure is None else observation(failure)}) from failure
    return {'source':actual,'captured':None if destination is None else {'path':destination_name,'bytes':written,'sha256':write_hash.hexdigest()},'custody':custody}


def read_metadata(root,member,*,cap,ledger):
    """Bounded JSON/source metadata; never used to buffer multi-GB arrays."""
    descriptor(member);integer(cap,'metadata cap');need(member['bytes']<=cap,'bounded metadata extent')
    parent=fd=None;parts=[];failure=None;before=None
    ledger.reserve('read_bytes',member['bytes']+1)
    try:
        parent,leaf=root.parent(member['path']);fd=os.open(leaf,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent);before=os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==member['bytes'],'ordinary exact metadata file')
        left=member['bytes']+1
        while left:
            guard(ledger,'before_original_metadata_chunk');chunk=os.read(fd,min(left,65536));parts.append(chunk);left-=len(chunk);guard(ledger,'after_original_metadata_chunk')
            if not chunk:break
        raw=b''.join(parts);after=os.fstat(fd);named=os.stat(leaf,dir_fd=parent,follow_symlinks=False)
        need(inode(before)==inode(after)==inode(named) and before.st_mtime_ns==after.st_mtime_ns==named.st_mtime_ns and before.st_size==after.st_size==named.st_size==len(raw),'same complete metadata file')
        need(pin(raw)=={k:member[k] for k in ('bytes','sha256')},'metadata body pin');root.verify()
    except BaseException as exc:failure=exc
    finally:
        closes=_close((fd,parent));account(ledger,'read_bytes',sum(len(x) for x in parts),closes)
        try:guard(ledger,'after_original_metadata_close')
        except BaseException as exc:
            if failure is None:failure=exc
            else:closes.append(observation(exc))
    if failure is not None or closes:raise Refusal('metadata capture failed',observation={'path':member['path'],'known_read_prefix':pin(b''.join(parts)),'primary':None if failure is None else observation(failure),'close_failures':closes}) from failure
    return raw


def npy_header(raw,*,extent,shape,dtypes=('<f4','<f8'),cap):
    """Validate only the selected NPYv1 header before any payload allocation."""
    need(type(raw) is bytes and len(raw)>=10 and raw[:8]==b'\x93NUMPY\x01\x00','NPYv1 header')
    size=struct.unpack('<H',raw[8:10])[0];need(0<size<=4096 and len(raw)>=10+size,'bounded complete header')
    text=raw[10:10+size];need(text.endswith(b'\n') and (10+size)%16==0,'NPYv1 padding')
    try:value=ast.literal_eval(text.decode('ascii').strip())
    except (ValueError,SyntaxError,UnicodeError) as exc:raise Refusal('literal ASCII array header') from exc
    fields(value,('descr','fortran_order','shape'),'array header');need(value['descr'] in dtypes and value['fortran_order'] is False,'selected nonobject little-endian dtype and C order')
    need(type(shape) is list and shape and all(type(x) is int and x>0 for x in shape),'positive original shape')
    need(type(value['shape']) is tuple and list(value['shape'])==shape,'complete selected shape')
    itemsize=int(value['descr'][-1]);count=1
    for dim in shape:count*=dim;need(count<=cap//itemsize,'bounded shape arithmetic')
    need(extent==10+size+count*itemsize and extent<=cap,'exact original array EOF')
    return {'offset':10+size,'shape':shape,'dtype':value['descr'],'itemsize':itemsize,'cells':count}


def exact_tree(directory,members,*,extra=()):
    """Reject unlisted/symlink/hardlink mount contents before exposing a tree."""
    import stat
    expected={r['path'] for r in members}|set(extra);need(len(expected)==len(members)+len(set(extra)),'unique complete tree inventory');seen=set();directories={'.'}
    for name in expected:
        relative(name)
        directories.update(str(p) for p in Path(name).parents)
    stack=[directory.path]
    while stack:
        base=stack.pop()
        for entry in os.scandir(base):
            rel=str(Path(entry.path).relative_to(directory.path));st=entry.stat(follow_symlinks=False)
            if stat.S_ISDIR(st.st_mode):need(rel in directories,'no unlisted mounted directory');stack.append(Path(entry.path))
            else:need(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and rel in expected,'only inventoried ordinary single-link mount files');seen.add(rel)
    need(seen==expected,'complete mounted source/resource/runtime inventory');directory.verify();return {'members':len(seen),'inventory_identity':identity(members),'extra_metadata':list(extra)}


def seal_tree(directory):
    """Make an operator-owned snapshot read-only before its first use."""
    for base,dirs,files in os.walk(directory.path,topdown=False,followlinks=False):
        for name in files:os.chmod(Path(base)/name,0o444,follow_symlinks=False)
        for name in dirs:os.chmod(Path(base)/name,0o555,follow_symlinks=False)
    os.chmod(directory.path,0o555,follow_symlinks=False);directory.verify()


def persist_chunks(root,name,chunks,*,cap):
    """Bounded reserved failure evidence, full streaming bytes and partial pin.

    Caller reserves finite bytes/files before the operation. This function does
    not reset a deadline or reclaim a failed reservation.
    """
    relative(name);integer(cap,'original reserved streaming publication cap');parent=fd=None;written=0;created=None;sha=hashlib.sha256();failure=None
    try:
        parent,leaf=root.parent(name);fd=os.open(leaf,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent);created=inode(os.fstat(fd))
        for raw in chunks:
            need(type(raw) is bytes and written+len(raw)<=cap,'all original failure evidence fits reserved full extent; no truncation');offset=0
            while offset<len(raw):
                n=os.write(fd,memoryview(raw)[offset:]);integer(n,'original streamed write',1,len(raw)-offset);sha.update(raw[offset:offset+n]);offset+=n;written+=n
        os.fsync(fd);root.verify();named=os.stat(leaf,dir_fd=parent,follow_symlinks=False);need(inode(named)==created and named.st_size==written,'same original full evidence file')
    except BaseException as exc:failure=exc
    finally:closes=_close((fd,parent))
    record={'path':name,'bytes':written,'sha256':sha.hexdigest()}
    if failure is not None or closes:raise Refusal('original reserved streaming evidence publication failed',observation={'path':name,'created_inode':created,'known_written_prefix':record,'unknown_physical_tail_possible':failure is not None,'primary':None if failure is None else observation(failure),'close_failures':closes}) from failure
    return record


def budget_method(fn):
    """Guard complete orchestration methods, including generator advancement.

    Cleanup/failure-evidence methods must not use this decorator: they retain
    their reserved capacity even when the original operational deadline expires.
    """
    from functools import wraps
    import inspect
    if inspect.isgeneratorfunction(fn):
        @wraps(fn)
        def generated(self,*args,**kwargs):
            with HandleCustody('original_generator:'+fn.__name__) as owned:
                iterator=owned.own(fn(self,*args,**kwargs),'iterator')
                while True:
                    self.budget.guard('before_'+fn.__name__+'_advance')
                    try:value=next(iterator)
                    except StopIteration:break
                    self.budget.guard('after_'+fn.__name__+'_advance');yield value
                self.budget.guard('after_'+fn.__name__+'_complete')
        return generated
    @wraps(fn)
    def guarded(self,*args,**kwargs):
        self.budget.guard('before_'+fn.__name__)
        value=fn(self,*args,**kwargs)
        self.budget.guard('after_'+fn.__name__)
        return value
    return guarded


RUNTIME_DEPLOYMENT_ROLE={'path':'DEPLOYMENT.json','template_path':'DEPLOYMENT.template.json','binding':'separately_captured_original_runtime_deployment_v1'}
DEPLOYMENT_TEMPLATE={'path':'DEPLOYMENT.template.json','bytes':181,'sha256':'7b3f4f5e6fb61a615cf4746ec7e5ce514d8d1f15e0090e9a088b99a8cd6957b9'}

def validate_code_source_manifest(manifest):
    """One closed runtime slot; no configurable projection or recursive digest."""
    need(manifest['runtime_deployment_role']==RUNTIME_DEPLOYMENT_ROLE,'only the exact named runtime deployment slot is disjoint')
    members=manifest['operative_members'];need(type(members) is list and len(members)==157,'complete source/control/template closure')
    for member in members:descriptor(member)
    paths=[r['path'] for r in members]
    need(len(set(paths))==len(paths) and 'SOURCE.json' not in paths and 'DEPLOYMENT.json' not in paths,'no code manifest self-reference or runtime deployment in code identity')
    need(DEPLOYMENT_TEMPLATE in members and 'cli.py' in paths and 'programme_worker.py' in paths and 'reference_worker.py' in paths,'exact immutable original null-authority template and whole entrypoints')
    need(manifest['operative_source_identity']==identity(members),'complete ordered immutable code-source identity')
    return manifest
