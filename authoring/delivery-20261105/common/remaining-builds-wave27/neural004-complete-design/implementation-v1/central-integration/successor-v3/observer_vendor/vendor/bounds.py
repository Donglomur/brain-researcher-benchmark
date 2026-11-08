"""Bounded source/metadata custody. No numeric interpretation or scientific imports."""
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time
from .engine import need, pin, encoded, parse, path, descriptor, cleanup_all, finish_cleanup

FIELDS = ('st_dev','st_ino','st_mode','st_size','st_nlink','st_mtime_ns','st_ctime_ns')

def relative(name):
    need(type(name) is str and 0 < len(name.encode()) <= 512, 'Bounded relative name')
    parts = PurePosixPath(name).parts
    need(str(PurePosixPath(name)) == name and not name.startswith('/') and len(parts) <= 8
         and all(re.fullmatch('[A-Za-z0-9_][A-Za-z0-9._-]*', x) and x not in ('.','..') for x in parts),
         'Ordinary canonical relative name')
    return name


def stamp(s): return tuple(getattr(s,k) for k in FIELDS)


class Meter:
    def __init__(self, read_limit, write_limit, deadline):
        need(type(read_limit) is int and read_limit > 0 and type(write_limit) is int and write_limit > 0,
             'Explicit prospective transport read/write ceilings')
        self.read_limit, self.write_limit, self.deadline = read_limit, write_limit, deadline
        self.read_bytes = self.write_bytes = self.write_reserved_bytes = 0
        self.last_observed=time.monotonic()
        need(self.last_observed<deadline,"Original transport interval")
    def tick(self):
        now=time.monotonic();need(self.last_observed<=now<self.deadline,'Original phase deadline and no clock rollback');self.last_observed=now;return now
    def read(self,n):
        self.tick(); need(type(n) is int and n >= 0 and self.read_bytes+n <= self.read_limit,'Transport read ceiling')
        self.read_bytes += n
    def ensure_read(self,n):
        self.tick();need(type(n) is int and n>=0 and self.read_bytes+n<=self.read_limit,'Prospective transport read reservation')
    def write(self,n):
        self.tick(); need(type(n) is int and n >= 0 and self.write_reserved_bytes+n <= self.write_limit,'Transport write ceiling')
        self.write_reserved_bytes += n
    def wrote(self,n):self.write_bytes+=n


def body(file, expected, meter, cap, retain=True):
    file=path(file);descriptor(expected,allow_empty=True);meter.ensure_read(expected['bytes']+1)
    need(expected['bytes']<=cap,'Declared file ceiling')
    fd=os.open(file,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    digest,parts,size=hashlib.sha256(),[],0;primary=None
    try:
        before=os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==expected['bytes'],'Single-link exact source extent')
        while True:
            meter.tick();raw=os.read(fd,min(65536,expected['bytes']+1-size));meter.read(len(raw))
            if not raw:break
            size+=len(raw);need(size<=expected['bytes'],'Exact source EOF');digest.update(raw)
            if retain:parts.append(raw)
        need(stamp(before)==stamp(os.fstat(fd))==stamp(file.lstat()),'Stable full file identity')
        need(size==expected['bytes'] and digest.hexdigest()==expected['sha256'],'Exact immutable file pin')
        return b''.join(parts) if retain else expected
    except BaseException as error:primary=error;raise
    finally:finish_cleanup([('body.close',lambda:os.close(fd))],primary)

def fsync_dir(p):
    fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);primary=None
    try:os.fsync(fd)
    except BaseException as error:primary=error;raise
    finally:finish_cleanup([('directory.close',lambda:os.close(fd))],primary)


