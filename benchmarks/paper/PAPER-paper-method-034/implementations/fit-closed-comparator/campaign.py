"""Complete48-fit then48-query fixed operator comparator programme.
Uses the unchanged reviewed MARBLE native phase runtime and bounded framed sink.
No runtime selection or qualified environment is included with this source.
"""
import json,os,stat,struct,time,types
from pathlib import Path
from contract import *
def source_module(name,raw,path):
    m=types.ModuleType(name);m.__file__=str(path);exec(compile(raw,str(path),'exec'),m.__dict__);return m
def bootstrap(repo,here,manifest_pin,budget):
    manifest_raw=budget.read(here/'SOURCE_MANIFEST.json',65536,manifest_pin);manifest=parse(manifest_raw)
    bodies={}
    for row in manifest['files']:
        bodies[row['path']]=budget.read(here/row['path'],row['bytes'],{k:row[k]for k in('bytes','sha256')})
    deps=parse(bodies['DEPENDENCIES.json']);old={}
    for role,row in deps['files'].items():
        old[role]=budget.read(repo/row['path'],row['bytes'],{k:row[k]for k in('bytes','sha256')})
    lib={'bodies':bodies,'old':old,'source':pin(manifest_raw)}
    for role in ('interface','runtime','sink','score_core'):
        lib[role]=source_module('closed_marble_'+role,old[role],repo/deps['files'][role]['path'])
    lib['collector']=source_module('closed_marble_collector',bodies['collector_one.py'],here/'collector_one.py')
    lib['interface'].captured_at=lambda fd,name,limit:budgeted_capture_at(budget,fd,name,limit)
    lib['spec']=parse(old['protocol']);lib['dependencies']=deps
    return lib
def mkdir(path):
    p=ordinary(path);p.mkdir(mode=0o700);return p
def sealed(root):
    for directory,dirs,files in os.walk(root,topdown=False,followlinks=False):
        for name in files:
            p=ordinary(Path(directory)/name);s=p.lstat();need(stat.S_ISREG(s.st_mode)and s.st_nlink==1,'ordinary mounted source')
            os.chmod(p,0o444)
        os.chmod(directory,0o555)
def program(lib,out,budget):
    root=mkdir(out/'program')
    for name in ('native_worker.py','contract.py'):
        budget.write(root/name,lib['bodies'][name])
    budget.write(root/'interface.py',lib['old']['interface'])
    for role,row in lib['dependencies']['files'].items():
        if 'program_target'in row:
            p=root/row['program_target'];p.parent.mkdir(parents=True,exist_ok=True);budget.write(p,lib['old'][role])
    sealed(root);return root
def prefix_labels(raw,rat,interface):
    h=interface.npy_header(raw,(rat['raw_samples'],3));count=rat['split_index'];dtype=h['dtype']
    header=repr({'descr':dtype,'fortran_order':False,'shape':(count,3)}).encode('latin1')
    header+=b' '*((64-((10+len(header)+1)%64))%64)+b'\n'
    return b'\x93NUMPY\x01\x00'+struct.pack('<H',len(header))+header+raw[h['offset']:h['offset']+count*3*int(dtype[-1])]
def exact_inventory(root,budget,cap,entries):
    rows=[];total=0
    for directory,dirs,files in os.walk(root,followlinks=False):
        for d in dirs:need(not(Path(directory)/d).is_symlink(),'no state directory alias')
        for name in files:
            p=ordinary(Path(directory)/name);size=p.stat().st_size;need(total+size<=cap and len(rows)<entries,'complete state capacity')
            raw=budget.read(p,size);rows.append({'path':str(p.relative_to(root)),**pin(raw)});total+=len(raw)
    return sorted(rows,key=lambda r:r['path'])
def validate_runtime(rt,phase,python,identity):
    need(rt['phase']==phase and rt['image']==identity['image']and rt['docker_host']==identity['docker_host']and rt['docker_binary']==identity['docker_binary']['path'],'same selected actual native context')
    expected=[python,'-B','/program/native_worker.py','--phase',phase,'--input','/input','--output','/output']
    if phase=='query':expected+=['--state','/state']
    need(rt['candidate_argv']==expected,'fixed comparator worker invocation')
