#!/usr/bin/env python3
"""Prepare all six acquisitions without fitting or computing prediction errors."""
import argparse
import hashlib
import io as streams
import os
from pathlib import Path
import shutil
import stat
import time
import zipfile
import numpy as np
import delivery_io as io
from array_io import put_array
from preparation_core import summarize,training_scale,select_training,PROTOCOL,ORDERS
from scorer_core import fingerprint,public_contract

SOURCE_PIN={'bytes':481579348,'sha256':'652bddde5091218819a0fd4be2e1e7bed03d2cca67a631bb7d135ce7b314b5e6'}
SHAPES=[(251,50,240),(203,50,240),(139,50,240),(114,50,240),(257,50,200),(168,50,200)]


def original_means(source,members):
    io.need(members['raw_source']['bytes']==SOURCE_PIN['bytes'] and
            members['raw_source']['sha256']==SOURCE_PIN['sha256'], 'Original source generation')
    io.need(type(members['members']) is list and len(members['members']) == 12,
            'Twelve source-member declarations; duplicates cannot be hidden')
    declarations={r['name']:r for r in members['members']}
    names=['panelDE_expt%d_F_%s'%(i,order.lower()) for i in range(1,7) for order in ORDERS]
    io.need(len(declarations)==12 and set(declarations)==set(names), 'All and only twelve DE condition tensors')
    source=io.regular(source);fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    results=[];provenance=[]
    with os.fdopen(fd,'rb') as stream:
        before=os.fstat(stream.fileno())
        io.need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==SOURCE_PIN['bytes'], 'Exact ordinary original archive')
        digest=hashlib.sha256()
        for block in iter(lambda:stream.read(1048576),b''):digest.update(block)
        io.need(digest.hexdigest()==SOURCE_PIN['sha256'], 'Whole-source integrity before decoding')
        stream.seek(0)
        with zipfile.ZipFile(stream) as archive:
            io.need(len(archive.namelist())==len(set(archive.namelist())), 'Unique archive member names')
            for i in range(1,7):
                for order in ORDERS:
                    name='panelDE_expt%d_F_%s'%(i,order.lower());d=declarations[name];entry=archive.getinfo(name+'.npy')
                    io.need(entry.file_size==d['member_bytes'] and entry.compress_size==d['member_compressed_bytes'] and
                            '%08x'%entry.CRC==d['member_crc32_hex'] and not(entry.flag_bits&1), 'Exact selected source member')
                    io.need(entry.file_size<=25000000,'Bounded one-member memory')
                    body=archive.read(entry) # complete decompression verifies ZIP CRC
                    io.need(hashlib.sha256(body[:d['header_bytes']]).hexdigest()==d['header_sha256'], 'Pinned NPY header')
                    array=np.load(streams.BytesIO(body),allow_pickle=False)
                    io.need(type(array) is np.ndarray and tuple(array.shape)==SHAPES[i-1] and array.dtype.str=='<f8', 'Exact selected tensor')
                    means,counts=summarize(array,np)
                    results.append({'acquisition':'acquisition_%d'%i,'order':order,'means':means,'counts':counts})
                    provenance.append({'member':name+'.npy',**io.pin(body),'shape':list(array.shape),
                        'infinite_values':0,'missing_trial_samples':int(array.size-np.isfinite(array).sum()),
                        'empty_cell_frames':int((counts==0).sum()),'cells':int(array.shape[0]),'trials_per_condition':50,
                        'observed_cells':int((counts>0).any(axis=1).sum()),
                        'unobserved_cells':[{'row_index0':int(i),'reason':'no_finite_source_trial_at_any_frame'}
                             for i in np.flatnonzero(~(counts>0).any(axis=1))]})
                    del array,body
        after=os.fstat(stream.fileno())
        io.need(all(getattr(before,k)==getattr(after,k) for k in ['st_dev','st_ino','st_size','st_nlink','st_mtime_ns','st_ctime_ns']), 'Source remained stable')
    return results,provenance


