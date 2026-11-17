"""Full concept/participant split derived from authentic string metadata only."""
import sys,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from common import PEOPLE,need
from source_metadata_core import validate_metadata

def make(m):
 m=validate_metadata(m);out={}
 def token(domain,s):return hashlib.sha256(('NEURAL056/v1/'+domain+'/'+s).encode()).hexdigest()[:24]
 for part in ['train','test']:
  out[part]=[{'image_id':'img_'+token('image',part+'/'+name),'concept_id':'concept_'+token('concept',concept)} for name,concept in zip(m[part+'_img_files'],m[part+'_img_concepts_THINGS'])]
 concepts=sorted({x['concept_id'] for x in out['train']},key=lambda x:(token('development',x),x));dev=set(concepts[:330]);out['development_indices']=[i for i,x in enumerate(out['train']) if x['concept_id']in dev];out['fit_indices']=[i for i,x in enumerate(out['train']) if x['concept_id']not in dev]
 out['folds']=[{'held_person':p,'training_people':[s for s in PEOPLE if s!=p],'inner_person_folds':[{'held':q,'fit':[s for s in PEOPLE if s not in(p,q)]} for q in PEOPLE if q!=p]} for p in PEOPLE]
 out['schema']='neural056_roster_v1';return out
