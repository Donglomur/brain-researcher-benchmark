"""Portable source-only stager for the final authenticated 131-member manifest.

No imports from an oracle, grader, reference bank or authoring helper.
"""
from __future__ import annotations
import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import threading
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

MANIFEST = Path('/app/source_manifest.json')
MANIFEST_SHA = '70000c5c93c2c43f1e7968feb38aaebb4e7622a5f6d2ec1167191337614ef950'
DS_COMMIT = '81c3294a906d03d41952a06df94c83746c2d7509'
TF_COMMIT = '15d7c02160f79f5218d2545b4febebeecc11531d'
IDS = tuple(range(2,10))+tuple(range(11,23))
TOTAL, SUPPLEMENT_TOTAL = 2197402958, 1782874
LIMITS = {'metadata': (63, SUPPLEMENT_TOTAL, 300), 'originals': (131, TOTAL, 1800)}


class SourceError(ValueError): pass


def need(value, code):
    if not value: raise SourceError(code)


def sha(raw): return hashlib.sha256(raw).hexdigest()


def strict_json(raw):
    def pairs(items):
        d={}
        for k,v in items: need(k not in d,'duplicate_json_key');d[k]=v
        return d
    def bad(_): raise SourceError('nonfinite_json')
    obj=json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)
    def check(x):
        if isinstance(x,float): need(math.isfinite(x),'nonfinite_json')
        elif isinstance(x,list):
            for v in x:check(v)
        elif isinstance(x,dict):
            for v in x.values():check(v)
    check(obj);return obj


def relative(path):
    need(isinstance(path,str) and path and '\\' not in path and '\0' not in path
         and not path.startswith('/') and all(x not in ('','.','..') for x in path.split('/')), 'relative_path')
    return path


def safe_path(path, *, fresh=False, directory=False):
    text=os.fspath(path)
    need(text.startswith('/') and '\0' not in text and all(x not in ('.','..') for x in text.split('/')), 'absolute_lexical_path')
    p=Path(text)
    for q in (*reversed(p.parents),p):
        if os.path.lexists(q):
            mode=q.lstat().st_mode;need(not stat.S_ISLNK(mode),'symlink_path')
            if q!=p:need(stat.S_ISDIR(mode),'non_directory_ancestor')
        elif q!=p:raise SourceError('missing_parent')
    if fresh:need(not os.path.lexists(p),'destination_exists')
    else:need(p.is_dir() if directory else p.is_file(),'wrong_file_kind')
    return p


def write_bytes(path,raw):
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as f:f.write(raw)


def write_json(path,value):write_bytes(path,(json.dumps(value,indent=2,allow_nan=False)+'\n').encode())


def expected_url(row):
    path=relative(row['path']);atlas=path.startswith('atlas/');source=path[6:] if atlas else path
    commit=TF_COMMIT if atlas else DS_COMMIT
    need(row['source_commit']==commit,'source_commit')
    if row['identity_kind']=='git_blob_content':
        repo='templateflow/tpl-MNI152NLin2009cAsym' if atlas else 'OpenNeuroDatasets/ds002790'
        return f'https://raw.githubusercontent.com/{repo}/{commit}/{source}'
    need(row['identity_kind']=='published_annex_payload_md5','identity_kind')
    return ('https://templateflow.s3.amazonaws.com/tpl-MNI152NLin2009cAsym/'+source if atlas
            else 'https://s3.amazonaws.com/openneuro.org/ds002790/'+source)


