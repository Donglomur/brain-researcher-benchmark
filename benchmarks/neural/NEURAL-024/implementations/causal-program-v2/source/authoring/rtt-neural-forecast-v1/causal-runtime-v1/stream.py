"""Existing BrainWide interactive pipe, with bounded prefix and full-byte hashes."""
import hashlib
import os
import selectors
import subprocess
import time
from common import DOCKER,ENV,need

STDOUT_CAP=90521600+16384
STDERR_CAP=32768
PREFIX_CAP=32768


class Stream:
    def __init__(self,name,deadline):
        self.deadline=deadline;self.out=bytearray();self.stdout=bytearray();self.stderr=bytearray()
        self.received={'stdout':0,'stderr':0};self.hashes={k:hashlib.sha256() for k in self.received}
        self.p=None;self.sel=selectors.DefaultSelector()
        try:
            self.p=subprocess.Popen([DOCKER,'start','--attach','--interactive',name],env=ENV,
                                     stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            for label,s in [('stdout',self.p.stdout),('stderr',self.p.stderr)]:
                os.set_blocking(s.fileno(),False);self.sel.register(s,selectors.EVENT_READ,label)
            os.set_blocking(self.p.stdin.fileno(),False)
        except BaseException:self.close();raise

    def pump(self):
        need(time.monotonic()<self.deadline,'Full single-session candidate wall limit')
        for key,_ in self.sel.select(min(.01,max(0,self.deadline-time.monotonic()))):
            b=os.read(key.fileobj.fileno(),4096)
            if not b:self.sel.unregister(key.fileobj);continue
            label=key.data;cap=STDOUT_CAP if label=='stdout' else STDERR_CAP
            self.received[label]+=len(b);self.hashes[label].update(b)
            target=self.stdout if label=='stdout' else self.stderr
            target.extend(b[:max(0,PREFIX_CAP-len(target))])
            need(self.received[label]<=cap,'Candidate stream cap; bounded diagnostic prefix retained')
            if label=='stdout':
                self.out.extend(b);need(len(self.out)<=8192,'Bounded pending frames')

    def line(self):
        need(time.monotonic()<self.deadline,'Reply admission before absolute deadline')
        while b'\n' not in self.out:
            need(self.sel.get_map(),'Candidate exited before complete reply');self.pump()
        b,_,rest=self.out.partition(b'\n');self.out=bytearray(rest)
        need(len(b)+1<=4096,'Response frame cap including newline')
        need(time.monotonic()<self.deadline,'Complete reply before absolute deadline')
        return bytes(b)

    def send(self,body):
        need(type(body) is bytes and len(body)<=4096 and body.endswith(b'\n'),'Bounded request frame')
        i=0
        while i<len(body):
            need(time.monotonic()<self.deadline,'Candidate input deadline')
            try:
                n=os.write(self.p.stdin.fileno(),body[i:]);need(n>0,'Closed candidate stdin');i+=n
            except BlockingIOError:self.pump()

    def finish(self):
        need(time.monotonic()<self.deadline,'Shutdown before absolute deadline')
        self.p.stdin.close()
        while self.sel.get_map():self.pump()
        need(not self.out,'No trailing unframed output')
        remaining=self.deadline-time.monotonic();need(remaining>0,'Shutdown wait before deadline')
        code=self.p.wait(timeout=remaining)
        need(time.monotonic()<self.deadline and code==0,'Normal complete candidate exit')
        return code

    def close(self):
        self.sel.close()
        if self.p is not None:
            if self.p.poll() is None:self.p.kill()
            self.p.wait(timeout=.8)
            for s in (self.p.stdin,self.p.stdout,self.p.stderr):
                if s is not None and not s.closed:s.close()
        return {'attach_cli_reaped':self.p is None or self.p.poll() is not None,
                'stream_bytes_received':dict(self.received),'stream_sha256':{k:v.hexdigest() for k,v in self.hashes.items()},
                'stream_prefix_bytes_retained':{'stdout':len(self.stdout),'stderr':len(self.stderr)},
                'full_stdout_retained':False}
