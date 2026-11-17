"""Complete concrete collection; no scientific finished-output callbacks."""
from pathlib import Path
import math
from core import need, encoded, pin, publish, fresh, describe_sealed
from artifacts import Artifacts
from journal import Journal
from provider import GlobalQuota
from transport import Transport
from investigator import Investigator
from reference_pipeline import References
from actor_pipeline import Actors
from records import Records
from bank import Bank
from views import packet
from schedule import graph, census


def raw_budget(b):
    return {'read_reserved':b.read_bytes,'write_reserved':b.write_bytes,'origin':b.origin,'deadline':b.deadline}


def phase_profile(job):
    k = job['kind']
    if k in ('reference_fit','reference_final_fit'): return 'reference_fit'
    if k == 'reference_select': return 'reference_select'
    if k in ('reference_inner_predict','reference_outer_predict','tool_bank'): return 'reference_predict'
    return 'global_author' if k == 'global_author' else 'case'


def collect(a, captured, budget, qualifications):
    journal = None; closed = False; current = None; completed = []; entered = []; setup = []
    transport = references = actors = phases = None; prepared = table = None; failure = None
    try:
        # Actual source, root, role, profile and immutable-bank qualification was
        # admitted before this entry; setup errors still retain every local cost.
        prepared, table = packet(a,budget)
        shape = census(table,a['modules'],a['cache'])
        proof = qualifications['resource_feasibility']['body']
        need(proof['census'] == shape and proof.get('complete_no_subset_plan') is True,
             'actual full census/resource profile join before workloads')
        bank = Bank(a,budget,prepared['manifest'])
        output = fresh(a['roots']['output'],budget); setup.append(str(output))
        reference = fresh(a['roots']['reference'],budget); setup.append(str(reference))
        for name in ('authors','actors','views','phases'):
            fresh(output/name,budget); setup.append(str(output/name))
        journal = Journal(output/'JOURNAL.jsonl',budget,a['resources']['journal_bytes'],a['resources']['event_bytes'])
        phases = Records(output/'phases',budget,a['resources']['record_bytes'],a['resources']['index_bytes'])
        # Only the actual fixed view plan selects training labels. Generic
        # admission/grading uses a stricter artifact reader excluding both label roots.
        artifacts = Artifacts(budget,[a['roots'][k] for k in ('source','output','reference','operator','store')],
                              a['roots']['targets'],[a['roots']['secrets']]); artifacts.gallery = bank
        transport = Transport(a,captured,budget,artifacts,journal.append,bank)
        quota = GlobalQuota(**a['provider_total'])
        investigator = Investigator(a,captured,budget,transport,artifacts,journal.append,quota)
        references = References(a,captured,budget,artifacts,transport,bank,prepared,table)
        actors = Actors(a,captured,budget,artifacts,transport,investigator,bank,prepared,table,references)
        for job in graph(table,a['modules'],a['cache']):
            current = job; profile = phase_profile(job); start = budget.tick()
            if profile in ('case','global_author'):
                cutoff = min(a['clock']['production_end'],start+a['provider_profiles'][profile]['seconds'])
            else:
                p = a['profiles'][profile]
                cutoff = min(a['clock']['production_end'],start+p['seconds']+p['retirement_seconds'])
            need(start < cutoff, 'positive complete phase allowance')
            journal.append({'kind':'phase_entered','identity':job['id'],'job':job,'profile':profile,
                            'entered_at':start,'cutoff':cutoff}); entered.append(job['id'])
            if job['kind'] == 'global_author':
                result = actors.author(job,cutoff)
            elif job['kind'] == 'actor_case':
                result = actors.case(job,cutoff)
            else:
                p = a['profiles'][profile]
                limits = {'native_cpu_ns':p['cpu_ns']+math.ceil(p['cpu_rate_ns']*p['qualified_enforcement_lag_seconds']),
                          'gpu_device_seconds':len(a['native_private']['gpu_ids'])*(p['seconds']+p['qualified_enforcement_lag_seconds'])}
                engine = transport.engines['private']; engine.begin_scope(job['id'],cutoff,limits)
                result = actors.tool(job) if job['kind'] == 'tool_bank' else references.invoke(job)
                result = {**result,'resources':engine.end_scope(job['id'])}
            budget.tick(cutoff)
            phases[job['id']] = result
            journal.append({'kind':'phase_completed','identity':job['id'],'record':phases.index[job['id']],'observed_end':budget.tick(cutoff)})
            if job['kind'] in ('global_author','actor_case'):
                journal.append({'kind':'episode_completed','identity':job['id'],'record':phases.index[job['id']]})
            completed.append(job['id']); current = None
        journal.close(); closed = True
        jp = describe_sealed(output/'JOURNAL.jsonl',a['resources']['journal_bytes'],budget)
        producer = {'schema':'neural049_complete_collection_v1','status':'complete','task':'NEURAL-049',
                    'source':captured['pin'],'authority':captured['authority_pin'],'original_origin':budget.origin,
                    'modules':a['modules'],'cache':a['cache'],'table':table,'packet':a['packet'],
                    'packet_metadata_costs':prepared['costs'],'view_helper_final_costs':prepared['_budget'].record(),'bank':bank.record(),
                    'census':shape,'phases':phases.index,'operations':transport.results.index,
                    'references':references.records.index,'actors':actors.results.index,'policies':actors.policies,
                    'journal':{'path':str(output/'JOURNAL.jsonl'),'pin':jp},'provider_costs':quota.record(),
                    'disposition':{'completed':completed,'failed':[],'entered_incomplete':[],'unentered':[]},
                    'costs_before_producer_publication':budget.record(),'scientific_qualification':None}
        raw = encoded(producer); need(len(raw) <= a['resources']['producer_bytes'], 'complete producer metadata cap')
        pp = publish(output/'PRODUCER.json',raw,budget,readonly=True); budget.tick()
        return {'status':'collected','producer':{'path':str(output/'PRODUCER.json'),'pin':pp},'source':captured['pin']}
    except BaseException as error:
        later = []
        if transport is not None:
            for engine in transport.engines.values():
                try: engine.abort_scope()
                except BaseException as secondary: later.append({'stage':'scope_failure_record','error':type(secondary).__name__})
        if journal is not None and not closed:
            try:
                journal.append({'kind':'study_failed','phase':None if current is None else current['id'],'error':type(error).__name__})
            except BaseException as secondary: later.append({'stage':'journal_failure_append','error':type(secondary).__name__})
            try: journal.close(); closed = True
            except BaseException as secondary: later.append({'stage':'journal_close','error':type(secondary).__name__})
        planned = [] if table is None else [j['id'] for j in graph(table,a['modules'],a['cache'])]
        failure = {'status':'failed','current':current,'completed':completed,
                   'entered_incomplete':[x for x in entered if x not in set(completed)],
                   'unentered':[x for x in planned if x not in set(entered)],'setup_returned':setup,
                   'original_error':type(error).__name__,'later':later,'costs':raw_budget(budget),
                   'journal_close_returned':closed,'unknown_original_tail_or_resources':True,'no_automatic_retry':True,
                   'nested':getattr(error,'failure_record',None)}
        error.failure_record = failure
        try:
            raw = encoded(failure); need(len(raw) <= a['resources']['failure_bytes'], 'bounded full failure record')
            publish(Path(a['roots']['output'])/'FAILED.json',raw,budget,readonly=True)
        except BaseException as secondary:
            failure['failure_publication'] = type(secondary).__name__; failure['costs_after_failure_attempt'] = raw_budget(budget)
        raise
