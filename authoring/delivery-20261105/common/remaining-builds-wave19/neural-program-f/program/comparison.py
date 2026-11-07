"""Operator-only original scoring after independent closure of all three panels."""
from pathlib import Path
import sys,types

def load_original(c,binding,read,tick):
    """Capture all four definitions before executing any; restore legacy imports."""
    captures={}
    for name in ('protocol.py','common.py','array_io.py','score.py'):
        row=binding['sources'][name]
        captures[name]=(row['path'],c.capture(row['path'],1048576,c.only_pin(row),tick,read))
    sentinel=object();names=('protocol','common','array_io')
    previous={name:sys.modules.get(name,sentinel) for name in names};oldpath=sys.path[:];mods={}
    try:
        for name in ('protocol','common','array_io','score'):
            filename,raw=captures[name+'.py'];m=types.ModuleType(name if name!='score' else 'neural026_original_score');m.__file__=filename
            exec(compile(raw,filename,'exec'),m.__dict__);mods[name]=m
            if name!='score':sys.modules[name]=m
        scorer=mods['score'];io=mods['array_io']
        c.need(scorer.p is mods['protocol'] and scorer.need is mods['common'].need
               and scorer.arrays is io.arrays,'captured definitions and exact legacy binding')
        # Source numerical functions are unchanged. Only file capture is instrumented
        # with stricter stable-ordinary custody, original caps and explicit read/clock debits.
        def bounded_capture(path,cap):return c.capture(path,cap,None,tick,read)
        io.capture=bounded_capture;scorer.capture=bounded_capture
        return scorer
    finally:
        sys.path[:]=oldpath
        for name,old in previous.items():
            if old is sentinel:sys.modules.pop(name,None)
            else:sys.modules[name]=old

def grade_panels(folders,design,read_target,scorer,expected_outputs,tick):
    """All rereads stay joined to independently closed pins, not a later manifest."""
    order=('specification_only','reference_code_control','trusted_reference');admitted={}
    original_capture=scorer.capture
    closed_paths={folders[panel]/(cid+'.npz'):pin for panel,rows in expected_outputs.items() for cid,pin in rows.items()}
    def closed_capture(path,cap):
        tick();path=Path(path)
        if path not in closed_paths:raise ValueError('only externally closed NPZ operands')
        raw=original_capture(path,cap)
        if scorer.identity(raw)!=closed_paths[path]:raise ValueError('output changed from independent closure')
        tick();return raw
    scorer.capture=closed_capture
    try:
        for panel in order:
            tick();admitted[panel]=scorer.admit_submission(folders[panel],design);tick()
            if admitted[panel]!=expected_outputs[panel]:raise ValueError('closed whole panel output identity')
        # No target callback has occurred. Every panel has passed original finite/ID/schema admission.
        calls=0
        def private(cid):
            nonlocal calls
            tick();raw=scorer.capture(folders['trusted_reference']/(cid+'.npz'),scorer.FILE_CAP)
            if scorer.identity(raw)!=admitted['trusted_reference'][cid]:raise ValueError('reference changed after joint admission')
            reference=scorer.arrays(raw,scorer.KEYS,scorer.FILE_CAP);tick()
            target=read_target(cid);calls+=1;tick()
            return target,reference
        result={}
        for panel in order[:2]:
            tick();result[panel]=scorer.evaluate(folders[panel],design,private);tick()
        return dict(schema='neural026_matched_grade_v2',status='scored',conditions=result,
                    descriptive_specification_minus_code_control_MAE=result[order[0]]['primary_value']-result[order[1]]['primary_value'],
                    canonical_tasks=1,case_count_per_panel=50,independent_mice=5,reference_producers=50,
                    reference_panel_reused=True,target_callback_calls=calls,original_primary_and_statistics_preserved=True,
                    scientific_qualified=False,runtime_qualified=False,submission_ready=False)
    finally:
        scorer.capture=original_capture


