"""Concrete role-matched strongest model API inside the assigned native view."""
from core import need
from state_io import load
from reference_models import predict


class Tools:
    def __init__(self,request,budget):
        self.request=request;self.budget=budget;self.states={}
        need(request['tool'] in ('T0','T1'),'explicit tool treatment')
        if request['tool']=='T0': need(request.get('tools')=={},'T0 cannot receive trained task states')
        else:
            need(set(request['tools'])=={'velocity','speed'},'both source-selected trained heads')
            for head,row in request['tools'].items():
                state=load(row['root'],row['model']['metadata'],budget,request['limits'])
                need(state['role']==request['role'] and state['fold']=='full'
                     and state['config']['id']==row['selected_config'],'exact own-role full-source selected tool')
                need(not set(state['training_animals'])&set(request['evaluation_animals']),'no evaluation-animal model lineage')
                self.states[head]=state

    def predict(self,window):
        import numpy as np
        need(self.request['tool']=='T1','no task-trained prediction in T0')
        self.budget.tick();heads=[]
        for i,head in enumerate(('velocity','speed')):
            value=predict(self.states[head],window,self.budget,self.request['device']);heads.append(value[:,i])
        return np.column_stack(heads)


def accessible_state_summary(tools):
    return {'tool':tools.request['tool'],'role':tools.request['role'],
            'heads':{k:{'family':v['config']['family'],'configuration':v['config']['id']}
                     for k,v in tools.states.items()}}
