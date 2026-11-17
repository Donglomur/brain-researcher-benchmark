"""Finite original-attempt custody before numerical or corpus effects.

An exclusive directory consumes an invocation even if its first file fails.
This is metadata custody, not a scientific store, a retry/adoption API, or proof
of native qualification. No filesystem work occurs at import.
"""
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import json
import math
import os
import re
import stat
import time


class AttemptError(RuntimeError):
    pass


class InvocationFailed(AttemptError):
    def __init__(self, report):
        super().__init__('original invocation failed; inspect bounded attempt evidence')
        self.report = report
        self.public_diagnostic = {
            'schema': 'n073_invocation_failure_pointer_v1',
            'attempt_root': report.get('attempt_root'),
            'stage': report.get('stage'),
            'original_exception_type': report.get('original_exception_type'),
            'failure_record_pin': report.get('failure_record_pin'),
            'failure_capture_errors': report.get('failure_capture_errors', []),
            'attempt_write_counters': {key:report.get('attempt_write_counters',{}).get(key)
                for key in ('reserved_bytes','written_bytes','records_attempted')},
            'claim_consumed': report.get('claim_consumed', False),
            'failure_details_durable': report.get('failure_details_durable', False),
            'scientific_qualification': False,
        }


def _need(ok, text):
    if not ok:
        raise AttemptError(text)


@dataclass(frozen=True)
class AttemptLimits:
    file_bytes: int
    total_write_bytes: int
    max_records: int
    max_json_nodes: int
    workspace_bytes: int
    wall_seconds: int
    failure_write_reserve_bytes: int
    failure_record_reserve: int
    failure_wall_seconds: int

    def __post_init__(self):
        _need(all(type(x) is int and 0 < x <= 2**53-1 for x in asdict(self).values()),
              'finite positive selected attempt capacities')
        _need(self.failure_record_reserve >= 2 and self.max_records > self.failure_record_reserve + 1,
              'separate failure-record reserve')
        _need(self.failure_write_reserve_bytes >= 2*self.file_bytes and
              self.total_write_bytes > self.failure_write_reserve_bytes + self.file_bytes,
              'separate two-file failure write reserve')
        _need(self.workspace_bytes >= 128*self.file_bytes + 8192,
              'bounded encoding/receipt workspace capacity')


def _encode(value, limits):
    # Reject excessive structure/string extents before allocating JSON output.
    stack = [(value, 0)]; nodes = text_chars = 0
    while stack:
        item, depth = stack.pop(); nodes += 1
        _need(depth <= 64 and nodes <= limits.max_json_nodes, 'attempt metadata tree bound')
        if type(item) is dict:
            _need(all(type(k) is str for k in item), 'string metadata keys')
            nodes += len(item)
            text_chars += sum(len(k) for k in item)
            stack.extend((v, depth+1) for v in item.values())
        elif type(item) in (tuple, list):
            stack.extend((v, depth+1) for v in item)
        elif type(item) is str:
            text_chars += len(item)
        elif type(item) is float:
            _need(math.isfinite(item), 'finite attempt number')
        else:
            _need(item is None or type(item) in (bool, int), 'plain bounded metadata only')
        _need(text_chars <= limits.file_bytes and len(stack) <= limits.max_json_nodes,
              'attempt metadata text/workspace bound')
    chunks=[]; size=0
    for chunk in json.JSONEncoder(sort_keys=True, separators=(',', ':'), allow_nan=False).iterencode(value):
        raw=chunk.encode('utf-8');size+=len(raw)
        _need(size+1 <= limits.file_bytes, 'attempt single-file encoding bound')
        chunks.append(raw)
    return b''.join(chunks)+b'\n'


