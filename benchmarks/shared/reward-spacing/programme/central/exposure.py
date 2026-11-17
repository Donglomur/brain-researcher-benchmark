"""Persistent common-corpus exposure ledger; identity is trusted custodian input."""
from pathlib import Path
import os,time
from .io import need,encode,decode,digest,capture,ordinary
ROLES={'paper_reproduction','paper_results','author_code_results','public_development','training','query_release','query_target','closed_interpretation','independent_replication'}
class Ledger:
    def __init__(self,path,identity):
        self.path=Path(path);self.identity=identity
        need(isinstance(identity,str) and len(identity)==64,'operator ledger identity')
    def records(self):
        raw=capture(self.path,cap=8<<20);doc=decode(raw)
        need(doc['schema']=='reward_shared_exposure_ledger_v1' and doc['identity']==self.identity,'shared ledger identity')
        previous=None
        for e in doc['events']:
            need(e['previous']==previous and e['digest']==digest({k:v for k,v in e.items() if k!='digest'}),'exposure chain')
            previous=e['digest']
        return doc
    def _prior(self,lineage,corpus_key):
        # Historical v1 keys included an arbitrary version. All three registered
        # tasks share this source family, so include their old keys conservatively.
        # This explicit legacy join preserves exposure across exports and aliases;
        # an independently authenticated new replication cannot be asserted by
        # editing a version, asset hash or biological-registry field.
        need(isinstance(corpus_key,str) and len(corpus_key)==64,'corpus family key')
        return [e for e in self.records()['events'] if e['actor_lineage']==lineage and
                e['canonical_task'] in ('PAPER-FIND-044','NEURAL-045','NEURAL-046')]
    def check(self,lineage,corpus_key,animals,claim,role):
        need(isinstance(lineage,str) and lineage and role in ROLES,'registered actor lineage/role')
        need(claim in ('exploratory','protected','confirmatory'),'explicit claim lane')
        prior=self._prior(lineage,corpus_key)
        if claim in ('protected','confirmatory'):
            # A paper-wide exposure bars the whole corpus, not just listed aliases.
            need(not any(e['role'] in {'paper_reproduction','paper_results','author_code_results'} for e in prior),'same-corpus paper exposure bars protected reuse')
            need(not any(e['role'] in {'training','query_target','closed_interpretation'} and (not e['animals'] or set(e['animals'])&set(animals)) for e in prior),'protected animal information already exposed')
        if claim=='confirmatory':
            need(any(e['role']=='independent_replication' for e in prior),'new sequestered replication evidence required')
            need(not any(e['role']=='public_development' for e in prior),'public historical corpus remains exploratory')
        return {'actor_lineage':lineage,'prior_events':len(prior),'claim_lane':claim,'scientific_qualification':False}
    def append(self,record):
        keys={'actor_lineage','episode','canonical_task','corpus_key','source_assets_and_transforms','visible_modalities','time_ranges','paper_results_seen','code_results_or_constants_seen','role','animals','timestamp'}
        need(set(record)==keys and record['role'] in ROLES,'complete exposure record')
        need(record['canonical_task'] in ('PAPER-FIND-044','NEURAL-045','NEURAL-046'),'one existing canonical task')
        lock=self.path.with_suffix('.lock');fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        try:
            doc=self.records();previous=doc['events'][-1]['digest'] if doc['events'] else None
            e=dict(record,previous=previous);e['digest']=digest(e);doc['events'].append(e)
            pending=self.path.with_suffix('.pending');ordinary(pending,False)
            with pending.open('xb') as stream:stream.write(encode(doc));stream.flush();os.fsync(stream.fileno())
            os.replace(pending,self.path);return e['digest']
        finally:os.close(fd);lock.unlink()
    def check_training_release(self,lineage,corpus_key,animals,claim):
        if claim=='exploratory':return
        prior=self._prior(lineage,corpus_key)
        need(not any(e['role'] in {'query_release','query_target'} and (not e['animals'] or set(e['animals'])&set(animals)) for e in prior),
             'new training release would disclose an earlier protected query target')
def create(path,identity):
    p=ordinary(path,False)
    with p.open('xb') as f:f.write(encode({'schema':'reward_shared_exposure_ledger_v1','identity':identity,'events':[]}))
