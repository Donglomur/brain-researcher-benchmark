"""Build the full32 ERP packet from authenticated external materials.

This operator tool keeps participant queries under public/ and targets/source
joins under private/. Supply trusted metadata descriptors and the exact historical
four-demo operands. File hashes authenticate bytes against those descriptors;
they do not establish provider provenance or participant process isolation.
"""
from __future__ import annotations
import hashlib
import hmac
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import struct
import sys
import time

CONDITION='erp-core-remaining-persons-released-marker-v1'
PEOPLE=['sub-008','sub-009']+[f'sub-{i:03}' for i in range(11,41)]
TARGET={11,22,33,44,55}
STIM={10*a+b for a in range(1,6) for b in range(1,6)}
DEFAULT_LIMITS={'read_bytes':8*1024**3,'output_bytes':512*1024**2,'query_line_bytes':60000,'metadata_file_bytes':1024**2,'source_chunk_bytes':2162688}
RECIPE_PIN={'bytes':2143,'sha256':'f6a16ba460ae3e3478a358cc499b8b69a3cc9ac0308d3334ebc48dc1d1c6feea'}
CENSUS_SHA='08df53adeeda8a4d3ba1ae6110490a239155e17678a8ac4753ed6807b2ffc155'
DEMO_PIN={'bytes':129921,'sha256':'19e4018216376af334fd5ead21e2c33d5761d9d56ce5c76d3a89411483906ed2'}
PROMPT_PIN={'bytes':1703,'sha256':'2ecc6656d099083f2d87112147430aa1f780c714ce31579e025c69ac74ec77a0'}
SCHEMA_PIN={'bytes':480,'sha256':'bd0c92c7016a20b039fbb273aad8802be1da088b0f1fec3e15fac0a1070eed12'}

class Refusal(ValueError):pass

def need(ok,message):
    if not ok:raise Refusal(message)

def unique(pairs):
    result={}
    for key,value in pairs:
        need(key not in result,'Duplicate JSON key');result[key]=value
    return result

def parse(body):
    return json.loads(body,object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(Refusal('Nonfinite JSON')))

def encoded(value):
    return (json.dumps(value,allow_nan=False,ensure_ascii=False,separators=(',',':'))+'\n').encode()

def descriptor(body):return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}

def identity(st):return (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)

class Budget:
    def __init__(self,deadline,limits=None,cleanup_deadline=None):
        self.deadline=deadline;self.cleanup_deadline=deadline if cleanup_deadline is None else cleanup_deadline
        need(math.isfinite(deadline) and math.isfinite(self.cleanup_deadline) and self.cleanup_deadline>=deadline,'Finite ordered work/cleanup deadline')
        self.limits=dict(DEFAULT_LIMITS if limits is None else limits)
        need(set(self.limits)==set(DEFAULT_LIMITS),'Exact packet budget keys')
        need(all(type(v) is int and v>0 for v in self.limits.values()),'Positive integer packet bounds')
        need(self.limits['query_line_bytes']==60000 and self.limits['source_chunk_bytes']%132==0,'Canonical line/chunk geometry')
        self.read_bytes=0;self.output_bytes=0
    def check(self):need(time.monotonic()<self.deadline,'Packet work deadline')
    def read(self,count):
        self.check();need(type(count)is int and count>=0 and self.read_bytes+count<=self.limits['read_bytes'],'Packet logical-read cap before read');self.read_bytes+=count
    def write(self,count,cleanup=False):
        need(time.monotonic()<(self.cleanup_deadline if cleanup else self.deadline),'Packet write deadline')
        ceiling=self.limits['output_bytes'] if cleanup else self.limits['output_bytes']-1048576
        need(self.output_bytes+count<=ceiling,'Packet output cap before write; preserve final-receipt reserve');self.output_bytes+=count

def pinned(path,pin,budget,cap=None):
    need(type(pin['bytes'])is int and pin['bytes']>0,'Input size pin')
    if cap is not None:need(pin['bytes']<=cap,'Input role cap')
    budget.read(pin['bytes']);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==pin['bytes'],'Exact ordinary single-link input')
        with os.fdopen(fd,'rb',closefd=False) as stream:body=stream.read(pin['bytes'])
        need(identity(before)==identity(os.fstat(fd)) and descriptor(body)=={k:pin[k] for k in ('bytes','sha256')},'Exact unchanged input bytes')
    finally:os.close(fd)
    return body

