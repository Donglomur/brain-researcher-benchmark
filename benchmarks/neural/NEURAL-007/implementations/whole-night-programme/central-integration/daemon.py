"""Complete bounded read-only Engine API v1.51 observations, never a daemon call on import."""
import os
import re
import socket
import stat
import struct
import time
from .core import need, number, integer, path, decode

LABEL = 'org.neurobench.osl-program-owner'
PATHS = {'container':'/v1.51/containers/json?all=true&size=false', 'volume':'/v1.51/volumes'}


def endpoint_identity(endpoint):
    need(type(endpoint) is dict and set(endpoint) == {'path','device','inode','uid','gid','peer_pid',
        'peer_uid','peer_gid','service_identity','metadata_namespace_qualified'}, 'Exact selected endpoint identity')
    need(endpoint['metadata_namespace_qualified'] is True and type(endpoint['service_identity']) is str
         and 0 < len(endpoint['service_identity']) <= 256, 'Independently qualified service and metadata scope')
    for key in ('device','inode','uid','gid','peer_pid','peer_uid','peer_gid'):
        integer(endpoint[key], 1 if key in ('inode','peer_pid') else 0)
    p = path(endpoint['path']); info = p.lstat()
    need(stat.S_ISSOCK(info.st_mode), 'Qualified ordinary Unix socket')
    need((info.st_dev,info.st_ino,info.st_uid,info.st_gid) ==
         tuple(endpoint[k] for k in ('device','inode','uid','gid')), 'Same selected endpoint inode')
    return p


class Wire:
    def __init__(self, connection, end, meter, header_cap, body_cap):
        self.connection, self.end, self.meter = connection, end, meter
        self.header_cap, self.body_cap = integer(header_cap, 1), integer(body_cap, 1)
        self.buffer = bytearray(); self.wire_bytes = self.body_bytes = 0
        self.max_wire = header_cap + 8 * body_cap + 65536

    def take(self, count):
        need(count >= 0, 'Nonnegative exact HTTP extent')
        while len(self.buffer) < count:
            need(time.monotonic() < self.end, 'HTTP original closeout')
            room = self.max_wire - self.wire_bytes
            need(room > 0, 'Complete HTTP wire bound')
            self.meter.reserve_read(min(65536, room))
            self.connection.settimeout(self.end-time.monotonic())
            raw = self.connection.recv(min(65536, room))
            self.meter.read(len(raw)); self.wire_bytes += len(raw)
            need(raw, 'HTTP premature EOF')
            self.buffer.extend(raw)
        result = bytes(self.buffer[:count]); del self.buffer[:count]
        return result

    def line(self, cap):
        result = bytearray()
        while not result.endswith(b'\r\n'):
            need(len(result) < cap, 'Bounded HTTP line')
            result.extend(self.take(1))
        return bytes(result[:-2])

    def body_piece(self, size):
        need(self.body_bytes + size <= self.body_cap, 'Complete encoded API body ceiling')
        self.body_bytes += size
        return self.take(size)

    def response(self):
        first = self.line(self.header_cap)
        need(first in (b'HTTP/1.1 200 OK', b'HTTP/1.0 200 OK'), 'Exact successful HTTP status')
        headers = {}; used = len(first)+2
        while True:
            line = self.line(self.header_cap-used); used += len(line)+2
            need(used <= self.header_cap, 'Complete HTTP header ceiling')
            if not line:
                break
            need(not line.startswith((b' ',b'\t')) and b':' in line, 'Unfolded HTTP header')
            key, value = line.split(b':',1)
            need(re.fullmatch(rb'[!#$%&\'*+.^_`|~0-9A-Za-z-]+',key), 'HTTP header token')
            key=key.lower(); value=value.strip()
            need(key not in headers and b'\r' not in value and b'\n' not in value, 'Unique HTTP header')
            headers[key]=value
        need(headers.get(b'content-type',b'').lower() in
             (b'application/json', b'application/json; charset=utf-8'), 'JSON API content type')
        need(b'content-encoding' not in headers and b'trailer' not in headers, 'No encoded expansion or trailers')
        length, transfer = headers.get(b'content-length'), headers.get(b'transfer-encoding')
        need((length is None) != (transfer is None), 'Exactly one complete HTTP framing mode')
        if length is not None:
            need(re.fullmatch(rb'0|[1-9][0-9]{0,18}',length), 'Canonical HTTP body extent')
            body = self.body_piece(int(length))
        else:
            need(transfer == b'chunked', 'Only exact chunked framing')
            chunks = []; chunk_count = 0
            while True:
                line=self.line(128); chunk_count+=1
                need(chunk_count <= self.body_cap+1 and re.fullmatch(rb'[0-9A-Fa-f]{1,16}',line),
                     'Bounded exact chunk size without extension')
                size=int(line,16)
                if size == 0:
                    need(self.take(2)==b'\r\n','No unexpected chunk trailers'); break
                chunks.append(self.body_piece(size))
                need(self.take(2)==b'\r\n','Complete chunk terminator')
            body=b''.join(chunks)
        need(not self.buffer, 'No trailing buffered response bytes')
        self.connection.settimeout(self.end-time.monotonic())
        self.meter.reserve_read(1)
        extra=self.connection.recv(1); self.meter.read(len(extra)); self.wire_bytes+=len(extra)
        need(extra==b'', 'Connection-close EOF after exactly one API response')
        need(time.monotonic()<self.end,'Complete HTTP EOF before closeout')
        return body


