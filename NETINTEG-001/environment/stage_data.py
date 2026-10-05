"""Pinned build-time source staging; verify_staged never fetches or decodes data.

The NITRC archive and member digests are measured fresh-HTTPS identities, not
publisher checksums. Conflicting existing files and failed transfer evidence
are preserved. Only explicit selected tar members can become runtime inputs.
"""
import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import signal
import tarfile
import time
import urllib.parse
import urllib.request


MANIFEST_SHA256 = '6bc0e95fdd48ed3d3229acc9ce9e48a55860837a5e10d3acade4f0d645cbc5aa'
PARTICIPANTS = (10042,10064,10128,21019,23008,23012,27011,27018,27034,27037,
    1019436,1206380,1418396,1517058,1552181,1562298,1679142,2014113,2497695,
    2950754,3007585,3154996,3205761,3520880,3624598,3699991,3884955,3902469,
    3994098,4016887,4046678,4134561,4164316,4275075,6115230,7774305,8409791,
    8697774,9744150,9750701)
COMMIT = 'd1454a611f7de10a3b36665e6fbb3fb6c770d140'
ATLAS_PREFIX = 'stable_projects/brain_parcellation/Schaefer2018_LocalGlobal/Parcellations/MNI/'
ATLAS_IMAGE = 'Schaefer2018_100Parcels_17Networks_order_FSLMNI152_2mm.nii.gz'
ATLAS_LABELS = 'Schaefer2018_100Parcels_17Networks_order.txt'
META_ROLES = {'ADHD200_40subs_ID.txt':'cohort_ids',
    'ADHD200_40subs_motion_parameters_and_phenotypics.csv':'phenotype_metadata',
    'ADHD200_40subs_slice_timing_parameters.csv':'slice_timing_metadata'}
DIRECT = {
    'atlas/'+ATLAS_IMAGE: ('atlas_image',f'https://raw.githubusercontent.com/ThomasYeoLab/CBIG/{COMMIT}/{ATLAS_PREFIX}{ATLAS_IMAGE}'),
    'atlas/'+ATLAS_LABELS: ('atlas_labels',f'https://raw.githubusercontent.com/ThomasYeoLab/CBIG/{COMMIT}/{ATLAS_PREFIX}{ATLAS_LABELS}'),
    'atlas/LICENSE.md': ('atlas_license',f'https://raw.githubusercontent.com/ThomasYeoLab/CBIG/{COMMIT}/LICENSE.md'),
    'provenance/nilearn_0.12.1_adhd.rst': ('adhd_terms','https://raw.githubusercontent.com/nilearn/nilearn/0.12.1/nilearn/datasets/description/adhd.rst'),
}
MAX_BYTES = 2_200_000_000
TIMEOUT_SECONDS = 1200


def reject_symlinks(path):
    path=Path(path).absolute()
    if any(p.is_symlink() for p in (path,*path.parents)):
        raise ValueError('Preserve symlink in source/destination path')


def make_directories(path):
    """Set755 on newly created owned directories only, never an existing cache."""
    path=Path(path);reject_symlinks(path);missing=[];cursor=path
    while not cursor.exists():missing.append(cursor);cursor=cursor.parent
    if not cursor.is_dir():raise ValueError('Non-directory staging ancestor')
    for item in reversed(missing):item.mkdir();item.chmod(0o755)


def safe_relative(value):
    if not isinstance(value,str) or not value or '\\' in value or '\0' in value:
        raise ValueError('Invalid relative source path')
    p=PurePosixPath(value)
    if p.is_absolute() or '..' in p.parts or p.as_posix()!=value or value=='.':
        raise ValueError('Unsafe/noncanonical relative source path')
    return value


def digest_record(record):
    if type(record.get('size_bytes')) is not int or not 0<record['size_bytes']<=150_000_000:
        raise ValueError('Invalid pinned source size')
    sha=record.get('sha256','')
    if not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):
        raise ValueError('Invalid source SHA256')


