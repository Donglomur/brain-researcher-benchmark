"""Explicit private atomic artifacts and durable hash-chain journal.

No filesystem discovery, reopen/recovery or import-time effects. The exclusive
0700 root is controlled by one trusted host store. Arbitrary same-UID host code is
outside this custody boundary; no claim to resist a hostile administrator.
"""
from dataclasses import dataclass,asdict
import hashlib
import json
import os
import posixpath
import re
import stat
import threading
from ..core.custody import VerifiedAuthority,canonical,digest,require_digest


class StoreError(RuntimeError):
    def __init__(self,message,incident=None):
        self.incident=incident
        super().__init__(message)


def _absolute(path):
    if not isinstance(path,str) or not path.startswith('/') or path=='/' or posixpath.normpath(path)!=path or '\x00' in path:
        raise StoreError('explicit canonical nonroot absolute path required')


def _overlap(a,b):
    return a==b or a.startswith(b.rstrip('/')+'/') or b.startswith(a.rstrip('/')+'/')


@dataclass(frozen=True)
class StoreAdmission:
    root:str
    run_id:str
    single_artifact_bytes:int
    total_write_bytes:int
    journal_record_bytes:int
    store_contract_digest:str
    public_mount_roots:tuple

    def validate(self):
        _absolute(self.root);require_digest(self.store_contract_digest)
        if not isinstance(self.run_id,str) or not self.run_id:raise StoreError('explicit private run identity required')
        for n in (self.single_artifact_bytes,self.total_write_bytes,self.journal_record_bytes):
            if type(n) is not int or n<=0:raise StoreError('positive explicit byte bounds required')
        if self.journal_record_bytes<2048 or self.total_write_bytes<self.journal_record_bytes:
            raise StoreError('qualified journal/incident capacity required')
        if not isinstance(self.public_mount_roots,tuple):raise StoreError('explicit complete public mount root tuple required')
        for root in self.public_mount_roots:
            _absolute(root)
            if _overlap(self.root,root):raise StoreError('private run root overlaps candidate/public mount')

    @property
    def binding_digest(self):return digest(asdict(self))


