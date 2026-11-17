"""Trusted canonical-store joins and one split at a time. No fitting or scoring.

Only this operator reads label-bearing canonical metadata. Candidate mounts are
new standalone files, never this store or a shared backing array.
"""
from collections import Counter
from pathlib import Path
import os,stat
PEOPLE=tuple(range(1,55));SESSIONS=(1,2);PHASES=('train','test')
PRED_CAP=262144;NATIVE_CAP=262144;JSON_CAP=5000000;MODEL_CAP=536870912
PAYLOAD=345600000

def pinrow(v,name,cap):
    c.need(type(v)is dict and set(v)=={'path','bytes','sha256'} and v['path']==name,'exact canonical basename')
    p=c.only_pin(v);c.need(p['bytes']<=cap,'bounded canonical extent');return p

def metadata_join(pool,gold):
    """Complete released preparation order, ID, participant/phase and label join."""
    c.need(type(pool)is dict and set(pool)=={'schema','generation','assets','gold'} and pool['schema']=='neural084_pool_v1','exact original pool schema')
    generation=pool['generation'];contracts._generation(generation)
    c.need(type(gold)is dict and set(gold)=={'schema','generation','rows'} and gold['schema']=='neural084_gold_v1' and gold['generation']==generation,'original trusted labels generation')
    expected=[(p,s,h) for p in PEOPLE for s in SESSIONS for h in PHASES]
    assets=pool['assets'];labels=gold['rows']
    c.need(type(assets)is list and len(assets)==216 and type(labels)is list and len(labels)==21600,'complete216phase arrays and21600 labels')
    seen=set();records=[];files={};counts=Counter();position=0
    for ordinal,(asset,key) in enumerate(zip(assets,expected)):
        c.need(type(asset)is dict and set(asset)=={'person','session','phase','signals','ids'},'exact original asset fields')
        person,session,phase=key
        c.need(type(asset['person'])is int and type(asset['session'])is int and (asset['person'],asset['session'],asset['phase'])==key,'original full ordered54x2x2')
        name='p%02d-s%d-%s.npy'%key;files[name]=pinrow(asset['signals'],name,1638400)
        contracts._ids(asset['ids'],100)
        for source_row,qid in enumerate(asset['ids']):
            row=labels[position];position+=1
            c.need(type(row)is dict and set(row)=={'id','person','session','phase','label'},'exact source label row')
            c.need(qid not in seen and row['id']==qid and type(row['person'])is int and type(row['session'])is int and (row['person'],row['session'],row['phase'])==key,'complete identity and array-row provenance join')
            c.need(type(row['label'])is int and row['label'] in (1,2,3,4),'source four-class label')
            seen.add(qid);counts[key+(row['label'],)]+=1
            records.append(dict(row,source=ordinal,row=source_row))
    c.need(len(seen)==21600 and len(counts)==864 and set(counts.values())=={25},'all54 people/session/phase/classes, no exclusion')
    return tuple(sorted(records,key=lambda r:r['id'])),files

def snapshot(root,files,cap=400000000):
    root=c.path(root);before=root.lstat();c.need(stat.S_ISDIR(before.st_mode) and stat.S_IMODE(before.st_mode) in (0o700,0o555),'ordinary canonical or owned directory')
    found,dirs,_=c.inventory(root,cap,len(files)+2)
    c.need(set(found)==set(files) and dirs==[root],'exact directory membership')
    for name,(_,stamp) in found.items():
        c.need(stamp[4]==files[name]['bytes'] and stat.S_IMODE(stamp[2])==0o444,'same readonly ordinary extent')
    c.need(c.stamp(before)==c.stamp(root.lstat()),'stable whole directory')
    return dict(root=c.stamp(before),files={name:found[name][1] for name in files})

def load(s,budget):
    root=c.path(s['canonical_root']);poolpin=c.only_pin(s['pool'])
    raw=c.capture(root/'pool.json',JSON_CAP,poolpin,budget.tick,budget.read);pool=contracts.decode(raw)
    goldpin=pinrow(pool['gold'],'gold.json',JSON_CAP)
    raw=c.capture(root/'gold.json',JSON_CAP,goldpin,budget.tick,budget.read);gold=contracts.decode(raw)
    records,files=metadata_join(pool,gold);del gold,raw
    files.update({'pool.json':poolpin,'gold.json':goldpin});before=snapshot(root,files)
    descriptors=[]
    for asset in pool['assets']:
        d=asset['signals'];descriptors.append(stream.authenticate(root/d['path'],c.only_pin(d),budget))
    c.need(snapshot(root,files)==before,'same complete canonical store after authentication')
    return dict(root=root,generation=pool['generation'],pool_pin=poolpin,gold_pin=goldpin,assets=pool['assets'],records=records,files=files,stamps=before,descriptors=tuple(descriptors),canonical_bytes=sum(v['bytes'] for v in files.values()))

def unchanged(store,budget):
    budget.tick();c.need(snapshot(store['root'],store['files'])==store['stamps'],'original complete canonical store unchanged');budget.tick()

