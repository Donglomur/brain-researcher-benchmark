"""Exact owned full input views. Never imports/unpickles original data.

Only closure-bound retirement is offered. An interrupted attempt is retained for
external recovery; no retry or presumed deletion of possibly mounted resources.
"""
import hashlib, os, stat
from pathlib import Path
from common import need, descriptor, ordinary, identity, relative, capture, save, canonical



def sync(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)


def copy(source,target,expected,budget):
    source,target=ordinary(source),ordinary(target);d=descriptor(expected,3*1024**3,allow_empty=True)
    budget.reading(d['bytes']+1);budget.writing(d['bytes'])
    target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    a=b=None;primary=None
    try:
        a=os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);before=os.fstat(a)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink in tuple(expected.get('links',(1,))) and before.st_size==d['bytes'],'exact copied input identity')
        b=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
        left=d['bytes'];h=hashlib.sha256();header=b''
        while left:
            budget.deadline();raw=os.read(a,min(left,1048576));need(raw,'complete copy')
            header+=raw[:max(0,64-len(header))];left-=len(raw);h.update(raw);v=memoryview(raw)
            while v:
                n=os.write(b,v);need(n>0,'complete owned write');v=v[n:]
        need(not os.read(a,1) and h.hexdigest()==d['sha256'] and identity(before)==identity(os.fstat(a))==identity(source.lstat()),'bounded stable full input authentication')
        os.fchmod(b,0o444);os.fsync(b)
    except BaseException as error:primary=error;raise
    finally:
        failures=[]
        for fd in (a,b):
            if fd is not None:
                try:os.close(fd)
                except BaseException as error:failures.append(type(error).__name__)
        if failures:
            if primary is not None:primary.add_note('Independent copy close uncertainty: '+','.join(failures))
            else:raise OSError('Independent copy close uncertainty: '+','.join(failures))
    sync(target.parent)
    return d


def tree(root):
    files={};dirs=[]
    def visit(p):
        for q in sorted(p.iterdir()):
            s=q.lstat();name=q.relative_to(root).as_posix()
            need(not stat.S_ISLNK(s.st_mode),'ordinary view inventory')
            if stat.S_ISDIR(s.st_mode):dirs.append(name);visit(q)
            else:
                need(stat.S_ISREG(s.st_mode) and s.st_nlink==1,'single-link view file');files[name]=s
    visit(root);return files,dirs


class View:
    def __init__(self,root,rows,metadata,budget):
        self.root=ordinary(root);self.budget=budget;self.expected={};self.live=False
        charge_before=budget.retained_charge
        need(not self.root.exists() and 1<=len(rows)<=180,'fresh bounded complete view')
        self.root.mkdir(mode=0o700,parents=True)
        for r in rows:
            name=str(relative(r['target']));need(name not in self.expected and name not in ('VIEW.json','BASELINE_REQUEST.json'),'unique scientific input member')
            self.expected[name]=copy(r['source'],self.root/name,r,budget)
        self.expected['VIEW.json']=save(self.root/'VIEW.json',canonical(metadata),budget)
        os.chmod(self.root/'VIEW.json',0o444)
        self.verify() # second complete body pass, after custody copy
        files,dirs=tree(self.root)
        for name in sorted(dirs,key=lambda n:n.count('/'),reverse=True):os.chmod(self.root/name,0o555)
        os.chmod(self.root,0o555);self.live=True
        self.retirement_credit=budget.retained_charge-charge_before
    def verify(self):
        files,_=tree(self.root);need(set(files)==set(self.expected),'complete exact view, no extras')
        for name,d in self.expected.items():
            need(stat.S_IMODE(files[name].st_mode)==0o444,'immutable public view mode')
            capture(self.root/name,d,3*1024**3,self.budget,retain=False,allow_empty=True)
    def handoff(self):
        need(self.live,'only live owned view');self.verify() # third full pass
        return self.root
    def retire_after_closed_execution(self,receipt,closure_check):
        need(self.live,'single execution retirement')
        closure_check(receipt) # no mutation before all owned native/host command closures
        self.verify() # fourth complete body pass
        files,dirs=tree(self.root)
        os.chmod(self.root,0o700)
        for name in sorted(dirs,key=lambda n:n.count('/')):os.chmod(self.root/name,0o700)
        failures=[]
        for name in sorted(files):
            try:(self.root/name).unlink()
            except BaseException as error:failures.append((name,type(error).__name__))
        for name in sorted(dirs,key=lambda n:n.count('/'),reverse=True):
            try:(self.root/name).rmdir()
            except BaseException as error:failures.append((name,type(error).__name__))
        try:self.root.rmdir()
        except BaseException as error:failures.append(('.',type(error).__name__))
        need(not failures,'independent exact-view cleanup uncertainty: '+repr(failures))
        sync(self.root.parent)
        self.budget.release_retired(self.retirement_credit)
        self.live=False
