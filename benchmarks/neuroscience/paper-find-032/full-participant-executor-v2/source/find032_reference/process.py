"""Concrete reference-only NativeOwner composition; no nominal lifecycle receipt."""
from dataclasses import dataclass,field
import os
from pathlib import Path
import selectors
import stat
import time
from find032_runtime.native_owner import NativeOwner,OwnedSelector,drain_original_streams
from find032_runtime.n071_linux.filesystem import Directory,FilePin,capture
from find032_runtime.outer import _capture_absolute,_publish,encoded
from .schema import need
from .files import directory_identity


@dataclass(eq=False)
class OwnedExecution:
    owner:object
    role:str
    directory:object=None
    child:object=None
    source_captures:list=field(default_factory=list)
    publications:list=field(default_factory=list)
    closed:bool=False
    directory_identities:dict=field(default_factory=dict)

    def require_closed(self):
        p,c=self.owner,self.child
        need(type(p)is NativeOwner and p.owner_pid==os.getpid() and p.first is None and
             p.owner.closed and not p.owner.custody.unknown and self.closed and c in p.children,
             'same actual original native owner after finish')
        need(c.waited and type(c.exit_code)is int and c.exit_code==0 and c.activated and
             not c.kill_sent and c.streams_closed and c.stream_eof=={'stdout','stderr'} and
             c.group_absence_observed and c.group.closed and c.group.final is not None and
             not c.group.final.populated and c.group.final.oom_kills==0 and all(g.closed and
             g.final is not None and g.final.oom_kills==0 for g in p.groups),
             'natural zero, two EOFs, actual group/descendant/FD closure')
        return self


class ProcessFailure(RuntimeError):
    def __init__(self,execution):
        self.execution=execution;self.first=execution.owner.first
        super().__init__('reference native process failed; original owners and prefixes retained')


def observe(parent,child,end):
    selector=None
    try:
        selector=OwnedSelector(parent)
        for name,handle in (('stdout',child.out_read),('stderr',child.err_read)):
            selector.register(handle.fd,selectors.EVENT_READ,name)
        parent.activate(child)
        while True:
            need(time.monotonic()<end,'original reference command cutoff')
            child.poll()
            if child.waited and child.exit_code!=0:raise RuntimeError('reference command nonzero')
            if child.waited and child.stream_eof=={'stdout','stderr'}:break
            for key,_ in selector.select(min(.05,max(0,end-time.monotonic()))):
                child.read_stream(key.data)
                if key.data in child.stream_eof:selector.unregister(key.fileobj)
            parent.tick()
        # Must precede cleanup kill; a living escaped descendant is a failed run.
        need(not child.group.sample(cleanup=True).populated,'naturally empty reference descendant tree')
    except BaseException as error:parent.fail(error,'reference command observation')
    finally:
        if selector is not None:
            try:selector.close()
            except BaseException as error:parent.fail(error,'reference selector close')