def require_directory(path):
    path=Path(path).absolute();need(path.resolve(strict=True)==path and stat.S_ISDIR(path.lstat().st_mode),'Trusted canonical ordinary directory');return path

class Output:
    def __init__(self,path,budget):
        self.path=Path(path).absolute();need(self.path.parent.resolve(strict=True)==self.path.parent,'Trusted output parent')
        self.path.mkdir(mode=0o700,exist_ok=False);self.budget=budget;self.files={};self.opened_files=[]
        for name in ['public','public/queries','private','private/people']:(self.path/name).mkdir(mode=0o700)
    def write(self,name,body,cleanup=False):
        need(type(body)is bytes and not Path(name).is_absolute() and '..'not in Path(name).parts,'Fixed relative output')
        self.budget.write(len(body),cleanup=cleanup);fd=os.open(self.path/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        self.opened_files.append(name)
        try:
            with os.fdopen(fd,'wb',closefd=False) as stream:stream.write(body);stream.flush();os.fsync(fd)
        finally:os.close(fd)
        pin=descriptor(body);self.files[name]=pin;return pin
    def document(self,name,value,cleanup=False):return self.write(name,encoded(value),cleanup=cleanup)
    def stream_queries(self,name,records):
        fd=os.open(self.path/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);digest=hashlib.sha256();count=size=0;index=[]
        self.opened_files.append(name)
        try:
            with os.fdopen(fd,'wb',closefd=False) as stream:
                for trial_id,body in records:
                    need(len(body)<=self.budget.limits['query_line_bytes'] and body.endswith(b'\n'),'Complete bounded query line')
                    self.budget.write(len(body));stream.write(body);digest.update(body)
                    index.append({'trial_id':trial_id,'path':name.removeprefix('public/'),'offset':size,**descriptor(body)});size+=len(body);count+=1
                stream.flush();os.fsync(fd)
        finally:os.close(fd)
        self.files[name]={'bytes':size,'sha256':digest.hexdigest()};return index,count

def check_inputs(value):
    need(value['schema']=='erp-core-full32-packet-inputs-v1' and value['condition_id']==CONDITION,'Condition input schema')
    rows=value['participants'];need([r['participant_id'] for r in rows]==PEOPLE and value['people']==32 and value['queries']==6400,'Exact full32 source complement')
    need(value['metadata_census']['sha256']==CENSUS_SHA,'Accepted full32 metadata census identity')
    for row in rows:
        summary=row['summary'];need(summary['stimuli']==200 and summary['targets']==40 and summary['nontargets']==160 and summary['channels']==33 and summary['sample_rate_hz']==1024,'Authenticated metadata census geometry')
        fdt=row['fdt'];need(fdt['basename']==row['participant_id']+'_task-P3_eeg.fdt' and fdt['source_path']==row['participant_id']+'/eeg/'+fdt['basename'],'Exact FDT identity')
        need(type(fdt['bytes'])is int and fdt['bytes']==summary['samples']*33*4,'Declared source bytes/sample geometry')
    return rows

def validate_metadata(meta,row):
    need(meta['participant_id']==row['participant_id'] and meta['status']=='metadata_admitted_signal_unread' and meta['summary']==row['summary'],'Accepted person metadata identity')
    need(meta['external_data']['basename']==row['fdt']['basename'] and meta['external_data']['manifest_declared_bytes']==row['fdt']['bytes'],'External FDT metadata identity')
    events=meta['events_operator_only'];stimuli=meta['stimuli_operator_only']
    needed=[x for x in events if x['event_code'] in STIM]
    need(stimuli==needed and len(stimuli)==row['summary']['stimuli'],'Every admitted stimulus retained in source order')
    n=row['summary']['samples'];anchors=[]
    for event in stimuli:
        a=event['released_anchor_0based'];code=event['event_code']
        need(type(a)is int and a==event['set_latency_1based']-1 and a==event['tsv_sample']-1,'Unchanged released-marker coordinates')
        need(a>=256 and a+768<=n and type(event['target'])is int and event['target']==int(code in TARGET),'Original complete epoch/target definition')
        anchors.append(a)
    need(len(set(anchors))==len(anchors) and anchors==sorted(anchors),'Unique ordered source anchors')
    return stimuli

def opaque_id(key,kind,person,anchor=None):
    message=encoded([CONDITION,kind,person,anchor]);return ('q-' if kind=='query' else 'p-')+hmac.new(key,message,hashlib.sha256).hexdigest()[:32 if kind=='query' else 24]

def load_recipe(recipe_path,recipe_pin,budget):
    body=pinned(recipe_path,recipe_pin,budget,16384);spec=importlib.util.spec_from_loader('erp_full32_exact_recipe',loader=None);module=importlib.util.module_from_spec(spec)
    module.__file__=str(recipe_path);exec(compile(body,str(recipe_path),'exec'),module.__dict__)
    need(module.np.__version__=='1.26.3' and sys.version_info[:3]==(3,11,6),'Frozen Python3.11.6/NumPy1.26.3 recipe runtime required')
    return module

def read_epochs(path,pin,summary,stimuli,order,budget,np):
    """Same full-source finite gate and raw epoch/byte layout as conversion_core."""
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==pin['bytes'],'Exact FDT regular-file geometry')
        digest=hashlib.sha256();remaining=pin['bytes']
        with os.fdopen(fd,'rb',closefd=False) as stream:
            while remaining:
                count=min(1048576,remaining);budget.read(count);body=stream.read(count);need(len(body)==count,'Truncated FDT authentication');digest.update(body);remaining-=count
            need(digest.hexdigest()==pin['sha256'] and identity(before)==identity(os.fstat(fd)),'Complete FDT source hash before sample decoding')
            stream.seek(0);remaining=pin['bytes']
            while remaining:
                count=min(budget.limits['source_chunk_bytes'],remaining);budget.read(count);body=stream.read(count);need(len(body)==count,'Truncated FDT finite scan')
                need(np.isfinite(np.frombuffer(body,dtype='<f4')).all(),'Nonfinite source amplitude; no trial deletion');remaining-=count
            raw=np.empty((len(stimuli),33,1024),dtype=np.float32);checks=0
            for out_index,source_index in enumerate(order):
                a=stimuli[source_index]['released_anchor_0based'];stream.seek((a-256)*33*4);budget.read(33*1024*4);body=stream.read(33*1024*4)
                need(len(body)==33*1024*4,'Complete native epoch bytes');raw[out_index]=np.frombuffer(body,dtype='<f4').reshape(1024,33).T
                for offset in (-256,-1,0,127,767):
                    for channel in range(33):
                        stream.seek(((a+offset)*33+channel)*4);budget.read(4);scalar=stream.read(4)
                        need(len(scalar)==4 and struct.unpack('<f',scalar)[0]==float(raw[out_index,channel,offset+256]),'Independent direct-byte sample/channel identity');checks+=1
            need(identity(before)==identity(os.fstat(fd)),'FDT changed during extraction')
    finally:os.close(fd)
    need(summary['samples']*33*4==pin['bytes'],'Source continuous geometry')
    return raw,checks

