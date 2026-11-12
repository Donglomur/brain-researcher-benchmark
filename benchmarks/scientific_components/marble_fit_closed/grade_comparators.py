"""Existing MARBLE score kernels behind complete protected comparator provenance."""
from pathlib import Path
from contract import *
from campaign import exact_inventory
def metadata(path,budget,expected=None):
    p=ordinary(path);size=p.stat().st_size
    need(type(size)is int and 0<size<=1048576,'ordinary bounded complete receipt')
    if expected is not None:need(expected['bytes']==size,'receipt extent')
    return parse(budget.read(p,size,expected))
def receipt_join(bank,c,f,q,report,source,budget):
    closure={k:f[k]for k in('state_metadata','training_embedding','observed','state_manifest')}
    need(q['coordinate']==c and q['phase']=='query'and q['fit_closure']==closure,'same original fit consumed by query')
    folder=bank/(key(c)+'--query');fitfolder=bank/(key(c)+'--fit')
    need(metadata(folder/'COMPLETE.json',budget)=={k:v for k,v in q.items()if k!='fit_closure'},'actual complete query receipt')
    closed_observation(metadata(folder/'OBSERVED.json',budget,q['observation']))
    fitmeta=metadata(fitfolder/'FIT_CLOSURE.json',budget)
    need(all(fitmeta[k]==v for k,v in f.items()),'original fit closure join')
    rows=fitmeta['files'];need(pin(encode(rows))==f['state_manifest'],'actual complete fit-state manifest identity')
    names=[r['path']for r in rows]
    need(names==sorted(set(names))and all(type(n)is str and not Path(n).is_absolute()and '..'not in Path(n).parts for n in names),'unique ordinary state membership')
    files={r['path']:{k:r[k]for k in('bytes','sha256')}for r in rows}
    need(files['STATE.json']==f['state_metadata'],'state metadata is in whole fit manifest')
    state=metadata(fitfolder/'capture/state/STATE.json',budget,f['state_metadata'])
    closed_observation(metadata(fitfolder/'OBSERVED.json',budget,f['observed']))
    fitcomplete=metadata(fitfolder/'COMPLETE.json',budget)
    need(fitcomplete['coordinate']==c and fitcomplete['phase']=='fit'and fitcomplete['embedding']==f['training_embedding']and fitcomplete['observation']==f['observed'],'actual fit output receipt')
    fitjob=metadata(fitfolder/'input/JOB.json',budget,fitcomplete['job']);queryjob=metadata(folder/'input/JOB.json',budget,q['job'])
    job_check(fitjob,'fit');job_check(queryjob,'query')
    for job in(fitjob,queryjob):need(job['coordinate']==c and job['source']==source and job['protocol']==report['protocol'],'actual selected source/coordinate/protocol')
    need(queryjob['closure']==closure,'actual query JOB consumes original closed state')
    need(state['schema']=='marble_comparator_state_v1'and state['coordinate']==c and state['source']==source and state['protocol']==report['protocol']and state['recipe']==recipe(c)and state['model_mode']=='eval','actual fit-state source/recipe')
    need(state['training_input']==fitjob['input']and state['training_labels']==fitjob['labels']and state['training_embedding']==f['training_embedding'],'state/fit input and output identities')
    need(files['post_fit_rng.pkl']==state['rng'],'RNG is part of closed state')
    checkpoint=state['checkpoint'];need(files[checkpoint['relative']]=={k:checkpoint[k]for k in('bytes','sha256')},'checkpoint is part of closed state')
    if c['method']=='marble':need(files['training_pca.pkl']==state['pca'],'fitted PCA is part of closed state')
    else:need(state['pca']is None,'no hidden CEBRA PCA')
    panel=report['panels'][c['method']]
    need(panel[filename(c,'fit')]==f['training_embedding']['sha256']and panel[filename(c,'query')]==q['embedding']['sha256'],'actual fit/query outputs equal protected bank bytes')
    # Full state was captured and authenticated by the controller on both sides
    # of query. Grading recaptures its metadata, not deserializing any model.
def admit_bank(bank,expected_pin,spec,source,budget,interface):
    bank=ordinary(bank);report=metadata(bank/'BANK.json',budget,expected_pin)
    need(report['schema']=='marble_closed_comparator_bank_v1' and report['source']==source and report['protocol']['id']==PROTOCOL,'bound original comparator bank')
    coords=schedule(spec);need([r['coordinate']for r in report['fits']]==coords and len(report['attempts'])==48,'complete48 fits')
    need([r['coordinate']for r in report['queries']]==coords,'complete48 query receipts')
    need(report['fit_count']==report['query_count']==48 and report['embeddings']==96,'full native comparator support')
    for c,row in zip(coords,report['attempts']):
        need(row=={'coordinate':c,'fit':'closed','query':'closed'},'all actual fit/query closures')
    for c,f,q in zip(coords,report['fits'],report['queries']):
        receipt_join(bank,c,f,q,report,source,budget)
    admitted={}
    for m in METHODS:
        v=interface.admit(bank/m,spec,'B',m)
        need(v[2]==report['panels'][m],'all32 comparator bytes match protected bank')
        admitted[m]=v
    # The protected external report pin binds observed fit/state/train identities;
    # it does not certify native execution, semantic method competence or containment.
    return report,admitted
def assess(lib,package,candidate,access_view,bank,bank_pin,budget):
    need(access_view in('A','B'),'fixed access arm')
    spec=lib['spec'];interface=lib['interface']
    candidates=interface.admit(candidate,spec,access_view,'candidate')
    report,refs=admit_bank(bank,bank_pin,spec,lib['source'],budget,interface)
    # All128 candidate/reference embedding bodies are captured before private labels.
    assets=metadata(Path(package)/'private/ASSETS.json',budget,report['assets'])
    pins={r['path']:r for r in assets['files']};labels={}
    for r in spec['rats']:
        relative='private/labels/'+r['rat']+'.npy';p=pins[relative];raw=budget.read(Path(package)/relative,p['bytes'],{k:p[k]for k in('bytes','sha256')})
        labels[r['rat']]=(raw,interface.npy_header(raw,(r['raw_samples'],3)))
    core=lib['score_core'];y=core.arrays(labels)
    admitted={'candidate':candidates,**refs}
    scores={m:core.score(core.arrays(v[1]),y,spec)for m,v in admitted.items()}
    return {'schema':'marble_fit_closed_grade_v1','protocol_id':PROTOCOL,'access_view':access_view,'scores':scores,
            'candidate_vs_native_marble':core.improvement(scores['candidate'],scores['marble']),
            'captured_artifact_hashes':{m:v[2]for m,v in admitted.items()},'protected_comparator_bank':bank_pin,
            'complete_native_provenance_admitted':True,'native_execution_or_method_qualification':False,
            'semantic_no_refit_proven':False,'consistency_is_descriptive_alignment_not_out_of_sample_transfer':True}

