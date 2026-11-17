"""Complete ten original cases, preserved arrays and two-stage fold views.

Metadata only until byte-preserving selected copies. No private target/key or fit.
"""
import ast,hashlib,math,os,stat
from collections import Counter
from pathlib import Path
JSON_CAP=16777216
NEURAL_CAP=200000000000
MODEL_CAP=268435456
PRED_CAP=4194304
NATIVE_CAP=262144
PEOPLE=tuple(f'sub-{i:02d}' for i in range(1,11))
DOCS=('TASK.md','CASE_SCHEMA.json','PREDICTION_SCHEMA.json','POLICY.json','interface.py','PROGRAM_ABI.md')

def relative(name):
    c.need(type(name)is str and name and '\\' not in name,'literal relative file')
    p=Path(name);c.need(not p.is_absolute() and '..' not in p.parts and p.as_posix()==name,'confined relative file');return name

def desc(value,name):
    c.need(type(value)is dict and set(value)=={'path','bytes','sha256'} and value['path']==name,'exact original named descriptor');return c.only_pin(value)

def read_meta(root,name,expected,budget):
    raw=c.capture(root/name,JSON_CAP,expected,budget.tick,budget.read);return raw,c.parse(raw)

def training_contract(t,held):
    keys={'schema','people','training_image_ids','original_THINGS_training_concept_ids','inner_development_row_indices','reference_calibration_panels','inner_participant_holdouts','image_features','rule'}
    c.need(type(t)is dict and set(t)==keys and t['schema']=='neural055-training-v1','exact original training schema')
    people=[x for x in PEOPLE if x!=held]
    c.need(type(t['people'])is list and len(t['people'])==9 and [x.get('person_id') for x in t['people']]==people and t['inner_participant_holdouts']==people,'all nine training/inner people, excludes held person')
    c.need(t['training_image_ids']==['train_'+str(i).zfill(5) for i in range(16540)],'all original training image rows')
    concepts=t['original_THINGS_training_concept_ids'];c.need(type(concepts)is list and len(concepts)==16540 and all(type(x)is str and 0<len(x.encode())<=1024 for x in concepts),'complete training concepts')
    groups=Counter(concepts);c.need(len(groups)==1654 and set(groups.values())=={10},'all1654 ten-exemplar concepts')
    order=sorted(groups,key=lambda x:(hashlib.sha256(('NEURAL-055/draft1/concept-development/'+x).encode()).hexdigest(),x));dev=set(order[:330])
    c.need(t['inner_development_row_indices']==[i for i,x in enumerate(concepts) if x in dev] and all(type(x)is int for x in t['inner_development_row_indices']),'original330 development groups')
    cp=t['reference_calibration_panels'];c.need(type(cp)is dict and set(cp)=={'schema','concepts','panels','truth_convention','outer_assessment_used'} and cp['schema']=='neural055-calibration-panels-v1' and cp['outer_assessment_used']is False,'original calibration metadata')
    selected=sorted(dev,key=lambda x:(hashlib.sha256(('NEURAL-055/draft1/calibration-concepts/'+x).encode()).hexdigest(),x))[:200]
    c.need(cp['concepts']==selected and type(cp['panels'])is list and len(cp['panels'])==10 and type(cp['truth_convention'])is str,'full calibration support')
    seen=set()
    for j,row in enumerate(cp['panels']):
        c.need(type(row)is dict and set(row)=={'exemplar_rank','training_row_indices'} and type(row['exemplar_rank'])is int and row['exemplar_rank']==j,'calibration exemplar rank')
        ids=row['training_row_indices'];c.need(type(ids)is list and len(ids)==200 and all(type(i)is int and 0<=i<16540 for i in ids),'complete calibration rows')
        c.need([concepts[i] for i in ids]==selected and not seen.intersection(ids),'same200 concepts, distinct exemplars');seen.update(ids)
    c.need(type(t['rule'])is str and t['rule'],'original training rule retained')
    return people

