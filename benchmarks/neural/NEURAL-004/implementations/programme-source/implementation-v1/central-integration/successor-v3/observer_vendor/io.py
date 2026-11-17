"""Strict bounded transport metadata; no native/scientific imports or execution."""
import hashlib,os,stat,time,uuid
from pathlib import Path
from .vendor.engine import need,encoded,parse,pin,descriptor,cleanup_all,finish_cleanup
from .vendor.bounds import fsync_dir,relative


def capture(path,expected=None,cap=2097152,meter=None):
    path=Path(path);need(path.is_absolute() and not any(p.is_symlink() for p in (path,*path.parents)),'Ordinary absolute capture')
    need(type(cap)is int and cap>0,'Explicit capture cap')
    if expected is not None:descriptor(expected,allow_empty=True);need(expected['bytes']<=cap,'Bounded expected extent')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);primary=None
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size<=cap,'Bounded single-link capture')
        if meter:meter.read(before.st_size+1)
        parts=[];n=0
        while True:
            raw=os.read(fd,min(65536,before.st_size+1-n))
            if not raw:break
            n+=len(raw);need(n<=before.st_size,'No silent capture truncation');parts.append(raw)
        fields=('st_dev','st_ino','st_size','st_mode','st_nlink','st_mtime_ns','st_ctime_ns');sig=lambda s:tuple(getattr(s,k) for k in fields)
        need(n==before.st_size and sig(before)==sig(os.fstat(fd))==sig(path.lstat()),'Exact stable named capture')
        raw=b''.join(parts)
        if expected is not None:need(pin(raw)==expected,'Exact source/output pin')
        return raw
    except BaseException as exc:primary=exc;raise
    finally:finish_cleanup([('capture.close',lambda:os.close(fd))],primary)


def publish(path,raw,meter=None,mode=0o444):
    path=Path(path);need(path.is_absolute() and not os.path.lexists(path) and not any(p.is_symlink() for p in path.parents),'Fresh ordinary publication')
    need(type(raw)is bytes,'Exact body')
    if meter:meter.write(len(raw))
    tmp=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.partial');fd=None;owned=None;linked=False
    def remove(q):
        try:s=q.lstat()
        except FileNotFoundError:return
        need((s.st_dev,s.st_ino)==owned and stat.S_ISREG(s.st_mode),'Preserve foreign replaced inode');q.unlink()
    try:
        fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode);s=os.fstat(fd);owned=(s.st_dev,s.st_ino);at=0
        while at<len(raw):
            if meter:meter.tick()
            n=os.write(fd,memoryview(raw)[at:]);need(type(n)is int and 0<n<=len(raw)-at,'Checked full write');at+=n
        os.fsync(fd);closing,fd=fd,None;os.close(closing);os.link(tmp,path,follow_symlinks=False);linked=True;remove(tmp);fsync_dir(path.parent)
        if meter:meter.tick()
        return pin(raw)
    except BaseException as exc:
        actions=[]
        if fd is not None:actions.append(('publish.close',lambda:os.close(fd)))
        if owned is not None and linked:actions.append(('publish.remove',lambda:remove(path)))
        if owned is not None:actions.extend([('temporary.remove',lambda:remove(tmp)),('parent.sync',lambda:fsync_dir(path.parent))])
        cleanup_all(actions,exc);raise


def failure(exc):return {'type':type(exc).__name__,'message':str(exc)[:2000],'cleanup_errors':getattr(exc,'cleanup_errors',[])}


class Clock:
    def __init__(self,origin,deadline):
        import math
        need(all(type(v)in(int,float) and math.isfinite(v) for v in (origin,deadline)) and 0<=origin<deadline,'Finite original clock')
        self.origin=origin;self.deadline=deadline;self.last=origin
    def tick(self):
        now=time.monotonic();need(self.last<=now<self.deadline,'Original clock, no rollback');self.last=now;return now
    def left(self):return self.deadline-self.tick()
