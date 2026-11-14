"""Copy exactly the reviewed private source kit; never execute its contents."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys

MANIFEST_BYTES=4865
MANIFEST_SHA256='425098566c260f68372ccfeb8f87cc6142fdde73de81f4c782ff2e50b0070f3a'
ROOTS=('configuration','owner','participant','runtime','setup')


def need(ok,code):
    if not ok:raise ValueError(code)


def encoded(value):return (json.dumps(value,indent=2,allow_nan=False)+'\n').encode()


class Budget:
    """Logical full-body requests and returned bytes, not kernel I/O."""
    def __init__(self,limit=33554432):self.limit=limit;self.requested=0;self.returned=0;self.calls=0
    def reserve(self,n):
        need(type(n) is int and n>=0 and self.requested+n<=self.limit,'source_read_budget')
        self.requested+=n;self.calls+=1
    def record(self,n):self.returned+=n
    def report(self):return {'limit':self.limit,'requested':self.requested,'returned':self.returned,'calls':self.calls}


def absolute(path):
    p=Path(path)
    need(p.is_absolute() and '..' not in p.parts,'absolute_path_without_traversal')
    need(not any(x.is_symlink() for x in (p,*p.parents)),'symlink_path')
    return p


def read_verified(path,entry,budget):
    p=absolute(path);budget.reserve(entry['bytes'])
    with os.fdopen(os.open(p,os.O_RDONLY|os.O_NOFOLLOW),'rb') as stream:
        before=os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1,'regular_single_link_source')
        need(before.st_size==entry['bytes'],'source_extent')
        body=stream.read(entry['bytes']+1);after=os.fstat(stream.fileno())
    now=p.lstat()
    need(all(getattr(before,k)==getattr(after,k)==getattr(now,k) for k in
         ('st_dev','st_ino','st_mode','st_size','st_nlink','st_mtime_ns','st_ctime_ns')),'source_changed_during_read')
    budget.record(len(body))
    need(len(body)==entry['bytes'] and hashlib.sha256(body).hexdigest()==entry['sha256'],'source_digest')
    return body


def validate_manifest(value):
    need(type(value) is dict and set(value)=={'schema','task','profile','entries','file_count','total_bytes','roots'} and
         value['schema']=='nider_exact_private_source_kit_v1' and value['task']=='PAPER-EXP-20261113-003' and
         value['profile']=='nider-three-contrast-reporting-v1' and value['roots']==list(ROOTS),'manifest_schema')
    entries=value['entries'];need(type(entries) is list and len(entries)==value['file_count']==27,'manifest_count')
    names=[]
    for entry in entries:
        need(type(entry) is dict and set(entry)=={'relative_path','bytes','sha256'},'manifest_entry')
        name=entry['relative_path'];need(type(name) is str,'manifest_path')
        path=PurePosixPath(name)
        need(not path.is_absolute() and len(path.parts)==2 and path.parts[0] in ROOTS and
             all(x not in ('','.','..') for x in path.parts) and str(path)==name and '\\' not in name,
             'manifest_path')
        need(type(entry['bytes']) is int and 0<entry['bytes']<=1048576 and type(entry['sha256']) is str and
             len(entry['sha256'])==64 and all(x in '0123456789abcdef' for x in entry['sha256']),'manifest_identity')
        names.append(name)
    need(names==sorted(names) and len(set(names))==27,'manifest_order_or_duplicate')
    need(sum(x['bytes'] for x in entries)==value['total_bytes']==317150,'manifest_total')
    return value


def load_manifest(budget,path=None):
    path=Path(__file__).with_name('KIT_MANIFEST.json') if path is None else path
    raw=read_verified(path,{'bytes':MANIFEST_BYTES,'sha256':MANIFEST_SHA256},budget)
    return validate_manifest(json.loads(raw))


def inventory(root,manifest):
    """Exact closure within the five operative directories; parent docs ignored."""
    root=absolute(root);need(root.is_dir(),'source_root_directory');names=[]
    for name in ROOTS:
        directory=absolute(root/name);need(directory.is_dir(),'missing_source_directory')
        for p in directory.iterdir():
            absolute(p);info=p.lstat()
            need(stat.S_ISREG(info.st_mode) and info.st_nlink==1,'unexpected_source_file_kind')
            names.append(str(p.relative_to(root)))
    need(sorted(names)==[x['relative_path'] for x in manifest['entries']],'source_file_universe')
    return sorted(names)


def read_source(root,manifest,budget):
    inventory(root,manifest)
    bodies={x['relative_path']:read_verified(Path(root)/x['relative_path'],x,budget) for x in manifest['entries']}
    inventory(root,manifest)
    return bodies


def stage(source_root,destination,budget=None):
    """Validate before creation; leave any interrupted fresh destination intact."""
    budget=Budget() if budget is None else budget
    manifest=load_manifest(budget);source_root=absolute(source_root);destination=absolute(destination)
    need(not destination.exists(),'destination_already_exists')
    need(destination.parent.is_dir(),'destination_parent_missing')
    need(destination!=source_root and source_root not in destination.parents and destination not in source_root.parents,
         'source_destination_overlap')
    bodies=read_source(source_root,manifest,budget)
    destination.mkdir(mode=0o700)
    for name in ROOTS:(destination/name).mkdir(mode=0o700)
    for entry in manifest['entries']:
        target=destination/entry['relative_path']
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as stream:
            stream.write(bodies[entry['relative_path']]);stream.flush();os.fsync(stream.fileno())
    inventory(destination,manifest)
    for entry in manifest['entries']:read_verified(destination/entry['relative_path'],entry,budget)
    return {'schema':'nider_private_source_kit_receipt_v1','source_root':str(source_root),'destination':str(destination),
            'manifest_sha256':MANIFEST_SHA256,'files':manifest['entries'],'file_count':27,'source_bytes':317150,
            'preserved_bytes':True,'no_content_imported_or_executed':True,'source_read_accounting':budget.report(),
            'scope':'Source transport only; no platform, runtime, rights or scientific qualification.'}


def main():
    os.umask(0o077);need(len(sys.argv)==3,'explicit_source_root_and_fresh_destination_required')
    print(encoded(stage(sys.argv[1],sys.argv[2])).decode(),end='')


if __name__=='__main__':main()
