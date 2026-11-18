"""Fixed read-only Linux network diagnostic; importing this file performs no I/O.

Only main() supplies live candidate adapters. Generated tests inject every OS
adapter. Complete means collection complete, never network-qualified or atomic.
ABI constants/layouts: Linux v6.12 uapi netlink/rtnetlink/if_link/if_addr headers.
"""
import hashlib
import json
import math
import os
import re
import resource
import signal
import socket
import struct
import sys
import time

OUTPUT_CAP = 262144
FINAL_RESERVE = 8192
RECEIVE_CAP = 1048576
DATAGRAM_CAP = 65536
DATAGRAM_COUNT_CAP = 128
MESSAGE_COUNT_CAP = 2048
ATTR_COUNT_CAP = 128
STATUS_CAP = 16384
WALL_SECONDS = 20
DUMP_SECONDS = 1
NLM_F_REQUEST_DUMP = 0x301
NLM_F_MULTI = 2
NLM_F_DUMP_INTR = 0x10
NLMSG_ERROR, NLMSG_DONE, NLMSG_OVERRUN = 2,3,4
HEADER = struct.Struct('=IHHII')
LINK = struct.Struct('=BBHiII')
ADDRESS = struct.Struct('=BBBBI')
ROUTE = struct.Struct('=BBBBBBBBI')
ATTRIBUTE = struct.Struct('=HH')
SCHEDULE = (('links_before',18,16,0,64),('addresses_ipv4',22,20,2,256),
            ('addresses_ipv6',22,20,10,256),('routes_ipv4',26,24,2,256),
            ('routes_ipv6',26,24,10,256),('links_after',18,16,0,64))
STATUS_KEYS = ('CapInh','CapPrm','CapEff','CapBnd','CapAmb','NoNewPrivs','Seccomp')


class ProbeFailure(Exception):
    def __init__(self,category):
        self.category = category
        super().__init__(category)


def require(ok,category):
    if not ok: raise ProbeFailure(category)


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')


def align4(length): return (length+3)&~3


def attributes(raw,offset):
    """Offsets reference complete retained frame_hex; all unknown types survive."""
    result = []; cursor = offset
    while cursor < len(raw):
        require(len(result) < ATTR_COUNT_CAP and len(raw)-cursor >= 4,'attribute_count_or_short_header')
        length,kind = ATTRIBUTE.unpack_from(raw,cursor)
        require(length >= 4 and cursor+align4(length) <= len(raw),'attribute_length_or_alignment')
        result.append({'offset':cursor,'length':length,'type_raw':kind,'type':kind&0x3fff,
                       'nested':bool(kind&0x8000),'network_byteorder':bool(kind&0x4000)})
        cursor += align4(length)
    require(cursor == len(raw),'attribute_tail')
    return result


def attr_payload(raw,attrs,kind,*,required=False):
    found = [v for v in attrs if v['type'] == kind]
    require(len(found) <= 1,'ambiguous_selected_attribute')
    if not found:
        require(not required,'missing_selected_attribute'); return None,None
    item = found[0]
    require(not item['nested'],'selected_scalar_attribute_is_nested')
    return raw[item['offset']+4:item['offset']+item['length']],item


def scalar(raw,attrs,kind,width,*,required=False):
    data,item = attr_payload(raw,attrs,kind,required=required)
    if data is None:return None
    require(len(data) == width,'selected_scalar_attribute_width')
    return int.from_bytes(data,'big' if item['network_byteorder'] else sys.byteorder)


def address_hex(raw,attrs,kind,family):
    data,_ = attr_payload(raw,attrs,kind)
    if data is None:return None
    require(len(data) == (4 if family == 2 else 16),'selected_address_width')
    return data.hex()


