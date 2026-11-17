"""Bounded interactive pipe transport, adapted from the accepted prefix reference."""
import os,selectors,subprocess,time
from common import DOCKER,ENV,need

class Stream:
    def __init__(self,name,deadline):
        self.deadline=deadline;self.out=bytearray();self.stdout=bytearray();self.stderr=bytearray();self.p=None;self.sel=selectors.DefaultSelector()
        try:
            self.p=subprocess.Popen([DOCKER,'start','--attach','--interactive',name],env=ENV,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            for label,s in [('stdout',self.p.stdout),('stderr',self.p.stderr)]:os.set_blocking(s.fileno(),False);self.sel.register(s,selectors.EVENT_READ,label)
            os.set_blocking(self.p.stdin.fileno(),False)
        except BaseException:self.close();raise
    def pump(self):
        need(time.monotonic()<self.deadline,'Full single-session candidate wall limit')
        for key,_ in self.sel.select(min(.01,max(0,self.deadline-time.monotonic()))):
            b=os.read(key.fileobj.fileno(),4096)
            if not b:self.sel.unregister(key.fileobj);continue
            target=self.stdout if key.data=='stdout'else self.stderr;cap=262144 if key.data=='stdout'else 32768
            room=cap-len(target);target.extend(b[:max(0,room)])
            need(len(b)<=room,'Candidate stream cap exceeded; bounded prefix retained')
            if key.data=='stdout':self.out.extend(b);need(len(self.out)<=8192,'Bounded pending frames')
    def line(self):
        need(time.monotonic()<self.deadline,'Reply admission before absolute candidate deadline')
        while b'\n'not in self.out:
            need(self.sel.get_map(),'Candidate exited before complete reply');self.pump()
        b,_,rest=self.out.partition(b'\n');self.out=bytearray(rest);need(len(b)<=4096,'Response frame cap');need(time.monotonic()<self.deadline,'Complete reply before absolute candidate deadline');return bytes(b)
    def send(self,body):
        need(type(body)is bytes and len(body)<=32768 and body.endswith(b'\n'),'Bounded request frame')
        i=0
        while i<len(body):
            need(time.monotonic()<self.deadline,'Candidate input deadline')
            try:n=os.write(self.p.stdin.fileno(),body[i:]);need(n>0,'Closed candidate stdin');i+=n
            except BlockingIOError:self.pump()
    def finish(self):
        need(time.monotonic()<self.deadline,'Shutdown starts before absolute candidate deadline')
        self.p.stdin.close()
        while self.sel.get_map():self.pump()
        need(not self.out,'No trailing unframed output')
        remaining=self.deadline-time.monotonic();need(remaining>0,'Shutdown wait before absolute candidate deadline')
        code=self.p.wait(timeout=remaining)
        need(time.monotonic()<self.deadline,'Shutdown complete before absolute candidate deadline')
        need(code==0,'Candidate process exited successfully');return code
    def close(self):
        self.sel.close()
        if self.p is not None:
            if self.p.poll()is None:self.p.kill()
            self.p.wait(timeout=.8)
            for s in (self.p.stdin,self.p.stdout,self.p.stderr):
                if s is not None and not s.closed:s.close()
        return {'attach_cli_reaped':self.p is None or self.p.poll()is not None}
