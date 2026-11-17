"""Concrete typed provider investigation, native analysis and sealed final methods."""
from pathlib import Path
import hashlib
from core import need, encoded, pin, publish, finite
from schedule import author_contexts
from runtime import Runtime


SYSTEM = '''You are implementing a NEURAL-058 cross-animal neural decoding method.
Return exactly one JSON action: python {action,code,rationale}, submit
{action,source,recipe,claim}, or stop {action,reason}. Analysis code defines
analyze(context). Submitted source defines fit(context) and
infer(context,state,provider_values). Optional numeric_features(context,state)
returns finite feature lists for the sealed recipe's numeric_slots. Each slot
has a frozen prompt string; later replies are finite numeric values only.
All source-animal labels are legal; no evaluation-animal wheel value is legal.
F authors see source data only and must seal a general method before evaluation.
I authors may investigate all unlabeled sessions of their one assigned animal.
C has only allowed context/anatomy; J adds the full neural events. T1 exposes
source-selected role-matched tools through context['tools'].predict(window).
T0 has no task-trained states. Native analyses can use the complete mounted
views and libraries. Return safe primitive arrays/dicts/lists as fitted state.
infer returns a dict from every current-session query ID to an N-by-2 numeric
matrix in original timestamp order: signed velocity then absolute speed.
Retired training mounts do not prohibit retaining training examples in state.
No generated code/DSL or method rewriting is permitted during sealed inference.
An independent semantic/exposure review is required before protected grading.
'''


def recipe(value):
    need(type(value)is dict and set(value)=={'numeric_slots'},'exact frozen numeric recipe')
    slots=value['numeric_slots'];need(type(slots)is list and len(slots)<=16,'bounded explicit numerical provider calls')
    for row in slots:
        need(type(row)is dict and set(row)=={'prompt'} and type(row['prompt'])is str
             and len(row['prompt'].encode())<=16384,'frozen numeric prompt, no query-supplied instructions')
    return value


