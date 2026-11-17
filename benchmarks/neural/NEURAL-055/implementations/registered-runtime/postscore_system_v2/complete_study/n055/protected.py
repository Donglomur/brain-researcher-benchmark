"""Target-last original grading and full scientific reporting.

All scientific functions are invoked only by a separately qualified operator
after actual whole-campaign custody. BUILD ONLY controls poison these providers.
"""
from pathlib import Path
from .common import require,keys,capture,parse,encoded,sha,relative
from .registry import PEOPLE,token,VALID
from . import reporting

def scientific_subject(plan,source,inputs,programmes):
    return {'schema':'neural055-scientific-authorization-subject-v1',
            'runtime_source':source.identity,'submitted_source':programmes.subject,
            'input_index':inputs.identity,'protected_panel':plan['protected_panel'],
            'paired_schedule':plan['paired_schedule'],'complete_cells':sha(encoded(plan['cells'])),
            'limits':plan['limits'],'phase_limits':plan['phase_limits'],'policy':plan['policy'],
            'resource_policy':plan['resource_policy'],
            'numerical_contract':'original_grade_scorer_plus_registered_exploratory_report'}

class Protected:
    def __init__(self,plan,operator_root,source,inputs,programmes,collection,banks,authority,journal,budget,postscore_context=None):
        self.plan=plan;self.root=Path(operator_root);self.source=source;self.inputs=inputs;self.programmes=programmes
        self.collection=collection;self.banks=banks;self.authority=authority;self.journal=journal;self.budget=budget
        self.original_case_reports={};self.original_panel_reports={};self.outcomes={};self.targets={}
        self.read_records=[];self.numerical_calls=[];self.completed=False;self.original_report=None
        self.graded_terminals={};self.graded_panels=[]
        self.postscore_context=postscore_context
    def boundary(self,stage):
        self.collection.require_current_barrier();self.programmes.unchanged()
        require(not self.budget.unknown,'unknown physical resource consumption forbids protected admission')
        self.budget.check('protected:'+stage)
    def selected_read(self,path,expected,role,cap):
        self.boundary('before '+role);p=Path(path)
        d=dict(path=p.name,bytes=expected['bytes'],sha256=expected['sha256'],mode=oct(p.stat().st_mode&0o777),role=role)
        raw=capture(p.parent,d,self.budget,cap)
        self.read_records.append({'role':role,'bytes':len(raw),'sha256':sha(raw)})
        self.boundary('after '+role);return raw
    def run(self):
        self.boundary('authorization')
        subject=scientific_subject(self.plan,self.source,self.inputs,self.programmes)
        self.authority.verify(self.plan['protected_scoring_authority'],'protected_numerical_grading',subject)
        self.boundary('after independent grading authority')
        # Revalidate every admissible full prediction before any target descriptor
        # or body is opened, not merely the next successful panel.
        interface=self.source.legacy_module('public/interface.py')
        for c in self.collection.expected:
            ident=token(c);terminal=self.collection.terminals[ident]
            if terminal['status'] not in VALID:continue
            d=self.collection.predictions[ident];case=self.inputs.rows[c['outer_person']]['case']
            raw=self.selected_read(d['path'],d,'committed_prediction',4194304)
            p=interface.decode_json(raw);interface.validate_prediction(case,p,row_sum_abs_tolerance=1e-6)
            require(p==d['value'],'same original committed full prediction')
            self.boundary('whole public prediction validation')
        public=self.inputs.index['public_panel'];public_path=Path(public['path'])
        public_raw=self.selected_read(public_path,public,'complete_public_panel',1048576)
        pub=parse(public_raw);require(pub['schema']=='neural055-public-panel-v1' and len(pub['cases'])==10,'original complete public panel')
        case_by_id={r['case']['case_id']:r for r in self.inputs.rows.values()}
        cases={}
        for d in pub['cases']:
            raw=self.selected_read(public_path.parent/str(relative(d['path'])),d,'original_public_case',1048576)
            c=interface.validate_case(parse(raw));require(c['case_id'] in case_by_id and c==case_by_id[c['case_id']]['case'],'exact original public case')
            require(c['case_id'] not in cases,'unique public cases');cases[c['case_id']]=c
        require(len(cases)==10,'all original public cases')
        self.boundary('all public predictions valid before first private open')
        # Numerical products populate separate report copies. Original barrier
        # subjects remain immutable throughout every later target/score call.
        self.graded_terminals={k:parse(encoded(v)) for k,v in self.collection.terminals.items()}
        self.graded_panels=parse(encoded(self.collection.collections))
        for panel in self.graded_panels:
            panel['cells']=[self.graded_terminals[token(t['cell_key'])] for t in panel['cells']]
        private_d=self.plan['protected_panel'];private_path=self.root/str(relative(private_d['path']))
        private_raw=capture(self.root,private_d,self.budget,1048576)
        private=parse(private_raw)
        keys(private,('schema','cases'))
        require(private['schema']=='neural055-private-panel-v1' and set(private['cases'])==set(cases),'same exact protected ten-case panel')
        grade=self.source.legacy_module('private/grade.py')
        original_read=grade.read_regular;original_descriptor=grade.descriptor_read
        selected={str(public_path):(public,'complete_public_panel')}
        selected.update({str(public_path.parent/str(relative(d['path']))):(d,'original_public_case') for d in pub['cases']})
        selected[str(private_path)]=(private_d,'protected_panel')
        for case_id,d in private['cases'].items():
            require(set(d)=={'path','bytes','sha256'},'closed protected target descriptor')
            path=private_path.parent/str(relative(d['path']))
            require(str(path) not in selected,'no protected/source path role alias')
            selected[str(path)]=(d,'protected_target')
        def read_regular(path,limit):
            p=Path(path);require(str(p) in selected,'only independently selected original grading input')
            d,role=selected[str(p)];return self.selected_read(p,d,role,limit)
        def descriptor_read(root,d,limit):
            require(type(d)is dict and set(d)=={'path','bytes','sha256'},'unchanged original grading descriptor')
            path=Path(root)/str(relative(d['path']))
            require(str(path) in selected and selected[str(path)][0]['bytes']==d['bytes'] and selected[str(path)][0]['sha256']==d['sha256'],'exact original descriptor join')
            return read_regular(path,limit)
        grade.read_regular=read_regular;grade.descriptor_read=descriptor_read
        try:
            for panel in self.graded_panels:
                key=token(panel['panel_key']);children=panel['cells'];complete=all(t['status'] in VALID for t in children)
                if complete:
                    folder=self.journal.root/('grade-'+key);folder.mkdir(mode=0o700)
                    for t in children:
                        c=t['cell_key'];ident=token(c);d=self.collection.predictions[ident]
                        raw=self.selected_read(d['path'],d,'original_panel_prediction',4194304)
                        target=folder/(t['public_case_identity']+'.json')
                        record=self.journal.write(str(target.relative_to(self.journal.root)),raw)
                        selected[str(target)]=({'path':target.name,'bytes':len(raw),'sha256':sha(raw)},'original_panel_prediction')
                    self.boundary('before unchanged original full-panel grader')
                    result=grade.grade(public_path,folder,private_path)
                    self.numerical_calls.append({'kind':'original_grade.grade','panel':panel['panel_key']})
                    self.boundary('after unchanged original full-panel grader')
                    self.original_panel_reports[key]=result
                    for report in result['cases']:self.original_case_reports[(key,report['case_id'])]=report
                elif self.plan['policy']['diagnostic_incomplete_scoring']:
                    for t in children:
                        if t['status'] not in VALID:continue
                        c=t['cell_key'];d=self.collection.predictions[token(c)];case=cases[t['public_case_identity']]
                        self.boundary('before original incomplete-panel case diagnostic')
                        result=grade.score_case(case,d['value'],lambda case=case:parse(descriptor_read(private_path.parent,private['cases'][case['case_id']],1048576)),
                                                row_sum_abs_tolerance=1e-6,independent_tie_order=case['candidate_ids'],log_loss_policy='natural_log_no_clipping')
                        self.numerical_calls.append({'kind':'original_grade.score_case_incomplete_diagnostic','cell':c})
                        self.boundary('after original incomplete-panel case diagnostic')
                        self.original_case_reports[(key,case['case_id'])]=result
                for t in children:
                    ident=token(t['cell_key']);case_id=t['public_case_identity']
                    report=self.original_case_reports.get((key,case_id))
                    if report is None:continue
                    t['numerical_disposition']={'status':'scored' if complete else 'incomplete_panel_diagnostic','original':report}
                    t['resource_dispositions']['numerical_availability']=t['numerical_disposition']['status']
                    case=cases[case_id]
                    if case_id not in self.targets:self.targets[case_id]=parse(descriptor_read(private_path.parent,private['cases'][case_id],1048576))
                    self.boundary('before prospective per-query diagnostics')
                    self.outcomes[ident]=reporting.query_outcomes(case,self.collection.predictions[ident]['value'],self.targets[case_id])
                    self.numerical_calls.append({'kind':'prospective_query_outcomes','cell':t['cell_key']})
                    self.boundary('after prospective per-query diagnostics')
                summary=panel['summary']
                if complete:
                    summary['primary_numerical_disposition']={'status':'scored','original':self.original_panel_reports[key]['panel']}
                elif self.plan['policy']['diagnostic_incomplete_scoring']:
                    valid=[r for (k,_),r in self.original_case_reports.items() if k==key]
                    correct=sum(r['assignment_correct'] for r in valid);missing=2000-200*len(valid)
                    summary['diagnostic_bounds_disposition']={'status':'incomplete_panel_bounds','lower':correct/2000,'upper':(correct+missing)/2000,'correct_completed':correct,'unavailable_queries':missing,'valid_panel_score':False}
        finally:
            grade.read_regular=original_read;grade.descriptor_read=original_descriptor
        self.boundary('before protected common pairing and schedules')
        ps=self.plan['paired_schedule']
        self.authority.verify(ps['qualification'],'paired_source_image_schedule',{'source':self.source.identity,'input':self.inputs.identity,'pairing':ps['pairing'],'schedule':ps['schedule'],'alignment':ps['alignment'],'pre_exposure':True})
        pairing=parse(capture(self.root,ps['pairing'],self.budget,16777216));schedule=parse(capture(self.root,ps['schedule'],self.budget,67108864))
        contrast=parse(self.source.bodies['contracts/CONTRASTS.json'])
        self.boundary('before full paired uncertainty')
        paired=reporting.paired_report(self.plan['system'],self.collection.expected,self.graded_terminals,
                                       self.outcomes,pairing,schedule,contrast,{},self.boundary)
        from .resource_policy import annotate_contrasts
        annotate_contrasts(paired,contrast,self.graded_terminals,self.plan['system'],self.budget.resource_policy)
        self.boundary('after full paired uncertainty')
        report={'schema':'neural055-complete-protected-report-v1','source':self.source.identity,
                'resource_policy':self.budget.resource_policy,'resource_interpretation':paired['resource_interpretation'],
                'cells':[self.graded_terminals[token(c)] for c in self.collection.expected],
                'panels':[x['summary'] for x in self.graded_panels],
                'phase_envelopes':[p for c in self.collection.expected for p in self.collection.phases[token(c)]],
                'paired':paired,'reference_banks':[self.banks.document(r) for r in self.banks.rows.values()],
                'independent_authority_uses':self.authority.used,'exposure':self.plan['exposure_declaration'],
                'original_physical_and_separate_attributable_costs':self.budget.snapshot(),
                'open_scientific_gates':30,'scientific_qualification_claim':False,
                'numerical_calls':self.numerical_calls,'private_per_query_targets_and_outcomes_omitted':True}
        self.original_report=report
        # Durable numerical evidence precedes optional interpretation. Report
        # failure does not change any committed prediction or numerical result.
        numerical=self.journal.json('PROTECTED_NUMERICAL_REPORT.json',report)
        self.boundary('after original numerical report publication')
        from .postscore_v2 import make_handoff
        handoff=make_handoff(self.plan,self.source,self.root,self.authority,self.journal,self.budget,self.postscore_context)
        self.interpretation_handoff=handoff
        disposition=handoff.run(paired,{'path':numerical['path'],'bytes':numerical['observed_bytes'],'sha256':numerical['sha256']})
        self.journal.carrier.retain(handoff)
        report['paired']['interpretation']=reporting.interpretation(disposition['records'])
        report['postscore_interpretation']=disposition
        report['original_numerical_publication']=numerical
        publication=self.journal.json('PROTECTED_REPORT.json',report)
        self.boundary('after complete report publication')
        self.completed=True
        return publication