def parse_record(frame,message_type,family):
    """Parse only declared fixed fields; raw frame retains everything else."""
    payload = frame[HEADER.size:]
    if message_type == 16:
        require(len(payload) >= LINK.size,'short_link_header')
        fam,pad,hardware,index,flags,change = LINK.unpack_from(payload)
        require(fam == family and index > 0,'link_family_or_index')
        attrs = attributes(frame,HEADER.size+LINK.size)
        name,item = attr_payload(frame,attrs,3,required=True)
        require(not item['network_byteorder'] and 2 <= len(name) <= 16 and name[-1:] == b'\0' and
                b'\0' not in name[:-1],'interface_name_encoding')
        try: name_text = name[:-1].decode('utf-8')
        except UnicodeError:raise ProbeFailure('unsupported_non_utf8_interface_name') from None
        parsed = {'family':fam,'pad':pad,'index':index,'name':name_text,'type':hardware,'flags':flags,
                  'change':change,'operstate':scalar(frame,attrs,16,1,required=True),
                  'MTU':scalar(frame,attrs,4,4,required=True)}
    elif message_type == 20:
        require(len(payload) >= ADDRESS.size,'short_address_header')
        fam,prefix,flags,scope,index = ADDRESS.unpack_from(payload)
        require(fam == family and index > 0 and prefix <= (32 if fam == 2 else 128),'address_header_scope')
        attrs = attributes(frame,HEADER.size+ADDRESS.size)
        parsed = {'family':fam,'index':index,'prefix_length':prefix,'flags_header':flags,'scope':scope,
                  'flags_attribute':scalar(frame,attrs,8,4),
                  'address_hex':address_hex(frame,attrs,1,fam),'local_hex':address_hex(frame,attrs,2,fam)}
    elif message_type == 24:
        require(len(payload) >= ROUTE.size,'short_route_header')
        fam,dst,src,tos,table,protocol,scope,kind,flags = ROUTE.unpack_from(payload)
        require(fam == family and dst <= (32 if fam == 2 else 128) and src <= (32 if fam == 2 else 128),
                'route_header_scope')
        attrs = attributes(frame,HEADER.size+ROUTE.size)
        extended_table = scalar(frame,attrs,15,4)
        parsed = {'family':fam,'destination_prefix_length':dst,'source_prefix_length':src,'tos':tos,
                  'table_header':table,'table_attribute':extended_table,
                  'table_effective':table if extended_table is None else extended_table,
                  'protocol':protocol,'scope':scope,'type':kind,'flags':flags,
                  'output_interface_index':scalar(frame,attrs,4,4),'input_interface_index':scalar(frame,attrs,3,4),
                  'destination_hex':address_hex(frame,attrs,1,fam),'source_hex':address_hex(frame,attrs,2,fam),
                  'gateway_hex':address_hex(frame,attrs,5,fam),'preferred_source_hex':address_hex(frame,attrs,7,fam)}
    else:raise ProbeFailure('unexpected_record_type')
    return parsed,attrs


def request_bytes(request_type,family,seq,port):
    require(type(seq) is int and 1 <= seq <= 6 and type(port) is int and 0 < port < 2**32,'request_identity')
    if request_type == 18 and family == 0:payload = LINK.pack(0,0,0,0,0,0)
    elif request_type == 22 and family in (2,10):payload = ADDRESS.pack(family,0,0,0,0)
    elif request_type == 26 and family in (2,10):payload = ROUTE.pack(family,0,0,0,0,0,0,0,0)
    else:raise ProbeFailure('mutation_or_unlisted_request_prohibited')
    return HEADER.pack(HEADER.size+len(payload),request_type,NLM_F_REQUEST_DUMP,seq,port)+payload


def parse_status(raw,eof):
    require(type(raw) is bytes and len(raw) <= STATUS_CAP and eof is True,'status_not_bounded_EOF')
    try: lines = raw.decode('ascii').splitlines()
    except UnicodeError:raise ProbeFailure('status_non_ascii') from None
    selected = {}; original = {}
    for line in lines:
        if ':' not in line:continue
        key,value = line.split(':',1)
        if key not in STATUS_KEYS:continue
        require(key not in selected,'duplicate_status_field')
        value = value.strip()
        require(bool(re.fullmatch('[0-9a-fA-F]{1,64}' if key.startswith('Cap') else '[0-9]{1,10}',value)),
                'status_field_encoding')
        selected[key] = value; original[key] = line
    require(set(selected) == set(STATUS_KEYS),'missing_status_field')
    return {'selected_raw_lines':original,'selected_values':selected,'source_bytes':len(raw),
            'source_sha256':hashlib.sha256(raw).hexdigest(),'EOF_observed':True,'capability_policy_inferred':False}


