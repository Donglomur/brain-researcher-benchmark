"""Source-owned common split, regional unit inverse and prepared-case occurrences.

These handles attest local captured metadata/caller lineage, never authentic-data
qualification or native admission. The upstream genuine input compiler stays open.
"""
from dataclasses import dataclass
from .domain import Refusal, MissingDefinition, Pin, TARGETS, canonical, strict_json, identity, validate_plan,closed

from . import schemas

_ISSUER=object()

@dataclass(frozen=True)
class RegionalSelection:
    owner: object
    case_id: str
    source_support: object
    capture: object
    indices: tuple
    source_units: tuple
    selected_units: tuple
    regions: tuple
    atlas: Pin
    token: object
    def require_original(self):
        if self.token is not _ISSUER or self.owner.regions.get(self.case_id) is not self:
            raise Refusal('regional selection issuer/occurrence')
        self.owner.require_ready()
        self.owner.store.require_capture(self.source_support)
        self.owner.store.require_capture(self.capture)
        return self

@dataclass(frozen=True)
class PreparedCase:
    owner: object
    case_id: str
    capture: object
    regional: RegionalSelection
    raw_document: bytes
    token: object
    def require_original(self):
        if self.token is not _ISSUER or self.owner.prepared.get(self.case_id) is not self:
            raise Refusal('prepared case issuer/occurrence')
        self.owner.require_ready(); self.regional.require_original()
        self.owner.store.require_capture(self.capture)
        if self.owner.store.read(self.capture.pin)!=self.raw_document:raise Refusal('prepared capture bytes')
        return self
    def document(self):
        self.require_original();return schemas.prepared(strict_json(self.raw_document))
    def query_support(self):
        d=self.document();s=d['full_support']
        rows=tuple(i for i,j in enumerate(d['row_inverse']) if s['partition'][j]=='test')
        ids=tuple(canonical(s['trial_ids'][d['row_inverse'][i]]) for i in rows)
        return rows,ids

def common_split_document(profile,cohort,source_selection,case_supports):
    """Pure deterministic descriptor calculation; its return confers no authority.

    Deliberately no input support/manifest Pin in this body: those original records
    can already name this split without a self-hash cycle. A later binding capture
    joins all actual original supports to this earlier actual split occurrence.
    """
    from .interchange import prospective_split,validate_trial_support
    if profile!='prospective40':raise MissingDefinition('historical split producer remains unselected')
    groups={}
    for case,support in case_supports:
        validate_trial_support(support)
        if case.dataset!='ibl' or support['session']!=case.session:raise Refusal('common split session/dataset')
        groups.setdefault(case.session,[]).append((case,support))
    sessions=[]
    for session,rows in sorted(groups.items()):
        if {c.target for c,s in rows}!=set(TARGETS):raise Refusal('common union needs all four target eligibility populations')
        original={};eligible={}
        for case,s in rows:
            for tid,index,segment,keep in zip(s['trial_ids'],s['sequence_index'],s['sequence_segment'],s['eligibility']):
                key=identity(tid)
                if key[0]!='integer':raise Refusal('original prospective integer trial IDs')
                coordinate=(index,segment)
                if key in original and original[key]!=coordinate:raise Refusal('shared trial sequence identity')
                original[key]=coordinate
                if keep:eligible[key]=tid
        ids=[eligible[k] for k in sorted(eligible)]
        if not ids:raise Refusal('empty common eligible union')
        partitions=prospective_split(session,ids)
        sessions.append({'session':session,'trial_ids':ids,'partition':partitions})
    if not sessions:raise Refusal('no available common support')
    return {'schema':'trial_session_common_union_split_v2','profile':profile,
            'cohort':cohort.document(),'source_selection':source_selection.document(),
            'algorithm':'existing_EID_NUL_integerID_SHA256_floor70_floor80', 'sessions':sessions}

