"""Container entry for the selected original NEURAL-017 S03 projection only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import stat
import sys
import time
import types
import zlib

COMPONENT=Path(__file__).resolve().parents[2]
THREADS=('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','OMP_THREAD_LIMIT','MKL_NUM_THREADS',
         'NUMEXPR_NUM_THREADS','NUMBA_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS')


def bootstrap(path,expected_sha,cap):
    before=path.lstat()
    if not stat.S_ISREG(before.st_mode)or before.st_nlink!=1 or not 0<before.st_size<=cap:raise ValueError('Bounded bootstrap')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb')as f:body=f.read(cap+1);after=os.fstat(f.fileno())
    stamp=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    if stamp(before)!=stamp(after)or stamp(after)!=stamp(path.lstat())or len(body)!=before.st_size or hashlib.sha256(body).hexdigest()!=expected_sha:
        raise ValueError('Exact stable bootstrap identity')
    return body


def main():
    start=time.monotonic();os.umask(0o077)
    parser=argparse.ArgumentParser();parser.add_argument('--selection-sha256',required=True);args=parser.parse_args()
    raw=bootstrap(Path('/selection.json'),args.selection_sha256,65536);selected=json.loads(raw)
    core_pin=next(r for r in selected['component_files']if r['path']=='core.py')
    body=bootstrap(COMPONENT/'core.py',core_pin['sha256'],262144)
    if len(body)!=core_pin['bytes']:raise ValueError('Exact core extent')
    core=types.ModuleType('_n017_s03_core');core.__file__=str(COMPONENT/'core.py')
    exec(compile(body,core.__file__,'exec'),core.__dict__);selected=core.decode(raw)
    core.need(selected['schema']=='NLB017_owned_S03_selection_v1','Fixed S03 selection')
    core.need(sys.version_info[:3]==(3,12,8),'Selected Python3.12.8')
    core.need(os.getuid()==selected['uid']and os.getgid()==selected['gid']and os.getuid()>0,'Selected nonroot identity')
    core.need(all(os.environ.get(k)=='1'for k in THREADS),'One numerical thread')
    resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_FSIZE,(core.ARCHIVE_CAP,core.ARCHIVE_CAP))
    import numpy as np
    core.need(np.__version__=='2.2.6','Selected original shuffle NumPy2.2.6')
    sources=core.load_sources(COMPONENT,Path('/dependencies'))
    compiled=core.decode(core.snapshot(Path('/compilation.json'),selected['compilation'],65536))
    core.need(core.compilation(compiled)==selected['input_descriptors'],'Selected exact11input descriptors')
    result=core.run_projection(sources,compiled,Path('/inputs'),Path('/out'),selected['opaque_fingerprint'],start+140)
    runtime={'python':platform.python_version(),'numpy':np.__version__,'numpy_file':np.__file__,
        'python_executable':sys.executable,'zlib_runtime':zlib.ZLIB_RUNTIME_VERSION,
        'zlib_compile':zlib.ZLIB_VERSION,'binary_or_hermetic_provenance_qualification':False}
    result.update(selection_sha256=args.selection_sha256,runtime=runtime,
        compilation=selected['compilation'],source_bindings=core.BINDINGS_PIN,
        opaque_fingerprint=selected['opaque_fingerprint'],physical_fingerprint=selected['physical_fingerprint'])
    encoded=core.encode(result);core.need(len(encoded)<=2*2**20,'Bounded complete private S03 receipt')
    core.need(time.monotonic()<start+140,'Original worker deadline before receipt')
    fd=os.open('/out/S03_RECEIPT.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb')as f:
        core.need(f.write(encoded)==len(encoded),'Complete private receipt write');f.flush();os.fsync(f.fileno())
    response=core.encode({'schema':'NLB017_owned_S03_worker_result_v1','status':'all_original_S03_products_validated',
        'receipt':core.byte_pin(encoded),'products':result['products'],'support':result['support'],
        'runtime':runtime,'seed_generated':False,'participant_executed':False,'benchmark_ready':False})
    core.need(len(response)<=16384,'Bounded compact worker response')
    core.need(sys.stdout.buffer.write(response)==len(response),'Complete worker response')
    sys.stdout.buffer.flush();core.need(time.monotonic()<start+140,'Final worker drain within original deadline')


if __name__=='__main__':main()
