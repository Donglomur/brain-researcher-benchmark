"""Offline fixed-local-checkpoint AlexNet ReLU7 producer; source-only until selected.

No scientific library, checkpoint, image or numerical array is opened at import.
The actual producer is reached only by the explicitly qualified prepare-features
command. Its strict manifest is consumed by the unchanged original builders.
"""
import hashlib
import io
import json
import math
import os
import platform
import signal
import stat
from pathlib import Path
from .common import capture,parse,encoded,sha,require,keys,integer,finite,stamp,descriptor,diagnostic_type

RECIPE={
    'schema':'neural055-fixed-alexnet-relu7-recipe-v1','representation_name':'alexnet_torchvision_0.11.2_relu7_4096',
    'torchvision':'0.11.2','torch':'1.10.1','device':'cpu','seed':20200220,'evaluation_mode':True,
    'pretrained_constructor':False,'checkpoint_loading':'exact_local_state_dict_strict_cpu_no_download',
    'image_conversion':'PIL_RGB','resize':[224,224],'interpolation':'torchvision0.11.2_PIL_default_bilinear',
    'tensor_conversion':'torchvision0.11.2_ToTensor','normalization_mean':[0.485,0.456,0.406],
    'normalization_std':[0.229,0.224,0.225],'network_path':'features; avgpool6x6; view(batch,-1); classifier0_through5_inclusive',
    'selected_layer':'ReLU7','features':4096,'one_image_per_forward':True,'output_dtype':'<f4',
    'training_rows':16540,'test_rows':200,'row_order':'exact_original_image_metadata_lists',
    'trained_transform_scope':'fixed_checkpoint_no_dataset_fitted_transform_no_EEG',
    'original_extractor_sha256':'8dcb281793e567e53ec891ae27ef13b0c0a7c60d4c46e6569a17156901eceaef',
    'official_alexnet_source_sha256':'4d878918c40544618f613fba5c2d2484b6659b58f7308b3d198cbdda78efad56'}

def validate_plan(plan,source):
    keys(plan,('schema','task_id','source_manifest','limits','trust','checkpoint','image_metadata','image_index',
               'image_root','environment','runtime_qualification','closure_reserve_seconds'))
    require(plan['schema']=='neural055-image-feature-preparation-plan-v1' and plan['task_id']=='NEURAL-055','explicit feature preparation plan')
    require(plan['source_manifest']['sha256']==source.identity,'exact complete feature source')
    for name in ('checkpoint','image_metadata','image_index'):descriptor(plan[name])
    require(0<plan['checkpoint']['bytes']<=536870912,'bounded local fixed checkpoint')
    root=Path(plan['image_root']);require(root.is_absolute() and '..'not in root.parts and all(not x.is_symlink()for x in(root,*root.parents)),'explicit unlinked local image root')
    env=plan['environment'];keys(env,('python','torch','torchvision','numpy','Pillow','device','memory_bytes','network_isolated','maximum_image_bytes','maximum_image_pixels'))
    require(env['torchvision']==RECIPE['torchvision'] and env['torch']==RECIPE['torch'] and env['device']=='cpu','fixed original library/device semantics')
    require(all(type(env[k])is str and env[k]for k in('python','numpy','Pillow')),'exact remaining runtime versions')
    integer(env['memory_bytes'],1073741824,17179869184);integer(env['maximum_image_bytes'],1,16777216);integer(env['maximum_image_pixels'],1,20000000)
    require(env['network_isolated']is True,'independently qualified offline operator environment')
    reserve=finite(plan['closure_reserve_seconds'],True);require(reserve<plan['limits']['wall_seconds'],'closure reserve inside original lifetime')
    return root,env

def original_metadata_digest(metadata):
    # Exact canonicalization in retained build_case.py:65, including its
    # default ensure_ascii=True. Common journal JSON intentionally differs.
    return sha(json.dumps(metadata,sort_keys=True,separators=(',',':')).encode())

def validate_image_index(value,metadata,maximum_image_bytes):
    keys(value,('schema','image_metadata_sha256','training','test'))
    require(value['schema']=='neural055-ordered-original-image-index-v1' and value['image_metadata_sha256']==original_metadata_digest(metadata),'exact original image ordering subject')
    seen=set()
    for label,field,size in(('training','train_img_files',16540),('test','test_img_files',200)):
        rows=value[label];require(type(rows)is list and len(rows)==size,'complete original image partition')
        for i,row in enumerate(rows):
            keys(row,('image_id','file'));require(row['image_id']==metadata[field][i],'exact row-to-image identity')
            descriptor(row['file']);require(0<row['file']['bytes']<=maximum_image_bytes,'bounded complete image source')
            name=row['file']['path'];require(name not in seen,'no duplicated image file across ordered partitions');seen.add(name)
    return value

