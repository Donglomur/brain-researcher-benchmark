"""Bounded Unix descriptor transport. Message paths never grant new operands."""
import array,hashlib,os,socket,stat,struct,time
import common as c

MAX_MESSAGE=65536

def send(sock,message,fd=None,*,deadline,budget):
    raw=c.encoded(message);budget.charge('write_bytes',len(raw));c.need(len(raw)<=MAX_MESSAGE,'bounded typed IPC message');remaining=deadline-time.monotonic();c.need(remaining>0,'original IPC endpoint')
    sock.settimeout(remaining);anc=[]if fd is None else[(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[fd]))]
    n=sock.sendmsg([raw],anc);c.need(n==len(raw),'complete one-packet IPC send')

def receive(sock,*,deadline,budget):
    remaining=deadline-time.monotonic();c.need(remaining>0,'original IPC endpoint');sock.settimeout(remaining)
    budget.charge('read_bytes',MAX_MESSAGE+1)
    raw,anc,flags,address=sock.recvmsg(MAX_MESSAGE+1,socket.CMSG_SPACE(4*8))
    fds=[]
    try:
        for level,kind,data in anc:
            c.need(level==socket.SOL_SOCKET and kind==socket.SCM_RIGHTS,'only exact descriptor transport')
            a=array.array('i');a.frombytes(data[:len(data)-(len(data)%a.itemsize)]);fds.extend(a)
        c.need(not(flags&(socket.MSG_TRUNC|socket.MSG_CTRUNC))and 0<len(raw)<=MAX_MESSAGE and len(fds)<=1,'complete bounded IPC packet and at most one descriptor')
        for fd in fds:os.set_inheritable(fd,False)
        return c.parse(raw),fds[0]if fds else None
    except BaseException:
        for fd in fds:os.close(fd)
        raise

def fd_capture(fd,pin,budget,maximum):
    c.exact(pin,('bytes','sha256'));n=c.integer(pin['bytes'],0,maximum);c.digest(pin['sha256']);budget.charge('read_bytes',n+1)
    before=os.fstat(fd);c.need(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and before.st_size==n,'ordinary exact passed input descriptor')
    os.lseek(fd,0,os.SEEK_SET);parts=[];total=0
    while total<=n:
        budget.check_clock();part=os.read(fd,min(1048576,n+1-total))
        if not part:break
        total+=len(part);parts.append(part)
    raw=b''.join(parts);after=os.fstat(fd);fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_nlink')
    c.need(c.pin(raw)==pin and all(getattr(before,k)==getattr(after,k)for k in fields),'complete stable passed source body')
    return raw

class Output:
    def __init__(self,fd,budget,maximum):
        self.fd=fd;self.budget=budget;self.maximum=c.integer(maximum,1);self.total=0;self.hash=hashlib.sha256()
        s=os.fstat(fd);c.need(stat.S_ISREG(s.st_mode)and s.st_nlink==1 and s.st_size==0,'fresh owned output descriptor')
    def write(self,raw):
        c.need(type(raw)is bytes and self.total+len(raw)<=self.maximum,'bounded complete projection output');self.budget.charge('write_bytes',len(raw));view=memoryview(raw)
        while view:
            self.budget.check_clock();n=os.write(self.fd,view);c.need(n>0,'complete projected output write');view=view[n:]
        self.total+=len(raw);self.hash.update(raw);return len(raw)
    def flush(self):os.fsync(self.fd);self.budget.check_clock()
    def pin(self):self.flush();return {'bytes':self.total,'sha256':self.hash.hexdigest()}
