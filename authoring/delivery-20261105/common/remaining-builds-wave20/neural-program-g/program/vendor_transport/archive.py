"""Single-file Docker archive over local AF_UNIX; bounded raw transport only.

No Docker CLI artifact stdout, tar extraction, pickle, native readers, network
endpoint, automatic API negotiation or scientific interpretation is used.
"""
import hashlib
import os
from pathlib import Path, PurePosixPath
import socket
import stat
import time
from urllib.parse import quote
from .engine import need, path, cleanup_all, finish_cleanup
from .bounds import relative, fsync_dir


class Wire:
    def __init__(self,sock,deadline,meter,ceiling):
        self.sock,self.deadline,self.meter,self.ceiling=sock,deadline,meter,ceiling
        self.buffer=bytearray();self.used=0
    def more(self):
        left=self.deadline-time.monotonic();need(left>0,'Archive original deadline')
        self.sock.settimeout(left)
        wanted=min(65536,self.ceiling+1-self.used);self.meter.ensure_read(wanted)
        data=self.sock.recv(wanted)
        self.used+=len(data);self.meter.read(len(data));need(self.used<=self.ceiling,'Archive wire byte ceiling')
        need(data,'Premature archive wire EOF');self.buffer.extend(data)
    def exact(self,n):
        need(type(n) is int and 0<=n<=65536,'Bounded archive read')
        while len(self.buffer)<n:self.more()
        raw=bytes(self.buffer[:n]);del self.buffer[:n];return raw
    def line(self,cap):
        while True:
            end=self.buffer.find(b'\r\n')
            if end>=0:
                need(end+2<=cap,'Bounded HTTP line');raw=bytes(self.buffer[:end]);del self.buffer[:end+2];return raw
            need(len(self.buffer)<cap,'Bounded HTTP line');self.more()


class Entity:
    def __init__(self,wire,headers,ceiling):
        self.wire,self.ceiling=wire,ceiling;self.used=0;self.chunk_left=0;self.ended=False
        transfer=headers.get(b'transfer-encoding');length=headers.get(b'content-length')
        need(not (transfer and length),'Unambiguous HTTP framing')
        need(transfer==b'chunked' or (transfer is None and length is not None and length.isdigit()),
             'Explicit bounded HTTP framing')
        self.chunked=transfer==b'chunked';self.remaining=None if self.chunked else int(length)
        need(self.remaining is None or self.remaining<=ceiling,'Archive advertised extent ceiling')
    def read(self,n):
        need(0<n<=65536,'Bounded entity read')
        if self.ended:return b''
        if self.chunked:
            if self.chunk_left==0:
                line=self.wire.line(80)
                need(line and all(x in b'0123456789abcdefABCDEF' for x in line),'Plain bounded chunk length')
                self.chunk_left=int(line,16)
                need(self.used+self.chunk_left<=self.ceiling,'Archive chunk cumulative cap')
                if self.chunk_left==0:
                    need(self.wire.line(2)==b'','No HTTP trailers');self.ended=True;return b''
            size=min(n,self.chunk_left);raw=self.wire.exact(size);self.chunk_left-=size
            if self.chunk_left==0:need(self.wire.exact(2)==b'\r\n','Exact HTTP chunk terminator')
        else:
            if self.remaining==0:self.ended=True;return b''
            size=min(n,self.remaining);raw=self.wire.exact(size);self.remaining-=size
        self.used+=len(raw);need(self.used<=self.ceiling,'Archive entity cap');return raw
    def exact(self,n):
        parts=[];total=0
        while total<n:
            part=self.read(min(65536,n-total));need(part,'Premature tar EOF');parts.append(part);total+=len(part)
        return b''.join(parts)


def octal(raw):
    value=raw.strip(b'\0 ')
    need(value and all(c in b'01234567' for c in value),'Ordinary tar octal')
    return int(value,8)


def tar_header(raw):
    need(len(raw)==512 and raw!=b'\0'*512,'One ordinary tar member')
    need(octal(raw[148:156])==sum(raw[:148])+8*32+sum(raw[156:]),'Tar checksum')
    def text(raw):
        head,_,tail=raw.partition(b'\0');need(not tail.strip(b'\0'),'Canonical tar string')
        return head.decode('utf-8')
    name=text(raw[:100]);prefix=text(raw[345:500])
    if prefix:name=prefix+'/'+name
    return {'name':name,'size':octal(raw[124:136]),'type':raw[156:157],
            'link':text(raw[157:257]),'mode':octal(raw[100:108])}


def pax(raw):
    """Permit bounded local metadata, never links/sparse/global overrides."""
    result={};at=0
    while at<len(raw):
        space=raw.find(b' ',at);need(space>at and raw[at:space].isdigit(),'PAX record length')
        n=int(raw[at:space]);need(n>space-at+3 and at+n<=len(raw),'Exact bounded PAX record')
        entry=raw[space+1:at+n];need(entry.endswith(b'\n') and b'=' in entry,'PAX key/value')
        key,value=entry[:-1].split(b'=',1);need(key not in result and key in (b'path',b'mtime',b'atime',b'ctime'),'No sparse/link/global PAX fields')
        result[key]=value;at+=n
    return result


