"""Build-time frozen CNP source acquisition; verify_staged is strictly offline."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import threading
import time
import urllib.parse
import urllib.request

MANIFEST_PATH = Path(__file__).with_name('source_manifest.json')
MANIFEST_SHA256 = 'f4ea1c9f5a3a75d722fedd2cece082dd84502f20c5c7d2d11704c5bcc45594e3'
CAP_BYTES, TIMEOUT_SECONDS = 2_400_000_000, 1800
S3_BASE = 'https://s3.amazonaws.com/openneuro/ds000030/ds000030_R1.0.5/uncompressed/'
GIT_BASE = 'https://raw.githubusercontent.com/nilearn/nilearn/4c76adf58b6b48cdbd3e2cfa9e848f3a9324e570/nilearn/datasets/data/fsaverage5/'
SAFE_HEADERS = {'content-length','content-type','content-encoding','etag','last-modified','x-amz-version-id'}


def reject_symlinks(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path,*path.parents)):
        raise ValueError('Symlinked path or ancestor forbidden')


def safe_relative(value):
    if not isinstance(value,str) or '\\' in value or '\x00' in value:
        raise ValueError('Unsafe relative source path')
    p = PurePosixPath(value)
    if p.is_absolute() or any(v in ('','.','..') for v in value.split('/')) or str(p) != value:
        raise ValueError('Unsafe relative source path')


def validate_record(r):
    safe_relative(r['path'])
    if type(r['size_bytes']) is not int or not 0 < r['size_bytes'] <= CAP_BYTES:
        raise ValueError('Invalid source size')
    if not re.fullmatch('[0-9a-f]{64}',r.get('sha256','')):
        raise ValueError('Invalid source digest')
    url = r['url']
    if 's3_version_id' in r:
        if not url.startswith(S3_BASE) or '?' in url or '#' in url:
            raise ValueError('Unexpected original S3 source')
        if (r['transport_url'] != url+'?versionId='+urllib.parse.quote(r['s3_version_id'],safe='')
                or not re.fullmatch('"[0-9a-f]{32}"',r.get('etag',''))):
            raise ValueError('Missing immutable version or single-part ETag')
    elif r['role'] in ('pial_left','pial_right'):
        if (url != GIT_BASE+f"pial_{r['role'].split('_')[1]}.gii.gz" or r['transport_url'] != url
                or not re.fullmatch('[0-9a-f]{40}',r.get('git_blob_sha1',''))):
            raise ValueError('Unexpected pial Git identity')
    elif r['role'] in ('annotation_left','annotation_right'):
        ident,hemi = (9343,'lh') if r['role']=='annotation_left' else (9342,'rh')
        if (url != f'https://www.nitrc.org/frs/download.php/{ident}/{hemi}.aparc.a2009s.annot'
                or r['transport_url'] != url or r['nitrc_release_id'] != 3353):
            raise ValueError('Unexpected annotation source')
    else:
        raise ValueError('Unrecognized source transport')


def read_manifest(path=MANIFEST_PATH):
    path=Path(path);reject_symlinks(path);raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=MANIFEST_SHA256:
        raise ValueError('Whole source manifest SHA-256 mismatch')
    m=json.loads(raw)
    if (m['task_id']!='CLINCONN-001' or m['source_version']!='ds000030_R1.0.5'
            or m['dataset_license']!='PDDL' or len(m['files'])!=697):
        raise ValueError('Unexpected original source release or inventory')
    for r in m['files']:validate_record(r)
    if len({r['path'] for r in m['files']})!=697 or sum(r['size_bytes'] for r in m['files'])!=2_305_653_613:
        raise ValueError('Duplicate source or changed payload')
    return m,raw


def verify_file(path,r):
    path=Path(path);reject_symlinks(path)
    if not path.is_file() or path.stat().st_size!=r['size_bytes']:
        raise ValueError(f"Missing/size-mismatched original: {r['path']}")
    sha=hashlib.sha256();md5=hashlib.md5();blob=hashlib.sha1(f"blob {r['size_bytes']}\0".encode())
    with path.open('rb') as stream:
        for b in iter(lambda:stream.read(1<<20),b''):sha.update(b);md5.update(b);blob.update(b)
    if sha.hexdigest()!=r['sha256']:raise ValueError('Original SHA256 mismatch')
    expected=r.get('md5',r.get('etag','').strip('"'))
    if expected and md5.hexdigest()!=expected:raise ValueError('Original MD5/ETag mismatch')
    if 'git_blob_sha1' in r and blob.hexdigest()!=r['git_blob_sha1']:raise ValueError('Published Git blob mismatch')


def inventory(root,expected):
    root=Path(root);reject_symlinks(root)
    if not root.is_dir():raise ValueError('Original source directory absent')
    dirs={str(p) for name in expected for p in PurePosixPath(name).parents if str(p)!='.'};found=set()
    for p in root.rglob('*'):
        if p.is_symlink():raise ValueError('Symlink in original source inventory')
        name=p.relative_to(root).as_posix()
        if p.is_file():found.add(name)
        elif not p.is_dir() or name not in dirs:raise ValueError('Unexpected directory/special source file')
    if found!=set(expected):raise ValueError('Original source inventory differs from pinned bundle')


def verify_staged(data_dir):
    data_dir=Path(data_dir);m,_=read_manifest(data_dir/'source_manifest.json')
    inventory(data_dir,[r['path'] for r in m['files']]+['source_manifest.json'])
    for r in m['files']:verify_file(data_dir/r['path'],r)
    return m


def write_json_new(path,value):
    reject_symlinks(path)
    with Path(path).open('x') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('Unpinned redirect forbidden')


def download_sources(m,ledger):
    ledger=Path(ledger);reject_symlinks(ledger);ledger.mkdir(parents=True,exist_ok=False)
    (ledger/'originals').mkdir(mode=0o755)
    started=time.monotonic();lock=threading.Lock();stop=threading.Event();state={'transferred_bytes':0,'completed_files':0}
    write_json_new(ledger/'attempt.json',dict(source_manifest_sha256=MANIFEST_SHA256,maximum_payload_bytes=CAP_BYTES,wall_seconds=TIMEOUT_SECONDS,concurrency=2,automatic_retries=0))
    def append(value):
        with lock,(ledger/'transfers.jsonl').open('a') as stream:stream.write(json.dumps(value)+'\n');stream.flush()
    def fetch(r):
        if stop.is_set():raise RuntimeError('Other source failed; no further request')
        validate_record(r);target=ledger/'originals'/r['path'];target.parent.mkdir(parents=True,exist_ok=True)
        partial=target.with_name(target.name+'.partial');n=0;headers={}
        print(f"Source start: {r['path']}, {r['size_bytes']} bytes",flush=True)
        try:
            h={'User-Agent':'clinconn-source-staging/1.0','Accept-Encoding':'identity'}
            if 's3_version_id' in r:h['If-Match']=r['etag']
            request=urllib.request.Request(r['transport_url'],headers=h)
            with urllib.request.build_opener(NoRedirect()).open(request,timeout=30) as response:
                headers={k.lower():v for k,v in response.headers.items() if k.lower() in SAFE_HEADERS}
                if response.status!=200 or response.geturl()!=r['transport_url'] or headers.get('content-encoding','identity')!='identity':raise ValueError('Unexpected HTTP status/URL/encoding')
                if 'content-length' in headers and int(headers['content-length'])!=r['size_bytes']:raise ValueError('Unexpected HTTP size')
                if 's3_version_id' in r and (headers.get('x-amz-version-id')!=r['s3_version_id'] or headers.get('etag')!=r['etag']):raise ValueError('Immutable S3 response identity differs')
                with partial.open('xb') as stream:
                    while True:
                        if stop.is_set() or time.monotonic()-started>TIMEOUT_SECONDS:raise TimeoutError('Source wall limit or another source failure')
                        block=response.read(min(1<<20,r['size_bytes']+1-n))
                        if not block:break
                        n+=len(block)
                        with lock:
                            state['transferred_bytes']+=len(block)
                            if state['transferred_bytes']>CAP_BYTES:raise ValueError('Cumulative source payload limit exceeded')
                        if n>r['size_bytes']:raise ValueError('Pinned individual source size exceeded')
                        stream.write(block)
            verify_file(partial,r)
            if target.exists():raise FileExistsError('Preserve original source target')
            partial.rename(target);target.chmod(0o444)
            with lock:state['completed_files']+=1
            append(dict(path=r['path'],status='verified',bytes=n,sha256=r['sha256'],headers=headers))
            print(f"Source verified: {r['path']}, {n} bytes",flush=True)
        except BaseException as e:
            stop.set();append(dict(path=r['path'],status='failed',bytes=n,headers=headers,error_type=type(e).__name__,error=str(e)))
            print(f"Source failed: {r['path']}, {n} bytes, {type(e).__name__}: {e}",flush=True);raise
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(fetch,r) for r in m['files']]
            try:
                for f in as_completed(futures):f.result()
            except BaseException:
                stop.set()
                for f in futures:f.cancel()
                raise
        write_json_new(ledger/'result.json',dict(status='complete',**state,elapsed_seconds=time.monotonic()-started))
    except BaseException as e:
        write_json_new(ledger/'result.json',dict(status='failed',**state,elapsed_seconds=time.monotonic()-started,error_type=type(e).__name__,error=str(e)));raise
    return ledger/'originals'


def stage_data(destination,source_dir=None,ledger=None,manifest_path=MANIFEST_PATH):
    destination=Path(destination).absolute();reject_symlinks(destination);m,raw=read_manifest(manifest_path)
    if destination.exists():return verify_staged(destination)
    if source_dir is not None:
        source=Path(source_dir).absolute();reject_symlinks(source)
        if source==destination or source in destination.parents or destination in source.parents:raise ValueError('Source/destination must be disjoint')
    else:
        ledger=Path(ledger).absolute() if ledger else destination.parent/(destination.name+'-download')
        if ledger==destination or ledger in destination.parents or destination in ledger.parents:raise ValueError('Ledger/destination must be disjoint')
        source=download_sources(m,ledger)
    inventory(source,[r['path'] for r in m['files']])
    for r in m['files']:verify_file(source/r['path'],r)
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=Path(tempfile.mkdtemp(prefix='.'+destination.name+'-staging-',dir=destination.parent));temporary.chmod(0o755)
    for r in m['files']:
        target=temporary/r['path'];target.parent.mkdir(parents=True,exist_ok=True)
        with (source/r['path']).open('rb') as src,target.open('xb') as dst:shutil.copyfileobj(src,dst,length=1<<20)
        target.chmod(0o444)
    with (temporary/'source_manifest.json').open('xb') as stream:stream.write(raw)
    (temporary/'source_manifest.json').chmod(0o444)
    for p in temporary.rglob('*'):
        if p.is_dir():p.chmod(0o755)
    verify_staged(temporary)
    if destination.exists() or destination.is_symlink():raise FileExistsError('Destination appeared during staging')
    temporary.rename(destination)
    print(f"Staged {len(m['files'])} original inputs plus manifest; no scientific processing",flush=True)
    return m


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--destination',type=Path,default=Path('/app/data/clinconn'))
    p.add_argument('--source-dir',type=Path,help='Optional exact original bundle for read-only offline reuse');p.add_argument('--manifest',type=Path,default=MANIFEST_PATH);p.add_argument('--ledger',type=Path);p.add_argument('--verify-existing',action='store_true');a=p.parse_args()
    if a.verify_existing:verify_staged(a.destination);print('Offline fixed source verification passed',flush=True)
    else:stage_data(a.destination,a.source_dir,a.ledger,a.manifest)


if __name__=='__main__':main()
