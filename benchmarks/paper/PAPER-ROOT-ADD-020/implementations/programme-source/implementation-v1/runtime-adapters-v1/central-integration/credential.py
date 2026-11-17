"""Receive one operator-owned FD; only the admitted parent reads its secret.

No broker is installed/started here. Broker identity/custody is a separate signed
deployment capability. No credential is serialized, hashed, logged or returned.
"""
import array
import fcntl
import os
import socket
import stat
import struct

def descriptor_metadata(mode,size,flags,seals,offset):
    # A sealed finite memfd cannot turn the parent's bounded os.read into a
    # blocking pipe/socket read. No key bytes are inspected to establish this.
    required=fcntl.F_SEAL_SEAL|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_GROW|fcntl.F_SEAL_WRITE
    u.need(stat.S_ISREG(mode) and type(size)is int and 0<size<=4096
           and flags&os.O_ACCMODE==os.O_RDONLY and seals&required==required and offset==0,
           'bounded read-only fully sealed credential memfd at offset zero required')

def receive(spec,job,reader):
    u.need(type(spec)is dict and set(spec)=={'socket_path','peer_uid','peer_gid','broker_source_digest'},'exact installed broker descriptor')
    path=u.absolute(spec['socket_path']);u.components(path)
    info=path.lstat();u.need(stat.S_ISSOCK(info.st_mode) and info.st_uid==spec['peer_uid'] and not stat.S_IMODE(info.st_mode)&0o007,
                            'private qualified broker socket required')
    u.need(type(spec['peer_uid'])is int and type(spec['peer_gid'])is int and spec['peer_uid']==0,'root-owned broker required')
    u.only_pin({'bytes':0,'sha256':spec['broker_source_digest']})
    request=u.canonical({'schema':'paper020_credential_fd_request_v1','run_id':job['run_id'],
                         'origin_ns':job['origin_ns'],'deadline_ns':job['deadline_ns']})
    sock=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET);received=[]
    try:
        sock.settimeout(max(0.000001,(reader.deadline-reader.tick())/1e9));sock.connect(str(path));reader.tick()
        peer=sock.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,struct.calcsize('3i'))
        pid,uid,gid=struct.unpack('3i',peer);u.need(pid>0 and (uid,gid)==(spec['peer_uid'],spec['peer_gid']),'broker peer identity differs')
        sock.sendall(request+b'\n');reader.tick()
        raw,ancillary,flags,_=sock.recvmsg(4096,socket.CMSG_SPACE(array.array('i').itemsize*2))
        for level,kind,data in ancillary:
            u.need(level==socket.SOL_SOCKET and kind==socket.SCM_RIGHTS,'unexpected broker ancillary data')
            fds=array.array('i');fds.frombytes(data);received.extend(fds)
        u.need(not flags and len(received)==1 and u.parse(raw)=={'request_digest':u.sha(request),'status':'credential_fd'},
               'exact credential descriptor transfer required')
        fd=received[0];u.need(fd>=3,'nonstandard credential FD required')
        info=os.fstat(fd);descriptor_metadata(info.st_mode,info.st_size,fcntl.fcntl(fd,fcntl.F_GETFL),
             fcntl.fcntl(fd,fcntl.F_GET_SEALS),os.lseek(fd,0,os.SEEK_CUR))
        os.set_inheritable(fd,False);reader.tick()
        received.clear();return fd
    finally:
        for fd in received:os.close(fd)
        sock.close()
