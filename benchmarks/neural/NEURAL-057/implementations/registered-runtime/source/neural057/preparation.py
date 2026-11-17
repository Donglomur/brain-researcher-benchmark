"""Actual original-source preparation, separate from any participant worker.

The raw EEG dictionary decoder is restricted to the pinned NumPy representation;
no arbitrary pickle classes or producer CSV predictions are admitted.
"""
import io,pickle,hmac,hashlib
from .domain import fields,need,parse,encoded,sha,PEOPLE
from .storage import read,json_write
from .taxonomy import category_schema,mapping,project_original_image_metadata
from .splits import window_indices,concept_groups,person_roles
from .features import mean_eeg,image_features,panel_features

def decode_official_epoch(raw):
    import numpy as np
    from numpy.lib import format
    stream=io.BytesIO(raw);version=format.read_magic(stream)
    need(version in ((1,0),(2,0)),'official NPY version')
    shape,fortran,dtype=(format.read_array_header_1_0(stream) if version==(1,0) else format.read_array_header_2_0(stream))
    need(shape==() and fortran is False and dtype==np.dtype('O'),'official scalar dictionary container')
    class Restricted(pickle.Unpickler):
        def find_class(self,module,name):
            allowed={('numpy','ndarray'):np.ndarray,('numpy','dtype'):np.dtype,
                     ('numpy.core.multiarray','_reconstruct'):np.core.multiarray._reconstruct,
                     ('numpy._core.multiarray','_reconstruct'):np.core.multiarray._reconstruct,
                     ('numpy.core.multiarray','scalar'):np.core.multiarray.scalar,
                     ('numpy._core.multiarray','scalar'):np.core.multiarray.scalar}
            need((module,name) in allowed,'no arbitrary serialized Python callable')
            return allowed[module,name]
        def persistent_load(self,pid):raise ValueError('no external pickle reference')
    container=Restricted(stream).load();need(stream.read(1)==b'','no trailing original data')
    need(type(container) is np.ndarray and container.shape==() and container.dtype==np.dtype('O'),'one original scalar dictionary')
    value=container.item();fields(value,('preprocessed_eeg_data','ch_names','times'))
    return value

class Prepared:
    def __init__(self,authority,journal):
        self.authority=authority;self.journal=journal;self.complete=False;self.data={};self.originals=[]
        authority.validate_live();authority.retain(self)
        a=authority.root['assets'];fields(a,('metadata','taxonomy_schema','taxonomy_schema_sha256','taxonomy_mapping','images','eeg','private_query_key'))
        b=authority.budget;root=authority.root['asset_root'];start=b.cost_point()
        def get(d,cap):
            raw=read(root,d,b,cap);self.originals.append(d);return raw
        meta=project_original_image_metadata(parse(get(a['metadata'],16777216)))
        schema=parse(get(a['taxonomy_schema'],65536));categories=category_schema(schema,a['taxonomy_schema_sha256'])
        self.category_sha=sha(encoded(schema));tax=parse(get(a['taxonomy_mapping'],16777216))
        need(tax['category_schema_sha256']==self.category_sha,'mapping to original category order')
        concepts=sorted({r['concept_id'] for part in meta.values() for r in part})
        self.labels=mapping(tax,categories,concepts);self.metadata=meta;self.categories=categories
        key=get(a['private_query_key'],32);need(len(key)==32,'original private query-ID key, never public')
        images=a['images'];need(type(images) is list and [r['image_id'] for r in images]==[r['image_id'] for p in ('training','test') for r in meta[p]],'complete original image source alignment')
        import numpy as np
        pixels=[]
        for row in images:
            fields(row,('image_id','file'));b.admit('before original image feature extraction')
            pixels.append(image_features(get(row['file'],33554432)));b.check('after original image feature extraction')
        self.image={'training':np.stack(pixels[:16540]),'test':np.stack(pixels[16540:])}
        need(type(a['eeg']) is list and [r['person'] for r in a['eeg']]==list(PEOPLE),'all ten original people')
        coordinates=None
        for person in a['eeg']:
            fields(person,('person','training','test'));p=person['person'];self.data[p]={}
            for kind,n,reps in [('training',16540,4),('test',200,80)]:
                b.admit('before original EEG read/decode')
                v=decode_official_epoch(get(person[kind],8589934592));x=v['preprocessed_eeg_data']
                need(type(x) is np.ndarray and x.shape==(n,reps,17,100),'complete original EEG dimensions')
                coord={'times':np.asarray(v['times']).tolist(),'channels':np.asarray(v['ch_names']).tolist()}
                windows=window_indices(coord['times'],coord['channels'])
                if coordinates is None:coordinates=coord
                need(coord==coordinates,'same verified coordinates across original people/splits')
                self.data[p][kind]=mean_eeg(x,reps,windows);b.check('after original repeated response mean')
        self.coordinates=coordinates
        self.groups=concept_groups([r['concept_id'] for r in meta['training']])
        self.query_ids={p:[hmac.new(key,('NEURAL-057/'+p+'/'+r['image_id']).encode(),hashlib.sha256).hexdigest() for r in meta['test']] for p in PEOPLE}
        self.private={p:[{'query_id':q,'concept_id':r['concept_id'],'target':self.labels[r['concept_id']]} for q,r in zip(self.query_ids[p],meta['test'])] for p in PEOPLE}
        self.receipt=json_write(journal,'PREPARATION.json',{'schema':'neural057-original-preparation-v1','root_sha256':authority.digest,'source_sha256':sha(encoded(authority.root['source_members'])),'category_schema_sha256':self.category_sha,'original_assets':self.originals,'coordinates':coordinates,'groups':self.groups,'census':{'people':10,'training_images':16540,'training_concepts':1654,'query_images':200,'query_concepts':200,'taxonomy_assigned':1448,'taxonomy_unsupported':406},'claim':'released MVNN representation; prospective windows; no causal isolation'})
        end=b.cost_point();self.setup={'wall_seconds':end['clock']-b.origin,**{k:end[k] for k in ('cpu_seconds','read_bytes','write_bytes','files','model_calls','stream_bytes')}};self.complete=True

    def live(self):
        self.authority.validate_live();need(self.complete and any(x is self for x in self.authority.attempts),'actual completed original preparation owner')

    def fit_data(self,cell):
        self.live();import numpy as np
        roles=person_roles(cell['person']);xs=[];ys=[];people=[];concepts=[]
        supported=[r for r in self.metadata['training'] if self.labels[r['concept_id']] is not None]
        ids=[r['row'] for r in supported]
        for p in roles['final_train']:
            x=panel_features(self.image['training'],self.data[p]['training'],cell['panel']);xs.append(x[ids]);ys.extend(self.labels[r['concept_id']] for r in supported);people.extend([p]*len(ids));concepts.extend(r['concept_id'] for r in supported)
        return np.concatenate(xs),np.asarray(ys,dtype='u1'),people,concepts,roles

    def query_data(self,cell):
        self.live();return panel_features(self.image['test'],self.data[cell['person']]['test'],cell['panel'])
