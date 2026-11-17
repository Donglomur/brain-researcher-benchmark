"""Offline complete35 retained-header outcome audit. No HTTP or numerical loading."""
import ast,base64,hashlib,http.client,io,json,math,os,re,resource,signal,stat,sys,time,types
from pathlib import Path
from decimal import Decimal
from urllib.parse import urljoin
READ_BYTES=12*1048576

def need(ok, message):
    if not ok:
        raise ValueError(message)

def bounded_number(value,limit):
    return type(value) in (int,float) and math.isfinite(value) and 0<=value<=limit

def strict(raw):
    def pairs(items):
        out={}
        for k,v in items:
            need(k not in out, 'duplicate JSON key')
            out[k]=v
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite JSON')))

def encoded(obj):
    return (json.dumps(obj,sort_keys=True,ensure_ascii=True,separators=(',',':'),allow_nan=False)+'\n').encode()

def identity(s):
    return tuple(getattr(s,k) for k in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns'))

class BaseReader:
    def __init__(self, maximum=READ_BYTES):
        self.maximum=maximum;self.bytes=0;self.reads=0;self.frozen={}

    def read(self,path,cap,expected=None):
        p=Path(path)
        need(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)),
             'ordinary absolute source/evidence path')
        before=p.lstat()
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<=before.st_size<=cap,
             'bounded singly linked ordinary file')
        need(self.bytes+before.st_size+1<=self.maximum,'whole audit managed-read allowance')
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            need(identity(os.fstat(fd))==identity(before),'opened file identity')
            with os.fdopen(fd,'rb',closefd=False) as f:raw=f.read(before.st_size+1)
            self.bytes+=len(raw);self.reads+=1
            need(len(raw)==before.st_size and identity(os.fstat(fd))==identity(before),'complete EOF/stable opened identity')
        finally:os.close(fd)
        need(identity(p.lstat())==identity(before),'stable lexical file identity')
        old=self.frozen.setdefault(str(p),identity(before));need(old==identity(before),'cross-pass file unchanged')
        desc={'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
        if expected is not None:need(desc==expected,'exact selected descriptor')
        return raw,desc

    def pin(self,desc,cap):
        need(type(desc) is dict and set(desc)=={'path','bytes','sha256'},'exact pin fields')
        return self.read(desc['path'],cap,desc)[0]

def original_headers(record):
    need(record.get('headers_representation')=='original_status_and_header_lines','actual original HTTP headers')
    raw=base64.b64decode(record['headers_base64'],validate=True);need(len(raw)<=4096,'header byte bound')
    stream=io.BytesIO(raw);status=None;headers=None;lines=0
    while True:
        line=stream.readline();lines+=1
        match=re.fullmatch(rb'HTTP/1\.[01] ([0-9]{3})[^\r\n]*(?:\r\n|\n)',line)
        need(match is not None,'original HTTP status line');status=int(match.group(1))
        block=[]
        while True:
            line=stream.readline();lines+=1;need(lines<=66,'bounded original header lines')
            need(bool(line),'complete original headers');block.append(line)
            if line in (b'\n',b'\r\n'):break
        headers=http.client.parse_headers(io.BytesIO(b''.join(block)))
        if status!=100:break
    need(stream.read()==b'' and status==record['response_status'],'exact final response/header join')
    out={}
    for k,v in headers.items():
        need(not any(c in k+v for c in '\r\n\x00'),'header injection')
        out.setdefault(k.lower(),[]).append(v)
    return status,out

def single(headers,key,required=True):
    values=headers.get(key,[]);need(len(values)==1 if required else len(values)<=1,'unique header '+key)
    return values[0] if values else None

def gone(pid,group=False):
    need(type(pid) is int and pid>1,'positive exact owned process identity')
    try:
        if group:os.killpg(pid,0)
        else:os.kill(pid,0)
    except ProcessLookupError:return {'pid':pid,'group':group,'status':'ESRCH'}
    except PermissionError:raise ValueError('owned identity absence not established: EPERM')
    raise ValueError('owned identity still present; no retry or signal from offline audit')

class Reader(BaseReader):
    """Cache each bounded ordinary file once; final metadata identity recheck."""
    def __init__(self):
        super().__init__();self.cache={};self.cache_bytes=0;self.tree_ids=None
    def read(self,path,cap,expected=None):
        key=str(Path(path))
        if key in self.cache:
            raw,pin=self.cache[key]
            need(len(raw)<=cap and (expected is None or expected==pin),'same cached descriptor')
            need(identity(Path(path).lstat())==self.frozen[key],'cached file unchanged')
            return raw,pin
        raw,pin=super().read(path,cap,expected)
        self.cache_bytes+=len(raw);need(self.cache_bytes<=10*1048576,'bounded one-pass metadata/entity cache')
        self.cache[key]=(raw,pin);return raw,pin
    def doc(self,path,cap=262144):return strict(self.read(path,cap)[0])
    def module(self,pin):
        raw=self.pin(pin,262144);m=types.ModuleType('_consensus_offline_'+Path(pin['path']).stem)
        m.__file__=pin['path'];exec(compile(raw,pin['path'],'exec'),m.__dict__);return m
    def finish(self):
        for path,old in self.frozen.items():need(identity(Path(path).lstat())==old,'final physical identity')

ROOT = Path('/UNCONFIGURED/producer')
AUDIT_ROOT = Path('/UNCONFIGURED/audit')
HERE=Path(__file__).resolve().parent
ROOT_FILES={'OWNER_BIRTH.json','CAPACITY.json','WORKER_BIRTH.json','PROCESS.json','MONITOR_START.json',
            'MONITOR_OUTCOME.json','COMPLETE35_HEADERS.json','WORKER_OUTCOME.json','OWNER_OUTCOME.json',
            'worker.stdout','worker.stderr'}
def snapshot(root):
    need(root.is_dir() and not any(p.is_symlink() for p in (root,*root.parents)),'ordinary actual root')
    found={};dirs=set();total=0
    for cur,children,files in os.walk(root,followlinks=False):
        rel=Path(cur).relative_to(root);need(str(rel) in ('.','HTTP','PROBES'),'literal actual directories')
        for n in children:
            p=Path(cur)/n;need(not p.is_symlink() and p.is_dir(),'ordinary actual child')
            dirs.add(str(p.relative_to(root)))
        for n in files:
            p=Path(cur)/n;r=str(p.relative_to(root))
            cap=262144
            if rel==Path('.'):need(n in ROOT_FILES,'unexpected actual root member')
            elif rel==Path('HTTP'):
                need(re.fullmatch(r'HTTP_[0-9]{3}\.(bin|json)|TRANSPORT_REPORT\.json',n),'HTTP member name')
                cap=4096 if n.endswith('.bin') else 16384
            else:need(re.fullmatch(r'(sysctl-(cores|memory)|pressure-[12]|vm-stat-[12]|ps-cpu-[12])\.json',n),'probe name')
            st=p.lstat();need(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and 0<=st.st_size<=cap,'bounded actual file')
            found[r]=identity(st);total+=st.st_size
            need(len(found)<=512 and total<=8*1048576,'whole actual namespace envelope')
    need(dirs<={'HTTP','PROBES'},'exact child directory scope')
    return found,total

def check_capacity(r,root,b,mods,require_pass):
    p=mods['policy'];c=r.doc(root/'CAPACITY.json');rows=[];values={};closed=[]
    for entry in c['probes']:
        name=entry['name'];row=r.doc(root/'PROBES'/(name+'.json'))
        need(row['pid']==entry['pid'],'capacity summary/probe identity')
        if 'receipt' in entry:need(r.read(root/'PROBES'/(name+'.json'),262144)[1]==entry['receipt'],'probe descriptor')
        rows.append(row)
        if row.get('pid') is not None:closed += [gone(row['pid']),gone(row['pid'],True)]
    if not require_pass and not c.get('passed'):
        need(c['physical_closure']==p.physical_closure(c['probe_admissions'],rows)
             and c['physical_closure']['all_probe_groups_absent'],'failed capacity physical closure')
        return {'passed':False,'verified_probe_records':len(rows),'closure':closed}
    need(len(rows)==8 and len({x['pid'] for x in rows})==8,'complete eight capacity probes')
    for row,(name,argv) in zip(rows,p.PROBES):values[name]=p.receipt(row,name,argv)
    need(all(int(a['ended_monotonic_ns'])<=int(z['started_monotonic_ns']) for a,z in zip(rows,rows[1:]))
         and int(rows[5]['started_monotonic_ns'])-int(rows[4]['ended_monotonic_ns'])>=200000000,'ordered separated samples')
    memory=p.integer(values['sysctl-memory'],'memory');cores=p.integer(values['sysctl-cores'],'cores')
    pressure=[p.integer(values['pressure-'+str(i)],'pressure') for i in (1,2)]
    ss=[p.vm_snapshot(values['vm-stat-'+str(i)],memory) for i in (1,2)]
    cpu=[p.cpu_cores(values['ps-cpu-'+str(i)]) for i in (1,2)]
    checks={'both_normal':pressure==[1,1],'same_page_size':ss[0]['page_bytes']==ss[1]['page_bytes'],
            'headroom':min(x['potential_headroom_bytes'] for x in ss)>=b['memory_floor_bytes'],
            'pageouts_unchanged':ss[0]['pageouts']==ss[1]['pageouts'],
            'swapouts_unchanged':ss[0]['swapouts']==ss[1]['swapouts'],
            'CPU_with_selected_reserved_slots':max(cpu)+b['observer_cpu_reserved_slots']<=cores,
            'disk':type(c['disk_free_bytes']) is int and c['disk_free_bytes']>=b['disk_floor_bytes']}
    need(c['checks']==checks and c['passed']==all(checks.values()) and (not require_pass or all(checks.values())),
         'independent capacity arithmetic')
    need(c['snapshots']==ss and c['pressure']==pressure and c['cpu_samples']==[str(x) for x in cpu]
         and c['cores']==cores,'complete capacity projection')
    for k in ('memory_floor_bytes','disk_floor_bytes','outside_host_bytes','outside_disk_bytes'):
        need(c[k]==b[k],'selected capacity booking')
    need(c['own_host_bytes']==128*1048576 and c['own_retention_bytes']==16*1048576
         and c['margin_bytes']==1073741824 and c['reserved_CPU_slots']==b['observer_cpu_reserved_slots'],'own/margin/CPU bookings')
    pc=p.physical_closure(c['probe_admissions'],rows)
    need(c['physical_closure']==pc and pc['all_probe_groups_absent'] and pc['complete_receipt_population'],'full probe closure')
    need(c['probe_CPU_partition_seconds']==5 and c['probe_CPU_partition_passed'] is True
         and bounded_number(c['waited_probe_CPU_seconds'],5),'capacity CPU partition')
    return {'passed':all(checks.values()),'checks':checks,'closure':closed,
            'last_probe_ended_monotonic_ns':rows[-1]['ended_monotonic_ns'],
            'first_probe_started_monotonic_ns':rows[0]['started_monotonic_ns'],
            'disk_is_retained_observation_not_new_probe':True}

def check_http(r,root,rows,targets,mods,complete):
    t=mods['range_transport'];hp=mods['header_protocol']
    descriptors=sorted((root/'HTTP').glob('HTTP_*.json')) if (root/'HTTP').exists() else []
    need(len(descriptors)<=210,'transaction cap')
    records=[];body_total=metadata_total=0
    for ordinal,p in enumerate(descriptors,1):
        need(p.name=='HTTP_%03d.json'%ordinal,'contiguous retained HTTP descriptors')
        rec=r.doc(p,16384);metadata_total+=r.read(p,16384)[1]['bytes']
        need(rec['index']==ordinal and type(rec['file_id']) is int,'descriptor ordinal/type')
        bp=root/'HTTP'/('HTTP_%03d.bin'%ordinal)
        need(rec['body_file']==bp.name,'body path')
        raw,pin=r.read(bp,4096)
        need(rec['body_returned']==rec['body_written']==rec['body_file_bytes']==len(raw)
             and rec['returned_sha256']==pin['sha256'] and rec.get('preservation_complete') is True,'complete retained entity custody')
        need(rec['body_closed'] is True and not rec['closure_errors'],'body descriptor closure')
        need(rec['response_closed'] in (True,None) and rec['connection_closed'] in (True,None),'partial connection closure semantics')
        body_total+=len(raw);records.append((rec,raw))
    need(body_total<=143780,'whole returned header bound')
    if not complete:
        return {'complete':False,'retained_descriptors':len(records),'retained_entity_bytes':body_total,
                'verified_scope':'All available descriptor/body identities and recorded resource closure only. Partial sequence is not promoted to complete35 semantic admission.'}
    need(len(records)==210,'all210 HTTP records')
    targetmap={x['file_id']:x['identity'] for x in targets}
    cursor=0;etags={};range_bodies={};magic=[];headers=[]
    def fetch(index,start,count,label):
        nonlocal cursor
        row=rows[index];url=row['canonical_download_url']
        expected_headers={'Range':'bytes=%d-%d'%(start,start+count-1),'Accept-Encoding':'identity',
                          'User-Agent':'CONSENSUS-NPY-Header-Metadata/1'}
        if row['file_id'] in etags:expected_headers['If-Match']=etags[row['file_id']]
        for hop in range(2):
            rec,raw=records[cursor];cursor+=1
            need((rec['file_id'],rec['label'],rec['requested_start'],rec['requested_count'],rec['request_url'])==
                 (row['file_id'],label,start,count,url),'complete ordered logical-range identity')
            need(rec['request_headers']==expected_headers and rec['request_issued'] is True,'exact range/If-Match request')
            need(rec['response_closed'] is True and rec['connection_closed'] is True and 'error' not in rec,'successful HTTP closure')
            need(bounded_number(rec['elapsed_seconds'],15),'per-transaction observed time')
            status,h=original_headers(rec)
            if hop==0:
                need(status in (301,302,303,307,308) and rec['status']=='REDIRECT_BODY_UNREAD'
                     and not raw and rec['body_intentionally_unread'] is True and rec['body_complete'] is False,'one unread canonical redirect')
                url=urljoin(url,single(h,'location'))
                need(rec['redirect_target_private']==url and t.storage_identity_allowed(url,targetmap[row['file_id']]),
                     'retained stable target and exact signing grammar')
            else:
                need(status==206 and rec['status']=='EXACT_RANGE_RETURNED' and rec['body_complete'] is True
                     and rec['body_intentionally_unread'] is False and len(raw)==count,'complete strict206 header entity')
                need(single(h,'content-range')=='bytes %d-%d/%d'%(start,start+count-1,row['bytes'])
                     and single(h,'content-length')==str(count) and 'transfer-encoding' not in h,'exact range/fullsize/framing')
                enc=single(h,'content-encoding',False);need(enc is None or enc.lower()=='identity','identity encoding')
                tag=single(h,'etag');need(t.strong_etag(tag) and rec['strong_etag']==tag,'strong response ETag')
                need(row['file_id'] not in etags or etags[row['file_id']]==tag,'stable per-object ETag')
                etags[row['file_id']]=tag;range_bodies[label]=raw
                return raw
    for i in range(35):
        raw=fetch(i,0,8,'f%02d-magic'%i)
        need(raw[:6]==b'\x93NUMPY' and tuple(raw[6:]) in ((1,0),(2,0)),'all35 valid first prefixes')
        magic.append(raw)
    for i,row in enumerate(rows):
        h=hp.remaining_header(i,row,magic[i],lambda label,start,count,i=i:fetch(i,start,count,label))
        h['strong_etag']=etags[row['file_id']];headers.append(h)
    need(cursor==210 and len(range_bodies)==105 and len(etags)==35,'whole range population')
    report=r.doc(root/'COMPLETE35_HEADERS.json')
    expected={'schema':'consensus35_primitive_header_report_v1','complete_metadata_inquiry':True,
              'headers':headers,'geometry':hp.geometry(headers,rows),'logical_ranges':105,'HTTP_transactions':210,
              'returned_entity_bytes':body_total,'numeric_payload_ranges_requested':0,
              'full_file_hashes_verified':False,'scientific_readiness':False}
    need(report==expected,'complete producer/independent retained-header reconstruction')
    transport=r.doc(root/'HTTP/TRANSPORT_REPORT.json',16384)
    required={'schema':'consensus35-primitive-header-range-transport-v1','phase':'headers',
              'status':'RANGES_ONLY_NO_DIRECTORY_CLAIM','whole_original_hashes_verified':False,
              'inventory_files':35,'inventory_advertised_bytes':sum(x['bytes'] for x in rows),
              'transactions':210,'redirects':105,'logical_ranges':105,'logical_range_requested_bytes':body_total,
              'complete_header_objects':35,'successful_ranges':105,'files_with_successful_ranges':35,
              'etags':{str(k):v for k,v in sorted(etags.items())},'body_returned_bytes':body_total,
              'body_written_bytes':body_total,'raw_metadata_written_bytes':metadata_total,
              'raw_metadata_records':210,'descriptors_written':210,'descriptors_failed':0,
              'unresolved_originals':[],'errors':[]}
    for k,v in required.items():need(transport[k]==v,'transport aggregate '+k)
    need(transport['limits']==dict(t.DEFAULTS,body_bytes=143780),'transport configured limits')
    need(bounded_number(transport['elapsed_seconds'],1470),'transport elapsed ceiling')
    return {'complete':True,'headers':headers,'geometry':expected['geometry'],'HTTP_transactions':210,
            'logical_ranges':105,'returned_entity_bytes':body_total,
            'signature_freshness':'Source-enforced local check; absolute per-transaction dispatch timestamps absent, so independently unobserved.',
            'NPY_parser_independence':'Accepted primitive semantic parser reused over independently authenticated retained entities; not a second NPY implementation.'}

def check_process(r,root,b,owner,mods):
    if not owner.get('worker_dispatched'):return {'worker_dispatched':False,'closures':[]}
    birth=r.doc(root/'WORKER_BIRTH.json');pid=birth['pid'];need(pid==birth['group_id'],'worker own group')
    closed=[gone(pid),gone(pid,True)]
    need(birth['owner_pid']==owner['owner_pid'],'worker/owner join')
    proc=r.doc(root/'PROCESS.json');need(proc['pid']==pid and proc['argv']==birth['argv'],'process launch join')
    expected=[b['python']['path'],'-I','-S','-B',b['owner']['path'],'--worker',
              owner['_binding']['path'],str(owner['_binding']['bytes']),owner['_binding']['sha256'],
              birth['gate_sha256'],str(owner['owner_pid'])]
    need(proc['argv'][:-1]==expected and len(proc['argv'])==len(expected)+1,'complete worker argument graph')
    need(proc['cwd']==str(root),'worker cwd')
    for stream in ('stdout','stderr'):
        raw,pin=r.read(root/('worker.'+stream),65536);rec=proc['streams'][stream]
        need(rec['bytes']==len(raw) and rec['sha256']==pin['sha256'],'whole worker stream custody')
    need(mods['monitor'].closure_ready(proc),'recorded owned worker closure')
    if owner['complete']:
        need(proc['complete'] is True and proc['natural_exit_observed'] is True
             and proc['gate_required'] is True and proc['gate_delivered'] is True
             and proc['gate_bytes_sent']==65 and not proc['errors'] and not proc['signals_received']
             and proc['closure']['signals_sent']==[] and proc['closure']['errors']==[]
             and proc['closure']['exit_code']==0,'natural successful worker')
        worker=r.doc(root/'WORKER_OUTCOME.json')
        need(worker['complete'] is True and 'error' not in worker and worker['pid']==worker['group_id']==pid,'worker outcome identity')
        need(worker['array_decoding'] is False and worker['scientific_readiness'] is False
             and worker['numeric_payload_ranges_requested']==0,'metadata-only worker claim')
        need(bounded_number(worker['elapsed_seconds'],1492) and bounded_number(worker['cpu_seconds'],30)
             and bounded_number(worker['peak_rss_bytes'],64*1048576)
             and bounded_number(worker['source_read_bytes'],4*1048576),'worker resource ledger')
        ms=r.doc(root/'MONITOR_START.json',8192);me=r.doc(root/'MONITOR_OUTCOME.json',8192)
        classification=mods['monitor'].interpret(ms,me,'intake',pid,64*1048576,4*1048576,4*1048576+143780,0)
        need(classification['classification']=='closed' and worker['monitor']['diagnostic_outcome']==me,'durable worker monitor')
        for key,name in [('complete35_headers','COMPLETE35_HEADERS.json')]:
            need(worker[key]==r.read(root/name,262144)[1],'worker selected '+name)
        disk_transport=r.doc(root/'HTTP/TRANSPORT_REPORT.json',16384)
        after=worker['transport']
        for k,v in disk_transport.items():
            if k not in ('elapsed_seconds','raw_metadata_written_bytes','raw_metadata_records'):
                need(after[k]==v,'postclose transport invariant '+k)
        trpin=r.read(root/'HTTP/TRANSPORT_REPORT.json',16384)[1]
        need(after['raw_metadata_records']==211 and after['raw_metadata_written_bytes']==disk_transport['raw_metadata_written_bytes']+trpin['bytes']
             and after['elapsed_seconds']>=disk_transport['elapsed_seconds'],'transport postclose metadata delta')
        need(worker['HTTP_transactions']==210 and worker['logical_ranges']==105
             and worker['returned_entity_bytes']==disk_transport['body_returned_bytes'],'worker aggregate join')
    return {'worker_dispatched':True,'closures':closed,'process':r.read(root/'PROCESS.json',262144)[1]}

def evaluate(r,b,binding,root,outer):
    initial,total=snapshot(root)
    # Read every retained bounded file exactly once, including failure remnants.
    for name in sorted(initial):r.read(root/name,262144)
    ob=r.doc(root/'OWNER_BIRTH.json');need(ob['pid']==ob['group_id']==ob['session_id']==outer['pid']==outer['group_id']==outer['session_id'],'owned outer identity')
    need(ob['binding']==binding and ob['actual_count']==1 and ob['retry'] is False
         and ob['root_authority']==b['root_authority'],'owner exact selection')
    closed=[gone(ob['pid']),gone(ob['pid'],True)]
    need(outer['selected_request']==binding and outer['retry'] is False,'outer selected request')
    expected_owner=[b['python']['path'],'-I','-S','-B',b['owner']['path'],'--owner',binding['path'],str(binding['bytes']),binding['sha256']]
    need(outer['argv']==expected_owner,'outer exec argument graph')
    owner=r.doc(root/'OWNER_OUTCOME.json')
    need(owner['schema']=='consensus35-header-owner-outcome-v1' and type(owner['complete']) is bool
         and owner['owner_pid']==owner['owner_group_id']==ob['pid'] and owner['automatic_retry'] is False,'owner outcome')
    need(owner['last_owned_cleanup']==[],'no unresolved fallback cleanup')
    need(bounded_number(owner['cpu_seconds'],5) and bounded_number(owner['peak_rss_bytes'],64*1048576)
         and bounded_number(owner['source_read_bytes'],4*1048576) and bounded_number(owner['elapsed_seconds'],1515),'owner reported envelope')
    expected_retained=[{'path':name,'bytes':initial[name][4]} for name in sorted(initial) if name!='OWNER_OUTCOME.json']
    need(owner['retained_files']==expected_retained and owner['retained_bytes_before_outcome']==sum(x['bytes'] for x in expected_retained),'owner census complete population')
    mods={k:r.module(b['sources'][k]) for k in ('policy','monitor','protocol','header_protocol','range_transport')}
    rows=mods['protocol'].validate_operands(strict(r.pin(b['sources']['operands'],262144)))
    target_doc=strict(r.pin(b['sources']['targets'],262144));targets=target_doc['targets']
    need(len(targets)==35 and all((x['index'],x['file_id'],x['declared_bytes'],x['canonical_download_url'])==
         (z['index'],z['file_id'],z['bytes'],z['canonical_download_url']) for x,z in zip(targets,rows)),'all35 target/operand joins')
    owner['_binding']=binding
    capacity=check_capacity(r,root,b,mods,owner['capacity_admitted'])
    process=check_process(r,root,b,owner,mods)
    http=check_http(r,root,rows,targets,mods,owner['complete'])
    if owner['complete']:
        need(owner['capacity_admitted'] and owner['worker_dispatched'] and 'error' not in owner,'complete owner success')
        names=set(ROOT_FILES)|{'PROBES/'+n+'.json' for n,_ in mods['policy'].PROBES}|{'HTTP/TRANSPORT_REPORT.json'}
        names|={'HTTP/HTTP_%03d.%s'%(i,ext) for i in range(1,211) for ext in ('bin','json')}
        need(set(initial)==names,'exact complete actual namespace')
        for key,name in [('capacity','CAPACITY.json'),('process','PROCESS.json'),('worker_outcome','WORKER_OUTCOME.json')]:
            need(owner[key]==r.read(root/name,262144)[1],'owner selected '+name)
        wb=r.doc(root/'WORKER_BIRTH.json')
        last=Decimal(capacity['last_probe_ended_monotonic_ns'])/Decimal(10**9)
        need(Decimal(str(ob['started_monotonic']))<=Decimal(capacity['first_probe_started_monotonic_ns'])/Decimal(10**9)
             <=last<=Decimal(str(wb['observed_monotonic'])) and
             0<=Decimal(str(wb['observed_monotonic']))-last<=15,'historic capacity freshness at worker spawn')
    need(snapshot(root)==(initial,total),'final complete namespace identity')
    r.finish()
    return {'classification':'AUDITED_COMPLETE_HEADERS' if owner['complete'] else 'AUDITED_CLOSED_FAILURE',
            'complete_headers':owner['complete'],'scientific_ready':False,'capacity':capacity,'process':process,
            'headers':http,'owner_closure':closed,'namespace_files':[r.read(root/n,262144)[1] for n in sorted(initial)],
            'namespace_bytes':total,'owner_outcome':r.read(root/'OWNER_OUTCOME.json',262144)[1],
            'audit_semantics':'Retained originals and source/request/lifecycle joins; no new request or numerical payload.'}

def reserve_bootstrap(reader,auditor_bytes):
    # External literal bootstrap requests this executable extent plus one EOF byte.
    # Reserve it inside the same12MiB grant; do not mislabel it as a Reader measurement.
    need(type(auditor_bytes) is int and 0<auditor_bytes<=262144,'bounded bootstrap source extent')
    reserve=auditor_bytes+1
    reader.maximum=READ_BYTES-reserve
    need(reader.bytes<=reader.maximum,'bootstrap plus already-read metadata within whole grant')
    return reserve

def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request',required=True);parser.add_argument('--bytes',required=True,type=int)
    parser.add_argument('--sha256',required=True);a=parser.parse_args()
    r=Reader();pin={'path':str(Path(a.request).absolute()),'bytes':a.bytes,'sha256':a.sha256}
    s=strict(r.pin(pin,262144))
    need(set(s)=={'schema','execution_authority','root_authority','owner_request','outer_birth','launch','returned','auditor','output_path'},
         'exact nine audit-request fields')
    need(s['schema']=='consensus35_offline_header_audit_v1' and s['execution_authority'] is True
         and type(s['root_authority']) is str and s['root_authority'],'selected offline audit only')
    need(s['auditor']['path']==str(Path(__file__).resolve()) and s['output_path']==str(AUDIT_ROOT),'literal audit source/output')
    r.pin(s['auditor'],262144)
    bootstrap_reserved=reserve_bootstrap(r,s['auditor']['bytes'])
    static=strict(r.pin({'path': '/UNCONFIGURED/STATIC_BINDINGS.json', 'bytes': 1, 'sha256': '0000000000000000000000000000000000000000000000000000000000000000'},262144));template=strict(r.pin(static['producer_request'],262144))
    b=strict(r.pin(s['owner_request'],262144))
    for k,v in template.items():
        if k not in ('execution_authority','observer_cpu_reserved_slots','root_authority'):need(b[k]==v,'immutable producer request '+k)
    need(set(b)==set(template) and b['execution_authority'] is True and type(b['observer_cpu_reserved_slots']) is int
         and 2<=b['observer_cpu_reserved_slots']<=64 and b['root_authority'],'exact actual authority and CPU booking')
    for source in [b['owner'],b['python'],*b['sources'].values(),static['launcher']]:r.pin(source,262144)
    need(str(Path(sys.executable).resolve())==b['python']['path'],'exact audit interpreter')
    outer=strict(r.pin(s['outer_birth'],65536));need(s['outer_birth']['path']==str(ROOT)+'.OUTER_BIRTH.json','outer birth path')
    launch=strict(r.pin(s['launch'],16384));ret=strict(r.pin(s['returned'],16384))
    need(launch['schema']=='consensus35_header_tool_launch_v1' and launch['once'] is True
         and launch['selected_request']==s['owner_request'] and launch['launcher']==static['launcher'],'exact capture launch')
    argv=[b['python']['path'],'-I','-S','-B',static['launcher']['path'],'--request',s['owner_request']['path'],
          '--bytes',str(s['owner_request']['bytes']),'--sha256',s['owner_request']['sha256']]
    need(launch['argv']==argv and ret['schema']=='consensus35_header_tool_return_v1'
         and ret['launch']==s['launch'] and ret['natural_return'] is True and ret['automatic_retry'] is False
         and type(ret['exit_code']) is int,'literal launch and natural terminal capture')
    need(type(ret['stdout']) is str and len(ret['stdout'].encode())<=65536
         and type(ret['stderr']) is str and len(ret['stderr'].encode())<=65536,'complete outer capture streams')
    need(not AUDIT_ROOT.exists() and not any(p.is_symlink() for p in AUDIT_ROOT.parents),'fresh audit namespace')
    resource.setrlimit(resource.RLIMIT_CPU,(10,10));started=time.monotonic()
    AUDIT_ROOT.mkdir(mode=0o700);result={'schema':'consensus35_offline_header_audit_outcome_v1','accepted':False,'request':pin}
    old=signal.getsignal(signal.SIGALRM)
    def timeout(*unused):raise TimeoutError('offline90second audit fuse')
    signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,90)
    try:
        result['evidence']=evaluate(r,b,s['owner_request'],ROOT,outer)
        complete=result['evidence']['complete_headers']
        need((ret['exit_code']==0)==complete,'tool natural-return/outcome agreement')
        if ret['stdout']:
            stdout=strict(ret['stdout'])
            need(stdout=={'complete':complete,'outcome':result['evidence']['owner_outcome'],
                 'worker_dispatched':result['evidence']['process']['worker_dispatched'],
                 'target_routes_approved':False,'header_ranges_authorized':False},'whole owner stdout/outcome join')
        else:need(not complete,'complete owner stdout required')
        need(ret['stderr']=='','complete tool stderr')
        need(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss<=128*1048576,'audit observed high-water RSS')
        result['accepted']=True
    except BaseException as exc:
        result['error']={'type':type(exc).__name__,'message':str(exc)[:1024]}
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)
        result.update(explicit_read_bytes=r.bytes,physical_reads=r.reads,
            bootstrap_source_read_reservation_bytes=bootstrap_reserved,
            combined_explicit_charge_bytes=r.bytes+bootstrap_reserved,
            whole_managed_read_allowance_bytes=READ_BYTES,
            remaining_Reader_ceiling_bytes=r.maximum,
            bootstrap_scope='Exact literal external source-capture reservation, not measured by Reader; interpreter/OS I/O remains excluded',
            elapsed_seconds=time.monotonic()-started,CPU_seconds=time.process_time(),
            peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            RSS_scope='sampled high-water check, not continuous OS enforcement',
            complete_lifetime_IO_accounting=False,children_spawned=0,HTTP_requests=0,numerical_payload_reads=0)
        raw=encoded(result);need(len(raw)<=2*1048576,'audit output partition')
        p=AUDIT_ROOT/'OUTCOME.json'
        with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        print(json.dumps({'accepted':result['accepted'],'outcome':{'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}}))
    return 0 if result['accepted'] else 1

if __name__=='__main__':raise SystemExit(main())

