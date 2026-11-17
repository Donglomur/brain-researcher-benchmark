"""Task-local adaptation of reviewed NEURAL069 create/capture/retire lifecycle.
No program execution, Docker operation or data read occurs at import.
"""
import base64,os,re,time,uuid
from pathlib import Path
import runtime as r
need=r.need;pin=r.pin;encoded=r.encoded;parse=r.parse
WRITE=None
def save(p,b,cap=1000000):
    need(WRITE is not None,'Preventive write budget');return WRITE.save(p,b,cap)
def syncdir(p):
    fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

def lifecycle(d,snapshot,c,lock,paths,attempt,verify_inputs,end):
    started=time.monotonic();command_start=len(d.records);work=end-60;items=[];closures=[];captured={};natural=None;failure=None;candidate_closed=False
    prefix='cascade44-'+uuid.uuid4().hex[:24]
    def item(role,kind):
        v={'kind':kind,'name':prefix+'-'+role,'owner':prefix+'/'+role,'attempted':False,'acknowledged':False};items.append(v)
        save(attempt/('INTENT-'+role+'.json'),encoded(v),4096);syncdir(attempt);return v
    def before(v):need(r.resource_inventory(d,v,v['owner'],work,'before_'+v['kind'])==[],'Fresh scoped resource')
    def create(v,role,mounts,memory):
        before(v);v['attempted']=True
        identity=r.call(d,r.create_args(v,role,mounts,memory),work,'create_'+role,4096,12).decode('ascii').strip();need(re.fullmatch('[a-f0-9]{64}',identity)is not None,'Created ID');v.update(id=identity,acknowledged=True)
        r.admission(r.inspect(d,'container',identity,work,'admit_'+role),v,role,mounts,memory)
    result={'schema':'cascade44_fold_lifecycle_v1','status':'failed','program_seal':c['program_seal'],'source_manifest':c['source_manifest'],'runtime_contract':c['runtime_contract'],'image':r.IMAGE,'candidate_seconds':c['candidate_seconds'],'memory_bytes':c['memory_bytes'],'candidate_started':False,'private_scoring_called':False,'namespace':prefix}
    try:
        image=parse(r.call(d,['image','inspect',r.IMAGE,'--format','{{json .}}'],work,'image',131072))
        need(image['Id']==r.IMAGE and not image['Config'].get('Volumes')and(not image['Config'].get('Healthcheck')or image['Config']['Healthcheck'].get('Test')==['NONE']),'Existing image without implicit resources')
        volume=item('volume','volume');before(volume);volume['attempted']=True
        response=r.call(d,['volume','create','--driver','local','--label',r.LABEL+'='+volume['owner'],'--opt','type=tmpfs','--opt','device=tmpfs','--opt','o='+r.VOLUME_OPTIONS,volume['name']],work,'create_volume',4096).decode().strip();need(response==volume['name'],'Volume acknowledgment');volume['acknowledged']=True
        v=r.inspect(d,'volume',volume['name'],work,'admit_volume');r.owned(v,volume,volume['owner']);need(v['Driver']=='local'and v['Options']=={'type':'tmpfs','device':'tmpfs','o':r.VOLUME_OPTIONS},'Exact tmpfs')
        keeper=item('holder','container');hm={'/trusted/holder.py':('bind',snapshot/'holder.py',False),'/trusted/LOCK.json':('bind',snapshot/'CAPTURE_LOCK.json',False),'/capture':('volume',volume['name'],False)}
        create(keeper,'holder',hm,134217728);r.call(d,['container','start',keeper['id']],work,'start_holder',4096)
        need(parse(r.call(d,['exec',keeper['id'],'python','-I','-B','/trusted/holder.py','ready'],work,'holder_ready',4096))=={'ready':True},'Live readonly keeper')
        producer=item('candidate','container');cm={'/entry.py':('bind',snapshot/'entry.py',False),'/run/PROGRAM_BINDING.json':('bind',snapshot/'PROGRAM_BINDING.json',False),'/output':('volume',volume['name'],True)}
        program=Path(c.get('program_directory',snapshot/'program'))
        actual={str(f.relative_to(program))for f in program.rglob('*')if f.is_file()}
        need(actual==set(c['program_files']),'Exact immutable program mount roster')
        for name in c['program_files']:cm['/program/'+name]=('bind',program/name,False)
        cm.update({'/input/'+n:('bind',p,False)for n,p in paths.items()});create(producer,'candidate',cm,c['memory_bytes'])
        begin=time.monotonic();result['candidate_started']=True;r.call(d,['container','start',producer['id']],work,'candidate_start',4096)
        raw=d(['container','wait',producer['id']],min(work,begin+c['candidate_seconds']),'candidate_wait',4096)
        wait_reply=raw.strip();v=r.inspect(d,'container',producer['id'],work,'candidate_exit');r.owned(v,producer,producer['owner']);s=v['State']
        natural={k:s[k]for k in ('Status','Running','Dead','Pid','ExitCode','OOMKilled')};need(wait_reply==b'0'and s['Status']=='exited'and s['Running']is False and s['Dead']is False and s['Pid']==0 and s['ExitCode']==0 and s['OOMKilled']is False,'Observed exit0/noOOM')
        natural={k:s[k]for k in ('Status','Running','Dead','Pid','ExitCode','OOMKilled')};result['observed_candidate_seconds']=time.monotonic()-begin;need(result['observed_candidate_seconds']<=c['candidate_seconds'],'Candidate elapsed')
        close=r.retire(d,producer,work);closures.append(close);need(close['closed']and close['removed'],'Removed producer before capture');items.remove(producer);candidate_closed=True
        idx=parse(r.call(d,['exec',keeper['id'],'python','-I','-B','/trusted/holder.py','index'],work,'capture_index',40000))
        need(type(idx)is dict and set(idx)=={'schema','files'}and idx['schema']=='cascade_spinal_capture_index_v1','Trusted index')
        rows=idx['files'];need(type(rows)is list and len(rows)==2 and [v['path']for v in rows]==['fold.json','predictions.npy'],'Exact captured outputs')
        for row in rows:
            need(set(row)=={'path','bytes','sha256'}and type(row['bytes'])is int and 0<row['bytes']<= (100000 if row['path']=='fold.json' else lock['prediction_max_bytes']) and re.fullmatch('[a-f0-9]{64}',row['sha256'])is not None,'Captured extent/pin')
        need(sum(v['bytes']for v in rows)<=1100000,'Combined capture cap')
        for row in rows:
            n=row['path'];raw=r.call(d,['exec',keeper['id'],'python','-I','-B','/trusted/holder.py','file','--name',n],work,'capture_file',4*((row['bytes']+2)//3)+1024)
            reply=parse(raw);need(type(reply)is dict and set(reply)=={'schema','path','bytes','sha256','base64'}and reply['schema']=='cascade_spinal_capture_file_v1'and reply['path']==n,'Capture reply')
            body=base64.b64decode(reply['base64'],validate=True);need(pin(body)=={k:row[k]for k in ('bytes','sha256')}=={k:reply[k]for k in ('bytes','sha256')},'Exact same bytes captured');captured[n]=body
            need(sum(map(len,captured.values()))<=1100000,'Complete output byte cap')
    except BaseException as error:failure=type(error).__name__
    finally:
        # The internal alarm reserves this cleanup tail; no retries/new work.
        for v in reversed(items):
            try:closures.append(r.retire(d,v,end))
            except BaseException as error:closures.append({'kind':v['kind'],'name':v['name'],'closed':False,'error_type':type(error).__name__})
    result.update(closures=closures,all_resources_closed=len(closures)==3 and all(v['closed']for v in closures),cli_reaped=d.reaped,natural_exit=natural,candidate_closed_before_capture=candidate_closed,command_metadata=[dict(v)for v in d.records[command_start:]],error_type=failure)
    if failure is None and len(captured)==2 and result['all_resources_closed']and result['cli_reaped']:
        try:
            result['public_post_pin']=verify_inputs();need(time.monotonic()<end,'Before publication deadline')
            output=attempt/'captured';WRITE.mkdir(output);rows=[]
            for n,b in captured.items():rows.append({'path':n,**save(output/n,b,1100000)})
            syncdir(output);result.update(status='captured',outputs=rows)
        except BaseException as error:result.update(status='failed',error_type=type(error).__name__)
    result['elapsed_seconds']=time.monotonic()-started;result['selected_fold_seconds']=c['candidate_seconds']+420;return result