class FeatureStream:
    """Sequential finite numeric output; actual returned prefixes remain charged."""
    def __init__(self,journal,name,expected_bytes):
        self.journal=journal;self.budget=journal.budget;self.carrier=journal.carrier
        self.path=journal.root/name;self.expected=expected_bytes;self.fd=None;self.first=None;self.hasher=hashlib.sha256()
        self.record={'path':name,'expected_bytes':expected_bytes,'observed_bytes':0,'sha256':None,'closed':False,'status':'opening'}
        journal.records.append(self.record);self.budget.admit_write(expected_bytes)
        try:self.fd=os.open(self.path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);self.budget.file_created()
        except BaseException as exc:self.fail(exc,'feature-open');raise
    def fail(self,exc,stage):
        if self.first is None:self.first=exc
        self.carrier.fail(exc,stage);self.record['status']='failed'
    def write(self,body):
        try:
            require(type(body)is bytes,'plain sequential feature bytes')
            require(self.record['observed_bytes']+len(body)<=self.expected,'original output extent')
            self.budget.check('before feature write');self.record['status']='writing';pos=0
            while pos<len(body):
                try:n=os.write(self.fd,memoryview(body)[pos:])
                except BaseException as exc:
                    n=self.budget.failed_write('feature:'+self.record['path'],exc,len(body)-pos)
                    if type(n)is int and 0<n<=len(body)-pos:self._returned(body[pos:pos+n]);pos+=n
                    elif n is None:self.record['unknown_write_extent']=True
                    raise
                n=self.budget.write_count('feature:'+self.record['path'],n,len(body)-pos)
                if n is None:self.record['unknown_write_extent']=True
                require(n is not None and n>0,'positive actual feature write')
                self._returned(body[pos:pos+n]);pos+=n;self.budget.check('after feature write')
            return len(body)
        except BaseException as exc:self.fail(exc,'feature-write');raise
    def _returned(self,part):
        self.hasher.update(part);self.record['observed_bytes']+=len(part);self.budget.written(len(part))
    def close(self,complete):
        if self.fd is None:return
        try:
            if complete:
                require(self.record['observed_bytes']==self.expected,'complete original feature output')
                os.fsync(self.fd);s=os.fstat(self.fd);require(s.st_size==self.expected and stamp(s)==stamp(self.path.lstat()),'same original feature file')
                self.budget.check('after feature fsync')
        except BaseException as exc:self.fail(exc,'feature-finalize')
        finally:
            try:os.close(self.fd);self.record['closed']=True
            except BaseException as exc:self.fail(exc,'feature-close');self.budget.uncertain('feature:'+self.record['path'],'managed_descriptor_closure',exc,descriptor=self.fd)
            self.fd=None;self.record['sha256']=self.hasher.hexdigest()
            if not complete and self.record['status']!='failed':self.record['status']='incomplete_not_admitted'
        if complete and self.first is None:
            try:
                d=os.open(self.path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
                directory_error=None
                try:os.fsync(d)
                except BaseException as exc:directory_error=exc;self.fail(exc,'feature-directory-sync')
                finally:
                    try:os.close(d)
                    except BaseException as exc:
                        self.budget.uncertain('feature-directory:'+self.record['path'],'managed_descriptor_closure',exc,descriptor=d)
                        self.fail(exc,'feature-directory-close')
                        if directory_error is None:directory_error=exc
                if directory_error is not None:raise directory_error
                self.budget.check('after feature directory close');self.record['status']='complete'
            except BaseException as exc:self.fail(exc,'feature-directory-finalize')
        if self.first is not None:raise self.first
    def descriptor(self):
        require(self.record['status']=='complete' and self.record['closed'],'complete admitted feature file only')
        return {'path':self.record['path'],'bytes':self.record['observed_bytes'],'sha256':self.record['sha256']}

def fixed_runtime(env,budget):
    # This changes only the newly selected standalone preparation process. These
    # ceilings do not replace independent offline/native runtime qualification.
    import resource
    require(platform.python_version()==env['python'],'exact Python runtime')
    for name,bound in((resource.RLIMIT_AS,env['memory_bytes']),(resource.RLIMIT_CPU,max(1,math.ceil(budget.limits['cpu_seconds']+budget.cpu_origin)))):
        soft,hard=resource.getrlimit(name);require(hard==resource.RLIM_INFINITY or bound<=hard,'selected limit within existing hard ceiling')
        if soft!=resource.RLIM_INFINITY:bound=min(bound,soft)
        resource.setrlimit(name,(bound,hard))
    import torch
    import torchvision
    import numpy as np
    import PIL
    require(torch.__version__.split('+')[0]==env['torch'] and torchvision.__version__.split('+')[0]==env['torchvision'],'exact qualified torch/torchvision')
    require(np.__version__==env['numpy'] and PIL.__version__==env['Pillow'],'exact qualified numeric/image libraries')
    torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.manual_seed(RECIPE['seed']);torch.use_deterministic_algorithms(True)
    require(torch.get_default_dtype()==torch.float32,'fixed float32 image network')
    return torch,torchvision,np

def produce(plan,operator_root,source,authority,journal,budget):
    root,env=validate_plan(plan,source);first=None;streams=[];records=[];result=None;old_handler=None;timer_owned=False
    subject={'source':source.identity,'checkpoint':plan['checkpoint'],'image_metadata':plan['image_metadata'],'image_index':plan['image_index'],
             'recipe':RECIPE,'environment':env,'limits':plan['limits'],'network_downloads':False,'training_or_EEG_fitting':False}
    authority.verify(plan['runtime_qualification'],'fixed_image_feature_preparation_runtime',subject)
    require(authority.trust['source_identity']==source.identity,'same independently qualified preparation source')
    work_end=budget.deadline-plan['closure_reserve_seconds']
    def guard(stage):budget.check(stage,work_end)
    def expired(*_):raise TimeoutError('original feature preparation work deadline')
    try:
        guard('before actual preparation inputs')
        metadata=source.legacy_module('private/preparation/metadata_core.py').validate_metadata(parse(capture(operator_root,plan['image_metadata'],budget,8388608)))
        index=validate_image_index(parse(capture(operator_root,plan['image_index'],budget,16777216)),metadata,env['maximum_image_bytes'])
        records=[{'partition':part,'row':i,'image_id':row['image_id'],'source':row['file'],'status':'unattempted'} for part in('training','test')for i,row in enumerate(index[part])]
        # Refuse to displace an existing alarm or reset an unrelated lifetime.
        require(signal.getitimer(signal.ITIMER_REAL)==(0.0,0.0),'standalone fresh preparation alarm')
        old_handler=signal.getsignal(signal.SIGALRM);signal.signal(signal.SIGALRM,expired);timer_owned=True
        signal.setitimer(signal.ITIMER_REAL,max(0.000001,work_end-budget.clock()))
        torch,tv,np=fixed_runtime(env,budget);guard('after scientific runtime import')
        checkpoint=capture(operator_root,plan['checkpoint'],budget,536870912);guard('after exact local checkpoint capture')
        # torchvision0.11.2 only calls its downloader when pretrained=True.
        model=tv.models.alexnet(pretrained=False,progress=False)
        state=torch.load(io.BytesIO(checkpoint),map_location='cpu');model.load_state_dict(state,strict=True)
        del state,checkpoint;model.eval();guard('after strict fixed checkpoint load')
        require(len(model.classifier)==7 and isinstance(model.classifier[5],torch.nn.ReLU),'exact ReLU7 selected module')
        transform=tv.transforms.Compose([tv.transforms.Resize((224,224)),tv.transforms.ToTensor(),
                                        tv.transforms.Normalize(RECIPE['normalization_mean'],RECIPE['normalization_std'])])
        from PIL import Image
        Image.MAX_IMAGE_PIXELS=env['maximum_image_pixels']
        offset=0;outputs={}
        for partition,count in(('training',16540),('test',200)):
            header=io.BytesIO();np.lib.format.write_array_header_1_0(header,{'descr':'<f4','fortran_order':False,'shape':(count,4096)})
            raw_header=header.getvalue();require(len(raw_header)<=4096,'bounded plain numeric NPY header')
            stream=FeatureStream(journal,partition+'_features.npy',len(raw_header)+count*4096*4);streams.append(stream);stream.write(raw_header)
            for i,row in enumerate(index[partition]):
                record=records[offset+i];record['status']='started'
                try:
                    guard('before original image');raw=capture(root,row['file'],budget,env['maximum_image_bytes'])
                    with Image.open(io.BytesIO(raw))as original:
                        require(original.width*original.height<=env['maximum_image_pixels'],'bounded original image pixels')
                        with original.convert('RGB')as rgb:tensor=transform(rgb).unsqueeze(0)
                    record['forward_started']=True
                    with torch.no_grad():
                        x=model.features(tensor);x=model.avgpool(x);x=x.view(x.size(0),-1)
                        for layer in list(model.classifier.children())[:6]:x=layer(x)
                    record['forward_returned']=True
                    guard('after exact original ReLU7 path');values=x.detach().cpu().numpy()
                    require(values.shape==(1,4096) and values.dtype==np.float32 and np.isfinite(values).all(),'finite complete ReLU7 row')
                    stream.write(np.asarray(values,dtype='<f4',order='C').tobytes(order='C'))
                    record['status']='complete'
                except BaseException as exc:
                    record['status']='failed';record['first_error_type']=diagnostic_type(exc);raise
            offset+=count;stream.close(True);outputs[partition]=stream.descriptor()
        guard('after complete original feature rows')
        manifest={'schema':'neural055-image-feature-manifest-v1','training_features':outputs['training'],'test_features':outputs['test'],
                  'image_metadata_sha256':original_metadata_digest(metadata),'checkpoint_sha256':plan['checkpoint']['sha256'],
                  'extraction_recipe_sha256':sha(encoded(RECIPE)),'representation_name':RECIPE['representation_name'],
                  'trained_transform_scope':RECIPE['trained_transform_scope']}
        require(not budget.unknown,'all original feature costs and closure known')
        journal.json('FEATURE_RECIPE.json',RECIPE);journal.json('FEATURE_MANIFEST.json',manifest)
        result={'schema':'neural055-complete-fixed-feature-production-v1','feature_manifest':'FEATURE_MANIFEST.json',
                'recipe':RECIPE,'actual_rows':{'training':16540,'test':200},'features':4096,'subject':subject,
                'actual_feature_forward_calls':16740,'investigator_model_calls':0,
                'no_EEG_or_target_access':True,'scientific_feature_extraction_performed':True,'benchmark_score_computed':False}
    except BaseException as exc:
        first=exc;journal.carrier.fail(exc,'original-feature-production')
        for row in records:
            if row['status']=='unattempted':row['status']='unattempted_after_original_failure'
    finally:
        # Keep the first operation error before close, timer and publication.
        for stream in streams:
            if stream.fd is not None:
                try:stream.close(False)
                except BaseException as exc:
                    journal.carrier.fail(exc,'feature-stream-cleanup')
                    if first is None:first=exc
        if timer_owned:
            for label,fn in(('alarm-disable',lambda:signal.setitimer(signal.ITIMER_REAL,0)),('handler-restore',lambda:signal.signal(signal.SIGALRM,old_handler))):
                try:fn()
                except BaseException as exc:
                    journal.carrier.fail(exc,label)
                    if first is None:first=exc
        try:
            journal.json('FEATURE_OPERATIONS.json',{'schema':'neural055-original-feature-operations-v1','rows':records,
                         'first_error_type':None if first is None else diagnostic_type(first),'scientific_qualification_claimed':False})
            budget.check('after original feature cleanup and publication')
        except BaseException as exc:
            journal.carrier.fail(exc,'feature-original-publication')
            if first is None:first=exc
    if first is not None:raise first
    return result

def execute(plan,operator_root,source_root,manifest_descriptor,output,origin,cpu_origin,bootstrap_read_bytes=0):
    """Actual bounded operator route using the original clock/error journal."""
    from .budget import Budget
    from .journal import Journal
    from .source import Sources
    from .authority import Authority
    from .common import FailureCarrier
    from .central import CompleteFailure
    budget=Budget(origin,plan['limits'],cpu_origin=cpu_origin);budget.read(bootstrap_read_bytes)
    carrier=FailureCarrier();journal=Journal(output,budget,carrier);source=None;first=None;result=None
    try:
        source=Sources(source_root,manifest_descriptor,budget)
        authority=Authority(operator_root,plan['trust'],budget)
        result=produce(plan,operator_root,source,authority,journal,budget)
        budget.check('before complete feature-entry finalization')
    except BaseException as exc:first=exc;carrier.fail(exc,'feature-entry')
    try:
        if source is not None:source.current()
        costs=journal.json('ORIGINAL_COSTS.json',budget.snapshot());budget.check('after feature-source/cost closure')
    except BaseException as exc:
        carrier.fail(exc,'feature-entry-finalization');costs={'status':'unavailable','original_counters_retained':True}
        if first is None:first=exc
    terminal={'schema':'neural055-original-complete-terminal-v1','status':'complete'if first is None else'unavailable',
              'mode':'prepare-features','result':result,'errors':carrier.document(),'costs':costs,
              'all_original_objects_retained':True,'no_failure_replaced_with_success':True}
    durable=journal.terminal(terminal)
    if first is not None or not durable:
        failure=CompleteFailure(carrier,None,terminal,journal)
        if first is not None:raise failure from first
        raise failure
    return terminal
