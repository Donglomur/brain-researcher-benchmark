"""Full accepted scope and strict future execution plans; no hidden fit-count guesses."""
from pathlib import Path
import itertools
from .objects import Reader,decode,digest,canonical,fields,positive
from .errors import require

CONTRACTS=Path(__file__).absolute().parent.parent/'contracts'


class Scope:
    def __init__(self,root=CONTRACTS,guard=None):
        self.guard=guard
        if guard:guard()
        root=Path(root)
        self.reader=Reader(root,4*1024**2,32,guard=guard)
        self.panel=decode(self.reader.capture('PANEL.json'))
        self.obligations=decode(self.reader.capture('CLAIM_OBLIGATIONS.json'))
        self.operators=decode(self.reader.capture('OPERATORS_PRODUCTS.json'))
        self.gates=decode(self.reader.capture('GATES.json'))
        self.controls=decode(self.reader.capture('FUTURE_CONTROLS.json'))
        self.discrepancies=decode(self.reader.capture('SOURCE_DISCREPANCIES.json'))
        self.history=decode(self.reader.capture('PUBLIC_PROVENANCE.json'))
        self.sources=decode(self.reader.capture('PUBLIC_SOURCE_INDEX.json'))
        self.existing=decode(self.reader.capture('EXISTING_SCOPE.json'))
        self.fixed_reference=decode(self.reader.capture('FIXED_REFERENCE_SOURCE.json'))
        if guard:guard()
        self.ids=[r['id'] for r in self.panel['cases']]
        require(len(self.ids)==len(set(self.ids))==2144,'full legacy case census')
        require(digest(canonical(self.ids))==self.existing['case_id_order_sha256'],'original case order')
        require(len(self.obligations['obligations'])==54 and len(self.obligations['source_families'])==13,'full obligations')
        require(len(self.operators['stages'])==22 and len(self.panel['datasets'])==10,'full stage/dataset scope')
        require(len(self.gates['gates'])==30 and len(self.controls['controls'])==50 and len(self.discrepancies['findings'])==37,'scope gates')
        require(self.history['private_history_records_not_distributed']==155 and len(self.sources['ordinary_author_files'])==87,'declared private history count and complete public author identity roster; not proof of private history')
        fs=[r for r in self.panel['cases'] if r['family']=='few_shot']
        tuples={(x['configuration']['person_slot'],x['configuration']['shots_per_class'],x['configuration']['draw_slot'],x['method']) for x in fs}
        require(tuples==set(itertools.product(range(1,10),(1,2,5,10,20),range(20),('REVE-Base-PT','REVE-Base-XFT'))),'full fewshot tuple set')
        self.stage={r['id']:r for r in self.operators['stages']}
        self.identity=digest(canonical({'panel':digest(canonical(self.panel)),'obligations':digest(canonical(self.obligations)),'operators':digest(canonical(self.operators))}))

        if guard:guard()

    def contrast_roster(self):
        return [{'arm':a,'dataset':d['id'],'condition':c,'reference':ref}
                for a,d,c,ref in itertools.product(('A','B'),self.panel['datasets'],self.panel['prospective_conditions'],self.panel['prospective_control_methods'])]

    def validate_plan(self,plan,production=True):
        fields(plan,('schema','scope','programmes','jobs','required_products','run_rosters','missing_ISRUC_mapping','reference_policies','confirmatory','resources','scientific_profiles'),('prediction_groups','case_profile_roster','support_admission','scientific_reductions','reference_run_bindings'))
        require(plan['schema']=='reve-complete-execution-plan-v1' and plan['scope']==self.identity,'plan scope')
        require(plan['confirmatory']==self.contrast_roster() and len(plan['confirmatory'])==160,'fixed complete A/B contrast union')
        require(set(plan['scientific_profiles'])>={'R-paper','R-native','I-person','I-person-montage'},'all scientific purposes')
        if production:
            require(len(plan['missing_ISRUC_mapping'])==2,'two missing ISRUC product mappings still require selection')
            require({r['method'] for r in plan['missing_ISRUC_mapping']}=={'DeepSleepNet','USleep'} and all(r['authority'] for r in plan['missing_ISRUC_mapping']),'selected ISRUC mapping')
        jobs=plan['jobs'];by_id={x['id']:x for x in jobs}
        require(len(by_id)==len(jobs) and jobs,'unique job census')
        seen=set()
        for j in jobs:
            fields(j,('id','programme','stage','operation','domain','context','source','inputs','parent_jobs','expected_outputs','resource_limit','case','run','reuse','payload'))
            require(j['stage'] in self.stage and set(j['parent_jobs'])<=seen,'job DAG order')
            require(j['operation']==self.stage[j['stage']]['operation'],'stage operation identity')
            require(j['expected_outputs'] and set(j['expected_outputs'])<=set(plan['required_products']),'job products')
            seen.add(j['id'])
        owners={}
        for j in jobs:
            for output in j['expected_outputs']:
                require(output not in owners,'multiple product producers');owners[output]=j['id']
        require(set(owners)==set(plan['required_products']),'complete product producers')
        ancestors={}
        for j in jobs:
            ancestors[j['id']]=set(j['parent_jobs']).union(*(ancestors[x] for x in j['parent_jobs']))
            require(set(j['inputs'])<=set(owners) and all(owners[x] in ancestors[j['id']] for x in j['inputs']),'input must be a declared earlier producer ancestor')
        for name,spec in plan['required_products'].items():
            refs=list(spec.get('parent_states',[]))
            if spec['kind']=='prediction':refs.append(spec['state'])
            if spec['kind']=='soup':refs.extend([*spec['soup_members'],spec['soup_state']])
            require(all(x in owners and owners[x] in ancestors[owners[name]] for x in refs),'state/member dependency is not an earlier declared ancestor')
        if production:
            from .support import validate_support_plan
            validate_support_plan(plan,self)
            from .scientific_identity import validate_case_bindings
            validate_case_bindings(plan,self)
            from .reductions import validate_reduction_plan
            validate_reduction_plan(plan,self)
            from .references import validate_reference_bindings
            validate_reference_bindings(plan,self)
            from .fixed_reference import validate_fixed_reference_plan
            validate_fixed_reference_plan(plan,self)
            programme_ids=[x['id'] for x in plan['programmes']]
            require(len(programme_ids)==len(set(programme_ids)),'programme identity')
            candidate_arms={x['arm'] for x in plan['programmes'] if x['role']=='candidate'}
            require(candidate_arms=={'A','B'},'both candidate arms')
            require(any(x['role']=='reference' for x in plan['programmes']),'independent reference producers')
            require(len([p for p in plan['programmes'] if p['role']=='candidate'])==2,'one complete programme per candidate arm')
            for p in plan['programmes']:
                fields(p,('id','role','arm','families','case_ids','obligations'))
                require(p['role'] in ('candidate','reference') and p['arm'] in (('A','B') if p['role']=='candidate' else ('reference',)),'programme role/arm')
                require(set(p['families'])=={f'RV-{i:02d}' for i in range(1,14)},'whole-family programme')
                require(set(p['case_ids'])==set(self.ids),'whole legacy output roster')
                require(set(p['obligations'])=={f'O{i:02d}' for i in range(1,55)},'all scientific obligations')
            require(all(plan['run_rosters'].get(x['id']) for x in plan['programmes']),'qualified nonfewshot run roster missing')
            require(len(plan['reference_policies'])==80,'all 80 prospective independent reference families')
            require({x['stage'] for x in jobs}==set(self.stage),'all22 stages remain required')
            by_case={r['id']:r for r in self.panel['cases']}
            for programme in plan['programmes']:
                pp=[x for x in plan['required_products'].values() if x['programme']==programme['id']]
                require(set().union(*(set(x['obligations']) for x in pp))=={f'O{i:02d}' for i in range(1,55)},'obligation producer coverage')
                predictions=[x for x in plan['prediction_groups'].values() if x['programme']==programme['id'] and x['case_id'] in by_case]
                runs=plan['run_rosters'][programme['id']]
                actual={(x['case_id'],x['run'],x['purpose']) for x in predictions}
                profiles=plan['case_profile_roster'][programme['id']]
                require(set(profiles)==set(self.ids),'complete selected source-case scientific-purpose map')
                for case,entry in profiles.items():
                    fields(entry,('profiles','qualification'))
                    require(entry['qualification'] and entry['profiles'] and len(entry['profiles'])==len(set(entry['profiles'])) and set(entry['profiles'])<=set(plan['scientific_profiles']),'qualified source-purpose map, not inferred run multiplication')
                expected={(case,run,purpose) for case,row in by_case.items() for run in (['case_draw'] if row['family']=='few_shot' else runs) for purpose in profiles[case]['profiles']}
                require(actual==expected and len(predictions)==len(expected),'all original cases and qualified runs have actual prediction producers')
                require({x['kind'] for x in pp}>={'executable','method_plan','corpus','preprocessing','architecture','state','loss_trace','schedule_trace','soup','claim','resource','scope'},'nonprediction scientific products required')
            grade_jobs=[j for j in jobs if j['stage']=='S20']
            require(len(grade_jobs)==1,'one globally closed grader stage')
            scoring=grade_jobs[0]['payload']['scoring']
            from .predictions import validate_groups
            validate_groups(plan)
            predicted=set(plan['prediction_groups'])
            require({x['prediction'] for x in scoring}==predicted and len(scoring)==len(predicted),'full scoring roster covers every passive whole-case group')
            for row in scoring:
                fields(row,('prediction','target','purpose','programme','case_id','run'))
                group=plan['prediction_groups'][row['prediction']]
                require(all(row[k]==group[k] for k in ('purpose','programme','case_id','run')),'scoring cannot relabel actual group')
            require(len(grade_jobs[0]['payload']['comparisons'])==160,'all160 comparison recipes')
            audits=grade_jobs[0]['payload']['scientific_audits']
            need={k for k,v in plan['required_products'].items() if v['kind'] in ('loss_trace','schedule_trace','soup','corpus','preprocessing','architecture','state')}
            require({x['product'] for x in audits}==need and len(audits)==len(need),'all scientific products need independent selected audit routes')
            for row in plan['missing_ISRUC_mapping']:
                fields(row,('method','authority','products'))
                require(row['products'] and set(row['products'])<=set(plan['required_products']),'missing ISRUC actual product producers')
                require(all(plan['required_products'][x]['dataset']=='ISRUC' and plan['required_products'][x]['method']==row['method'] for x in row['products']),'ISRUC mapping cannot be a name-only claim')
            for p in plan['programmes']:
                for method in ('DeepSleepNet','USleep'):
                    require(any(v['programme']==p['id'] and v.get('dataset')=='ISRUC' and v.get('method')==method and v['kind']=='prediction' and v['case_id'] not in self.ids for v in plan['required_products'].values()),'two source products remain additional to all2144 legacy slots')
        return {'scope':self.identity,'plan':digest(canonical(plan)),'jobs':len(jobs),'products':len(owners),'production':production}
