"""Concrete private compiler and arm-only materialized datasets.

The trusted evaluator alone holds original identities/targets. The actor
manifest has independent per-invocation opaque IDs, no source paths/row map,
exact time, chapter/participant strings or query labels. OS isolation and
immutable read-only mounts are required from the external native owner.
"""
from pathlib import Path
from fractions import Fraction
import hashlib,hmac,io,os
from collections import Counter
from programme.contracts import Pin,Asset,need,rational,fields
from source.neural090.public.context import derive
from .protocol import ARMS,PROTECTED,BATCH
from .planning import event_id,rank,interval_union,shifted_donors
from .custody import encoded,write_fresh,open_pinned,stable
from .features import (TrainInterval,fit_train_channel_moments,apply_frozen_channel_moments,
    AcousticTrainView,AudioClockEvidence,acoustic_features_from_reader,fit_train_acoustic_moments,
    WordSpan,TranscriptTrainView,fit_transcript_vocabulary,encode_transcript,timing_one_hot)

ROLES=(('inner','train','inner_train'),('inner','tune','inner_tune'),
       ('final','train','source_refit'),('final','calibration','calibration'),('final','query','query'))

def opaque(secret,role,original):
    need(type(secret) is bytes and len(secret)==32,'external independent32-byte invocation key')
    return hmac.new(secret,('N090-ARM-ROW-v1:'+role+':'+original).encode(),hashlib.sha256).hexdigest()

def write_array(path,shape,dtype,rows,account,ledger):
    """Write a real no-pickle NPY payload incrementally, with independent close."""
    import numpy as np
    dtype=np.dtype(dtype);header=io.BytesIO()
    np.lib.format.write_array_header_1_0(header,{'descr':dtype.str,'fortran_order':False,'shape':shape})
    head=header.getvalue();total=len(head)+dtype.itemsize*__import__('math').prod(shape)
    account.charge('write',total);stream=None;fd=None;digest=hashlib.sha256();count=0
    try:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);stream=os.fdopen(fd,'wb');fd=None
        stream.write(head);digest.update(head)
        for row in rows:
            value=np.asarray(row,dtype=dtype);need(value.shape==shape[1:] and np.isfinite(value).all(),'exact finite projected row')
            body=value.tobytes(order='C');stream.write(body);digest.update(body);count+=1
            need(count<=shape[0],'no extra projected row')
        need(count==shape[0],'all projected rows; never partial capture')
        stream.flush();os.fsync(stream.fileno());need(os.fstat(stream.fileno()).st_size==total,'full NPY extent')
    except BaseException as e:ledger.record('array-write',e)
    finally:
        if stream is not None:ledger.attempt('array-close',stream.close)
        elif fd is not None:ledger.attempt('array-fd-close',lambda:os.close(fd))
    ledger.raise_first();return {'path':Path(path).name,**Pin(total,digest.hexdigest()).json()}

