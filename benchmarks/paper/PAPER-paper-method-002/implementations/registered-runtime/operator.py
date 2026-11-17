"""Inactive Jaxley source inspection and source-bound future protected operator.

No qualification/input/resource issuer lives here. Source bootstrap costs are
ordinary Python I/O, not authenticated native whole-controller observations.
"""
import argparse
import contextlib
import hashlib
import importlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys

TASK='PAPER-paper-method-002'
LOCK_PIN={'bytes': 24659, 'sha256': 'dd97d36e59482e7984792698e3c001f3d43da8a995a78823c78540cf8dc4bc0b'}  # Bound by composition before placement; no self-hash cycle.
LAST_ERRORS=[]
ONE=1048576
TOTAL=4194304

def require(ok,message):
    if not ok:raise ValueError(message)

def pin(body):return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}

def _identity(s):return (s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)

def read_regular(root,relative,expected):
    """Nonblocking descriptor walk, complete bound, no-follow and raw-first close."""
    require(type(relative)is str and relative and not relative.startswith('/'),'relative source path')
    parts=relative.split('/');require(all(x not in ('','.','..')for x in parts),'literal source components')
    require(type(expected)is dict and set(expected)=={'bytes','sha256'} and type(expected['bytes'])is int and 0<expected['bytes']<=ONE,'ordinary exact member bound')
    fds=[];first=None;body=None
    try:
        # Absolute roots may have conventional symlinked ancestors; the source
        # root itself and every source member ancestor are opened no-follow.
        fd=os.open(os.fspath(root),os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_NONBLOCK);fds.append(fd)
        for part in parts[:-1]:
            fd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd);fds.append(fd)
        fd=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd);fds.append(fd)
        before=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and before.st_size==expected['bytes'],'opened member must be exact ordinary file')
        chunks=[];left=expected['bytes']
        while left:
            b=os.read(fd,left);require(bool(b),'short ordinary source');chunks.append(b);left-=len(b)
        require(not os.read(fd,1),'unexpected source suffix')
        require(_identity(before)==_identity(os.fstat(fd)),'source changed during capture')
        body=b''.join(chunks);require(pin(body)==expected,'source pin mismatch');body.decode('utf8')
    except BaseException as error:
        first=error;LAST_ERRORS.append(('read',error))
    finally:
        for fd in reversed(fds):
            try:os.close(fd)
            except BaseException as error:
                LAST_ERRORS.append(('close',error))
                if first is None:first=error
    if first is not None:raise first
    return body

def capture_source(root=None):
    root=Path(__file__).absolute().parent if root is None else Path(root)
    require(LOCK_PIN is not None,'unbound construction template')
    raw=read_regular(root,'CENTRAL_SOURCE_LOCK.json',LOCK_PIN);lock=json.loads(raw)
    require(lock['task_id']==TASK and len(lock['source'])==67,'complete selected source roster')
    rows=lock['files'];require(len({x['path']for x in rows})==len(rows),'unique whole source/context map')
    require(sum(x['bytes']for x in rows)+len(raw)<=TOTAL,'complete source bootstrap bound')
    bodies={}
    for row in rows:
        bodies[row['path']]=read_regular(root,row['path'],{k:row[k]for k in('bytes','sha256')})
    require(len(lock['scope']['groups'])==36 and lock['scope']['condition_family_jobs']==144,'complete family support')
    limits=json.loads(bodies['CURRENT_SCIENTIFIC_LIMITS.json'])
    require(len(limits['gates'])==21 and all(v is False for v in limits['gates'].values()) and limits['source_complete']is False,'unqualified source status')
    return root,lock,bodies

def inspect_source(root=None):
    _,lock,bodies=capture_source(root)
    return {'task_id':TASK,'status':'inactive_authenticated_source','source_roles':67,
            'source_bytes':sum(r['bytes']for r in lock['source']),'scope':lock['scope'],
            'gates':json.loads(bodies['CURRENT_SCIENTIFIC_LIMITS.json'])['gates'],
            'remaining':json.loads(bodies['CURRENT_SCIENTIFIC_LIMITS.json'])['remaining'],
            'source_complete':False,'runnable':False,'research_qualified':False,
            'run':None,'score':None,'native_authority_issued':False,
            'bootstrap_read_bytes':sum(len(x)for x in bodies.values())+LOCK_PIN['bytes'],
            'physical_native_bootstrap_accounting':'unmeasured; original whole-controller qualification remains required'}

