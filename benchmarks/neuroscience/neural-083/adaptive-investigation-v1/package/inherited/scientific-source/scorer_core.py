"""Strict completepanel probability scorer; no decoder/model execution."""
import math,re,statistics,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
import protocol as p
TOKEN=re.compile(r'(case|person|trial)_[a-f0-9]{24}\Z')
def panel(v):
 p.exact(v,['schema','generation','settings','arms','cases']);p.need(v['schema']=='neural083_panel_v1' and type(v['generation'])is str and re.fullmatch('[a-f0-9]{64}',v['generation']) and v['settings']==list(p.SETTINGS) and v['arms']==list(p.ARMS),'Panelidentity')
 p.need(type(v['cases'])is list and len(v['cases'])==108,'All54×2cases');cases=set();people={};trials=set()
 for r in v['cases']:
  p.exact(r,['case','person','session','query']);p.need(type(r['case'])is str and r['case'].startswith('case_') and TOKEN.fullmatch(r['case']) and r['case'] not in cases,'DistinctcaseID');cases.add(r['case'])
  p.need(type(r['person'])is str and r['person'].startswith('person_') and TOKEN.fullmatch(r['person']) and type(r['session'])is int and r['session'] in (1,2),'Personsession')
  ss=people.setdefault(r['person'],set());p.need(r['session'] not in ss,'Onecasepersession');ss.add(r['session'])
  p.need(type(r['query'])is list and len(r['query'])==100 and r['query']==sorted(r['query']),'100opaqueorderedqueries')
  for t in r['query']:p.need(type(t)is str and t.startswith('trial_') and TOKEN.fullmatch(t) and t not in trials,'Distincttrial');trials.add(t)
 p.need(len(people)==54 and all(ss=={1,2} for ss in people.values()),'Completebiologicalpanel')
 return {r['case']:r for r in v['cases']}

def admit(v,s):
 cases=panel(v);p.exact(s,['schema','generation','outcomes']);p.need(s['schema']=='neural083_predictions_v1' and s['generation']==v['generation'] and type(s['outcomes'])is list and len(s['outcomes'])==1296,'All108×4×3conditions')
 out={};abstain=[]
 for r in s['outcomes']:
  p.need(type(r)is dict and r.get('status') in ('complete','abstain'),'Explicitstatus')
  p.exact(r,['schema','generation','case','setting','arm','status','predictions' if r['status']=='complete' else 'reason'])
  p.need(r['schema']=='neural083_case_prediction_v1' and r['generation']==v['generation'] and type(r['case'])is str and r['case'] in cases and r['setting'] in p.SETTINGS and r['arm'] in p.ARMS,'Exactcondition')
  key=(r['case'],r['setting'],r['arm']);p.need(key not in out,'Uniquecondition')
  if r['status']=='abstain':p.need(type(r['reason'])is str and 0<len(r['reason'])<=256,'Boundedreason');out[key]=None;abstain.append(key);continue
  pred=r['predictions'];p.need(type(pred)is list and len(pred)==100,'Everyquery')
  values=[]
  for t,row in zip(cases[r['case']]['query'],pred):
   p.exact(row,['trial','p_right']);z=row['p_right'];p.need(row['trial']==t and type(z)in (int,float) and 0<=z<=1 and math.isfinite(z),'Orderedfiniteprobabilities');values.append(z)
  out[key]=values
 p.need(len(out)==1296,'Completeconditioncollection');return out,abstain

def score(v,s,load_targets):
 pred,abstain=admit(v,s)
 if abstain:return {'status':'abstained','primary_score':None,'private_callbacks':0,'abstaining_conditions':len(abstain)}
 truth=load_targets();p.exact(truth,['schema','generation','cases']);p.need(truth['schema']=='neural083_targets_v1' and truth['generation']==v['generation'] and len(truth['cases'])==108,'Privategeneration/allcases')
 targets={}
 for r in truth['cases']:
  p.exact(r,['case','labels']);y=r['labels'];p.need(r['case'] not in targets and type(y)is list and len(y)==100 and all(type(z)is int and z in (0,1) for z in y) and y.count(0)==y.count(1)==50,'Exactbalancedprivatetargets');targets[r['case']]=y
 cases=panel(v);p.need(set(targets)==set(cases),'Exactprivatejoin');per={}
 for case,r in cases.items():
  y=targets[case]
  for setting in p.SETTINGS:
   for arm in p.ARMS:
    z=pred[case,setting,arm];ba=sum(sum((value>=.5)==bool(cls) for value,yy in zip(z,y) if yy==cls)/50 for cls in (0,1))/2
    loss=math.fsum(-math.log(max(1e-15,value if yy else 1-value)) for value,yy in zip(z,y))/100
    per[case,setting,arm]={'balanced_accuracy':ba,'log_loss':loss}
 people=sorted({r['person'] for r in cases.values()});summary={};person_values={}
 for setting in p.SETTINGS:
  for arm in p.ARMS:
   key=setting+'/'+arm;values=[]
   for person in people:
    own=[r['case'] for r in cases.values() if r['person']==person]
    values.append({'person':person,**{metric:sum(per[c,setting,arm][metric] for c in own)/2 for metric in ('balanced_accuracy','log_loss')}})
   person_values[key]=values;summary[key]={metric:math.fsum(r[metric] for r in values)/54 for metric in ('balanced_accuracy','log_loss')}
 contrasts={}
 for name,active,control in [('eeg_minus_context','target20/EEG','target20/CONTEXT'),('eeg_minus_permuted','target20/EEG','target20/PERMUTED_EEG'),('calibration20_minus_zero','target20/EEG','transfer0/EEG'),('calibration100_minus20','target100/EEG','target20/EEG'),('same_minus_other_session20','target20/EEG','other_session20/EEG')]:
  d=[a['balanced_accuracy']-b['balanced_accuracy'] for a,b in zip(person_values[active],person_values[control])];contrasts[name]={'per_person':d,'mean':math.fsum(d)/54,'descriptive_se':statistics.stdev(d)/math.sqrt(54)}
 return {'status':'scored','primary_score':summary['target20/EEG']['balanced_accuracy'],'primary':'target20/EEG/person_macro_session_macro_balanced_accuracy','direction':'higher','macro':summary,'per_person':person_values,'paired_balanced_accuracy_differences':contrasts,'private_callbacks':1,'biological_n':54,'scientific_success':None,'cue_independent_intention_established':False,'runtime_verified':False,'uncertainty':'SD/sqrt54 descriptive; shared donortraining/calibration dependence not a calibrated population CI.'}