class Compiler:
    def __init__(self,store,events,words):
        self.store,self.events,self.words=store,events,words
        self.rows={event_id(r):r for rows in events.values() for r in rows}
        self.context={};self.wordspans={}
        for key,rows in events.items():
            contexts=derive([r['start_sample'] for r in rows],store.index[key].clock.sample_count)
            self.context.update({event_id(r):tuple(c) for r,c in zip(rows,contexts)})
            self.wordspans[key]=tuple(WordSpan(w['canonical_word'],w['text'],rational(w['onset_seconds']),rational(w['end_seconds'])) for w in words[key])
    def acoustic(self,row,release):
        key=tuple(row['run_key']);a=self.store.supplements[key]['audio'];store=self.store
        class Reader:
            def read_interval(self,source_id,start,stop):
                need(source_id=='/'.join(key),'private exact audio owner');return store.audio(key,start,stop)
        # annotation + offset = audio-origin + source_index/rate.
        origin=rational(a['sample_zero_seconds'])-rational(a['annotation_to_audio_seconds'])
        clock=AudioClockEvidence('/'.join(key),a['sample_rate'],a['sample_count'],origin,Fraction(1,a['sample_rate']),
                                  a['evidence']['sha256'],a['decode_evidence']['sha256'],a['amplitude_evidence']['sha256'])
        return acoustic_features_from_reader(Reader(),clock=clock,event_onset_meg_seconds=rational(row['annotation_seconds']),diagnostic_release=release)
    def prepare(self,plan,arm,secret,destination,release=None):
        """Real feature producer; called only inside admitted evaluator context."""
        need(arm in ARMS,'exact arm');need((release is None)==(arm in PROTECTED),'protected-first diagnostic release boundary')
        destination=Path(destination);need(not destination.exists(),'exclusive fresh arm view directory')
        self.store.ledger.raise_first();destination.mkdir(mode=0o700)
        private={'roles':{},'normalization':{},'shift_donors':{},'acoustic':{},'transcript_overlap':{},'source_plan':plan}
        manifest={'schema':'n090-arm-view-v1','arm':arm,'roles':{},'vocabulary_sizes':{},'query_labels_present':False,
                  'exposure':'protected' if arm in PROTECTED else 'stimulus_exposed_diagnostic','row_identity':'independent_per_invocation_opaque',
                  'source_complete':False,'research_qualified':False}
        channels=tuple(self.store.channels['channel_names']);store=self.store;root_rows=self.rows
        class NeuralReader:
            channel_order=channels
            def read_interval(self,recording_id,start,stop):return store.meg(tuple(recording_id.split('/')),start,stop)
        sequence=0
        for stage,train_role in (('inner','inner_train'),('final','source_refit')):
            training=[self.rows[x] for x in plan['roles'][train_role]];moment=None;vocab=None;audio_cache={}
            if arm in ('neural','time_shifted_neural'):
                intervals=[TrainInterval('/'.join(k),store.index[k].clock.evidence.sha256,a,b,'TRAIN') for k,spans in interval_union(training).items() for a,b in spans]
                moment=fit_train_channel_moments(NeuralReader(),intervals,channel_order=channels,admission_ref=plan['case']+':'+stage)
                private['normalization'][stage]={'kind':'unique_continuous_train_samples','samples':moment.sample_count,'mean':moment.mean.tolist(),'std':moment.std.tolist(),'intervals':[(v.recording_id,v.start,v.stop) for v in moment.admitted_intervals]}
            elif arm=='acoustic':
                for row in training:audio_cache[event_id(row)]=self.acoustic(row,release)
                moment=fit_train_acoustic_moments((AcousticTrainView(event_id(r),'TRAIN',audio_cache[event_id(r)]) for r in training),admission_ref=plan['case']+':'+stage,diagnostic_release=release)
                private['normalization'][stage]={'kind':'original_TRAIN_rows_times_125_event_local_frames','rows':len(training),'frames':moment.sample_count,'mean':moment.mean.tolist(),'std':moment.std.tolist(),'unique_canonical_events':len({r['canonical_event'] for r in training})}
            elif arm=='transcript':
                vocab=fit_transcript_vocabulary((TranscriptTrainView('TRAIN',rational(r['annotation_seconds']),self.wordspans[tuple(r['run_key'])]) for r in training),admission_ref=plan['case']+':'+stage,diagnostic_release=release)
                need(len(vocab.tokens)<=50002,'fixed complete vocabulary bound; no frequency truncation');private['normalization'][stage]={'kind':'source_TRAIN_vocabulary_only','tokens':len(vocab.tokens),'frozen_vocabulary':vocab.tokens}
            manifest['vocabulary_sizes'][stage]=len(vocab.tokens) if vocab else 2
            for s,role,planrole in ROLES:
                if s!=stage:continue
                rows=[self.rows[x] for x in plan['roles'][planrole]]
                # Every role gets the independent arm key and opaque ordering; source chronology is not emitted.
                rows.sort(key=lambda r:opaque(secret,stage+'/'+role,event_id(r)))
                ids=[opaque(secret,stage+'/'+role,event_id(r)) for r in rows]
                private['roles'][stage+'/'+role]=dict(zip(ids,(event_id(r) for r in rows)))
                donor=shifted_donors(rows) if arm=='time_shifted_neural' and rows else {}
                if donor:private['shift_donors'][stage+'/'+role]={'mapping':donor,'reuse_counts':dict(Counter(donor.values()))}
                timing=[timing_one_hot(*self.context[event_id(r)]) for r in rows]
                lengths=[]
                def values():
                    for row in rows:
                        identity=event_id(row)
                        if arm in ('neural','time_shifted_neural'):
                            source=root_rows[donor[identity]] if donor else row;key=tuple(source['run_key']);a=source['start_sample']
                            yield apply_frozen_channel_moments(store.meg(key,a,a+125),moment,channel_order=channels)
                        elif arm=='timing':yield timing_one_hot(*self.context[identity])
                        elif arm=='acoustic':
                            feature=audio_cache.get(identity)
                            if feature is None:feature=self.acoustic(row,release)
                            private['acoustic'][stage+'/'+role+'/'+identity]=feature.private_audit
                            yield apply_frozen_channel_moments(feature.logmel,moment,channel_order=moment.channel_order)
                        else:
                            words=self.wordspans[tuple(row['run_key'])];onset=rational(row['annotation_seconds'])
                            value=encode_transcript(words,onset,vocab,diagnostic_release=release);lengths.append(value.length)
                            used=[w.word_id for w in sorted(words,key=lambda w:(w.start,w.end,w.word_id)) if w.end<onset][-256:]
                            private['transcript_overlap'][stage+'/'+role+'/'+identity]=[w for w in used if w in set(plan['query_word_identity_private'].values())]
                            yield value.token_ids
                shape={'neural':(306,125),'time_shifted_neural':(306,125),'timing':(25,),'acoustic':(80,125),'transcript':(256,)}[arm]
                sequence+=1;name='part%02d.npy'%sequence
                value_pin=write_array(destination/name,(len(rows),*shape),'<i8' if arm=='transcript' else '<f4',values(),store.accounting,store.ledger)
                row={'ids':ids,'values':value_pin,'shape':[len(rows),*shape],'count':len(rows)}
                if role!='query':
                    row['seed_orders']={str(seed):sorted(range(len(rows)),key=lambda k:hashlib.sha256(('N090-MATCHED-BATCH-v1:'+str(seed)+':'+event_id(rows[k])).encode()).digest()) for seed in range(10)}
                # Common coarse timing is visible to every arm. Original CNN uses only its tensor; it is unchanged.
                sequence+=1;row['timing']=write_array(destination/('part%02d.npy'%sequence),(len(rows),25),'<f4',iter(timing),store.accounting,store.ledger)
                if arm=='transcript':row['lengths']=lengths
                if role!='query':row['labels']=[r['label'] for r in rows]
                manifest['roles'][stage+'/'+role]=row
        pin=write_fresh(destination/'view.json',encoded(manifest),store.accounting,store.ledger)
        return {'manifest':{'path':'view.json',**pin.json()},'private':private,'row_counts':{k:v['count'] for k,v in manifest['roles'].items()}}