def plan(config,lib):
    required={'schema','package_root','output','source','assets','runtime_identity','python','jobs','read_bytes','write_bytes','retained_bytes','metadata_bytes','whole_seconds'}
    need(set(config)==required and config['schema']=='marble_closed_comparator_campaign_v1','exact campaign configuration')
    need(config['source']==lib['source'],'source selection')
    spec=lib['spec'];coords=schedule(spec);need(list(config['jobs'])==[key(c)for c in coords],'complete ordered48-job bank')
    identity=config['runtime_identity'];need(set(identity)=={'image','docker_host','docker_binary','versions_evidence'},'explicit original native identity')
    prefixes=[];floor=0
    for c in coords:
        item=config['jobs'][key(c)]
        need(set(item)=={'fit','query','state_bytes','state_entries','worker_limits'},'closed slot')
        for phase in ('fit','query'):
            validate_runtime(item[phase],phase,config['python'],identity);prefixes.append(item[phase]['name_prefix'])
        for name in('state_bytes','state_entries'):need(type(item[name])is int and item[name]>0,'complete state bounds')
        need(set(item['worker_limits'])=={'read_bytes','write_bytes','model_member_bytes','state_metadata_bytes','rng_member_bytes'},'worker bounds')
        for v in item['worker_limits'].values():need(type(v)is int and v>0,'finite positive worker demand')
        r=next(r for r in spec['rats']if r['rat']==c['rat'])
        # Both captured quarantine and final comparator bank copies remain.
        floor+=item['state_bytes']+2*((r['train_rows']+r['test_rows'])*c['dimension']*4+256)
    need(len(set(prefixes))==96,'96 unique native ownership prefixes')
    for k in('read_bytes','write_bytes','retained_bytes','metadata_bytes'):need(type(config[k])is int and config[k]>0,'explicit whole capacity')
    need(type(config['whole_seconds'])in(int,float)and math.isfinite(config['whole_seconds'])and config['whole_seconds']>0,'whole lifecycle clock')
    need(config['metadata_bytes']>=4096,'aggregate metadata failure reserve')
    need(config['retained_bytes']>=floor+config['metadata_bytes'],'complete state/output retention before first fit')
    return coords
def stream_spec(c,phase,item):
    return {'phase':phase,'embeddings':[filename(c,phase)],'state_bytes':item['state_bytes']if phase=='fit'else 0,'state_entries':item['state_entries']if phase=='fit'else 0,'stream_bytes':item[phase]['streams']['collector_stdout_bytes'],'payload_bytes':item[phase]['output_limits']['bytes']}
def preflight_phases(config,lib,coords,prog,collector,out):
    # Admit every exact future native selection before the first fit. Paths are
    # literal future ownership paths; this call never creates or starts a worker.
    for phase in('fit','query'):
        for c in coords:
            item=config['jobs'][key(c)];mounts={'/program':str(prog),'/input':str(out/(key(c)+'--'+phase)/'input')}
            if phase=='query':mounts['/state']=str(out/(key(c)+'--fit')/'capture/state')
            spec=stream_spec(c,phase,item);lib['collector'].spec_check(spec)
            lib['runtime'].selected(item[phase],mounts,str(collector),['--root','/output','--spec',encode(spec).decode().strip()])
class MetadataLedger:
    """Aggregate retained host JSON, including an unreclaimed failure reserve."""
    def __init__(self,budget,cap):
        need(type(cap)is int and cap>=4096,'aggregate metadata includes failure reserve')
        self.budget=budget;self.cap=cap;self.used=4096
        budget.charge('write',4096)
    def write(self,path,raw):
        need(self.used+len(raw)<=self.cap,'aggregate retained metadata ceiling')
        self.used+=len(raw) # precharge before any open/write; never refund failure
        return self.budget.write(path,raw)
