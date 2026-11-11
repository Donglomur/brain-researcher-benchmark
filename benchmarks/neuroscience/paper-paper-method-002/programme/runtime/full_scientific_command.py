"""Closed CPU full-source argv. Existing legacy sandbox command is unchanged."""
import os,sys
from .strict import Root,require
from .full_scientific_bindings import Failures

def command(binding,roots,job,driver_pin,clock):
    require(sys.platform=='linux','qualified Linux deployment required')
    require(binding['sandbox']=='bubblewrap_cgroup_v2'and binding['rootfs_immutable']is True,'qualified immutable dependency image')
    require(binding['network']is False and binding['executable_immutable_evidence'],'exact offline executable qualification')
    require(not binding['requires_gpu'],'CPU adapter cannot invent GPU isolation; GPU groups need the separately qualified native device launcher')
    require(set(roots)=={'rootfs','program','inputs','output'}and all(r.fd is not None for r in roots.values()),'original mount FDs')
    bwrap=binding['bwrap_path'];parent,leaf=os.path.split(bwrap)
    owner=Failures()
    try:
        binary=owner.own(Root(parent))
        binary.authenticate(leaf,{'bytes':binding['bwrap_bytes'],'sha256':binding['bwrap_sha256']},cap=binding['bwrap_bytes'],clock=clock)
    except BaseException as error:owner.catch(error)
    owner.close_all();owner.raise_first()
    argv=['/runtime/bin/python','-I','-B','/program/full_scientific_entry.py','/inputs/invocation.json','/output',
          str(job['metadata_limits']['invocation_bytes']),str(driver_pin['bytes'])]
    require(binding['argv']==argv,'fixed full-source bridge and explicit capacity operands')
    args=[bwrap,'--unshare-all','--new-session','--die-with-parent','--clearenv',
          '--ro-bind',f"/proc/self/fd/{roots['rootfs'].fd}",'/',
          '--ro-bind',f"/proc/self/fd/{roots['program'].fd}",'/program',
          '--ro-bind',f"/proc/self/fd/{roots['inputs'].fd}",'/inputs',
          '--bind',f"/proc/self/fd/{roots['output'].fd}",'/output',
          '--proc','/proc','--dev','/dev','--tmpfs','/tmp','--setenv','HOME','/tmp',
          '--setenv','PATH','/runtime/bin','--setenv','PYTHONDONTWRITEBYTECODE','1','--chdir','/program','--',*argv]
    return args,tuple(r.fd for r in roots.values())
