"""Complete source-owned preparation/80-cell reference/80-cell candidate/scoring chain."""
import os
from pathlib import Path
from .domain import need,fields,encoded,parse,sha,cell,cell_key,registry,prediction
from .storage import write,json_write,array_bytes,read
from .preparation import Prepared
from .runtime.common import FailureCarrier
from .runtime.native import DockerHost,PhaseCustody
from .execution import QualifiedRunner

class CellAttempt:
    def __init__(self,campaign,cell_,role):
        self.campaign=campaign;self.cell=cell(cell_);self.role=role;self.key=cell_key(cell_);self.fit=PhaseCustody();self.infer=PhaseCustody()
        self.status='retained_before_effects';self.first=None;self.errors=FailureCarrier();self.prediction=None;self.model=None;self.fit_seal=None;self.views=[]
        campaign.attempts.append(self);campaign.authority.retain(self)

    def terminal(self):
        return {'cell':self.cell,'role':self.role,'status':self.status,'fit_phase_id':None if self.fit.phase is None else self.fit.phase.id,'infer_phase_id':None if self.infer.phase is None else self.infer.phase.id,'fit_seal':self.fit_seal,'errors':self.errors.document(),'partial_objects_retained':True}

class Campaign:
    def __init__(self,authority,journal):
        self.authority=authority;self.journal=journal;self.budget=authority.budget;self.carrier=journal.carrier;self.attempts=[];self.prepared=None;self.score_open=False
        self.programmes={};self.commits={};authority.retain(self)
        for mode,raw in authority.programmes.items():
            d=write(journal,'programmes/'+mode+'.py',raw);self.programmes[mode]=journal.root/d['path'];self.commits[mode]=d
        self.reference_commit=write(journal,'programmes/REFERENCE.py',authority.sources['reference_entry.py'])
        self.source=Path(authority.root['source_root'])
        self.runner=QualifiedRunner(authority,journal,self.carrier)
        self.host=DockerHost(authority.root['native_profile'],self.runner,journal,self.budget,self.carrier)

    def view(self,attempt,phase,model_sha=None):
        p=self.prepared;p.live();c=attempt.cell
        name='views/'+attempt.role+'/'+attempt.key+'/'+phase;root=self.journal.root/name
        need(not root.exists(),'fresh full-cell/phase public view')
        if phase=='fit':
            x,y,people,concepts,roles=p.fit_data(c)
            xd=write(self.journal,name+'/features.npy',array_bytes(x));yd=write(self.journal,name+'/targets.npy',array_bytes(y))
            meta={'schema':'neural057-fit-view-v1','cell':c,'category_schema_sha256':p.category_sha,'categories':p.categories,'features':dict(xd,path='features.npy'),'targets':dict(yd,path='targets.npy'),'people':people,'concepts':concepts,'roles':roles,'groups':p.groups,'preparation_sha256':p.receipt['sha256']}
            md=json_write(self.journal,name+'/train.json',meta)
        else:
            need(attempt.fit_seal is not None and model_sha==attempt.fit_seal['model']['sha256'],'original same-cell FIT seal only')
            x=p.query_data(c);xd=write(self.journal,name+'/features.npy',array_bytes(x))
            meta={'schema':'neural057-query-view-v1','cell':c,'category_schema_sha256':p.category_sha,'categories':p.categories,'features':dict(xd,path='features.npy'),'query_ids':p.query_ids[c['person']],'fit_state_sha256':model_sha,'preparation_sha256':p.receipt['sha256']}
            md=json_write(self.journal,name+'/query.json',meta)
        profile=self.authority.root['native_profile'];json_write(self.journal,name+'/HOST.json',{'schema':'neural057-no-service-visible-profile-v1','memory_bytes':profile['memory_bytes'],'pids':profile['pids']})
        json_write(self.journal,name+'/CELL.json',c)
        captured={r['path']:r for r in self.journal.records if r['status']=='complete' and r['closed']}
        expected={}
        for f in root.iterdir():
            rel=f.relative_to(self.journal.root).as_posix();r=captured[rel]
            expected[f.name]={'path':rel,'bytes':r['observed_bytes'],'sha256':r['sha256']}
        # All actual content was just captured/read back above. This final census
        # is metadata-only; the second full identity read below is charged.
        for d in expected.values():read(self.journal.root,d,self.budget,d['bytes'])
        os.chmod(root,0o555);attempt.views.append((root,expected));return root,md

    def captured(self,phase,name,cap):
        need(phase in self.host.originals and phase.closed and phase.accounting_complete and phase.durable,'actual retired original phase before output')
        r=phase.outputs[name];need(r['usable'] is True,'complete successful original output')
        p=Path(r['path']);need(p.is_relative_to(self.journal.root),'original owned capture path');os.chmod(p,0o444)
        d={'path':p.relative_to(self.journal.root).as_posix(),'bytes':r['bytes'],'sha256':r['sha256']}
        return read(self.journal.root,d,self.budget,cap),d

    def run_cell(self,c,role):
        need(role in ('participant','reference'),'fixed scientific owner role');a=CellAttempt(self,c,role)
        began=False
        try:
            self.budget.begin_cell(dict(c,role=role),self.authority.root['cell_limits'],self.prepared.setup);began=True
            self.authority.validate_live();commit=self.commits[c['mode']] if role=='participant' else self.reference_commit
            programme=self.journal.root/commit['path'];original=self.authority.programmes[c['mode']] if role=='participant' else self.authority.sources['reference_entry.py']
            need(read(self.journal.root,commit,self.budget,131072)==original,'unchanged committed code before exposure')
            view,viewpin=self.view(a,'fit');a.status='fit_started'
            self.authority.validate_sources()
            fit=self.host.phase(c,'fit',programme,view,None,self.journal.root/('outputs/'+role+'/'+a.key+'/fit'),self.source,self.budget.action_deadline(self.authority.root['fit_seconds']),self.budget.clock(),role=role,custody=a.fit)
            a.status='fit_retired';model,modelpin=self.captured(fit,'model.bin',268435456)
            method,methodpin=self.captured(fit,'selected_method.json',8388608);decl,_=self.captured(fit,'operations.json',8388608)
            m=parse(method);fields(m,('schema','cell','category_schema_sha256','state_sha256','method_id','fit_view_sha256','selection'))
            need(m['schema']=='neural057-selected-method-v1' and m['cell']==c and m['state_sha256']==modelpin['sha256'] and m['category_schema_sha256']==self.prepared.category_sha and m['fit_view_sha256']==viewpin['sha256'],'original method-state-cell-view joins')
            need(type(m['method_id']) is str and 0<len(m['method_id'].encode())<=1024 and type(m['selection']) is dict,'bounded nonauthoritative selection declaration')
            if role=='reference':need(m['method_id']=='weighted-independent-logistic-v1','actual fixed reference identity')
            declaration=parse(decl);fields(declaration,('schema','phase','cell','services','query_access','native_cost_authority'))
            need(declaration['schema']=='neural057-participant-declaration-v1' and declaration['phase']=='FIT' and declaration['cell']==c and declaration['services']==[] and declaration['query_access'] is False and declaration['native_cost_authority'] is False,'closed declaration never grants authority')
            a.model=modelpin;a.fit_seal={'schema':'neural057-fit-seal-v1','cell':c,'role':role,'program':commit,'view':viewpin,'model':modelpin,'method':methodpin,'original_phase':fit.id,'phase_publication':fit.publication,'source_identity':sha(encoded(self.authority.root['source_members']))}
            json_write(self.journal,'seals/'+role+'/'+a.key+'.json',a.fit_seal);a.status='sealed'
            view,_=self.view(a,'infer',modelpin['sha256']);a.status='infer_started'
            self.authority.validate_sources()
            infer=self.host.phase(c,'infer',programme,view,self.journal.root/modelpin['path'],self.journal.root/('outputs/'+role+'/'+a.key+'/infer'),self.source,self.budget.action_deadline(self.authority.root['infer_seconds']),self.budget.clock(),role=role,custody=a.infer)
            a.status='infer_retired';raw,_=self.captured(infer,'prediction.json',4194304)
            op,_=self.captured(infer,'operations.json',8388608);decl=parse(op);fields(decl,('schema','phase','cell','services','query_transform_fitting','native_cost_authority'))
            need(decl['schema']=='neural057-participant-declaration-v1' and decl['phase']=='INFER' and decl['cell']==c and decl['services']==[] and decl['query_transform_fitting'] is False and decl['native_cost_authority'] is False,'closed original INFER declaration')
            a.prediction=prediction(parse(raw),self.prepared.query_ids[c['person']],c,modelpin['sha256'])
            need(a.prediction['category_schema_sha256']==self.prepared.category_sha,'fixed original category order')
            for root,expected in a.views:
                need({p.name for p in root.iterdir()}==set(expected),'unchanged whole original view namespace')
                for d in expected.values():read(self.journal.root,d,self.budget,d['bytes'])
            a.status='complete'
        except BaseException as exc:
            a.first=exc;a.errors.fail(exc,'original-cell');self.carrier.fail(exc,'original-cell:'+a.key);a.status='failed'
        finally:
            if began:
                try:self.budget.finish_cell()
                except BaseException as exc:
                    a.errors.fail(exc,'original-cell-budget-close');self.carrier.fail(exc,'original-cell-budget-close');a.status='failed'
                    if a.first is None:a.first=exc
            try:json_write(self.journal,'terminals/'+role+'/'+a.key+'.json',a.terminal())
            except BaseException as exc:
                a.errors.fail(exc,'original-cell-terminal');self.carrier.fail(exc,'original-cell-terminal');a.status='failed'
                if a.first is None:a.first=exc
        if a.first is not None:raise a.first
        return a

    def barrier(self):
        need(self.prepared is not None and self.prepared.complete,'original preparation complete')
        expected={(role,cell_key(c)) for role in ('reference','participant') for c in registry()}
        need(len(self.attempts)==160 and {(a.role,a.key) for a in self.attempts}==expected,'full exact160 owned cells; no partial denominator')
        need(all(a.campaign is self and a.status=='complete' and a.prediction is not None and a.fit.phase is not None and a.infer.phase is not None for a in self.attempts),'all actual complete producer occurrences')
        phases=[phase for a in self.attempts for phase in (a.fit.phase,a.infer.phase)]
        need(len({id(p) for p in phases})==320 and {id(p) for p in phases}=={id(p) for p in self.host.originals},'all original phase objects exactly once; no equal copies/unused original')
        for a in self.attempts:
            need(a.fit.phase.cell==a.infer.phase.cell==a.cell and a.fit.phase.kind=='fit' and a.infer.phase.kind=='infer','same cell and original phase roles')
            need(a.fit.phase.accounting['kind']==a.infer.phase.accounting['kind']==a.role and a.fit_seal['original_phase']==a.fit.phase.id,'independent reference/participant ownership')
            need(a.prediction['fit_state_sha256']==a.model['sha256']==a.fit_seal['model']['sha256'],'same actual fitted state into protected collection')
        need(all(p.closed and p.accounting_complete and p.durable for p in self.host.originals) and len(self.host.originals)==320,'all320 exact phases retired before protected scoring')
        self.authority.validate_sources();self.score_open=True

    def run(self):
        self.prepared=Prepared(self.authority,self.journal)
        # Parent directories are source-owned before native capture effects.
        for role in ('reference','participant'):
            for c in registry():
                (self.journal.root/'outputs'/role/cell_key(c)).mkdir(parents=True,exist_ok=False,mode=0o700)
                self.run_cell(c,role)
        self.barrier()
        from .scoring import score_cell,paired_summary,native_summary,independent_comparisons
        results={}
        for role in ('reference','participant'):
            rows=[]
            for a in self.attempts:
                if a.role!=role:continue
                rows.append(score_cell(a.prediction,self.prepared.query_ids[a.cell['person']],a.cell,a.model['sha256'],self.prepared.category_sha,self.prepared.private[a.cell['person']]))
            results[role]={'cells':rows,'primary_native_loss':native_summary(rows),'paired_gain':paired_summary(rows)}
        comparison=independent_comparisons(results['reference']['cells'],results['participant']['cells'])
        report={'schema':'neural057-complete-report-v1','status':'numerical_complete_pending_independent_semantic_qualification','results':results,'independent_comparisons':comparison,'source':sha(encoded(self.authority.root['source_members'])),'preparation':self.prepared.receipt,'costs':self.budget.snapshot(),'limitations':['public corpus and taxonomy','released all-session MVNN','200ms sequence overlap','late prospective window is not causal isolation','native total logical I/O and file churn unobserved'],'native_loss':'mean Bernoulli log loss in nats/category; equal concept then person','no_benchmark_count_claim':True}
        return json_write(self.journal,'REPORT.json',report)
