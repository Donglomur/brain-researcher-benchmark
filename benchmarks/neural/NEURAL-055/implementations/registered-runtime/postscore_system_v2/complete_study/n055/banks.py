"""Original independent training banks; query outputs are never reusable state."""
import os
from pathlib import Path
from .common import require,parse,capture,encoded,sha,stamp,diagnostic_type
from .registry import cell,training_key,token,PEOPLE,SEEDS
from .seals import Seal
from .native import PhaseCustody

def expected_training_cells():
    result=[]
    for ref in ('R1','R2','R3'):
        for arm in ('FULL','PRE_ONLY','POST_ONLY'):
            for seed in (SEEDS if ref=='R3' else ('DETERMINISTIC',)):
                result.extend(cell(ref,'REFERENCE','REFERENCE',seed,arm,p) for p in PEOPLE)
    require(len(result)==150 and len({token(training_key(c)) for c in result})==150,'all150 independent training-bank keys')
    return result

class TrainingBanks:
    def __init__(self,plan,source,inputs,views,host,journal,budget,authority):
        self.plan=plan;self.source=source;self.inputs=inputs;self.views=views;self.host=host
        self.journal=journal;self.budget=budget;self.authority=authority;self.expected=expected_training_cells()
        self.rows={token(training_key(c)):{'cell':c,'status':'unattempted_after_failure','original':None,'seal':None,'cause':None} for c in self.expected}
        self.base=journal.root/'reference_banks';self.base.mkdir(mode=0o700)
        self.subject={'schema':'neural055-independent-reference-recipe-subject-v1','runtime_source':source.identity,
                      'resource_policy':budget.resource_policy,
                      'input_index':inputs.identity,'environment':plan['runtime_environment'],
                      'expected_training_keys':[training_key(c) for c in self.expected],
                      'expected_training_jobs':8520,'full_reference_design':plan['reference_qualification']['design']}
        # Qualification is of an independently reviewed, preexisting complete
        # recipe/backend/competence evidence. It does not invent current fits.
        self.qualification=authority.verify(plan['reference_qualification']['receipt'],'reference_recipe_qualification',self.subject)
    def fit(self,c):
        key=token(training_key(c));row=self.rows[key]
        require(row['status']=='unattempted_after_failure','one original training-bank attempt')
        row['status']='attempted';start=self.budget.cost_point();view=None;first=None;observation=None;custody=PhaseCustody()
        row['resource_policy']=self.budget.resource_policy
        action_origin=start['clock'];deadline=self.budget.action_deadline(self.plan['phase_limits']['reference_fit'])
        try:
            with self.budget.action(deadline):
                view,view_identity=self.views.build(c,'FIT',deadline)
                runtime=self.source.actor_current();programme=runtime/'reference_entry.py'
                output=self.base/key
                observation=self.host.phase(c,'fit',programme,view,None,output,runtime,deadline,action_origin,role='reference',custody=custody)
                require(observation is custody.phase,'same producer-owned original reference phase')
                row['original']=observation
                seal=Seal(c,self.source.identity,view_identity,observation,self.journal,self.budget)
                row['seal']=seal
                d=observation.outputs['operations.json'];path=Path(d['path'])
                raw=capture(path.parent,dict(path=path.name,mode=oct(path.stat().st_mode&0o777),role='reference_operations',
                            bytes=d['bytes'],sha256=d['sha256']),self.budget,8388608)
                operations=parse(raw)
                require(operations['schema']=='neural055-reference-original-operations-v1' and operations['cell']==c and operations['phase']=='fit','same original reference operations')
                require(operations['original_first_error'] is None and all(r['status']=='complete' for r in operations['records']),'all expected original reference fitting work completed')
                from .learning import expected_jobs
                jobs=expected_jobs(c['evaluated_system'],c['outer_person'],training_key(c)['mask'],c['seed'],[p for p in PEOPLE if p!=c['outer_person']])
                require(encoded([r['expected_identity'] for r in operations['records']])==encoded(jobs),'complete exact inner/final job registry')
                self.views.retire(view,deadline);view=None
                # This directory contains exactly original FIT artifacts; no
                # queries, target maps or outer predictions can enter a T1 bank.
                directory=seal.model.parent
                require({p.name for p in directory.iterdir()}=={'model.bin','selected_method.json','operations.json'},'training-only exact bank namespace')
                stamps={}
                for p in directory.iterdir():os.chmod(p,0o444);stamps[p.name]=stamp(p.lstat())
                os.chmod(directory,0o555)
                row.update(status='complete',directory=directory,stamps=stamps,operations=operations,
                           calibration=seal.method['reference_detail']['calibration']['status'])
        except BaseException as exc:
            first=exc;row['cause']=exc;row['status']='safe_failed'
            self.journal.carrier.fail(exc,'reference-bank:'+key)
            native=custody.phase
            if native is not None:row['original']=native
            if native is not None and not native.closed:row['status']='blocked_unresolved_containment'
        finally:
            if view is not None:
                try:self.views.retire(view,deadline)
                except BaseException as exc:
                    self.journal.carrier.fail(exc,'reference-view-retirement:'+key);row['status']='blocked_unresolved_containment'
                    if first is None:first=exc;row['cause']=exc
            row['setup']=None;row['setup_closure_raw']=None;row['setup_publication']=None
            try:
                row['operation_ids']=[k for k,v in self.budget.operations.items() if v.get('native_id')==getattr(row['original'],'id',None)]
                if row['original'] is not None:
                    row['operation_ids']=[x.id for x in row['original'].commands]+[row['original'].id]
                row['setup_native_expected_unobserved']=[x for x in self.budget.native_unobserved if x['operation']in row['operation_ids']]
                # This immutable production receipt precedes its own full cost
                # closure. It makes no circular claim to include its final write.
                publication=self.document(row)
                publication['setup_finalization']='pending_original_publication_and_clock_closure'
                record=self.journal.json(key+'-BANK.json',publication)
                row['setup_publication']={'path':record['path'],'bytes':record['observed_bytes'],
                                          'sha256':record['sha256'],'mode':'0o444','role':'original_training_bank_publication'}
                path=self.journal.root/record['path'];os.chmod(path,0o444)
                self.budget.admit('after original immutable bank publication',deadline)
                end=self.budget.cost_point()
                setup={k:end[k]-start[k] for k in ('cpu_seconds','read_bytes','write_bytes','files','model_calls','stream_bytes')}
                setup['wall_seconds']=end['clock']-start['clock']
                # Immutable supervisor-owned observation, retained with the row.
                # Subsequent cell/campaign reports publish this existing record;
                # those reports are charged to their own original lifetimes.
                closure={'schema':'neural055-original-bank-setup-closure-v1','source':self.source.identity,
                         'resource_policy':self.budget.resource_policy,'training_key':training_key(c),
                         'publication':row['setup_publication'],'original_start':start,'original_end':end,
                         'original_deadline':deadline,'setup':setup,'operation_ids':row['operation_ids'],
                         'publication_complete_before_end':True}
                row['setup_closure_raw']=encoded(closure)
                row['setup_closure_sha256']=sha(row['setup_closure_raw']);row['setup']=setup
                self.budget.admit('after original setup observation custody',deadline)
            except BaseException as exc:
                self.journal.carrier.fail(exc,'reference-setup-publication-and-cost:'+key)
                row['setup']=None;row['setup_failure_type']=diagnostic_type(exc)
                if row['status']!='blocked_unresolved_containment':row['status']='reference_unqualified'
                if first is None:first=exc;row['cause']=exc
        return row
    def selected_row(self,c,tool=False):
        keycell=dict(c)
        if tool:keycell.update(evaluated_system='R2',mode='REFERENCE',tool_setting='REFERENCE',seed='DETERMINISTIC')
        key=token(training_key(keycell));row=self.rows[key]
        require(row['status']=='complete' and row.get('setup') is not None,'independent complete qualified original bank required')
        require(row.get('resource_policy')==self.budget.resource_policy and self.budget.resource_policy is not None,'exact current setup resource policy; no backfill')
        raw=row.get('setup_closure_raw');require(type(raw)is bytes and sha(raw)==row['setup_closure_sha256'],'immutable original setup observation')
        closure=parse(raw)
        require(closure['schema']=='neural055-original-bank-setup-closure-v1' and closure['source']==self.source.identity
                and closure['resource_policy']==self.budget.resource_policy and closure['training_key']==training_key(keycell)
                and closure['publication']==row['setup_publication'] and closure['setup']==row['setup']
                and closure['operation_ids']==row['operation_ids'] and closure['publication_complete_before_end']is True,
                'same source/key/publication/cost original setup closure')
        require(closure['original_start']['clock']<=closure['original_end']['clock']<=closure['original_deadline'],'original complete setup chronology')
        for k in ('wall_seconds','cpu_seconds','read_bytes','write_bytes','files','model_calls','stream_bytes'):require(k in row['setup']and row['setup'][k]is not None and row['setup'][k]>=0,'no missing/free measured standalone setup')
        return row
    def setup_for(self,c,tool=False):
        # No file/native/scientific effect. The consumer opens its matched
        # envelope before revalidating any bank artifacts.
        return dict(self.selected_row(c,tool)['setup'])
    def get(self,c,tool=False):
        row=self.selected_row(c,tool)
        self.budget.admit('before current training-bank revalidation')
        capture(self.journal.root,row['setup_publication'],self.budget,16777216)
        seal=row['seal'];seal.unchanged()
        require({p.name for p in row['directory'].iterdir()}==set(row['stamps']),'same exact readonly training-only bank namespace')
        require(all(stamp((row['directory']/n).lstat())==s for n,s in row['stamps'].items()),'unchanged training-only artifacts')
        return row
    def document(self,row):
        return {'cell':row['cell'],'training_key':training_key(row['cell']),'status':row['status'],
                'first_error':None if row['cause'] is None else {'type':diagnostic_type(row['cause'])},
                'original':None if row['original'] is None else row['original'].document(),
                'seal':None if row['seal'] is None else row['seal'].document,
                'setup_standalone_cost':row.get('setup'),'original_physical_operation_ids':row.get('operation_ids',[]),
                'setup_publication':row.get('setup_publication'),
                'setup_closure':None if row.get('setup_closure_raw')is None else parse(row['setup_closure_raw']),
                'setup_closure_sha256':row.get('setup_closure_sha256'),
                'resource_policy':row.get('resource_policy'),'setup_native_expected_unobserved':row.get('setup_native_expected_unobserved'),
                'no_outer_query_outputs_in_reusable_bank':True}