def bounded_json(value,limit):
    """Canonical JSON body with preflight allocation bounds and chunk accounting."""
    if type(limit) is not int or limit<=0:raise StoreError('positive encoder bound required')
    # Lower-bound walk rejects huge strings/containers before JSONEncoder can
    # allocate their escaped representation. Ancestor identities detect cycles.
    active=set();minimum=0
    def walk(obj):
        nonlocal minimum
        if isinstance(obj,str):minimum+=len(obj)+2
        elif obj is None or type(obj) in (bool,int,float):minimum+=1
        elif isinstance(obj,(dict,list,tuple)):
            oid=id(obj)
            if oid in active:raise StoreError('cyclic JSON value')
            active.add(oid);minimum+=2+max(0,len(obj)-1)
            if minimum>limit:raise StoreError('JSON body exceeds artifact bound')
            if isinstance(obj,dict):
                for k,v in obj.items():
                    if not isinstance(k,str):raise StoreError('JSON object keys must be strings')
                    walk(k);minimum+=1;walk(v)
            else:
                for v in obj:walk(v)
            active.remove(oid)
        else:raise StoreError('unsupported JSON value type')
        if minimum>limit:raise StoreError('JSON body exceeds artifact bound')
    try:walk(value)
    except RecursionError as exc:raise StoreError('JSON nesting cannot be encoded by selected runtime') from exc
    chunks=[];size=0
    encoder=json.JSONEncoder(sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
    try:
        for chunk in encoder.iterencode(value):
            b=chunk.encode('utf-8');size+=len(b)
            if size>limit:raise StoreError('JSON body exceeds artifact bound')
            chunks.append(b)
    except (ValueError,TypeError,UnicodeError,RecursionError) as exc:raise StoreError('noncanonical JSON body') from exc
    return b''.join(chunks)


def bounded_utf8(text,limit):
    if not isinstance(text,str) or len(text)>limit:raise StoreError('UTF8 text exceeds artifact bound')
    chunks=[];size=0
    for offset in range(0,len(text),4096):
        try:b=text[offset:offset+4096].encode('utf-8')
        except UnicodeError as exc:raise StoreError('invalid UTF8 text') from exc
        size+=len(b)
        if size>limit:raise StoreError('UTF8 text exceeds artifact bound')
        chunks.append(b)
    return b''.join(chunks)


class PrivateRunStore:
    def __init__(self,admission,*,authority,role='reference_fit',domain='authentic'):
        if not isinstance(admission,StoreAdmission):raise StoreError('typed store admission required')
        admission.validate()
        if domain not in ('authentic','invented'):raise StoreError('explicit authority domain required')
        self.a=admission;self.authority=authority;self.role=role;self.domain=domain
        self._auth()
        self.rootfd=None;self.identity=None;self.started=False;self.closed=False;self.failed=False
        self.actual_write_bytes=0;self.planned_body_bytes=0;self.file_sequence=0;self.journal_index=0
        self.head='0'*64;self.artifacts={};self.partial_operations=[];self.incidents=[];self._lock=threading.RLock()

    def _auth(self):
        if not isinstance(self.authority,VerifiedAuthority):raise StoreError('typed verified authority required before effects')
        self.authority.require(role=self.role,domain=self.domain,bindings={
            'run_digest':digest(self.a.run_id),'private_store_admission_digest':self.a.binding_digest,
            'private_store_contract_digest':self.a.store_contract_digest})

    def assert_private_boundary(self,candidate_sources):
        """Owner must call for every future public/candidate mount source."""
        for path in candidate_sources:
            _absolute(path)
            if _overlap(self.a.root,path):raise StoreError('private artifacts/journal cannot be a candidate mount')

    def _check_root(self):
        self._auth()
        if self.rootfd is None or not self.started or self.closed:raise StoreError('store root is not open')
        st=os.fstat(self.rootfd)
        if (st.st_dev,st.st_ino)!=self.identity or not stat.S_ISDIR(st.st_mode) or stat.S_IMODE(st.st_mode)!=0o700 or st.st_uid!=os.getuid():
            raise StoreError('private owned root identity/mode changed')

    def create(self):
        with self._lock:
            self._auth()
            if self.started or self.rootfd is not None:raise StoreError('exclusive root creation is single-use')
            parts=self.a.root.split('/')[1:];parent=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
            created=False
            try:
                for component in parts[:-1]:
                    child=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent)
                    os.close(parent);parent=child
                os.mkdir(parts[-1],mode=0o700,dir_fd=parent);created=True
                self.rootfd=os.open(parts[-1],os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent)
                st=os.fstat(self.rootfd);self.identity=(st.st_dev,st.st_ino);self.started=True
                os.fsync(parent);self._check_root()
                self._append('store_open',{'admission_digest':self.a.binding_digest,'domain':self.domain,
                    'run_digest':digest(self.a.run_id),'candidate_exportable':False})
                return self.status()
            except BaseException as exc:
                self.failed=True
                incident={'operation':'create','root_created':created,'error_type':type(exc).__name__,'error':str(exc),
                    'original_partial_root_retained':created,'clean_open':False}
                self.incidents.append(incident)
                raise StoreError('private store creation failed; original state retained',incident) from exc
            finally:os.close(parent)

    def _ensure_capacity(self,amount):
        if amount<0 or self.actual_write_bytes+amount>self.a.total_write_bytes:
            raise StoreError('exact logical file-body write bound would be exceeded')

    def _atomic(self,name,body):
        """Flat private namespace, single synchronized writer, exclusive new target.

        Same-directory rename gives atomic visibility. Target absence is protected
        by this exclusive new0700 root/single writer, not a hostile same-UID host.
        No os.replace, hardlink publication or adoption of preexisting state.
        """
        self._check_root();self._ensure_capacity(len(body));self.file_sequence+=1
        temporary=f't{self.file_sequence:08d}.part';fd=None
        op={'target':name,'temporary':temporary,'intended_bytes':len(body),'written_bytes':0,
            'intended_sha256':hashlib.sha256(body).hexdigest(),'published':False,'durable':False}
        self.partial_operations.append(op)
        try:
            try:os.stat(name,dir_fd=self.rootfd,follow_symlinks=False)
            except FileNotFoundError:pass
            else:raise StoreError('target exists; overwrite/adoption forbidden')
            fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=self.rootfd)
            st=os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1 or st.st_uid!=os.getuid():raise StoreError('exclusive regular nonhardlinked temporary required')
            view=memoryview(body)
            while op['written_bytes']<len(body):
                n=os.write(fd,view[op['written_bytes']:op['written_bytes']+65536])
                if n<=0:raise StoreError('short/no-progress artifact write')
                self.actual_write_bytes+=n;op['written_bytes']+=n
            os.fsync(fd);st=os.fstat(fd)
            if st.st_nlink!=1 or st.st_size!=len(body):raise StoreError('temporary link/length changed')
            os.close(fd);fd=None
            os.rename(temporary,name,src_dir_fd=self.rootfd,dst_dir_fd=self.rootfd);op['published']=True
            final=os.stat(name,dir_fd=self.rootfd,follow_symlinks=False)
            if not stat.S_ISREG(final.st_mode) or final.st_nlink!=1 or (final.st_dev,final.st_ino)!=(st.st_dev,st.st_ino):
                raise StoreError('atomic publication identity changed')
            os.fsync(self.rootfd);op['durable']=True
            return dict(op)
        except BaseException as exc:
            op['error_type']=type(exc).__name__;op['error']=str(exc)
            raise
        finally:
            if fd is not None:os.close(fd)

    def _event_bytes(self,kind,payload):
        event={'schema':'n073_private_journal_v1','run_digest':digest(self.a.run_id),'domain':self.domain,
            'index':self.journal_index,'previous':self.head,'kind':kind,'payload':payload}
        # Bound before hashing: oversized payloads cannot force an unbounded
        # canonical serialization merely to discover their journal hash.
        core=bounded_json(event,self.a.journal_record_bytes-96)
        event['event_digest']=hashlib.sha256(core).hexdigest()
        return event,bounded_json(event,self.a.journal_record_bytes-1)+b'\n'

    def _append(self,kind,payload):
        event,body=self._event_bytes(kind,payload)
        receipt=self._atomic(f'j{self.journal_index:08d}.json',body)
        self.head=event['event_digest'];self.journal_index+=1
        return {'event':event,'artifact':receipt}

    def _incident(self,operation,exc):
        self.failed=True
        original={'operation':operation,'error_type':type(exc).__name__,'error':str(exc),
            'last_durable_journal_index':self.journal_index-1,'last_durable_head':self.head,
            'actual_write_bytes_before_incident':self.actual_write_bytes,
            'partial_operations':self.partial_operations[-3:],'candidate_exportable':False}
        self.incidents.append(original)
        # Preserve full original error in memory even if the bounded durable
        # sidecar cannot fit, cannot be written, or the filesystem itself failed.
        try:
            body=bounded_json(original,self.a.journal_record_bytes-1)+b'\n'
            self._atomic(f'incident{len(self.incidents):08d}.json',body)
            original['durable_incident_written']=True
        except BaseException as capture:
            original['durable_incident_written']=False;original['incident_capture_error']=str(capture)
        return original

    def _put(self,key,body,media_type):
        with self._lock:
            self._check_root()
            if self.failed:raise StoreError('failed store cannot continue or retry')
            if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,95}',key):raise StoreError('flat safe unique artifact key required')
            if key in self.artifacts:raise StoreError('artifact key already committed; no overwrite')
            if len(body)>self.a.single_artifact_bytes:raise StoreError('single-artifact bound exceeded')
            name='a-'+key+('.json' if media_type=='application/json' else '.txt')
            descriptor={'key':key,'file':name,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),
                        'media_type':media_type,'candidate_exportable':False}
            _,prepare=self._event_bytes('artifact_prepare',descriptor)
            # One bounded final commit OR incident remains reserved after body.
            self._ensure_capacity(len(prepare)+len(body)+self.a.journal_record_bytes)
            self.planned_body_bytes+=len(body)
            try:
                self._append('artifact_prepare',descriptor)
                original=self._atomic(name,body)
                commit=self._append('artifact_commit',descriptor)
                receipt={**descriptor,'domain':self.domain,'publication':original,
                         'commit_digest':commit['event']['event_digest'],'journal_index':commit['event']['index']}
                self.artifacts[key]=receipt
                return receipt
            except BaseException as exc:raise StoreError('artifact transaction failed; original partials retained',self._incident('put:'+key,exc)) from exc

    def put_json(self,key,value):
        self._auth()
        return self._put(key,bounded_json(value,self.a.single_artifact_bytes),'application/json')

    def put_utf8(self,key,text):
        self._auth()
        return self._put(key,bounded_utf8(text,self.a.single_artifact_bytes),'text/plain; charset=utf-8')

    def append_event(self,kind,payload):
        with self._lock:
            self._check_root()
            if self.failed:raise StoreError('failed store cannot append/retry')
            if not isinstance(kind,str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}',kind):raise StoreError('canonical event kind required')
            _,body=self._event_bytes(kind,payload);self._ensure_capacity(len(body)+self.a.journal_record_bytes)
            try:return self._append(kind,payload)
            except BaseException as exc:raise StoreError('journal append failed; original partial retained',self._incident('append:'+kind,exc)) from exc

    def status(self):
        return {'schema':'n073_private_store_status_v1','domain':self.domain,'run_digest':digest(self.a.run_id),
            'admission_digest':self.a.binding_digest,'root':self.a.root,'root_identity':self.identity,
            'journal_events':self.journal_index,'journal_head':self.head,'committed_artifacts':len(self.artifacts),
            'planned_artifact_body_bytes':self.planned_body_bytes,'actual_file_body_write_bytes':self.actual_write_bytes,
            'single_artifact_bound':self.a.single_artifact_bytes,'total_write_bound':self.a.total_write_bytes,
            'failed':self.failed,'closed':self.closed,'candidate_exportable':False}

    def close(self):
        with self._lock:
            self._check_root()
            try:
                if not self.failed:
                    self._append('store_close',{'committed_artifacts':len(self.artifacts),'prior_journal_head':self.head,
                        'actual_file_body_write_bytes_before_close_event':self.actual_write_bytes})
                os.fsync(self.rootfd)
            except BaseException as exc:self._incident('close',exc)
            finally:os.close(self.rootfd);self.rootfd=None;self.closed=True
            result=self.status();result['receipt_digest']=digest(result);return result


