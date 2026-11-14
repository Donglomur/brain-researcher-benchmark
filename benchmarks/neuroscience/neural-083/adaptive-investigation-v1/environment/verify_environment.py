"""Future selected dependency check only; never fits or opens benchmark data."""
import argparse
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import stat
import sys


def need(value,message):
    if not value:raise RuntimeError(message)


def capture(path):
    need(path.is_absolute() and not any(x.is_symlink() for x in (path,*path.parents)),
         'unlinked absolute lock')
    before=path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<before.st_size<=262144,'bounded ordinary lock')
    stamp=lambda x:(x.st_dev,x.st_ino,x.st_mode,x.st_nlink,x.st_size,x.st_mtime_ns,x.st_ctime_ns)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    first=None;secondary=None;parts=[]
    try:
        need(stamp(before)==stamp(os.fstat(fd)),'opened lock identity');left=before.st_size
        while left:
            b=os.read(fd,min(65536,left));need(bool(b),'short lock');parts.append(b);left-=len(b)
        need(not os.read(fd,1),'lock grew')
        need(stamp(before)==stamp(os.fstat(fd))==stamp(path.lstat()),'stable lock identity')
    except BaseException as error:first=error
    finally:
        try:os.close(fd)
        except BaseException as error:secondary=error
    if first is not None:
        if secondary is not None:first.add_note('Secondary lock close: '+repr(secondary))
        raise first
    if secondary is not None:raise secondary
    return b''.join(parts)


def main():
    parser=argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('--lock',type=Path,required=True)
    parser.add_argument('--bootstrap',action='store_true')
    args=parser.parse_args();raw=capture(args.lock.absolute());lock=json.loads(raw)
    need(lock['schema']=='neural083_environment_v1' and lock['platform']=='linux/amd64','selected environment lock')
    need(platform.system()=='Linux' and platform.machine()=='x86_64' and
         platform.python_implementation()=='CPython' and platform.python_version()==lock['python']=='3.11.11',
         'actual prospective Linux amd64 CPython3.11.11')
    need(sys.flags.isolated and sys.dont_write_bytecode,'actual isolated no-bytecode invocation')
    report={'schema':'neural083_dependency_check_v1','python':platform.python_version(),
            'executable':sys.executable,'lock':{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},
            'bootstrap_only':args.bootstrap,'native_qualification':False,'scientific_qualification':False,
            'data_opened':False,'fits_performed':0,'model_server_qualified':False}
    if not args.bootstrap:
        need(not sys.flags.no_site,'actual preparation child site discovery is enabled')
        normalize=lambda n:n.lower().replace('_','-').replace('.','-')
        expected={normalize(r['name']):r['version'] for r in lock['python_artifacts']}
        rows=[(normalize(d.metadata['Name']),d.version) for d in importlib.metadata.distributions()]
        need(len(rows)==len(dict(rows)) and dict(rows)==expected and len(expected)==8,'exact eight distributions')
        for name in ('numpy','scipy','scipy.io','scipy.signal','scipy.linalg','sklearn',
                     'sklearn.discriminant_analysis','sklearn.linear_model','joblib','threadpoolctl'):
            importlib.import_module(name)
        report['distributions']=dict(rows)
    print(json.dumps(report,sort_keys=True))


if __name__=='__main__':main()
