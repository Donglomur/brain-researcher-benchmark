"""Concrete provider/analysis loops with fresh contexts and fixed F continuation."""
from pathlib import Path
from core import need,encoded,publish,pin,finite
from provider import Provider
from worker_common import recipe
from authority import method as admit_method

class Investigator:
    def __init__(self,a,budget,record,transport,quota,protocol):self.a=a;self.b=budget;self.record=record;self.t=transport;self.quota=quota;self.protocol=protocol
    def provider(self,profile):return Provider(self.a['provider'],self.b,self.record,self.a['phase_limits'][profile],self.quota)
    def save(self,identity,response,mode,tool,cutoff,*,admission=True):
        a=self.a;r=a['resources'];folder=Path(a['roots']['output'])/'methods';name=pin(identity.encode())['sha256']
        raw=response['source'].encode();need(0<len(raw)<=r['candidate_source_bytes'],'bounded actual authored source')
        rec=recipe(response['recipe']);rb=encoded(rec);cb=encoded(response['claim'])
        need(len(rb)<=r['candidate_recipe_bytes']and len(cb)<=32768,'bounded recipe/claim')
        source={'path':str(folder/(name+'.py')),'pin':publish(folder/(name+'.py'),raw,self.b,readonly=True)}
        recipe_row={'path':str(folder/(name+'.recipe.json')),'pin':publish(folder/(name+'.recipe.json'),rb,self.b,readonly=True)}
        claim={'path':str(folder/(name+'.claim.json')),'pin':publish(folder/(name+'.claim.json'),cb,self.b,readonly=True)}
        review=admit_method(a,identity,source['pin'],recipe_row['pin'],claim['pin'],mode,self.b,cutoff)if admission else None
        return {'identity':identity,'mode':mode,'tool':tool,'source':source,'recipe':recipe_row,'recipe_value':rec,'claim':claim,'admission':review}
    def loop(self,identity,mode,tool,profile,cutoff,case=None,policy=None):
        provider=self.provider(profile);messages=[{'role':'system','content':self.protocol+'\nReturn JSON action python(code,rationale), submit(source,recipe,claim), or stop(reason). Source is authored Python; I policy source is plain instruction text. No other case or reference is available.'}]
        if policy:messages.append({'role':'system','content':policy})
        messages.append({'role':'user','content':encoded({'identity':identity,'mode':mode,'tool':tool,'case':None if case is None else {'person':case['person'],'world':case['world'],'sessions':case['view']['sessions'],'channels':len(case['view']['channels'])}}).decode()})
        analyses=[]
        for step in range(self.a['phase_limits'][profile]['steps']):
            self.b.tick(cutoff);value,text,raw=provider.complete(messages,[identity],cutoff);messages.append({'role':'assistant','content':text})
            if value['action']=='stop':raise ValueError('actor explicitly stopped without complete output')
            if value['action']=='submit':
                method=self.save(identity,value,mode,tool,cutoff)
                self.record({'kind':'episode_completed','identity':identity,'method':method,'analysis_operations':[x['operation']for x in analyses],'provider':{'calls':provider.calls,'tokens':provider.tokens,'money_reserved':provider.money_reserved}})
                return method,analyses,provider
            analysis=self.save(identity+'/analysis/'+str(step),{'source':value['code'],'recipe':{'provider_slots':{}},'claim':{}},mode,tool,cutoff,admission=False)
            row=self.t.invoke(identity+'/analysis/'+str(step),'analysis',profile,cutoff,case=case,method=analysis,tool=tool);analyses.append(row)
            feedback=self.t.json(row,'FEEDBACK.json');messages.append({'role':'user','content':encoded(feedback).decode()})
        raise ValueError('complete source was not submitted within fixed provider budget')
    def solve(self,identity,method,case,profile,cutoff,provider=None):
        provider=provider or self.provider(profile);values={};ops=[]
        if method['recipe_value']['provider_slots']:
            row=self.t.invoke(identity+'/features','candidate_features',profile,cutoff,case=case,method=method,tool=method['tool']);ops.append(row)
            from fixed_provider import execute
            values,_=execute(provider,method['recipe_value'],self.t.json(row,'FEATURES.json'),identity,cutoff)
        row=self.t.invoke(identity+'/solve','candidate',profile,cutoff,case=case,method=method,tool=method['tool'],provider_values=values);ops.append(row)
        return row,ops
