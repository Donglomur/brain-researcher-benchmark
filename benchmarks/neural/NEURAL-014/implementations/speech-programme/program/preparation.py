"""Operator-only full sanitized projection and deterministic index admission.

No call is made by the candidate controller. Future input preparation needs its
own root-selected complete resource envelope and independent native admission.
The builder and verifier import only the exact reviewed NumPy2.2.6 environment;
the hardened -S candidate controller never imports NumPy or reads pool targets.
"""
import hashlib,os,struct,time

def seed(case_id):
    return int.from_bytes(hashlib.sha256(('neural014-row-permutation-v1|'+case_id).encode()).digest()[:8],'big')

def index_bytes(row):
    import numpy as np
    c.need(np.__version__=='2.2.6','original exact permutation library version')
    steps=row['steps'];c.need(type(steps)is int and 0<steps<=100000,'full complete trial length')
    indices=np.random.default_rng(seed(row['id'])).permutation(steps)
    return b'N014P1\0\0'+struct.pack('<I',steps)+b''.join(struct.pack('<I',int(i)) for i in indices)

def binding(row,raw,generator_source):
    return dict(schema='neural014-permutation-preparation-v1',case_id=row['id'],steps=row['steps'],seed=seed(row['id']),numpy='2.2.6',raw_feature=c.only_pin(row['features']),permutation=c.pin(raw),generator_source=c.exact_pin(generator_source))

def verify_index(row,raw,receipt,generator_source):
    """Future independent admission recomputes semantic order, not just bijection.

    Use the explicitly selected PCG64 generator independently of the producer's
    default_rng spelling. Exact source-controlled NumPy version and array input
    identity join are prerequisites; a receipt alone is not provenance.
    """
    import numpy as np
    c.need(np.__version__=='2.2.6','independent frozen permutation library')
    c.need(c.encoded(receipt)==c.encoded(binding(row,raw,generator_source)),'exact case/seed/length/raw-array/index/source binding')
    actual=packet.permutation(raw,row['steps'])
    expected=np.random.Generator(np.random.PCG64(seed(row['id']))).permutation(row['steps'])
    c.need(actual==[int(i) for i in expected],'independently recomputed original permutation; bijection alone insufficient')
    return True

def build(pool,source_root,out,budget,generator_source,pool_pin):
    """Concrete future full-source projection; never invoked in construction.

    `pool` is captured under pool_pin by the authorized caller, and no unknown
    transcript/target is printed or returned. Source pool/gold stay outside the
    emitted candidate-controller tree. Budget is the separately selected input
    preparation envelope, not the later candidate producer allowance.
    """
    c.need(c.pin(c.encoded(pool))==pool_pin,'canonical captured original pool identity')
    science.validate_pool(pool);source_root=c.path(source_root);out=c.path(out)
    # Admit every array path/extent/role before the first file open. The older
    # pool validator intentionally does not authenticate feature descriptors.
    provisional={r['id']:dict(path='permutations/'+r['id']+'.bin',bytes=12+4*r['steps'],sha256='0'*64) for r in pool['rows'] if r['role']=='query'}
    packet.project_pool(pool,provisional)
    c.need(not out.exists() and out.parent.is_dir() and not out.is_relative_to(source_root) and not source_root.is_relative_to(out),'fresh disjoint prepared tree')
    budget.capacity(65536);started=time.monotonic();out.mkdir(mode=0o700)
    for name in ('arrays','permutations'):(out/name).mkdir(mode=0o700)
    pins={};receipts=[];array_total=0;index_total=0
    for row in pool['rows']:
        raw=c.capture(source_root/row['features']['path'],packet.ARRAY_CAP,c.only_pin(row['features']),budget.tick,budget.read)
        packet.npy(raw,row['steps'])
        # Full finite check, unchanged values. Fake role leaves every raw bit.
        raw=packet.transform(raw,row,dict(treatment=None,arm=None))
        pin=c.save(out/row['features']['path'],raw,packet.ARRAY_CAP,budget.tick,budget.write)
        c.need(pin==c.only_pin(row['features']),'source primitive bytes preserved');c.readable(out/row['features']['path'],budget.tick);array_total+=len(raw)
        if row['role']=='query':
            index=index_bytes(row);receipt=binding(row,index,generator_source)
            # Separate implementation recomputation is also exposed to future
            # independent admission; builder self-check alone is not that review.
            verify_index(row,index,receipt,generator_source)
            path='permutations/'+row['id']+'.bin';pin=c.save(out/path,index,400012,budget.tick,budget.write);c.readable(out/path,budget.tick)
            pins[row['id']]=dict(pin,path=path);receipts.append(receipt);index_total+=len(index)
    public=packet.project_pool(pool,pins);plan=packet.admit(public)
    c.need(plan['total_feature_bytes']==array_total and plan['permutation_bytes']==index_total,'all original retained arrays and indices accounted')
    public_pin=c.save(out/'PUBLIC.json',c.encoded(public),packet.JSON_CAP,budget.tick,budget.write);c.readable(out/'PUBLIC.json',budget.tick)
    for name in ('arrays','permutations'):os.chmod(out/name,0o555);c.sync_dir(out/name,budget.tick)
    os.chmod(out,0o555);c.sync_dir(out,budget.tick)
    return dict(schema='neural014-sanitized-projection-v1',source_pool=pool_pin,generator_source=generator_source,public_manifest=public_pin,plan={k:plan[k] for k in packet.PLAN_FIELDS},permutations=receipts,elapsed_seconds=time.monotonic()-started,costs=budget.record(),all45_sessions=True,query_targets_emitted=False,scientific_execution=False,independent_input_admission=False)

def independent_indices(public,source_root,receipts,generator_source,read):
    """Full-Q future semantic audit, not a sample; never called during build work."""
    plan=packet.admit(public);rows=plan['queries']
    c.need(type(receipts)is list and len(receipts)==len(rows),'all query permutation receipts')
    byid={r['case_id']:r for r in receipts};c.need(len(byid)==len(rows) and set(byid)==set(plan['query_by_id']),'exact full permutation receipt support')
    for row in rows:
        pin=row['permutation'];raw=read(c.path(source_root)/pin['path'],400012,c.only_pin(pin))
        verify_index(row,raw,byid[row['id']],generator_source)
    return dict(query_count=len(rows),permutation_bytes=plan['permutation_bytes'],semantic_recomputation=True,physical_electrode_loss_claim=False)