def validate_manifest(manifest):
    if manifest.get('schema_version')!=1 or manifest.get('dataset_id')!='nilearn-adhd40-schaefer100-17':
        raise ValueError('Unexpected dataset/schema')
    if manifest.get('snapshot_id')!='netinteg-originals-20261001' or manifest.get('participants')!=list(PARTICIPANTS):
        raise ValueError('Unexpected exact40 participant identity/order')
    expected={f'metadata/{name}':role for name,role in META_ROLES.items()}
    expected.update({path:role for path,(role,url) in DIRECT.items()})
    for pid in PARTICIPANTS:
        expected[f'data/{pid:07d}/{pid:07d}_rest_tshift_RPI_voreg_mni.nii.gz']='bold'
        expected[f'data/{pid:07d}/{pid:07d}_regressors.csv']='confounds'
    records=manifest.get('files',[])
    if len(records)!=87 or {r.get('path'):r.get('role') for r in records}!=expected:
        raise ValueError('Expected exactly87 literal source paths/roles')
    for item in records:
        safe_relative(item['path']);digest_record(item)
        if item['role'] in ('bold','confounds'):
            if type(item.get('participant')) is not int or f"{item['participant']:07d}"!=PurePosixPath(item['path']).parts[1]:
                raise ValueError('Source participant/path disagreement')
        elif 'participant' in item:
            raise ValueError('Participant must be absent for cohort-level source')
        if item['path'] in DIRECT and item.get('url')!=DIRECT[item['path']][1]:
            raise ValueError('Unexpected immutable direct-source URL')
    archive_records=manifest.get('archives',[])
    if len(archive_records)!=41 or {a.get('archive_id') for a in archive_records}!=set(range(7781,7822)):
        raise ValueError('Expected exact41 original archive IDs')
    by_path={r['path']:r for r in records}
    mapped=set()
    for archive in archive_records:
        digest_record(archive)
        aid=archive['archive_id']
        filename='adhd40_metadata.tgz' if aid==7781 else f'adhd40_{PARTICIPANTS[aid-7782]:07d}.tgz'
        url=f'https://www.nitrc.org/frs/download.php/{aid}/{filename}'
        if archive.get('url')!=url or archive.get('filename')!=filename:
            raise ValueError('Unexpected original archive URL/name')
        members=archive.get('members',[])
        if len(members)!=(3 if aid==7781 else 2):raise ValueError('Unexpected selected member count')
        names=set()
        for member in members:
            path=safe_relative(member['path']);name=safe_relative(member['archive_member'])
            digest_record(member)
            if path not in by_path or path in mapped or name in names:raise ValueError('Duplicate/unknown selected member')
            ref=by_path[path]
            if any(member[key]!=ref[key] for key in ('size_bytes','sha256','archive_member')) or ref.get('archive_id')!=aid or ref.get('source_url')!=url:
                raise ValueError('Archive/file identity mapping mismatch')
            if name!=(path.removeprefix('metadata/') if aid==7781 else path):
                raise ValueError('Unexpected selected member path')
            names.add(name);mapped.add(path)
    if mapped!={p for p in by_path if p not in DIRECT}:raise ValueError('Incomplete archive coverage')
    if sum(a['size_bytes'] for a in archive_records)+sum(by_path[p]['size_bytes'] for p in DIRECT)>MAX_BYTES:
        raise ValueError('Frozen source set exceeds transfer cap')


def read_manifest(path):
    path=Path(path);reject_symlinks(path)
    if not path.is_file() or path.stat().st_size>1_000_000:raise ValueError('Invalid source manifest type/size')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=MANIFEST_SHA256:raise ValueError('Whole source manifest SHA256 mismatch')
    manifest=json.loads(raw);validate_manifest(manifest)
    return manifest,raw


