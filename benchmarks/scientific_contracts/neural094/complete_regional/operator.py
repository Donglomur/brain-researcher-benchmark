"""Inactive NEURAL-094 source inspector. Never imports benchmark modules.

The manifest digest and positive byte/time allowances are trusted operator
operands. Verification authenticates source bytes, not scientific data, external
authoring evidence, process containment or permission to execute the programme.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import time


class Refusal(ValueError):
    pass


def need(ok,why):
    if not ok:
        raise Refusal(why)


def pin(body):
    return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}


def decode(body):
    def pairs(rows):
        result={}
        for key,value in rows:
            need(key not in result,'Duplicate metadata key')
            result[key]=value
        return result
    return json.loads(body,object_pairs_hook=pairs,
        parse_constant=lambda value:need(False,'Nonfinite metadata'))


class Budget:
    def __init__(self,read_bytes,write_bytes,seconds):
        need(type(read_bytes) is int and read_bytes>0 and type(write_bytes) is int and write_bytes>0,
             'Explicit positive source-read/output byte allowances')
        need(type(seconds) in (int,float) and math.isfinite(seconds) and seconds>0,
             'Explicit positive monotonic deadline')
        self.read_limit=read_bytes;self.write_limit=write_bytes
        self.read_bytes=0;self.write_bytes=0;self.end=time.monotonic()+seconds
    def charge(self,kind,count):
        need(time.monotonic()<self.end,'Inspection deadline')
        need(kind in ('read','write') and type(count) is int and count>=0,'Typed byte charge')
        field=kind+'_bytes';setattr(self,field,getattr(self,field)+count)
        need(getattr(self,field)<=getattr(self,kind+'_limit'),'Inspection '+kind+' allowance exhausted')


def relative(name):
    need(type(name) is str and name and '\\' not in name and '\x00' not in name
         and not PurePosixPath(name).is_absolute()
         and all(p not in ('','.','..') for p in name.split('/')),'Safe source path')
    return name


def descriptor(row):
    need(type(row) is dict and set(row)=={'bytes','sha256'}
         and type(row['bytes']) is int and 0<=row['bytes']<=1048576
         and type(row['sha256']) is str and len(row['sha256'])==64
         and all(c in '0123456789abcdef' for c in row['sha256']),'Exact bounded source pin')


def read(root,name,expected,budget):
    descriptor(expected);target=root/relative(name)
    need(not any(p.is_symlink() for p in (target,*target.parents)),'No linked source ancestry')
    budget.charge('read',expected['bytes']+1)
    fd=os.open(target,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        first=os.fstat(fd)
        need(stat.S_ISREG(first.st_mode) and first.st_nlink==1 and first.st_size==expected['bytes'],
             'Ordinary exact source member')
        with os.fdopen(fd,'rb',closefd=False) as stream:body=stream.read(expected['bytes']+1)
        after=os.fstat(fd);named=target.lstat()
        need(all(getattr(first,k)==getattr(after,k)==getattr(named,k) for k in
             ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')),
             'Source file/name remained stable')
    finally:os.close(fd)
    need(pin(body)==expected,'Authenticated source bytes')
    return body


def inspect(root,manifest_pin,*,budget):
    """Read only the complete fixed source package. No source module imports."""
    root=Path(root)
    need(root.is_absolute() and root.is_dir() and not root.is_symlink(),'Absolute ordinary package root')
    raw=read(root,'SOURCE_MANIFEST.json',manifest_pin,budget)
    manifest=decode(raw)
    need(type(manifest) is dict and set(manifest)=={'schema','assignment','files','runtime_inventory',
         'source_origin','scientific_scope','execution_authority','scientific_qualification'}
         and manifest['schema']=='neural094_installed_complete_regional_source_v1'
         and manifest['assignment']=='NEURAL-094'
         and manifest['execution_authority'] is False and manifest['scientific_qualification'] is False,
         'Exact inactive source manifest')
    files=manifest['files']
    need(type(files) is dict and len(files)==34 and 'SOURCE_MANIFEST.json' not in files
         and len({n.casefold() for n in files})==len(files),'Complete 34 payloads plus source manifest')
    actual=[]
    for folder,dirs,names in os.walk(root,followlinks=False):
        need(not any(Path(folder,d).is_symlink() for d in dirs),'No linked package directory')
        actual.extend(str(Path(folder,n).relative_to(root)) for n in names)
    need(len(actual)==35 and set(actual)=={'SOURCE_MANIFEST.json',*files},'No missing or extra source body')
    captured={name:read(root,name,row,budget) for name,row in files.items()}
    need(manifest['runtime_inventory']==files['RUNTIME_INVENTORY.json'],'Exact runtime-inventory binding')
    inventory=decode(captured['RUNTIME_INVENTORY.json'])
    need(inventory['schema']=='neural094_complete_runtime_source_inventory_v1'
         and inventory['execution_authority'] is False and inventory['scientific_qualification'] is False
         and type(inventory['files']) is list and len(inventory['files'])==29,'Complete accepted runtime source')
    selected={row['path']:{k:row[k] for k in ('bytes','sha256')} for row in inventory['files']}
    need(len(selected)==29 and set(selected)=={n for n in files if n.startswith('source/')}
         and all(files[n]==row for n,row in selected.items())
         and type(inventory['bytes']) is int and inventory['bytes']==sum(row['bytes'] for row in selected.values()),
         'All runtime source bodies joined without importing them')
    need(manifest['scientific_scope']=={'sessions':39,'mice':10,'literal_regions':73,'pairs':2628,'seeds':5},
         'Unchanged complete scientific scope')
    output={'schema':'neural094_installed_complete_regional_inspection_v1','assignment':'NEURAL-094',
        'state':'INSTALLED_SOURCE_ONLY_INACTIVE','source_manifest':manifest_pin,
        'source_members':29,'mounted_members_if_materialized':33,'package_members':35,
        'source_bytes':inventory['bytes'],'scientific_scope':manifest['scientific_scope'],
        'benchmark_modules_imported':False,'authentic_inputs_opened':False,
        'execution_authority':False,'scientific_qualification':False,
        'registration_delta':0,'qualification_delta':0}
    body=json.dumps(output,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n'
    budget.charge('write',len(body))
    return body


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('inspect',))
    parser.add_argument('--source-bytes',type=int,required=True)
    parser.add_argument('--source-sha256',required=True)
    parser.add_argument('--read-bytes',type=int,required=True)
    parser.add_argument('--write-bytes',type=int,required=True)
    parser.add_argument('--seconds',type=float,required=True)
    args=parser.parse_args(argv)
    budget=Budget(args.read_bytes,args.write_bytes,args.seconds)
    body=inspect(Path(__file__).absolute().parent,
        {'bytes':args.source_bytes,'sha256':args.source_sha256},budget=budget)
    need(sys.stdout.buffer.write(body)==len(body),'Complete inspection output')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
