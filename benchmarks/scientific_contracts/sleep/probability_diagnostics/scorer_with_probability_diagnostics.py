"""Private complete-panel grading with target-last chronology.

No query label is opened until all required candidate AND independent-reference
prediction files and source/model/control joins pass. This is a separately
selected numerical operation, never an engineering construction step.
"""
from pathlib import Path
import hashlib
import math
import os
import struct
import re
from .common import capture, decode, descriptor, need, npy_header, ordinary, pin
from .science import confusion, combine_confusions, person_macro, probabilities
from .probability_diagnostics import ProbabilityAccumulator, panel_macro


def locator(value):
    need(type(value) is dict and set(value)=={'path','bytes','sha256'},'Exact artifact locator')
    descriptor({k:value[k] for k in ('bytes','sha256')});return Path(value['path'])


def array_rows(artifact, epochs, columns, dtype, meter):
    path=locator(artifact); expected={k:artifact[k] for k in ('bytes','sha256')}
    h=npy_header(path,expected['bytes'],meter)
    shape=[epochs,columns] if columns else [epochs]
    need(h['shape']==shape and h['dtype']==dtype,'Exact full-clock declared output geometry')
    path,before=ordinary(path); digest=hashlib.sha256();count=0
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    try:
        st=os.fstat(fd);need((st.st_dev,st.st_ino)==(before.st_dev,before.st_ino),'Exact output inode')
        def take(n):
            nonlocal count
            meter.read(n);body=os.read(fd,n);need(len(body)==n,'No truncated numeric artifact');count+=n;digest.update(body);return body
        take(h['header_bytes'])
        code='<'+'d'*columns if dtype=='<f8' else ('b' if dtype=='|i1' else '?')
        width=8*columns if dtype=='<f8' else 1
        for _ in range(epochs):
            values=list(struct.unpack(code,take(width)))
            if dtype=='<f8':probabilities([values],1)
            yield values if columns else values[0]
        meter.read(1);need(os.read(fd,1)==b'','Exact numeric EOF')
        after=os.fstat(fd)
        need((st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_nlink)==
             (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,1),'Stable numeric capture')
        need({'bytes':count,'sha256':digest.hexdigest()}==expected,'Exact entire numeric content')
    finally:os.close(fd)


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
    from .vendor_transport.engine import validate_natural_exit
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
    from .common import VIEWS
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
    from .common import encoded
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


