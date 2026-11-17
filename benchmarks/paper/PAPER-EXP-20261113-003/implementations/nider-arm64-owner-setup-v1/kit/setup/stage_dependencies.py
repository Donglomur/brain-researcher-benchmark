"""Deterministic dependency-only staging; no acquisition, Docker or install."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

LOCK_BYTES = 54066
LOCK_SHA256 = 'c14b3cb46b988166263ebe52fa652224c5c5009b77e107ad7dc6e29d3d25ad49'
INSTALLERS = {'offline_install.sh': {'bytes': 987, 'sha256': '6741af4a7032ad2d7e8005516b6ef7fd2ccd34f68e521e0d816ae4f1d94e785c'}, 'install_locked.R': {'bytes': 4057, 'sha256': '0d603f24bfa5680c93d2ac06a208a4fc35dc6842d99c9905bdc81e0fa8a225c1'}}  # exact ordinary source identities sealed by composer


def need(ok, code):
    if not ok: raise ValueError(code)


def data(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def read_file(path, size, sha):
    p = Path(path)
    need(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)), 'staging_plain_path')
    need(type(size) is int and 0 <= size <= 104857600, 'staging_extent')
    with os.fdopen(os.open(p, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as f:
        a=os.fstat(f.fileno());need(stat.S_ISREG(a.st_mode) and a.st_size==size, 'staging_regular_file')
        b=f.read(size+1);z=os.fstat(f.fileno())
    now=p.lstat()
    need(all(getattr(a,k)==getattr(z,k)==getattr(now,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')), 'staging_changed')
    need(len(b)==size and hashlib.sha256(b).hexdigest()==sha, 'staging_identity')
    return b


def table(headers, rows):
    values=[[str(row[h]) for h in headers] for row in rows]
    need(all(not any(c in x for c in '\t\r\n') for row in values for x in row), 'staging_table_lexeme')
    return ('\t'.join(headers)+'\n'+''.join('\t'.join(row)+'\n' for row in values)).encode()


def stage(request):
    need(type(request) is dict and set(request)=={'schema','archive_paths','output_root'} and
         request['schema']=='nider_dependency_staging_request_v1', 'staging_request')
    fixed=json.loads(read_file(Path(__file__).with_name('DEPENDENCIES.json').resolve(), LOCK_BYTES, LOCK_SHA256))
    entries=[]
    for row in fixed['R_packages']:
        a=row['archive'];entries.append(('r/archives/'+a['Filename'],int(a['Bytes']),a['SHA256']))
    for row in fixed['OS_packages']:entries.append(('os/'+row['filename'],row['bytes'],row['SHA256']))
    need(len(entries)==82 and len({x[0] for x in entries})==82 and
         type(request['archive_paths']) is dict and set(request['archive_paths'])=={x[0] for x in entries}, 'staging_exact82_archives')
    root=Path(request['output_root'])
    need(root.is_absolute() and '..' not in root.parts and not any(p.is_symlink() for p in (root,*root.parents)) and not root.exists(), 'staging_fresh_root')
    root.mkdir(mode=0o700);(root/'inputs/r/archives').mkdir(parents=True,mode=0o700);(root/'inputs/os').mkdir(mode=0o700)
    files=[];read_bytes=0
    def write(relative,raw):
        p=root/relative
        with p.open('xb') as f:f.write(raw)
        p.chmod(0o600)
        item={'path':relative,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()};files.append(item);return item
    for relative,size,sha in entries:
        raw=read_file(request['archive_paths'][relative],size,sha);read_bytes+=len(raw)
        need(read_bytes<=1073741824,'staging_read_cap')
        write('inputs/'+relative,raw)
    plan=table(['Package','Version','Requires'],fixed['R_packages'])
    archives=table(['Package','Version','Filename','SHA256','Bytes','SourceURL'],[x['archive'] for x in fixed['R_packages']])
    order=('\n'.join(fixed['OS_install_order'])+'\n').encode()
    need(hashlib.sha256(plan).hexdigest()==fixed['old_PACKAGE_PLAN_sha256'] and
         hashlib.sha256(archives).hexdigest()==fixed['old_SOURCE_ARCHIVES_sha256'] and
         hashlib.sha256(order).hexdigest()==fixed['old_OS_ORDER_sha256'], 'staging_original_configuration_bytes')
    write('PACKAGE_PLAN.tsv',plan);write('inputs/r/SOURCE_ARCHIVES.tsv',archives);write('inputs/os/INSTALL_ORDER.txt',order)
    checksum=''.join(x['sha256']+'  '+x['path'].removeprefix('inputs/')+'\n' for x in files if x['path'].startswith('inputs/')).encode()
    write('inputs/INPUTS.sha256',checksum)
    for name,entry in INSTALLERS.items():
        need(re.fullmatch('[A-Za-z0-9_.-]+',name) is not None,'installer_name')
        write(name,read_file(Path(__file__).with_name(name).resolve(),entry['bytes'],entry['sha256']))
    expected={x['path'] for x in files}
    need({str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}==expected,'staging_no_extra_inputs')
    receipt={'schema':'nider_portable_dependency_staging_v1','setup_lock_sha256':LOCK_SHA256,
             'root':str(root),'files':files,'archive_count':82,'archive_body_read_bytes':read_bytes,
             'input_scope':'only_locked_dependencies_and_installers','network_calls':0,'native_calls':0}
    # Receipt is outside the mounted staging directory, so it cannot introduce
    # uncontrolled paths or inputs to the installer.
    return receipt


def build_plan(staging, owner_root, name):
    from build_spec import make_plan
    fixed=json.loads(read_file(Path(__file__).with_name('DEPENDENCIES.json').resolve(),LOCK_BYTES,LOCK_SHA256))
    return make_plan(staging,owner_root,name,fixed,LOCK_SHA256)


if __name__=='__main__':
    os.umask(0o077)
    need(len(sys.argv)==4,'staging_request_sha_and_receipt')
    p=Path(sys.argv[1]).resolve();request=json.loads(read_file(p,p.stat().st_size,sys.argv[2]))
    value=stage(request)
    out=Path(sys.argv[3]);need(out.is_absolute() and not out.exists() and not out.is_relative_to(Path(value['root'])),'external_staging_receipt')
    with out.open('xb') as f:f.write(data(value))
