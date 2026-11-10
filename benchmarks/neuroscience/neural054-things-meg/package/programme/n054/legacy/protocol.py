"""NEURAL054 frozen prospective development protocol. No empirical fitted constants."""
import hashlib,math
PERSONS=('BIGMEG1','BIGMEG2','BIGMEG3','BIGMEG4')
LABELS=('animal','bird','body part','clothing','clothing accessory','container','dessert','drink','electronic device','food','fruit','furniture','home decor','insect','kitchen appliance','kitchen tool','medical equipment','musical instrument','office supply','part of car','plant','sports equipment','tool','toy','vegetable','vehicle','weapon')
WINDOWS={'PRE':(-100,-20),'EARLY_MINUS':(60,140),'EARLY':(80,160),'EARLY_PLUS':(100,180),'LATE':(200,280)}
ARMS=('VISUAL','OCULAR','NUISANCE','NEURAL','JOINT')
FAMILIES={'VISUAL':('visual',),'OCULAR':('ocular',),'NUISANCE':('visual','ocular'),'NEURAL':('neural',),'JOINT':('visual','ocular','neural')}
FOLDS=5
N_LABELS=27
N_CONCEPTS=1854
MEG_CHANNELS=271
FAMILY_DIMS={'visual':103,'ocular':24,'neural':1084}

def need(ok,msg):
 if not ok:raise ValueError(msg)

def number(x,lo=-1e12,hi=1e12):return type(x) in (int,float) and lo<=x<=hi and math.isfinite(x)
def concept_fold(concept):
 need(type(concept)is int and 1<=concept<=N_CONCEPTS,'Source concept identity')
 return int.from_bytes(hashlib.sha256(('NEURAL054-concept-v1:'+str(concept)).encode()).digest()[:8],'big')%FOLDS

def cases():return [{'case':f'{person}_S{session:02}_F{fold}','person':person,'session':session,'fold':fold} for person in PERSONS for session in range(1,13) for fold in range(FOLDS)]

def member(row,c):
 if row['person']==c['person'] and row['session']==c['session'] and concept_fold(row['concept'])==c['fold']:return 'query'
 if row['person']!=c['person'] and row['session']!=c['session'] and concept_fold(row['concept'])!=c['fold']:return 'train'
 return None

def window_indices(window,rate):
 need(window in WINDOWS and rate in (200,1200),'Frozen window/grid')
 a,b=WINDOWS[window];return list(range(int((a+100)*rate/1000),int((b+100)*rate/1000)))

def bins(window,rate):
 indexes=window_indices(window,rate);n=len(indexes)//4;need(len(indexes)%4==0,'Four equal20ms bins');return [indexes[k*n:(k+1)*n] for k in range(4)]

def mean(xs):need(bool(xs),'Nonempty mean');return math.fsum(xs)/len(xs)
def summary(xs):
 need(len(xs)==4,'Exactly four participants')
 if any(x is None for x in xs):return {'mean':None,'se':None,'descriptive_interval':None,'n':sum(x is not None for x in xs)}
 m=mean(xs);se=math.sqrt(math.fsum((x-m)**2 for x in xs)/3/4)
 return {'mean':m,'se':se,'descriptive_interval':[m-3.182446*se,m+3.182446*se],'n':4}

def rank_ok(singular):
 need(len(singular)>=8 and all(number(float(v),0,1e100) for v in singular),'Finite singular values')
 return singular[0]>0 and singular[7]>singular[0]*1e-10