def verify_file(path,record):
    path=Path(path);reject_symlinks(path);digest_record(record)
    if not path.is_file() or path.stat().st_size!=record['size_bytes']:raise ValueError(f'Source size/type mismatch: {path}')
    before=path.stat();h=hashlib.sha256()
    blob=hashlib.sha1(f'blob {record["size_bytes"]}\0'.encode()) if 'git_blob_sha1' in record else None
    with path.open('rb') as stream:
        while chunk:=stream.read(1<<20):
            h.update(chunk)
            if blob is not None:blob.update(chunk)
    after=path.stat()
    if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):
        raise ValueError('Source changed while checking')
    if h.hexdigest()!=record['sha256'] or (blob is not None and blob.hexdigest()!=record['git_blob_sha1']):
        raise ValueError(f'Source digest mismatch: {path}')


def inventory(root,records,allow_missing=False):
    root=Path(root);reject_symlinks(root)
    expected={r['path'] for r in records}|{'source_manifest.json'}
    expected_dirs={p.as_posix() for name in expected for p in PurePosixPath(name).parents if p.as_posix()!='.'}
    found=set()
    if root.exists():
        if not root.is_dir():raise ValueError('Source root is not a directory')
        for path in root.rglob('*'):
            reject_symlinks(path);rel=path.relative_to(root).as_posix()
            if path.is_dir():
                if rel not in expected_dirs:raise ValueError('Unexpected source directory')
            elif path.is_file():
                if rel not in expected:raise ValueError('Unexpected source file')
                found.add(rel)
            else:raise ValueError('Unexpected source filesystem entry')
    if not allow_missing and found!=expected:raise ValueError('Incomplete exact source inventory')
    return found


def verify_staged(source_dir):
    source_dir=Path(source_dir);manifest,_=read_manifest(source_dir/'source_manifest.json')
    inventory(source_dir,manifest['files'])
    for record in manifest['files']:verify_file(source_dir/record['path'],record)
    return manifest


@contextlib.contextmanager
def deadline(seconds):
    def expired(*unused):raise TimeoutError('Source staging wall-clock bound exceeded')
    old_handler=signal.signal(signal.SIGALRM,expired)
    old_timer=signal.setitimer(signal.ITIMER_REAL,seconds)
    try:yield
    finally:
        signal.setitimer(signal.ITIMER_REAL,*old_timer);signal.signal(signal.SIGALRM,old_handler)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):return None


def json_new(path,obj):
    with Path(path).open('x') as stream:json.dump(obj,stream,indent=2,allow_nan=False);stream.write('\n')


def source_location(url):
    parsed=urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parsed.scheme,parsed.netloc,parsed.path,'',''))


