"""Separate original-input preparation operation; no acquisition or model run."""
from core import need,capture,parse
from contracts import COHORT_PIN
from authority import Qualifications,effective_selection
from preparation import run as prepare


def run(request,budget,frozen):
    need(request.get('schema')=='neural058_preparation_envelope_v1' and request.get('task')=='NEURAL-058'
         and request.get('selected') is True,'independently selected original-input preparation')
    authority=request['authority']
    need(authority['source']==frozen['pin'] and authority['origin']==budget.origin and authority['deadline']==budget.deadline,
         'exact inherited preparation source and original clocks')
    need(authority['limits']['read_bytes']==budget.read_cap and authority['limits']['write_bytes']==budget.write_cap,
         'actual inherited whole preparation resource selection')
    raw,_=capture(request['cohort']['path'],COHORT_PIN,COHORT_PIN['bytes'],budget,readonly=True)
    need(request['cohort']['pin']==COHORT_PIN,'exact full canonical biological metadata')
    qualification=Qualifications(authority,frozen['pin'],budget)
    # Source-owned evidence checker; no callback can provide prepared science.
    result=prepare(authority,parse(raw),budget,
                   lambda kind,subject:qualification.require(kind,effective_selection(subject)))
    budget.tick()
    return {'prepared':result,'qualification':qualification.observed,
            'actual_external_process_and_resource_admission_still_required':True,
            'model_or_scoring_execution':False}
