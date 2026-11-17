"""Owned finalizer full-stream/pidfd collection, adapted from accepted StreamPump."""
import base64
import hashlib
import os
import selectors
import stat
import subprocess
from nb079_observation_common import require, integer, collect_errors, close_all, bounded_decode, fields


class FinalizerPump:
    def __init__(self,root_fd,root_path,clock,ledger,limits):
        self.root,self.root_path,self.clock,self.ledger,self.limits=root_fd,root_path,clock,ledger,limits
        self.selector=selectors.DefaultSelector();self.records={};self.files={};self.process=None;self.pidfd=None
        self.finished=None;self.closed=False
    def attach(self,process,pidfd):
        require(type(process) is subprocess.Popen and self.process is None,'exact unique owned Popen')
        self.process,self.pidfd=process,pidfd
        for name in ('stdout','stderr'):
            stream=getattr(process,name);fd=stream.fileno()
            require(stat.S_ISFIFO(os.fstat(fd).st_mode),'actual owned full pipe');os.set_blocking(fd,False)
            self.records[name]={'bytes':0,'retained_bytes':0,'digest':hashlib.sha256(),'retained_digest':hashlib.sha256(),
                'eof':False,'durable':False,'pending_block_base64':None,'pending_block_retained_bytes':0,'output':'finalizer-'+name+'.log'}
            self.files[name]=os.open(self.records[name]['output'],os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400,dir_fd=self.root)
            self.selector.register(fd,selectors.EVENT_READ,('stream',name))
        self.selector.register(pidfd,selectors.EVENT_READ,('exit',None))
    def consume(self,name,raw,phase):
        row=self.records[name]
        if not raw:
            row['eof']=True;os.fsync(self.files[name]);os.fsync(self.root);row['durable']=True;return
        row['bytes']+=len(raw);row['digest'].update(raw);row['pending_block_base64']=base64.b64encode(raw).decode('ascii')
        row['pending_block_retained_bytes']=0;self.ledger.returned('pipe_read_bytes',len(raw));first=None
        try:
            self.ledger.charge({'write_bytes':len(raw),'log_bytes':len(raw)},'full returned finalizer stream retention',phase)
            require(row['bytes']<=self.limits['stream_bytes'],'whole stream bound; no truncated success')
        except BaseException as error:first=error
        def retain():
            done=0
            while done<len(raw):
                self.clock.tick(phase);n=os.write(self.files[name],memoryview(raw)[done:])
                require(type(n) is int and 0<n<=len(raw)-done,'positive complete stream retention')
                row['retained_digest'].update(memoryview(raw)[done:done+n]);done+=n
                row['retained_bytes']+=n;row['pending_block_retained_bytes']+=n;self.ledger.returned('write_bytes',n)
            row['pending_block_base64']=None;row['pending_block_retained_bytes']=0
        first=collect_errors([('retain actual returned stream prefix',retain)],first)
        if first is not None:raise first
    def once(self,phase,maximum_wait_ns):
        now=self.clock.tick(phase);timeout=max(0,min(integer(maximum_wait_ns),getattr(self.clock,phase)-now))/1e9
        for key,_ in self.selector.select(timeout):
            if key.data[0]=='exit':
                value=os.waitid(os.P_PIDFD,self.pidfd,os.WEXITED|os.WNOWAIT|os.WNOHANG)
                require(value is not None and value.si_pid==self.process.pid,'original pidfd wait event')
                require(type(value.si_code) is int and type(value.si_status) is int,'integer original wait status, never bool')
                self.finished={'pid':value.si_pid,'code':value.si_code,'status':value.si_status,
                    'natural_zero':value.si_code==os.CLD_EXITED and value.si_status==0,'observed_ns':self.clock.tick(phase)}
                # Original wait evidence precedes the actual Popen reap.
                returned=self.process.wait(timeout=0)
                expected=value.si_status if value.si_code==os.CLD_EXITED else -value.si_status
                require(type(returned) is int and returned==expected,'original waitid/Popen reap agreement')
                self.finished['popen_returncode']=returned;self.selector.unregister(key.fd)
            else:
                name=key.data[1];remaining=self.limits['stream_bytes']-self.records[name]['bytes']
                maximum=min(self.limits['block_bytes'],max(1,remaining+1))
                self.ledger.charge({'data_read_bytes':maximum},'bounded process-pipe read before effect',phase)
                try:raw=os.read(key.fd,maximum)
                except BlockingIOError:continue
                self.consume(name,raw,phase)
                if not raw:self.selector.unregister(key.fd)
        self.clock.tick(phase)
    def ready(self,fd):
        os.set_blocking(fd,False);raw=bytearray()
        while True:
            self.once('scientific',self.limits['poll_ns'])
            require(self.finished is None,'prelude still blocked before release')
            self.ledger.charge({'data_read_bytes':2-len(raw)},'bounded readiness read before effect')
            try:block=os.read(fd,2-len(raw))
            except BlockingIOError:continue
            if not block:
                require(bytes(raw)==b'R','one exact readiness byte followed by EOF');return
            raw.extend(block);self.ledger.returned('readiness_read_bytes',len(block))
            require(bytes(raw)==b'R','no extra readiness byte')
    def complete(self):return self.finished is not None and all(self.records.get(name,{}).get('eof') for name in ('stdout','stderr'))
    def finish(self):
        while not self.complete():self.once('outer',self.limits['poll_ns'])
        require(self.finished['natural_zero'] is True,'original finalizer failed; full streams retained')
        require(all(row['durable'] for row in self.records.values()),'both streams durably complete including empty EOF')
        return self.finished
    def descriptors(self):
        return {name:{'path':self.root_path+'/'+row['output'],'bytes':row['bytes'],'sha256':row['digest'].hexdigest(),
            'retained_bytes':row['retained_bytes'],'retained_sha256':row['retained_digest'].hexdigest(),
            'eof':row['eof'],'durable':row['durable'],'pending_block_base64':row['pending_block_base64'],
            'pending_block_retained_bytes':row['pending_block_retained_bytes']} for name,row in self.records.items()}
    def close(self,primary=None):
        if self.closed:return
        self.closed=True;ops=[('process selector close',self.selector.close)]
        for name,fd in list(self.files.items()):
            del self.files[name];ops.extend([('partial stream fsync',lambda fd=fd:os.fsync(fd)),('stream output close',lambda fd=fd:os.close(fd))])
        close_all(ops,primary)


def parse_terminal(raw,encoding):
    require(type(raw) is bytes and raw.endswith(b'\n'),'complete finalizer terminal newline')
    lines=raw.splitlines();found=[]
    for i,line in enumerate(lines):
        try:value=bounded_decode(line,encoding)
        except (ValueError,UnicodeError):continue
        if type(value) is dict and value.get('schema')=='n079_complete_source_terminal_v1':found.append((i,value))
    require(len(found)==1 and found[0][0]==len(lines)-1,'one exact final complete-source terminal line')
    result=found[0][1]
    fields(result,('schema','status','result','original_outer','terminal_transport'),'original complete-source terminal ABI')
    require(result['status']=='complete' and result['terminal_transport']=='same reserved finalizer row; counters in body precede this whole stdout frame',
            'original actual finalizer terminal semantics')
    return result