def download_sources(records,ledger):
    """Serial exact GETs; sanitized evidence, no credentials/ranges/retries."""
    ledger=Path(ledger);reject_symlinks(ledger);ledger.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();total=0;completed={};active=None
    json_new(ledger/'attempt.json',{'sources':records,'maximum_bytes':MAX_BYTES,'timeout_seconds':TIMEOUT_SECONDS,'retries':0})
    opener=urllib.request.build_opener(NoRedirect)
    try:
        with deadline(TIMEOUT_SECONDS):
            for index,record in enumerate(records):
                active={'url':record['url'],'received_bytes':0,'started_at_utc':datetime.now(timezone.utc).isoformat()}
                print(json.dumps({'source_transfer':'start','index':index,'source':source_location(record['url']),
                                  'expected_bytes':record['size_bytes']}),flush=True)
                request=urllib.request.Request(record['url'],headers={'User-Agent':'netinteg-source-staging/1.0','Accept-Encoding':'identity'})
                target=ledger/f'payload-{index}.partial'
                with opener.open(request,timeout=60) as response:
                    active.update(status=response.status,headers={key:response.headers[key] for key in
                        ('Content-Length','Content-Type','Last-Modified','ETag','Content-MD5','Digest') if response.headers.get(key) is not None})
                    if response.status!=200 or response.geturl()!=record['url']:
                        raise ValueError('Unexpected source HTTP status/URL')
                    if int(response.headers.get('Content-Length','-1'))!=record['size_bytes'] or response.headers.get('Content-Encoding','identity')!='identity':
                        raise ValueError('Unexpected source HTTP length/encoding')
                    with target.open('xb') as stream:
                        while True:
                            remaining=min(record['size_bytes']-active['received_bytes'],MAX_BYTES-total)
                            chunk=response.read(min(1<<20,remaining+1))
                            if not chunk:break
                            total+=len(chunk);active['received_bytes']+=len(chunk)
                            if total>MAX_BYTES or active['received_bytes']>record['size_bytes']:raise ValueError('Source byte bound exceeded')
                            stream.write(chunk)
                verify_file(target,record);target.chmod(0o444)
                completed[record['url']]=target
                json_new(ledger/f'payload-{index}.json',{**active,'sha256':record['sha256'],'status':'verified'})
                print(json.dumps({'source_transfer':'verified','index':index,'source':source_location(record['url']),
                                  'received_bytes':active['received_bytes'],'sha256':record['sha256']}),flush=True)
        json_new(ledger/'result.json',{'status':'verified','transferred_bytes':total,'elapsed_seconds':time.monotonic()-started})
    except BaseException as error:
        json_new(ledger/'result.json',{'status':'failed','transferred_bytes':total,'elapsed_seconds':time.monotonic()-started,
                  'active_source':active,'error_type':type(error).__name__,'error':str(error),'automatic_retry':False})
        print(json.dumps({'source_transfer':'failed','source':None if active is None else source_location(active['url']),
                          'received_bytes':0 if active is None else active['received_bytes'],
                          'error_type':type(error).__name__,'error':str(error)[:400]}),flush=True)
        raise
    return completed


def copy_exclusive(source,target,record):
    source=Path(source);target=Path(target);reject_symlinks(source);reject_symlinks(target)
    make_directories(target.parent)
    with source.open('rb') as src,target.open('xb') as dst:
        while chunk:=src.read(1<<20):dst.write(chunk)
    verify_file(target,record);target.chmod(0o444)


def extract_selected(archive_path,records,destination):
    """Never extractall; reject every unsafe member, write selected names only."""
    destination=Path(destination);reject_symlinks(destination)
    required={safe_relative(r['archive_member']):r for r in records}
    if not records or len(required)!=len(records):raise ValueError('Duplicate/missing extraction selection')
    seen=set();found=set();unpacked=0
    with tarfile.open(archive_path,'r|gz') as archive:
        for member in archive:
            name=safe_relative(member.name)
            if not(member.isfile() or member.isdir()) or member.size<0:raise ValueError('Unsafe tar member type')
            if name in seen:raise ValueError('Duplicate tar member')
            seen.add(name);unpacked+=member.size
            if len(seen)>1000 or unpacked>200_000_000:raise ValueError('Unexpected archive expansion')
            if name not in required:continue
            record=required[name]
            if not member.isfile() or member.size!=record['size_bytes']:raise ValueError('Selected member size/type mismatch')
            target=destination/safe_relative(record['path']);reject_symlinks(target);make_directories(target.parent)
            source=archive.extractfile(member)
            if source is None:raise ValueError('Missing selected source stream')
            with target.open('xb') as stream:
                remaining=member.size
                while remaining:
                    chunk=source.read(min(1<<20,remaining))
                    if not chunk:raise ValueError('Truncated selected member')
                    stream.write(chunk);remaining-=len(chunk)
                if source.read(1):raise ValueError('Excess selected member bytes')
            verify_file(target,record);target.chmod(0o444);found.add(name)
    if found!=set(required):raise ValueError('Missing selected members')