def receive_one(entity,name,expected_bytes,write):
    h=tar_header(entity.exact(512));attrs={}
    if h['type']==b'x':
        need(h['size']<=8192,'Bounded local PAX metadata');attrs=pax(entity.exact(h['size']))
        need(not entity.exact((-h['size'])%512).strip(b'\0'),'PAX zero padding')
        h=tar_header(entity.exact(512))
    effective=attrs.get(b'path',h['name'].encode()).decode('utf-8')
    need(effective==PurePosixPath(name).name and h['type'] in (b'0',b'\0') and h['link']=='',
         'Exact sole regular archive basename; no links or extra entries')
    need(h['size']==expected_bytes and h['mode'] & 0o7000==0,'Exact ordinary extent/mode')
    digest=hashlib.sha256();left=expected_bytes
    while left:
        raw=entity.exact(min(left,65536));write(raw);digest.update(raw);left-=len(raw)
    need(not entity.exact((-expected_bytes)%512).strip(b'\0'),'Zero payload padding')
    need(entity.exact(1024)==b'\0'*1024,'Two tar end blocks')
    extra=0
    while True:
        raw=entity.read(65536)
        if not raw:break
        extra+=len(raw);need(extra<=10240 and not raw.strip(b'\0'),'Only bounded terminal tar padding')
    need(not entity.wire.buffer,'No extra framed HTTP bytes')
    return {'bytes':expected_bytes,'sha256':digest.hexdigest()}


def capture(socket_path,container_id,name,expected_bytes,destination,meter,deadline):
    """Future direct local API transfer, exclusive checked/fsynced host publication."""
    import re
    relative(name);need(re.fullmatch('[0-9a-f]{64}',container_id),'Exact owned holder ID')
    socket_path=path(socket_path);before=socket_path.stat();need(stat.S_ISSOCK(before.st_mode),'Local Unix socket only')
    destination=path(destination);need(type(expected_bytes) is int and expected_bytes>=0,'Exact inventoried extent')
    started=time.monotonic();meter.write(expected_bytes)
    sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);fd=None;identity=None;wire=None;primary=None
    try:
        sock.settimeout(max(.001,deadline-time.monotonic()));sock.connect(str(socket_path))
        request=('GET /v1.41/containers/'+container_id+'/archive?path='+quote('/capture/'+name,safe='')+
                 ' HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\nAccept-Encoding: identity\r\n\r\n').encode('ascii')
        sock.sendall(request);wire=Wire(sock,deadline,meter,expected_bytes+131072)
        status=wire.line(256);need(status in (b'HTTP/1.1 200 OK',b'HTTP/1.0 200 OK'),'Successful local archive response')
        headers={};header_bytes=len(status)+2
        while True:
            line=wire.line(16384-header_bytes);header_bytes+=len(line)+2
            if not line:break
            need(b':' in line and not line[:1].isspace(),'Ordinary HTTP header')
            key,value=line.split(b':',1);key=key.lower();need(key not in headers,'No duplicate HTTP headers')
            headers[key]=value.strip()
        need(headers.get(b'content-encoding',b'identity')==b'identity','No compressed archive')
        entity=Entity(wire,headers,expected_bytes+32768)
        fd=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        s=os.fstat(fd);identity=(s.st_dev,s.st_ino)
        def write(raw):
            at=0
            while at<len(raw):
                meter.tick();need(time.monotonic()<deadline,'Archive phase deadline')
                n=os.write(fd,memoryview(raw)[at:]);need(n>0,'Checked streaming file write');at+=n;meter.wrote(n)
        result=receive_one(entity,name,expected_bytes,write)
        os.fsync(fd);closing,fd=fd,None;os.close(closing);fsync_dir(destination.parent)
        after=socket_path.stat();need((before.st_dev,before.st_ino)==(after.st_dev,after.st_ino),'Same local socket')
        need(time.monotonic()<deadline,'Complete capture before original phase cutoff')
        return {'file':result,'wire_bytes':wire.used,'seconds':time.monotonic()-started,'transport':'local_unix_archive_v1.41'}
    except BaseException as error:
        primary=error;actions=[]
        if fd is not None:actions.append(('archive.output.close',lambda:os.close(fd)))
        if identity is not None:
            def remove_owned():
                try:s=destination.lstat()
                except FileNotFoundError:return
                need((s.st_dev,s.st_ino)==identity and stat.S_ISREG(s.st_mode),'Archive cleanup refused replaced/unowned inode')
                destination.unlink()
            actions.append(('archive.output.remove_owned',remove_owned))
            actions.append(('archive.output.parent_fsync',lambda:fsync_dir(destination.parent)))
        cleanup_all(actions,primary)
        raise
    finally:finish_cleanup([('archive.socket.close',sock.close)],primary)
