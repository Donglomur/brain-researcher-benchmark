"""Full fixed/adaptive/reference composition with retained raw owner.

Uses actual Engine->Transport->worker calls. No scientific callback is accepted
as native authority. Entry must supply the independently admitted deployment;
source dictionaries or matching pins alone do not qualify that deployment.
"""
from pathlib import Path
from core import need,parse,encoded,capture,publish,pin
from schema import MODES,ARMS,REFERENCES,validate_view,validate_prediction
from custody import Attempt,Barrier
from engine import Engine
from transport import Transport

def schedule(views):
    cells=[]
    for v in views:
        for mode in MODES:
            for arm in ARMS:
                cells.append({'identity':v['held']+'/'+mode+'/'+arm,'held':v['held'],'family':mode+'/'+arm,'mode':mode,'arm':arm,'tool':'numeric' if arm=='numeric' else 'decoder','reference':None,'epoch_root':v['epoch_root']})
        for method in REFERENCES:
            cells.append({'identity':v['held']+'/reference/'+method,'held':v['held'],'family':'reference/'+method,'mode':'frozen_program','arm':'decoder_only','tool':'decoder','reference':method,'epoch_root':v['epoch_root']})
    return cells

class Campaign:
    def __init__(self,selection,source,budget,views,private_descriptor):
        self.selection=selection;self.source=source;self.budget=budget;self.views=views;self.private_descriptor=private_descriptor
        self.attempt=Attempt(selection['study']);self.events=[];self.engine=None;self.transport=None;self.barrier=None
    def record(self,row):
        self.events.append(row)
        # Actual bounded append-only ordinary accounting log lives outside all
        # actor mounts. A publication failure remains inside Campaign ownership.
        need(len(self.events)<=self.selection['max_events'],'finite campaign events')
        path=Path(self.selection['journal_root'])/(str(len(self.events))+'.json')
        publish(path,encoded(row),self.budget,readonly=True)
    def run(self):
        a=self.attempt;s=self.selection;result=None
        try:
            self.engine=Engine(s['engine'],self.budget,self.record);a.owned.append(self.engine)
            self.transport=Transport(s,self.source,self.budget,self.engine);a.owned.append(self.transport)
            cells=schedule(self.views);self.barrier=Barrier(tuple(c['identity'] for c in cells),self.transport);a.owned.append(self.barrier)
            views={v['held']:v for v in self.views};predictions={};reasoning=[]
            for cell in cells:
                record=views[cell['held']];raw,_=capture(record['path'],record['pin'],s['worker_limits']['metadata_bytes'],self.budget,readonly=True);view=validate_view(parse(raw))
                method=s['fixed_decoder'] if cell['arm']=='decoder_only' else s['methods'][cell['mode']+'/'+cell['arm']]
                recipe={'method':cell['reference'] or 'combined'} if cell['arm']=='decoder_only' else method['recipe']
                self.engine.begin_scope(cell['identity'],min(self.budget.deadline,self.budget.tick()+s['episode_seconds']),s['episode_limits'])
                operation_count=2
                if cell['mode']=='case_adaptive_equal_inputs_tools_compute' and cell['arm']!='decoder_only':
                    investigation=self.transport.run(cell,'investigate',view,method,recipe)
                    # The actual case-authored method is frozen and hashed before
                    # model fitting, and remains identical at prediction time.
                    method=investigation['artifacts']['METHOD.py'];r=investigation['artifacts']['RECIPE.json']
                    raw,_=capture(r['path'],r['pin'],s['worker_limits']['metadata_bytes'],self.budget,readonly=True);recipe=parse(raw)
                    operation_count+=1
                trained=self.transport.run(cell,'fit',view,method,recipe)
                rd=trained['artifacts']['REASONING.json'];raw,_=capture(rd['path'],rd['pin'],s['worker_limits']['metadata_bytes'],self.budget,readonly=True);declared=parse(raw)
                from reasoning import check as check_reasoning
                checked=check_reasoning(declared['declaration'],method['pin'],trained['artifacts']['MODEL.bin']['pin'])
                need(checked==declared,'independent source/model/interpretation lineage join')
                predicted=self.transport.run(cell,'predict',view,method,recipe,trained['artifacts']['MODEL.bin'])
                self.engine.end_scope(cell['identity'])
                d=predicted['artifacts']['PREDICTIONS.json'];raw,_=capture(d['path'],d['pin'],s['worker_limits']['metadata_bytes'],self.budget,readonly=True);value=parse(raw)
                validate_prediction(value,[r['id'] for r in view['query']])
                self.barrier.accept(cell['identity'],predicted,d);predictions.setdefault(cell['family'],[]).append(value)
                reasoning.append({'cell':cell['identity'],'reasoning':checked,'prediction':d,'training_receipt':trained['artifacts']['TRAINING.json']})
                a.known_cost_prefix.append({'cell':cell['identity'],'native_operations':operation_count,'observed_cpu_ns':self.engine.used_cpu,'reserved_cpu_ns':self.engine.reserved_cpu})
            self.barrier.seal();self.barrier.target_access()
            # Only after *all* candidates and references are immutable and closed
            # does this evaluator re-open protected targets for scoring.
            p=self.private_descriptor;raw,_=capture(p['path'],p['pin'],s['private_metadata_bytes'],self.budget,readonly=True);private=parse(raw)
            from score import run as score
            from score_check import check
            scored=score(self.barrier,predictions,private);checks={}
            for family,values in predictions.items():checks[family]=check([r for v in values for r in v['probabilities']],private['rows'],scored[family])
            from uncertainty import paired
            intervals=paired(scored,s['uncertainty_seed'])
            result={'schema':'n041_complete_report_v1','task':'NEURAL-041','scores':scored,'checks':checks,
                'source':pin(encoded(self.source)),'protocol':s['protocol'],'complete_cells':len(cells),
                'scope':'offline held-patient memory-load prediction; no claim of causal memory mechanism',
                'preparation_costs':s['preparation_receipt'],'cost_prefix':a.known_cost_prefix,
                'paired_patient_uncertainty':intervals,'reasoning_evidence':reasoning,
                'unknown_physical_hdf5_daemon_io':True,'qualification':s['qualification_evidence']}
            self.record({'kind':'all_scored','cells':len(cells)})
            publish(Path(s['report_root'])/'REPORT.json',encoded(result),self.budget,readonly=True)
            a.known_cost_prefix.append(self.budget.record());a.status='complete'
            publish(Path(s['report_root'])/'COMPLETE.json',encoded(a.summary()),self.budget,readonly=True)
            self.budget.tick()
        except BaseException as error:
            a.failed('campaign',error)
            if self.barrier is not None:self.barrier.fail()
        if a.raw_first is not None:
            if self.engine is not None:a.cleanup('abort_scope',lambda:self.engine.abort_scope)
            a.cleanup('final_logical_cost',lambda:lambda:a.known_cost_prefix.append(self.budget.record()))
            a.cleanup('failure_publication',lambda:lambda:publish(Path(s['report_root'])/'FAILED.json',encoded(a.summary()),self.budget,readonly=True))
            a.raise_first()
        return result
