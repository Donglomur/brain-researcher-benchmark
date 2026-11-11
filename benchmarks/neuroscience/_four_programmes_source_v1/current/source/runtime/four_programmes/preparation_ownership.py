"""Actual anchored directory/file ownership for paired preparation.

All resources enter the original preparation's custody before subsequent
observations. Ambiguous mkdir/open/close never grants ownership or a retry.
Only observed exact inode/device/kind joins authorize deletion. No recursive
delete or discovery of unselected files is performed.
"""
import os
import stat
import time
from .common import Store, need, integer, relative
from .early_resources import EarlyResources
from .precommit_records import CONDITIONS, validate_type

class PreparationRawCustody:
    def __init__(self,owner):
        need(type(owner) is EarlyResources and owner.parent.owner is owner,'same actual original early owner')
        self.owner=owner;self.raw_first=None;self.raw_secondaries=[];self.unknown=[]
        self.handles=[];self.next_handle=0
    def retain(self,error,site,unknown=None):
        # Store actual exception identity before any diagnostic or owner call.
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.raw_secondaries.append(error)
        if unknown is not None:self.unknown.append((site,unknown))
        try:self.owner.parent.retain(error,'development_prepare','unknown_failure',site)
        except BaseException as secondary:
            if secondary is not self.raw_first:self.raw_secondaries.append(secondary)
    def register(self,handle):
        need(sum(h.condition==handle.condition for h in self.handles)<128,
             'original per-arm 128-slot cleanup capacity reserved before acquisition')
        handle.ordinal=self.next_handle;self.next_handle+=1;self.handles.append(handle)

class OwnedParentAnchor:
    def __init__(self,custody,condition):
        self.condition=condition;self.fds=[];self.leaf=None;self.close_unknown=False
        custody.register(self)

