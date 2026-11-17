"""Actual owned endpoint return counts; no storage/network-byte conversion."""
import struct
import base64
from ach_resource_common import require, integer, token, bounded_encode, bounded_decode


class Endpoints:
    def __init__(self, selected, owner):
        self.selected = selected
        self.values = {name: {'read_bytes': 0, 'write_bytes': 0, 'attempts': 0,
                              'failed_attempts': 0, 'coverage': 'owned_positive_return_prefixes'}
                       for name in selected['endpoint_limits'] if selected['endpoint_owners'][name] == owner}
        self.active = {}; self.attempt_sequence = 0

    def begin(self, endpoint):
        require(endpoint in self.values, 'selected observer-owned endpoint')
        self.attempt_sequence += 1
        key = self.attempt_sequence
        self.active[key] = endpoint
        self.values[endpoint]['attempts'] += 1
        try:
            self.enforce(endpoint)
        except BaseException:
            self.end(key, failed=True)
            raise
        return key

    def charge(self, attempt, direction, count):
        require(attempt in self.active and direction in ('read_bytes', 'write_bytes'), 'live owned endpoint direction')
        integer(count)
        name = self.active[attempt]
        self.values[name][direction] += count
        self.enforce(name)

    def end(self, attempt, failed=False):
        require(attempt in self.active and type(failed) is bool, 'one actual endpoint attempt closure')
        name = self.active.pop(attempt)
        if failed:
            self.values[name]['failed_attempts'] += 1

    def enforce(self, name):
        for field, maximum in self.selected['endpoint_limits'][name].items():
            require(self.values[name][field] <= maximum, 'actual endpoint limit exceeded; prefix retained')

    def snapshot(self, *, closed=False):
        require(not closed or not self.active, 'all owned endpoint attempts closed')
        return {name: dict(value) for name, value in self.values.items()}


def _prefix(direction, requested, raw, disposition):
    return {'direction':direction,'requested_bytes':requested,'positive_return_bytes':len(raw),
            'observed_prefix_base64':base64.b64encode(raw).decode('ascii'),'disposition':disposition}


def send_bytes(sock, raw, endpoint, attempt, clock, phase):
    offset=0
    try:
        while offset < len(raw):
            clock.tick(phase)
            sock.settimeout(max(0.001,(getattr(clock,phase)-clock.tick(phase))/1e9))
            sent=sock.send(memoryview(raw)[offset:])
            require(type(sent) is int and 0<sent<=len(raw)-offset,'actual positive endpoint send return')
            offset+=sent  # Retain observed return before a charge/cutoff can fail.
            endpoint.charge(attempt,'write_bytes',sent)
    except BaseException as error:
        error.typed_io_prefix=_prefix('write_bytes',len(raw),raw[:offset],'failed_positive_return_prefix')
        raise


def receive_bytes(sock,count,endpoint,attempt,clock,phase):
    integer(count);parts=[];remaining=count
    try:
        while remaining:
            clock.tick(phase)
            sock.settimeout(max(0.001,(getattr(clock,phase)-clock.tick(phase))/1e9))
            raw=sock.recv(min(remaining,65536))
            require(type(raw) is bytes and len(raw)<=remaining,'actual bounded endpoint receive')
            if raw:parts.append(raw);remaining-=len(raw)
            endpoint.charge(attempt,'read_bytes',len(raw))
            require(raw,'incomplete endpoint frame')
        return b''.join(parts)
    except BaseException as error:
        error.typed_io_prefix=_prefix('read_bytes',count,b''.join(parts),'failed_observed_prefix')
        raise


def send_frame(sock,value,selected,endpoint,attempt,clock,phase):
    raw=bounded_encode(value,selected['encoding_limits']);header=struct.pack('!Q',len(raw));stage='header'
    record={'direction':'write_bytes','declared_body_bytes':len(raw),'header':None,'body':None,'disposition':'attempted'}
    try:
        send_bytes(sock,header,endpoint,attempt,clock,phase)
        record['header']=_prefix('write_bytes',8,header,'complete');stage='body'
        send_bytes(sock,raw,endpoint,attempt,clock,phase)
        return raw
    except BaseException as error:
        record[stage]=getattr(error,'typed_io_prefix',None)
        record['disposition']='failed';error.typed_transport_prefix=record
        raise


def receive_frame(sock,selected,endpoint,attempt,clock,phase):
    stage='header';record={'direction':'read_bytes','declared_body_bytes':None,'header':None,'body':None,'disposition':'attempted'}
    try:
        header=receive_bytes(sock,8,endpoint,attempt,clock,phase)
        record['header']=_prefix('read_bytes',8,header,'complete')
        size=struct.unpack('!Q',header)[0];record['declared_body_bytes']=size;stage='extent'
        require(size<=selected['encoding_limits']['bytes'],'frame extent before receive')
        stage='body';raw=receive_bytes(sock,size,endpoint,attempt,clock,phase)
        record['body']=_prefix('read_bytes',size,raw,'complete');stage='decode'
        value=bounded_decode(raw,selected['encoding_limits'])
        return value,raw
    except BaseException as error:
        if stage in ('header','body'):record[stage]=getattr(error,'typed_io_prefix',None)
        record['disposition']='undecodable' if stage=='decode' else 'failed_'+stage
        error.typed_transport_prefix=record
        raise
