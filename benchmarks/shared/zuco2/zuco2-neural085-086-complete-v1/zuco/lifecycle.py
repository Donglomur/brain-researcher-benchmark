"""Complete 32-operator/25-stage evidence ledger; statuses never establish science."""
from .io import *
from .operators import initial,record,NATIVE_UNRESOLVED,ROOT

def new():
    chain=decode(read(ROOT/'normative/PROTECTED_EXECUTION_CHAIN.json',2*1024**2))
    return {"operators":initial(),"stages":{x['id']:{"operation":x['operation'],"status":"not_started","evidence":[]} for x in chain['stages']},"scientific_qualification":False}
def stage(book,key,evidence,status='source_executed_unqualified'):
    need(key in book['stages'] and evidence,'stage_evidence');book['stages'][key].update(status=status,evidence=evidence)
def operators(book,keys,evidence,status='computed_unqualified'):
    for key in keys:record(book['operators'],key,evidence,status)
def source_stages(book,panel,source):
    for s in ['S01','S02','S03','S04']:stage(book,s,[source['preparation_receipt']],'externally_qualified_input_custody')
    for o in ['O01','O02','O03','O04','O05','O06','O09']:record(book['operators'],o,[source['preparation_receipt']],'externally_prepared_input_custody')
    # No source-stage record is promoted into a missing native operator implementation.
    return book

def prediction_stages(book,report):
    evidence=[{"campaign_plan_sha256":digest(report['plan']),"original_attempts_sha256":digest(report['original_attempts'])}]
    for s in ['S05','S06','S07','S08','S09','S10','S11','S12','S13','S14','S15','S16','S21']:
        stage(book,s,evidence,'failed_or_incomplete' if report['original_failure'] else 'source_executed_unqualified')
    operators(book,['O20','O21','O22','O23','O24','O25','O26','O27'],evidence,'failed_or_incomplete' if report['original_failure'] else 'computed_unqualified')
    return book
