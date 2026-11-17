"""Metadata-only extraction of the exact parent scorer pre-numeric joins.

Parent scorer.py22,105 B/323df0f19e5ff293523f1bf8d3db2623b95bd8d9ca0266cad12eb192cbaca1a9.
This omits array_rows and every score/boundary-audit/target operation. Complete
producer provenance does not establish valid numerical probabilities or scores.
"""
from pathlib import Path
from collections import OrderedDict
import re
from _sleep_parent.common import need, pin
from .panel_primitives import (admit_panel,expected_phases,producer_receipt,
    phase_operands,admit_presentation_view,admit_current_view,locator)


def admit(records,graph,prepared,receipt_paths,source,meter,operands,presentations,folds):
    grant={'source':source}
    got=admit_panel(records,graph,prepared,receipt_paths); phases=expected_phases(graph)
    from _sleep_parent.presentation import admit as admit_presentation
    need(set(presentations)=={str(f['fold']) for f in folds},'All six private matched presentation namespaces')
    source_rows=[{'official_subject':s,'official_night':n} for s,n in prepared]
    for f in folds:admit_presentation(presentations[str(f['fold'])],f,source_rows)
    needed=set(phases)|{v['fit'] for v in phases.values()}
    need(set(operands)==needed,'Exact complete graded logical phase closure')
    wires=[x['wire_phase'] for x in operands.values()]
    need(len(wires)==len(set(wires)) and all(type(x) is str and re.fullmatch('[0-9a-f]{32}',x) for x in wires),'Unique actual opaque wire phases')
    # Pass1: every source/producer/output is admitted before any scoring-time
    # private target access. Earlier operator preparation had separate authority.
    receipt_cache=OrderedDict(); operand_cache=OrderedDict()
    def receipt_for(d):
        key=(receipt_paths[d['sha256']],d['bytes'],d['sha256'],source['bytes'],source['sha256'])
        if key not in receipt_cache:
            receipt_cache[key]=producer_receipt(key[0],d,meter)
            if len(receipt_cache)>2:receipt_cache.popitem(last=False)
        receipt_cache.move_to_end(key)
        return receipt_cache[key]
    def operands_for(receipt,identity,role,action):
        record=operands[identity]
        key=(identity,role,action,receipt['request_sha256'],source['bytes'],source['sha256'],
            tuple((name,record[name]['path'],record[name]['bytes'],record[name]['sha256']) for name in ('request','job','view','binding')))
        if key not in operand_cache:
            operand_cache[key]=phase_operands(receipt,identity,role,action,source,operands,meter)
            if len(operand_cache)>2:operand_cache.popitem(last=False)
        operand_cache.move_to_end(key)
        return operand_cache[key]
    # Only metadata admission order changes; original producers/scientific
    # arrays/reference numerical order and protected scoring remain unchanged.
    for row in sorted(got.values(),key=lambda r:(r['fit']['sha256'],r['context'])):
        fitted=receipt_for(row['fit']); inference=receipt_for(row['inference'])
        expected=phases[row['context']]
        infer_job,infer_view,infer_binding=operands_for(inference,row['context'],expected['role'],'reference_infer' if expected['reference'] else 'infer')
        fit_job,fit_view,fit_binding=operands_for(fitted,expected['fit'],expected['role'],'reference_fit' if expected['reference'] else 'fit')
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
            from _sleep_parent.common import VIEWS
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
            # Numerical probability validation remains protected score work.
    return got