def run(config,lib,budget,phase_runner=None,clock=time.monotonic):
    coords=plan(config,lib);out=mkdir(config['output']);started=clock();end=started+config['whole_seconds']
    metadata=MetadataLedger(budget,config['metadata_bytes'])
    attempts=[{'coordinate':c,'fit':'not_attempted','query':'not_attempted'}for c in coords];fits={};banks={};queries={}
    def save(name,value):
        raw=encode(value);need(len(raw)<=config['metadata_bytes'],'bounded complete metadata')
        return metadata.write(out/name,raw)
    def guard():
        need(clock()<end,'complete campaign deadline')
        total=count=0
        for directory,dirs,files in os.walk(out,followlinks=False):
            for name in dirs:need(not(Path(directory)/name).is_symlink(),'owned directory alias')
            for name in files:
                p=Path(directory)/name;s=p.lstat();need(stat.S_ISREG(s.st_mode)and s.st_nlink==1,'ordinary retained output');total+=s.st_size;count+=1
        need(total<=config['retained_bytes'],'complete retained output ceiling')
    try:
        package=ordinary(config['package_root'])
        assets=parse(budget.read(package/'private/ASSETS.json',config['assets']['bytes'],config['assets']));assets={r['path']:r for r in assets['files']}
        native=config['runtime_identity']
        budget.read(native['docker_binary']['path'],native['docker_binary']['bytes'],{k:native['docker_binary'][k]for k in('bytes','sha256')})
        staged_input_bound=0
        for c in coords:
            for split in ('train','test'):
                staged_input_bound+=assets[f"public/input/{c['condition']}-{c['rat']}-{split}.npy"]['bytes']
            if c['method']=='cebra-behavior':staged_input_bound+=assets[f"private/labels/{c['rat']}.npy"]['bytes']+128
        output_floor=sum(config['jobs'][key(c)]['state_bytes']+2*((next(r for r in lib['spec']['rats']if r['rat']==c['rat'])['train_rows']+next(r for r in lib['spec']['rats']if r['rat']==c['rat'])['test_rows'])*c['dimension']*4+256)for c in coords)
        program_bound=sum(len(v)for v in lib['bodies'].values())+sum(len(v)for v in lib['old'].values())
        need(config['retained_bytes']>=staged_input_bound+output_floor+program_bound+config['metadata_bytes'],'full staged inputs/program/state/output/metadata retention')
        prog=program(lib,out,budget);collector=out/'collector.py';budget.write(collector,lib['bodies']['collector_one.py'])
        preflight_phases(config,lib,coords,prog,collector,out)
        for method in METHODS:banks[method]=mkdir(out/method)
        save('SELECTION.json',config);save('PLANNED.json',attempts)
        runner=lib['runtime'].run_phase if phase_runner is None else phase_runner
        for phase in('fit','query'):
            for ordinal,c in enumerate(coords):
                guard();k=key(c);item=config['jobs'][k];rat=next(r for r in lib['spec']['rats']if r['rat']==c['rat']);split='train'if phase=='fit'else'test'
                folder=mkdir(out/(k+'--'+phase));view=mkdir(folder/'input')
                relative=f"public/input/{c['condition']}-{c['rat']}-{split}.npy";asset=assets[relative];expected={v:asset[v]for v in('bytes','sha256')}
                raw=budget.read(package/relative,expected['bytes'],expected)
                shape=[rat['split_index']if phase=='fit'else rat['raw_samples']-rat['split_index'],rat['neurons']if c['condition']=='clean'else len(rat['half_columns_zero_based'])]
                lib['interface'].npy_header(raw,shape);budget.write(view/'neural.npy',raw);label_pin=None
                if phase=='fit'and c['method']=='cebra-behavior':
                    relative=f"private/labels/{c['rat']}.npy";asset=assets[relative];expected_label={v:asset[v]for v in('bytes','sha256')}
                    labels=budget.read(package/relative,expected_label['bytes'],expected_label)
                    label_pin=budget.write(view/'labels.npy',prefix_labels(labels,rat,lib['interface']))
                closure=None if phase=='fit'else fits[k]['closure']
                job={'schema':'marble_closed_comparator_job_v1','coordinate':c,'phase':phase,'protocol':{'id':PROTOCOL,**pin(lib['old']['protocol'])},'source':lib['source'],'input':expected,'input_shape':shape,'labels':label_pin,'closure':closure,'limits':item['worker_limits']}
                job_check(job,phase);metadata.write(view/'JOB.json',encode(job));sealed(view)
                mounts={'/program':str(prog),'/input':str(view)}
                if phase=='query':
                    previous=fits[k];state=previous['state_root']
                    need(exact_inventory(state,budget,item['state_bytes'],item['state_entries'])==previous['state_files'],'complete unchanged fit state')
                    mounts['/state']=str(state)
                spec=stream_spec(c,phase,item)
                lib['collector'].spec_check(spec);attempts[ordinal][phase]='dispatched';save(f'ATTEMPTS-{phase}-{ordinal:02d}.json',attempts)
                receive=lib['sink'].Receiver(folder/'capture',spec,min(end,clock()+item[phase]['clocks']['whole_seconds']),clock);events=[]
                def journal(event):
                    body=encode(event);need(len(body)<=item[phase]['streams']['journal_bytes'],'bounded runtime observation')
                    metadata.write(folder/f'JOURNAL-{len(events):04d}.json',body);events.append(pin(body));guard()
                def chunk(raw):budget.charge('write',len(raw));receive.feed(raw);guard()
                try:
                    observed=runner(item[phase],mounts,str(collector),['--root','/output','--spec',encode(spec).decode().strip()],chunk,journal,started=clock())
                    closed_observation(observed)
                    stream=receive.finish()
                finally:receive.close()
                name=filename(c,phase);path=folder/'capture/embeddings'/name;size=path.stat().st_size
                body=budget.read(path,size);lib['interface'].npy_header(body,(rat[split+'_rows'],c['dimension']))
                ep=budget.write(banks[c['method']]/name,body)
                phase_pin=metadata.write(folder/'OBSERVED.json',encode(observed))
                if phase=='fit':
                    state=folder/'capture/state';state_files=exact_inventory(state,budget,item['state_bytes'],item['state_entries'])
                    state_raw=budget.read(state/'STATE.json',item['worker_limits']['state_metadata_bytes']);meta=parse(state_raw)
                    need(meta['coordinate']==c and meta['source']==lib['source']and meta['protocol']==job['protocol']and meta['training_embedding']==ep and meta['training_input']==job['input']and meta['training_labels']==label_pin and meta['recipe']==recipe(c)and meta['model_mode']=='eval','actual selected training output/state join')
                    closure={'state_metadata':pin(state_raw),'training_embedding':ep,'observed':phase_pin,'state_manifest':pin(encode(state_files))}
                    fits[k]={'closure':closure,'state_root':state,'state_files':state_files};sealed(state)
                    metadata.write(folder/'FIT_CLOSURE.json',encode({'coordinate':c,**closure,'files':state_files,'qualification':False}))
                else:
                    need(exact_inventory(fits[k]['state_root'],budget,item['state_bytes'],item['state_entries'])==fits[k]['state_files'],'state retained after query')
                completed={'coordinate':c,'phase':phase,'embedding':ep,'observation':phase_pin,'events':events,'job':pin(encode(job))}
                if phase=='query':queries[k]={**completed,'fit_closure':closure}
                attempts[ordinal][phase]='closed';metadata.write(folder/'COMPLETE.json',encode(completed))
        panels={}
        for method in METHODS:
            metadata.write(banks[method]/'submission.json',encode({'schema':'marble_embedding_submission_v1','protocol_id':PROTOCOL,'access_view':'B','method':method,'method_name':'fixed fit-closed prospective native comparator'}))
            # Existing admission captures every embedding before the trusted scorer is reachable.
            admitted=lib['interface'].admit(banks[method],lib['spec'],'B',method);panels[method]=admitted[2]
        guard()
        result={'schema':'marble_closed_comparator_bank_v1','protocol':{'id':PROTOCOL,**pin(lib['old']['protocol'])},'source':lib['source'],'assets':config['assets'],'fits':[{'coordinate':c,**fits[key(c)]['closure']}for c in coords],'queries':[queries[key(c)]for c in coords],'attempts':attempts,'panels':panels,'fit_count':48,'query_count':48,'embeddings':96,'native_parity_qualified':False,'semantic_no_refit_proven':False,'external_native_qualification_required':True}
        save('BANK.json',result);guard();return result
    except BaseException as error:
        # Preserve all already captured bytes and original attempt census.
        raw=encode({'schema':'marble_comparator_campaign_failure_v1','error_type':type(error).__name__,'error':str(error)[:1000],'completed_fits':len(fits),'all_outputs_retained':True,'qualification':False})
        need(len(raw)<=4096,'reserved failure extent')
        with (out/'FAILURE.json').open('xb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
        raise