def _pin(name, raw):
    return {'file': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def _root(path):
    path=Path(path)
    _need(path.is_absolute() and str(path) == os.path.normpath(str(path)) and str(path) != '/',
          'canonical selected attempt parent')
    fd=os.open('/', os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:
        for part in path.parts[1:]:
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
            os.close(fd);fd=child
        info=os.fstat(fd)
        _need(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700,
              'owned private0700 attempt parent')
        return fd
    except BaseException:
        os.close(fd);raise


def _error(exc):
    # Private original details are exact within an explicit finite cap. A larger
    # message is reported as a capture limitation, never silently called exact.
    message=str(exc)
    return {'type':type(exc).__name__, 'message':message if len(message)<=4096 else None,
            'message_capture_error':None if len(message)<=4096 else 'original_message_exceeds4096chars'}


class AttemptClaim:
    def __init__(self, parent, invocation_id, identities, limits):
        _need(type(limits) is AttemptLimits, 'selected exact AttemptLimits')
        _need(type(invocation_id) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,128}',invocation_id),
              'bounded original invocation ID')
        self.parent=Path(parent);self.name='attempt-'+invocation_id;self.root=str(self.parent/self.name)
        self.invocation_id=invocation_id;self.identities=dict(identities);self.limits=limits
        self.parentfd=self.fd=None;self.identity=None;self.consumed=False;self.stage='claim'
        self.reserved_bytes=0;self.written_bytes=0;self.operations=[];self.pins=[]
        self.claim_pin=self.preparation_pin=None;self.failure_deadline=None
        self.deadline=time.monotonic()+limits.wall_seconds;self.failed=False;self.closed=False

    @classmethod
    def create(cls, *, parent, invocation_id, identities, limits):
        claim=cls(parent,invocation_id,identities,limits)
        try:
            claim.parentfd=_root(parent)
            # mkdir is the atomic claim. FileExistsError never opens/adopts the
            # old attempt, and no callback/preparation effect has occurred.
            os.mkdir(claim.name,0o700,dir_fd=claim.parentfd)
            claim.consumed=True
            os.fsync(claim.parentfd)
            claim.fd=os.open(claim.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=claim.parentfd)
            st=os.fstat(claim.fd);claim.identity=(st.st_dev,st.st_ino)
            _need(st.st_uid==os.getuid() and stat.S_IMODE(st.st_mode)==0o700,'owned exclusive attempt directory')
            body={'schema':'n073_original_invocation_claim_v1','invocation_id':invocation_id,
                  'identities':dict(identities),'attempt_root':claim.root,
                  'directory_identity':list(claim.identity),'limits':asdict(limits),
                  'scientific_qualification':False,'automatic_retry_or_adoption':False}
            claim.claim_pin=claim._write('claim.json',body)
            return claim
        except BaseException as exc:
            report=claim.fail(exc, snapshot={'claim_creation':True}, cleanup=[])
            claim.close()
            raise InvocationFailed(report) from exc

    def _check(self, failure=False):
        deadline=self.failure_deadline if failure else self.deadline
        _need(deadline is not None and time.monotonic()<=deadline,'attempt metadata wall capacity exhausted')
        _need(self.fd is not None and not self.closed,'live original attempt descriptor')
        now=os.fstat(self.fd);named=os.stat(self.name,dir_fd=self.parentfd,follow_symlinks=False)
        _need((now.st_dev,now.st_ino)==self.identity==(named.st_dev,named.st_ino) and
              stat.S_ISDIR(named.st_mode) and now.st_uid==os.getuid() and
              stat.S_IMODE(now.st_mode)==0o700,'original attempt directory identity changed')

    def _write(self, name, value, *, failure=False):
        self._check(failure);raw=_encode(value,self.limits)
        ceiling=self.limits.total_write_bytes-(0 if failure else self.limits.failure_write_reserve_bytes)
        records=self.limits.max_records-(0 if failure else self.limits.failure_record_reserve)
        _need(self.reserved_bytes+len(raw)<=ceiling and len(self.operations)<records,
              'attempt cumulative capacity; original reservation retained')
        self.reserved_bytes+=len(raw)
        op={'file':name,'reserved_bytes':len(raw),'written_bytes':0,'durable':False}
        self.operations.append(op);fd=None
        try:
            fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,
                       0o600,dir_fd=self.fd)
            st=os.fstat(fd)
            _need(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_uid==os.getuid()
                  and stat.S_IMODE(st.st_mode)==0o600,'owned regular exclusive attempt record')
            while op['written_bytes']<len(raw):
                self._check(failure)
                n=os.write(fd,raw[op['written_bytes']:op['written_bytes']+65536])
                _need(n>0,'attempt record write made no progress')
                op['written_bytes']+=n;self.written_bytes+=n
            os.fsync(fd);after=os.fstat(fd);named=os.stat(name,dir_fd=self.fd,follow_symlinks=False)
            _need((st.st_dev,st.st_ino)==(after.st_dev,after.st_ino)==(named.st_dev,named.st_ino)
                  and after.st_size==len(raw) and after.st_nlink==1,'attempt record identity/extent changed')
            os.fsync(self.fd);op['durable']=True
            pin=_pin(name,raw);self.pins.append(pin);return pin
        except BaseException as exc:
            op['error_type']=type(exc).__name__;raise
        finally:
            if fd is not None:os.close(fd)

    def begin(self, stage, snapshot):
        _need(not self.failed and type(stage) is str and re.fullmatch('[a-z0-9_]{1,64}',stage),
              'finite original stage before effects')
        self.stage=stage
        return self._write('event-%04d.json'%len(self.operations),{
            'schema':'n073_original_stage_v1','stage':stage,'snapshot':snapshot,
            'attempt_write_counters':self.counters(),'scientific_qualification':False})

    def preparation_complete(self, snapshot):
        _need(self.preparation_pin is None and not self.failed,'one preparation boundary')
        self.preparation_pin=self._write('preparation-complete.json',{
            'schema':'n073_original_preparation_complete_v1','invocation_id':self.invocation_id,
            'claim_pin':self.claim_pin,'snapshot':snapshot,'scientific_qualification':False})
        return self.binding()

    def binding(self):
        self._check()
        _need(not self.failed and self.claim_pin is not None and self.preparation_pin is not None,
              'actual original claim and completed preparation required')
        return {'schema':'n073_attempt_binding_v1','root':self.root,'directory_identity':list(self.identity),
                'claim_pin':dict(self.claim_pin),'preparation_pin':dict(self.preparation_pin)}

    def counters(self):
        return {'reserved_bytes':self.reserved_bytes,'written_bytes':self.written_bytes,
                'records_attempted':len(self.operations),'partial_operations':[dict(x) for x in self.operations]}

    def fail(self, original, *, snapshot, cleanup):
        self.failed=True
        if self.failure_deadline is None:self.failure_deadline=time.monotonic()+self.limits.failure_wall_seconds
        errors=[];structured=None
        try:
            structured=getattr(original,'receipt',None)
            detail=_error(original)
            cause=_error(original.__cause__) if original.__cause__ is not None else None
        except BaseException as error:
            errors.append({'operation':'original_detail_capture','exception_type':type(error).__name__})
            detail={'type':type(original).__name__};cause=None
        payload={'schema':'n073_original_invocation_failure_v2','stage':self.stage,'original':detail,
                 'original_cause':cause,'original_structured_receipt':structured,
                 'snapshot':snapshot,'cleanup_outcomes':cleanup,'attempt_write_counters':self.counters(),
                 'claim_consumed':self.consumed,'scientific_qualification':False}
        pin=None
        try:pin=self._write('failure.json',payload,failure=True)
        except BaseException as capture:
            errors.append({'operation':'failure_record_capture','exception_type':type(capture).__name__})
            try:
                self._write('failure-capture-error.json',{
                    'schema':'n073_original_failure_capture_error_v1','stage':self.stage,
                    'original_exception_type':type(original).__name__,'failure_capture_errors':errors,
                    'attempt_write_counters':self.counters(),'claim_consumed':self.consumed,
                    'original_failure_details_preserved':False,'scientific_qualification':False},failure=True)
            except BaseException as terminal:
                errors.append({'operation':'failure_capture_error_record','exception_type':type(terminal).__name__})
        return {'attempt_root':self.root,'stage':self.stage,'original_exception_type':type(original).__name__,
                'failure_record_pin':pin,'failure_capture_errors':errors,'claim_consumed':self.consumed,
                'failure_details_durable':pin is not None and not errors,
                'attempt_write_counters':self.counters(),'scientific_qualification':False}

    def close(self):
        for name in ('fd','parentfd'):
            fd=getattr(self,name)
            if fd is not None:
                os.close(fd);setattr(self,name,None)
        self.closed=True


