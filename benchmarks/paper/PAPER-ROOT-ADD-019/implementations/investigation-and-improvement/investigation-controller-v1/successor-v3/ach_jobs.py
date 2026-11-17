"""Fixed physical process protocol for generated source and trusted reference source."""
import secrets
from pathlib import PurePosixPath
from ach_util import need,pin,pin_bytes,encode,decode,exact_fields,finite,finish_owned

STRATA=('offer_CPIn','reward_SideOff','side_on','opt_out')

class ToolExecutionFailure(ValueError):
    """Independently closed ordinary child failure, never a scientific result."""
    def __init__(self,receipt):
        super().__init__('generated training programme failed');self.receipt=receipt

def safe_name(name):
    need(type(name) is str and name not in ('','.','..') and PurePosixPath(name).name==name and
         '/' not in name and '\\' not in name and all(ord(c)>=32 for c in name),'ordinary opaque output name')
    return name

class Jobs:
    def __init__(self,transport,ledger,journal,worker_source,limits,python_path,exposure_pin):
        self.transport,self.ledger,self.journal=transport,ledger,journal
        self.worker=worker_source;self.limits=limits;self.python=python_path;self.exposure_pin=exposure_pin
        need(type(worker_source) is bytes and type(python_path) is str and python_path.startswith('/'),'pinned worker and admitted interpreter')
    def run(self,kind,source,payload,materials,*,sealed=None,extra_sources=None):
        job='job_'+secrets.token_hex(16);context='realm_'+secrets.token_hex(16)
        raw=encode(payload);sealed={} if sealed is None else sealed;extra_sources={} if extra_sources is None else extra_sources
        need(len(source)<=self.limits['code_bytes'] and len(raw)<=self.limits['input_bytes'],'preventive complete source/input extent')
        need(sum(len(v) for v in sealed.values())<=self.limits['model_bytes'],'complete sealed state extent')
        request={'schema':'ach_generated_program_job_v1','job_id':job,'kind':kind,
            'program':{'path':'/program/PROGRAM.py',**pin_bytes(source)},
            'input':{'path':'/request/INPUT.json',**pin_bytes(raw)},'limits':self.limits,
            'origin_ns':self.ledger.origin,'deadline_ns':self.ledger.scientific}
        files={'/source/WORKER.py':self.worker,'/program/PROGRAM.py':source,
               '/request/INPUT.json':raw,'/request/JOB.json':encode(request)}
        for name,body in sealed.items():files['/request/sealed/'+safe_name(name)]=body
        for name,body in extra_sources.items():
            need(name.startswith('/source/') and name not in files,'separate fixed trusted source')
            files[name]=body
        view={'schema':'ach_minimized_process_view_v1','materials':materials,'exposure_admission':self.exposure_pin,
            'forbidden_feedback':['native','reference_results','outer_labels','other_contexts']}
        self.ledger.reserve({'processes':1,'retained_bytes':sum(map(len,files.values()))},kind+'/complete staged inputs')
        live=self.ledger.acquire_live(sum(map(len,files.values()))+self.limits['model_bytes']+self.limits['result_bytes'],kind+'/live inputs and result')
        primary=None
        try:
            self.journal.append('job_attempt',{'job':job,'context':context,'kind':kind,'source_pin':pin_bytes(source),
                'payload_pin':pin_bytes(raw),'sealed':{k:pin_bytes(v) for k,v in sealed.items()},'view_pin':pin(view)})
            outcome=self.transport.run(context,job,files,view,[self.python,'-I','-B','/source/WORKER.py'],kind)
            outputs=outcome['outputs'];need('EXECUTION.json' in outputs,'trusted execution evidence')
            evidence=decode(outputs['EXECUTION.json'],self.limits['result_bytes'])
            need(evidence['program_pin']==pin_bytes(source) and evidence['input_pin']==pin_bytes(raw) and
                 type(evidence['actual_child_exit_code']) is int and evidence['actual_child_exit_code']>=0 and
                 evidence['job_id']==job,'actual source/input/natural child result lineage')
            observation=outcome['record']['observation']
            for name in ('stdout','stderr'):
                need(evidence[name+'_pin']=={k:observation[name][k] for k in ('bytes','sha256')},
                     'independently retained complete generated child stream')
            if evidence['actual_child_exit_code']!=0:
                need(evidence['status']=='generated_program_failed','explicit independently closed failed proposal')
                failure={'execution':evidence,'closure_pin':outcome['record']['observation_pin'],
                    'artifact_pins':{k:pin_bytes(v) for k,v in outputs.items()}}
                self.journal.append('training_program_failure',failure)
                raise ToolExecutionFailure(failure)
            need(evidence['status']=='completed' and 'RESULT.json' in outputs,'actual successful typed result')
            result=decode(outputs['RESULT.json'],self.limits['result_bytes'])
            self.journal.append('job_success',{'record':outcome['record'],'execution':evidence,'result':result,
                'artifact_pins':{k:pin_bytes(v) for k,v in outputs.items()}})
            return {'result':result,'files':{k:v for k,v in outputs.items() if k not in ('RESULT.json','EXECUTION.json')},
                'closure_pin':outcome['record']['observation_pin'],'record':outcome['record']}
        except ToolExecutionFailure as error:primary=error;raise
        except BaseException as error:
            primary=error
            self.ledger.fail(kind,error)
            try:self.journal.failure(kind,error)
            except BaseException as close_error:
                setattr(error,'journal_close_error',type(close_error).__name__)
            raise
        finally:finish_owned([('job live reservation release',lambda:self.ledger.release_live(live))],primary)

    def candidate_fit(self,source,training,materials):
        out=self.run('fit',source,{'kind':'fit','training':training},materials)
        result=out['result'];exact_fields(result,('kind','heads','method_description'),'candidate fit result')
        need(result['kind']=='fit' and set(result['heads'])==set(STRATA),'complete four-head candidate bundle')
        need(type(result['method_description']) is str and len(result['method_description'])<=8192,'bounded method description')
        referenced=set()
        for names in result['heads'].values():
            need(type(names) is list and names and len(names)==len(set(names)),'complete nonempty head state references')
            for name in names:need(safe_name(name) in out['files'],'head references actual immutable state');referenced.add(name)
        need(referenced==set(out['files']),'all generated fitted state accounted in four heads')
        return {**out,'source':source,'state_pin':pin({k:pin_bytes(v) for k,v in out['files'].items()}),
            'head_manifest_pin':pin(result['heads'])}
    def candidate_predict(self,fit,query,materials):
        out=self.run('predict',fit['source'],{'kind':'predict','query':query,'heads':fit['result']['heads'],
            'model_files':{k:'/request/sealed/'+k for k in fit['files']}},materials,sealed=fit['files'])
        r=out['result'];exact_fields(r,('kind','id','log_seconds'),'one actual target-free prediction')
        need(r['kind']=='predict' and r['id']==query['id'] and not out['files'],'exact query prediction, no updated state')
        return finite(r['log_seconds']),out