def protected_grade(c,source_path,source_pin,selection_spec,external_spec,outer_proof_spec,
                    read_target,*,deadline,read_limit):
    """Concrete source route; only a trusted operator supplies custody/target authority.

    A valid-looking proof document is not authority. The operator must separately
    authenticate its provenance and authorization, exact grader numerical image,
    target-binding callback and callback I/O/work limits. A separately qualified
    enclosing process supplies the hard cutoff and memory/CPU bound. This code's
    checks are cooperative; target callback costs are outside managed_read_limit.
    No candidate-facing callback/entrypoint is provided.
    """
    c.need(type(read_limit)is int and read_limit>0,'explicit grading read allowance');spent=0
    def tick():c.before(deadline)
    def read(n):
        nonlocal spent
        c.need(type(n)is int and n>=0 and spent+n<=read_limit,'protected whole read allowance');spent+=n;tick()
    read(1000000);manifest,bodies,_=c.load(source_path,source_pin,deadline);here=Path(source_path).parent
    contracts=c.module(bodies,'contracts.py',here);policy=c.module(bodies,'policy.py',here,c=c,contracts=contracts)
    admission=c.module(bodies,'admission.py',here)
    selection=policy.selection(c.parse(c.capture(selection_spec['path'],32768,c.only_pin(selection_spec),tick,read)),source_pin)
    external=c.parse(c.capture(external_spec['path'],contracts.EXTERNAL_CAP,c.only_pin(external_spec),tick,read))
    proof=c.parse(c.capture(outer_proof_spec['path'],32768,c.only_pin(outer_proof_spec),tick,read))
    c.need(proof.get('schema')=='neural026_outer_observer_admission_v2' and proof.get('external')==c.only_pin(external_spec)
           and proof.get('source')==source_pin and proof.get('selection')==c.only_pin(selection_spec),'root-owned exact outer proof')
    for flag in ('grading_authorized','natural_exit_zero','process_reaped','process_group_absent','stdout_eof','stderr_eof',
                 'durably_closed_before_original_deadline','numerical_grader_and_target_callback_resources_admitted'):
        c.need(proof.get(flag) is True,'independent outer/scoring admission '+flag)
    root=c.path(selection['output'])
    c.need(external.get('schema')=='neural026_matched_external_v2' and external.get('status')=='complete_unqualified'
           and external.get('source')==source_pin and external.get('selection')==c.only_pin(selection_spec)
           and external.get('attempt')==str(root) and external.get('captured_worker_source')==manifest['files']['worker.py']
           and external.get('grading_performed') is False and external.get('full50_three_panels') is True
           and type(external.get('native_producers'))is int and external['native_producers']==150,'selected external observer')
    child=external['child']
    c.need(child.get('natural_exit') is True and type(child.get('exit_code'))is int and child['exit_code']==0
           and all(child.get(k) is True for k in ('process_reaped','process_group_absent','streams_closed')),'natural closed worker')
    ref=c.pin(bodies['reference_program.py'])
    policy.reviews(c.parse(c.capture(selection['reviews']['path'],2097152,c.only_pin(selection['reviews']),tick,read)),selection,ref)
    # Preserve execution-clock evidence while independently timing later grading I/O.
    proxy=types.SimpleNamespace(**{name:getattr(c,name) for name in ('parse','capture','need','only_pin','inventory','validate_natural_exit','validate_cli_commands','pin','encoded')})
    proxy.before=lambda _original:tick()
    admission.admit(proxy,contracts,ref,{k:c.only_pin(v) for k,v in c.parse(bodies['BINDING.json'])['sources'].items()},root,external['worker_terminal'],source_pin,selection,external['whole_deadline'],read)
    canonical=c.parse(c.capture(selection['canonical']['path'],contracts.CATALOGUE_CAP,c.only_pin(selection['canonical']),tick,read))
    done=c.parse(c.capture(root/'COMPLETE.json',contracts.COMPLETE_CAP,external['worker_terminal']['complete'],tick,read))
    folders={p:root/'panels'/p for p in contracts.PANELS};expected={}
    for panel in contracts.PANELS:
        m=c.parse(c.capture(folders[panel]/'submission.json',contracts.CASE_RECEIPT_CAP,done['panels'][panel],tick,read))
        expected[panel]={r['case_id']:c.only_pin(r) for r in m['cases']}
    scorer=load_original(c,c.parse(bodies['BINDING.json']),read,tick);tick()
    result=grade_panels(folders,canonical['design'],read_target,scorer,expected,tick);tick()
    result.update(source=source_pin,external_observer=c.only_pin(external_spec),root_outer_proof=c.only_pin(outer_proof_spec),
                  managed_read_reservations=spent,target_callback_accounting='Separate trusted allowance, including both repeated target reads and work',
                  grade_clock='Cooperative checks; enclosing hard cutoff and resource qualification required')
    tick();return result
