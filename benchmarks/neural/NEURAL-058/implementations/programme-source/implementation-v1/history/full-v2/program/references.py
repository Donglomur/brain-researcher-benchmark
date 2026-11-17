"""Concrete full160-fold reference campaign, source selection and all final models."""
from pathlib import Path
from core import need,finite
from ordering import sessions,subset_animals
from schedule import reference_selection,final_models,final_reference_sessions
from reference_selection import choose


def state_mounts(product,destination='/inputs/model'):
    model=product['result']['model'];members={r['path']:r['pin'] for r in product['derived']['members']}
    rows=[model['metadata']]+model['arrays'];out=[]
    for row in rows:
        need(members.get(row['path'])==row['pin'],'every state member belongs to independently closed producer bundle')
        out.append({'source':str(Path(product['root'])/row['path']),'destination':destination+'/'+row['path'],
                    'pin':row['pin'],'bytes_cap':row['pin']['bytes']})
    return out


class References:
    def __init__(self,runtime,views,selection,budget,emit):
        self.runtime=runtime;self.views=views;self.selection=selection;self.budget=budget;self.emit=emit
        self.cv={};self.models={};self.predictions={};self.selected=None

    def profile(self,config):
        return self.selection['native_profiles']['reference_'+config['family']]

    def cutoff(self,profile):
        return min(self.budget.deadline,self.budget.tick()+finite(profile['wall_seconds']))

    def base(self,spec):
        return {'schema':'neural058_reference_request_v1','task':'NEURAL-058','role':spec['role'],
                'fold':spec['fold'],'config':spec['config'],'input_root':'/inputs/corpus',
                'output_root':'/scratch/result','limits':self.selection['data_limits'],
                'device':self.selection['reference_device']}

    def build(self):
        roster=self.views.roster
        for spec in reference_selection(roster):
            train=spec['training_sessions'];val=spec['validation_sessions']
            request=self.base(spec)|{'operation':'fit','training':self.views.input_rows(spec['role'],train),
                     'validation':self.views.input_rows(spec['role'],val),
                     'training_animals':subset_animals(roster,train),
                     'forbidden_animals':roster['eval_animals']+subset_animals(roster,val)}
            profile=self.profile(spec['config'])
            product=self.runtime.run(spec['id'],'reference',request,self.views.mounts(spec['role'],train+val),
                                     self.cutoff(profile),profile)
            result=product['result']
            need(result['training_sessions']==train and result['training_animals']==request['training_animals'],
                 'actual complete fit lineage')
            expected_animals={roster['source'][s]['animal'] for s in val}
            need(set(result['animals'])==expected_animals,'complete actual held-fold animal scores')
            need([r['session'] for r in result['predictions']]==val,'all OOF prediction sessions')
            self.cv[(spec['role'],spec['config']['id'],spec['fold'])]=product
        self.selected=choose({k:p['result'] for k,p in self.cv.items()},roster['source_animals'])
        self.emit({'kind':'source_reference_selection','task':'NEURAL-058','selection':self.selected,
                   'actual_cv_producers':[p['operation'] for p in self.cv.values()]})
        for spec in final_models(self.selected['choices']):
            train=sessions(roster,'source');request=self.base(spec)|{'operation':'fit',
                'training':self.views.input_rows(spec['role'],train),'validation':[],
                'training_animals':roster['source_animals'],'forbidden_animals':roster['eval_animals']}
            profile=self.profile(spec['config'])
            product=self.runtime.run(spec['id'],'reference',request,self.views.mounts(spec['role'],train),self.cutoff(profile),profile)
            need(product['result']['training_sessions']==train and product['result']['training_animals']==roster['source_animals'],
                 'complete423-session126-animal full refit')
            self.models[(spec['role'],spec['config']['id'])]=product
        for spec in final_reference_sessions(roster,self.selected['choices']):
            role=spec['role'];config_id=spec['model'].split('/')[-1];model=self.models[(role,config_id)]
            request={'schema':'neural058_reference_request_v1','task':'NEURAL-058','role':role,'operation':'predict',
                     'fold':'full','config':model['result']['config'],'model_root':'/inputs/model',
                     'model':model['result']['model'],'evaluation':self.views.input_rows(role,[spec['session']]),
                     'input_root':'/inputs/corpus','output_root':'/scratch/result','limits':self.selection['data_limits'],
                     'device':self.selection['reference_device']}
            mounts=self.views.mounts(role,[spec['session']])+state_mounts(model)
            profile=self.profile(request['config'])
            product=self.runtime.run(spec['id'],'reference',request,mounts,self.cutoff(profile),profile)
            need(len(product['result']['predictions'])==1 and product['result']['predictions'][0]['session']==spec['session'],
                 'exact independent reference session output')
            self.predictions[(role,config_id,spec['session'])]=product
        return self.selected

    def tools(self,role,tool):
        if tool=='T0':return {},[]
        need(tool=='T1' and self.selected is not None,'source-selected trained-tool treatment')
        rows={};mounts=[];used=set()
        for head in ('velocity','speed'):
            item=self.selected['strongest'][role+'/'+head];config=item['config'];model=self.models[(role,config)]
            destination='/inputs/tools/'+config
            rows[head]={'root':destination,'model':model['result']['model'],'selected_config':config,
                        'selection':item,'producer':model['operation']}
            if config not in used:mounts.extend(state_mounts(model,destination));used.add(config)
        return rows,mounts