class Preparation:
    def __init__(self,plan,input_store,store):
        validate_plan(plan)
        self.plan=plan;self.input_store=input_store;self.store=store
        self.started=False;self.state='new';self.first=None;self.secondary=[]
        self.supports={};self.manifests={};self.split=None;self.binding=None
        self.regions={};self.prepared={};self.case_attempts=set();self.case_states={}
    def fail(self,stage,exc):
        value={'stage':stage,'type':type(exc).__name__,'message':str(exc)[:4096]}
        if self.first is None:self.first=value
        else:self.secondary.append(value)
        self.store.budget.fail(stage,exc)
    def begin(self):
        if self.started:raise Refusal('preparation/common split already attempted')
        self.started=True;self.state='attempted'
        try:
            rows=[]
            for ordinal,case in enumerate(self.plan.cases):
                if case.availability!='available':continue
                if case.dataset!='ibl':raise MissingDefinition('external input producer remains unavailable')
                raw=self.input_store.read(case.trial_support);support=strict_json(raw)
                cap=self.store.put('preparation/original-support/'+str(ordinal)+'.json',raw)
                self.supports[case.case_id]=(cap,raw)
                manifest_raw=self.input_store.read(case.source);manifest=strict_json(manifest_raw)
                if manifest['session']!=case.session or Pin.parse(manifest['support'])!=case.trial_support:
                    raise Refusal('original case manifest/support identity')
                mcap=self.store.put('preparation/original-manifest/'+str(ordinal)+'.json',manifest_raw)
                self.manifests[case.case_id]=(mcap,manifest_raw)
                rows.append((case,support))
            document=common_split_document(self.plan.profile,self.plan.cohort,self.plan.source_selection,rows)
            self.split=self.store.put_json('preparation/common-union-split.json',document)
            assignments={s['session']:{identity(i):p for i,p in zip(s['trial_ids'],s['partition'])} for s in document['sessions']}
            for case,s in rows:
                if Pin.parse(s['split_source'])!=self.split.pin:raise Refusal('original support must select exact actual common split')
                for tid,part,keep in zip(s['trial_ids'],s['partition'],s['eligibility']):
                    key=identity(tid)
                    # Shared original rows inherit the one union assignment, even when this target excludes them.
                    if key in assignments[case.session] and part!=assignments[case.session][key]:
                        raise Refusal('target/shared-row common assignment mismatch')
                    if keep and key not in assignments[case.session]:raise Refusal('eligible row absent from common split')
            for job in self.plan.jobs:
                if any(key in self.supports for key in job.case_ids) and job.split!=self.split.pin:
                    raise Refusal('selected job/common split identity')
            self.binding=self.store.put_json('preparation/common-split-binding.json',
                 {'schema':'trial_session_common_split_binding_v2','split':self.split.pin.document(),
                  'sources':[{'case':c.case_id,'original_support':c.trial_support.document(),
                              'support_capture':self.supports[c.case_id][0].pin.document(),
                              'original_manifest':c.source.document(),'manifest_capture':self.manifests[c.case_id][0].pin.document()}
                             for c,s in rows]})
            self.state='ready';return self
        except BaseException as exc:
            self.state='failed';self.fail('common-split',exc);raise
    def require_ready(self):
        if self.state!='ready' or self.split is None or self.binding is None:raise Refusal('original common split not ready')
        self.store.require_capture(self.split);self.store.require_capture(self.binding)
        if self.split.ordinal>=self.binding.ordinal:raise Refusal('common split/binding order')
    def case(self,case_id):
        case=next((x for x in self.plan.cases if x.case_id==case_id),None)
        if case is None:raise Refusal('foreign preparation case')
        return case
    def source_support(self,case_id):
        self.require_ready();cap,raw=self.supports[case_id];self.store.require_capture(cap)
        if self.store.read(cap.pin)!=raw:raise Refusal('original support capture changed')
        return strict_json(raw)
    def manifest(self,case_id):
        self.require_ready();cap,raw=self.manifests[case_id];self.store.require_capture(cap)
        if self.store.read(cap.pin)!=raw:raise Refusal('original manifest capture changed')
        return strict_json(raw)
    def enter_case(self,case):
        self.require_ready()
        if self.case(case.case_id) is not case:raise Refusal('original selected Case object')
        if case.case_id in self.case_attempts:raise Refusal('case preparation already attempted')
        self.case_attempts.add(case.case_id)
        self.case_states[case.case_id]='attempted'
    def select_region(self,case):
        if self.case_states.get(case.case_id)!='attempted' or case.case_id in self.regions:raise Refusal('regional producer order/retry')
        support=self.source_support(case.case_id);manifest=self.manifest(case.case_id)
        atlas=Pin.parse(manifest['atlas'])
        # Original atlas bytes are authenticated at the input store; no invented atlas mapping.
        self.input_store.read(atlas)
        units=tuple(canonical(x) for x in support['unit_ids']);regions=tuple(support['unit_regions'])
        if any(type(r) is not str or not r for r in regions):raise Refusal('original unit region labels')
        indices=tuple(i for i,r in enumerate(regions) if case.region=='all' or r==case.region)
        if not indices:raise Refusal('no original units in requested region')
        selected=tuple(units[i] for i in indices)
        cap=self.store.put_json('preparation/regions/'+str(self.plan.cases.index(case))+'.json',
              {'schema':'trial_session_regional_selection_v2','case':case.case_id,'region':case.region,
               'original_support':self.supports[case.case_id][0].pin.document(),'atlas':atlas.document(),
               'original_units':support['unit_ids'],'original_regions':list(regions),'indices':list(indices),
               'selected_units':[strict_json(x) for x in selected],
               'split':self.split.pin.document(),'split_binding':self.binding.pin.document()})
        value=RegionalSelection(self,case.case_id,self.supports[case.case_id][0],cap,indices,units,
                                selected,tuple(regions[i] for i in indices),atlas,_ISSUER)
        self.regions[case.case_id]=value;return value
    def selected_support(self,regional):
        regional.require_original()
        support=self.source_support(regional.case_id)
        support['unit_ids']=[strict_json(x) for x in regional.selected_units]
        support['unit_regions']=list(regional.regions)
        return support
    def complete_case(self,case,capture,regional):
        self.require_ready();regional.require_original();self.store.require_capture(capture)
        if self.case_states.get(case.case_id)!='attempted' or case.case_id in self.prepared or self.case(case.case_id) is not case:raise Refusal('prepared occurrence')
        if regional.owner is not self or regional.case_id!=case.case_id or regional.capture.ordinal>=capture.ordinal:
            raise Refusal('regional/prepared chronology')
        raw=self.store.read(capture.pin);d=schemas.prepared(strict_json(raw))
        closed(d,('schema','case_id','x','y','row_inverse','full_support','exclusions','window','method','unit_selection','common_split'),'interchange')
        if d['schema']!='trial_session_interchange_v1':raise Refusal('interchange schema')
        for name,axes in (('x',['original_trial','time','unit']),('y',['original_trial','output'])):
            leaf=d[name];closed(leaf,('pin','dtype','shape','axis_ids'),'prepared leaf')
            self.store.earlier_capture(Pin.parse(leaf['pin']),capture)
            if leaf['axis_ids']!=axes or len(leaf['shape'])!=len(axes):raise Refusal('prepared coordinate axes')
            if any(type(v) is not int or v<=0 for v in leaf['shape']):raise Refusal('prepared positive shape')
        expected=self.selected_support(regional)
        if d['case_id']!='preparation/'+case.case_id:raise Refusal('prepared source case')
        schemas.exact(d['full_support'],expected,'prepared source/support')
        if Pin.parse(d['unit_selection'])!=regional.capture.pin or Pin.parse(d['common_split'])!=self.split.pin:
            raise Refusal('prepared unit/split publication')
        inverse=[i for i,keep in enumerate(expected['eligibility']) if keep]
        schemas.exact(d['row_inverse'],inverse,'actual target eligibility/common-union inverse')
        if d['x']['shape'][0]!=len(inverse) or d['x']['shape'][2]!=len(regional.indices):
            raise Refusal('regional neural axes')
        if d['y']['shape'][0]!=len(inverse):raise Refusal('target row axes')
        columns=1 if case.target in ('choice','prior') else 50
        if d['y']['shape'][1]!=columns:raise Refusal('fixed target output columns')
        value=PreparedCase(self,case.case_id,capture,regional,raw,_ISSUER)
        self.prepared[case.case_id]=value;self.case_states[case.case_id]='complete';return value
    def require_job(self,job):
        self.require_ready()
        if next((j for j in self.plan.jobs if j.job_id==job.job_id),None) is not job:raise Refusal('original selected Job object')
        if job.split!=self.split.pin:raise Refusal('job split must be actual common split')
        for key in job.case_ids:
            if key not in self.prepared:raise Refusal('job preparation incomplete')
            self.prepared[key].require_original()
        return tuple(self.prepared[k] for k in job.case_ids)
