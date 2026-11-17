"""Exact051 lifecycle function pair with076namespace; source-only adaptation."""
import time,uuid,re
from common import need
from capture import capture_output

def case_lifecycle(e,d,snapshot,c,view,attempt,destination,writer,end):
    """Task adaptation of reviewed069/CASCADE ordering; exact ownership only."""
    r=e.r;start=time.monotonic();command_start=len(d.records);work=end-60;items=[];closures=[];failure=None;natural=None;score=None;candidate_closed=False
    prefix='neural076-'+uuid.uuid4().hex[:24]
    def item(role,kind):
        x={'kind':kind,'name':prefix+'-'+role,'owner':prefix+'/'+role,'attempted':False,'acknowledged':False};items.append(x)
        writer.json(attempt/('INTENT-'+role+'.json'),x,4096);return x
    def before(x):need(r.resource_inventory(d,x,x['owner'],work,'before_'+x['kind'])==[])
    def create(x,role,mounts,memory):
        before(x);x['attempted']=True
        ident=r.call(d,r.create_args(x,role,mounts,memory),work,'create_'+role,4096,12).decode('ascii').strip()
        need(re.fullmatch('[a-f0-9]{64}',ident));x.update(id=ident,acknowledged=True)
        r.admission(r.inspect(d,'container',ident,work,'admit_'+role),x,role,mounts,memory)
    try:
        need(time.monotonic()<work-30)
        image=r.parse(r.call(d,['image','inspect',r.IMAGE,'--format','{{json .}}'],work,'image',131072))
        need(image['Id']==r.IMAGE and not image['Config'].get('Volumes') and (not image['Config'].get('Healthcheck') or image['Config']['Healthcheck'].get('Test')==['NONE']))
        volume=item('volume','volume');before(volume);volume['attempted']=True
        result=r.call(d,['volume','create','--driver','local','--label',r.LABEL+'='+volume['owner'],'--opt','type=tmpfs','--opt','device=tmpfs','--opt','o='+r.VOLUME_OPTIONS,volume['name']],work,'create_volume',4096).decode().strip()
        need(result==volume['name']);volume['acknowledged']=True
        v=r.inspect(d,'volume',volume['name'],work,'volume_admit');r.owned(v,volume,volume['owner'])
        need(v['Driver']=='local' and v['Options']=={'type':'tmpfs','device':'tmpfs','o':r.VOLUME_OPTIONS})
        holder=item('holder','container');hm={'/trusted/holder.py':('bind',snapshot/'holder.py',False),'/capture':('volume',volume['name'],False)}
        create(holder,'holder',hm,268435456);r.call(d,['container','start',holder['id']],work,'holder_start',4096)
        need(r.parse(r.call(d,['exec',holder['id'],'python','-I','-B','/trusted/holder.py','ready'],work,'holder_ready',4096))=={'ready':True})
        producer=item('candidate','container');cm={'/entry.py':('bind',snapshot/'entry.py',False),'/submission/program.py':('bind',snapshot/'program.py',False),'/case':('bind',view,False),'/output':('volume',volume['name'],True)}
        create(producer,'candidate',cm,c['memory_bytes']);begin=time.monotonic()
        r.call(d,['container','start',producer['id']],work,'candidate_start',4096)
        reply=d(['container','wait',producer['id']],min(work,begin+c['candidate_seconds']),'candidate_wait',4096)
        state=r.inspect(d,'container',producer['id'],work,'candidate_exit');r.owned(state,producer,producer['owner'])
        natural={k:state['State'][k]for k in ('Status','Running','Dead','Pid','ExitCode','OOMKilled')}
        need(reply.strip()==b'0' and natural=={'Status':'exited','Running':False,'Dead':False,'Pid':0,'ExitCode':0,'OOMKilled':False} and time.monotonic()-begin<=c['candidate_seconds'])
        close=r.retire(d,producer,work);closures.append(close);need(close['closed'] and close['removed']);items.remove(producer);candidate_closed=True
        score=capture_output(e,d,holder,work,destination,writer)
    except BaseException as exc:failure=type(exc).__name__
    finally:
        for x in reversed(items):
            try:closures.append(r.retire(d,x,end))
            except BaseException as exc:closures.append({'kind':x['kind'],'name':x['name'],'closed':False,'error_type':type(exc).__name__})
    closed=len(closures)==3 and all(x.get('closed') and x.get('removed') and x.get('absence_observed') and x.get('creation_outcome_unknown') is False for x in closures)
    return {'schema':'neural076_case_lifecycle_v1','status':'captured' if failure is None and score is not None and closed and d.reaped else 'failed',
            'program':c['program'],'condition':c['condition'],'image':r.IMAGE,'score':score,'natural_exit':natural,
            'candidate_closed_before_capture':candidate_closed,'closures':closures,'all_resources_closed':closed,'cli_reaped':d.reaped,
            'error_type':failure,'elapsed_seconds':time.monotonic()-start,'limit_seconds':c['candidate_seconds']+420,
            'command_metadata':[dict(x) for x in d.records[command_start:]],'private_scoring_called':False}

def lifecycle_closed(x):
    need(x['status']=='captured' and x['all_resources_closed'] is True and x['candidate_closed_before_capture'] is True
         and x['cli_reaped'] is True and x['error_type'] is None and x['private_scoring_called'] is False
         and x['natural_exit']=={'Status':'exited','Running':False,'Dead':False,'Pid':0,'ExitCode':0,'OOMKilled':False}
         and 0<=x['elapsed_seconds']<=x['limit_seconds'])
    need(len(x['closures'])==3 and all(z.get('closed') and z.get('removed') and z.get('absence_observed') and z.get('creation_outcome_unknown') is False for z in x['closures']))
    return True
