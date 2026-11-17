"""Task-local captured-source wiring; inherited scientific/profile bodies stay fixed."""
from pathlib import Path
from types import SimpleNamespace
from admission import ROOT,HERE,need,module
OLD='authoring/shared-program-runner-v2/'
BASE='authoring/dmfc-timing/program-runner-v2/'
LOCAL=HERE.relative_to(ROOT).as_posix()+'/'

def load(bodies):
    def make(rel,values=None,replacements=()):
        need(rel in bodies,'Execution dependency in exact source hold')
        body=bodies[rel].decode('utf-8')
        for a,b in replacements:need(body.count(a)==1,'Exact one-source transformation');body=body.replace(a,b)
        return module(ROOT/rel,body,values)
    absence=make(BASE+'absence.py');oldcontract=make(BASE+'runtime_contract.py')
    budget=make(BASE+'host_budget.py')
    imports='from runtime_contract import IMAGE,THREADS,LIMITS,TMPFS,VOLUME_OPTIONS,canonical,command,verify,require\n'
    symbols={k:getattr(oldcontract,k)for k in('IMAGE','THREADS','LIMITS','TMPFS','VOLUME_OPTIONS','canonical','command','verify','require')}
    engine=make(BASE+'engine.py',dict(symbols,absence=absence.absence),[('from absence import absence\n',''),(imports,'')])
    contract=make(LOCAL+'transport/contract_profile.py')
    dependencies=dict(BaseEngine=engine.Engine,HostBudget=budget.HostBudget,regular=engine.regular,digest=engine.digest,snapshot=engine.snapshot,absence=absence.absence,contract=contract)
    recovery=make(LOCAL+'transport/recovery.py',dependencies)
    transport=make(LOCAL+'transport/engine_profile.py',dict(dependencies,recovery=recovery))
    profile=make(OLD+'profile.py');assembler=make(OLD+'assemble_glial.py',{'decode':profile.decode,'need':profile.need},[('from profile import decode,need\n','')])
    unit=make(OLD+'unit.py',{'regular':engine.regular,'digest':engine.digest,'ProfileEngine':transport.ProfileEngine,'need':profile.need,'runtime':profile.runtime},[
        ('from qualified_core import regular,digest\n',''),('from engine_profile import ProfileEngine\n',''),('from profile import need,runtime\n',''),
        ("        start=time.monotonic();event('candidate_start_requested')", "        need(engine.end-time.monotonic()>=32,'Full20s candidate plus12s capture/normal-cleanup reserve before start')\n        start=time.monotonic();event('candidate_start_requested')")])
    validator=make(LOCAL+'ownership/trusted_controller.py')
    owner=make(LOCAL+'ownership/process_owner.py',{'validate_controller':validator.validate_controller},[('from trusted_controller import validate_controller\n','')])
    grader=make(LOCAL+'grader/grade_bridge.py')
    return SimpleNamespace(HostBudget=budget.HostBudget,digest=engine.digest,snapshot=engine.snapshot,profile=profile,assembler=assembler,unit=unit,owner=owner,grader=grader,recovery=recovery)

def recover_unit(api,attempt,end,budget,program,units):
    attempt=Path(attempt)
    rows=[x for x in units if x['unit_id']==attempt.name];need(len(rows)==1,'Exact active unit profile')
    if not attempt.exists():return [{'unit_id':attempt.name,'not_dispatched':True,'absence_verified':True}]
    return api.recovery.recover_unit(attempt,end,budget,program,rows[0])