def stage_data(destination,manifest_path,cache_dir=None,archive_cache_dirs=(),ledger=None):
    destination=Path(destination);manifest,raw=read_manifest(manifest_path)
    found=inventory(destination,manifest['files'],allow_missing=True)
    manifest_target=destination/'source_manifest.json'
    if 'source_manifest.json' in found and manifest_target.read_bytes()!=raw:raise ValueError('Preserve conflicting destination manifest')
    missing=[]
    for record in manifest['files']:
        if record['path'] in found:verify_file(destination/record['path'],record)
        else:missing.append(record)
    # All preexisting targets are verified before cache/network/writes.
    sources={}
    if cache_dir is not None:
        cache_dir=Path(cache_dir);reject_symlinks(cache_dir)
        if not cache_dir.is_dir():raise ValueError('Cache directory does not exist')
        for record in missing:
            candidates=[cache_dir/record['path']]
            if 'archive_member' in record:candidates.append(cache_dir/record['archive_member'])
            for candidate in dict.fromkeys(candidates):
                reject_symlinks(candidate)
                if candidate.exists():verify_file(candidate,record);sources[record['path']]=candidate;break
    needed=[];archive_sources={};archive_records={}
    for archive in manifest['archives']:
        selected=[r for r in missing if r.get('archive_id')==archive['archive_id'] and r['path'] not in sources]
        if not selected:continue
        archive_records[archive['archive_id']]=selected
        for root in archive_cache_dirs:
            root=Path(root);reject_symlinks(root)
            if not root.is_dir():raise ValueError('Archive cache directory does not exist')
            candidate=root/archive['filename'];reject_symlinks(candidate)
            if candidate.exists():verify_file(candidate,archive);archive_sources[archive['archive_id']]=candidate;break
        if archive['archive_id'] not in archive_sources:needed.append(archive)
    needed.extend(r for r in missing if r['path'] in DIRECT and r['path'] not in sources)
    if needed:
        ledger=Path(ledger) if ledger is not None else destination.parent/'netinteg_source_download'
        if ledger.absolute()==destination.absolute() or destination.absolute() in ledger.absolute().parents:
            raise ValueError('Transfer evidence must be outside closed runtime source inventory')
        downloaded=download_sources(needed,ledger)
        for record in needed:
            if 'archive_id' in record:archive_sources[record['archive_id']]=downloaded[record['url']]
            else:sources[record['path']]=downloaded[record['url']]
    make_directories(destination)
    for aid,selected in archive_records.items():extract_selected(archive_sources[aid],selected,destination)
    for record in missing:
        if record['path'] in sources:copy_exclusive(sources[record['path']],destination/record['path'],record)
    if manifest_target.exists():
        if manifest_target.read_bytes()!=raw:raise ValueError('Preserve conflicting destination manifest race')
    else:
        with manifest_target.open('xb') as stream:stream.write(raw)
        manifest_target.chmod(0o444)
    verify_staged(destination)
    print('Verified87 fixed source files and source_manifest.json; no scientific processing.',flush=True)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination',type=Path,default=Path('/app/data/netinteg'))
    parser.add_argument('--manifest',type=Path,default=Path(__file__).with_name('source_manifest.json'))
    parser.add_argument('--verify-existing',action='store_true',help='Offline identity check only; never fetch')
    parser.add_argument('--cache-dir',type=Path,help='Read-only verified runtime/source member cache')
    parser.add_argument('--archive-cache-dir',type=Path,action='append',default=[],help='Read-only original archives; may repeat for separate owned folders')
    parser.add_argument('--ledger',type=Path,help='Fresh exclusive transfer-evidence directory outside runtime source')
    args=parser.parse_args()
    if args.verify_existing:verify_staged(args.destination);print('Existing closed source bundle verified offline.',flush=True)
    else:stage_data(args.destination,args.manifest,args.cache_dir,args.archive_cache_dir,args.ledger)


if __name__=='__main__':main()
