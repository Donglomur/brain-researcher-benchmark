"""Exact parent metadata primitives with an explicit bounded captured-reader adaptation.

Origin: parent scorer.py22,105 B/323df0f19e5ff293523f1bf8d3db2623b95bd8d9ca0266cad12eb192cbaca1a9.
Function bodies are unchanged except local import names. The reader is this
central programme's metered, stable-byte reader; no numerical function is copied.
This adaptation does not modify the original parent source or protected scorer.
"""
from pathlib import Path
import re
from .core import capture as central_capture, decode
from _sleep_parent.common import descriptor, need, pin


def capture(path,expected=None,cap=1048576,meter=None):
    p=Path(path)
    need(p.name in {'REQUEST.json','JOB.json','VIEW.json','BINDING.json','RECEIPT.json','TRANSFORM.json'}
         and any(p.is_relative_to(root) for root in meter.owned_roots),
         'Only pre-admitted operation metadata operands, never a numerical/source locator')
    return central_capture(path,expected,meter,cap)

def locator(value):
    need(type(value) is dict and set(value)=={'path','bytes','sha256'},'Exact artifact locator')
    descriptor({k:value[k] for k in ('bytes','sha256')});return Path(value['path'])


def lineage(row):
    keys={'source','recipe','model','fit','inference','context','mode','profile','fold','subject','view','control','nights'}
    need(set(row)==keys,'Exact private prediction/provenance record')
    for k in ('source','recipe','model','fit','inference'):descriptor(row[k])
    need(type(row['fold']) is int and type(row['subject']) is int,'Typed original biological identity')
    need(row['control'] in ('original','shifted','association'),'Declared control state')
    return row


def admit_panel(records, graph, prepared, receipt_reader):
    """receipt_reader is an operator path registry, not a callback/tool route."""
    expected={}
    for c in graph['candidate_contexts']:
        for control in c['inferences']:
            expected[c['id']+'-'+control]={'fold':c['fold'],'subject':c['subject'],'view':c['view'],'mode':c['mode'],
                'profile':c['fitting_profile'],'control':control,'nights':c['nights']}
    for r in graph['references']:
        if r['kind']=='reference_infer':
            expected[r['id']]={'fold':r['fold'],'subject':r['subject'],'view':r['view'],'mode':r['family'],
                'profile':'independent_reference','control':r['control'],'nights':r['nights']}
    need(type(records) is list and len(records)==len(expected)==2106,'All936candidate+1170reference inferences')
    got={}
    for row in records:
        lineage(row);key=row['context'];need(key in expected and key not in got,'No duplicate/missing/foreign output')
        exp=expected[key];need(all(row[k]==exp[k] for k in ('fold','subject','view','mode','profile','control')),'Exact canonical panel identity')
        need(type(row['nights']) is list and len(row['nights'])==len(exp['nights']),'All current-person nights')
        seen=set()
        for n in row['nights']:
            need(set(n)=={'night','epochs','probabilities'} and type(n['night']) is int and n['night'] not in seen,'Exact unique source night')
            seen.add(n['night']);need(n['night'] in exp['nights'],'Original night belongs to this person')
            need(n['epochs']==prepared[(row['subject'],n['night'])]['epochs'],'Complete uncropped epoch support')
            locator(n['probabilities'])
        need(seen==set(exp['nights']),'No omitted night')
        # Receipt contents must have been independently captured by the host,
        # not merely returned as candidate-authored JSON.
        for k in ('fit','inference'):
            need(row[k]['sha256'] in receipt_reader,'Independently retained producer receipt')
        got[key]=row
    for key,row in got.items():
        if row['control']=='shifted':
            original=got[key.rsplit('-',1)[0]+'-original']
            need(all(row[k]==original[k] for k in ('source','recipe','model','fit','view','subject','fold','mode','profile')), 'Shift uses identical sealed fitted state and inference source')
        if row['profile']=='training_only_reuse':
            peers=[r for r in got.values() if r['profile']==row['profile'] and r['fold']==row['fold'] and r['view']==row['view']]
            need(all(all(r[k]==row[k] for k in ('source','recipe','model','fit')) for r in peers),'One actual train-only fold/view seal, not candidate assertion')
    return got