def run_owned(cfg,source_root,source_pins,request,request_pin):
    """The one real fixed scientific CLI child, with no nested owner/registry."""
    need(os.uname().sysname=='Linux' and os.geteuid()==0,'Linux root actual native owner')
    t=cfg['times'];end=t['child_end'];cleanup=t['cleanup_end'];final=t['owner_end']
    p=NativeOwner(cfg['host_selection'],t['origin'],final);result=OwnedExecution(p,'worker')
    directory=child=None
    try:
        need(time.monotonic()<end,'live original child admission')
        need(type(source_pins)is dict and 1<=len(source_pins)<=256 and
             sum(v['bytes'] for v in source_pins.values())<=4194304,'fixed complete source capture ceiling')
        src=Directory.open_absolute(p.owner,p.capacity,str(source_root))
        try:
            for name,selected in sorted(source_pins.items()):
                p.tick()
                result.source_captures.append(capture(src,FilePin(name,selected['bytes'],selected['sha256'],selected['mode'])))
        finally:src.fd.close()
        for name,selected in ((cfg['python'],cfg['python_pin']),(request,request_pin),
                              (cfg['input_manifest'],cfg['input_manifest_pin'])):
            result.source_captures.append(_capture_absolute(p,name,selected))
        base=Directory.open_absolute(p.owner,p.capacity,cfg['protected_parent'])
        try:
            result.directory_identities['parent']=directory_identity(base.fd.require_live())
            directory=base.child(cfg['run_name'],create=True)
        finally:base.fd.close()
        result.directory=directory.absolute
        result.directory_identities['run']=directory_identity(directory.fd.require_live())
        s=os.fstat(directory.fd.require_live())
        need(s.st_uid==0 and stat.S_IMODE(s.st_mode)==0o700,'fresh private owner root')
        out=directory.child('outputs',create=True)
        result.directory_identities['outputs']=directory_identity(out.fd.require_live());out.fd.close()
        for name in ('matplotlib','tmp','home'):
            temporary=directory.child(name,create=True);temporary.fd.close()
        cache=directory.child('bytecode-cache',create=True)
        try:
            os.fchmod(cache.fd.require_live(),0o550)
            need(not os.listdir(cache.fd.require_live()),'fresh empty readonly source cache')
            cache_path=cache.absolute
        finally:cache.fd.close()
        manifest={'schema':'find032_reference_captured_sources_v1','root':str(source_root),'files':source_pins}
        desc=_publish(p,directory,'SOURCE_CAPTURE.json',encoded(manifest),result)
        bootstrap=sum(v['bytes'] for v in source_pins.values())+desc['bytes']+request_pin['bytes']
        token=p.capacity.reserve('read_bytes',bootstrap,'complete reference child source/request recapture')
        p.capacity.settle(token,token.capacity)
        # Explicit scientific logical/output ownership is selected in the request;
        # it is not inferred from these ordinary source counters or cgroup memory.
        p.prepare()
        argv=[cfg['python'],'-I','-S','-B','-X','pycache_prefix='+cache_path,
              str(Path(source_root)/'find032_reference/entry.py'),'--mode','worker',
              '--request',request,'--request-bytes',str(request_pin['bytes']),
              '--request-sha256',request_pin['sha256'],'--request-mode',str(request_pin['mode']),
              '--source-manifest',desc['path'],'--source-manifest-bytes',str(desc['bytes']),
              '--source-manifest-sha256',desc['sha256'],'--original-endpoint',str(end)]
        env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8',
             'HOME':str(Path(directory.absolute)/'home'),'TMPDIR':str(Path(directory.absolute)/'tmp'),
             'R_USER':str(Path(directory.absolute)/'home'),'XDG_CACHE_HOME':str(Path(directory.absolute)/'home'),
             'MPLBACKEND':'Agg','MPLCONFIGDIR':str(Path(directory.absolute)/'matplotlib'),
             'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1',
             'NUMEXPR_NUM_THREADS':'1','PYTHONHASHSEED':str(cfg['fixed_seed'])}
        env.update(cfg['runtime_environment'])
        # Hash seed is explicit environment provenance; -I makes CPython ignore it.
        # Numerical fixed_seed behavior remains exactly the unchanged study source.
        child=p.spawn(argv,env,p.controller_group,end);result.child=child
        observe(p,child,end)
    except BaseException as error:
        if p.owner.custody.first is not None:p.fail(p.owner.custody.first,'original resource acquisition')
        p.fail(error,'reference owned command')
    finally:
        if child is None and p.children:child=p.children[0];result.child=child
        if p.controller_group is not None:
            try:p.close_group(p.controller_group,cleanup)
            except BaseException as error:p.fail(error,'reference controller cgroup retirement')
        if child is not None:
            for name,operation in (('wait',lambda:child.retire(cleanup)),
                                   ('drain',lambda:drain_original_streams(child,cleanup)),
                                   ('streams',child.close_streams)):
                try:operation()
                except BaseException as error:p.fail(error,'reference '+name)
        if p.recovery_group is not None:
            try:p.close_group(p.recovery_group,final)
            except BaseException as error:p.fail(error,'unused selected recovery group retirement')
        # This is explicitly pre-retirement evidence, never reference authority.
        if directory is not None:
            if child is not None:
                for stream in ('stdout','stderr'):
                    try:_publish(p,directory,stream+'.bin',bytes(getattr(child,stream)),result)
                    except BaseException as error:p.fail(error,'original '+stream+' publication')
            try:
                _publish(p,directory,'OWNER_PENDING.json',encoded({
                    'schema':'FIND032_REFERENCE_OWNER_PENDING_V1','role':'worker',
                    'child':None if child is None else child.projection(),
                    'errors':[{'stage':s,'type':type(e).__name__} for s,e in p.errors],
                    'normal':p.capacity.report(),'recovery':p.recovery_capacity.report(),
                    'final_owner_retirement_pending':True,'reference_support_admitted':False}),result)
            except BaseException as error:p.fail(error,'pending original owner publication')
        try:p.finish()
        except BaseException as error:
            if p.first is None:p.fail(error,'final original owner retirement')
    if p.first is None:
        try:
            p.tick();need(time.monotonic()<final,'original final owner deadline')
            result.closed=True;result.require_closed()
        except BaseException as error:result.closed=False;p.fail(error,'actual final reference closure')
    if p.first is not None:raise ProcessFailure(result) from p.first
    return result
