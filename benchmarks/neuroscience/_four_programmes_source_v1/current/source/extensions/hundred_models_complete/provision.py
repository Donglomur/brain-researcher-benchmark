"""Matched resource views. Copies actual admitted files; no data is read at import."""
import hashlib
import os
from pathlib import Path
from .guard import need,ordinary,encoded,bare,Publisher
from .array_io import verify_file

def provision(source_root,files,common_source,b_source,arm,output,budget):
    need(arm in ('A','B'),'two matched paper/data access arms')
    files=list(files);common_source=list(common_source);b_source=list(b_source)
    need(all(x['role'] in ('paper','stimuli','neural_derivative','identity_metadata','task_instruction','checkpoint','preprocessing_contract') for x in files),'common input roles exclude reference answers')
    need(all(x['role'] in ('public_interface','environment_specification','dependency_source') for x in common_source),'common support contains no author solutions')
    need(all(x['role']=='author_code' for x in b_source),'only frozen author code differs between arms')
    rows=files+common_source+(b_source if arm=='B' else [])
    need(len({x['target'] for x in rows})==len(rows),'unique full visible namespace')
    publisher=Publisher(output,budget);copied=[]
    try:
        for row in rows:
            d=row['source'];src=verify_file(source_root,d,budget);dest=ordinary(publisher.root,row['target']);dest.parent.mkdir(parents=True,exist_ok=True)
            budget.charge('read_bytes',d['bytes']+1);budget.charge('write_bytes',d['bytes']);h=hashlib.sha256();n=0
            with src.open('rb') as inp,dest.open('xb') as out:
                while True:
                    budget.check();block=inp.read(min(65536,d['bytes']+1-n))
                    if not block:break
                    n+=len(block);need(n<=d['bytes'],'source copy extent');h.update(block);need(out.write(block)==len(block),'full resource write')
                out.flush();os.fsync(out.fileno())
            need(n==d['bytes'] and h.hexdigest()==d['sha256'],'actual copied resource identity');dest.chmod(0o400)
            verify_file(source_root,d,budget);copied.append({'target':row['target'],'source':d,'visibility':'B_author_code' if row in b_source else 'common'})
        budget.check();return publisher.write('VISIBLE_INPUTS.json',encoded({'arm':arm,'files':copied,'same_common_resource_digest':bare(encoded(list(files)+list(common_source))),'external_isolation_required':True,'private_precomputed_answers_supplied':False}))
    except BaseException as error:error.known_output_prefix={'directory':str(publisher.root),'copied':copied,'current_copy_may_be_partial':True,'budget':budget.snapshot()};raise
