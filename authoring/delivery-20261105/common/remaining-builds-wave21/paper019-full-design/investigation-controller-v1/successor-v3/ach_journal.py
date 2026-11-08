"""Private exclusive append-only artifacts; source-level durability, not custody proof."""
import os
from pathlib import Path
from ach_util import need,encode,pin_bytes,integer,finish_owned

class Journal:
    def __init__(self,root,ledger,record_cap):
        self.root=Path(root);self.ledger=ledger;self.cap=integer(record_cap,1);self.serial=0;self.records=[]
        need(self.root.is_absolute() and not self.root.exists(),'new independently admitted private journal directory')
        self.root.mkdir(mode=0o700);self.fd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        self.closed=False
    def append(self,kind,value,*,cutoff='scientific'):
        need(not self.closed,'open journal');self.ledger.tick(cutoff)
        raw=encode({'ordinal':self.serial,'kind':kind,'value':value})
        need(len(raw)<=self.cap,'complete journal record cap, no truncation')
        self.ledger.reserve({'write_bytes':len(raw),'retained_bytes':len(raw)},'private journal '+kind,cutoff=cutoff)
        name=f'{self.serial:09d}.json';self.serial+=1
        fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400,dir_fd=self.fd);primary=None
        try:
            data=memoryview(raw)
            while data:
                self.ledger.tick(cutoff);n=os.write(fd,data);need(n>0,'complete journal write');data=data[n:]
            os.fsync(fd)
        except BaseException as error:primary=error;raise
        finally:finish_owned([('journal record descriptor close',lambda:os.close(fd))],primary)
        os.fsync(self.fd);self.ledger.tick(cutoff)
        receipt={'path':str(self.root/name),**pin_bytes(raw)};self.records.append(receipt)
        return receipt
    def failure(self,phase,error):
        return self.append('failure',{'phase':phase,'type':type(error).__name__,
            'message':str(error)[:2048],'ledger':self.ledger.report()},cutoff='closeout')
    def close(self):
        if not self.closed:
            try:finish_owned([('journal directory fsync',lambda:os.fsync(self.fd)),('journal directory close',lambda:os.close(self.fd))])
            finally:self.closed=True
