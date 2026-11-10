"""Closed prospective recipes. These never assert recovery of historical recipes."""
import hashlib,json
from pathlib import Path

DATASETS={'PhysioNet-MI':(4,800),'BCIC-IV-2a':(4,800),'TUEV':(6,1000),'TUAB':(2,2000),'HMC':(5,6000),'ISRUC':(5,6000),'FACED':(9,2000),'Mumtaz2016':(2,1000),'MentalArithmetic':(2,1000),'BCIC2020-3':(5,600)}
DATASETS.update({'PhysioNet-MI-LR':(2,800),'BCIC-IV-2a-LR':(2,800)})
BASES=('REVE-Small','REVE-Base','REVE-Large','CBraMod','EEGNet','EEGConformer','SPaRCNet','ContraWR','CNN-Transformer','FFCL','ST-Transformer','BIOT','LaBraM-Base','LaBraM-Large','LaBraM-Huge','DeepSleepNet','USleep','fixed_spectral_ridge')
ALIASES={**{b:b for b in BASES},**{b+s:b for b in ('REVE-Base','CBraMod','BIOT','LaBraM-Base') for s in ('_PT','_frozen','_noPT')},'REVE-Base-PT':'REVE-Base','REVE-Base-XFT':'REVE-Base'}
BRAINDEX='1aea0425029aca30adb26735807ee11a9964637b'

def canonical(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()
def need(x,msg):
    if not x:raise ValueError(msg)
def identity(x):return hashlib.sha256(canonical(x)).hexdigest()
def recipe(method,dataset,ablation=None):
    need(method in ALIASES and dataset in DATASETS,'closed model/dataset registry')
    ablation=ablation or {}
    base=ALIASES[method];classes,samples=DATASETS[dataset]
    if dataset=='PhysioNet-MI' and 'channels' in ablation:classes=2
    if method in ('REVE-Base-PT','REVE-Base-XFT'):
        need(dataset=='BCIC-IV-2a-LR','fewshot encoder endpoint');classes=2
    need(base not in ('DeepSleepNet','USleep') or dataset=='ISRUC','additional sleep methods are ISRUC only')
    stages=[{'name':'FT','epochs':100,'learning_rates':[0.0001,0.0005,0.001],'weight_decay':0.01}]
    if base=='EEGNet':stages=[{'name':'FT','epochs':300,'learning_rates':[0.001],'weight_decay':0.0}]
    if base.startswith(('REVE','CBraMod','BIOT','LaBraM')):
        stages=[{'name':'LP','epochs':20,'learning_rates':[0.001],'weight_decay':0.01},{'name':'FT','epochs':80,'learning_rates':[0.0001,0.0005],'weight_decay':0.01}]
    if method.endswith('_frozen') or ablation.get('adaptation')=='LP' or 'pooling' in ablation:stages=stages[:1]
    if base=='fixed_spectral_ridge' or method=='REVE-Base-PT':stages=[]
    return {'schema':'reve-fixed-prospective-recipe-v1','method':method,'base':base,'dataset':dataset,'classes':classes,'samples':samples,'sampling_hz':200,'sequence_length':20 if dataset=='ISRUC' else 1,'stages':stages,'batch_size':8 if dataset=='ISRUC' else 32,'selection':'binary_AUROC_or_multiclass_kappa' if base=='fixed_spectral_ridge' else 'balanced_accuracy','tie':'first_chronological','refit_validation':False,'optimizer':'closed_form_ridge' if base=='fixed_spectral_ridge' else 'AdamW','penalties':[.001,.01,.1,1.,10.] if base=='fixed_spectral_ridge' else [],'normalization':('fixed_physical_100uV_for_PT' if method=='REVE-Base-PT' else ('training_spectral_constant_safe' if base=='fixed_spectral_ridge' else 'training_channel_abs95_then_fixed')),'geometry':'qualified_cm_cartesian_training_montage_idw3_for_fixed_channel_models','historical_reproduction':False,'profile':'S7-fixed-prospective-v1'}

def validate_configuration(c):
    required={'recipe','seed','device','scientific_cases','initialization','geometry_qualification','purpose','condition','ablation','pretraining_identity'}
    need(type(c)is dict and set(c)==required,'complete closed scientific configuration')
    r=c['recipe'];need(r==recipe(r['method'],r['dataset'],c['ablation']),'reference recipe is immutable')
    need(type(c['seed'])is int and 0<=c['seed']<2**32 and c['device'] in ('cpu','cuda'),'seed/device')
    need(c['purpose'] in ('R-paper','R-native','I-person','I-person-montage'),'scientific purpose')
    need(c['condition'] in ('source','strict_person','strict_person_and_montage'),'exposure condition')
    need(c['geometry_qualification'] and c['scientific_cases'],'selected geometry and original cases')
    need(c['initialization'] in ('scratch','qualified_passive_pretrained','qualified_parent_state'),'explicit initialization')
    method=r['method']
    if method.endswith('_noPT'):need(c['initialization']=='scratch','noPT cannot load pretraining')
    if method.endswith(('_PT','_frozen','-PT','-XFT')):need(c['initialization']!='scratch' and c['pretraining_identity'],'pretrained condition cannot silently use scratch')
    need(type(c['ablation'])is dict,'explicit scientific ablation')
    return c

def catalogue():return {m:{d:recipe(m,d) for d in DATASETS if (m not in ('DeepSleepNet','USleep') or d=='ISRUC') and (m not in ('REVE-Base-PT','REVE-Base-XFT') or d=='BCIC-IV-2a-LR')} for m in ALIASES}