def producer_receipt(path, expected, meter):
    r=decode(capture(path,expected,meter=meter))
    from _sleep_parent.vendor_transport.engine import validate_natural_exit
    need(r['status']=='captured' and r['producer_closed_before_capture'] is True and r['all_native_resources_closed'] is True
         and r['cli_reaped'] is True and r['output_inventory']['complete'] is True,'Independently captured naturally closed producer')
    validate_natural_exit(r['natural_exit'])
    need(r['timing']['origin']<=r['timing']['started']<r['timing']['finished']<r['timing']['phase_deadline']<=r['timing']['original_deadline'],'Original producer chronology')
    return r


def expected_phases(graph):
    result={}
    for c in graph['candidate_contexts']:
        fit=c['id']+'-fit' if c['final_fit']=='fresh_current_context' else c['final_fit']
        for control in c['inferences']:
            result[c['id']+'-'+control]={'fit':fit,'role':'A' if c['mode']=='frozen_program' else 'B','reference':False}
    for r in graph['references']:
        if r['kind']=='reference_infer':result[r['id']]={'fit':r['model'],'role':'reference','reference':True}
    return result


def phase_operands(receipt, expected_id, expected_role, expected_action, source, operands, meter):
    need(expected_id in operands,'Independently captured phase operands')
    operand=operands[expected_id]
    need(operand['logical_phase']==expected_id and type(operand['wire_phase']) is str and re.fullmatch('[0-9a-f]{32}',operand['wire_phase']), 'Private exact logical-to-opaque phase binding')
    need(receipt['phase_id']==operand['wire_phase'] and receipt['role']==expected_role and receipt['source']==source,'Exact graph-derived opaque producer phase/role/source')
    values={}
    for key in ('request','job','view','binding'):
        a=operands[expected_id][key];values[key]=decode(capture(locator(a),{k:a[k] for k in ('bytes','sha256')},meter=meter))
    request=values['request'];job=values['job'];view=values['view']
    need(operands[expected_id]['request']['sha256']==receipt['request_sha256'] and request['phase_id']==operand['wire_phase']
         and request['role']==expected_role and request['source']==source and request['action']=='held_attempt','Sealed exact request/receipt identity')
    need(request['clock']['origin']==receipt['timing']['origin'] and request['clock']['phase_deadline']==receipt['timing']['original_deadline'] and receipt['timing']['phase_deadline']<=request['clock']['phase_deadline'],'Same original phase clock')
    need(job['schema']=='neural007_worker_job_v1' and job['action']==expected_action,'Exact source-owned phase JOB')
    for target,key in (('/job.json','job'),('/view/VIEW.json','view')):
        a=operands[expected_id][key];need(list(receipt['input_before'][target]['files'].values())==[{k:a[k] for k in ('bytes','sha256')}], 'Actual mounted JOB/VIEW equals sealed operand')
    binding=values['binding'];need(all(set(x)=={'directory','subject','night','epochs'} and type(x['subject']) is int and type(x['night']) is int and type(x['epochs']) is int for x in binding['sources']), 'Typed original identity binding')
    need(binding['schema']=='neural007_private_view_binding_v1' and binding['public_view']=={k:operands[expected_id]['view'][k] for k in ('bytes','sha256')}, 'Exact private original membership binds public view')
    need({r['directory'] for r in binding['sources']}=={r['directory'] for r in view['nights']} and len(binding['sources'])==len(view['nights']), 'Complete unique private membership')
    return job,view,binding