def publish(file,raw,meter,mode=0o600):
    """Exclusive durable metadata publication; preserve every cleanup failure."""
    file=path(file);need(type(raw) is bytes,'Complete metadata bytes');meter.write(len(raw))
    fd=None;identity=None
    def remove_owned():
        try:s=file.lstat()
        except FileNotFoundError:return
        need((s.st_dev,s.st_ino)==identity and stat.S_ISREG(s.st_mode),'Cleanup refused replaced/unowned output inode')
        file.unlink()
    try:
        fd=os.open(file,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
        s=os.fstat(fd);need(stat.S_ISREG(s.st_mode),'Owned ordinary output inode');identity=(s.st_dev,s.st_ino);at=0
        while at<len(raw):
            meter.tick();n=os.write(fd,memoryview(raw)[at:]);need(type(n) is int and 0<n<=len(raw)-at,'Checked complete write');at+=n;meter.wrote(n)
        os.fsync(fd);closing,fd=fd,None;os.close(closing);fsync_dir(file.parent)
        return pin(raw)
    except BaseException as primary:
        actions=[]
        if fd is not None:actions.append(('output.close',lambda:os.close(fd)))
        if identity is not None:
            actions.append(('output.remove_owned',remove_owned))
            actions.append(('output.parent_fsync',lambda:fsync_dir(file.parent)))
        cleanup_all(actions,primary)
        raise

def native_readable(s,directory=False):
    """Explicit container UID/GID, without changing host source permissions."""
    shift=6 if s.st_uid==65534 else 3 if s.st_gid==65534 else 0
    required=5 if directory else 4
    need(((s.st_mode>>shift)&required)==required,'Immutable view must be readable/traversable by container UID/GID65534')


def tree(desc, meter):
    need(type(desc) is dict and set(desc)=={'path','kind','purpose','files'},'Exact immutable mount descriptor')
    root=path(desc['path']);need(desc['kind'] in ('file','directory'),'Typed input mount')
    files=desc['files'];need(type(files) is dict and files,'Complete nonempty immutable file tree')
    for name,p in files.items():relative(name);descriptor(p,allow_empty=True)
    if desc['kind']=='file':
        need(set(files)=={root.name},'Single mounted filename');native_readable(root.lstat());body(root,files[root.name],meter,files[root.name]['bytes'],False)
    else:
        need(root.is_dir(),'Directory mount');expected_dirs={''}
        for name in files:
            expected_dirs.update(str(p) for p in PurePosixPath(name).parents if str(p)!='.')
        got={};dirs={''};before={}
        for parent, directory_names, names in os.walk(root,followlinks=False):
            parent=path(parent);native_readable(parent.lstat(),True);before[str(parent)]=stamp(parent.lstat())
            for d in directory_names:
                child=path(parent/d);need(child.is_dir(),'Ordinary input directory')
                dirs.add(str(child.relative_to(root)));need(len(dirs)<=len(expected_dirs),'Bounded input directories')
            for name in names:
                child=path(parent/name);rel=str(child.relative_to(root));need(rel in files and rel not in got,'Exact closed input membership')
                native_readable(child.lstat());body(child,files[rel],meter,files[rel]['bytes'],False);got[rel]=files[rel]
        need(got==files and dirs==expected_dirs,'Complete exact input tree including directories')
        for p,s in before.items():need(stamp(Path(p).lstat())==s,'Stable input directory')
    return {'kind':desc['kind'],'purpose':desc['purpose'],'files':files}


def mount_identity(mounts):
    return {target:{k:v for k,v in desc.items() if k!='path'} for target,desc in sorted(mounts.items())}


def local_metadata(file,cap,meter):
    """Stable bounded private journal body; ownership/request pins stay external."""
    file=path(file);fd=os.open(file,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);primary=None
    try:
        first=os.fstat(fd)
        need(stat.S_ISREG(first.st_mode) and first.st_nlink==1 and 0<first.st_size<=cap,'Bounded private journal record')
        meter.ensure_read(first.st_size+1);pieces=[];n=0
        while True:
            raw=os.read(fd,min(65536,first.st_size+1-n));meter.read(len(raw))
            if not raw:break
            n+=len(raw);need(n<=first.st_size,'Journal extent');pieces.append(raw)
        need(n==first.st_size and stamp(first)==stamp(os.fstat(fd))==stamp(file.lstat()),'Stable complete private record')
        return b''.join(pieces)
    except BaseException as error:primary=error;raise
    finally:finish_cleanup([('local_metadata.close',lambda:os.close(fd))],primary)
