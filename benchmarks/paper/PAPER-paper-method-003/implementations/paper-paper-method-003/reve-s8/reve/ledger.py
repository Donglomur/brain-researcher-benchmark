"""Controller-owned append-only original attempt evidence."""
from pathlib import Path
import fcntl
import os
from .objects import canonical,decode,digest,write_new
from .errors import require
from .custody import Custody


class Ledger:
    def __init__(self, root, cap):
        self.custody=Custody();self.root=Path(root);self.cap=cap
        self.root.mkdir(mode=0o700,parents=True,exist_ok=True)
        require(not self.root.is_symlink(),'ledger root symlink')
        self.path=self.root/'events.jsonl'
        if not self.path.exists():write_new(self.path,b'')

    def rows(self):
        require(self.path.stat().st_size<=self.cap,'ledger cap')
        raw=self.path.read_bytes();rows=[];parent=None
        for line in raw.splitlines():
            row=decode(line);require(row['sequence']==len(rows) and row['parent']==parent,'ledger chain')
            parent=digest(canonical(row));rows.append(row)
        return rows

    def append(self,kind,payload):
        fd=os.open(self.path,os.O_RDWR|os.O_NOFOLLOW);original=None
        try:
            fcntl.flock(fd,fcntl.LOCK_EX)
            rows=self.rows();row={'sequence':len(rows),'parent':digest(canonical(rows[-1])) if rows else None,'kind':kind,'payload':payload}
            raw=canonical(row);require(os.fstat(fd).st_size+len(raw)<=self.cap,'ledger metadata budget')
            os.lseek(fd,0,os.SEEK_END);offset=0
            while offset<len(raw):
                n=os.write(fd,raw[offset:]);offset+=n;require(n>0,'ledger write made no progress')
            os.fsync(fd)
            return {'sequence':row['sequence'],'sha256':digest(raw)}
        except BaseException as exc:
            original=exc;self.custody.fail(exc,'Ledger.append');raise
        finally:
            try:os.close(fd)
            except BaseException as secondary:
                if original is not None:self.custody.add_secondary(secondary,'Ledger.close')
                else:
                    self.custody.fail(secondary,'Ledger.close');raise

    def ensure_capacity(self,amount):
        require(type(amount) is int and amount>0 and self.path.stat().st_size+amount<=self.cap,'prospective original-evidence metadata reservation')

    def reserve_attempt(self,identifier,request):
        require(not any(r['kind']=='attempt_begin' and r['payload']['attempt_id']==identifier for r in self.rows()),'attempt replay')
        return self.append('attempt_begin',{'attempt_id':identifier,'request':request})
