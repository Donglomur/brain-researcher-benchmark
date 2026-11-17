"""Operator-owned host artifact budget, checked BEFORE each managed write.

Directories must have no hostile concurrent writers. Metadata accounting does
not follow symlinks; pytest's generated convenience links count their own bytes.
No file content is read to calculate retained size.
"""
import os
from pathlib import Path
import stat

class BudgetError(ValueError):pass

class HostBudget:
    def __init__(self,root,limit=5_000_000,reserve=2_000_000):
        self.root=Path(root).absolute();self.limit=limit;self.reserve=reserve
        if type(limit)is not int or type(reserve)is not int or not 0<=reserve<limit:raise BudgetError('invalid budget')
        if not self.root.is_dir() or any(p.is_symlink()for p in (self.root,*self.root.parents)):raise BudgetError('unlinked operator root')
    def used(self):
        total=0
        for root,dirs,files in os.walk(self.root,followlinks=False):
            for name in dirs+files:
                s=(Path(root)/name).lstat()
                if not stat.S_ISDIR(s.st_mode):total+=s.st_size
        return total
    def check(self,additional,*,receipt=False):
        if type(additional)is not int or additional<0:raise BudgetError('invalid planned byte count')
        used=self.used();ceiling=self.limit if receipt else self.limit-self.reserve
        if used+additional>ceiling:raise BudgetError('cumulative host bytes would exceed cap or consume receipt reserve')
        return used
    def safe_destination(self,path):
        path=Path(path).absolute()
        if '..'in path.parts or not path.is_relative_to(self.root) or path==self.root:raise BudgetError('destination outside budget root')
        if any(p.is_symlink()for p in (path,*path.parents)):raise BudgetError('linked destination')
        if path.exists():raise BudgetError('fresh budgeted file required')
        return path
    def write(self,path,data,*,receipt=False,mode=0o400):
        if type(data)is not bytes:raise BudgetError('exact serialized bytes required')
        path=self.safe_destination(path);self.check(len(data),receipt=receipt)
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb')as stream:stream.write(data)
        path.chmod(mode)
        return len(data)
