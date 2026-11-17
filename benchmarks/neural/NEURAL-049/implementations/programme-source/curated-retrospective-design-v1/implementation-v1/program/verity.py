"""Exact accepted fs-verity kernel primitives; actual backend remains unqualified."""
from pathlib import Path
import os,stat,struct,sys,fcntl
from core import need,integer,descriptor,parent_chain,stamp,close_preserving,sync_dir
BACKEND="linux-x86_64-fsverity-sha256-4096-v1"
ENABLE=(1<<30)|(128<<16)|(ord("f")<<8)|133
MEASURE=(3<<30)|(4<<16)|(ord("f")<<8)|134

def supported():
    need(sys.platform=='linux' and sys.byteorder=='little' and os.uname().machine=='x86_64',
         'actual selected Linux x86_64 fs-verity ABI; no fallback')

def measured(fd,budget):
    budget.tick();budget.reserve_write(68);budget.reserve_read(68)
    data=bytearray(struct.pack('<HH',0,64)+bytes(64))
    result=fcntl.ioctl(fd,MEASURE,data,True);budget.tick()
    algorithm,size=struct.unpack('<HH',data[:4])
    need(type(result)is int and result==0 and algorithm==1 and size==32,'actual SHA256 fs-verity measurement')
    return {'algorithm':'sha256','digest':bytes(data[4:36]).hex()}

def identity(st):
    return {'device':st.st_dev,'inode':st.st_ino,'bytes':st.st_size,
            'mtime_ns':st.st_mtime_ns,'ctime_ns':st.st_ctime_ns}

def ordinary(st,expected):
    need(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_size==expected['bytes'],'ordinary exact single-link gallery file')

def enable(path,expected,budget,kernel_read,kernel_write):
    """Cooperative-clock syscall, not a hard-kill or crash-atomic guarantee."""
    supported();path=parent_chain(path);descriptor(expected)
    budget.reserve_read(integer(kernel_read,expected['bytes']));budget.reserve_write(integer(kernel_write,1)+128)
    budget.tick();fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);ordinary(before,expected)
        need(before.st_mode&0o200 and stamp(before)==stamp(os.lstat(path)),
             'closed writable descriptors, owner permission retained for enable, exact name')
        arg=struct.pack('<IIIIQIIQ11Q',1,1,4096,0,0,0,0,0,*([0]*11))
        need(len(arg)==128,'exact enabled ABI structure')
        result=fcntl.ioctl(fd,ENABLE,arg);budget.tick()
        need(type(result)is int and result==0,'actual enable result; no retry on existing/unknown state')
        after=os.fstat(fd);ordinary(after,expected)
        need((before.st_dev,before.st_ino,before.st_size)==(after.st_dev,after.st_ino,after.st_size)
             and stamp(after)==stamp(os.lstat(path)),'same image through declared enable transition')
        digest=measured(fd,budget)
        os.fchmod(fd,0o444);os.fsync(fd);budget.tick()
        sealed=os.fstat(fd);ordinary(sealed,expected)
        need(sealed.st_mode&0o222==0 and (sealed.st_dev,sealed.st_ino)==(before.st_dev,before.st_ino)
             and stamp(sealed)==stamp(os.lstat(path)),'same final sealed inode after declared chmod transition')
        result={'backend':BACKEND,'measurement':digest,'identity':identity(sealed)}
    finally:close_preserving(fd)
    sync_dir(path.parent);budget.tick()
    need(identity(os.lstat(path))==result['identity'],'sealed gallery name unchanged after close')
    budget.tick();return result

def verify(path,expected,kernel,budget):
    supported();path=parent_chain(path);descriptor(expected)
    need(type(kernel)is dict and kernel.get('backend')==BACKEND,'independently qualified fs-verity descriptor')
    budget.tick();fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);ordinary(before,expected)
        need(before.st_mode&0o222==0 and identity(before)==kernel['identity']
             and stamp(before)==stamp(os.lstat(path)),'same qualified immutable gallery name/inode')
        actual=measured(fd,budget);need(actual==kernel['measurement'],'actual kernel-enforced content measurement')
        need(stamp(before)==stamp(os.fstat(fd))==stamp(os.lstat(path)),'same gallery descriptor/name after measurement')
        budget.tick()
    finally:close_preserving(fd)
    need(identity(os.lstat(path))==kernel['identity'],'gallery name unchanged after close');budget.tick()
    return kernel['measurement']