def verify_attempt_binding(binding, *, parent, invocation_id, identities, limits, ledger):
    """Bounded independent original claim/preparation join, no data/native reads."""
    _need(type(binding) is dict and set(binding)=={'schema','root','directory_identity','claim_pin','preparation_pin'}
          and binding['schema']=='n073_attempt_binding_v1','exact attempt binding')
    expected=str(Path(parent)/('attempt-'+invocation_id))
    _need(binding['root']==expected and type(binding['directory_identity']) is list
          and len(binding['directory_identity'])==2,'selected original attempt namespace')
    deadline=time.monotonic()+limits.wall_seconds
    parentfd=_root(parent);fd=None
    try:
        fd=os.open('attempt-'+invocation_id,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parentfd)
        info=os.fstat(fd)
        _need([info.st_dev,info.st_ino]==binding['directory_identity'] and info.st_uid==os.getuid()
              and stat.S_IMODE(info.st_mode)==0o700,'original attempt root changed')
        for failure_name in ('failure.json','failure-capture-error.json'):
            try:os.stat(failure_name,dir_fd=fd,follow_symlinks=False)
            except FileNotFoundError:pass
            else:raise AttemptError('original attempt contains failure/partial failure evidence')
        values={}
        for role,name in (('claim_pin','claim.json'),('preparation_pin','preparation-complete.json')):
            pin=binding[role]
            _need(type(pin) is dict and set(pin)=={'file','bytes','sha256'} and pin['file']==name
                  and type(pin['bytes']) is int and 0<pin['bytes']<=limits.file_bytes
                  and type(pin['sha256']) is str and re.fullmatch('[a-f0-9]{64}',pin['sha256']),
                  'bounded original attempt pin')
            row=ledger.reserve(expected+'/'+name,pin['bytes']);filefd=None
            try:
                filefd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,dir_fd=fd)
                before=os.fstat(filefd)
                _need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==pin['bytes']
                      and before.st_uid==os.getuid() and stat.S_IMODE(before.st_mode)==0o600,
                      'owned regular original attempt record')
                raw=bytearray()
                while len(raw)<pin['bytes']:
                    _need(time.monotonic()<=deadline,'original attempt verification wall bound')
                    part=os.read(filefd,min(65536,pin['bytes']-len(raw)))
                    _need(part,'short original attempt record');raw.extend(part)
                    row['read_bytes']+=len(part);ledger.actual_bytes+=len(part)
                after=os.fstat(filefd);named=os.stat(name,dir_fd=fd,follow_symlinks=False)
                _need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
                      (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)
                      and (after.st_dev,after.st_ino)==(named.st_dev,named.st_ino)
                      and hashlib.sha256(raw).hexdigest()==pin['sha256'],'changed original attempt record')
                value=json.loads(raw)
                _need(_encode(value,limits)==raw,'canonical original attempt metadata')
                values[role]=value;row['status']='complete'
            except BaseException as exc:
                row['status']='failed';row['error_type']=type(exc).__name__;raise
            finally:
                if filefd is not None:os.close(filefd)
        claim=values['claim_pin'];prep=values['preparation_pin']
        _need(set(claim)=={'schema','invocation_id','identities','attempt_root','directory_identity','limits','scientific_qualification','automatic_retry_or_adoption'},'closed original claim fields')
        _need(set(prep)=={'schema','invocation_id','claim_pin','snapshot','scientific_qualification'} and type(prep['snapshot']) is dict,'closed original preparation fields')
        _need(claim.get('schema')=='n073_original_invocation_claim_v1' and claim.get('invocation_id')==invocation_id
              and claim.get('identities')==identities and claim.get('attempt_root')==expected
              and claim.get('directory_identity')==binding['directory_identity'] and claim.get('limits')==asdict(limits)
              and claim.get('scientific_qualification') is False and claim.get('automatic_retry_or_adoption') is False,
              'original claim identity/selection differs')
        _need(prep.get('schema')=='n073_original_preparation_complete_v1' and prep.get('invocation_id')==invocation_id
              and prep.get('claim_pin')==binding['claim_pin'] and prep.get('scientific_qualification') is False,
              'original preparation does not join original claim')
        named=os.stat('attempt-'+invocation_id,dir_fd=parentfd,follow_symlinks=False)
        _need([named.st_dev,named.st_ino]==binding['directory_identity'],'original attempt namespace replaced')
        return binding
    finally:
        if fd is not None:os.close(fd)
        os.close(parentfd)
