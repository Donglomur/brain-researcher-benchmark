"""NEURAL083 fixed full-panel protocol; pure metadata arithmetic."""
import math,hashlib,hmac,json
PEOPLE=tuple(range(1,55));SESSIONS=(1,2)
SETTINGS=('target20','transfer0','target100','other_session20')
ARMS=('EEG','CONTEXT','PERMUTED_EEG')
CHANNEL_INDEX_1=(8,9,10,11,13,14,15,18,19,20,21,33,34,35,36,37,38,39,40,41)
N_TRIALS=100;SAMPLES=251;CHANNELS=20

def need(ok,message):
 if not ok:raise ValueError(message)
def exact(v,fields):need(type(v)is dict and set(v)==set(fields),'Exact object fields')
def token(secret,kind,value):return kind+'_'+hmac.new(secret,(kind+'\0'+str(value)).encode(),hashlib.sha256).hexdigest()[:24]
def training_selection(person,session,setting,records):
 need(person in PEOPLE and session in SESSIONS and setting in SETTINGS,'Declared person/session/setting')
 result=[]
 for r in records:
  pp,ss=r['person'],r['session'];n=0;role='donor'
  if pp!=person:n=100
  elif setting=='target20' and ss==session:n=20;role='calibration'
  elif setting=='target100' and ss==session:n=100;role='calibration'
  elif setting=='other_session20' and ss==3-session:n=20;role='calibration'
  if n:result.append((pp,ss,n,role))
 need(sum(x[2] for x in result if x[3]=='calibration')=={'target20':20,'transfer0':0,'target100':100,'other_session20':20}[setting],'Exact target label budget')
 return result

def indices(onsets):
 # Source MATLAB positive round(idc + t/10), inclusive100:350, then convert1-based.
 need(type(onsets)is list and len(onsets)==100 and all(type(t)is int and t>0 for t in onsets) and all(a<b for a,b in zip(onsets,onsets[1:])),'100chronological native1-based sample onsets')
 return [[math.floor(t/10+j+.5)-1 for j in range(100,351)] for t in onsets]
def context(session,trial,onsets):
 return [float(session==1),float(session==2),trial/99,0. if trial==0 else (onsets[trial]-onsets[trial-1])/1000.,float(trial==0)]
