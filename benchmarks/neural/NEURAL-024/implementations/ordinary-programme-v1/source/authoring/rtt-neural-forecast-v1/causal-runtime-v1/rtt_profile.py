"""The original candidate and grade roles over one explicit prepared-case custody map."""
import copy
import re
from common import HERE,ROOT,Engine,legacy,need,assets,regular,strict,pin,save

IMAGE=legacy.IMAGE
LABELS=('candidate','grade')
from prepared_binding import packet


def mapping(run,label):
    need(label in LABELS,'Only candidate and grade over existing prepared case')
    case=packet();need(str(run)==case['new_run'],'one fixed runtime destination')
    if label=='candidate':
        return {'/program/program.py':(str(run/'program.py'),True),
                '/training/source_counts.npz':(case['public']['source_counts.npz']['path'],True),
                '/training/calibration_counts.npz':(case['public']['calibration_counts.npz']['path'],True),
                '/public/TASK.md':(str(HERE/'TASK.md'),True),
                '/public/PROTOCOL.json':(str(HERE/'PROTOCOL.json'),True)}
    held=assets();need(held['binding_status']=='bound_scientific_source','Exact held science required')
    value={destination:(str(ROOT/descriptor['path']),True)for destination,descriptor in held['grade_readonly'].items()}
    for name,row in case['private'].items():value['/private/'+name]=(row['path'],True)
    value['/submission/commits.jsonl']=(str(run/'candidate/commits.jsonl'),True)
    value['/source/invocation.json']=(str(run/'grade/invocation.json'),True)
    value['/out']=(str(run/'grade/output'),False)
    return value


def command(label,mounts):
    need(label in LABELS,'Exact phase command')
    if label=='candidate':return ['-I','-B','/program/program.py']
    config=pin(mounts['/source/SCIENTIFIC_INPUTS.json'][0],64000)
    value=['-I','-B','/source/'+label+'.py','--inputs','/source/SCIENTIFIC_INPUTS.json',
           '--inputs-sha256',config['sha256']]
    if label=='grade':
        invocation=pin(mounts['/source/invocation.json'][0],32768)
        value+=['--invocation','/source/invocation.json','--invocation-sha256',invocation['sha256']]
    return value+['--out','/out']


def limits(label):
    cpu=(1050,1051) if label=='candidate' else (59,60)
    size={'prepare':45260800,'candidate':16777216,'grade':131072}[label]
    return {**legacy.ULIMITS,'cpu':cpu,'fsize':(size,size)}


def create_args(name,label,mounts):
    argv=['create','--pull','never','--name',name,'--network','none','--read-only','--user','65534:65534',
          '--cap-drop','ALL','--security-opt','no-new-privileges:true','--memory',str(3*1024**3),
          '--memory-swap',str(3*1024**3),'--cpus','1.75','--pids-limit','32','--shm-size','1048576',
          '--restart','no','--log-driver','none','--workdir','/tmp','--entrypoint','python',
          '--tmpfs','/tmp:'+legacy.TMPFS['/tmp']]
    if label=='candidate':argv+=['-i']
    for key,(lo,hi) in limits(label).items():argv+=['--ulimit',f'{key}={lo}:{hi}']
    for key in legacy.THREADS:argv+=['--env',key+'=1']
    argv+=['--env','PYTHONDONTWRITEBYTECODE=1']
    for destination,(source,ro) in sorted(mounts.items()):
        need(source.startswith('/') and not any(c in source for c in ',\r\n'),'Exact literal mount')
        argv+=['--mount',f'type=bind,src={source},dst={destination}'+(',readonly' if ro else '')]
    return argv+[IMAGE,*command(label,mounts)]


def verify_exact(info,name,label,mounts,base_env):
    h,c=info['HostConfig'],info['Config']
    need(h['Memory']==h['MemorySwap']==3*1024**3 and h['NanoCpus']==1750000000,
         'Exact1.75CPU/3GiB within aggregate2CPU/4GiB')
    need('OomKillDisable' in h and (h['OomKillDisable'] is None or h['OomKillDisable'] is False),
         'Strict null/false OOM setting')
    need(c['Cmd']==command(label,mounts) and c.get('StdinOnce') is (label=='candidate')
         and len(h['Ulimits'])==len(limits(label))
         and {r['Name']:(r['Soft'],r['Hard']) for r in h['Ulimits']}==limits(label),'Exact command and limits')
    environment=dict(base_env);environment.update({key:'1' for key in legacy.THREADS},PYTHONDONTWRITEBYTECODE='1')
    normalized=copy.deepcopy(info)
    normalized['HostConfig']['Memory']=normalized['HostConfig']['MemorySwap']=4*1024**3
    normalized['HostConfig']['NanoCpus']=2000000000
    normalized['HostConfig']['Ulimits']=[{'Name':k,'Soft':lo,'Hard':hi} for k,(lo,hi) in legacy.ULIMITS.items()]
    program='program.py' if label=='candidate' else label+'.py'
    normalized['Config']['Cmd']=['-I','-B','/program/'+program]
    legacy.verify(normalized,name,mounts,environment,'65534:65534',program,label=='candidate')
    need(h['AutoRemove'] is False,'Explicit owned removal')
    return {'status':'exact_rtt_causal_boundary_verified','label':label,
            'readonly_mounts':sum(ro for _,ro in mounts.values()),'interactive':label=='candidate',
            'threads':1,'declared_profile_delta_verified':True}


def returned_identity(record,name,argv):
    need(type(record) is dict and set(record)=={'name','argv','returncode','stdout','stderr'}
         and record['name']==name and record['argv']==argv and type(record['returncode']) is int
         and type(record['stdout']) is str and type(record['stderr']) is str
         and len(record['stdout'])<=65536 and len(record['stderr'])<=65536,'Exact saved create result')
    if record['returncode']==0:
        need(re.fullmatch('[a-f0-9]{64}\n',record['stdout']) and not record['stderr'],'One successful immutable create ID')
        return record['stdout'][:-1]
    return None


def agree_identities(returned,observed):
    need(returned is None or type(returned) is str and re.fullmatch('[a-f0-9]{64}',returned),'Returned ID shape')
    need(all(type(value) is str and re.fullmatch('[a-f0-9]{64}',value) for value in observed),'Observed ID shapes')
    values=set(observed)
    if returned is not None:values.add(returned)
    need(len(values)<=1,'Create-returned and every inspected/live immutable ID agree')
    return values


class StreamEngine(Engine):
    def create_task(self,name,label,mounts,environment):
        argv=create_args(name,label,mounts);self.own('container',name,argv)
        reply=self.run(argv,cap=65536)
        record={'name':name,'argv':argv,'returncode':reply.returncode,
                'stdout':reply.stdout.decode('ascii',errors='replace'),'stderr':reply.stderr.decode('ascii',errors='replace')}
        save(self.out/'create_result.json',record,self.budget,150000)
        returned=returned_identity(record,name,argv)
        need(reply.returncode==0,'Owned task created')
        inspected=self.inspect('container',name)
        agree_identities(returned,[inspected.get('Id')])
        return inspected,verify_exact(inspected,name,label,mounts,environment)
