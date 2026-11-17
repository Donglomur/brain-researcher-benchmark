"""Capsule-local scientific API. Actual hardware allowance encloses every call."""
from core import need,integer
from epoch_io import load_epoch

class TrainingAPI:
    def __init__(self,view,budget,limits,tool,mode):
        need(not view['query'],'training capsule must never have held-patient query rows')
        self.rows=tuple(view['training']);self.regions=tuple(view['regions']);self.budget=budget
        self.limits=limits;self.tool=tool;self.mode=mode;self.events=[];self.calls=0
    def epoch(self,row):
        need(row in self.rows,'training-only epoch identity')
        return load_epoch('/inputs/epochs',row,self.budget,self.limits['epoch_bytes'],self.regions)
    def fit_reference(self,method):
        need(self.tool=='decoder','decoder API absent in generic numeric arm')
        self.calls+=1;need(self.calls<=self.limits['analysis_calls'],'finite training-only tool calls')
        from reference import features,fit_state
        data=[dict(r,features=features(None if method=='prior' else self.epoch(r),self.regions,method)) for r in self.rows]
        state,report=fit_state(data,method)
        self.events.append({'call':self.calls,'method':method,'report':report,'scope':'training_patients_only'})
        return state

class PredictionAPI:
    def __init__(self,view,budget,limits,tool):
        need(not view['training'],'prediction capsule has no training labels or original trial metadata')
        self.rows=tuple(view['query']);self.regions=tuple(view['regions']);self.budget=budget;self.limits=limits;self.tool=tool
    def epoch(self,row):
        need(row in self.rows,'query-only epoch identity')
        return load_epoch('/inputs/epochs',row,self.budget,self.limits['epoch_bytes'],self.regions)
    def predict_reference(self,state):
        need(self.tool=='decoder','decoder API absent in generic numeric arm')
        from reference import features,predict_state
        data=[dict(r,features=features(None if state['method']=='prior' else self.epoch(r),self.regions,state['method'])) for r in self.rows]
        p=predict_state(state,data)
        return {'schema':'n041_predictions_v1','probabilities':[{'id':r['id'],'p_high':float(v)} for r,v in zip(self.rows,p)]}