def projected(raw, kind, row_cap, depth=64, nodes=2000000):
    value=decode(raw,depth,nodes)
    if kind == 'volume':
        need(type(value) is dict and 'Volumes' in value and 'Warnings' in value,
             'Required v1.51 volume fields')
        need(value['Warnings'] is None or type(value['Warnings']) is list and not value['Warnings'],
             'No incomplete inventory warnings')
        rows=[] if value['Volumes'] is None else value['Volumes']
    else:
        need(kind=='container','Known API resource kind'); rows=value
    need(type(rows) is list and len(rows)<=row_cap,'Complete bounded API inventory')
    result=[]; identities=set(); aliases=set()
    for row in rows:
        need(type(row) is dict,'API inventory row')
        labels=row.get('Labels')
        need(labels is None or type(labels) is dict,'API label map')
        owner=None if labels is None else labels.get(LABEL)
        need(owner is None or type(owner) is str and len(owner)<=512 and '\0' not in owner,'Selected owner value')
        if kind=='container':
            ident=row.get('Id'); names=row.get('Names')
            need(type(ident) is str and re.fullmatch('[0-9a-f]{64}',ident),'Full container ID')
            need(type(names) is list and names and len(names)<=128,'Complete returned container names')
            normalized=[]
            for name in names:
                need(type(name) is str and name.startswith('/') and len(name)<=512
                     and re.fullmatch('/[A-Za-z0-9][A-Za-z0-9_.\-/]*',name), 'Exact container name/alias')
                normalized.append(name[1:])
            need(len(set(normalized))==len(normalized),'No duplicate names')
            need(not aliases.intersection(normalized),'Unambiguous cross-container aliases')
            aliases.update(normalized)
            item={'id':ident,'names':normalized,'owner':owner}
        else:
            ident=row.get('Name')
            need(type(ident) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,511}',ident),'Exact volume name')
            item={'name':ident,'owner':owner}
        need(ident not in identities,'No duplicate API identities'); identities.add(ident); result.append(item)
    return result


def request(endpoint, kind, end, profile, meter):
    """Concrete Unix transport. Inputs must already be independently qualified."""
    p=endpoint_identity(endpoint); started=time.monotonic()
    need(number(end) and started<end<=meter.end,'Original API closeout deadline')
    connection=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    try:
        connection.settimeout(end-time.monotonic()); connection.connect(str(p))
        need(hasattr(socket,'SO_PEERCRED'),'Qualified Linux Unix peer credentials')
        credentials=struct.unpack('3i',connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
        need(credentials==tuple(endpoint[k] for k in ('peer_pid','peer_uid','peer_gid')),'Exact qualified peer process')
        command=('GET '+PATHS[kind]+' HTTP/1.1\r\nHost: localhost\r\nAccept: application/json\r\nConnection: close\r\n\r\n').encode('ascii')
        connection.settimeout(end-time.monotonic()); connection.sendall(command)
        wire=Wire(connection,end,meter,profile['header_bytes'],profile['body_bytes'])
        body=wire.response()
        projection=projected(body,kind,profile['rows'],meter.depth,meter.nodes)
        # Raw body is transient only; no body pin or arbitrary fields in output.
        result={'kind':kind,'started':started,'ended':time.monotonic(),'wire_bytes':wire.wire_bytes,
            'body_bytes':len(body),'complete_framing_and_eof':True,'rows':projection,
            'service_identity':endpoint['service_identity'],'socket':str(p)}
        endpoint_identity(endpoint)
        need(time.monotonic()<end,'Identity rechecked before closeout')
        return result
    finally:
        connection.close()


def absent(owned, containers, volumes, creators_closed):
    """Empty sequential lists never cure unknown creation/creator custody."""
    need(creators_closed is True, 'Independently completed creator/ACK dispositions first')
    need(type(owned) is list,'Complete owned-resource set')
    for resource in owned:
        need(type(resource) is dict and set(resource)=={'kind','name','owner','id','creation_complete'},
             'Exact admitted owned resource')
        need(resource['creation_complete'] is True,'No unknown or pending creation')
        rows=containers if resource['kind']=='container' else volumes
        need(resource['kind'] in ('container','volume'),'Exact resource kind')
        for row in rows:
            names=row['names'] if resource['kind']=='container' else [row['name']]
            need(resource['name'] not in names and resource['owner']!=row['owner']
                 and (resource['kind']!='container' or resource['id']!=row['id']),
                 'Owned resource remains by ID, name or owner, including mismatched labels')
    return {'all_owned_resources_absent':True,'creators_independently_closed':True,
            'atomic_snapshot':False,'external_future_creation_excluded':False}
