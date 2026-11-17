"""Full train-only inner contexts and final refit packets; never expose outer EEG."""
from pathlib import Path
from .core import need,read_json,capture,save,write_new,byte_pin,digest
from .protocol import PEOPLE,validate_roster,permutation
from .arrays import decode,encode

class Panel:
    def __init__(self,path,budget):
        from legacy.public.common import validate_design
        self.root=Path(path);self.budget=budget
        self.design=validate_design(read_json(self.root/'design.json',budget=budget))
        self.roster=validate_roster(read_json(self.root/'ROSTER.json',4*1024**2,budget=budget))
        self.people=read_json(self.root/'PEOPLE.json',budget=budget)
        self.features=read_json(self.root/'FEATURES.json',budget=budget)
        self.targets=read_json(self.root/'TARGETS.json',budget=budget)
        need(digest(self.roster)==self.design['roster_sha256'] and digest(self.people)==self.design['coordinates']['source_binding_sha256']
             and digest(self.features)==self.design['feature_binding_sha256'],'complete source lineage')
        need(self.targets['design_sha256']==digest(self.design) and set(self.targets['targets'])==set(PEOPLE),'exact target descriptors, bodies unopened')
        need(set(self.people)==set(PEOPLE),'all ten people')
        pins=read_json(Path(__file__).resolve().parents[1]/'legacy/operator/SOURCE_BINDINGS.json',budget=budget)
        seen=[]
        for person in PEOPLE:
            row=self.people[person]
            need(row['person']==person and row['schema']=='neural056_staged_person_v1','staged participant')
            need(row['archive']=={k:pins['assets'][person][k] for k in ('bytes','sha256')},'publisher-to-person identity')
            need(row['coordinates']=={k:self.design['coordinates'][k] for k in ('channel_names','times_seconds','units')},'all actual coordinate equality')
            seen.append(row['arrays']['train']['sha256'])
        need(len(set(seen))==10,'no duplicate participant surrogate')
    def with_budget(self,budget):
        # Share only immutable operator metadata; every nested payload read and
        # packet write now uses this case handle, including protected validation.
        view=object.__new__(Panel);view.__dict__=dict(self.__dict__);view.budget=budget
        return view
    def training(self,person):
        row=self.people[person]['arrays']['train'];raw=capture(self.root/'people'/person/'train.npz',row['bytes'],row,self.budget)
        return decode(raw,{'mean':(16540,17,100)},230000000)['mean']
    def image_features(self,partition):
        n=16540 if partition=='train' else 200;row=self.features['arrays'][partition]
        raw=capture(self.root/'features'/(partition+'.npz'),row['bytes'],row,self.budget)
        return decode(raw,{'representation':(n,4096),'low_level':(n,768)},330000000)
    def outer_target(self,person):
        row=self.targets['targets'][person];raw=capture(self.root/'targets'/(person+'.npz'),row['bytes'],row,self.budget)
        return decode(raw,{'mean':(200,17,100),'half_odd':(200,17,100),'half_even':(200,17,100)},10000000)

def build_packet(panel,case,arm,destination,inner=None):
    import numpy as np
    need(arm in case['arms'],'known arm')
    need(case['person'] in PEOPLE and case['training_people']==[p for p in PEOPLE if p!=case['person']],'whole outer person')
    out=Path(destination);out.mkdir(mode=0o700);train=out/'train';query=out/'query';train.mkdir();query.mkdir()
    if inner is not None:
        need(inner in case['inner'],'declared inner fold')
        people=inner['training_people'];fit=panel.roster['fit_indices'];qi=panel.roster['development_indices']
        need(len(people)==8 and case['person'] not in people and inner['held'] not in people,'held outer and inner excluded')
        qpart='train';context=inner['context_id']
    else:
        people=case['training_people'];fit=list(range(16540));qi=list(range(200));qpart='test';context=case['case_id']
    total=np.zeros((len(fit),17,100),dtype=np.float64)
    for person in people:
        data=panel.training(person)
        with np.errstate(over='raise',invalid='raise'):total+=data[fit]/len(people)
        del data
    need(np.isfinite(total).all(),'finite equally weighted training mean')
    concepts=[panel.roster['train'][i]['concept_id'] for i in fit]
    if arm=='response_permuted':total=total[permutation(concepts,1324 if inner else 1654)]
    key='low_level' if arm=='low_level' else 'representation'
    data=panel.image_features('train');x=data[key][fit];del data
    data=panel.image_features(qpart);q=data[key][qi];del data
    tpin=write_new(train/'training.npz',encode({'x':x,'y':total}),panel.budget)
    qpin=write_new(query/'query.npz',encode({'x':q}),panel.budget)
    del x,q,total
    # Actor sees opaque arm ID, never the mapping to representation/permutation.
    public={'schema':'neural056_training_context_v1','context_id':context,'arm_id':case['arms'][arm],
      'train_rows':len(fit),'query_rows':len(qi),'feature_count':768 if key=='low_level' else 4096,
      'response_shape':[17,100],'training_concept_ids':concepts,'training_image_ids':[panel.roster['train'][i]['image_id'] for i in fit],
      'seed':case['matched_rng_seed'],'arrays':{'training':{k:tpin[k] for k in ('bytes','sha256')}},
      'query_EEG_present':False,'fit_only':True}
    save(train/'context.json',public,panel.budget)
    query_meta={'schema':'neural056_query_context_v1','context_id':context,'arm_id':case['arms'][arm],
      'query_rows':len(qi),'feature_count':public['feature_count'],'response_shape':[17,100],
      'query_image_ids':[panel.roster[qpart][i]['image_id'] for i in qi],
      'arrays':{'query':{k:qpin[k] for k in ('bytes','sha256')}},'EEG_present':False}
    save(query/'context.json',query_meta,panel.budget)
    return {'train':str(train),'query':str(query),'rows':len(qi),'features':public['feature_count'],
      'case_id':case['case_id'],'context_id':context,'person':case['person'],'arm':arm,
      'inner_person':inner['held'] if inner else None,'query_indices':qi,'training_people':people,
      'training_indices':fit,'train_metadata_id':digest(public),'query_metadata_id':digest(query_meta)}

def inner_target(panel,packet):
    need(packet['inner_person'] is not None,'inner targets only')
    data=panel.training(packet['inner_person'])
    return data[packet['query_indices']].reshape(len(packet['query_indices']),1700)

