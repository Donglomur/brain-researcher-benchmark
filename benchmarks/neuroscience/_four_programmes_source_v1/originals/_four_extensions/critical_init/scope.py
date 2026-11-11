"""Immutable full support; source gaps cannot shrink the programme."""
from pathlib import Path
from .custody import parse, read_pin, pin, encode, need
from .guard import distinct, RequiredUnscorable

NAMES=('PANEL_OBLIGATIONS.json','FULL_SUPPORT.json','POPULATION_CONTRACT.json',
       'PROGRAMME_AND_METRICS.json','REQUIRED_GATES.json','SOURCE_CONFLICTS.json')
class Scope:
    def __init__(self, root, bindings, budget):
        self.root=Path(root);self.bindings=bindings
        self.documents={n:parse(read_pin(root,bindings[n],1_048_576,budget))for n in NAMES}
        self.panels=self.documents[NAMES[0]]['rows']
        self.panel_ids=[r['id']for r in self.panels]
        distinct(self.panel_ids);need(len(self.panel_ids)==76,'all76 published panels')
        self.support=self.documents['FULL_SUPPORT.json']
        self.sessions=self.support['core29']['sessions']
        need(len(self.sessions)==29 and len({s['session_id']for s in self.sessions})==29,'all29 source sessions')
        self.populations=self.documents['POPULATION_CONTRACT.json']
        self.gates=self.documents['REQUIRED_GATES.json']['items']
        self.stages=self.documents['PROGRAMME_AND_METRICS.json']['stages']
        self.conflicts=self.documents['SOURCE_CONFLICTS.json']['items']
        need(len(self.gates)==len(self.stages)==len(self.conflicts)==17,'complete17 gates/stages/conflicts')
        self.digest=pin(encode({k:bindings[k]for k in NAMES}))['sha256']
    def endpoint_population(self, endpoint, variant, invocation=None):
        row=next((r for r in self.populations['endpoints']if r['endpoint']==endpoint),None)
        need(row is not None,'known exact population endpoint')
        if variant=='held_author_source':return row['literal_held_code_session_ids']
        if variant=='corrected_scientific':return row['common_corrected_scientific_session_ids']
        if variant=='paper_independent':
            if not invocation or invocation.get('adjudicated_endpoint')!=endpoint:
                raise RequiredUnscorable('G11','Actual published endpoint population not adjudicated',row)
            members=distinct(invocation['session_ids'])
            need(set(members)<=set(s['session_id']for s in self.sessions),'source-bound adjudication')
            return members
        raise RequiredUnscorable('G15','Prospective endpoint population must be independently frozen')
    def whole_plan(self, declared):
        """A full plan includes every original panel/cell disposition, not just executable rows."""
        need(set(declared['panels'])==set(self.panel_ids),'complete76 panel mapping')
        need(declared['core_sessions']==[s['session_id']for s in self.sessions],'full29 core identities and order')
        need(declared['facemap_sessions']==16 and declared['facemap_mice']==12,'original fullFacemap count')
        need(declared['external_task_sessions']==6,'all6 external original task sessions')
        need(set(declared['stages'])=={r['id']for r in self.stages},'full17 process stages')
        need(set(declared['conflicts'])=={r['id']for r in self.conflicts},'all17 scientific conflicts')
        jobs=declared['jobs'];distinct([j['id']for j in jobs])
        jobids={j['id']for j in jobs}
        for panel,entry in declared['panels'].items():
            need(entry['status'] in ('bound','required_unscorable'),'typed panel disposition')
            if entry['status']=='bound':
                need(entry['jobs'] and set(entry['jobs'])<=jobids,'actual producer jobs for every bound panel')
            else:need(entry.get('gate') and entry.get('reason'),'unavailable original remains explicit')
        need(declared['native_missing_roles_preserved'] is True,'missing native obligations not erased')
        return {'plan_digest':pin(encode(declared)),'complete_scope':True,
                'executable':all(x['status']=='bound'for x in declared['panels'].values()),
                'scientifically_qualified':False}

