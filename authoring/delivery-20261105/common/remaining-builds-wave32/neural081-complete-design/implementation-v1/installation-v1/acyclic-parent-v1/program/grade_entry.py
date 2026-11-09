"""Literal isolated protected G5 entry; complete pretarget replay before labels."""
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
    start_grade(module,request,
        {'path':a.request,'bytes':int(a.request_bytes),'sha256':a.request_sha256},
        {'path':a.bootstrap,'bytes':int(a.bootstrap_bytes),'sha256':a.bootstrap_sha256},
        origin=origin,deadline=deadline,read_cap=read_cap,write_cap=write_cap,
        initial_read_bytes=used,entry_path=str(Path(__file__)),entry_bytes=int(a.entry_bytes))


def start_grade(b,raw_request,request_desc,bootstrap_desc,**selected):
    import sys,importlib.util
    budget=b.WorkerBudget(selected['origin'],selected['deadline'],selected['read_cap'],selected['write_cap'],selected['initial_read_bytes'])
    request=b.parse(raw_request)
    b.exact(request,('schema','job','source','payload','output_root','allowed','protected','source_manifest','clock','worker_io'))
    b.need(request['schema']=='neural081_grader_worker_request_v1' and request['job']=='G5/complete' and request['clock']=={'origin':budget.origin,'deadline':budget.end} and request['worker_io']==budget.limits,'original isolated G5 source/request/clock')
    manifest=b.parse(b.capture(request['source_manifest'],budget));b.exact(manifest,('schema','entry','bootstrap','modules','dependency_qualification','installed_versions'))
    b.need(manifest['schema']=='neural081_grader_source_manifest_v1' and manifest['bootstrap']==bootstrap_desc and manifest['entry']['path']==selected['entry_path'] and manifest['entry']['bytes']==selected['entry_bytes'],'literal captured grader entry')
    b.capture(manifest['entry'],budget);b.capture(manifest['bootstrap'],budget)
    required=frozenset(('common','protocol','arrays','custody','outputs','metrics','grading','closure','schedule','runtime','host_observation','candidate_runner','transport','transport.common','transport.provider','transport.process','authority'))
    sources=b.authenticate_modules(manifest['modules'],budget,required,(selected['entry_path'],bootstrap_desc['path']))
    qualified=b.parse(b.capture(manifest['dependency_qualification'],budget))
    b.exact(qualified,('schema','status','source','source_members','installed_versions','image_identity','independent_issuer','protected_custody'))
    b.need(qualified['schema']=='neural081_grader_environment_qualification_v1' and qualified['status']=='qualified' and qualified['source']==request['source'] and qualified['installed_versions']==manifest['installed_versions'] and qualified['source_members']==[manifest['entry'],manifest['bootstrap'],*[r['source']for r in manifest['modules']]],'separate acyclic exact protected grading qualification')
    for name in ('image_identity','independent_issuer','protected_custody'):b.exact(qualified[name],('path','bytes','sha256'))
    class CapturedPackages(b.CapturedModules):
        def find_spec(self,fullname,path=None,target=None):
            if fullname in self.sources:return importlib.util.spec_from_loader(fullname,self,origin=self.sources[fullname][0],is_package=fullname=='transport')
            return None
    sys.meta_path.insert(0,CapturedPackages(sources))
    import common as c
    from custody import Access
    import grading,outputs
    b.need(manifest['installed_versions']=={'python':sys.version.split()[0]},'exact selected trusted Python version')
    output=c.absolute(request['output_root']);c.need(output.is_dir() and not any(x.is_symlink()for x in(output,*output.parents)),'selected fresh trusted G5 output')
    access=Access('G5',request['allowed'],request['protected'],budget)
    result=grading.execute(request['payload'],access,request['source'],output)
    outputs.finish(output,result,budget,request_desc,request['source'],request['job']);budget.check_clock()


if __name__=='__main__':main()