def inspect_case(entry,budget):
    c.need(type(entry)is dict and set(entry)=={'person','public_root','CASE.json','ASSETS.json'},'exact operator case descriptor')
    held=entry['person'];c.need(held in PEOPLE,'original participant');root=c.path(entry['public_root']);c.need(Path(entry['public_root']).is_absolute(),'absolute public root')
    case_raw,case=read_meta(root,'CASE.json',c.exact_pin(entry['CASE.json']),budget);core.validate_case(case)
    assets_raw,a=read_meta(root,'ASSETS.json',c.exact_pin(entry['ASSETS.json']),budget)
    keys={'schema','case_id','query_eeg','candidate_features','coordinates','training','query_repeats_averaged','target_person_labeled_calibration','image_representation'}
    c.need(type(a)is dict and set(a)==keys and a['schema']=='neural055-case-assets-v1' and a['case_id']==case['case_id'] and type(a['query_repeats_averaged'])is int and a['query_repeats_averaged']==80 and a['target_person_labeled_calibration']is False,'exact original assets and80-repeat access')
    train_raw,t=read_meta(root,'TRAINING.json',desc(a['training'],'TRAINING.json'),budget);people=training_contract(t,held)
    coord_raw,coord=read_meta(root,'coordinates.json',desc(a['coordinates'],'coordinates.json'),budget)
    c.need(type(coord)is dict and set(coord)=={'channel_names','times_seconds','units'} and coord['units']=='released_noise_normalized_EEG_not_microvolts','original transductive coordinates')
    ch=coord['channel_names'];ts=coord['times_seconds'];c.need(type(ch)is list and len(ch)==17 and all(type(x)is str and x for x in ch) and len(set(ch))==17,'all17 source coordinate names')
    c.need(type(ts)is list and len(ts)==100 and all(type(x)in(int,float) and math.isfinite(x) for x in ts) and all(x<y for x,y in zip(ts,ts[1:])),'all100 increasing finite source times')
    representation=a['image_representation'];c.need(type(representation)is dict and set(representation)=={'checkpoint_sha256','extraction_recipe_sha256','representation_name','trained_transform_scope'} and representation['trained_transform_scope']=='fixed_checkpoint_no_dataset_fitted_transform_no_EEG' and type(representation['representation_name'])is str and representation['representation_name'],'fixed image condition')
    for k in ('checkpoint_sha256','extraction_recipe_sha256'):c.exact_pin(dict(bytes=1,sha256=representation[k]))
    files={'CASE.json':c.pin(case_raw),'ASSETS.json':c.pin(assets_raw),'TRAINING.json':c.pin(train_raw),'coordinates.json':c.pin(coord_raw)}
    arrays={}
    for key,name,shape in [('query_eeg','query.npy',(200,17,100)),('candidate_features','candidate_features.npy',(200,None))]:
        files[name]=desc(a[key],name);arrays[name]={'pin':files[name],'shape':shape,'eeg':key=='query_eeg'}
    files['training_image_features.npy']=desc(t['image_features'],'training_image_features.npy');arrays['training_image_features.npy']={'pin':files['training_image_features.npy'],'shape':(16540,None),'eeg':False}
    for row in t['people']:
        c.need(set(row)=={'person_id','eeg'},'original person file fields');name='train/'+row['person_id']+'.npy';files[name]=desc(row['eeg'],name);arrays[name]={'pin':files[name],'shape':(16540,17,100),'eeg':True}
    actual,dirs,_=c.inventory(root,NEURAL_CAP,64)
    c.need(set(actual)==set(files) and {str(x.relative_to(root)) for x in dirs}=={'.','train'},'exact public-only original case tree')
    for name,(_,stamp) in actual.items():c.need(stamp[4]==files[name]['bytes'] and stat.S_IMODE(stamp[2])==0o444,'readonly ordinary original public file')
    c.need(all(stat.S_IMODE(x.lstat().st_mode)==0o555 for x in dirs),'readonly original public directories')
    fit_names=set(files)-{'CASE.json','ASSETS.json','query.npy','candidate_features.npy'}
    return dict(person=held,root=root,case=case,assets=a,training=t,coordinates=coord,files=files,arrays=arrays,fit_names=fit_names,stamps={n:v[1] for n,v in actual.items()},total_bytes=sum(x['bytes'] for x in files.values()),fit_bytes=sum(files[n]['bytes'] for n in fit_names))