def fold_rows(store,person,kind):
    c.need(type(person)is int and person in PEOPLE and kind in ('fit','query'),'complete selected fold/split')
    rows=tuple(r for r in store['records'] if (r['person']==person)==(kind=='query'))
    expected=21200 if kind=='fit' else 400;c.need(len(rows)==expected,'full original row support')
    selected=tuple(i for i,a in enumerate(store['assets']) if (a['person']==person)==(kind=='query'))
    c.need(len(selected)==(212 if kind=='fit' else 4),'only complete selected source phases')
    local={old:new for new,old in enumerate(selected)}
    order=tuple((local[r['source']],r['row']) for r in rows)
    return rows,order,tuple(store['descriptors'][i] for i in selected)

def stage(store,person,kind,current,budget,training=None):
    unchanged(store,budget);current=c.path(current)
    c.need(current==budget.root/'current' and not os.path.lexists(current),'fresh sole current split')
    rows,order,descriptors=fold_rows(store,person,kind)
    budget.capacity(16384);current.mkdir(mode=0o700);c.sync_dir(current.parent,budget.tick)
    name='training.npy' if kind=='fit' else 'queries.npy'
    array=stream.gather(current/name,order,descriptors,budget);files={name:array}
    if kind=='fit':
        c.need(training is None,'no prior fold state in training')
        metadata=dict(schema='neural084_training_v1',rows=[{k:r[k] for k in ('id','label','person','session','phase')} for r in rows])
        raw=c.encoded(metadata);files['training.json']=c.save(current/'training.json',raw,JSON_CAP,budget.tick,budget.write);c.readable(current/'training.json',budget.tick)
        manifest=dict(schema='neural084_train_view_v2',generation=store['generation'],fold='fold%03d'%person,classes=[1,2,3,4],rows=21200,training=dict(path=name,**array),training_metadata=dict(path='training.json',**files['training.json']))
        files['train.json']=c.save(current/'train.json',c.encoded(manifest),262144,budget.tick,budget.write);c.readable(current/'train.json',budget.tick)
    else:
        c.need(type(training)is dict and set(training)=={'training.npy','training.json','train.json'},'prior complete training pins only')
        manifest=dict(schema='neural084_fold_v1',generation=store['generation'],fold='fold%03d'%person,ids=[r['id'] for r in rows],classes=[1,2,3,4],training=dict(path='training.npy',**training['training.npy']),training_metadata=dict(path='training.json',**training['training.json']),queries=dict(path=name,**array))
        files['fold.json']=c.save(current/'fold.json',c.encoded(manifest),262144,budget.tick,budget.write);c.readable(current/'fold.json',budget.tick)
    os.chmod(current,0o555);c.sync_dir(current,budget.tick);c.sync_dir(current.parent,budget.tick)
    unchanged(store,budget);return files,manifest

def verify(current,files,budget):
    before=snapshot(current,files,budget.limits['retained']);c.need(stat.S_IMODE(before['root'][2])==0o555,'sealed split directory')
    for name,pin in files.items():
        stamp=contracts._stream_file(current/name,pin,budget)
        c.need(stamp==before['files'][name],'same hash-verified split member')
    c.need(snapshot(current,files,budget.limits['retained'])==before,'whole split unchanged');return before

def retire(current,files,stamps,budget):
    budget.capacity();c.need(current==budget.root/'current' and snapshot(current,files,budget.limits['retained'])==stamps,'same sole owned split before retirement')
    fd=os.open(current,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        c.need(c.stamp(os.fstat(fd))==stamps['root'],'same selected directory inode');os.fchmod(fd,0o700)
        for name in files:
            budget.tick();c.need(c.stamp(os.stat(name,dir_fd=fd,follow_symlinks=False))==stamps['files'][name],'same retired member');os.unlink(name,dir_fd=fd)
        budget.tick();os.fsync(fd);budget.tick();c.need(c.stamp(os.fstat(fd))==c.stamp(current.lstat()),'same empty directory');os.rmdir(current)
    finally:os.close(fd)
    c.sync_dir(current.parent,budget.tick);c.need(not os.path.lexists(current),'durable whole split absence');budget.tick()

def seal_model(source,target,pin,budget):
    c.need(not os.path.lexists(target) and source.parent.parent==target.parent,'one fold same-volume model rename')
    c.readable(source,budget.tick);stamp=contracts._stream_file(source,pin,budget)
    c.need(source.parent.stat().st_dev==target.parent.stat().st_dev,'same filesystem seal')
    budget.tick();os.rename(source,target);c.sync_dir(source.parent,budget.tick);c.sync_dir(target.parent,budget.tick)
    c.need(not os.path.lexists(source) and c.stamp(target.lstat())[:-1]==stamp[:-1],'same model inode/mode/extent/mtime; rename may change ctime')
    return contracts._stream_file(target,pin,budget) # post-rename SHA/stamp, separately charged

def retire_model(path,pin,stamp,budget):
    budget.capacity();c.need(path.is_relative_to(budget.root) and path.name=='model.bin','owned model only')
    c.need(contracts._stream_file(path,pin,budget)==stamp,'same model bytes and inode after inference')
    parent=path.parent;before=parent.lstat();fd=os.open(parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        c.need((before.st_dev,before.st_ino)==(os.fstat(fd).st_dev,os.fstat(fd).st_ino),'same owned model directory')
        c.need(c.stamp(os.stat(path.name,dir_fd=fd,follow_symlinks=False))==stamp,'same final model');budget.tick();os.unlink(path.name,dir_fd=fd);os.fsync(fd);budget.tick()
    finally:os.close(fd)
    c.need(not os.path.lexists(path),'model durably absent');c.sync_dir(parent.parent,budget.tick)
