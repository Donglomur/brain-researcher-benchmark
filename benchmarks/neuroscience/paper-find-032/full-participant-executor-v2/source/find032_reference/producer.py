"""Callable protected reference invocation and post-process-retirement admission."""
from dataclasses import dataclass,field
import hashlib
import os
import re
from pathlib import Path
import stat
import time
from find032.core import Budget,Custody,encode_json
from find032.complete_capture import capture_metadata
from find032_runtime.staging import strict
from .schema import validate,need,SCOPE,private_directory
from .files import root,read_at,write_at,rename_no_replace,errors,ORIGINALS,join_directory,join_named_directory
from .process import run_owned,OwnedExecution,ProcessFailure


@dataclass(eq=False)
class ReferenceExecution:
    native:object
    request_sha256:str
    custody:object
    output_root:object=None
    result_pin:object=None
    support:object=None
    support_pin:object=None
    admitted:bool=False
    final_deadline:float=0
    diagnostic:object=None
    diagnostic_custody:object=None
    summary_token:object=None
    publication_effects:list=field(default_factory=list)

    def require_closed(self):
        need(type(self.native)is OwnedExecution and type(self.custody)is Custody,
             'original callable reference invocation; file-only reconstruction prohibited')
        self.custody.raise_first();self.native.require_closed()
        need(self.admitted and self.output_root is not None and self.result_pin is not None and
             self.support_pin is not None and self.support['status']=='reference_materialized_after_cli_retirement',
             'completed full verification, no-replace publication and exact diagnostic closure')
        return self

    def assessment_operands(self):
        """Actual result of this invocation only, not a filename or boolean issuer.

        This returns genuine produced operands for existing assess_closed after
        its separate full candidate closure. It grants no scientific qualification.
        """
        self.require_closed()
        return {'reference_root':self.output_root,'reference_result_pin':dict(self.result_pin)}


class ReferenceFailure(RuntimeError):
    def __init__(self,execution):
        self.execution=execution;self.first=execution.custody.first
        super().__init__('reference invocation failed; original owner, files and first failure retained')


