"""Trusted G0 literal isolated entry; ten physical workers only."""
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
    start_preparation(module, request,
        {'path': a.request, 'bytes': int(a.request_bytes), 'sha256': a.request_sha256},
        {'path': a.bootstrap, 'bytes': int(a.bootstrap_bytes), 'sha256': a.bootstrap_sha256},
        origin=origin, deadline=deadline, read_cap=read_cap, write_cap=write_cap,
        initial_read_bytes=used, entry_path=str(Path(__file__)), entry_bytes=int(a.entry_bytes))


def start_preparation(b, raw_request, request_desc, bootstrap_desc, **selected):
    import sys
    budget=b.WorkerBudget(selected['origin'],selected['deadline'],selected['read_cap'],selected['write_cap'],selected['initial_read_bytes'])
    request=b.parse(raw_request)
    b.exact(request,('schema','job','source','payload','output_root','allowed','protected','source_manifest','clock','worker_io'))
    b.need(request['schema']=='neural081_preparation_worker_request_v1' and request['clock']=={'origin':budget.origin,'deadline':budget.end} and request['worker_io']==budget.limits,'original trusted preparation clock/reservation')
    manifest=b.parse(b.capture(request['source_manifest'],budget))
    b.exact(manifest,('schema','entry','bootstrap','modules','dependency_qualification','installed_versions'))
    b.need(manifest['schema']=='neural081_preparation_source_manifest_v1' and manifest['bootstrap']==bootstrap_desc,'exact selected G0 source closure')
    b.need(manifest['entry']['path']==selected['entry_path'] and manifest['entry']['bytes']==selected['entry_bytes'],'literal isolated trusted preparer')
    b.capture(manifest['entry'],budget);b.capture(manifest['bootstrap'],budget)
    required=frozenset(('common','protocol','arrays','custody','outputs','preparation','preparation_worker'))
    sources=b.authenticate_modules(manifest['modules'],budget,required,(selected['entry_path'],bootstrap_desc['path']))
    qualification=b.parse(b.capture(manifest['dependency_qualification'],budget))
    b.exact(qualification,('schema','status','source','installed_versions','image_identity','independent_issuer','physical_io_enforcement','memory_enforcement','annotation_authority'))
    b.need(qualification['schema']=='neural081_preparation_environment_qualification_v1' and qualification['status']=='qualified' and qualification['source']==request['source'] and qualification['installed_versions']==manifest['installed_versions'],'independently selected original-format preparation environment')
    for name in ('image_identity','independent_issuer','physical_io_enforcement','memory_enforcement','annotation_authority'):b.exact(qualification[name],('path','bytes','sha256'))
    b.need(qualification['annotation_authority']==request['payload']['annotation_authority'],'same exact physical annotation source qualification')
    b.exact(manifest['installed_versions'],('numpy','mne'))
    for version in manifest['installed_versions'].values():b.need(type(version)is str and version,'selected qualified package version')
    sys.meta_path.insert(0,b.CapturedModules(sources))
    import common as c
    from custody import Access
    import preparation_worker,outputs
    c.need(c.typed_equal(request['payload']['environment'],{**manifest['installed_versions'],'source_qualified':True,'annotation_qualified':True}),'trusted preparation environment before imports/data')
    output=c.absolute(request['output_root']);c.need(output.is_dir() and not any(x.is_symlink() for x in(output,*output.parents)),'fresh selected preparer workspace')
    access=Access('G0',request['allowed'],request['protected'],budget)
    result=preparation_worker.execute(request['payload'],access,request['source'],output)
    outputs.finish(output,result,budget,request_desc,request['source'],request['job'])
    budget.check_clock()


if __name__ == '__main__':
    main()