def admit_current_view(row,receipt,view,prepared,operands,source,meter,binding):
    need(view['view']==row['view'] and view['role']=='infer' and view['current_person'] is not None,'Exact current-person inference view')
    need(len(view['nights'])==len(row['nights']) and all(n['person']==view['current_person'] and n['split_role']=='current_query'
         and n['target_role']=='unlabeled' for n in view['nights']),'All and only unlabeled current-person nights')
    transformed={}
    if row['control']=='shifted' and row['mode'] in ('frozen_program','case_adaptive_equal_inputs_tools_compute'):
        a=operands[row['context']]['transform'];trace=decode(capture(locator(a),{k:a[k] for k in ('bytes','sha256')},meter=meter))
        need(trace['source']==source and trace['context']==row['context'].rsplit('-',1)[0]
             and trace['trace']['transform']=='same_epoch_rotation_on_EEG_only_v1','Exact trusted control transform/source/context')
        transformed={m['target']:m for m in trace['trace']['members']}
        need(len(transformed)==2*len(row['nights']),'Every full current-night EEG channel transformed once')
    expected_nights={n['night']:n['epochs'] for n in row['nights']};seen=set()
    membership={r['directory']:r for r in binding['sources']}
    from _sleep_parent.common import VIEWS
    for n in view['nights']:
        night=int(n['night'].removeprefix('night-'));need(night in expected_nights and night not in seen,'Exact current original night');seen.add(night)
        e=expected_nights[night];need(n['epochs']==e and n['channels']==list(VIEWS[row['view']]),'Full original epoch/channel geometry')
        need(membership[n['directory']]=={'directory':n['directory'],'subject':row['subject'],'night':night,'epochs':e}, 'Private original query-person identity join')
        original=prepared[(row['subject'],night)]
        for name,a in [('clock.npy',original['clock'])]+[(f'channel-{c}.npy',original['channels'][str(c)]) for c in VIEWS[row['view']]]:
            rel=n['directory']+'/'+name;target='/view/'+rel;expected={k:a[k] for k in ('bytes','sha256')}
            if rel in transformed:
                t=transformed[rel];need(t['original']==expected and t['epochs']==e and t['offset_epochs']==max(1,e//3),'Authenticated complete shift origin/offset')
                expected=t['transformed']
            need(list(receipt['input_before'][target]['files'].values())==[expected],'Actual source-bound current signal/clock operands')
        need(not any('/'+n['directory']+'/' in k and k.endswith(('/stages.npy','/mask.npy')) for k in receipt['input_before']),'No private current targets in inference')
    need(seen==set(expected_nights),'Complete current-person night support')


def admit_presentation_view(view,binding,presentation,reference):
    """Private order/alias joins; arrays and within-night chronology are unchanged."""
    sources=binding['sources'];by_dir={x['directory']:x for x in sources}
    observed=[by_dir[n['directory']] for n in view['nights']]
    need(observed==sources,'Private order equals actual captured public listing')
    if reference:
        need(binding['presentation'] is None and [(x['subject'],x['night']) for x in sources]==sorted((x['subject'],x['night']) for x in sources),'Unchanged canonical reference numerical order')
        return
    from _sleep_parent.common import encoded
    need(binding['presentation']==pin(encoded(presentation)),'Exact per-fold privately bound matched presentation')
    groups=presentation['fit_group_order']+presentation['validation_group_order']
    remaining={x['subject'] for x in sources}-set(groups)
    need(len(remaining)<=1,'At most one current held person')
    groups+=list(remaining)
    pairs={(x['subject'],x['night']) for x in sources}
    expected=[(s,n) for s in groups for n in presentation['night_order'][str(s)] if (s,n) in pairs]
    need([(x['subject'],x['night']) for x in sources]==expected,'Matched whole-group/night listing permutation')
    for n,b in zip(view['nights'],sources):
        need(n['person']==presentation['aliases'][str(b['subject'])] and n['night']=='night-'+str(b['night']), 'Random alias/private source join')
        role='fit52' if b['subject'] in presentation['fit_group_order'] else ('validation13' if b['subject'] in presentation['validation_group_order'] else 'current_query')
        need(n['split_role']==role,'Unchanged original fit/validation/query membership')
