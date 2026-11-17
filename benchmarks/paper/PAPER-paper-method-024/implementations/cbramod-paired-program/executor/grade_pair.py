"""Admit BOTH complete outputs before opening the delayed private binding.

All numerical scoring delegates to the unchanged accepted CBraMod grader.
The full executor starts this child after all owned Docker resources close.
Standalone artifact grading proves neither resource closure nor program identity.
"""
import importlib
from pathlib import Path
import tempfile
import safe_io as safe
import operator_api
import streaming
from engine import read_pinned, lexical_path, pin


def admit_roles(r):
    """Protect direct grading too; no operator/query/capture I/O precedes this."""
    safe.need(type(r) is dict and set(r)=={'operator_root','query','query_pin','captures','binding','binding_pin',
                                         'evaluation_condition','grade_end'},'Closed trusted grading request')
    owner=lexical_path(r['binding']).parent
    safe.need(type(r['captures']) is dict and set(r['captures'])=={'A','B'},'Both grading captures')
    paths=[lexical_path(r['operator_root']),lexical_path(r['query']),Path(__file__).parent]
    for arm in ('A','B'):
        row=r['captures'][arm]
        safe.need(type(row) is dict and set(row)=={'root','submission'},'Exact captured arm descriptor')
        paths.append(lexical_path(row['root']));pin(row['submission'],4_000_000)
    safe.need(all(owner!=p and owner not in p.parents and p not in owner.parents for p in paths),
              'Dedicated grade private owner disjoint from source/query/capture roles')
    pin(r['query_pin'],256_000_000);pin(r['binding_pin'],4_000_000)


def preflight(host, q, candidates):
    """Every file, including B's final case, is admitted before any gold access."""
    with host.modules() as bodies:
        c=importlib.import_module('contract');a=importlib.import_module('arrays')
        panel=safe.strict(bodies['runtime/source/benchmark/public/PANEL.json'])
        dmap={d['id']:d for d in panel['primary_downstream_datasets']}
        import numpy as np
        for arm,(root,submission) in candidates.items():
            spec=c.submission(submission,q,panel)
            safe.need(submission['information_arm']==operator_api.ARMS[arm],'Exact captured arm')
            with tempfile.TemporaryDirectory(prefix='cbramod-paired-preflight-') as tmp:
                for row,case in zip(submission['files'],spec):
                    dest=Path(tmp)/'one';arr=a.snapshot(root,row,dest)
                    try:
                        if dmap[case['dataset']]['task']!='regression':
                            for start in range(0,len(arr),4096):
                                x=arr[start:start+4096]
                                safe.need((x>=0).all() and (x<=1).all() and
                                          (np.abs(x.astype(np.float64).sum(axis=1)-1)<=1e-6).all(),
                                          'Both complete arms need normalized probabilities before private access')
                    finally:arr._mmap.close()
                    dest.unlink()


def grade(r):
    admit_roles(r)
    host=operator_api.load(r['operator_root']);panel,c=operator_api.public(host)
    q=safe.strict(read_pinned(Path(r['query']),r['query_pin'],256_000_000))
    host._condition(r['evaluation_condition'],q['purpose'])
    candidates={}
    for arm in ('A','B'):
        root=Path(r['captures'][arm]['root'])
        submission=safe.strict(read_pinned(root/'submission.json',r['captures'][arm]['submission'],4_000_000))
        candidates[arm]=(root,submission)
    preflight(host,q,candidates)
    # No binding path is opened, statted, hashed or interpreted above this line.
    binding=safe.strict(read_pinned(r['binding'],r['binding_pin'],4_000_000))
    safe.need(type(binding) is dict and set(binding)=={'schema','query_sha256','targets','reference_metrics','reference_source_sha256'}
              and binding['schema']=='cbramod_private_binding_v1' and binding['query_sha256']==c.digest(q),
              'Exact late private binding')
    c.sha(binding['reference_source_sha256'])
    safe.need(type(binding['targets']) is dict and set(binding['targets'])=={d['id'] for d in q['datasets']},'All12 targets')
    private_root=Path(r['binding']).parent
    refs=safe.strict(safe.captured(private_root,binding['reference_metrics'],16_000_000))
    import numpy as np
    targets={};total=0
    with tempfile.TemporaryDirectory(prefix='cbramod-paired-targets-') as tmp:
        for d in q['datasets']:
            row=binding['targets'][d['id']]
            safe.need(type(row) is dict and set(row)=={'path','bytes','sha256'},'Exact private target descriptor')
            name=row['path'];safe.need(type(name) is str and name and not Path(name).is_absolute() and
                                      all(x not in ('','.','..') for x in name.split('/')),'Relative private target')
            total+=row['bytes'];safe.need(total<=100_000_000,'Complete target byte limit')
            dest=Path(tmp).resolve()/d['id'];streaming.copy(private_root/name,dest,row,r['grade_end'],100_000_000)
            streaming.npy_envelope(dest,[len(d['rows'])],'<f8')
            targets[d['id']]=np.load(dest,allow_pickle=False)
        gold={'query_sha256':c.digest(q),'targets':targets,'reference_metrics':refs,
              'reference_source_sha256':binding['reference_source_sha256']}
        results={arm:host.grade_artifacts(value,q,root,lambda:gold,r['evaluation_condition'])
                 for arm,(root,value) in candidates.items()}
    return {'schema':'cbramod_paired_result_v1','task_id':operator_api.TASK,'arms':results,
            'both_complete_outputs_admitted_before_private_access':True,
            'scope':operator_api.scope(host),'cross_arm_statistical_inference':None,
            'scientific_qualification':False,'historical_superiority_claim':False,
            'note':'Access boundary alone does not authenticate recipes, model identity, seeds, cohort parity or matched baseline training.'}
