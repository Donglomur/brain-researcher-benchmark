"""Frozen exact S2 module loading; no author code or native data are imported."""
from pathlib import Path
import sys,importlib
from .io import need,capture,decode,sha,digest
ROOT=Path(__file__).resolve().parents[1]
SOURCE_LOCK='CURRENT_SOURCE_LOCK.json'
TASKS=('PAPER-FIND-044','NEURAL-045','NEURAL-046')
FULL='complete_reward_programme_v1'
def paper(name):
    location=str(ROOT/'paper/runtime')
    if location not in sys.path:sys.path.insert(0,location)
    module=importlib.import_module(name)
    need(Path(module.__file__).resolve().parent==ROOT/'paper/runtime','paper module namespace collision')
    return module
def neural(name):
    location=str(ROOT/'neural')
    if location not in sys.path:sys.path.insert(0,location)
    module=importlib.import_module('neuro.'+name)
    need(Path(module.__file__).resolve().parent==ROOT/'neural/neuro','neural module namespace collision')
    return module
def configuration():return paper('pipeline').load_config(ROOT/'paper/config')
def inspect(expected,budget=None):
    read=capture if budget is None else budget.read
    body=read(ROOT/SOURCE_LOCK,expected);lock=decode(body)
    need(lock.get('schema')=='reward_complete_central_current_source_lock_v1','current source-lock schema')
    members={p['path']:p for p in lock['files']}
    need(len(members)==len(lock['files'])<=256,'source closure size/duplicates')
    for name,field in (('SOURCE_LOCK.json','predecessor_source_lock'),('SOURCE.json','predecessor_distribution')):
        need(members.get(name)==lock[field],'historical source binding')
    distribution=decode(read(ROOT/'SOURCE.json',lock['predecessor_distribution']))
    need(set(members)==({p['path'] for p in distribution['files']}|{'SOURCE.json'})-{'README.md'},'current source closure membership')
    for p in lock['files']:
        from .io import relative
        read(relative(ROOT,p['path']),p)
    a=capture(ROOT/'paper/runtime/reward_common.py');b=capture(ROOT/'neural/neuro/reward_common.py')
    need(a==b and sha(a)=='dd446a2dde9ce45163bf10985f48e7657dd24f30b14660a271a7baadea39c6fc','exact common runtime')
    scope=paper('pipeline').full_scope(configuration());matrix,_=neural('contracts').specifications()
    need(len(scope['panels'])==166 and len(scope['conditions'])==13 and len(matrix['cells'])==84,'complete source dimensions')
    return {'lock':lock,'source':expected,'scope':scope,'matrix':matrix,'canonical_ids':list(TASKS),'independent_corpora':1,'scientific_qualification':False}
