"""Closed NEURAL-017 native job identities; exact ordinal lookup, no scheduler."""
from dataclasses import dataclass
from .contracts import closed, integer, need
from .programme import CONDITIONS, REFERENCES, P4H, allowed_references, bank_id, expected_groups, group_id

SLOT_KEYS={'authoring_token_caps','investigation_exchanges','investigation_tool_slots','f_reference_calls'}
GROUPS=expected_groups()
F_IDS=tuple(group_id(g)for g in GROUPS if g['mode']=='F')
I_IDS=tuple(group_id(g)for g in GROUPS if g['mode']=='I')


def slots(selection):
    closed(selection,SLOT_KEYS)
    caps=selection['authoring_token_caps']
    need(type(caps)is list and 1<=len(caps)<=1024,'explicit finite authoring rounds')
    for cap in caps:integer(cap,1,P4H['model_tokens'])
    for key in SLOT_KEYS-{'authoring_token_caps'}:integer(selection[key],1)
    return selection


def _row(job,stage,role,parent,profile):
    return dict(job=job,stage=stage,role=role,parent_group=parent,runtime_profile=profile)


@dataclass(frozen=True)
class JobRoster:
    phase:str
    authoring_token_caps:tuple
    investigation_exchanges:int
    investigation_tool_slots:int
    f_reference_calls:int

    @classmethod
    def from_selection(cls,selection,phase):
        slots(selection);need(phase in('authoring','campaign'),'closed operator phase')
        return cls(phase,tuple(selection['authoring_token_caps']),selection['investigation_exchanges'],
                   selection['investigation_tool_slots'],selection['f_reference_calls'])
    def specification(self):
        return {'phase':self.phase,'slots':{'authoring_token_caps':list(self.authoring_token_caps),
            'investigation_exchanges':self.investigation_exchanges,
            'investigation_tool_slots':self.investigation_tool_slots,'f_reference_calls':self.f_reference_calls}}
    def __len__(self):
        return 100*len(self.authoring_token_caps)if self.phase=='authoring'else 100+50*self.f_reference_calls+28750*(self.investigation_exchanges+self.investigation_tool_slots)
    @property
    def physical_count(self):
        return len(self)if self.phase=='authoring'else len(self)+28750*self.investigation_tool_slots
    def census(self):
        if self.phase=='authoring':return {gid:2*len(self.authoring_token_caps)for gid in F_IDS}
        return {'operator':2,'references':44,'assessment':2,'reporting':2,
            **{gid:1+self.f_reference_calls for gid in F_IDS},
            **{gid:575*(self.investigation_exchanges+self.investigation_tool_slots)for gid in I_IDS}}
    def _fixed_before_F(self):
        rows=[_row('prepare/raw','S02','raw_prepare','operator','raw_operator'),
              _row('prepare/views','S03','project_views','operator','raw_operator')]
        rows += [_row('train/'+r,'S05','reference_train','references','reference_producer')for r in REFERENCES]
        rows += [_row('development/'+r,'S05','reference_development','references','reference_producer')for r in ('R0-R1','R3')]
        rows += [_row(bank_id(c,r),'S06','reference_predict','references','reference_producer')for c in CONDITIONS for r in allowed_references(c)]
        return rows
    def row(self,ordinal):
        integer(ordinal,0,len(self)-1)
        if self.phase=='authoring':
            width=2*len(self.authoring_token_caps);gi,within=divmod(ordinal,width);n,kind=divmod(within,2);gid=F_IDS[gi]
            return _row(gid+('/author-model-%04d'%n if kind==0 else'/author-check-%04d'%n),
                        'S01','model_exchange'if kind==0 else'source_syntax',gid,
                        'model_gateway'if kind==0 else'reference_producer')
        if ordinal<44:return self._fixed_before_F()[ordinal]
        current=ordinal-44;width=1+self.f_reference_calls
        if current<50*width:
            gi,part=divmod(current,width);gid=F_IDS[gi]
            if part==0:return _row(gid+'/programme','S07','participant_F',gid,'participant_'+gid.split('/')[1][-1])
            return _row(gid+'/reference-service-%06d'%part,'S07','participant_tool',gid,{'reference_predict':'reference_tool'})
        current-=50*width
        if current<2:return _row(('TOOL_ONLY_BATCH','TOOL_ONLY_CASE')[current],'S06','tool_only','references','reference_producer')
        current-=2;actor_width=self.investigation_exchanges+self.investigation_tool_slots;group_width=575*actor_width
        if current<50*group_width:
            gi,part=divmod(current,group_width);actor,call=divmod(part,actor_width);gid=I_IDS[gi]
            prefix=gid+('/preparation'if actor==0 else'/case-%04d'%(actor-1));stage='S08'if actor==0 else'S09'
            if call<self.investigation_exchanges:return _row(prefix+'/model-%03d'%call,stage,'model_exchange',gid,'model_gateway')
            n=call-self.investigation_exchanges+1
            return _row(prefix+'/tool-%03d'%n,stage,'participant_tool',gid,
                        {'run_python':'participant_'+gid.split('/')[1][-1],'reference_predict':'reference_tool'})
        tail=current-50*group_width
        return [_row('assessment/grade','S13','protected_score','assessment','protected_score'),
                _row('assessment/uncertainty','S14','protected_uncertainty','assessment','protected_score'),
                _row('report/aggregate','S15','aggregate_report','reporting','protected_score'),
                _row('report/model','S15','model_exchange','reporting','model_gateway')][tail]
    def ordinal(self,job):
        need(type(job)is str,'source-owned job ID')
        if self.phase=='campaign':
            fixed={r['job']:i for i,r in enumerate(self._fixed_before_F())}
            after=44+50*(1+self.f_reference_calls)
            fixed.update(TOOL_ONLY_BATCH=after,TOOL_ONLY_CASE=after+1)
            tail=after+2+28750*(self.investigation_exchanges+self.investigation_tool_slots)
            fixed.update({'assessment/grade':tail,'assessment/uncertainty':tail+1,'report/aggregate':tail+2,'report/model':tail+3})
            if job in fixed:return fixed[job]
        bits=job.split('/');need(len(bits)in(4,5),'closed generated job shape');gid='/'.join(bits[:3]);suffix=bits[3]
        if self.phase=='authoring':
            need(gid in F_IDS and len(bits)==4,'original authoring group')
            if suffix.startswith('author-model-'):n=int(suffix[len('author-model-'):]);kind=0
            elif suffix.startswith('author-check-'):n=int(suffix[len('author-check-'):]);kind=1
            else:raise ValueError('closed authoring slot')
            index=F_IDS.index(gid)*2*len(self.authoring_token_caps)+2*n+kind
        elif gid in F_IDS:
            need(len(bits)==4,'original F slot')
            part=0 if suffix=='programme'else int(suffix.removeprefix('reference-service-'))
            need(suffix=='programme'or suffix.startswith('reference-service-'),'closed F slot')
            index=44+F_IDS.index(gid)*(1+self.f_reference_calls)+part
        else:
            need(gid in I_IDS and len(bits)==5,'original I slot')
            actor=0 if suffix=='preparation'else int(suffix.removeprefix('case-'))+1
            need(suffix=='preparation'or suffix.startswith('case-'),'closed I actor')
            call=bits[4]
            if call.startswith('model-'):offset=int(call[len('model-'):])
            elif call.startswith('tool-'):offset=self.investigation_exchanges+int(call[len('tool-'):])-1
            else:raise ValueError('closed I native slot')
            width=self.investigation_exchanges+self.investigation_tool_slots
            index=46+50*(1+self.f_reference_calls)+I_IDS.index(gid)*575*width+actor*width+offset
        need(self.row(index)['job']==job,'exact complete original job spelling and ordinal')
        return index
    def rows(self):
        for ordinal in range(len(self)):yield self.row(ordinal)
    def __iter__(self):
        for row in self.rows():yield row['job']


def job_roster(selection,phase):
    roster=JobRoster.from_selection(selection,phase)
    return list(roster.rows()),roster.census()


def path_selection(geometry,selected_slots,phase):
    closed(geometry,{'programme','run_id','store_root','output_parent','metadata_parent','profiles'})
    jobs,census=job_roster(selected_slots,phase);used=set()
    for row in jobs:
        p=row['runtime_profile'];used.update(p.values()if type(p)is dict else[p])
    need(set(geometry['profiles'])==used,'complete exact phase deployment profiles')
    return {**geometry,'jobs':jobs,'process_census':census}
