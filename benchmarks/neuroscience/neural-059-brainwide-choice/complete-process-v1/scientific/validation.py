"""Chronological full-grid validation journal. Trusted source capability, not host authority."""
import hashlib
import json
from copy import deepcopy
from .contracts import need,canonical,pin,probability,CONDITIONS,STATUS
from .io import Journal

def stage_digest(snapshot):
    return hashlib.sha256(json.dumps(snapshot,sort_keys=True,separators=(',',':'),ensure_ascii=True,
                                    allow_nan=False).encode()).hexdigest()

class ValidationPanel:
    def __init__(self,session,conditions,journal,project_case):
        need(type(journal) is Journal,'actual owned validation journal required')
        need(tuple(conditions) in (CONDITIONS,('SHN','SBHN')),'complete selected matched validation conditions')
        self._session=deepcopy(session);self.conditions=tuple(conditions);self.journal=journal;self.project=project_case
        self._cases=[c for c in self._session['cases'] if c['split']=='val']
        need([c['ordinal'] for c in self._cases]==sorted(c['ordinal'] for c in self._cases),'validation original chronology')
        self.expected={(f,c) for f in ('L','H') for c in self.conditions}
        self.stages={};self.position=0;self.pending=None;self.records=[];self.previous=None
        self.sealed=None;self.failed=None;self.queries={}

    def register(self,stage):
        need(self.position==0 and self.pending is None and self.sealed is None and not self.records,
             'all train-only stages registered before validation')
        snapshot=deepcopy(stage['snapshot']);ident=stage_digest(snapshot)
        key=(snapshot['family'],snapshot['condition'])
        need(key in self.expected and key not in self.stages and stage['stage_identity']==ident,
             'exact unique candidate stage identity')
        need(snapshot['session_id']==self._session['session_id'],'stage/source session')
        candidates=snapshot['candidates'];n=3 if key[0]=='L' else 12
        need(len(candidates)==n and [x['index'] for x in candidates]==list(range(n)),
             'full fixed candidate grid before validation')
        self.stages[key]={'snapshot':snapshot,'identity':ident};self.queries[key]=[]

    def _stage(self,stage):
        snap=stage['snapshot'];key=(snap['family'],snap['condition'])
        need(key in self.stages and stage['stage_identity']==stage_digest(snap)==self.stages[key]['identity']
             and snap==self.stages[key]['snapshot'],'unchanged registered stage')
        return key

    def next_case(self):
        need(self.failed is None and self.sealed is None and self.pending is None,'validation pending/failed/closed')
        need(set(self.stages)==self.expected,'complete both-family matched panel before first view')
        if self.position==len(self._cases):return None
        case=self._cases[self.position];prior=case.get('prior_case_id')
        if case.get('history_available') and any(x['case_id']==prior for x in self._cases):
            need(any(x['case_id']==prior for x in self.records),'previous scored validation history must commit')
        self.pending={'case':case,'views':{},'observations':{}}
        return case['case_id']

    def current_view(self,stage):
        key=self._stage(stage)
        need(self.pending is not None and self.failed is None,'current validation case required')
        need(key not in self.pending['observations'],'stage cannot revisit committed current observation')
        view=self.project(deepcopy(self.pending['case']),key[1],include_label=False)
        need(type(view) is dict and 'y' not in view,'validation is y-free')
        old=self.pending['views'].setdefault(key,deepcopy(view));need(old==view,'fixed current view')
        return deepcopy(view)

    def submit(self,stage,observations):
        key=self._stage(stage);need(self.pending is not None and key in self.pending['views'],'view first')
        need(key not in self.pending['observations'],'one candidate panel per stage/case')
        expected=self.stages[key]['snapshot']['candidates']
        need(type(observations) is list and len(observations)==len(expected),'all fixed candidates captured')
        for actual,want in zip(observations,expected):
            need(actual['index']==want['index'] and actual['config']==want['config'] and
                 actual['parameter_identity']==want['parameter_identity'],'candidate/config/parameter capture join')
            if want['status']=='available':
                need(actual['status']=='available','available candidate must capture prediction or fail')
                probability(actual['p'])
            else:need(actual['status']=='unavailable' and actual['p'] is None,'explicit unavailable candidate disposition')
        self.pending['observations'][key]=deepcopy(observations)

    def commit_case(self):
        need(self.pending is not None and self.failed is None,'current healthy validation case')
        try:
            need(set(self.pending['observations'])==self.expected,'entire candidate/family/condition panel before advance')
            case=self.pending['case']
            panels=[{'family':f,'condition':c,'stage_identity':self.stages[(f,c)]['identity'],
                     'view':self.pending['views'][(f,c)],'candidates':self.pending['observations'][(f,c)]}
                    for f,c in sorted(self.expected)]
            record={'kind':'validation_panel','status':STATUS,'session_id':self._session['session_id'],
                'source_identity':self._session['source_identity'],'unit_ids':self._session['unit_ids'],
                'case_id':case['case_id'],'ordinal':case['ordinal'],'prior_case_id':case.get('prior_case_id'),
                'sequence':self.position,'previous':self.previous,'panels':panels}
            raw=canonical(record);ack=self.journal.append(raw);need(ack==pin(raw),'exact durable validation ACK')
            for key,view in self.pending['views'].items():self.queries[key].append(deepcopy(view))
            self.records.append({**record,'ack':ack});self.previous=ack;self.position+=1;self.pending=None
            return deepcopy(ack)
        except BaseException as error:
            self.failed={'type':type(error).__name__,'error':str(error),'position':self.position}
            raise

    def seal(self):
        need(self.failed is None and self.pending is None and self.position==len(self._cases),
             'complete chronological panel before labels')
        need(set(self.stages)==self.expected,'complete registered grid even with zero validation support')
        need(self.sealed is None,'one validation seal')
        # Explicit terminal record also covers an empty validation census.
        record={'kind':'validation_complete','session_id':self._session['session_id'],
                'case_ids':[x['case_id'] for x in self._cases],'last_panel':self.previous,
                'stages':{f+':'+c:self.stages[(f,c)]['identity'] for f,c in sorted(self.expected)}}
        need(self.journal.append(canonical(record))==pin(record),'exact terminal validation receipt')
        self.sealed={'completion':pin(record),'journal':self.journal.seal()}
        return deepcopy(self.sealed)

    def released(self,stage):
        key=self._stage(stage);need(self.sealed is not None and self.failed is None,'sealed validation before label release')
        views=deepcopy(self.queries[key]);need(len(views)==len(self._cases),'complete retained validation views')
        labels=[]
        for view,case in zip(views,self._cases):
            need(view['case_id']==case['case_id'],'exact original validation label inverse')
            labels.append({'case_id':case['case_id'],'y':case['y']});view['y']=case['y']
        transcript=[]
        for record in self.records:
            one=next(x for x in record['panels'] if (x['family'],x['condition'])==key)
            transcript.append({'case_id':record['case_id'],'view':deepcopy(one['view']),
                               'candidates':deepcopy(one['candidates']),'whole_panel_ack':record['ack']})
        return {'labels':labels,'labelled_views':views,'transcript':transcript,
                'validation_identity':deepcopy(self.sealed),'stage_identity':stage['stage_identity']}
