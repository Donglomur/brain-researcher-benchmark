"""Fixed full-study compiler. Metadata is a definition, never data qualification."""
from .domain import Refusal,MissingDefinition,canonical,relative,OBLIGATIONS,CONDITIONS
COHORTS=('brainwide433','comparison10','backbone30','ibl_unaligned','allen_visual_running','allen_lick7','primate_rtt','scaling','prospective40')
MODELS=('linear','single_rrr','mlp','multi_rrr','multi_region_rrr','multi_linear','multi_mlp')
STATE_MODELS=('hmm','bmm_hmm','empirical_bmm_hmm','lg_ar1','empirical_lg_ar1')
PANEL_OPERATORS={'F1':('psth','schematic'),'F2':('projection_ari','decoding','trace','historical_bootstrap'),'F3':('conditional_residual',),
 'F4':('state_trace','oracle'),'F5':('decoding',),'F6':('pruning','psth'),'F7':('regional_timing','regional_decoding'),
 'F8':('external_decoding',),'S1':('state_graph',),'S2':('rank_curve',),'S3':('fourier','pca_refit'),
 'S4':('imposter_null',),'S5':('savgol','oracle_error'),'S6':('lick_decoding',),'S7':('session_scaling',),'S8':('neuron_rank',)}
def need(v,msg):
 if not v:raise Refusal(msg)
def unique(rows,key):
 values=[r[key]for r in rows];need(len(values)==len(set(values)),'duplicate '+key)
 return set(values)
def validate(study):
 need(study['schema']=='trial_full_study_v4','study schema')
 need(study['recipe']in('paper_method_reconstruction','prospective40'),'named recipe')
 need(study['canonical']=='PAPER-paper-method-replacement-009','canonical identity')
 need(set(study['cohorts'])==set(COHORTS),'complete historical and prospective populations')
 cases=study['cases'];ids=unique(cases,'id')
 for c in cases:
  relative(c['id']);need(c['cohort']in COHORTS,'cohort');need(c['status']in('available','unavailable','unknown'),'case disposition')
  need(type(c['session'])is str and type(c['animal'])is str and c['animal']!='','original session/animal')
  if c['status']=='available':need(c['raw']is not None and c['original_definition']is not None,'actual input/definition pins')
  else:need(c['reason']is not None,'unavailable/unknown reason')
 # The actual incidence is retained, never made Cartesian by these checks.
 bw=[c for c in cases if c['cohort']=='brainwide433']
 need(len({c['session']for c in bw})==433 and len({c['region']for c in bw})==270,'433/270 declared full incidence')
 for s,r in {(c['session'],c['region'])for c in bw}:
  need({c['target']for c in bw if(c['session'],c['region'])==(s,r)}=={'choice','prior'},'both brainwide targets')
 re=[c for c in cases if c['cohort']=='prospective40'];need(len({c['session']for c in re})==40,'separate RE40')
 for s in {c['session']for c in re}:
  need({c['target']for c in re if c['session']==s}=={'choice','prior','wheel-speed','whisker-motion-energy'},'RE four target dispositions')
 expected={'comparison10':10,'backbone30':30,'allen_lick7':7,'primate_rtt':1}
 for name,count in expected.items():need(len(set(study['cohorts'][name]['sessions']))==count,'original cohort '+name)
 need(study['cohorts']['scaling']['training_sizes']==[5,10,20,40,73],'full scaling sizes')
 need(len(study['cohorts']['scaling']['test_sessions'])==5,'fixed five scaling test sessions')
 need(len(study['cohorts']['ibl_unaligned']['train_sessions'])==50 and len(study['cohorts']['ibl_unaligned']['test_sessions'])==10,'unaligned 50/10')
 need(len(study['cohorts']['allen_visual_running']['train_sessions'])==58 and len(study['cohorts']['allen_visual_running']['test_sessions'])==10,'Allen58/10')
 for name in COHORTS:
  cohort=study['cohorts'][name];declared=set(cohort.get('sessions',cohort.get('train_sessions',[])+cohort.get('test_sessions',[])))
  need(declared=={c['session']for c in cases if c['cohort']==name},'source-owned complete cohort/case inverse '+name)
  if 'train_sessions'in cohort:need(not set(cohort['train_sessions'])&set(cohort['test_sessions']),'original cohort disjoint train/test roles')
 panels=study['panels'];unique(panels,'id');need({p['group']for p in panels}==set(OBLIGATIONS),'all16 groups')
 for group,operators in PANEL_OPERATORS.items():need(set(operators)<={p['operator']for p in panels if p['group']==group},'complete required operations for '+group)
 for p in panels:
  need(p['operator']in PANEL_OPERATORS[p['group']],'fixed full panel dispatch')
  need(set(p['cases'])<=ids and p['definition']is not None,'panel selected original support/recipe')
  need(p['status']in('available','unavailable','unknown'),'panel disposition')
 jobs=study['jobs'];jids=unique(jobs,'id');paired={}
 for j in jobs:
  relative(j['id']);need(set(j['cases'])<=ids and j['cases'],'job cases')
  need(j['role']in('reference','candidate'),'fit jobs only; panels have a separate full census')
  need(j['arm']in CONDITIONS,'information arm')
  need(j['method']in MODELS+STATE_MODELS+('improved',),'fixed model family')
  need(j['configuration']is not None and j['split']is not None,'source-selected fit/split')
  need(not set(j['cases'])&set(j['prior_training_cases']),'disjoint fold case roles')
  need(set(j['prior_training_cases'])<=ids,'complete source-owned training case inventory')
  if j['role']=='candidate':paired.setdefault((tuple(j['cases']),canonical(j['split']),canonical(j['configuration'])),set()).add(j['arm'])
  need(set(j['depends_on'])<=jids and j['id']not in j['depends_on'],'job dependency')
 need(all(v==set(CONDITIONS)for v in paired.values()),'both arms identical support/budget')
 for c in cases:
  need(all(sum(c['id']in j['cases']and j['role']=='candidate'and j['arm']==a for j in jobs)==1 for a in CONDITIONS),'one complete query assignment per arm/case')
  need(any(c['id']in j['cases']and j['role']=='reference'for j in jobs),'every case has reference disposition')
  need(all(any(c['id']in j['cases']and j['role']=='candidate'and j['arm']==a for j in jobs)for a in CONDITIONS),'every case two arms')
 # Topological order is selected, including fitted empirical-prior dependencies.
 seen=set()
 for j in jobs:need(set(j['depends_on'])<=seen,'original dependency order');seen.add(j['id'])
 need(len(jobs)<=study['limits']['jobs'],'fixed capacity')
 return study

def support_summary(study):
 return {'cohorts':{name:{'declared_cases':sum(c['cohort']==name for c in study['cases']),
 'dispositions':{status:sum(c['cohort']==name and c['status']==status for c in study['cases'])for status in('available','unavailable','unknown')}}for name in COHORTS},
 'panels':[{k:p[k]for k in('id','group','operator','status','reason')}for p in study['panels']],
 'actual_support_verified':False,'counts_are_not_authority':True}