def validate_manifest(obj):
    rows=obj['files'];need(isinstance(rows,list) and len(rows)==131,'closed131')
    need(obj['dataset_commit']==DS_COMMIT and obj['templateflow_commit']==TF_COMMIT,'manifest_commits')
    need(obj['fixed_numeric_ids']==list(IDS) and obj['dataset_release']=='2.0.0','fixed_cohort_release')
    seen=set();roles={};supplement=[]
    for row in rows:
        path=relative(row['path']);need(path not in seen,'duplicate_member');seen.add(path)
        need(type(row['size_bytes']) is int and 0<row['size_bytes']<=TOTAL,'member_size')
        need(type(row['metadata_supplement']) is bool,'supplement_boolean')
        need(row['url']==expected_url(row),'exact_source_url')
        p=urlsplit(row['url']);need(p.scheme=='https' and not p.query and not p.fragment and not p.username and p.port is None,'url_components')
        need(re.fullmatch('[0-9a-f]{40}',row['source_git_blob_sha1'] or ''),'source_git_identity')
        if row['identity_kind']=='git_blob_content':
            need(row['source_git_mode'] in ('100644','100755') and row['content_git_blob_sha1']==row['source_git_blob_sha1'] and row['md5'] is None,'git_content_pin')
        else:
            need(row['source_git_mode']=='120000' and row['content_git_blob_sha1'] is None
                 and re.fullmatch('[0-9a-f]{32}',row['md5'] or ''),'annex_payload_pin')
        need(row['sha256'] is None or re.fullmatch('[0-9a-f]{64}',row['sha256']),'sha256_pin')
        person=row['participant_id'];number=row['numeric_id']
        need((person is None and number is None) or (type(number) is int and number in IDS and person==f'sub-{number:04d}'),'literal_participant')
        key=(person,row['role']);need(key not in roles,'duplicate_role_identity');roles[key]=path
        if row['metadata_supplement']:
            need(row['role'] in ('raw_bold_json','preproc_bold_json','confounds_json','readme','participants_schema','task_bold_json','task_events_json') and row['identity_kind']=='git_blob_content','metadata_only_member')
            supplement.append(row)
    required={(f'sub-{n:04d}',r) for n in IDS for r in ('bold','events','confounds','raw_bold_json','preproc_bold_json','confounds_json')}
    required|={(None,r) for r in ('participants','participants_schema','dataset_description','derivative_description','readme','task_bold_json','task_events_json','atlas_image','atlas_labels','atlas_description','atlas_license')}
    need(set(roles)==required,'exact_role_inventory')
    need(sum(r['size_bytes'] for r in rows)==TOTAL and obj['total_bytes']==TOTAL,'total_bytes')
    need(len(supplement)==63 and sum(r['size_bytes'] for r in supplement)==SUPPLEMENT_TOTAL,'supplement_inventory')
    return obj


def read_manifest(manifest_path=MANIFEST):
    need(re.fullmatch('[0-9a-f]{64}', MANIFEST_SHA), 'final_manifest_not_frozen')
    p=safe_path(manifest_path);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        before=os.fstat(f.fileno());need(stat.S_ISREG(before.st_mode) and 0<before.st_size<256*1024,'manifest_size')
        raw=f.read(256*1024+1)
        need(len(raw)==before.st_size and identity(before)==identity(os.fstat(f.fileno())),'manifest_changed')
    need(identity(before)==identity(p.lstat()),'manifest_replaced')
    need(sha(raw)==MANIFEST_SHA,'manifest_sha256')
    obj=validate_manifest(strict_json(raw))
    need(all(isinstance(r['sha256'],str) and re.fullmatch('[0-9a-f]{64}',r['sha256']) for r in obj['files']), 'all131_measured_sha_required')
    return obj,raw


class NoRedirect(HTTPRedirectHandler):
    def reject(self,req,fp,code,msg,headers):fp.close();raise SourceError('redirect_refused_'+str(code))
    http_error_301=http_error_302=http_error_303=http_error_307=http_error_308=reject