def prepare(source,members_path,output,max_bytes):
    started=time.monotonic();members=io.json_file(members_path,100000)
    pool,provenance=original_means(source,members)
    scales={(r['acquisition'],r['order']):training_scale(r['means'],r['counts'],np) for r in pool}
    source_code=[]
    for name in ['prepare.py','preparation_core.py']:
        path=Path(__file__).parent/name;source_code.append({'name':name,**io.pin(io.read(path,100000))})
    generation=fingerprint({'protocol':PROTOCOL,'source_pin':SOURCE_PIN,'source_code':source_code,
                            'members_metadata':io.pin(io.read(members_path,100000))})
    panel={'schema':'neural037-panel-v1','generation':generation,'contexts':[]}
    for r in pool:
        panel['contexts'].append({'context_id':r['acquisition']+'_'+r['order'],'acquisition':r['acquisition'],
            'query_order':r['order'],'cell_keys':['cell_%04d'%i for i in range(r['means'].shape[0])],
            'frames':r['means'].shape[1]})
    panel['packet_id']=fingerprint(panel);public_contract(panel)
    # Exact array lengths plus conservative bounded JSON allowance. All source
    # support is retained; no smaller cohort is selected to meet a byte cap.
    array_total=sum(r['means'].nbytes+r['counts'].nbytes+256 for r in pool)
    required_upper=array_total*12+2000000
    io.need(type(max_bytes) is int and required_upper<=max_bytes<=150000000,'Full preparation must fit explicit cap')
    out=io.fresh(output);(out/'public').mkdir();(out/'private').mkdir();(out/'private/pool').mkdir()
    written=[]
    def put_json(relative,value):
        path=out/relative;path.parent.mkdir(parents=True,exist_ok=True)
        d=io.put(path,value,1000000);written.append({'path':relative,**d});return d
    prepared=[]
    for r in pool:
        item={'acquisition':r['acquisition'],'order':r['order'],'shape':list(r['means'].shape)}
        for kind in ['means','counts']:
            relative='private/pool/'+r['acquisition']+'_'+r['order']+'_'+kind+'.npy'
            d=put_array(out/relative,r[kind],np);written.append({'path':relative,**d})
            item[kind]={'path':relative,**d}
        prepared.append(item)
    targets={'schema':'neural037-targets-v1','packet_id':panel['packet_id'],'contexts':{}}
    for query in prepared:
        context_id=query['acquisition']+'_'+query['order'];other='CBA' if query['order']=='ABC' else 'ABC'
        target={'training_scale':scales[(query['acquisition'],other)]}
        for kind in ['means','counts']:
            target[kind]={**query[kind],'path':query[kind]['path'].removeprefix('private/')}
        targets['contexts'][context_id]=target
        viewdir='private/contexts/'+context_id
        (out/viewdir/'arrays').mkdir(parents=True)
        training=[]
        for index,row in enumerate(select_training(prepared,query['acquisition'],query['order'])):
            staged={'acquisition':row['acquisition'],'order':row['order'],'shape':row['shape']}
            for kind in ['means','counts']:
                relative='arrays/train_%02d_%s.npy'%(index,kind)
                destination=out/viewdir/relative
                # Owned ordinary copies, not hardlinks: one view can be safely
                # mounted without a writable link into another context.
                shutil.copyfile(out/row[kind]['path'],destination);destination.chmod(0o444)
                pin={k:row[kind][k] for k in ['bytes','sha256']}
                io.read(destination,pin['bytes'],pin,retain=False)
                staged[kind]={'path':relative,**pin};written.append({'path':viewdir+'/'+relative,**pin})
            training.append(staged)
        query_metadata=next(c for c in panel['contexts'] if c['context_id']==context_id)
        view={'schema':'neural037-context-v1','packet_id':panel['packet_id'],'query':query_metadata,
              'training':training,'training_scale':target['training_scale'],
              'scope':'complete-condition holdout, native source frames, no animal-transfer claim'}
        put_json(viewdir+'/input.json',view)
    put_json('public/panel.json',panel);put_json('private/targets.json',targets)
    preparation={'schema':'neural037-actual-data-only-preparation-v1','protocol':PROTOCOL,'packet_id':panel['packet_id'],
        'source_pin':SOURCE_PIN,'selected_members':provenance,'implementation':source_code,
        'acquisitions':6,'contexts':12,'source_rois':sum(s[0] for s in SHAPES),'numpy':np.__version__,
        'new_models_fit':0,'candidate_programs_run':0,'scientific_scores_computed':0,
        'elapsed_seconds':time.monotonic()-started,'new_retained_cap':max_bytes,
        'animal_map_verified':False,'physical_frame_timing_verified':False,
        'no_response_values_printed':True}
    put_json('private/PREPARATION.json',preparation)
    bindings={'schema':'neural037-prepared-bindings-v1','packet_id':panel['packet_id'],'files':written}
    binding_body=io.canonical(bindings)
    io.need(sum(r['bytes'] for r in written)+len(binding_body)<=max_bytes,'Complete retained bytes cap')
    io.put(out/'FILE_BINDINGS.json',bindings,1000000)
    return {'status':'data_only_prepared','contexts':12,'source_rois':preparation['source_rois'],
            'files':len(written)+1,'bytes':sum(r['bytes'] for r in written)+len(binding_body),
            'elapsed_seconds':preparation['elapsed_seconds'],'models_fit':0,'scientific_scores':0}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--members',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--max-output-bytes',type=int,required=True);a=p.parse_args()
    import json
    print(json.dumps(prepare(a.source,a.members,a.output,a.max_output_bytes),sort_keys=True))