def checked_names(value):
    require(type(value) is list and len(value) <= 64,'if_nameindex_count')
    result = []
    for item in value:
        require(type(item) in (tuple,list) and len(item) == 2 and type(item[0]) is int and item[0] > 0 and
                type(item[1]) is str and 0 < len(item[1].encode('utf-8')) <= 15 and '\0' not in item[1],
                'if_nameindex_shape')
        result.append([item[0],item[1]])
    require(len({v[0] for v in result}) == len(result) == len({v[1] for v in result}),'if_nameindex_duplicate')
    return sorted(result)


class Collector:
    def __init__(self,clock):
        self.clock = clock; self.started = clock()
        self.result = {'schema':'dosei_network_state_diagnostic_v1','status':'diagnostic_incomplete',
            'collection_complete':False,'network_qualified':False,'atomic_snapshot':False,'retry_count':0,
            'byteorder':sys.byteorder,'socket_family':'AF_NETLINK','netlink_protocol':'NETLINK_ROUTE',
            'requested_route_table':0,'routing_rules_collected':False,
            'limits':{'wall_seconds':20,'per_dump_seconds':1,'receive_bytes':RECEIVE_CAP,
                      'datagrams':DATAGRAM_COUNT_CAP,'messages':MESSAGE_COUNT_CAP,'output_bytes':OUTPUT_CAP,
                      'links_per_dump':64,'addresses_or_routes_per_family':256},
            'socket_cleanup_errors':[],'dumps':[],
            'counters':{'receive_requested_charge_bytes':0,'observed_receive_bytes':0,'unknown_receive_grant_bytes':0,
                        'datagrams':0,'messages':0,'send_requested_bytes':0,'send_confirmed_bytes':0},
            'kernel_discarded_or_physical_IO_bytes_not_measured':True,
            'stability_projection_fields':['index','name','type','flags','operstate','MTU']}

    def check(self,deadline=None):
        now = self.clock()
        require(type(now) in (int,float) and math.isfinite(now) and now >= self.started,'clock_invalid')
        remaining = min(self.started+WALL_SECONDS,deadline if deadline is not None else self.started+WALL_SECONDS)-now
        require(remaining > 0,'deadline_exceeded'); return remaining

    def fit(self):
        require(len(encoded(self.result)) <= OUTPUT_CAP-FINAL_RESERVE,'diagnostic_output_capacity')

    def dump(self,factory,spec,seq):
        name,request_type,response_type,family,item_cap = spec; self.check()
        record = {'name':name,'family':family,'records':[],'datagrams':[],'done':None,'complete':False}
        self.result['dumps'].append(record)
        sock = None; primary = None; deadline = self.clock()+DUMP_SECONDS
        try:
            sock = factory(); self.check(deadline); sock.settimeout(self.check(deadline))
            sock.bind((0,0)); local = sock.getsockname()
            require(type(local) in (tuple,list) and len(local) == 2 and type(local[0]) is int and
                    0 < local[0] < 2**32 and local[1] == 0,'local_netlink_port_or_groups')
            port = local[0]; request = request_bytes(request_type,family,seq,port)
            record.update(sequence=seq,local_port=port,request_hex=request.hex())
            counts = self.result['counters']; counts['send_requested_bytes'] += len(request)
            sent = sock.sendto(request,(0,0)); require(type(sent) is int and sent == len(request),'request_send_incomplete')
            counts['send_confirmed_bytes'] += sent
            done = False
            while not done:
                sock.settimeout(self.check(deadline))
                require(counts['datagrams'] < DATAGRAM_COUNT_CAP,'datagram_count_cap')
                allowance = min(DATAGRAM_CAP,RECEIVE_CAP-counts['receive_requested_charge_bytes'])
                require(allowance > 0,'receive_byte_cap')
                counts['receive_requested_charge_bytes'] += allowance
                counts['unknown_receive_grant_bytes'] += allowance
                data,ancillary,flags,sender = sock.recvmsg(allowance,0)
                require(type(data) is bytes and len(data) <= allowance,'recv_return_shape')
                counts['observed_receive_bytes'] += len(data); counts['datagrams'] += 1
                counts['unknown_receive_grant_bytes'] -= allowance
                counts['receive_requested_charge_bytes'] -= allowance-len(data)
                diagnostic = {'ordinal':len(record['datagrams']),'bytes':len(data),
                    'sha256':hashlib.sha256(data).hexdigest(),'sender':list(sender),'flags':flags}
                record['datagrams'].append(diagnostic)
                # Reserve bounded failure provenance even if frame decoding fails.
                self.result['last_datagram'] = {'dump':name,**diagnostic,'prefix_hex':data[:1024].hex(),
                                              'prefix_is_complete_datagram':len(data) <= 1024}
                require(not ancillary and type(flags) is int and flags == 0,'truncated_or_ancillary_datagram')
                require(type(sender) in (tuple,list) and len(sender) == 2 and sender == (0,0),
                        'non_kernel_sender_or_multicast')
                require(len(data) >= HEADER.size,'empty_or_short_datagram')
                cursor = 0
                while cursor < len(data):
                    require(not done,'message_after_DONE')
                    require(len(data)-cursor >= HEADER.size,'short_netlink_header')
                    length,kind,nflags,nseq,nport = HEADER.unpack_from(data,cursor)
                    require(length >= HEADER.size and cursor+align4(length) <= len(data),'message_length_or_alignment')
                    require(nseq == seq and nport == port,'sequence_or_local_port_mismatch')
                    require(not nflags&NLM_F_DUMP_INTR,'dump_interrupted')
                    counts['messages'] += 1; require(counts['messages'] <= MESSAGE_COUNT_CAP,'message_count_cap')
                    frame = data[cursor:cursor+length]; aligned_frame = data[cursor:cursor+align4(length)]
                    saved = {'datagram':diagnostic['ordinal'],'offset':cursor,'frame_hex':aligned_frame.hex(),
                        'header':{'length':length,'type':kind,'flags':nflags,'sequence':nseq,'port':nport}}
                    if kind in (NLMSG_ERROR,NLMSG_OVERRUN):
                        record['error_message'] = saved
                        if kind == NLMSG_ERROR and length >= HEADER.size+4:
                            record['error_message']['error_code'] = struct.unpack_from('=i',frame,HEADER.size)[0]
                        raise ProbeFailure('netlink_ERROR_or_OVERRUN')
                    require(nflags == NLM_F_MULTI,'unexpected_or_filtered_response_flags')
                    if kind == NLMSG_DONE:
                        require(length == HEADER.size+4,'unsupported_DONE_payload')
                        errno = struct.unpack_from('=i',frame,HEADER.size)[0]
                        saved['error_code'] = errno; record['done'] = saved
                        require(errno == 0,'DONE_error'); done = True
                    else:
                        require(kind == response_type,'unexpected_response_type')
                        require(len(record['records']) < item_cap,'per_dump_record_cap')
                        parsed,attrs = parse_record(frame,kind,family)
                        saved.update(parsed=parsed,attributes=attrs); record['records'].append(saved)
                    cursor += align4(length)
                    # Never delete records/attributes to manufacture a fitting
                    # successful subset. Capacity failure remains incomplete;
                    # final encoding uses an explicit unavailable-raw fallback.
                    self.fit()
                require(cursor == len(data),'datagram_tail')
            self.check(deadline)
        except BaseException as error:
            primary = error; raise
        finally:
            if sock is not None:
                try:sock.close(); record['socket_closed'] = True
                except BaseException as error:
                    record['socket_closed'] = False
                    self.result['socket_cleanup_errors'].append({'dump':name,'type':type(error).__name__})
                    if primary is None:raise ProbeFailure('socket_close_unconfirmed') from None
        self.check(deadline)
        record['complete'] = True


