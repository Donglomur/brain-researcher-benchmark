"""Independent complete packet review, using only stdlib and one shared cache."""
import argparse,hashlib,json,math,os,signal,stat,struct,time
from pathlib import Path
PACKET=('GEOMETRY.private.json','RUNTIME_OBSERVED.private.json','PROJECTION_RECEIPT.private.json',
        'WORKER_RESULT.private.json','input/INPUT.json','input/values.f64',
        'input/pair_counts.u8','input/missingness.json')
CAP=40*1024*1024
MANIFEST_CAP=262144
READS=0
DEADLINE=0

def need(value,why):
    if not value:raise ValueError(why)
def check():need(time.monotonic()<DEADLINE,'original_review_deadline')
def decode(raw):
    def pairs(items):
        d={}
        for k,v in items:need(k not in d,'duplicate_json_key');d[k]=v
        return d
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite_JSON')))
def encode(value):return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def ordinary(path,cap,expected=None):
    global READS
    p=Path(path);need(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)),
                     'ordinary_absolute_path')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        s=os.fstat(fd);need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and 0<=s.st_size<=cap,'ordinary_extent')
        READS+=s.st_size;need(READS<=2*CAP+16*1024*1024,'complete_review_read_ceiling')
        parts=[];left=s.st_size
        while left:
            check();b=os.read(fd,min(65536,left));need(bool(b),'complete_read');parts.append(b);left-=len(b)
        fields=('st_dev','st_ino','st_uid','st_gid','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
        physical={k:getattr(s,k) for k in fields}
        need(physical=={k:getattr(os.fstat(fd),k) for k in fields}==
             {k:getattr(p.lstat(),k) for k in fields},'stable_complete_original')
        raw=b''.join(parts)
        if expected is not None:need(pin(raw)==expected,'exact_pin')
        return raw,physical
    finally:os.close(fd)
def write(path,raw):
    p=Path(path);need(not p.exists() and not p.is_symlink(),'exclusive_output')
    with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    p.chmod(0o400)

def recompute(values):
    """Independent float iteration; producer uses uint64 classification instead."""
    need(len(values)==35616000,'all4452000_operand_bytes')
    cells=7*53*200;persons=15
    masks=[[0]*cells for _ in range(4)]
    census=[[[0]*4 for _ in range(persons)] for _ in range(4)]
    total=0
    for i,(value,) in enumerate(struct.iter_unpack('<d',values)):
        if i%159000==0:check()
        condition,within=divmod(i,cells*persons);cell,person=divmod(within,persons)
        if math.isfinite(value):category=0;masks[condition][cell]|=1<<person
        elif math.isnan(value):category=1
        else:category=2 if value>0 else 3
        census[condition][person][category]+=1;total+=1
    result=bytearray(3*cells)
    for cell in range(cells):
        if cell%200==0:check()
        a,b,c,d=(row[cell] for row in masks)
        for plane,mask in enumerate((a&c,b&d,a&b&c&d)):result[plane*cells+cell]=mask.bit_count()
    need(total==4452000 and all(sum(row)==74200 for group in census for row in group),'complete_independent_census')
    return bytes(result),census

def transport_check(obj,literal,owner_root):
    need(set(obj)=={'schema','events'} and obj['schema']=='tms_full_paired_generation_transport_v1','transport_schema')
    events=obj['events'];need(type(events) is list and 1<=len(events)<=512,'finite_exact_transport')
    session=None;parts=[]
    for i,event in enumerate(events):
        need(set(event)=={'tool','request','result'},'exact_event_envelope')
        if i==0:need(event['tool']=='exec_command' and event['request']==literal,'exact_owner_tool_request')
        else:
            q=event['request']
            need(event['tool']=='write_stdin' and session is not None and q['session_id']==session
                 and q.get('chars','')=='','owned_empty_poll')
        r=event['result'];need(type(r) is dict and type(r.get('output')) is str,'complete_tool_output')
        parts.append(r['output'])
        if i<len(events)-1:need('exit_code' not in r and type(r.get('session_id')) is int,'nonterminal_session')
        else:need(r.get('exit_code')==0 and 'session_id' not in r,'natural_terminal_zero')
        session=r.get('session_id')
    result=decode(''.join(parts).encode())
    need(result=={'status':'completed','outcome':str(Path(owner_root)/'OUTCOME.json')},'exact_owner_terminal_stdout')
    return len(events)

def semantics(data,config,meta):
    request,science,inventory,binding=map(lambda x:decode(meta[x]),('request','scientific','inventory','owner_binding'))
    manifest=decode(data['packet:input/INPUT.json']);geometry=decode(data['packet:GEOMETRY.private.json'])
    receipt=decode(data['packet:PROJECTION_RECEIPT.private.json']);worker=decode(data['packet:WORKER_RESULT.private.json'])
    runtime=decode(data['packet:RUNTIME_OBSERVED.private.json']);census=decode(data['packet:input/missingness.json'])
    owner=decode(data['owner:OUTCOME.json']);original=request['original']
    values=data['packet:input/values.f64'];pairs=data['packet:input/pair_counts.u8']
    need(geometry['schema']=='tms-full-paired-source-geometry-v1','geometry_schema')
    source={k:original['file'][k] for k in ('bytes','sha256')}
    need(geometry['source']==source and geometry['shape']==[62,53,200,15]
         and geometry['conditions']==science['condition_order'],'full_original_geometry')
    labels=geometry['labels'];need(len(labels)==len(set(labels))==62,'all62_unique_original_labels')
    for key,n in [('frequency',53),('time',200)]:
        axis=geometry[key]
        need(type(axis) is list and len(axis)==n and all(type(x) in (int,float) and math.isfinite(x) for x in axis)
             and all(a<b for a,b in zip(axis,axis[1:])),'whole_monotonic_'+key)
    selected=[i for i,label in enumerate(labels) if label in science['selected_channel_set']]
    actual=[labels[i] for i in selected];primary=[i for i,x in enumerate(actual) if x in science['primary_six_channel_set']]
    need(len(selected)==7 and len(primary)==6 and set(actual)==set(science['selected_channel_set']),'all_seven_six_labels')
    need(manifest['schema']=='tms-full-paired-original-input-v1' and manifest['shape']==[4,7,53,200,15]
         and manifest['axis_order']==science['output_dimensions']
         and manifest['dtype']=='little-endian-IEEE754-binary64' and manifest['order']=='C; source_position fastest'
         and manifest['conditions']==geometry['conditions'] and manifest['source']==source
         and manifest['scientific_contract']==pin(meta['scientific']),'complete_input_manifest')
    need(manifest['original_labels']==labels and manifest['selected_labels']==actual
         and manifest['selected_original_channel_indices']==selected
         and manifest['primary_six_indices_within_selected']==primary
         and manifest['sensitivity_seven_indices']==list(range(7))
         and manifest['frequency_coordinates']==geometry['frequency']
         and manifest['time_coordinates']==geometry['time']
         and manifest['source_positions']==list(range(15))
         and manifest['source_declared_roster']==science['coordinates']['source_declared_roster']
         and manifest['pairing_provenance']==science['pairing']
         and manifest['physical_person_ids_independently_verified'] is False
         and manifest['contains_protected_reference_or_derived_statistic'] is False,'all_coordinates_and_scope')
    need(manifest['values']=={'file':'values.f64',**pin(values)}
         and manifest['finite_pair_counts']=={'file':'pair_counts.u8',**pin(pairs),'dtype':'uint8',
             'shape':[3,7,53,200],'order':['pin_T_and_NT','pout_T_and_NT','all_four_interaction']}
         and manifest['missingness']=={'file':'missingness.json',**pin(data['packet:input/missingness.json'])},
         'all_payload_identity_joins')
    actual_pairs,actual_census=recompute(values)
    expected_census={'schema':'tms_full_paired_missingness_v1',
        'categories':['finite','nan','positive_infinity','negative_infinity'],
        'axis_order':['condition','source_position','category'],'shape':[4,15,4],'counts':actual_census,
        'per_condition_position_total':74200,'all_operands':4452000,'finite_pair_shape':[3,7,53,200],
        'finite_pair_order':['pin_T_and_NT','pout_T_and_NT','all_four_interaction'],'no_imputation_or_dropping':True}
    need(actual_pairs==pairs and len(pairs)==222600 and census==expected_census,'every_count_and_census_value')
    def entry(relative):return {'path':str(Path(config['generation_root'])/relative),**pin(data['packet:'+relative])}
    joins={'input_manifest':'input/INPUT.json','values':'input/values.f64','pair_counts':'input/pair_counts.u8',
           'missingness':'input/missingness.json','source_geometry':'GEOMETRY.private.json'}
    need(all(receipt[k]==entry(v) for k,v in joins.items()),'whole_receipt_members')
    need(receipt['schema']=='tms-full-paired-original-projection-receipt-v1'
         and receipt['source_lock_sha256']==config['source_lock']['sha256']
         and receipt['request_sha256']==config['request']['sha256']
         and receipt['source']==source and receipt['source_before']==receipt['source_after']==original['physical']
         and receipt['original_body_hash_passes']==2 and receipt['postpass_full_hash']==source
         and receipt['source_closed'] is True and receipt['source_channel_slabs']==28
         and receipt['initial_source_vectors']==28 and receipt['operand_count']==4452000
         and receipt['value_bytes']==35616000 and receipt['validity_count_bytes']==222600
         and receipt['reference_reads']==receipt['model_calls']==0 and receipt['fitting'] is False
         and receipt['no_dropping_or_imputation'] is True
         and receipt['full_registered_scientific_task_qualified'] is False
         and receipt['redistribution_authority'] is False,'complete_original_projection_provenance')
    cleanup=receipt['source_cleanup']
    need(len(cleanup)==4 and [x['role'] for x in cleanup]==['slab','file','stream','fd']
         and all(x['attempted'] and x['close_returned'] and x['observed_closed'] and not x['errors'] for x in cleanup),
         'all_four_original_resources_closed')
    need(worker['schema']=='tms_full_paired_projection_worker_result_v1'
         and worker['status']=='COMPLETE_LOSSLESS_INPUT_PENDING_WHOLE_REVIEW'
         and worker['source_lock_sha256']==config['source_lock']['sha256']
         and worker['request_sha256']==config['request']['sha256']
         and worker['generation_id']==request['generation_id']
         and worker['source_before']==worker['source_after']==original['physical']
         and worker['all_operands']==4452000 and worker['all_pair_counts']==222600
         and worker['runtime']==entry('RUNTIME_OBSERVED.private.json')
         and worker['outputs']=={'receipt':entry('PROJECTION_RECEIPT.private.json'),
             'manifest':entry('input/INPUT.json'),'values':entry('input/values.f64'),
             'pair_counts':entry('input/pair_counts.u8'),'missingness':entry('input/missingness.json'),
             'geometry':entry('GEOMETRY.private.json'),'source_cleanup':cleanup,
             'all_values':4452000,'all_pair_counts':222600},'complete_worker_output_joins')
    before_result=sum(len(data['packet:'+n]) for n in PACKET if n!='WORKER_RESULT.private.json')
    need(worker['reserved_write_bytes_before_result']==worker['successful_write_bytes_before_result']==before_result
         and before_result+len(data['packet:WORKER_RESULT.private.json'])<=request['limits']['worker_write_bytes']
         and 0<worker['managed_read_bytes']<=request['limits']['worker_read_bytes']
         and 0<worker['report_point_rss_bytes']<=request['limits']['worker_report_point_rss_bytes']
         and 0<=worker['elapsed_seconds']<worker['deadline_seconds']==330
         and worker['reference_construction'] is False and worker['model_calls']==0
         and worker['fitting'] is False and worker['scientific_admission'] is False
         and worker['hard_or_full_lifetime_RSS_claim'] is False and worker['global_OS_native_IO_metered'] is False,
         'whole_worker_resource_and_claim_bounds')
    d=inventory['descriptor']
    need((runtime['python_version'],runtime['numpy_version'],runtime['h5py_version'],runtime['hdf5_version'])==
         (d['python_version'],d['numpy_version'],d['h5py_version'],d['hdf5_version'])
         and runtime['selected_inventory_checked_before_package_imports'] is True
         and runtime['full_native_dependency_binary_closure'] is False and runtime['matlab_native_parity'] is False,
         'actual_runtime_versions_and_limits')
    expected_components={'executable':d['executable'],**d['modules']}
    expected_dist={dist+'/'+name:e for dist,row in d['distribution_metadata'].items() for name,e in row['files'].items()}
    for observed,expected in ((runtime['components'],expected_components),(runtime['distribution_metadata'],expected_dist)):
        need(set(observed)==set(expected),'complete_runtime_population')
        for name,e in expected.items():
            row={'path':e['resolved_path'],'bytes':e['bytes'],'mode':e['mode']}
            if 'sha256' in e:row['sha256']=e['sha256']
            else:row.update(mtime_ns=e['mtime_ns'],ctime_ns=e['ctime_ns'],body_hash_observed=False)
            need(observed[name]==row,'complete_runtime_component_'+name)
    need(owner['status']=='completed' and owner['invocations']==1 and owner['retries']==0
         and owner['returncode']==0 and owner['sources_unchanged'] is True
         and owner['argv']==binding['argv'] and owner['binding_sha256']==pin(meta['owner_binding'])['sha256']
         and owner['group_policy']=='new_session','natural_one_attempt_owner')
    group=owner['group_cleanup']
    need(group['group']==owner['pid'] and group['complete'] and group['absent']
         and group['absence_basis']['errno']==3 and group['termination']=='explicit_esrch_observed'
         and group['terminal_errors']==[] and group['signals_sent']==[],'explicit_natural_owned_group_ESRCH')
    need(data['owner:stderr.txt']==b'' and decode(data['owner:stdout.txt'])==
         {'worker_complete':True,'all4452000':True,'all222600':True,'reference_constructed':False},
         'whole_worker_capture')
    expected_streams=[{'path':str(Path(config['owner_root'])/name),**pin(data['owner:'+name])}
                      for name in ('stdout.txt','stderr.txt')]
    need(owner['stream_originals']==expected_streams and
         owner['metadata_bytes_read']==len(meta['owner_binding'])+2*sum(p['bytes'] for p in binding['source_pins'])
         +sum(len(data['owner:'+name]) for name in ('stdout.txt','stderr.txt')),'complete_owner_counters')
    event_count=transport_check(decode(data['transport']),config['generation_tool_request'],config['owner_root'])
    return {'accepted_packet':True,'all_operands':4452000,'all_pair_counts':222600,'all_census_entries':240,
            'all_output_files':8,'all_runtime_components':11,'transport_events':event_count,
            'original_MAT_reread_by_reviewer':False,'statistic_or_scientific_qualification':False,
            'linkage_limit':'Exact reviewed reader, two complete producer original hashes and whole geometry/custody; no second independent MAT decoder.'}

def main():
    global DEADLINE
    start=time.monotonic();DEADLINE=start+330
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('original review deadline')))
    signal.setitimer(signal.ITIMER_REAL,330)
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--config-sha256',required=True)
    p.add_argument('--role',choices=('author','peer'),required=True);args=p.parse_args()
    raw,_=ordinary(args.config,262144);need(pin(raw)['sha256']==args.config_sha256,'exact_review_config')
    config=decode(raw);need(config['schema']=='tms_full_paired_whole_review_v1','review_schema')
    root=Path(config['generation_root']);owner=Path(config['owner_root']);cache=Path(config['cache_root'])
    for path in (root,owner,cache,Path(config[args.role+'_report'])):
        need(path.is_absolute() and '..' not in path.parts
             and not any(x.is_symlink() for x in (path,*path.parents)),'ordinary_bound_namespaces')
    need(set(str(x.relative_to(root)) for x in root.rglob('*') if x.is_file())==set(PACKET)
         and {str(x.relative_to(root)) for x in root.rglob('*') if x.is_dir()}=={'input'}
         and all(not x.is_symlink() for x in root.rglob('*')),'complete_original_packet_census')
    need({x.name for x in owner.iterdir()}=={'OUTCOME.json','stdout.txt','stderr.txt'},'complete_owner_census')
    original_paths=[('packet:'+name,root/name,35616000 if name=='input/values.f64' else 262144) for name in PACKET]
    original_paths += [('owner:'+name,owner/name,1048576 if name.endswith('.txt') else 262144)
                      for name in ('OUTCOME.json','stdout.txt','stderr.txt')]
    original_paths += [('transport',Path(config['transport']),1048576)]
    metadata_paths=[(key,config[key]) for key in ('request','scientific','inventory','owner_binding')]
    selected=[(key,path,cap,None) for key,path,cap in original_paths]
    selected += [('metadata:'+key,Path(row['path']),262144,{k:row[k] for k in ('bytes','sha256')})
                 for key,row in metadata_paths]
    data={};meta={};rows=[];total=0
    if args.role=='author':need(not cache.exists() and not cache.is_symlink(),'one_fresh_cache');cache.mkdir(mode=0o700)
    else:
        raw_capture,_=ordinary(cache/'CAPTURE.private.json',MANIFEST_CAP)
        old=decode(raw_capture);need(old['config_sha256']==args.config_sha256,'same_selected_cache')
    for i,(key,path,cap,expected) in enumerate(selected):
        body,physical=ordinary(path,cap,expected);total+=len(body)
        need(total+MANIFEST_CAP<=CAP,'complete_cache_includes_manifest')
        cached_name=str(i).zfill(2)+'.body'
        row={'key':key,'original':str(path),'cache_file':cached_name,**pin(body),'physical':physical}
        if args.role=='author':write(cache/cached_name,body)
        else:
            need(old['members'][i]==row,'same_complete_original_and_physical_identity')
            cached,_=ordinary(cache/cached_name,cap,pin(body));need(cached==body,'entire_cache_matches_original')
            body=cached  # Peer semantic review consumes the same independently verified cache.
        rows.append(row)
        if key.startswith('metadata:'):meta[key.split(':',1)[1]]=body
        else:data[key]=body
    capture={'schema':'tms_full_paired_one_cache_v1','config_sha256':args.config_sha256,'members':rows,'body_bytes':total}
    if args.role=='author':
        capture_body=encode(capture);need(len(capture_body)<=MANIFEST_CAP and total+len(capture_body)<=CAP,'one_complete_cache_extent')
        write(cache/'CAPTURE.private.json',capture_body);cache.chmod(0o500)
        # Author's independent semantic pass reads the just-verified cache, not a second MAT/original pass.
        data={};meta={}
        for row in rows:
            body,_=ordinary(cache/row['cache_file'],35616000,{k:row[k] for k in ('bytes','sha256')})
            if row['key'].startswith('metadata:'):meta[row['key'].split(':',1)[1]]=body
            else:data[row['key']]=body
    else:
        need(len(old['members'])==len(rows) and old['body_bytes']==total
             and {x.name for x in cache.iterdir()}=={x['cache_file'] for x in rows}|{'CAPTURE.private.json'},
             'complete_one_cache_population')
    report=semantics(data,config,meta);report.update(role=args.role,managed_read_bytes=READS,
        elapsed_seconds=time.monotonic()-start,cache_body_bytes=total,
        source_only_frozen_policy=False,whole_actual_caller_closure_still_required=True)
    target=Path(config[args.role+'_report']);need(not target.exists(),'fresh_review_report')
    target.mkdir(mode=0o700);write(target/'WHOLE_PACKET_REVIEW.private.json',encode(report));target.chmod(0o500)
    print(json.dumps(report));return 0

if __name__=='__main__':raise SystemExit(main())