def score(records, graph, prepared, receipt_paths, grant, meter, operands, presentations, folds):
    need(grant['schema']=='neural007_full_panel_scoring_grant_v1' and grant['authorized'] is True,'Separate protected scoring authority')
    need(grant['predictions']==pin(__import__('json').dumps(records,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n'), 'Frozen complete prediction panel')
    got=admit_panel(records,graph,prepared,receipt_paths); phases=expected_phases(graph)
    from .presentation import admit as admit_presentation
    need(set(presentations)=={str(f['fold']) for f in folds},'All six private matched presentation namespaces')
    source_rows=[{'official_subject':s,'official_night':n} for s,n in prepared]
    for f in folds:admit_presentation(presentations[str(f['fold'])],f,source_rows)
    needed=set(phases)|{v['fit'] for v in phases.values()}
    need(set(operands)==needed,'Exact complete graded logical phase closure')
    wires=[x['wire_phase'] for x in operands.values()]
    need(len(wires)==len(set(wires)) and all(type(x) is str and re.fullmatch('[0-9a-f]{32}',x) for x in wires),'Unique actual opaque wire phases')
    # Pass1: every source/producer/output is admitted before any scoring-time
    # private target access. Earlier operator preparation had separate authority.
    validated_receipts={}
    for row in got.values():
        for key in ('fit','inference'):
            p=row[key]
            if p['sha256'] not in validated_receipts:
                validated_receipts[p['sha256']]=producer_receipt(receipt_paths[p['sha256']],p,meter)
        inference=validated_receipts[row['inference']['sha256']]
        fitted=validated_receipts[row['fit']['sha256']]
        expected=phases[row['context']]
        infer_job,infer_view,infer_binding=phase_operands(inference,row['context'],expected['role'],'reference_infer' if expected['reference'] else 'infer',grant['source'],operands,meter)
        fit_job,fit_view,fit_binding=phase_operands(fitted,expected['fit'],expected['role'],'reference_fit' if expected['reference'] else 'fit',grant['source'],operands,meter)
        admit_presentation_view(infer_view,infer_binding,presentations[str(row['fold'])],expected['reference'])
        admit_presentation_view(fit_view,fit_binding,presentations[str(row['fold'])],expected['reference'])
        need(fit_view['view']==row['view'] and fit_view['role']=='fit65' and fit_view['current_person'] is None,'Final fit uses full training-only realm')
        need(len({n['person'] for n in fit_view['nights']})==65 and all(n['target_role']=='training' and n['split_role'] in ('fit52','validation13') for n in fit_view['nights']),'Complete grouped final training support')
        held={c['subject'] for c in graph['candidate_contexts'] if c['fold']==row['fold']}
        training={s for s,n in prepared if s not in held}
        wanted={(s,n) for s,n in prepared if s in training}
        need({(x['subject'],x['night']) for x in fit_binding['sources']}==wanted and len(fit_binding['sources'])==len(wanted), 'All and only final65 original training-person nights')
        by_directory={x['directory']:x for x in fit_binding['sources']}
        for n in fit_view['nights']:
            b=by_directory[n['directory']];target=prepared[(b['subject'],b['night'])]
            need(b['epochs']==n['epochs']==target['epochs'], 'Full original final-fit clock')
            from .common import VIEWS
            need(n['channels']==list(VIEWS[row['view']]),'Exact final fitting channel view')
            fitting_arrays={name:target[name] for name in ('clock','stages','mask')}
            fitting_arrays.update({f'channel-{c}':target['channels'][str(c)] for c in VIEWS[row['view']]})
            for name,a in fitting_arrays.items():
                need(list(fitted['input_before']['/view/'+n['directory']+'/'+name+'.npy']['files'].values())==[{k:a[k] for k in ('bytes','sha256')}], 'Final fit clocks and targets bind admitted training only')
        if expected['reference']:
            need(infer_job['family']==row['mode'] and fit_job['family']==row['mode'] and infer_job.get('shifted',False)==(row['control']=='shifted')
                 and fit_job.get('association_control',False)==(row['control']=='association'),'Exact reference family/control JOB state')
        admit_current_view(row,inference,infer_view,prepared,operands,grant['source'],meter,infer_binding)
        need(fitted['timing']['finished'] < inference['timing']['started'], 'Fit state sealed before inference')
        if row['mode'] in ('frozen_program','case_adaptive_equal_inputs_tools_compute'):
            fitted_files={k.removeprefix('artifacts/'):v for k,v in fitted['output_inventory']['files'].items() if k.startswith('artifacts/')}
            need(pin(__import__('json').dumps(fitted_files,sort_keys=True,separators=(',',':')).encode()+b'\n')==row['model'], 'Exact fitted complete model bundle')
            need(inference['input_before']['/model']['files']==fitted_files, 'Only exact fitted state mounted in inference')
            for target,key in (('/candidate/main.py','source'),('/recipe','recipe')):
                need(list(inference['input_before'][target]['files'].values())==[row[key]], 'Inference exact code/recipe binding')
            need(list(fitted['input_before']['/recipe']['files'].values())==[row['recipe']], 'Fit/infer recipe equality')
        else:
            need(fitted['output_inventory']['files']['MODEL.pkl']==row['model'] and
                 list(inference['input_before']['/model/MODEL.pkl']['files'].values())==[row['model']], 'Independent reference fitted state join')
            need(inference['source']==row['source'], 'Reference implementation source join')
        for n in row['nights']:
            artifact=n['probabilities'];output=Path(inference['quarantine_root'])
            path=locator(artifact);need(path.is_relative_to(output),'Prediction from exact captured producer root')
            rel=path.relative_to(output).as_posix()
            need(inference['output_inventory']['files'].get(rel)=={k:artifact[k] for k in ('bytes','sha256')},'Prediction joins complete captured inventory')
            for _ in array_rows(artifact,n['epochs'],5,'<f8',meter):pass
    # The separate content/split/mount chronological audit is pinned here; it
    # cannot be replaced by a model's own success declaration.
    audit=decode(capture(grant['boundary_audit_path'],grant['boundary_audit'],meter=meter))
    need(audit['predictions']==grant['predictions'] and audit['full_scope_and_mount_order_admitted'] is True
         and audit['fit_model_source_lineage_admitted'] is True,'Independent complete exposure/fit lineage audit')
    return _score_admitted_panel(got, graph, prepared, grant, meter)


def _score_admitted_panel(got, graph, prepared, grant, meter):
    panels={}
    probability_panels={}
    for row in got.values():
        matrices=[]
        diagnostics=ProbabilityAccumulator()
        for n in row['nights']:
            target=prepared[(row['subject'],n['night'])]
            y=list(array_rows(target['stages'],n['epochs'],0,'|i1',meter))
            mask=list(array_rows(target['mask'],n['epochs'],0,'|b1',meter))
            need(all(type(v) is int and -1<=v<=4 for v in y) and mask==[v>=0 for v in y],'Private evaluator mask/stage equality')
            matrix=[[0]*5 for _ in range(5)]
            diagnostics.begin_night(n['night'],n['epochs'])
            for p,stage in zip(array_rows(n['probabilities'],n['epochs'],5,'<f8',meter),y):
                diagnostics.update(p,stage)
                if stage>=0:matrix[stage][max(range(5),key=lambda i:(p[i],-i))]+=1
            diagnostics.end_night()
            matrices.append(matrix)
        panel=(row['mode'],row['profile'],row['view'],row['control'])
        need(row['subject'] not in panels.setdefault(panel,{}),'One prediction per person/panel')
        panels[panel][row['subject']]=combine_confusions(matrices)
        probability_panels.setdefault(panel,{})[row['subject']]=diagnostics.result()
    result={'|'.join(k):person_macro(v,78) for k,v in panels.items()}
    differences={}
    for mode in ('frozen_program','case_adaptive_equal_inputs_tools_compute'):
        profile=graph['profile'] if mode=='frozen_program' else 'current_person'
        for a,b,name in [('EC','C','EEG_over_clock'),('EOC','OC','EEG_given_EOG'),('EOC','EC','EOG_given_EEG')]:
            pa=result['|'.join((mode,profile,a,'original'))];pb=result['|'.join((mode,profile,b,'original'))]
            differences[mode+'|'+name]={'mean_delta':pa['primary']-pb['primary'],
                'paired_person_deltas':{str(s):pa['people'][s]['fixed_five_macro_f1']-pb['people'][s]['fixed_five_macro_f1'] for s in pa['people']}}
    grade={'schema':'neural007_full153_grade_v1','panels':result,'contrasts':differences,'people':78,'nights':153,
        'predictions':grant['predictions'],'raw_native_LLM_understanding_tested':False,'scientific_content_admitted':False,
        'research_qualified':False,'submission_ready':False,'independent_tasks':1}
    diagnostic_panels={'|'.join(k):panel_macro(v,panels[k]) for k,v in probability_panels.items()}
    return {'schema':'neural007_full153_grade_with_probability_diagnostics_v2',
        'grade':grade,
        'probability_diagnostics':{'schema':'neural007_full153_probability_diagnostics_v1',
            'predictions':dict(grant['predictions']),'people':78,'nights':153,
            'classes':['W','N1','N2','N3','R'],'panels':diagnostic_panels}}
