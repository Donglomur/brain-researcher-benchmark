"""Actual scientific child: exact unchanged full reference_campaign and own roots."""
import os
from pathlib import Path
import sys
import time
from find032.core import Budget, Custody, encode_json
from find032.admission import parse_input_manifest
from find032.controller import reference_campaign
from find032_runtime.staging import strict
from .schema import validate,need,SCOPE
from .files import root,read_absolute,read_at,write_at,errors,ORIGINALS


def run(raw, source_root, bootstrap):
    cfg=validate(raw,source_root);t=cfg['times'];custody=Custody();evidence=Custody()
    need(bootstrap['original_endpoint']==t['child_end'],'same scientific child original endpoint')
    science=Budget(**cfg['budgets']['science'],deadline=t['work_end'],custody=custody)
    receipt=Budget(**cfg['budgets']['child_evidence'],deadline=t['child_end'],custody=evidence)
    # Reserve fixed receipt before any scientific input read; write_at's actual
    # reserve is against the same independent selected ledger, not new allowance.
    token=receipt.reserve('write',cfg['output']['receipt_bytes'])
    creation=receipt.reserve('files',1)
    input_fd=output_fd=evidence_fd=None;outcome=None;manifest_pin=None;report=None
    run_root=Path(cfg['protected_parent'])/cfg['run_name']
    try:
        input_raw,_=read_absolute(cfg['input_manifest'],cfg['input_manifest_pin'],science,custody)
        plan=parse_input_manifest(input_raw)
        need(sum(row.bytes for row in plan.members)<=cfg['budgets']['science']['read_bytes']-cfg['input_manifest_pin']['bytes'],
             'all132 authentic captures fit original science read budget')
        input_fd=root(cfg['input_root'],custody);output_fd=root(run_root/'outputs',custody)
        need(not os.listdir(output_fd),'fresh private full output directory')
        # Explicit runtime prefixes only; captured finder still owns all task imports.
        sys.path.extend(cfg['numerical_search_roots'])
        outcome=reference_campaign(plan,input_fd,output_fd,science,custody,
                                   fixed_seed=cfg['fixed_seed'],member_bytes=cfg['output']['member_bytes'])
        ORIGINALS.append(outcome)
        outcome.custody.raise_first();need(outcome.status in ('source_run_returned_unqualified',
             'partial_scientific_support_unqualified'),'unchanged successful full producer disposition')
        # Core closes its science Budget at return; receipt uses preselected independent reserve.
        _,manifest_pin=read_at(output_fd,'RESULT_MANIFEST.json',receipt,evidence,
                               maximum=cfg['output']['member_bytes'],mode=0o600)
    except BaseException as error:
        if custody.first is None:custody.catch('full reference child',error)
    finally:
        if output_fd is not None:custody.close('reference output root',lambda:os.close(output_fd))
        if input_fd is not None:custody.close('reference input root',lambda:os.close(input_fd))
    # Original logical reservations have already been made. Emit exactly one
    # original receipt even after scientific failure; no recursive publication.
    report={'schema':'FIND032_REFERENCE_CHILD_V1','scope':SCOPE,'status':'failed' if custody.first or evidence.first else
            'full_producer_returned_pending_original_process_retirement','profile':cfg['profile'],
            'fixed_seed':cfg['fixed_seed'],'input_manifest':cfg['input_manifest_pin'],
            'result_manifest':manifest_pin,'errors':errors(custody),'evidence_errors':errors(evidence),
            'science_budget':science.report(),'bootstrap':bootstrap,
            'native_qualification':False,'scientific_qualification':False,'parent_retirement_pending':True}
    try:
        evidence_fd=root(run_root,evidence);body=encode_json(report)
        need(len(body)<=cfg['output']['receipt_bytes'],'complete original child receipt fits')
        # Adopt the already reserved envelope exactly; no double resource reserve.
        handle=None;done=0
        try:
            handle=os.open('CHILD_RESULT.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,
                           0o600,dir_fd=evidence_fd);receipt.observed(creation,1)
            while done<len(body):
                need(time.monotonic()<t['child_end'],'original child receipt deadline');n=os.write(handle,memoryview(body)[done:done+65536])
                need(0<n<=min(65536,len(body)-done),'complete child receipt progress');done+=n
            os.fsync(handle);os.fchmod(handle,0o400);os.fsync(evidence_fd);receipt.observed(token,done)
        finally:
            if handle is not None:evidence.close('child receipt file close',lambda:os.close(handle))
    except BaseException as error:
        evidence.catch('original child receipt publication',error)
    finally:
        if evidence_fd is not None:evidence.close('child receipt root close',lambda:os.close(evidence_fd))
    ORIGINALS.append((custody,evidence,outcome,report))
    custody.raise_first();evidence.raise_first();return 0
