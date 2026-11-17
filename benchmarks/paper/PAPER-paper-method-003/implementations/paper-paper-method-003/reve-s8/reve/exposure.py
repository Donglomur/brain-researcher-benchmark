from .deadline import boundary
"""Operator-owned pre-label domains; taint belongs to developer/source ancestry."""
from .errors import require
from .objects import canonical,digest,fields


ROLES={'candidate_A','candidate_B','independent_reference','operator_historical_audit'}
PURPOSES={'R-paper','R-native','I-person','I-person-montage'}


class Exposure:
    def __init__(self,roster,ledger,guard=None):
        self.guard=guard
        if guard:guard()
        fields(roster,('schema','aliases','uncertain','person_of','recording_of','domains'))
        require(roster['schema']=='reve-private-domain-roster-v1','exposure schema')
        self.ledger=ledger;self.roster=roster;self.domains={};self.contexts={};self.artifacts={};self.grants=[];self.operation_grants={}
        self.aliases=roster['aliases'];self.uncertain=set(roster['uncertain'])
        self.person_of=roster['person_of'];self.recording_of=roster['recording_of']
        require(type(self.aliases) is dict and all(type(k) is str and type(v) is str for k,v in self.aliases.items()),'alias mapping')
        for row in roster['domains']:
            fields(row,('id','role','arm','purpose','profile','family','dataset','query_support_policy','query_events','query_people','allowed_labels','allowed_signals','source_access','prelabel_qualification','protected_calibration_pool'))
            require(row['id'] not in self.domains and row['role'] in ROLES and row['purpose'] in PURPOSES,'domain identity')
            require(row['family'] in {f'RV-{i:02d}' for i in range(1,14)},'family')
            require(row['arm'] in ('A','B','reference','operator'),'arm')
            if row['role']=='candidate_A':require(row['arm']=='A' and row['source_access']=='paper_only','A source access')
            if row['role']=='candidate_B':require(row['arm']=='B' and row['source_access']=='paper_and_code','B source access')
            self.domains[row['id']]=row
        require(self.domains,'empty exposure roster')
        self.roster_id=digest(canonical(roster))
        ledger.append('exposure_roster_sealed',{'sha256':self.roster_id,'domain_ids':list(self.domains)})

    @boundary
    def canon(self,values):
        require(all(v in self.aliases for v in values),'unresolved alias')
        require(not (set(values)&self.uncertain),'uncertain alias cannot establish clean exposure')
        return {self.aliases[v] for v in values}

    @boundary
    def conflict(self,labels,signals,consumer):
        d=self.domains[consumer]
        canonical_labels=self.canon(labels)
        require(all(x in self.person_of and x in self.recording_of for x in canonical_labels),'missing label biological ancestry')
        held_person=(d['purpose'] in ('I-person','I-person-montage') and d['family']!='RV-11' and
                     bool({self.person_of[x] for x in canonical_labels}&set(d['query_people'])))
        return bool(held_person or canonical_labels&self.canon(d['query_events']) or
                    not self.canon(signals)<=self.canon(d['allowed_signals']))

    @boundary
    def admit_context(self,identity,domain,source_access,parents,qualification,prior_labels=(),prior_signals=()):
        require(identity not in self.contexts,'context reuse')
        d=self.domains[domain]
        require(qualification==d['prelabel_qualification'] and qualification,'unqualified developer custody')
        require(source_access==d['source_access'],'source access class')
        labels=set(prior_labels);signals=set(prior_signals)
        for parent in parents:
            p=self.contexts[parent]
            require(p['source_access']==source_access,'cross-arm source context')
            labels.update(p['labels']);signals.update(p['signals'])
        require(not self.conflict(labels,signals,domain),'exposed developer ancestry')
        if d['family']=='RV-11':
            require(not self.canon(labels)&self.canon(d['protected_calibration_pool']),'few-shot common context contains target-person labels')
        value={'id':identity,'domain':domain,'source_access':source_access,'parents':list(parents),'labels':sorted(labels),'signals':sorted(signals),'sealed':False,'qualification':qualification,'case':None}
        self.contexts[identity]=value
        return self.ledger.append('context_admitted',value)

    @boundary
    def grant(self,context,labels,signals,kind):
        c=self.contexts[context];d=self.domains[c['domain']]
        require(not c['sealed'],'context frozen')
        require(kind in ('development','case_calibration','unlabelled'),'grant kind')
        require(self.canon(labels)<=self.canon(d['allowed_labels']),'label grant outside domain')
        require(self.canon(signals)<=self.canon(d['allowed_signals']),'signal grant outside domain')
        if d['family']=='RV-11':
            require(c['case'] is not None or not self.canon(labels)&self.canon(d['protected_calibration_pool']),'no BCIC labels in common RV11 context')
            if c['case'] is not None:require(set(labels)<=set(c['case']['calibration_events']),'cross-case labels')
        require(not self.conflict(labels,signals,c['domain']),'grant overlaps protected query')
        c['labels']=sorted(set(c['labels'])|set(labels));c['signals']=sorted(set(c['signals'])|set(signals))
        receipt=self.ledger.append('information_grant',{'context':context,'kind':kind,'labels':list(labels),'signals':list(signals),'complete_exposure':{'labels':c['labels'],'signals':c['signals']}})
        self.grants.append(receipt);return receipt

    @boundary
    def register_artifact(self,identity,context,parent_artifacts,kind,producer):
        require(identity not in self.artifacts,'artifact identity already registered')
        c=self.contexts[context];labels=set(c['labels']);signals=set(c['signals']);ancestors=set();feedback=c.get('feedback_exposed',False)
        if type(producer) is str and producer in self.operation_grants:
            g=self.operation_grants[producer];require(g['context']==context,'operation context mismatch')
            labels.update(g['labels']);signals.update(g['signals'])
        for name in parent_artifacts:
            self.admit_reuse(name,context)
            a=self.artifacts[name];labels.update(a['labels']);signals.update(a['signals']);ancestors.update(a['contexts']);feedback=feedback or a.get('feedback_exposed',False)
        ancestors.add(context)
        a={'id':identity,'context':context,'contexts':sorted(ancestors),'domain':c['domain'],'source_access':c['source_access'],'labels':sorted(labels),'signals':sorted(signals),'parents':list(parent_artifacts),'kind':kind,'producer':producer,'case':c['case'],'eligible':kind=='source','feedback_exposed':feedback}
        self.artifacts[identity]=a;self.ledger.append('artifact_exposure',a);return a

    @boundary
    def admit_inputs(self,operation_id,context,labels,signals,operation):
        require(operation_id not in self.operation_grants,'operation grant replay')
        c=self.contexts[context];d=self.domains[c['domain']]
        if operation in ('predict','scientific_report'):
            require(c['sealed'] and not labels,'query requires frozen method/state and no labels')
            require(self.canon(signals)<=self.canon(d['allowed_signals']),'query signal outside view')
        else:
            self.grant(context,labels,signals,'case_calibration' if operation=='calibrate_case' else ('development' if labels else 'unlabelled'))
        g={'context':context,'labels':list(labels),'signals':list(signals),'operation':operation}
        self.operation_grants[operation_id]=g
        return self.ledger.append('operation_input_grant',{'operation_id':operation_id,**g})

    @boundary
    def admit_reuse(self,identity,consumer_context):
        a=self.artifacts[identity];c=self.contexts[consumer_context]
        require(a['eligible'],'incomplete/failed product cannot be reused')
        require(not a.get('feedback_exposed',False),'post-grading feedback artifact cannot become a blind learning input')
        old=self.domains[a['domain']];new=self.domains[c['domain']]
        require(old['role']==new['role'] and old['arm']==new['arm'],'cross-role/arm artifact reuse')
        require(old['purpose']==new['purpose'] and a['source_access']==c['source_access'],'purpose/source reuse')
        require(not self.conflict(a['labels'],a['signals'],c['domain']),'artifact ancestry contamination')
        if a['case'] is not None:require(c['case']==a['case'],'cross-draw case state')
        if new['family']=='RV-11' and c['case'] is None:require(not self.canon(a['labels'])&self.canon(new['protected_calibration_pool']),'fewshot source must be target-label clean')
        return self.ledger.append('reuse_admitted',{'producer':identity,'original_process':a['producer'],'consumer_context':consumer_context,'roster':self.roster_id})

    @boundary
    def close_products(self,identities):
        require(all(x in self.artifacts and self.artifacts[x]['kind']=='product' and not self.artifacts[x]['eligible'] for x in identities),'product closure replay')
        for identifier in identities:self.artifacts[identifier]['eligible']=True
        return self.ledger.append('product_exposure_closed',{'identities':list(identities)})

    @boundary
    def freeze(self,context):
        c=self.contexts[context];require(not c['sealed'],'already frozen');c['sealed']=True
        return self.ledger.append('context_frozen',c)

    @boundary
    def case_child(self,identity,parent,domain,case):
        p=self.contexts[parent];d=self.domains[domain]
        fields(case,('id','person','shots','draw','method','calibration_events','query_events','universe'))
        require(p['sealed'] and self.domains[p['domain']]['family']==d['family']=='RV-11','case parent must be frozen RV11')
        require(not self.canon(p['labels'])&self.canon(d['protected_calibration_pool']),'case parent target-label taint')
        require(len(case['universe'])==len(set(case['universe']))==288,'fewshot full universe')
        cal=set(case['calibration_events']);query=set(case['query_events'])
        require(len(cal)==2*case['shots'] and len(query)==288-2*case['shots'] and not cal&query and cal|query==set(case['universe']),'fewshot support partition')
        require(set(d['query_events'])==query and set(d['allowed_labels'])==cal,'case-domain grant binding')
        self.admit_context(identity,domain,p['source_access'],[parent],d['prelabel_qualification'])
        self.contexts[identity]['case']=case
        return self.ledger.append('case_child_created',{'id':identity,'parent':parent,'case':case})

    @boundary
    def compatible_group(self,contexts):
        for a in contexts:
            for b in contexts:
                c=self.contexts[a];d=self.contexts[b]
                da=self.domains[c['domain']];db=self.domains[d['domain']]
                require((da['role'],da['arm'],da['purpose'],c['source_access'])==(db['role'],db['arm'],db['purpose'],d['source_access']),'incompatible roles')
                require(not self.conflict(c['labels'],c['signals'],d['domain']),'ordered-pair conflict')
        return self.ledger.append('domain_group_admitted',{'contexts':list(contexts),'roster':self.roster_id})