def inspect_index(raw,budget):
    index=c.parse(raw);c.need(type(index)is dict and set(index)=={'schema','cases','public_panel'} and index['schema']=='neural055-full10-input-index-v1','operator complete input index')
    c.need(type(index['cases'])is list and len(index['cases'])==10 and [r.get('person') for r in index['cases']]==list(PEOPLE),'all ten original people in source order')
    rows=[inspect_case(r,budget) for r in index['cases']];c.need(len({x['case']['case_id'] for x in rows})==10 and len({str(x['root']) for x in rows})==10,'distinct original whole public cases')
    for i,r in enumerate(rows):
        for other in rows[i+1:]:c.need(not r['root'].is_relative_to(other['root']) and not other['root'].is_relative_to(r['root']),'nonoverlapping public roots')
        c.need(r['coordinates']==rows[0]['coordinates'] and r['training']=={**rows[0]['training'],'people':r['training']['people'],'inner_participant_holdouts':r['training']['inner_participant_holdouts']} and r['assets']['image_representation']==rows[0]['assets']['image_representation'],'common source coordinates/concepts/encoder and exact permitted per-fold people')
    # Grading roster is public-only. No private panel/target descriptor is opened.
    panel=index['public_panel'];c.need(type(panel)is dict and set(panel)=={'path','bytes','sha256'} and Path(panel['path']).is_absolute(),'pinned original public scoring panel')
    p=c.path(panel['path']);public=c.parse(c.capture(p,JSON_CAP,c.only_pin(panel),budget.tick,budget.read))
    c.need(type(public)is dict and set(public)=={'schema','cases'} and public['schema']=='neural055-public-panel-v1' and type(public['cases'])is list and len(public['cases'])==10,'complete original public grading panel')
    original={r['case']['case_id']:r for r in rows};found=set()
    for d in public['cases']:
        c.need(type(d)is dict and set(d)=={'path','bytes','sha256'},'public roster descriptor');name=relative(d['path']);case=core.validate_case(c.parse(c.capture(p.parent/name,JSON_CAP,c.only_pin(d),budget.tick,budget.read)))
        ident=case['case_id'];c.need(ident in original and ident not in found and case==original[ident]['case'],'exact original public grading identity');found.add(ident)
    total=sum(x['total_bytes'] for x in rows);c.need(total<=NEURAL_CAP,'complete declared input capacity; never reduce panel')
    plan=dict(cases=10,query_count=2000,total_feature_bytes=total,fit_feature_bytes=sum(x['fit_bytes'] for x in rows),max_query_feature_bytes=max(x['total_bytes'] for x in rows))
    return index,rows,plan

def limits(plan,fit_seconds,infer_seconds):
    c.need(type(fit_seconds)is int and 1<=fit_seconds<=43200 and type(infer_seconds)is int and 1<=infer_seconds<=3600,'selected full-fold intervals')
    c.need(plan['cases']==10 and plan['query_count']==2000,'complete ten-fold scope')
    retained=plan['max_query_feature_bytes']+12*MODEL_CAP+30*PRED_CAP+40*NATIVE_CAP+32*JSON_CAP+32000000
    reads=4*plan['total_feature_bytes']+40*MODEL_CAP+10*516000000+60*PRED_CAP+80*JSON_CAP
    writes=2*plan['total_feature_bytes']+40*MODEL_CAP+40*PRED_CAP+40*JSON_CAP
    observer_reads=12*MODEL_CAP+30*PRED_CAP+32*JSON_CAP+16000000
    seconds=600+(observer_reads+999999)//1000000
    return dict(retained=retained,reads=reads,writes=writes,observer_reads=observer_reads,total_managed_reads=reads+observer_reads+4000000,observer_seconds=seconds,whole_seconds=600+10*(fit_seconds+infer_seconds+300)+seconds,phase_count=20,query_count=2000)

def npy_header(head,total,row):
    c.need(type(total)is int and total>0 and type(head)is bytes and len(head)>=10 and head[:6]==b'\x93NUMPY','ordinary NPY')
    ver=head[6:8];c.need(ver in (b'\x01\x00',b'\x02\x00'),'NPY1/2');off=10 if ver==b'\x01\x00' else 12;n=int.from_bytes(head[8:off],'little');c.need(0<n<=4096 and len(head)>=off+n,'complete bounded header')
    d=ast.literal_eval(head[off:off+n].decode('latin1'));c.need(type(d)is dict and set(d)=={'descr','fortran_order','shape'},'plain NPY header');shape=d['shape']
    c.need(type(shape)is tuple and len(shape)==len(row['shape']) and all(type(x)is int and x>0 for x in shape) and all(a is None or a==b for a,b in zip(row['shape'],shape)),'full original array axes')
    c.need(type(d['fortran_order'])is bool,'explicit original memory order')
    allowed={e+k+str(w) for e in ('<','>','|') for k in ('i','u','f') for w in (1,2,4,8) if (e=='|')==(w==1) and (k!='f' or w in (2,4,8))}
    c.need(d['descr'] in allowed,'plain original numeric dtype');width=int(d['descr'][-1]);count=math.prod(shape)
    if row['eeg']:c.need(d['descr']=='<f8' and d['fortran_order']is False,'original staged C-order float64 EEG')
    c.need(off+n+count*width==total,'complete NPY extent');return dict(dtype=d['descr'],shape=list(shape),fortran_order=d['fortran_order'],header_bytes=off+n)