def run_probe(*,socket_factory,if_nameindex,read_status,uname,clock):
    """All external effects are injected; production main supplies fixed adapters."""
    collector = Collector(clock); result = collector.result
    try:
        raw,eof = read_status(); result['process_status'] = parse_status(raw,eof); collector.check()
        kernel = uname()
        require(type(kernel) in (tuple,list) and len(kernel) == 5 and
                all(type(v) is str and len(v.encode('utf-8')) <= 1024 for v in kernel),'uname_shape')
        result['uname'] = dict(zip(('sysname','nodename','release','version','machine'),kernel))
        require(kernel[0] == 'Linux','unsupported_kernel')
        result['if_nameindex_before'] = checked_names(if_nameindex()); collector.check()
        for seq,spec in enumerate(SCHEDULE,1):collector.dump(socket_factory,spec,seq)
        result['if_nameindex_after'] = checked_names(if_nameindex()); collector.check()
        before = [v['parsed'] for v in result['dumps'][0]['records']]
        after = [v['parsed'] for v in result['dumps'][-1]['records']]
        fields = result['stability_projection_fields']
        projection = lambda rows:sorted([[r[key] for key in fields] for r in rows])
        result['link_stability_before'] = projection(before); result['link_stability_after'] = projection(after)
        for rows,names in ((before,result['if_nameindex_before']),(after,result['if_nameindex_after'])):
            require(len({r['index'] for r in rows}) == len(rows) and len({r['name'] for r in rows}) == len(rows),
                    'duplicate_link_identity')
            require(sorted([[r['index'],r['name']] for r in rows]) == names,'if_nameindex_link_crosscheck_changed')
        require(result['link_stability_before'] == result['link_stability_after'] and
                result['if_nameindex_before'] == result['if_nameindex_after'],'link_stability_projection_changed')
        collector.fit(); result['collection_complete'] = True; result['status'] = 'diagnostic_collection_complete'
    except BaseException as error:
        result['failure'] = {'category':getattr(error,'category','unsupported_or_OS_failure'),
                             'type':type(error).__name__,'errno':getattr(error,'errno',None)}
    result['elapsed_seconds'] = max(0,clock()-collector.started)
    raw = encoded(result)+b'\n'
    if len(raw) > OUTPUT_CAP:
        # No successful subset: retain compact bounded failure provenance and
        # hashes/counts; all omitted raw data is explicitly unavailable here.
        result = {'schema':'dosei_network_state_diagnostic_v1','status':'diagnostic_incomplete',
            'collection_complete':False,'network_qualified':False,'atomic_snapshot':False,
            'failure':{'category':'final_output_capacity'},'counters':result['counters'],
            'discarded_in_memory_result_bytes':len(raw),'discarded_in_memory_result_sha256':hashlib.sha256(raw).hexdigest(),
            'raw_complete_evidence_not_retained':True,'socket_cleanup_errors':result['socket_cleanup_errors']}
    return result