class OwnedPreparationPath:
    """One exact directory or file and its original parent/descriptor slots."""
    def __init__(self,custody,condition,store,name,kind):
        need(type(custody) is PreparationRawCustody and condition in CONDITIONS,'actual preparation and arm')
        need(type(store) is Store and store.meter is custody.owner.arms[condition], 'same original arm-owned Store')
        relative(name);need(kind in ('directory','regular_file'),'fixed preparation resource kind')
        self.custody=custody;self.condition=condition;self.store=store;self.name=name;self.kind=kind
        self.anchor_handle=OwnedParentAnchor(custody,condition)
        self.parents=self.anchor_handle.fds;self.leaf=None;self.fd=None;self.identity=None;self.created=False
        self.create_attempted=False;self.open_attempted=False;self.cleanup_attempted=False
        self.mkdir_entered=False;self.open_entered=False
        self.removal_attempted=False;self.removed=False;self.close_unknown=False
        self.content=None;self.readonly=False;self.write_entered=False
        custody.register(self)
    def _own_error(self,error,site,unknown=None):self.custody.retain(error,site,unknown)
    def anchor(self):
        need(not self.parents and self.leaf is None,'one original parent anchor acquisition')
        try:
            self.store.meter.charge('work_units',4096)
            parents,leaf=self.store._parent(self.name)
            self.parents.extend(parents);self.leaf=leaf;self.anchor_handle.leaf=leaf
        except BaseException as error:
            self.anchor_handle.close_unknown=True
            self._own_error(error,'PreparationPath.anchor','parent acquisition');raise
    def mkdir(self):
        need(self.kind=='directory' and not self.create_attempted and self.custody.raw_first is None,
             'one source-owned directory creation before failure')
        self.create_attempted=True
        try:
            self.anchor();self.store.meter.charge('work_units',4096)
            self.mkdir_entered=True
            os.mkdir(self.leaf,mode=0o700,dir_fd=self.parents[-1])
            self.created=True  # Own successful return before any observation.
        except BaseException as error:
            self._own_error(error,'PreparationPath.mkdir','create effect unknown' if self.mkdir_entered and not self.created else None);raise
    def open(self):
        need(self.created and not self.open_attempted and self.custody.raw_first is None,
             'open only exact successfully created original path once')
        self.open_attempted=True
        try:
            self.store.meter.charge('work_units',4096)
            flags=os.O_RDONLY|os.O_NOFOLLOW|(os.O_DIRECTORY if self.kind=='directory' else 0)
            self.open_entered=True
            self.fd=os.open(self.leaf,flags,dir_fd=self.parents[-1])
        except BaseException as error:
            if self.open_entered and self.fd is None:self.close_unknown=True
            self._own_error(error,'PreparationPath.open','open return unknown' if self.open_entered else None);raise
    def write_new(self,raw):
        from .common import pin
        need(self.kind=='regular_file' and type(raw) is bytes and not self.create_attempted and
             self.custody.raw_first is None,'one original exact immutable selected file')
        self.create_attempted=True
        try:
            self.anchor();self.store.meter.charge('work_units',4096)
            self.store.meter.charge('write_bytes',len(raw));self.store.meter.charge('retained_bytes',len(raw))
            self.open_entered=True
            self.fd=os.open(self.leaf,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=self.parents[-1])
            self.created=True;self.open_attempted=True
            at=0
            while at<len(raw):
                self.store.meter.charge('work_units',4096);self.write_entered=True
                count=os.write(self.fd,raw[at:])
                need(type(count) is int and 0<count<=len(raw)-at,'actual bounded positive original write return')
                at+=count
            self.store.meter.charge('work_units',8192);os.fsync(self.fd);os.fchmod(self.fd,0o444)
            self.readonly=True
            expected={'path':self.name,**pin(raw)}
            self.store.meter.charge('retained_bytes',len(raw)+1)
            observed=self.store.read(expected,len(raw),metadata=False)
            need(observed==raw,'complete actual immutable view copy readback')
            self.content=expected
            self.identify()
            return expected
        except BaseException as error:
            if self.open_entered and self.fd is None:self.close_unknown=True
            self._own_error(error,'PreparationPath.write_new','original file write/create/close extent unknown');raise
    def identify(self):
        need(self.fd is not None and self.identity is None,'actual earlier descriptor before original identification')
        try:
            self.store.meter.charge('work_units',8192)
            a=os.fstat(self.fd);b=os.stat(self.leaf,dir_fd=self.parents[-1],follow_symlinks=False)
            match=stat.S_ISDIR if self.kind=='directory' else stat.S_ISREG
            need(match(a.st_mode) and match(b.st_mode) and (a.st_dev,a.st_ino)==(b.st_dev,b.st_ino),
                 'same original anchored actual path and acquired descriptor')
            observed=time.monotonic_ns();integer(observed);self.store.meter.check()
            self.identity={'schema':'ci_owned_path_identity_v1','parent_handle_ordinal':self.anchor_handle.ordinal,
                'relative_path':self.name,'device':a.st_dev,'inode':a.st_ino,'kind':self.kind,
                'mode':stat.S_IMODE(a.st_mode),'uid':a.st_uid,'observed_ns':observed}
            validate_type('OwnedPathIdentity',self.identity)
            return self.identity
        except BaseException as error:
            self._own_error(error,'PreparationPath.identify','original identity unavailable');raise
    def assert_same_path(self):
        need(self.created and self.identity is not None and self.parents,'actual observed original ownership before deletion')
        self.store.meter.charge('work_units',4096)
        s=os.stat(self.leaf,dir_fd=self.parents[-1],follow_symlinks=False)
        kind=stat.S_ISDIR if self.kind=='directory' else stat.S_ISREG
        need(kind(s.st_mode) and (s.st_dev,s.st_ino)==(self.identity['device'],self.identity['inode']),
             'never delete replaced/preexisting/unobserved path')
    def remove(self):
        need(not self.removal_attempted,'one original removal attempt')
        self.removal_attempted=True
        try:
            self.assert_same_path()
            self.store.meter.charge('work_units',4096)
            if self.kind=='directory':os.rmdir(self.leaf,dir_fd=self.parents[-1])
            else:os.unlink(self.leaf,dir_fd=self.parents[-1])
            self.removed=True
        except BaseException as error:
            self._own_error(error,'PreparationPath.remove','removal effect unknown');raise
    def close(self):
        need(not self.cleanup_attempted,'one original descriptor cleanup attempt')
        self.cleanup_attempted=True
        first=None
        # Relinquish each descriptor slot before close; never retry an ambiguous
        # integer after another operation might have reused it.
        if self.fd is not None:
            closing,self.fd=self.fd,None
            try:os.close(closing)
            except BaseException as error:
                first=error;self.close_unknown=True;self._own_error(error,'PreparationPath.close','fd closure unknown')
        while self.parents:
            closing=self.parents.pop()
            try:os.close(closing)
            except BaseException as error:
                self.close_unknown=True;self.anchor_handle.close_unknown=True
                self._own_error(error,'PreparationPath.parent_close','parent fd closure unknown')
                if first is None:first=error
        if first is not None:raise first