class State:
    def __init__(self,rows,phase,clock=time.monotonic):
        self.rows={r['path']:r for r in rows};self.phase=phase;self.clock=clock;self.start=clock()
        self.max_requests,self.expected_bytes,self.seconds=LIMITS[phase]
        self.cap=self.expected_bytes+self.max_requests # one EOF sentinel per exact member
        self.lock=threading.Lock();self.abort=threading.Event();self.started=set();self.received=0;self.reserved=0
    def check(self):
        need(not self.abort.is_set(),'capture_cancelled')
        need(self.clock()-self.start<self.seconds,'capture_deadline')
    def begin(self,row):
        with self.lock:
            self.check();need(row==self.rows.get(row['path']),'unregistered_member')
            need(row['path'] not in self.started and len(self.started)<self.max_requests,'duplicate_or_excess_start')
            self.started.add(row['path'])
    def reserve(self,n):
        with self.lock:
            self.check();need(self.received+self.reserved+n<=self.cap,'aggregate_byte_cap');self.reserved+=n
    def complete_read(self,reserved,actual):
        with self.lock:
            self.reserved-=reserved;need(0<=actual<=reserved,'read_bound');self.received+=actual


def download_one(row,root,receipts,state,opener=None):
    state.begin(row);path=row['path'];target=root/path;target.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
    print(json.dumps(dict(source_start=path,size_bytes=row['size_bytes'])),flush=True)
    partial=target.with_name(target.name+'.partial');index=list(state.rows).index(path)
    report=dict(path=path,role=row['role'],url=row['url'],status='started',bytes_received=0,
                identity_kind=row['identity_kind'],attempts=1,redirects=0)
    digests={'sha256':hashlib.sha256(),'md5':hashlib.md5(),
             'git_blob_sha1':hashlib.sha1(b'blob '+str(row['size_bytes']).encode()+b'\0')}
    try:
        need(row['url']==expected_url(row),'exact_source_url')
        with os.fdopen(os.open(partial,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as f:
            client=opener or build_opener(ProxyHandler({}),NoRedirect())
            request=Request(row['url'],headers={'User-Agent':'EMOMATCH-fixed131-source-capture','Accept-Encoding':'identity'})
            with client.open(request,timeout=min(30,state.seconds-(state.clock()-state.start))) as response:
                report['http_status']=response.status
                need(response.status==200 and response.geturl()==row['url'],'http_status_or_endpoint')
                headers=response.headers
                report['headers']={k:headers[k] for k in ('Content-Length','Content-Type','ETag','Last-Modified','x-amz-version-id') if k in headers}
                lengths=headers.get_all('Content-Length',[])
                need(len(lengths)==1 and re.fullmatch('[0-9]{1,12}',lengths[0]),'strict_content_length')
                need(int(lengths[0])==row['size_bytes'],'published_size_header_mismatch')
                need(headers.get('Content-Encoding','identity').lower() in ('','identity'),'content_encoding')
                ctype=headers.get('Content-Type','').split(';')[0].lower()
                need(ctype in ('text/plain','application/json','application/octet-stream','binary/octet-stream','application/gzip','application/x-gzip'),'content_type')
                read=getattr(response,'read1',response.read);remaining=row['size_bytes']
                while True:
                    amount=min(1024*1024,remaining) if remaining else 1
                    state.reserve(amount)
                    try:chunk=read(amount)
                    except BaseException:state.complete_read(amount,0);raise
                    need(isinstance(chunk,bytes),'body_type');state.complete_read(amount,len(chunk))
                    report['bytes_received']+=len(chunk)
                    need(len(chunk)<=remaining,'oversized_original')
                    if not chunk:need(remaining==0,'truncated_original');break
                    f.write(chunk)
                    for digest in digests.values():digest.update(chunk)
                    remaining-=len(chunk)
            f.flush();os.fsync(f.fileno())
        observed={k:v.hexdigest() for k,v in digests.items()}
        if row['md5'] is not None:need(observed['md5']==row['md5'],'published_md5_mismatch')
        if row['content_git_blob_sha1'] is not None:need(observed['git_blob_sha1']==row['content_git_blob_sha1'],'published_git_blob_mismatch')
        if row['sha256'] is not None:need(observed['sha256']==row['sha256'],'captured_sha256_mismatch')
        # Atomic no-overwrite publication inside this newly owned attempt only.
        os.link(partial,target,follow_symlinks=False);partial.unlink();target.chmod(0o444)
        report.update(status='verified',size_bytes=row['size_bytes'],**observed)
        print(json.dumps(dict(source_verified=path,size_bytes=row['size_bytes'])),flush=True)
        return report
    except BaseException as error:
        state.abort.set()
        if isinstance(error,HTTPError):report['http_status']=error.code;error.close()
        report.update(status='failed_preserved',error_type=type(error).__name__,
            error_code=str(error) if isinstance(error,SourceError) else 'transport_or_io_failure')
        print(json.dumps(dict(source_failed=path,http_status=report.get('http_status'),error_code=report['error_code'])),flush=True)
        raise
    finally:write_json(receipts/f'{index:03d}.json',report)


def identity(info):
    return info.st_dev,info.st_ino,info.st_mode,info.st_size,info.st_mtime_ns,info.st_ctime_ns


def inventory(root,rows):
    root=safe_path(root,directory=True);expected={r['path'] for r in rows};directories=set()
    for name in expected:
        parent=Path(name).parent
        while str(parent)!='.':directories.add(parent.as_posix());parent=parent.parent
    files=set();found_dirs=set()
    def visit(directory):
        with os.scandir(directory) as entries:
            for e in entries:
                mode=e.stat(follow_symlinks=False).st_mode;rel=Path(e.path).relative_to(root).as_posix()
                need(not stat.S_ISLNK(mode),'source_symlink')
                if stat.S_ISDIR(mode):
                    need(rel in directories,'unexpected_source_directory');found_dirs.add(rel);visit(e.path)
                else:need(stat.S_ISREG(mode),'nonregular_source_member');files.add(rel)
    visit(root);need(files==expected and found_dirs==directories,'closed131_inventory')
    return root


def authenticate_file(path,row,*,output=None,previous_identity=None):
    path=safe_path(path);before=path.lstat()
    need(before.st_size==row['size_bytes'],'source_size')
    if previous_identity is not None:need(identity(before)==previous_identity,'source_changed_after_precheck')
    hashes={'sha256':hashlib.sha256(),'md5':hashlib.md5(),
            'git_blob_sha1':hashlib.sha1(b'blob '+str(row['size_bytes']).encode()+b'\0')}
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        need(identity(os.fstat(f.fileno()))==identity(before),'source_replaced_before_read');remaining=row['size_bytes']
        while remaining:
            chunk=f.read(min(1024*1024,remaining));need(chunk,'source_truncated');remaining-=len(chunk)
            for h in hashes.values():h.update(chunk)
            if output is not None:output.write(chunk)
        need(not f.read(1),'source_oversize')
        need(identity(os.fstat(f.fileno()))==identity(before),'source_changed_during_read')
    need(identity(path.lstat())==identity(before),'source_replaced_after_read')
    digests={k:h.hexdigest() for k,h in hashes.items()}
    need(digests['sha256']==row['sha256'],'source_sha256')
    if row['md5'] is not None:need(digests['md5']==row['md5'],'source_md5')
    if row['content_git_blob_sha1'] is not None:need(digests['git_blob_sha1']==row['content_git_blob_sha1'],'source_git_blob')
    return identity(before)


def authenticate_all(root,rows):
    root=inventory(root,rows)
    identities={r['path']:authenticate_file(root/r['path'],r) for r in rows}
    inventory(root,rows);return identities


def verify_staged(data_dir,manifest_path=MANIFEST):
    manifest,_=read_manifest(manifest_path);authenticate_all(data_dir,manifest['files']);return manifest


def disjoint(*paths):
    concrete=[Path(p).resolve(strict=False) for p in paths if p is not None]
    for i,a in enumerate(concrete):
        for b in concrete[i+1:]:need(a!=b and a not in b.parents and b not in a.parents,'overlapping_paths')


def copy_all(source,dest,rows,identities):
    for row in rows:
        target=dest/row['path'];target.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
        partial=target.with_name(target.name+'.partial')
        with os.fdopen(os.open(partial,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as f:
            authenticate_file(source/row['path'],row,output=f,previous_identity=identities[row['path']])
            f.flush();os.fsync(f.fileno())
        os.link(partial,target,follow_symlinks=False);partial.unlink();target.chmod(0o444)


def stage(destination,work_dir,*,manifest_path=MANIFEST,source_dir=None,opener_factory=None):
    manifest,_=read_manifest(manifest_path);rows=manifest['files']
    dest=safe_path(destination,fresh=True);work=safe_path(work_dir,fresh=True)
    source=safe_path(source_dir,directory=True) if source_dir is not None else None
    disjoint(dest,work,source,safe_path(manifest_path))
    need(shutil.disk_usage(dest.parent).free>=TOTAL+5*1024**3,'disk_reserve')
    work.mkdir(mode=0o755);receipts=work/'members';receipts.mkdir(mode=0o755);state=None
    failure=None;identities={};started=time.monotonic()
    try:
        # No original copy or destination creation until every local input passes.
        if source is not None:identities=authenticate_all(source,rows)
        dest.mkdir(mode=0o755)
        if source is not None:copy_all(source,dest,rows,identities)
        else:
            state=State(rows,'originals')
            with ThreadPoolExecutor(max_workers=2) as pool:
                iterator=iter(rows);pending=set()
                def submit(row):return pool.submit(download_one,row,dest,receipts,state,opener_factory() if opener_factory else None)
                for _ in range(2):
                    row=next(iterator,None)
                    if row:pending.add(submit(row))
                try:
                    while pending:
                        done,pending=wait(pending,timeout=0.1,return_when=FIRST_COMPLETED);state.check()
                        for f in done:f.result()
                        for _ in done:
                            row=next(iterator,None)
                            if row:pending.add(submit(row))
                except BaseException:state.abort.set();raise
        authenticate_all(dest,rows)
    except BaseException as error:failure=error
    report=dict(status='failed_preserved' if failure else 'complete',source_manifest_sha256=MANIFEST_SHA,
        mode='verified_local_copy' if source is not None else 'bounded_original_download',
        files_expected=len(rows),source_bytes=TOTAL,elapsed_seconds=time.monotonic()-started,
        requests_started=len(state.started) if state else 0,bytes_received=state.received if state else 0,
        source_numeric_parsing=False,automatic_retries=0,
        error_type=type(failure).__name__ if failure else None,
        error_code=(str(failure) if isinstance(failure,SourceError) else 'staging_failure') if failure else None)
    write_json(work/'result.json',report)
    if failure:raise failure
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination');parser.add_argument('--work-dir');parser.add_argument('--source-dir')
    parser.add_argument('--manifest',default=str(MANIFEST));parser.add_argument('--verify-existing',action='store_true')
    args=parser.parse_args(argv)
    if not args.destination:
        print(json.dumps(dict(status='plan_only',manifest_sha256=MANIFEST_SHA,files=131,source_bytes=TOTAL,
            runtime_source_root='/app/data/emomatch',public_manifest='/app/source_manifest.json',
            frozen_final_manifest_required=True)));return 0
    if args.verify_existing:
        if args.source_dir or args.work_dir:parser.error('verify-existing is read-only; no source-dir/work-dir')
    elif not args.work_dir:parser.error('--work-dir required for preserved capture/copy evidence')
    def expired(*_):raise SourceError('wall_deadline')
    prior=signal.signal(signal.SIGALRM,expired);signal.alarm(1800)
    try:
        if args.verify_existing:
            verify_staged(args.destination,args.manifest);report=dict(status='verified',files=131,source_bytes=TOTAL)
        else:report=stage(args.destination,args.work_dir,manifest_path=args.manifest,source_dir=args.source_dir)
        print(json.dumps(report));return 0
    except BaseException as error:
        print(json.dumps(dict(status='failed_preserved',error_type=type(error).__name__,
            error_code=str(error) if isinstance(error,SourceError) else 'staging_failure')));return 1
    finally:signal.alarm(0);signal.signal(signal.SIGALRM,prior)


if __name__=='__main__':raise SystemExit(main())
