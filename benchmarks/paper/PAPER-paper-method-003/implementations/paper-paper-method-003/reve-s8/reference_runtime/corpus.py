"""Closed, bounded-shard full-corpus input stream; no discovery or download."""
from .catalog import need
from .io import data_view

class CorpusStream:
    def __init__(self,io,name,c):
        parent=io.parent(name);product=parent['product'];provenance=parent.get('provenance',{})
        need(product['kind']=='preprocessing' and provenance.get('stage')=='S22' and provenance.get('source')==product['source'] and provenance.get('request')==product['request'],'S08 requires the actual registered S22 producer')
        details=product['details'];need(details['recipe'].get('kind')=='full_session_corpus' and details['unit_projection'].get('physical')=='session_zscore_clipped15','full-session registered corpus method required')
        bucket=details['unit_projection']['corpus'];need(bucket in product['objects'] and details['state']['normalization'] in product['objects'],'actual owned corpus and normalization products')
        self.io=io.produced_view(name);self.c=c;self.m=self.io.json(bucket['path'])
        required={'schema','dataset','unit','sampling_hz','source_inventory','expected_source_ids','pretraining_exclusion_qualification','geometry_qualification','normalization_qualification','chunks','geometry_dictionary','corpus_identity','excluded_sources'}
        need(set(self.m)==required and self.m['schema']=='reve-corpus-buckets-v1','complete closed corpus stream')
        need(self.m['dataset']=='REVE-92-source-corpus' and self.m['unit']=='session_zscore_clipped15' and self.m['sampling_hz']==200,'full original corpus input projection')
        need(self.m['source_inventory'] and self.m['pretraining_exclusion_qualification'] and self.m['normalization_qualification'] and self.m['geometry_qualification']==c['geometry_qualification'],'independently qualified corpus identities/exclusions/statistics')
        need(self.m['normalization_qualification']==details['recipe']['normalization_identity'],'normalization producer and stream cannot disagree')
        sources=self.m['expected_source_ids'];need(len(sources)==len(set(sources))==92,'all92 actual source slots')
        chunks=self.m['chunks'];need(chunks and len({x['view'] for x in chunks})==len(chunks),'nonduplicated selected corpus shards')
        actual=set()
        for row in chunks:
            need(set(row)=={'view','rows','channels','source_ids','events_identity'},'closed shard metadata')
            need(type(row['rows'])is int and row['rows']>0 and type(row['channels'])is int and row['channels']>(6 if c['purpose']=='R-native' else 0) and row['events_identity'],'qualified shard extent and original channel eligibility')
            need(row['source_ids'] and set(row['source_ids'])<=set(sources),'source identity cannot be invented by the loader');actual.update(row['source_ids'])
        exclusions=self.m['excluded_sources'];need(type(exclusions)is list,'explicit source exclusions')
        excluded=set()
        for item in exclusions:
            need(set(item)=={'source_id','reason','evidence','eligible_windows'} and item['source_id'] in sources and item['source_id'] not in excluded and item['reason'] and item['evidence'] and item['eligible_windows']==0,'qualified zero-eligible source disposition')
            excluded.add(item['source_id'])
        need(not actual&excluded and actual|excluded==set(sources),'no omitted corpus source or invented positive eligibility');self.summary={'support':self.m['corpus_identity'],'channel_ids':[]}
    def geometry(self):return self.io.array(self.m['geometry_dictionary'])
    def number_batches(self,batch):return sum((x['rows']+batch-1)//batch for x in self.m['chunks'])
    def batches(self,generator,batch):
        import torch
        from .catalog import identity
        for idx in torch.randperm(len(self.m['chunks']),generator=generator).tolist():
            row=self.m['chunks'][idx];manifest,x,pos,_=data_view(self.io,row['view'],'pretrain',self.c)
            need(x.shape[:2]==(row['rows'],row['channels']) and identity(manifest['events'])==row['events_identity'],'actual shard support matches selected full corpus census')
            need(manifest['corpus_identity']==self.m['corpus_identity'] and manifest['pretraining_exclusion_qualification']==self.m['pretraining_exclusion_qualification'] and manifest['normalization_qualification']==self.m['normalization_qualification'],'each actual shard shares qualified corpus exclusions/statistics')
            order=torch.randperm(len(x),generator=generator).tolist()
            for start in range(0,len(order),batch):
                ids=order[start:start+batch];positions=pos[ids] if pos.ndim==3 else pos[None].repeat(len(ids),axis=0)
                yield manifest,x[ids],positions,ids
            # Release this shard before reading the next. Repeated epoch I/O is
            # actual training cost inside the same native process receipt.
            del x,pos
