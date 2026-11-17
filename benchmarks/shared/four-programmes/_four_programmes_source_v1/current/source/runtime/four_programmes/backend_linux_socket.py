"""Actual anchored Unix socket observation/removal with once-only ownership."""
import os
import stat
from .common import need
from .preparation_ownership import OwnedPreparationPath
from .backend_linux_io import NativeIOCustody
from .precommit_records import validate_type


class OwnedBackendSocket:
    def __init__(self,handle,io,workspace):
        need(type(io) is NativeIOCustody and io.handle is handle,'same original backend IO owner')
        need(type(workspace) is OwnedPreparationPath and workspace.condition==handle.condition and
             workspace.custody.owner is handle.owner and workspace.fd is not None and
             workspace.identity is not None,'actual retained arm workspace anchor')
        self.handle=handle;self.io=io;self.workspace=workspace;self.identity=None
        self.prechecked=False;self.observed=None;self.close_entered=False;self.unlink_entered=False
        self.absent=False;self.closed_ns=None;self.raw_first=None;self.secondaries=[]
        self.unknown=False

    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        self.unknown=True;self.io.retain(error,'socket_'+site)

    def _anchor(self,deadline):
        self.io.now(deadline);self.io.work()
        a=os.fstat(self.workspace.fd);expected=self.workspace.identity
        need(stat.S_ISDIR(a.st_mode) and (a.st_dev,a.st_ino)==(expected['device'],expected['inode']) and
             stat.S_IMODE(a.st_mode)==0o700,'same private original workspace descriptor')

    def before_spawn(self):
        need(not self.prechecked,'one original pre-spawn socket absence check')
        self.prechecked=True
        try:
            self._anchor(self.handle.J)
            try:os.stat('backend.sock',dir_fd=self.workspace.fd,follow_symlinks=False)
            except FileNotFoundError:return
            raise FileExistsError('original backend socket path must be absent before spawn')
        except BaseException as error:self.retain(error,'precheck');raise

    def observe(self):
        need(self.prechecked and self.identity is None and not self.close_entered,'single original socket identity')
        try:
            self._anchor(self.handle.J)
            a=os.stat('backend.sock',dir_fd=self.workspace.fd,follow_symlinks=False)
            need(stat.S_ISSOCK(a.st_mode) and a.st_uid==self.workspace.identity['uid'],
                 'actual Unix socket owned by original workspace user')
            now=self.io.now(self.handle.J)
            self.observed=a
            self.identity={'schema':'ci_owned_path_identity_v1','parent_handle_ordinal':self.workspace.ordinal,
                'relative_path':'backend.sock','device':a.st_dev,'inode':a.st_ino,'kind':'socket',
                'mode':stat.S_IMODE(a.st_mode),'uid':a.st_uid,'observed_ns':now}
            validate_type('OwnedPathIdentity',self.identity);return self.identity
        except BaseException as error:self.retain(error,'identify');raise

    def close_once(self):
        if self.close_entered:return self.absent and self.raw_first is None
        self.close_entered=True
        try:
            self._anchor(self.handle.R)
            # No guessed identity or preexisting-path deletion on partial setup.
            need(self.identity is not None,'actual earlier socket identity before removal')
            try:a=os.stat('backend.sock',dir_fd=self.workspace.fd,follow_symlinks=False)
            except FileNotFoundError:
                self.absent=True;self.closed_ns=self.io.now(self.handle.R);return True
            need(stat.S_ISSOCK(a.st_mode) and (a.st_dev,a.st_ino,a.st_uid)==
                (self.identity['device'],self.identity['inode'],self.identity['uid']),
                'never delete a replacement or unobserved socket')
            self.io.work();self.unlink_entered=True
            os.unlink('backend.sock',dir_fd=self.workspace.fd)
            try:os.stat('backend.sock',dir_fd=self.workspace.fd,follow_symlinks=False)
            except FileNotFoundError:self.absent=True
            need(self.absent,'actual absence after original unlink')
            self.closed_ns=self.io.now(self.handle.R);return True
        except BaseException as error:self.retain(error,'close');raise
