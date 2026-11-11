"""Source-owned complete authentic preparation route, never executed in BUILD.

Original source conversion remains trusted isolated ingestion, not a general
pickle sandbox. The exact existing publisher pins are preserved.
"""
from pathlib import Path
from .core import need,read_json,capture,write_new,save,descriptor,digest
from .runtime import tree
from .protocol import PEOPLE

def materialize(rows,destination,budget):
    root=Path(destination);root.mkdir(mode=0o700)
    need(type(rows)is list and len(rows)>0,'explicit complete input descriptors')
    names=set()
    for row in rows:
        name=row['name'];need(type(name)is str and '/' not in name and '\\' not in name and name not in ('','.','..') and name not in names,'single unique staging name')
        names.add(name);raw=capture(row['path'],row['bytes'],row,budget);write_new(root/name,raw,budget)
    return root

def prepare(inputs,source,destination,dispatcher):
    """Uses all ten source archives and both image archives; no small substitute."""
    b=dispatcher.budget;out=Path(destination);out.mkdir();runtime=dispatcher.profile
    need(set(inputs['eeg'])==set(PEOPLE),'all ten exact archives')
    need(set(inputs['images'])=={'training_images','test_images'},'both full original image archives')
    pins=read_json(Path(source)/'legacy/operator/SOURCE_BINDINGS.json',budget=b)
    for key,row in [*inputs['eeg'].items(),*inputs['images'].items()]:
        need({k:row[k] for k in ('bytes','sha256')}=={k:pins['assets'][key][k] for k in ('bytes','sha256')},'exact publisher archive')
    staged=out/'staged';staged.mkdir();history=[]
    for person in PEOPLE:
        files=[{**inputs['eeg'][person],'name':'source.zip'},{**inputs['acquisition'],'name':'acquisition.json'}]
        i=materialize(files,out/(person+'-input'),b)
        cmd=[runtime['python'],'/source/legacy/operator/prepare_source.py','--archive','/input/0/source.zip',
             '--person',person,'--acquisition','/input/0/acquisition.json','--output','/output/staged']
        run=dispatcher.run(cmd,[i],source,out/(person+'-process'),'prepare')
        need(run['complete'],'full archive staging failed')
        product=Path(run['outputs']['root'])/'staged';need(product.is_dir(),'staged source product')
        # Whole staged output is copied from the authenticated original product.
        target=staged/person;target.mkdir()
        for row in tree(product,runtime['output_bytes'],100,b)['members']:
            need('/' not in row['relative'],'flat exact staged output')
            write_new(target/row['relative'],capture(row['path'],row['bytes'],row,b),b)
        history.append(run)
    checkpoint=read_json(inputs['checkpoint_binding']['path'],expected=inputs['checkpoint_binding'],budget=b)
    need(checkpoint['schema']=='neural056_checkpoint_v1' and
         {k:checkpoint[k] for k in ('bytes','sha256')}=={k:inputs['checkpoint'][k] for k in ('bytes','sha256')},
         'exact externally selected ImageNet checkpoint')
    files=[{**inputs['images']['training_images'],'name':'training.zip'},{**inputs['images']['test_images'],'name':'test.zip'},
           {**inputs['image_metadata'],'name':'metadata.json'},{**inputs['acquisition'],'name':'acquisition.json'},
           {**inputs['checkpoint'],'name':'checkpoint.pt'},{**inputs['checkpoint_binding'],'name':'checkpoint.json'}]
    i=materialize(files,out/'feature-input',b)
    cmd=[runtime['python'],'/source/legacy/operator/features.py','--images-train','/input/0/training.zip','--images-test','/input/0/test.zip',
      '--metadata','/input/0/metadata.json','--acquisition','/input/0/acquisition.json','--checkpoint','/input/0/checkpoint.pt',
      '--binding','/input/0/checkpoint.json','--output','/output/features']
    run=dispatcher.run(cmd,[i],source,out/'feature-process','feature');need(run['complete'],'complete feature extraction failed');history.append(run)
    features=Path(run['outputs']['root'])/'features'
    meta=materialize([{**inputs['image_metadata'],'name':'metadata.json'}],out/'metadata-input',b)
    cmd=[runtime['python'],'/source/legacy/operator/build_panel.py','--staged','/input/0','--features','/input/1',
         '--metadata','/input/2/metadata.json','--output','/output/panel']
    run=dispatcher.run(cmd,[staged,features,meta],source,out/'panel-process','prepare')
    need(run['complete'],'full panel construction failed');history.append(run)
    save(out/'PREPARATION_HISTORY.json',history,b)
    return Path(run['outputs']['root'])/'panel',history