def copy_file(src,dst,expected,budget,array=None):
    src=c.path(src);dst=c.path(dst);fd=os.open(src,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);out=None;geometry=None
    try:
        s=os.fstat(fd);c.need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_size==expected['bytes'],'ordinary selected extent');budget.read(s.st_size+1);budget.write(s.st_size)
        out=os.open(dst,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400);h=hashlib.sha256();count=0
        while True:
            budget.tick();b=os.read(fd,min(1048576,s.st_size+1-count));budget.tick()
            if not b:break
            c.need(count+len(b)<=s.st_size,'no growing source')
            if count==0 and array is not None:geometry=npy_header(b[:4108],s.st_size,array)
            count+=len(b);h.update(b);v=memoryview(b)
            while v:budget.tick();n=os.write(out,v);c.need(n>0,'copy progress');v=v[n:]
        c.need(count==s.st_size and h.hexdigest()==expected['sha256'] and c.stamp(s)==c.stamp(os.fstat(fd))==c.stamp(src.lstat()),'exact stable whole source copy');os.fchmod(out,0o444);os.fsync(out);budget.tick()
    finally:
        if out is not None:os.close(out)
        os.close(fd)
    c.sync_dir(dst.parent,budget.tick);return geometry

def view(root,row,kind,docs,budget):
    c.need(kind in ('fit','infer') and not root.exists(),'fresh isolated fold view');budget.capacity(32768);root.mkdir(mode=0o700);(root/'train').mkdir(mode=0o700)
    names=row['fit_names'] if kind=='fit' else set(row['files']);expected={};width=None
    for name in sorted(names):
        expected[name]=row['files'][name];g=copy_file(row['root']/name,root/name,expected[name],budget,row['arrays'].get(name))
        if g is not None and not row['arrays'][name]['eeg']:
            if width is None:width=g['shape'][1]
            c.need(g['shape'][1]==width,'shared training/candidate image feature dimension')
    for name,raw in docs.items():c.need(name in DOCS,'only declared public docs');expected[name]=c.save(root/name,raw,65536,budget.tick,budget.write);c.readable(root/name,budget.tick)
    name='train.json' if kind=='fit' else 'query.json';value=dict(schema='neural055-'+kind+'-input-v1',training='TRAINING.json',coordinates='coordinates.json')
    if kind=='infer':value.update(case='CASE.json',assets='ASSETS.json')
    expected[name]=c.save(root/name,c.encoded(value),32768,budget.tick,budget.write);c.readable(root/name,budget.tick)
    os.chmod(root/'train',0o555);os.chmod(root,0o555);c.sync_dir(root,budget.tick);return expected

def verify_view(root,expected,budget):
    files,dirs,_=c.inventory(root,budget.limits['retained'],128);c.need(set(files)==set(expected),'exact current-view inventory')
    for name,(_,s) in files.items():c.need(s[4]==expected[name]['bytes'] and stat.S_IMODE(s[2])==0o444,'readonly exact view member')
    c.need(all(stat.S_IMODE(d.lstat().st_mode)==0o555 for d in dirs),'readonly exact view directories');budget.tick();return {n:v[1] for n,v in files.items()}

def retire(root,expected,stamps,budget):
    c.need(verify_view(root,expected,budget)==stamps,'same trusted immutable view during native exposure')
    os.chmod(root,0o700);os.chmod(root/'train',0o700)
    for name in expected:budget.tick();(root/name).unlink()
    (root/'train').rmdir();root.rmdir();c.sync_dir(root.parent,budget.tick)

def unchanged(row,budget):
    files,_,_=c.inventory(row['root'],NEURAL_CAP,64);c.need({n:v[1] for n,v in files.items()}==row['stamps'],'original full public case remains unchanged');budget.tick()

def prediction(raw,case):
    c.need(type(raw)is bytes and 0<len(raw)<=PRED_CAP,'complete4MiB output');return core.validate_prediction(case,core.decode_json(raw),row_sum_abs_tolerance=1e-6)
