"""Concrete readonly anchored artifact resolution and complete-byte observation.

This is a mechanical observation producer, not a root admission factory. The
fixed native engine must supply the actual retained selected root descriptor
from its independently admitted context. A matching stat/Pin is not authority.
"""
import os
import stat
from .common import need
from .backend_linux_io import DescriptorSlot, NativeIOCustody
from .backend_linux_observations import hash_artifact_fd

ROLES={'server_executable':'executable','model_gguf':'model','template':'template',
       'tokenizer_source':'tokenizer','renderer_source':'renderer'}


class ArtifactReadAttempt:
    def __init__(self,io,root,role,components,selected):
        need(type(io) is NativeIOCustody and type(root) is DescriptorSlot and root.custody is io and
             root in io.slots and root.role=='artifact_root' and root.fd is not None and not root.close_entered,
             'actual retained original root descriptor, not a supplied integer/path')
        need(role in ROLES and type(components) is tuple and 1<=len(components)<=64 and
             all(type(c) is str and 0<len(c)<=255 and c not in ('.','..') and '/' not in c and '\0' not in c
                 for c in components),'exact closed selected component projection')
        self.io=io;self.root=root;self.role=role;self.components=components;self.selected=selected
        self.entered=False;self.directories=[];self.file=None;self.observation=None;self.root_before=None
        self.raw_first=None;self.secondaries=[];self.close_entered=False;self.closed=False
        # Caller retains this actual attempt before run; no file effect above.

    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        self.io.retain(error,'artifact_'+site)

    def _root(self):
        self.io.work();s=os.fstat(self.root.fd);v=os.fstatvfs(self.root.fd)
        need(stat.S_ISDIR(s.st_mode) and self.root.identity is not None and
             (s.st_dev,s.st_ino)==self.root.identity[:2],'same actual opened root')
        need(v.f_flag & os.ST_RDONLY,'actual selected filesystem readonly observation')
        return s

    def run(self,deadline):
        need(not self.entered,'one original artifact read attempt');self.entered=True
        try:
            self.io.now(deadline);self.root_before=self._root();parent=self.root
            for component in self.components[:-1]:
                slot=self.io.slot('artifact_directory');self.directories.append(slot)
                slot.openat(parent.fd,component,os.O_RDONLY|os.O_DIRECTORY|os.O_NONBLOCK)
                a=os.stat(component,dir_fd=parent.fd,follow_symlinks=False)
                need(stat.S_ISDIR(a.st_mode) and (a.st_dev,a.st_ino)==slot.identity[:2],
                     'same named/opened intermediate directory, no symlink or replacement')
                need(a.st_dev==self.root_before.st_dev,'no unselected mount crossing under root')
                parent=slot;self.io.now(deadline)
            self.file=self.io.slot(ROLES[self.role])
            self.file.openat(parent.fd,self.components[-1],os.O_RDONLY|os.O_NONBLOCK)
            a=os.stat(self.components[-1],dir_fd=parent.fd,follow_symlinks=False)
            need(stat.S_ISREG(a.st_mode) and (a.st_dev,a.st_ino)==self.file.identity[:2] and
                 a.st_dev==self.root_before.st_dev,'same selected actual named file before body read')
            self.observation=hash_artifact_fd(self.file,self.selected,deadline)
            b=os.stat(self.components[-1],dir_fd=parent.fd,follow_symlinks=False)
            need((b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns,b.st_ctime_ns)==
                 (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns),'no changed named artifact after full read')
            after=self._root();need((after.st_dev,after.st_ino)==(self.root_before.st_dev,self.root_before.st_ino),
                'same root after complete original observation')
            return self.observation
        except BaseException as error:self.retain(error,'run');raise
        finally:
            original=self.raw_first
            try:self.close_once()
            except BaseException as error:
                self.retain(error,'close')
                if original is None:raise

    def close_once(self):
        if self.close_entered:return self.closed
        self.close_entered=True;first=None
        for slot in ([self.file] if self.file is not None else [])+list(reversed(self.directories)):
            if not slot.close():
                error=slot.raw_first
                if error is None:error=RuntimeError('artifact descriptor acquisition/closure remains unknown')
                if first is None:first=error
                self.retain(error,'descriptor_close')
        self.closed=first is None
        if first is not None:raise first
        return True
