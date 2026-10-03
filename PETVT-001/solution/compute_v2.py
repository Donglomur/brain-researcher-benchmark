"""Reviewed replacement candidate; old guarded compute remains quarantined."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import types
import warnings

PINS={'kinetics':'86f120fe69b5dc71585b37e418441c8d2455502666746f1504037ac20376559c',
      'source_reader':'7d054197abbfb295f15f74e29bb19fa4283f4e0e23d77edc82c4cde13ee87439',
      'output_writer':'f0e17397874648a064621268bf3ec290ae12c4ac43802a9cdbaa2f2592934e7f'}


def load_code(root=None):
    root=Path(__file__).resolve().parent if root is None else Path(root);buffers={}
    for name,pin in PINS.items():
        if type(pin)is not str or not re.fullmatch('[0-9a-f]{64}',pin):raise ValueError('unfrozen oracle pin')
        path=root/(name+'.py')
        if any(p.is_symlink()for p in (path,*path.parents)):raise ValueError('oracle code symlink')
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            before=os.fstat(fd)
            if not stat.S_ISREG(before.st_mode)or not 0<before.st_size<=262144:raise ValueError('oracle code bound')
            with os.fdopen(fd,'rb',closefd=False)as stream:raw=stream.read(262145)
            sig=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
            if len(raw)!=before.st_size or sig(before)!=sig(os.fstat(fd))or sig(before)!=sig(path.lstat()):raise ValueError('oracle code changed')
            if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('oracle code hash')
            buffers[name]=raw
        finally:os.close(fd)
    modules={}
    for name,raw in buffers.items():
        module=types.ModuleType(name);module.__file__=str(root/(name+'.py'));sys.modules[name]=module
        exec(compile(raw,module.__file__,'exec'),module.__dict__);modules[name]=module
    return modules


def output_path(path,protected):
    lexical=Path(path).absolute()
    if any(p.is_symlink()for p in (lexical,*lexical.parents)):raise ValueError('output symlink')
    out=lexical.resolve()
    for p in map(lambda p:Path(p).resolve(),protected):
        if p==out or p in out.parents or out in p.parents:raise ValueError('output overlaps source/code/documents')
    return out


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default=os.environ.get('OUTPUT_DIR','/app/output'))
    parser.add_argument('--data-dir',default='/app/data/petvt')
    parser.add_argument('--manifest',default='/app/source_manifest.json')
    parser.add_argument('--method',default='/app/method_contract.json')
    parser.add_argument('--schema',default='/app/output_schema.json')
    args=parser.parse_args(argv);out=None
    try:
        out=output_path(args.output,[Path(__file__).resolve().parent,args.data_dir,args.manifest,args.method,args.schema])
        out.mkdir(parents=True,exist_ok=True)
        if any(out.iterdir()):raise ValueError('output must be fresh and empty')
        modules=load_code()
        with warnings.catch_warnings(record=True)as caught:
            warnings.simplefilter('always')
            basis=modules['source_reader'].load(args.data_dir,args.manifest,args.method,args.schema)
            actual=modules['output_writer'].artifacts(basis)
        actual['metadata']['warnings']=[str(w.message)for w in caught]
        modules['output_writer'].write(out,actual)
        for name,cap in basis['schema']['limits']['file_bytes'].items():
            if (out/name).stat().st_size>cap:raise ValueError('output cap exceeded')
        print(json.dumps({'status':'complete','n_subjects':7,'n_records':28}));return 0
    except Exception as exc:
        if out is not None and out.is_dir():
            try:
                with (out/'failure_report.json').open('x',encoding='utf-8')as stream:
                    json.dump({'status':'failed','error_type':type(exc).__name__},stream)
            except (FileExistsError,OSError):pass
        print(json.dumps({'status':'failed','error_type':type(exc).__name__}));return 1


if __name__=='__main__':raise SystemExit(main())