class Authors:
    def __init__(self,runtime,views,references,selection,budget,emit):
        self.runtime=runtime;self.views=views;self.references=references;self.selection=selection;self.budget=budget;self.emit=emit
        self.methods={};self.fits={};self.outputs={};self.transcripts={}

    def base(self,panel,animal,stage,program,recipe_value):
        source=sorted(self.views.roster['source']) if stage in ('analysis','fit') else []
        evaluation=[] if panel['mode']=='F' and stage in ('analysis','fit') else self.views.animal_sessions(animal)
        tools,tool_mounts=self.references.tools(panel['role'],panel['tool'])
        req={'schema':'neural058_candidate_request_v1','task':'NEURAL-058','stage':stage,'panel':panel['id'],
             'mode':panel['mode'],'role':panel['role'],'tool':panel['tool'],'animal':animal,
             'training':self.views.input_rows(panel['role'],source),'evaluation':self.views.input_rows(panel['role'],evaluation),
             'evaluation_animals':self.views.roster['eval_animals'],'animal_sessions':evaluation,
             'input_root':'/inputs/corpus','output_root':'/scratch/result','program':{'path':'/inputs/method.py','pin':program['pin']},
             'tools':tools,'recipe':recipe_value,'limits':self.selection['data_limits'],'device':self.selection['candidate_device']}
        mounts=self.views.mounts(panel['role'],source+evaluation)+tool_mounts
        mounts.append({'source':program['path'],'destination':'/inputs/method.py','pin':program['pin'],
                       'bytes_cap':self.selection['data_limits']['source_bytes']})
        return req,mounts

    def write_program(self,name,text,budget):
        raw=text.encode();need(0<len(raw)<=self.selection['data_limits']['source_bytes'],'bounded sealed source')
        path=self.runtime.requests/(hashlib.sha256(name.encode()).hexdigest()+'.py')
        d=publish(path,raw,budget,readonly=True)
        return {'path':str(path),'pin':d}

    def construct(self,panel,animal,panel_budget,cutoff):
        identity=panel['id']+'/author/'+animal;need(identity not in self.methods,'fresh author context')
        description={'task':'NEURAL-058','panel':panel,'animal':animal,
                     'source_sessions':423,'source_animals':126,'evaluation_sessions':[] if animal=='global' else self.views.animal_sessions(animal),
                     'targets':'signed velocity primary; absolute-speed secondary, no evaluation labels',
                     'resource_scope':'remaining shared whole-panel ceilings, never a fresh allowance per animal'}
        messages=[{'role':'system','content':SYSTEM},{'role':'user','content':encoded(description).decode()}]
        self.transcripts[identity]=messages
        ordinal=0
        while True:
            panel_budget.tick(cutoff);ordinal+=1
            action,text,_=panel_budget.provider.complete(messages,(panel['id'],animal),cutoff,'author')
            messages.append({'role':'assistant','content':text})
            if action['action']=='stop': raise ValueError('author explicitly failed: '+action['reason'][:512])
            if action['action']=='submit':
                selected_recipe=recipe(action['recipe'])
                method=self.write_program(identity+'/sealed',action['source'],panel_budget)
                record={'program':method,'recipe':selected_recipe,'claim':action['claim'],'panel':panel,
                        'animal':animal,'sealed_at':panel_budget.tick(cutoff),
                        'transcript':pin(encoded(messages)),'semantic_qualification_pending':True}
                self.methods[identity]=record
                self.emit({'kind':'method_sealed','task':'NEURAL-058','identity':identity,**record})
                break
            program=self.write_program(identity+'/analysis/'+str(ordinal),action['code'],panel_budget)
            request,mounts=self.base(panel,animal,'analysis',program,{'numeric_slots':[]})
            profile=self.selection['native_profiles']['candidate_analysis']
            end=min(cutoff,panel_budget.tick()+finite(profile['wall_seconds']))
            product=self.runtime.run(identity+'/analysis/'+str(ordinal),'candidate',request,mounts,end,profile,panel_budget)
            result=product['result'];need(result['stage']=='analysis','actual returned analysis')
            messages.append({'role':'user','content':encoded({'analysis':result['analysis'],'stdout':result['stdout']}).decode()})
        request,mounts=self.base(panel,animal,'fit',method,selected_recipe)
        profile=self.selection['native_profiles']['candidate_fit'];end=min(cutoff,panel_budget.tick()+finite(profile['wall_seconds']))
        product=self.runtime.run(identity+'/fit','candidate',request,mounts,end,profile,panel_budget)
        need(product['result']['stage']=='fit','actual submitted fit completion')
        self.fits[identity]=product
        return record,product

    def state_mounts(self,fit):
        state=fit['result']['state'];members={r['path']:r['pin'] for r in fit['derived']['members']};rows=[]
        for d in [state['metadata']]+state['arrays']:
            need(members.get(d['path'])==d['pin'],'candidate state belongs to exact closed own-context fit')
            rows.append({'source':str(Path(fit['root'])/d['path']),'destination':'/inputs/state/'+d['path'],
                         'pin':d['pin'],'bytes_cap':d['pin']['bytes']})
        return rows

    def infer_session(self,panel,animal,session,panel_budget,cutoff):
        identity=panel['id']+'/author/'+('global' if panel['mode']=='F' else animal)
        method=self.methods[identity];fit=self.fits[identity]
        request,mounts=self.base(panel,animal,'infer',method['program'],method['recipe'])
        request.update(current_session=session,state_root='/inputs/state',state=fit['result']['state'],provider_values=[])
        mounts+=self.state_mounts(fit);operation=panel['id']+'/predict/'+session
        if method['recipe']['numeric_slots']:
            features_request=dict(request);features_request['stage']='numeric_features'
            profile=self.selection['native_profiles']['candidate_features'];end=min(cutoff,panel_budget.tick()+finite(profile['wall_seconds']))
            product=self.runtime.run(operation+'/features','candidate',features_request,mounts,end,profile,panel_budget)
            features=product['result']['features'];need(len(features)==len(method['recipe']['numeric_slots']),'fixed numerical feature slots')
            values=[]
            for slot,numbers in zip(method['recipe']['numeric_slots'],features,strict=True):
                messages=[{'role':'system','content':'Return exactly JSON {"values": [finite numbers]}. '+slot['prompt']},
                          {'role':'user','content':encoded(numbers).decode()}]
                action,_,_=panel_budget.provider.complete(messages,(panel['id'],animal),cutoff,'fixed_numeric')
                values.append(action['values'])
            request['provider_values']=values
        profile=self.selection['native_profiles']['candidate_infer'];end=min(cutoff,panel_budget.tick()+finite(profile['wall_seconds']))
        product=self.runtime.run(operation,'candidate',request,mounts,end,profile,panel_budget)
        result=product['result'];need(result['stage']=='infer' and result['session']==session
                                    and result['animal']==animal and result['state']==fit['result']['state'],
                                    'exact own-context full session prediction')
        self.outputs[(panel['id'],session)]=product
        return product