def build(inputs_path,inputs_pin,metadata_root,fdt_root,demonstrations_path,output,deadline,*,prompt_path,response_schema_path,key_path,key_pin,limits=None,cleanup_deadline=None):
    """Return a complete packet census or an explicit incomplete census.

    The caller supplies trusted external descriptors and keeps private outputs
    away from participants. This function performs no download, model call or fit.
    Every FDT is authenticated on the same open descriptor before decoding.
    """
    budget=Budget(deadline,limits,cleanup_deadline=cleanup_deadline);inputs=parse(pinned(inputs_path,inputs_pin,budget,131072));rows=check_inputs(inputs)
    metadata_root=require_directory(metadata_root);fdt_root=require_directory(fdt_root)
    census=parse(pinned(metadata_root/'ALL32_METADATA_ADMISSION.json',inputs['metadata_census'],budget,262144))
    need(census['selected_participants']==PEOPLE and census['full_cohort_complete'] is True and census['total_stimuli']==6400,'Accepted complete metadata census')
    need([{'participant_id':r['participant_id'],'summary':r['summary'],'record':r['record']} for r in census['participants']]==[{'participant_id':r['participant_id'],'summary':r['summary'],'record':{k:r['metadata'][k] for k in ('bytes','sha256')}} for r in rows],'Per-person census pins unchanged')
    demos=pinned(demonstrations_path,DEMO_PIN,budget,129921);prompt=pinned(prompt_path,PROMPT_PIN,budget,1703);schema=pinned(response_schema_path,SCHEMA_PIN,budget,480)
    key=pinned(key_path,key_pin,budget,32);need(len(key)==32,'Private32-byte opaque identity key')
    recipe=load_recipe(Path(__file__).with_name('recipe.py'),RECIPE_PIN,budget);np=recipe.np
    out=Output(output,budget)
    status_rows=[];roster=[];private_index=[];seen_ids=set();seen_people=set();failure=False
    try:
        out.document('STARTED.json',{'schema':'erp-core-full32-packet-started-v1','condition_id':CONDITION,'selected_participants':PEOPLE,'queries':6400,'private_key_sha256':key_pin['sha256'],'new_benchmarks':0})
        out.write('public/demonstrations.json',demos);out.write('public/prompt.txt',prompt);out.write('public/response_schema.json',schema)
        for row in rows:
            person=row['participant_id']
            if time.monotonic()>=deadline:
                status_rows.append({'participant_id':person,'status':'not_attempted_deadline'});failure=True;continue
            try:
                meta=parse(pinned(metadata_root/(person+'.json'),row['metadata'],budget,budget.limits['metadata_file_bytes']));stimuli=validate_metadata(meta,row)
                need(meta['channel_order']==list(recipe.CHANNELS),'Authenticated channel order must match unchanged historical recipe')
                case=opaque_id(key,'person',person);need(case not in seen_people,'Opaque person collision');seen_people.add(case)
                ids=[opaque_id(key,'query',person,x['released_anchor_0based']) for x in stimuli]
                need(len(set(ids))==200 and not seen_ids.intersection(ids),'Opaque query collision');order=sorted(range(len(ids)),key=lambda i:ids[i]);seen_ids.update(ids)
                raw,checks=read_epochs(fdt_root/row['fdt']['basename'],row['fdt'],row['summary'],stimuli,order,budget,np)
                waveforms=recipe.transform(raw)
                def records():
                    for j,i in enumerate(order):
                        body,error=recipe.record_bytes(ids[i],waveforms[j]);need(error==0.,'Lossless historical serialization');yield ids[i],body
                entries,count=out.stream_queries('public/queries/'+case+'.jsonl',records());need(count==200,'Every authenticated person trial retained')
                private_rows=[{'trial_id':ids[i],'source_anchor_0based':stimuli[i]['released_anchor_0based'],'source_event_code':stimuli[i]['event_code'],'target':stimuli[i]['target']} for i in order]
                private_pin=out.document('private/people/'+case+'.json',{'participant_id':person,'opaque_person_id':case,'trials':private_rows,'metadata_pin':row['metadata'],'source_fdt':row['fdt'],'independent_struct_checks':checks})
                roster.extend(entries);private_index.append({'participant_id':person,'opaque_person_id':case,'trials':200,'record':private_pin,'path':'private/people/'+case+'.json'})
                status_rows.append({'participant_id':person,'status':'packet_person_complete','trials':count,'independent_struct_checks':checks})
                del raw,waveforms
            except Exception as exc:
                failure=True;record={'participant_id':person,'status':'packet_person_failed_no_omission','error_type':type(exc).__name__,'message':str(exc)[:512]};status_rows.append(record)
                # Attempt a bounded diagnostic only while ordinary work remains.
                if time.monotonic()<deadline:out.document('private/'+person+'.FAILED.json',record)
        complete=not failure and len(status_rows)==32 and len(roster)==6400 and len({x['trial_id'] for x in roster})==6400
        if complete:
            roster.sort(key=lambda x:x['trial_id']);out.document('public/roster.json',roster);out.document('private/PARTICIPANT_JOIN.json',private_index)
            public_files={name.removeprefix('public/'):pin for name,pin in sorted(out.files.items()) if name.startswith('public/')}
            public_manifest={'schema':'erp-core-full32-public-packet-v1','benchmark_id':'NEURAL-077','condition_id':CONDITION,'people':32,'query_count':6400,'demonstration_count':4,'natural_class_prior_supplied':False,'channel_order':['Cz','Pz'],'shape_per_query':[2,1024],'sampling_hz':1024,'sample_offsets':[-256,768],'physical_display_shift_established':False,'extra_marker_shift_samples':0,'native_units':'EEGLAB stored amplitude; independent physical calibration unresolved','files':public_files,'transport_qualified':False,'model_context_qualified':False,'old400_unchanged':True,'new_benchmarks':0}
            out.document('public/PACKET.json',public_manifest)
    except BaseException as exc:
        failure=True
        finished={r['participant_id'] for r in status_rows}
        for person in PEOPLE:
            if person not in finished:status_rows.append({'participant_id':person,'status':'not_attempted_owner_failure','error_type':type(exc).__name__})
    # Completion metadata is bounded cleanup work; the outer owner owns its hard
    # deadline. Never promote partial public files to a complete packet.
    complete=not failure and len(status_rows)==32 and all(r['status']=='packet_person_complete' for r in status_rows) and 'public/PACKET.json' in out.files
    census={'schema':'erp-core-full32-packet-census-v1','status':'full32_packet_materialized_no_models' if complete else 'incomplete_full32_packet','condition_id':CONDITION,'participants':status_rows,'full_cohort_complete':complete,'query_count':6400 if complete else None,'private_key_sha256':key_pin['sha256'],'read_bytes_charged':budget.read_bytes,'read_counter_scope':'Explicit builder input bytes reserved before reads; caller descriptor authentication and runtime-library reads are separate','output_bytes_before_final_receipt':budget.output_bytes,'all32_sources_required':True,'no_person_omission_or_replacement':True,'new_benchmarks':0,'model_calls':0,'fits':0,'physical_display_shift_established':False,'runtime_transport_qualified':False,'files':dict(out.files),'uncommitted_files':[name for name in out.opened_files if name not in out.files],'uncommitted_file_policy':'Preserved incomplete bytes are not admitted or assigned completed-file hashes; outer cleanup inventories them without promoting a partial packet'}
    # Caller must reserve cleanup time; no unbounded cleanup exemption exists.
    out.document('COMPLETE.json' if complete else 'INCOMPLETE.json',census,cleanup=True)
    return census