class ArmViews:
    def __init__(self,root,manifest,accounting,ledger):
        self.root=Path(root);self.manifest=manifest;self.accounting=accounting;self.ledger=ledger;self.arrays={}
        fields(manifest,('schema','arm','roles','vocabulary_sizes','query_labels_present','exposure','row_identity','source_complete','research_qualified'))
        need(manifest['schema']=='n090-arm-view-v1' and manifest['arm'] in ARMS and manifest['query_labels_present'] is False,'strict arm-only manifest')
        need(set(manifest['roles'])=={s+'/'+r for s,r,_ in ROLES},'all inner/refit/cal/query roles')
        expected_files={'view.json'}
        for key,row in manifest['roles'].items():
            required={'ids','values','shape','count','timing'}
            if not key.endswith('/query'):required|={'labels','seed_orders'}
            if manifest['arm']=='transcript':required.add('lengths')
            fields(row,required)
            for member in ('values','timing'):
                asset=Asset.parse(row[member]);need('/' not in asset.path,'flat arm-only payload members');expected_files.add(asset.path)
            if 'labels' in row:need(len(row['labels'])==row['count'] and all(type(y) is int and 0<=y<39 for y in row['labels']),'full visible source/CAL labels only')
            if 'lengths' in row:need(len(row['lengths'])==row['count'] and all(type(v) is int and 0<=v<=256 for v in row['lengths']),'explicit token prefix lengths')
            need(len(row['ids'])==len(set(row['ids']))==row['count'],'complete opaque row support')
            need(all(type(x) is str and len(x)==64 for x in row['ids']),'opaque row identity')
            need(('labels' in row)==(not key.endswith('/query')),'query label absence')
        observed=set()
        for path in self.root.iterdir():
            need(not path.is_symlink() and path.is_file(),'flat ordinary arm-only tree');observed.add(path.name)
        need(observed==expected_files,'no extra source/identity/target/other-arm file in worker view')
    def vocabulary_size(self,stage):return self.manifest['vocabulary_sizes'][stage]
    def count(self,stage,role):return self.manifest['roles'][stage+'/'+role]['count']
    def array(self,asset):
        import numpy as np
        key=asset['path']
        if key not in self.arrays:
            f=None
            try:
                f,before=open_pinned(self.root,Asset.parse(asset),self.accounting,self.ledger)
                self.accounting.charge('read',asset['bytes']);value=np.load(f,allow_pickle=False)
                need(stable(before,os.fstat(f.fileno())) and value.dtype.kind in 'fi','complete stable no-pickle arm tensor');value.setflags(write=False)
                self.arrays[key]=value
            except BaseException as e:self.ledger.propagated('arm-array-load',e)
            finally:
                if f is not None:self.ledger.attempt('arm-array-close',f.close)
            self.ledger.raise_first()
        return self.arrays[key]
    def release_stage(self,stage):
        for key,row in self.manifest['roles'].items():
            if key.startswith(stage+'/'):
                for name in ('values','timing'):self.arrays.pop(row[name]['path'],None)
    def loader(self,stage,role,seed,shuffle):
        import torch
        row=self.manifest['roles'][stage+'/'+role];values=self.array(row['values']);timing=self.array(row['timing'])
        need(tuple(values.shape)==tuple(row['shape']) and tuple(timing.shape)==(row['count'],25),'actual full arm tensor axes')
        # Sorting by a domain-separated seed hash avoids dependency-shuffle/RNG side effects.
        order=list(range(row['count']))
        if shuffle:
            order=row['seed_orders'][str(seed)]
            need(len(order)==row['count'] and set(order)==set(range(row['count'])),'complete privately paired source batch order')
        class Dataset(torch.utils.data.Dataset):
            def __len__(self):return row['count']
            def __getitem__(self,ordinal):
                i=order[ordinal];item={'values':torch.tensor(values[i]),'timing':torch.tensor(timing[i]),'ids':row['ids'][i]}
                if 'labels' in row:item['labels']=row['labels'][i]
                if 'lengths' in row:item['lengths']=row['lengths'][i]
                return item
        return torch.utils.data.DataLoader(Dataset(),batch_size=BATCH,shuffle=False,num_workers=0,drop_last=False)
