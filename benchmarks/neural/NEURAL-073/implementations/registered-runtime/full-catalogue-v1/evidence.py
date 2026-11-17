"""Bounded consumers of the original private store, never a result-discovery API.

A hash chain is not custody: load_evidence requires the independently authenticated
operator terminal object. Neural/model/capture identities are commitments of that
trusted writer; this consumer never opens those bodies. There is no synthetic
success, partial-scope score or recovery by choosing another invocation.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from collections import Counter
from contextlib import contextmanager
import hashlib
import json
import math
import os
import re
import stat
import time
from .runtime.core.custody import canonical, digest, require_digest, CustodyError
from .runtime.private_store.store import verify_journal_frames


class EvidenceError(CustodyError):
    pass


IDENTITY_KEYS = frozenset(('accepted_parent_closure_digest','code_closure_digest',
    'task_design_digest','deployment_digest','source_freeze_digest','policy_file_digest',
    'invocation_intent_digest','execution_selection_envelope_sha256',
    'runtime_policy_digest','plan_digest','assessment_digest'))
MANIFEST_KEYS = frozenset(('schema','domain','run_id','status','identities','store_close',
    'artifacts','journal','roles','opaque_commitments','diagnostics'))
ROLE_KEYS = frozenset(('run_contract','full_locked_closure','full_study_results',
    'full_score_capability','candidate_contexts','outer_references','reference_oof','provider_usage'))
FINAL_STATUSES = ('complete','complete_with_candidate_failures')
STATUSES = FINAL_STATUSES + ('running_unscored','infrastructure_invalid')
_SAFE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,255}\Z')
_KEY = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,95}\Z')
_SEAL = object()


@dataclass(frozen=True)
class EvidenceLimits:
    max_manifest_bytes: int
    max_file_bytes: int
    max_total_read_bytes: int
    max_journal_events: int
    max_artifacts: int
    max_json_nodes: int
    max_live_bytes: int
    wall_seconds: int

    def __post_init__(self):
        if any(type(v) is not int or v <= 0 for v in asdict(self).values()):
            raise EvidenceError('finite positive explicit evidence bounds required')
        if self.max_manifest_bytes > self.max_file_bytes:
            raise EvidenceError('manifest must fit explicit single-file bound')


class EvidenceMeter:
    """Conservative logical allocation/read bounds; not an RSS measurement."""
    def __init__(self, limits):
        if type(limits) is not EvidenceLimits:
            raise EvidenceError('exact EvidenceLimits required')
        self.limits=limits;self.read_bytes=0;self.resident=0;self.peak=0
        self.deadline=time.monotonic()+limits.wall_seconds

    def check(self):
        if time.monotonic()>self.deadline:
            raise EvidenceError('evidence wall bound exhausted; original attempt invalid')

    def read(self, n):
        self.check()
        if type(n) is not int or n<0 or self.read_bytes+n>self.limits.max_total_read_bytes:
            raise EvidenceError('cumulative evidence read bound exceeded')
        self.read_bytes+=n

    def retain(self, n):
        self.check()
        if type(n) is not int or n<0 or self.resident+n>self.limits.max_live_bytes:
            raise EvidenceError('conservative evidence working-set bound exceeded')
        self.resident+=n;self.peak=max(self.peak,self.resident)

    def release(self,n):
        if type(n) is not int or not 0<=n<=self.resident:
            raise EvidenceError('invalid working-set release')
        self.resident-=n

    @contextmanager
    def workspace(self,n):
        self.retain(n)
        try:yield
        finally:self.release(n)

    def receipt(self):
        self.check()
        return {'source_body_read_bytes':self.read_bytes,'conservative_peak_workspace_bytes':self.peak,
                'limits':asdict(self.limits),'physical_RSS_measured':False}


def _closed(value, keys, name):
    if type(value) is not dict or set(value)!=set(keys):
        raise EvidenceError('closed '+name+' fields required')
    return value


def _nonnegative(v):
    if type(v) is not int or v<0:raise EvidenceError('nonnegative exact integer required')
    return v


def _unique(pairs):
    out={}
    for k,v in pairs:
        if k in out:raise EvidenceError('duplicate JSON key')
        out[k]=v
    return out


def parse_json(raw, *, limits, newline=None):
    """Strict JSON with a conservative caller reservation before decoding."""
    if type(raw) is not bytes or len(raw)>limits.max_file_bytes:
        raise EvidenceError('bounded exact JSON bytes required')
    def invalid(_):raise EvidenceError('nonfinite JSON constant')
    try:value=json.loads(raw.decode('utf-8'),object_pairs_hook=_unique,parse_constant=invalid)
    except (ValueError,UnicodeError,RecursionError) as exc:raise EvidenceError('invalid complete JSON') from exc
    stack=[(value,0)];nodes=0
    while stack:
        x,depth=stack.pop();nodes+=1
        if nodes>limits.max_json_nodes or depth>96:raise EvidenceError('JSON tree bound exceeded')
        if type(x) is dict:stack.extend((v,depth+1) for v in x.values());nodes+=len(x)
        elif type(x) is list:stack.extend((v,depth+1) for v in x)
        elif type(x) is float and not math.isfinite(x):raise EvidenceError('nonfinite JSON number')
        elif x is not None and type(x) not in (str,int,float,bool):raise EvidenceError('non-JSON value')
    if newline is not None and canonical(value)+(b'\n' if newline else b'')!=raw:
        raise EvidenceError('noncanonical JSON file bytes')
    return value


def validate_pin(pin):
    _closed(pin,('file','bytes','sha256'),'file pin')
    if type(pin['file']) is not str or not _SAFE.fullmatch(pin['file']) or pin['file'] in ('.','..'):
        raise EvidenceError('explicit flat safe file name required')
    _nonnegative(pin['bytes']);require_digest(pin['sha256'])
    return pin


def _open_root(root):
    if type(root) is not str or not root.startswith('/') or root=='/' or os.path.normpath(root)!=root:
        raise EvidenceError('canonical nonroot absolute run directory required')
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:
        for part in root.split('/')[1:]:
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
            os.close(fd);fd=child
        st=os.fstat(fd)
        if not stat.S_ISDIR(st.st_mode) or stat.S_IMODE(st.st_mode)!=0o700 or st.st_uid!=os.getuid():
            raise EvidenceError('owned private0700 run root required')
        return fd,(st.st_dev,st.st_ino)
    except BaseException:
        os.close(fd);raise


def _read(fd,pin,meter):
    validate_pin(pin);n=pin['bytes']
    if n>meter.limits.max_file_bytes:raise EvidenceError('single evidence body bound exceeded')
    meter.read(n)
    filefd=os.open(pin['file'],os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,dir_fd=fd)
    try:
        before=os.fstat(filefd)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size!=n
            or before.st_uid!=os.getuid() or stat.S_IMODE(before.st_mode) not in (0o400,0o600)):
            raise EvidenceError('owned private readable regular single-link evidence extent required')
        body=bytearray()
        while len(body)<n:
            meter.check();part=os.read(filefd,min(65536,n-len(body)))
            if not part:raise EvidenceError('short evidence read')
            body.extend(part)
        #The stable post-read fstat detects growth; no uncharged byte outside
        #the selected exact extent is read as an EOF lookahead.
        after=os.fstat(filefd)
        if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(
            after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):
            raise EvidenceError('evidence changed during read')
        if hashlib.sha256(body).hexdigest()!=pin['sha256']:raise EvidenceError('evidence byte digest mismatch')
        return bytes(body)
    finally:os.close(filefd)


def validate_manifest_shape(m,limits):
    _closed(m,MANIFEST_KEYS,'private run manifest')
    if m['schema']!='n073_private_run_manifest_v2' or m['domain']!='authentic':
        raise EvidenceError('authentic private-run manifest required')
    if type(m['run_id']) is not str or not m['run_id'] or m['status'] not in STATUSES:
        raise EvidenceError('explicit original run identity/status required')
    _closed(m['identities'],IDENTITY_KEYS,'run identities')
    for value in m['identities'].values():require_digest(value)
    if type(m['artifacts']) is not dict or len(m['artifacts'])>limits.max_artifacts:
        raise EvidenceError('complete bounded committed artifact index required')
    if type(m['journal']) is not list or len(m['journal'])>limits.max_journal_events:
        raise EvidenceError('complete bounded ordered journal index required')
    names=set()
    for index,pin in enumerate(m['journal']):
        validate_pin(pin)
        if pin['file']!=f'j{index:08d}.json':raise EvidenceError('exact original journal sequence required')
        names.add(pin['file'])
    for key,row in m['artifacts'].items():
        _closed(row,('key','file','bytes','sha256','media_type','candidate_exportable','domain',
                     'publication','commit_digest','journal_index'),'artifact receipt')
        if type(key) is not str or not _KEY.fullmatch(key) or row['key']!=key:
            raise EvidenceError('canonical unique artifact key required')
        suffix={ 'application/json':'.json','text/plain; charset=utf-8':'.txt' }.get(row['media_type'])
        # The unchanged private store uses text/plain (without charset).
        if row['media_type']=='text/plain':suffix='.txt'
        if suffix is None or row['file']!='a-'+key+suffix or row['file'] in names:
            raise EvidenceError('unique actual store artifact path required')
        names.add(row['file']);validate_pin({k:row[k] for k in ('file','bytes','sha256')})
        if row['domain']!='authentic' or row['candidate_exportable'] is not False:
            raise EvidenceError('private authentic artifact required')
        require_digest(row['commit_digest']);_nonnegative(row['journal_index'])
        pub=row['publication']
        _closed(pub,('target','temporary','intended_bytes','written_bytes','intended_sha256','published','durable'),'publication')
        if (pub['target']!=row['file'] or pub['intended_bytes']!=row['bytes'] or pub['written_bytes']!=row['bytes']
            or pub['intended_sha256']!=row['sha256'] or pub['published'] is not True or pub['durable'] is not True
            or type(pub['temporary']) is not str or not re.fullmatch(r't\d{8}\.part',pub['temporary'])):
            raise EvidenceError('artifact lacks exact successful durable original publication')
    _closed(m['roles'],ROLE_KEYS,'artifact roles')
    for key in ('run_contract','full_locked_closure','full_study_results','full_score_capability'):
        if m['roles'][key] not in m['artifacts']:raise EvidenceError('missing required artifact role')
    for role,count in (('candidate_contexts',234),('outer_references',455),('provider_usage',234)):
        rows=m['roles'][role]
        if type(rows) is not dict or len(rows)!=count or any(v not in m['artifacts'] for v in rows.values()) or len(set(rows.values()))!=count:
            raise EvidenceError('exact complete '+role+' artifact role set required')
    keys=m['roles']['reference_oof']
    if type(keys) is not list or len(keys)!=55068 or len(set(keys))!=55068 or any(k not in m['artifacts'] for k in keys):
        raise EvidenceError('all55068 original OOF artifacts required')
    used=[m['roles'][k] for k in ('run_contract','full_locked_closure','full_study_results','full_score_capability')]
    used+=list(m['roles']['candidate_contexts'].values())+list(m['roles']['outer_references'].values())+list(m['roles']['provider_usage'].values())+keys
    if len(used)!=len(set(used)):raise EvidenceError('scientific artifact roles cannot alias')
    _closed(m['diagnostics'],('incidents','partial_operations','cleanup_outcomes'),'original diagnostics')
    if any(type(m['diagnostics'][k]) is not list for k in m['diagnostics']):
        raise EvidenceError('complete original diagnostics lists required')
    if type(m['opaque_commitments']) is not list or not m['opaque_commitments']:
        raise EvidenceError('explicit complete source/native/model/capture commitments required')
    categories=set();tokens=set()
    for row in m['opaque_commitments']:
        _closed(row,('kind','identity','descriptor_digest','body_read_by_observer'),'opaque commitment')
        if row['kind'] not in ('source','native','model','capture','input') or row['body_read_by_observer'] is not False:
            raise EvidenceError('identity-only opaque commitment required')
        require_digest(row['identity']);require_digest(row['descriptor_digest'])
        token=(row['kind'],row['identity'])
        if token in tokens:raise EvidenceError('duplicate opaque commitment')
        tokens.add(token);categories.add(row['kind'])
    for outcome in m['diagnostics']['cleanup_outcomes']:
        _closed(outcome,('operation','status','original'),'cleanup outcome')
        if type(outcome['operation']) is not str or not outcome['operation'] or outcome['status']!='complete' or type(outcome['original']) is not dict:
            raise EvidenceError('original cleanup failure blocks qualification')
    if categories!={'source','native','model','capture','input'}:
        raise EvidenceError('all opaque identity classes required; no body qualification inferred')
    return m


class EvidenceBundle:
    __slots__=('manifest','manifest_pin','terminal_claims','meter','_fd','root_identity',
               'reference_jobs','reference_events_digest','context_events','tool_events','journal_counts','_seal')
    def __init__(self,seal,**values):
        if seal is not _SEAL:raise EvidenceError('use authenticated load_evidence')
        self._seal=seal
        for key,value in values.items():setattr(self,key,value)
    def require(self):
        if self._seal is not _SEAL or self._fd is None:raise EvidenceError('live authenticated evidence bundle required')
        self.meter.check();return self
    def close(self):
        if self._fd is not None:os.close(self._fd);self._fd=None
    def __enter__(self):return self.require()
    def __exit__(self,*_):self.close()
    @contextmanager
    def artifact(self,key,*,text=False):
        self.require()
        if key not in self.manifest['artifacts']:raise EvidenceError('unlisted artifact read forbidden')
        row=self.manifest['artifacts'][key]
        if (text and row['media_type'] not in ('text/plain','text/plain; charset=utf-8')) or (
            not text and row['media_type']!='application/json'):
            raise EvidenceError('artifact media does not match consumer')
        #64x bytes+4KiB bounds CPython JSON objects, decoder, canonical comparison,
        #copies and node stack conservatively for this finite nesting profile.
        with self.meter.workspace(64*row['bytes']+4096):
            raw=_read(self._fd,{k:row[k] for k in ('file','bytes','sha256')},self.meter)
            if text:yield raw
            else:yield parse_json(raw,limits=self.meter.limits,newline=False)


def _context_of(kind,payload):
    if kind in ('candidate_process_original','guard_original_close'):
        return payload.get('original_receipt',{}).get('context_id')
    if kind=='candidate_model_original':
        return payload.get('inference_record',{}).get('generation_inference',{}).get('context_id')
    if kind=='f_actual_snapshot':
        return payload.get('binding',{}).get('context_id')
    if kind=='broker_original_close':
        return payload.get('context_id') or payload.get('claims',{}).get('context_id')
    return payload.get('context') or payload.get('context_id')


def validate_tool_preparation(p):
    """Pure receipt identities only; genuine native custody is a separate gate."""
    _closed(p,('outer_person','condition','tool_files_digest','materialization','native_seal'),'original public tools preparation')
    from .runtime.core.plan import PEOPLE,CONDITIONS
    key=(p['outer_person'],p['condition'])
    if key not in {(person,condition) for person in PEOPLE for condition in CONDITIONS}:
        raise EvidenceError('duplicate or unknown original outer/condition tool preparation')
    require_digest(p['tool_files_digest'])
    material=p['materialization']
    _closed(material,('files_digest','counters','backing_mount_qualified','source_of_models'),'original tool materialization')
    if (material['files_digest']!=p['tool_files_digest'] or material['backing_mount_qualified'] is not False
        or material['source_of_models']!='selected concrete fitted states'):
        raise EvidenceError('original fitted-tool materialization identity differs')
    sealed=p['native_seal'];_closed(sealed,('evidence','evidence_digest','mounts'),'actual native tool seal metadata')
    if (sealed['evidence_digest']!=digest(sealed['evidence']) or sealed['evidence'].get('schema')!='n073-native-private-seal-v1'
        or sealed['evidence'].get('state')!='sealed' or type(sealed['mounts']) is not list or len(sealed['mounts'])!=1):
        raise EvidenceError('actual completed native tool seal metadata required')
    mount=sealed['mounts'][0]
    _closed(mount,('role','source','destination','members','manifest_digest','export_evidence_digest'),'original sealed tool mount')
    if (mount['role']!='reference_tools' or mount['destination']!='/tools'
        or mount['manifest_digest']!=digest(mount['members']) or mount['manifest_digest']!=p['tool_files_digest']
        or mount['export_evidence_digest']!=sealed['evidence_digest']):
        raise EvidenceError('original full reference-tool mount differs')
    return key


class _JournalFrames:
    def __init__(self,bundle):
        self.b=bundle;self.prepared={};self.committed={};self.open_count=0;self.close_count=0
        self.jobs={};self.reference_hash=hashlib.sha256();self.reference_hash.update(b'[');self.reference_n=0
        self.contexts={k:[] for k in bundle.manifest['roles']['candidate_contexts']};self.counts=Counter();self.tools={}
    def __len__(self):return len(self.b.manifest['journal'])
    def __iter__(self):
        for pin in self.b.manifest['journal']:
            with self.b.meter.workspace(64*pin['bytes']+4096):
                raw=_read(self.b._fd,pin,self.b.meter)
                event=parse_json(raw,limits=self.b.meter.limits,newline=True)
                self.consume(event,pin)
                yield raw
        self.reference_hash.update(b']')
    def consume(self,e,pin):
        kind=e['kind'];p=e['payload'];self.counts[kind]+=1
        if type(p) is not dict:raise EvidenceError('journal payload object required')
        if kind=='artifact_prepare':
            k=p.get('key')
            if k in self.prepared or k in self.committed:raise EvidenceError('artifact was retried or prepared twice')
            self.prepared[k]=p
        elif kind=='artifact_commit':
            k=p.get('key')
            if k not in self.prepared or canonical(p)!=canonical(self.prepared.pop(k)) or k in self.committed:
                raise EvidenceError('artifact prepare/commit mismatch')
            row=self.b.manifest['artifacts'].get(k)
            if row is None or {n:row[n] for n in ('key','file','bytes','sha256','media_type','candidate_exportable')}!=p:
                raise EvidenceError('journal artifact absent from or differs from complete index')
            if row['journal_index']!=e['index'] or row['commit_digest']!=e['event_digest']:
                raise EvidenceError('artifact commit identity mismatch')
            self.committed[k]=e['event_digest']
        elif kind=='store_open':
            self.open_count+=1
            if e['index']!=0 or p.get('admission_digest')!=self.b.manifest['store_close'].get('admission_digest'):
                raise EvidenceError('original store admission/open mismatch')
        elif kind=='store_close':
            self.close_count+=1
            if (e['index']!=len(self)-1 or p.get('committed_artifacts')!=len(self.committed)
                or p.get('prior_journal_head')!=e['previous']):raise EvidenceError('final store close mismatch')
            if p.get('actual_file_body_write_bytes_before_close_event')+pin['bytes']!=self.b.manifest['store_close']['actual_file_body_write_bytes']:
                raise EvidenceError('actual store write accounting differs at close')
        elif kind=='public_tools_prepared':
            key=validate_tool_preparation(p)
            if key in self.tools:raise EvidenceError('duplicate original outer/condition tool preparation')
            self.b.meter.retain(64*pin['bytes']+4096);self.tools[key]=e
        elif kind in ('reference_reserved','reference_completed'):
            k=p.get('key');require_digest(k)
            if kind=='reference_reserved':
                if k in self.jobs or p.get('status')!='reserved':raise EvidenceError('reference attempt repeated/unreserved')
                self.b.meter.retain(64*pin['bytes']+4096);self.jobs[k]=p
            else:
                old=self.jobs.get(k)
                if old is None or old.get('status')!='reserved' or p.get('status')!='complete' or p.get('parents')!=old.get('parents'):
                    raise EvidenceError('reference completion differs from original reservation')
                require_digest(p.get('result_digest'))
                self.b.meter.retain(64*pin['bytes']+4096);self.jobs[k]=p
                if self.reference_n:self.reference_hash.update(b',')
                self.reference_hash.update(canonical(p));self.reference_n+=1
        elif kind in ('reference_failed','outer_failed','study_original_failure','candidate_infrastructure_incident',
                      'context_invalid_originals','store_incident'):
            raise EvidenceError('original infrastructure/reference/store incident blocks qualification')
        elif kind in ('candidate_process_original','guard_original_close','broker_original_close',
                      'candidate_failure','candidate_model_original','f_actual_snapshot','i_prequery_barrier'):
            c=_context_of(kind,p)
            if c not in self.contexts:
                # Model/snapshot payloads are joined by their embedded original
                #context fields; unknown or omitted identity cannot be guessed.
                raise EvidenceError('original context event lacks exact registered context identity: '+kind)
            self.b.meter.retain(64*pin['bytes']+4096);self.contexts[c].append(e)


def load_evidence(run_root,manifest_pin,*,terminal,limits):
    from .authority import VerifiedTerminal
    if type(terminal) is not VerifiedTerminal:raise EvidenceError('independently verified terminal custody required')
    validate_pin(manifest_pin);meter=EvidenceMeter(limits)
    if manifest_pin['bytes']>limits.max_manifest_bytes:raise EvidenceError('manifest bound exceeded')
    #Do not open even the directory before authentic terminal admission.
    claims=terminal.claims
    if claims.get('domain')!='authentic' or claims.get('manifest_pin')!=manifest_pin:
        raise EvidenceError('production evidence requires independently bound exact manifest pin')
    fd,identity=_open_root(run_root)
    try:
        meter.retain(64*manifest_pin['bytes']+4096)
        raw=_read(fd,manifest_pin,meter);m=parse_json(raw,limits=limits,newline=True)
        validate_manifest_shape(m,limits)
        claims=terminal.require(manifest_pin=manifest_pin,run_id=m['run_id'],identities=m['identities'])
        if (m['status'] not in FINAL_STATUSES or claims.get('status')!=m['status']
            or claims.get('artifact_index_digest')!=digest(m['artifacts'])):
            raise EvidenceError('terminal status/artifact index not fully closed')
        close=m['store_close'];receipt=close.get('receipt_digest')
        if (receipt!=digest({k:v for k,v in close.items() if k!='receipt_digest'})
            or claims.get('close_receipt_digest')!=receipt or close.get('schema')!='n073_private_store_status_v1'
            or close.get('domain')!='authentic' or close.get('run_digest')!=digest(m['run_id'])
            or close.get('root')!=run_root or close.get('root_identity')!=list(identity)
            or close.get('failed') is not False or close.get('closed') is not True
            or close.get('candidate_exportable') is not False
            or close.get('committed_artifacts')!=len(m['artifacts'])
            or close.get('journal_events')!=len(m['journal'])
            or claims.get('journal_events')!=len(m['journal'])
            or claims.get('journal_head')!=close.get('journal_head')):
            raise EvidenceError('original successful store-close identity/accounting required')
        if m['diagnostics']['incidents']:raise EvidenceError('original store incidents block qualification')
        for op in m['diagnostics']['partial_operations']:
            if (type(op) is not dict or op.get('published') is not True or op.get('durable') is not True
                or op.get('written_bytes')!=op.get('intended_bytes') or 'error' in op or 'error_type' in op):
                raise EvidenceError('original partial/failed write blocks qualification')
        extents={p['file']:{k:p[k] for k in ('file','bytes','sha256')} for p in m['journal']}
        extents.update({p['file']:{k:p[k] for k in ('file','bytes','sha256')} for p in m['artifacts'].values()})
        operations=m['diagnostics']['partial_operations'];targets=[o.get('target') for o in operations]
        if len(targets)!=len(extents) or set(targets)!=set(extents) or len({o.get('temporary') for o in operations})!=len(operations):
            raise EvidenceError('full original publication operation list required')
        for op in operations:
            pin=extents[op['target']]
            if op['intended_bytes']!=pin['bytes'] or op['intended_sha256']!=pin['sha256']:
                raise EvidenceError('original operation does not match committed file extent')
        bundle=EvidenceBundle(_SEAL,manifest=m,manifest_pin=dict(manifest_pin),terminal_claims=claims,
            meter=meter,_fd=fd,root_identity=identity,reference_jobs={},reference_events_digest=None,
            context_events={},tool_events={},journal_counts={})
        frames=_JournalFrames(bundle)
        verify_journal_frames(frames,run_id=m['run_id'],domain='authentic',
            expected_head=claims['journal_head'],expected_events=claims['journal_events'])
        if frames.open_count!=1 or frames.close_count!=1 or frames.prepared or set(frames.committed)!=set(m['artifacts']):
            raise EvidenceError('complete exact successful journal/artifact join required')
        actual=sum(x['bytes'] for x in m['journal'])+sum(x['bytes'] for x in m['artifacts'].values())
        if (actual!=close['actual_file_body_write_bytes'] or sum(x['bytes'] for x in m['artifacts'].values())!=close['planned_artifact_body_bytes']):
            raise EvidenceError('store byte totals differ from original publications')
        bundle.reference_jobs=frames.jobs;bundle.reference_events_digest=frames.reference_hash.hexdigest()
        from .runtime.core.plan import PEOPLE,CONDITIONS
        if set(frames.tools)!={(p,c) for p in PEOPLE for c in CONDITIONS} or len(frames.tools)!=39:
            raise EvidenceError('all39 unique original outer-person/condition tool preparations required')
        bundle.context_events=frames.contexts;bundle.tool_events=frames.tools;bundle.journal_counts=dict(frames.counts)
        return bundle
    except BaseException:
        os.close(fd);raise
