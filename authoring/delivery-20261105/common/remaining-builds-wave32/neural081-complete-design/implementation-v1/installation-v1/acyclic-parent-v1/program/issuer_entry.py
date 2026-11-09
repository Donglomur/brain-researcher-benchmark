"""Literal isolated persistent issuer entry; source capture before restrictions."""
import argparse
import hashlib
import os
import stat
import time
import types
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    for name in ('request', 'request-bytes', 'request-sha256', 'bootstrap', 'bootstrap-bytes',
                 'bootstrap-sha256', 'read-cap', 'write-cap', 'origin', 'deadline', 'entry-bytes'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--issuer-fd',required=True)
    a = parser.parse_args()
    origin, deadline = float(a.origin), float(a.deadline)
    read_cap, write_cap = int(a.read_cap), int(a.write_cap)
    used = int(a.entry_bytes)  # Interpreter source demand, separate from later authentication.
    if not (0 <= origin < time.monotonic() < deadline and read_cap > 0 and write_cap > 0):
        raise ValueError('invalid original worker bounds')

    def capture(path, size, digest):
        nonlocal used
        size = int(size)
        if size < 1 or size > 16 * 2**20 or used + size + 1 > read_cap:
            raise ValueError('bootstrap capture reservation')
        used += size + 1
        p = Path(path)
        if not p.is_absolute() or str(p) != path or any(x.is_symlink() for x in (p, *p.parents)):
            raise ValueError('ordinary exact bootstrap path')
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            first = os.fstat(fd)
            if not stat.S_ISREG(first.st_mode) or first.st_nlink != 1 or first.st_size != size:
                raise ValueError('bootstrap extent')
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                raw = stream.read(size + 1)
            last, named = os.fstat(fd), p.lstat()
            fields = ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
            if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest or any(
                    getattr(first, k) != getattr(last, k) or getattr(first, k) != getattr(named, k) for k in fields):
                raise ValueError('bootstrap complete source identity')
        finally:
            os.close(fd)
        if time.monotonic() >= deadline:
            raise ValueError('original deadline exceeded')
        return raw

    boot = capture(a.bootstrap, a.bootstrap_bytes, a.bootstrap_sha256)
    request = capture(a.request, a.request_bytes, a.request_sha256)
    module = types.ModuleType('worker_bootstrap')
    module.__file__ = a.bootstrap
    exec(compile(boot, a.bootstrap, 'exec'), module.__dict__)
    b=module;budget=b.WorkerBudget(origin,deadline,read_cap,write_cap,used)
    envelope=b.parse(request)
    b.exact(envelope,('schema','source','config','source_manifest'))
    b.need(envelope['schema']=='neural081_issuer_entry_request_v1','source-owned issuer entry')
    manifest=b.parse(b.capture(envelope['source_manifest'],budget))
    b.exact(manifest,('schema','entry','bootstrap','modules','dependency_qualification','installed_versions'))
    b.need(manifest['schema']=='neural081_issuer_source_manifest_v1' and manifest['entry']['path']==str(Path(__file__)) and manifest['entry']['bytes']==int(a.entry_bytes) and manifest['bootstrap']=={'path':a.bootstrap,'bytes':int(a.bootstrap_bytes),'sha256':a.bootstrap_sha256},'actual issuer source/bootstrap')
    b.capture(manifest['entry'],budget);b.capture(manifest['bootstrap'],budget)
    required=frozenset(('common','protocol','arrays','fd_protocol','projection_engine','issuer_sandbox','issuer_worker'))
    sources=b.authenticate_modules(manifest['modules'],budget,required,(str(Path(__file__)),a.bootstrap))
    qualification=b.parse(b.capture(manifest['dependency_qualification'],budget))
    b.exact(qualification,('schema','status','source','source_members','installed_versions','physical_namespace','scm_rights','independent_issuer'))
    b.need(qualification['schema']=='neural081_projection_issuer_qualification_v1' and qualification['status']=='qualified' and qualification['source']==envelope['source'] and qualification['source_members']==[manifest['entry'],manifest['bootstrap'],*[r['source']for r in manifest['modules']]] and qualification['installed_versions']==manifest['installed_versions'],'exact independently qualified persistent issuer')
    for name in ('physical_namespace','scm_rights','independent_issuer'):b.exact(qualification[name],('path','bytes','sha256'))
    config=envelope['config']
    b.need(config['origin']==origin and config['origin']+config['limits']['seconds']==deadline and config['limits']['read_bytes']==read_cap and config['limits']['write_bytes']==write_cap,'original complete issuer clock and reserved IO')
    import sys
    sys.meta_path.insert(0,b.CapturedModules(sources))
    import issuer_worker
    import numpy
    b.need(manifest['installed_versions']=={'numpy':numpy.__version__},'selected issuer numerical version')
    issuer_worker.serve(int(a.issuer_fd),config,envelope['source'],initial_read_bytes=budget.used['read_bytes'])


if __name__ == '__main__':
    main()
