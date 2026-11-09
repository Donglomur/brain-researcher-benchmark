"""FD-relative directory capabilities with original-name identity joins.

Capabilities prevent adopting replacement directories. They do not themselves
prove exclusive parent lifetime against the same UID. Real execution additionally
requires independently authenticated positive custody/enclosure evidence.
"""
from pathlib import Path
import os,stat
from banc_runtime.codec import need,relative
from .failures import combine
_CAPS={}

def identity(st):return {'device':st.st_dev,'inode':st.st_ino}

class Directory:
    def __init__(self,path,fd,parent=None):
        self.path=path;self.fd=fd;self.parent=parent;self.identity=identity(os.fstat(fd));self.state='open'
    def __fspath__(self):return str(self.path)
    def __str__(self):return str(self.path)
    def __truediv__(self,name):return self.path/name
    def __getattr__(self,name):return getattr(self.path,name)
    def stat(self):self.verify();return os.fstat(self.fd)
    def verify(self):
        need(self.state=='open','directory capability closure is unavailable or ambiguous')
        need(identity(os.fstat(self.fd))==self.identity,'original directory fd identity')
        if self.parent is None:st=os.stat(self.path,follow_symlinks=False)
        else:
            self.parent.verify();st=os.stat(self.path.name,dir_fd=self.parent.fd,follow_symlinks=False)
        need(stat.S_ISDIR(st.st_mode) and identity(st)==self.identity,'original acquired directory name replaced')
        return self
    def child(self,name,create=False):
        need(type(name) is str and name not in ('','.','..') and '/' not in name and '\\' not in name,'one ordinary child directory')
        self.verify();path=self.path/name
        if create:os.mkdir(name,mode=0o700,dir_fd=self.fd)
        if str(path) in _CAPS:return _CAPS[str(path)].verify()
        fd=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=self.fd)
        cap=Directory(path,fd,self);_CAPS[str(path)]=cap
        cap.verify();return cap
    def close(self):
        need(self.state=='open','directory close is attempted only once')
        self.state='close_attempted'
        try:os.close(self.fd)
        except BaseException:
            self.state='close_ambiguous';raise
        self.state='closed'

def acquire(path,expected=None):
    if isinstance(path,Directory):cap=path.verify()
    else:
        p=Path(path).absolute();need(str(p)==os.path.normpath(str(p)),'canonical absolute directory')
        key=str(p)
        if key in _CAPS:cap=_CAPS[key].verify()
        elif p.parent==p:
            fd=os.open(str(p),os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);cap=Directory(p,fd);_CAPS[key]=cap;cap.verify()
        else:cap=acquire(p.parent).child(p.name)
    if expected is not None:need(cap.identity==expected,'independently selected original directory identity')
    return cap

def parent(root,name,create=False):
    cap=acquire(root);parts=Path(relative(name)).parts
    for part in parts[:-1]:
        try:cap=cap.child(part)
        except FileNotFoundError:
            need(create,'ordinary parent must exist');cap=cap.child(part,create=True)
    cap.verify();return cap,parts[-1]

def open_file(root,name,flags,mode=0o600):
    cap,leaf=parent(root,name);cap.verify()
    fd=os.open(leaf,flags|os.O_NOFOLLOW,mode,dir_fd=cap.fd)
    return cap,leaf,fd

def unlink(root,name,expected_identity):
    cap,leaf=parent(root,name);cap.verify();st=os.stat(leaf,dir_fd=cap.fd,follow_symlinks=False)
    need(stat.S_ISREG(st.st_mode) and identity(st)==expected_identity,'original owned file retirement identity')
    os.unlink(leaf,dir_fd=cap.fd);cap.verify()

def bindings(root):
    root=acquire(root)
    rows=[]
    for path,cap in sorted(_CAPS.items()):
        if cap.path==root.path or cap.path.is_relative_to(root.path):cap.verify();rows.append({'path':path,'identity':cap.identity})
    return rows

def restore(rows,root):
    root=acquire(root)
    for row in rows:
        need(set(row)=={'path','identity'} and Path(row['path']).is_relative_to(root.path),'owned prior directory binding')
        acquire(row['path'],row['identity'])

def close_all():
    errors=[]
    for cap in sorted(_CAPS.values(),key=lambda c:len(c.path.parts),reverse=True):
        if cap.state=='open':
            try:cap.close()
            except BaseException as exc:errors.append({'path':str(cap.path),'type':type(exc).__name__,'message':str(exc),'state':cap.state})
    _CAPS.clear()
    return errors