def invoke_reference(raw,source_root,source_pins,request,request_pin,bootstrap):
    cfg=validate(raw,source_root);t=cfg['times'];custody=Custody()
    need(bootstrap['original_endpoint']==t['final_end'],'same enclosing original CLI endpoint')
    selected=cfg['output'];parent=Path(cfg['protected_parent'])
    run=parent/cfg['run_name'];target=parent/cfg['final_name']
    need(not os.path.lexists(run) and not os.path.lexists(target),'fresh create-only reference operation and target')
    # One original finalization allowance exists before the actual child starts.
    budget=Budget(**cfg['budgets']['finalization'],deadline=t['final_end'],custody=custody)
    diagnostic_custody=Custody()
    diagnostic=Budget(**cfg['budgets']['diagnostic'],deadline=t['final_end'],custody=diagnostic_custody)
    summary_token=diagnostic.reserve('write',16384)
    result=ReferenceExecution(None,hashlib.sha256(raw).hexdigest(),custody,final_deadline=t['final_end'],
                              diagnostic=diagnostic,diagnostic_custody=diagnostic_custody,summary_token=summary_token)
    opened=[];child_report=None
    try:
        result.native=run_owned(cfg,source_root,source_pins,request,request_pin)
        result.native.require_closed()  # Actual scientific CLI command result, not child JSON.
        private_directory(parent);private_directory(run)
        run_fd=root(run,custody);opened.append(run_fd)
        out_fd=root(run/'outputs',custody);opened.append(out_fd)
        target_parent=root(parent,custody);opened.append(target_parent)
        originals=result.native.directory_identities
        join_directory(run_fd,originals['run']);join_directory(out_fd,originals['outputs'])
        join_directory(target_parent,originals['parent'])
        join_named_directory(target_parent,cfg['run_name'],originals['run'])
        join_named_directory(run_fd,'outputs',originals['outputs'])
        need(os.fstat(out_fd).st_dev==os.fstat(target_parent).st_dev,'same-filesystem atomic protected publication')
        child_raw,_=read_at(run_fd,'CHILD_RESULT.json',budget,custody,
                            maximum=selected['receipt_bytes'],mode=0o400)
        child_report=strict(child_raw)
        need(type(child_report)is dict and child_report.get('schema')=='FIND032_REFERENCE_CHILD_V1' and
             child_report.get('status')=='full_producer_returned_pending_original_process_retirement' and
             child_report.get('scope')==SCOPE and child_report.get('profile')==cfg['profile'] and
             child_report.get('fixed_seed')==cfg['fixed_seed'] and
             child_report.get('input_manifest')==cfg['input_manifest_pin'] and
             child_report.get('native_qualification') is False and
             child_report.get('scientific_qualification') is False and
             child_report.get('parent_retirement_pending') is True and
             child_report.get('errors',{}).get('occurrences')==0 and
             child_report.get('evidence_errors',{}).get('occurrences')==0,
             'actual matching full original child terminal receipt after natural zero')
        pin=child_report['result_manifest']
        need(type(pin)is dict and set(pin)=={'name','bytes','sha256'} and
             pin['name']=='RESULT_MANIFEST.json' and type(pin['bytes'])is int and
             0<pin['bytes']<=selected['member_bytes'] and type(pin['sha256'])is str and
             re.fullmatch('[0-9a-f]{64}',pin['sha256']), 'exact bounded terminal pin before first read')
        result_raw,_=read_at(out_fd,'RESULT_MANIFEST.json',budget,custody,maximum=pin['bytes'],expected=pin,mode=0o600)
        admitted=capture_metadata(out_fd,pin,budget,custody,member_bytes=selected['member_bytes'],
              total_bytes=selected['total_bytes'],file_count=selected['file_count'],fixed_seed=cfg['fixed_seed'])
        # Read every actual declared body, including all NPZ/PDF bytes, without
        # scientific decoding. The exact existing protocol defines permissible absence.
        rows=[pin]+strict(result_raw)['products']
        need(len({row['name'] for row in rows})==len(rows),'unique complete full-output inventory')
        verified=[]
        for row in rows:
            _,observed=read_at(out_fd,row['name'],budget,custody,maximum=row['bytes'],expected=row,mode=0o600,retain=False)
            verified.append(observed)
        need(len(rows)<=1087 and sum(r['bytes'] for r in rows)<=selected['total_bytes'],
             'full source-defined output bound')
        result.native.require_closed();budget.checkpoint()
        result.result_pin=dict(pin)
        result.support={'schema':'FIND032_PROTECTED_REFERENCE_SUPPORT_V1','status':'reference_materialized_after_cli_retirement',
            'profile':cfg['profile'],'scope':SCOPE,'fixed_seed':cfg['fixed_seed'],
            'request_sha256':result.request_sha256,'input_manifest':cfg['input_manifest_pin'],
            'source_pins':source_pins,'output_root':str(target),'result_manifest':pin,
            'verified_files':verified,'comparison_dispositions':admitted['comparison_dispositions'],
            'scientific_payloads_decoded_by_parent':False,'actual_original_cli':result.native.child.projection(),
            'actual_original_owner_closed':True,'parent_budget':result.native.owner.capacity.report(),
            'cleanup_budget':result.native.owner.recovery_capacity.report(),'child':child_report,
            'bootstrap':bootstrap,'external_enclosing_cli_exit_required':True,
            'file_alone_is_reference_authority':False,'scientific_qualification':False,'native_qualification':False,
            'historical_paper_parity':'unavailable separate route'}
        body=encode_json(result.support)
        need(len(body)<=selected['receipt_bytes'],'complete final reference support fits selected ceiling')
        # Every regular-file reader is already closed. Keep the verified directory
        # FD through atomic publication so the renamed name joins that same inode.
        custody.raise_first();result.native.require_closed();budget.checkpoint()
        result.publication_effects.append({'transition':'rename_no_replace','attempted':True,'returned':False})
        rename_no_replace(run_fd,'outputs',target_parent,cfg['final_name'],budget,custody,
                          verified_output_fd=out_fd,original_directories=originals)
        result.publication_effects[-1]['returned']=True
        result.output_root=str(target)
        result.support_pin=write_at(run_fd,'REFERENCE_SUPPORT.json',body,budget,custody)
    except BaseException as error:
        if isinstance(error,ProcessFailure):result.native=error.execution
        if custody.first is None:custody.catch('protected full reference invocation',error)
    finally:
        for fd in reversed(opened):custody.close('reference finalization original root',lambda fd=fd:os.close(fd))
    # A visible directory/report cannot override late descriptor, deadline or
    # command failure. Partial effects remain protected and are never reused.
    try:
        custody.raise_first();budget.checkpoint();result.native.require_closed()
        need(time.monotonic()<t['final_end'],'full final support original deadline')
        result.admitted=True;result.require_closed()
    except BaseException as error:
        result.admitted=False
        if custody.first is None:custody.catch('final reference admission',error)
    ORIGINALS.append((result,child_report,budget))
    if custody.first is not None:
        fd=None
        try:
            if result.native is not None and result.native.directory == str(run):
                fd=root(run,diagnostic_custody)
                native_errors=[{'stage':stage,'type':type(error).__name__} for stage,error in result.native.owner.errors]
                failure=encode_json({'schema':'FIND032_REFERENCE_FAILURE_V1','request_sha256':result.request_sha256,
                    'reference_support_admitted':False,'errors':errors(custody),'native_errors':native_errors,
                    'publication_effects':result.publication_effects,'finalization_budget':budget.report(),
                    'child_result_seen':child_report is not None,'automatic_retry':False,
                    'partial_outputs_preserved':True,'python_error_identity_survives_exit':False})
                need(len(failure)<=selected['receipt_bytes'],'bounded original final failure report')
                write_at(fd,'REFERENCE_FAILURE.json',failure,diagnostic,diagnostic_custody)
        except BaseException as error:
            diagnostic_custody.catch('secondary final failure publication',error)
        finally:
            if fd is not None:diagnostic_custody.close('final failure root',lambda:os.close(fd))
        # Do not replace the original failure with publication/close failure.
        raise ReferenceFailure(result) from custody.first.raw
    return result