def cli(argv=None):
    """Build from explicit external paths; output must be a fresh directory."""
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['build'])
    for name in ['inputs','metadata-root','fdt-root','demonstrations','prompt','response-schema','key','output']:
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--inputs-bytes',type=int,required=True)
    parser.add_argument('--inputs-sha256',required=True)
    parser.add_argument('--key-sha256',required=True)
    parser.add_argument('--work-seconds',type=float,default=1740)
    parser.add_argument('--whole-seconds',type=float,default=1800)
    args=parser.parse_args(argv);start=time.monotonic()
    need(0<args.work_seconds<=1740 and args.work_seconds+5<=args.whole_seconds<=1800,'Work and cleanup must fit the30-minute whole bound')
    result=build(args.inputs,{'bytes':args.inputs_bytes,'sha256':args.inputs_sha256},args.metadata_root,args.fdt_root,args.demonstrations,args.output,start+args.work_seconds,
        prompt_path=args.prompt,response_schema_path=args.response_schema,
        key_path=args.key,key_pin={'bytes':32,'sha256':args.key_sha256},cleanup_deadline=start+args.whole_seconds)
    print(json.dumps({'status':result['status'],'full_cohort_complete':result['full_cohort_complete'],'query_count':result['query_count'],'model_calls':0,'new_benchmarks':0}))
    return 0 if result['full_cohort_complete'] else 2

if __name__=='__main__':
    raise SystemExit(cli())