def verify_journal_frames(frames,*,run_id,domain,expected_head,expected_events):
    """Pure explicit-byte verifier; never opens/scans a root or recovers partials."""
    require_digest(expected_head)
    if type(expected_events) is not int or expected_events<0 or len(frames)!=expected_events:
        raise StoreError('journal completeness differs from externally bound event count')
    head='0'*64
    for index,body in enumerate(frames):
        if not isinstance(body,bytes) or not body.endswith(b'\n'):raise StoreError('incomplete journal artifact')
        try:event=json.loads(body[:-1].decode('utf-8'),object_pairs_hook=_unique,parse_constant=_invalid_constant)
        except (UnicodeError,ValueError) as exc:raise StoreError('invalid journal JSON') from exc
        expected={'schema','run_digest','domain','index','previous','kind','payload','event_digest'}
        if (not isinstance(event,dict) or set(event)!=expected or event['schema']!='n073_private_journal_v1'
            or type(event['index']) is not int or event['index']!=index or event['previous']!=head
            or event['run_digest']!=digest(run_id) or event['domain']!=domain):raise StoreError('journal chain/identity mismatch')
        if canonical(event)+b'\n'!=body:raise StoreError('noncanonical journal bytes')
        h=digest({k:v for k,v in event.items() if k!='event_digest'})
        if event['event_digest']!=h:raise StoreError('journal hash mismatch')
        head=h
    if head!=expected_head:raise StoreError('journal final head differs from external custody binding')
    return {'events':len(frames),'head':head,'run_digest':digest(run_id),'domain':domain,
            'verification':'explicit bytes only; supplied head must be externally custody-bound'}


def _unique(pairs):
    obj={}
    for k,v in pairs:
        if k in obj:raise StoreError('duplicate journal key')
        obj[k]=v
    return obj


def _invalid_constant(value):raise StoreError('nonfinite journal number')