def run(raw,source_root,source_pins,request,request_pin,bootstrap):
    result=invoke_reference(raw,source_root,source_pins,request,request_pin,bootstrap)
    # The CLI's small stdout is a locator/provenance summary, not a replacement
    # for its invoking caller's actual natural-zero/stream observation.
    result.require_closed()
    summary=encode_json({'schema':'FIND032_REFERENCE_CLI_V1','status':'completed_source_run_unqualified',
        'assessment_operands':result.assessment_operands(),'reference_support':result.support_pin,
        'support_root':result.native.directory,'request_sha256':result.request_sha256,
        'external_enclosing_exit_required':True,'scientific_qualification':False,'native_qualification':False})
    need(len(summary)<=16384,'bounded final CLI summary')
    done=0
    try:
        while done<len(summary):
            need(time.monotonic()<result.final_deadline,'original CLI final publication deadline')
            n=os.write(1,memoryview(summary)[done:]);need(0<n<=len(summary)-done,'complete final CLI stream');done+=n
        result.diagnostic.observed(result.summary_token,done)
        need(time.monotonic()<result.final_deadline,'original CLI post-publication deadline')
    except BaseException as error:
        result.admitted=False;result.custody.catch('final original CLI summary',error)
        raise ReferenceFailure(result) from result.custody.first.raw
    return 0
