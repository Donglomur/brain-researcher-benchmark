"""Collect all precommitted pair support, including failed outer lifetimes."""
from central_common import need,pin,capture,exact_json

ROLES=('reference','candidate_A','candidate_B')
class Products:
    def __init__(self,invocation):
        self.invocation=invocation;self.reopened=[];self.pairs=[];self.complete=True
        prepared=invocation.prepared;root=prepared['specification']['output_root']
        maximum=invocation.deployment['maximum_metadata_bytes'];meter=invocation.sources.meter
        validation=invocation.runtime.load('mintbench.validation')
        render=invocation.runtime.load('mintbench.report').render_markdown
        plan=prepared['request']['plan'];ids={c['id'] for c in plan['cases']}
        self.plan_sha256=validation.digest(plan)
        expected_campaigns=prepared['request']['campaigns'];self.expected_pair_count=len(expected_campaigns)
        self.outer=invocation.outer;self.block=None;self.failure=None
        def read(path,expected=None):
            support={'path':path,'state':'not_attempted','attempted':False}
            try:
                # An exhausted original closure reserve leaves explicit unattempted
                # support; it cannot erase records captured for preceding pairs.
                meter.tick('outer');support['attempted']=True
                raw,observed=capture(path,expected,meter,maximum=maximum,phase='outer')
                self.reopened.append(observed);support['capture']=observed
                value=exact_json(raw,maximum);support['state']='captured'
                return value,support
            except FileNotFoundError as error:
                support.update(state='absent',reason=type(error).__name__)
            except BaseException as error:
                support.update(state='invalid_or_unreadable' if support['attempted'] else 'not_attempted',
                    reason=type(error).__name__+': '+str(error)[:300],
                    capture_prefix=getattr(error,'central_capture_prefix',None))
            self.complete=False;return None,support
        def invalid(support,error):
            support.update(state='invalid',reason=type(error).__name__+': '+str(error)[:300]);self.complete=False
        expected=pin(validation.encoded(invocation.outer)+b'\n')
        outer,self.outer_support=read(root+'/outer-observation.json',expected)
        if self.outer_support['state']=='captured':
            try:
                need(outer==invocation.outer,'same returned and durably written outer observation')
                self.outer_support['state']='valid'
            except BaseException as error:invalid(self.outer_support,error)
        child=self.outer.get('child',{});diagnostics=child.get('diagnostics',{}).get('streams',{})
        complete_child=(child.get('natural_exit') is True and child.get('exit_code')==0
            and child.get('forced_termination') is False and child.get('group_absent') is True
            and child.get('streams_closed') is True and set(diagnostics)=={'out','err'}
            and all(x.get('complete_original_stream') is True for x in diagnostics.values()))
        outer_complete=self.outer.get('success') is True and complete_child and self.outer_support['state']=='valid'
        if not outer_complete:
            self.complete=False;self.failure='Original outer lifetime incomplete or failed; retained pair evidence does not imply complete coverage or scientific success.'
        block,self.block_support=read(root+'/block-result.json')
        if self.block_support['state']=='captured':
            try:
                need(type(block) is dict and len(block['pairs'])==len(expected_campaigns),'entire balanced block represented')
                for c,summary in zip(expected_campaigns,block['pairs']):
                    need(summary['pair']==c['schedule']['pair_id'] and summary['order']==c['schedule']['order'],'same selected pair and order')
                need(block['scientifically_qualified'] is False,'block cannot confer qualification')
                self.block=block;self.block_support['state']='valid'
                if block.get('complete_execution') is not True:self.complete=False
            except BaseException as error:invalid(self.block_support,error)
        for c in expected_campaigns:
            expected_pair={'pair':c['schedule']['pair_id'],'schedule':c['schedule'],
                'plan_sha256':self.plan_sha256,'campaign_sha256':validation.digest(c),'required_case_ids':sorted(ids)}
            final,final_support=read(c['output_root']+'/campaign-final.json')
            valid_final=False
            if final_support['state']=='captured':
                try:
                    need(type(final) is dict and final['plan_sha256']==self.plan_sha256 and final['schedule']==c['schedule'],'same complete plan and selected pair')
                    need(type(final['executions']) is list and type(final['reports']) is list,'original final lists')
                    need(all(x.get('role') in ROLES for x in final['executions']),'no unplanned role')
                    need(final.get('scientifically_qualified') is False,'final cannot confer qualification')
                    final_support['state']='valid';valid_final=True
                    if final.get('fatal') is not None:self.complete=False
                except BaseException as error:invalid(final_support,error)
            outcomes={};missing={};role_support={};reports={};rendered={}
            for role in ROLES:
                outcomes[role]=None;missing[role]=sorted(ids)
                rs={'execution':'not_observed','attempt_status':'unknown','required_case_count':len(ids)}
                role_support[role]=rs
                if valid_final:
                    try:
                        matches=[x for x in final['executions'] if x['role']==role]
                        need(len(matches)<=1,'one original execution per role and pair')
                        if not matches:
                            rs.update(execution='absent_from_final',attempt_status='not_recorded_in_final');self.complete=False;continue
                        outcome=matches[0]
                        need(outcome['plan_sha256']==self.plan_sha256,'same full role plan')
                        outputs=[x['case'] for x in outcome['outputs']];failed=[x['case'] for x in outcome['failures']]
                        need(len(outputs)==len(set(outputs)) and len(failed)==len(set(failed))
                             and not(set(outputs)&set(failed)) and set(outputs+failed)<=ids,'original role output/failure support')
                        outcomes[role]=outcome;missing[role]=sorted(ids-set(outputs+failed))
                        rs.update(execution='valid',attempt_status='recorded',
                            missing_case_ids=missing[role],failed_case_ids=failed)
                        if missing[role] or failed:self.complete=False
                    except BaseException as error:rs.update(execution='invalid',reason=type(error).__name__+': '+str(error)[:300]);self.complete=False
                else:self.complete=False
            # Fixed expected names, independent of final/block availability.
            for role in ('candidate_A','candidate_B'):
                report,support=read(c['output_root']+'/'+role+'-report.json')
                role_support[role]['report']=support
                if support['state']!='captured':continue
                try:
                    need(report['task']=='PAPER-paper-method-011' and report['plan_sha256']==self.plan_sha256 and len(report['modules'])==17,'whole original report identity')
                    need([m['module'] for m in report['modules']]==[m['module'] for m in plan['module_support']],'complete original module order')
                    need(report['scientific_qualification'] is False,'no report grants scientific qualification')
                    need(report['selected_and_realized_schedule']==c['schedule'],'same report pair schedule')
                    reports[role]=report;support['state']='valid'
                    if report['complete_artifact_coverage'] is not True:self.complete=False
                    try:rendered[role]=render(report);support['rendering']='complete'
                    except BaseException as error:
                        support['rendering']='invalid_or_unreadable';support['rendering_failure']=type(error).__name__+': '+str(error)[:300]
                        self.complete=False
                except BaseException as error:invalid(support,error)
            self.pairs.append({**expected_pair,'final':final if valid_final else None,'final_support':final_support,
                'final_failure':None if not valid_final else final.get('fatal'),
                'final_journal':None if not valid_final else final.get('journal'),
                'executions':outcomes,'missing_attempts':missing,'role_support':role_support,'reports':reports,'rendered':rendered})
        if not self.complete and self.failure is None:
            self.failure='One or more required artifacts, attempts, reports or block outcomes remain incomplete, failed, invalid, unreadable or unattempted.'
    def envelope(self,schema):
        return {'schema':schema,'outer':self.outer,'outer_support':self.outer_support,
            'block':self.block,'block_support':self.block_support,'expected_plan_sha256':self.plan_sha256,
            'expected_pair_count':self.expected_pair_count,'complete_observed_artifact_coverage':self.complete,
            'failure':self.failure,'scientific_qualification':False,'collection_pins':self.reopened}
    def pair_support(self,p):
        return {k:p[k] for k in ('pair','schedule','plan_sha256','campaign_sha256','required_case_ids','final_support','final_failure','final_journal','role_support','missing_attempts')}
    def reference(self):
        return {**self.envelope('motormint_reference_products_v2'),'pairs':[
            {**self.pair_support(p),'reference':p['executions']['reference']} for p in self.pairs],
            'missing_or_failed_preserved':not self.complete,'independent_reference_executed_here':False}
    def candidate(self):
        return {**self.envelope('motormint_paired_candidate_products_v2'),'pairs':[
            {**self.pair_support(p),'candidate_A':p['executions']['candidate_A'],'candidate_B':p['executions']['candidate_B']} for p in self.pairs],
            'whole_scope_required':True,'candidate_executed_here':False}
    def grade(self):
        return {**self.envelope('motormint_original_protected_assessments_v2'),'pairs':[
            {**self.pair_support(p),'reports':p['reports']} for p in self.pairs],
            'scientifically_qualified':False,'score_recomputed_here':False,'no_scalar_across_incompatible_estimands':True}
    def report(self):
        return {**self.envelope('motormint_central_report_views_v2'),'pairs':[
            {**self.pair_support(p),'reports':p['rendered'],'original_reports':p['reports']} for p in self.pairs],
            'full_scope':self.invocation.sources.manifest['scope'],'complete':self.complete}
