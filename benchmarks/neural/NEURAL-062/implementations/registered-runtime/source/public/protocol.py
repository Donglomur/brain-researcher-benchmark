"""NEURAL062 held-mouse closed-vocabulary image identity; prospective population features."""
import math
ARMS=('CONTEXT','PRE','POST','PRE_POST');CONTEXTS=('CHANGE','REPEAT');SETS=('A','B','G','H')
CRE=('Slc17a7-IRES2-Cre','Sst-IRES-Cre','Vip-IRES-Cre');AREA=('VISp','VISl','VISal','VISam');EXPERIENCE=('Familiar','Novel 1','Novel >1');PROJECT=('VisualBehavior','VisualBehaviorTask1B','VisualBehaviorMultiscope','VisualBehaviorMultiscope4areasx2d')
WINDOWS={'PRE':(-.5,-.25,0.),'POST':(.05,.30,.55)}
STATS=('mean','sd','q10','q25','q50','q75','q90')
BASE_NUMERIC=('run_early','run_late','pupil_early','pupil_late','run_coverage_early','run_coverage_late','pupil_coverage_early','pupil_coverage_late')
STATIC=tuple('cre_'+x for x in CRE)+tuple('area_'+x for x in AREA)+tuple('experience_'+x for x in EXPERIENCE)+('passive','depth_div400','GCaMP6f','GCaMP6s')+tuple('project_'+x for x in PROJECT)
BASE_NAMES=BASE_NUMERIC+tuple('missing_'+x for x in BASE_NUMERIC[:4])+('missing_PRE','missing_POST')+STATIC

def need(x,m):
 if not x:raise ValueError(m)
def number(x):return type(x)in(int,float) and -1e20<=x<=1e20 and math.isfinite(x)
def features(x,n):need(type(x)is list and len(x)==n and all(v is None or number(v) for v in x),'Bounded nullable features')
def names(arm):
 need(arm in ARMS,'Arm');wins={'CONTEXT':(),'PRE':('PRE',),'POST':('POST',),'PRE_POST':('PRE','POST')}[arm]
 return BASE_NAMES+tuple(f'{w}_{b}_{s}' for w in wins for b in(0,1) for s in STATS)
def running_bin(v):
 if v is None:return 'missing'
 need(number(v),'Running scalar');return 'below1' if v<1 else '1to5' if v<5 else '5to10' if v<10 else '10plus'
def static(row):
 need(row['cre_line'] in CRE and row['targeted_structure'] in AREA and row['experience_level'] in EXPERIENCE and row['project_code'] in PROJECT and row['passive'] in('True','False') and row['indicator'] in('GCaMP6f','GCaMP6s'),'Known metadata categories')
 d=float(row['targeted_imaging_depth']);need(math.isfinite(d) and 0<d<=1000,'Native depth')
 return [int(row['cre_line']==x) for x in CRE]+[int(row['targeted_structure']==x) for x in AREA]+[int(row['experience_level']==x) for x in EXPERIENCE]+[int(row['passive']=='True'),d/400]+[int(row['indicator']==x) for x in('GCaMP6f','GCaMP6s')]+[int(row['project_code']==x) for x in PROJECT]
