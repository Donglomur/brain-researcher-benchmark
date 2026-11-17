"""Actual opaque model seals; selected-method assertions never self-qualify semantics."""
import hashlib
import os
from pathlib import Path
from .common import capture,parse,require,keys,stamp,ordinary,pin
from .registry import PEOPLE,token

METHOD_FIELDS=('schema','cell','fitted_people','fit_rows','learned_transforms','inner_search','selected_settings',
               'inference_action_policy','source_lineage')

def selected_method(body,cell):
    value=parse(body);keys(value,METHOD_FIELDS,('reference_detail',))
    require(value['schema']=='neural055-selected-method-v2' and value['cell']==cell,'same full-cell selected method')
    eligible=set(PEOPLE)-{cell['outer_person']}
    require(type(value['fitted_people'])is list and len(set(value['fitted_people']))==len(value['fitted_people']) and set(value['fitted_people'])<=eligible,'declared permitted fitting people')
    require(type(value['fit_rows'])is list and len(set(value['fit_rows']))==len(value['fit_rows']) and all(type(i)is int and 0<=i<16540 for i in value['fit_rows']),'declared original training rows')
    require(type(value['learned_transforms'])is list and type(value['inner_search'])is list and type(value['source_lineage'])is list,'complete typed method records')
    require(type(value['inference_action_policy'])is dict and value['inference_action_policy'].get('query_fit') is False,'explicit selected no-query-fit policy')
    if cell['mode']!='REFERENCE':
        actions=value['inference_action_policy'].get('broker_actions')
        require(type(actions)is list,'public ABI sealed broker action list, empty if unused')
        for action in actions:
            keys(action,('provider','operation'))
            require(all(type(action[k])is str and action[k] for k in ('provider','operation')),'literal declared broker action')
    return value

def file_identity(path,budget,cap):
    p=Path(path);s=ordinary(p);require(0<s.st_size<=cap,'opaque model/output cap')
    budget.admit_read(s.st_size+1);h=hashlib.sha256();count=0;fd=None;first=None;failures=[]
    try:
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
        require(stamp(os.fstat(fd))==stamp(s),'same opaque source handle')
        while True:
            budget.check('before opaque source read');body=os.read(fd,min(1048576,s.st_size+1-count));count+=len(body);budget.read(len(body));h.update(body)
            budget.check('after opaque source read return');require(count<=s.st_size,'opaque source grew')
            if not body:break
        require(count==s.st_size and stamp(os.fstat(fd))==stamp(s)==stamp(p.lstat()),'whole stable opaque source')
    except BaseException as exc:first=exc;failures.append(exc)
    finally:
        if fd is not None:
            try:os.close(fd)
            except BaseException as exc:
                failures.append(exc)
                budget.uncertain('opaque:'+str(p),'managed_descriptor_closure',exc,descriptor=fd)
                if first is None:first=exc
    if first is not None:
        from .common import CaptureFailure
        raise CaptureFailure(first,[('opaque',e) for e in failures],None,{'path':str(p),'observed_bytes':count,'sha256':h.hexdigest()}) from first
    budget.check('after opaque source close')
    return {'bytes':count,'sha256':h.hexdigest()}

class Seal:
    def __init__(self,cell,source_identity,fit_view,original_phase,journal,budget):
        self.cell=cell;self.budget=budget;self.original_phase=original_phase
        require(original_phase.cell==cell and original_phase.kind=='fit' and original_phase.closed and original_phase.errors.first is None,'original natural closed same-cell FIT')
        require(fit_view['phase']=='FIT' and fit_view['cell']==cell and not {'query.npy','CASE.json','ASSETS.json','candidate_features.npy'}&set(fit_view['files']),'no query exposure in original FIT view')
        require(original_phase.natural['ExitCode']==0 and not original_phase.natural['OOMKilled'],'original natural FIT zero')
        out=original_phase.outputs;require(set(out)=={'model.bin','selected_method.json','operations.json'},'complete selected-method phase ABI')
        self.model=Path(out['model.bin']['path']);self.model_pin=file_identity(self.model,budget,268435456)
        require(self.model_pin=={k:out['model.bin'][k] for k in ('bytes','sha256')},'actual captured opaque model')
        d=out['selected_method.json'];path=Path(d['path'])
        raw=capture(path.parent,dict(path=path.name,bytes=d['bytes'],sha256=d['sha256'],mode=oct(path.stat().st_mode&0o777),role='selected_method_sidecar'),budget,8388608)
        self.method=selected_method(raw,cell)
        os.chmod(self.model,0o444);self.model_stamp=stamp(self.model.lstat())
        self.document={'schema':'neural055-original-model-seal-v2','cell':cell,'source_identity':source_identity,'model':self.model_pin,
                       'fit_view':fit_view,'selected_method':pin(raw),'inference_action_policy':self.method['inference_action_policy'],
                       'original_native':original_phase.document(),'query_exposed_count':0,'semantic_qualification':'independent_post_operation_review_required'}
        self.receipt=journal.json(token(cell)+'-MODEL_SEAL.json',self.document)
        budget.check('after actual model sealing',original_phase.deadline)
    def unchanged(self):
        require(stamp(self.model.lstat())==self.model_stamp,'same original sealed model')
        require(file_identity(self.model,self.budget,268435456)==self.model_pin,'whole exact original sealed model')
        return self.model