class _CapturedSource(importlib.abc.MetaPathFinder,importlib.abc.Loader):
    def __init__(self,root,bodies):
        self.root=root;self.modules={};self.loaded={}
        for path,body in bodies.items():
            if not path.startswith('programme/')or not path.endswith('.py'):continue
            parts=list(PurePosixPath(path).relative_to('programme').with_suffix('').parts)
            package=parts[-1]=='__init__'
            if package:parts.pop()
            if parts and all(x.isidentifier()for x in parts):self.modules['.'.join(parts)]=(path,body,package)
        self.reserved={n.split('.')[0]for n in self.modules}
    def find_spec(self,fullname,path=None,target=None):
        if fullname in self.modules:
            p,b,pkg=self.modules[fullname]
            return importlib.util.spec_from_loader(fullname,self,origin=str(self.root/p),is_package=pkg)
        if fullname.split('.')[0]in self.reserved:raise ImportError('unselected source import '+fullname)
        return None
    def create_module(self,spec):return None
    def exec_module(self,module):
        p,b,pkg=self.modules[module.__name__];module.__file__=str(self.root/p)
        if pkg:module.__path__=[str((self.root/p).parent)]
        self.loaded[module.__name__]=module
        exec(compile(b,module.__file__,'exec'),module.__dict__)

@contextlib.contextmanager
def captured_modules(root,bodies):
    finder=_CapturedSource(root,bodies)
    require(not any(n.split('.')[0]in finder.reserved for n in sys.modules),'source namespace already loaded; use fresh interpreter')
    # Only captured names can satisfy any reserved import, before execution.
    sys.meta_path.insert(0,finder)
    try:yield finder
    finally:
        if finder in sys.meta_path:sys.meta_path.remove(finder)
        for name,module in finder.loaded.items():
            if sys.modules.get(name)is module:del sys.modules[name]

def _selected_tree(lock,selection):
    require(type(selection)is dict and selection.get('source_tree')==lock['source'],'selection must bind exact accepted67-role programme tree')
    require(selection.get('task_id')==TASK,'same canonical task')

def compile_selection(selection,*,root=None):
    """Actual complete compiler; metadata only, no input/read/native authority."""
    root,lock,bodies=capture_source(root);_selected_tree(lock,selection)
    with captured_modules(root,bodies):
        return importlib.import_module('scientific.campaign').compile_campaign(selection)

def run_scientific_sources(authority_root,receipt_path,receipt_pin,authority_limits,selection,global_limits,*,root=None):
    """Exact original owner/controller after source binding; prospective only.

This route does not call a substitute owner or supply a qualification receipt.
The original controller independently requires genuine protected FullAuthority,
complete144stage/source bindings and actual native observations; these are unissued.
"""
    root,lock,bodies=capture_source(root);_selected_tree(lock,selection)
    with captured_modules(root,bodies):
        return importlib.import_module('runtime.full_scientific_controller').run_scientific_sources(
            authority_root,receipt_path,receipt_pin,authority_limits,selection,global_limits)

def run_operator_configuration(configuration_root,configuration_path,configuration_bytes,configuration_sha256,*,root=None):
    """Call the accepted protected CLI after binding the selected source tree.

    The original CLI owns configuration descriptors and their cleanup. Its
    existing controller is retained; the one call boundary additionally checks
    that the admitted selection names the exact captured 67-role source tree.
    This API neither creates nor repairs external qualification evidence.
    """
    require(type(configuration_root)is str and configuration_root,'explicit configuration root')
    require(type(configuration_path)is str and configuration_path,'explicit configuration path')
    require(type(configuration_bytes)is int and configuration_bytes>0,'explicit complete configuration extent')
    require(type(configuration_sha256)is str and len(configuration_sha256)==64 and
            all(c in '0123456789abcdef'for c in configuration_sha256),'exact configuration hash')
    root,lock,bodies=capture_source(root)
    with captured_modules(root,bodies):
        entry=importlib.import_module('full_scientific_operator')
        original=entry.run_scientific_sources
        def bound(authority_root,receipt_path,receipt_pin,authority_limits,selection,global_limits):
            _selected_tree(lock,selection)
            return original(authority_root,receipt_path,receipt_pin,authority_limits,selection,global_limits)
        entry.run_scientific_sources=bound
        try:
            return entry.main([
                '--configuration-root='+configuration_root,
                '--configuration-path='+configuration_path,
                '--configuration-bytes='+str(configuration_bytes),
                '--configuration-sha256='+configuration_sha256])
        finally:entry.run_scientific_sources=original

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--inspect',action='store_true')
    mode.add_argument('--run',action='store_true')
    for name in ('root','path','bytes','sha256'):
        p.add_argument('--configuration-'+name,type=int if name=='bytes'else str)
    args=p.parse_args(argv)
    values=[getattr(args,'configuration_'+n)for n in ('root','path','bytes','sha256')]
    if args.inspect:
        require(all(v is None for v in values),'inspect accepts no configuration operands')
        result=inspect_source()
    else:
        require(all(v is not None for v in values),'run requires all exact configuration operands')
        result=run_operator_configuration(*values)
    print(json.dumps(result,sort_keys=True,indent=2));return result

if __name__=='__main__':main()