def live_status():
    fd = os.open('/proc/self/status',os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
    try:
        chunks = []; count = 0
        while count <= STATUS_CAP:
            raw = os.read(fd,min(4096,STATUS_CAP+1-count))
            if not raw:return b''.join(chunks),True
            chunks.append(raw); count += len(raw)
        return b''.join(chunks),False
    finally:os.close(fd)


def main():
    # The trusted candidate is the only entrypoint with live adapters.
    resource.setrlimit(resource.RLIMIT_CORE,(0,0)); resource.setrlimit(resource.RLIMIT_CPU,(2,3))
    def timeout(*_):raise ProbeFailure('candidate_wall_deadline')
    signal.signal(signal.SIGALRM,timeout); signal.setitimer(signal.ITIMER_REAL,WALL_SECONDS)
    try:
        result = run_probe(socket_factory=lambda:socket.socket(socket.AF_NETLINK,socket.SOCK_RAW,0),
                           if_nameindex=socket.if_nameindex,read_status=live_status,
                           uname=lambda:tuple(os.uname()),clock=time.monotonic)
        raw = encoded(result)+b'\n'; require(len(raw) <= OUTPUT_CAP,'final_output_capacity')
        sys.stdout.buffer.write(raw);sys.stdout.buffer.flush()
        return 0 if result['collection_complete'] else 1
    finally:signal.setitimer(signal.ITIMER_REAL,0)


if __name__ == '__main__':raise SystemExit(main())
