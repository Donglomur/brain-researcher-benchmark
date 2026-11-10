"""Concrete operator-owned reference and numerical worker entrypoint.

Executed only inside the qualified scientific worker boundary. No import of
submitted participant source occurs here. Missing original producers refuse
with their named source gate; an arbitrary configured callback cannot replace an original scientific method.
EEGNet and prospective Temple producers are concrete; original no-predictor
wiring and historical Temple training recipes remain unresolved.
"""
import argparse,hashlib,json,os
from pathlib import Path
from .protocol import HandleCustody,need,fields,identity,encode,decode,digest,descriptor,observation,Refusal
from .metrics import classify,BinaryRankStore,MONITOR
from .scope import CLASSES


def load_json(path):return decode(Path(path).read_bytes())
def source_pin(path):
    path=Path(path);h=hashlib.sha256();n=0
    with path.open('rb') as stream:
        while True:
            b=stream.read(1024*1024)
            if not b:break
            h.update(b);n+=len(b)
    return {'path':path.name,'bytes':n,'sha256':h.hexdigest()}


class Worker:
    def __init__(self,request,output):
        self.request=request;self.output=Path(output);self.output.mkdir(exist_ok=True);self.inputs={x['name']:Path(x['guest_root']) for x in request['inputs']};self.inputs['author_source']=Path(__file__).resolve().parent.parent/'author-source';self.artifacts=[];self.products=[]
        self.response={'schema':'eegpt_science_response_v1','request_id':request['request_id'],'status':'ok','artifacts':self.artifacts,'products':self.products,'generated_source':None,'selected_state':None,'decision':'done','diagnostics':{},'method_declaration':'independent operator-owned full EEGPT reference worker; original source qualification remains separate'}
    def json(self,name,value):
        path=self.output/name;need(not path.exists(),'one original worker product');path.write_bytes(encode(value));pin=source_pin(path);self.artifacts.append(pin);return pin
    def array(self,name,value):
        import numpy as np
        path=self.output/name;need(not path.exists(),'one original array');array=np.asarray(value);need(array.dtype.kind in 'fbiu','nonobject numerical output')
        with path.open('xb') as f:np.lib.format.write_array(f,np.asarray(array,order='C'),version=(1,0),allow_pickle=False)
        pin=source_pin(path);self.artifacts.append(pin);return pin
    def rows(self,name):
        document=load_json(self.inputs[name]/'rows.json');need(document['schema']=='eegpt_public_rows_v1' and document['rows'],'complete public capability rows')
        need(document['whole_support_identity']==identity([r['row_id'] for r in document['rows']]),'actual complete row support');return document
    def epochs(self,document):
        import numpy as np
        for row in document['rows']:
            s=row['signal'];path=Path(s['path']);pin=source_pin(path);need(pin['bytes']==s['bytes'] and pin['sha256']==s['sha256'],'actual original signal capability bytes')
            x=np.load(path,allow_pickle=False);need(x.dtype.kind=='f' and list(x.shape)==s['shape'] and np.isfinite(x).all(),'complete canonical signal-only float epoch');yield x,row['label'],row['row_id'],row['person_id']
    def recipe(self):
        need('recipes' in self.inputs,'qualified exact original reference recipe capability required')
        document=load_json(self.inputs['recipes']/'REFERENCE_RECIPES.json');spec=self.request['scope'];key=identity({k:spec[k] for k in ('mode','policy_id','dataset','outer_fold','method')});need(key in document['recipes'],'complete exact selected scientific reference recipe');row=decode(encode(document['recipes'][key]));digest(row['qualification'])
        if 'fit' in row and 'seed' in row['fit']:
            if row['fit']['seed']=='request_declared_seed':row['fit']['seed']=self.request['seed']
            else:need(row['fit']['seed']==self.request['seed'],'original selected recipe seed matches actual declared stream')
        return row
    def feature_matrix(self,document):
        import numpy as np
        from .spectral import features
        result=[];labels=[];people=[]
        for x,y,_,person in self.epochs(document):
            rate=document['rows'][len(result)]['sampling_hz'];result.append(features(x[None,:,:],rate)[0]);labels.append(y);people.append(person)
        return np.stack(result),np.asarray(labels),people
    def fit_spectral(self,recipe):
        import numpy as np
        from .spectral import fit
        train=self.rows('train');validation=self.rows('validation');x,y,_=self.feature_matrix(train);v,z,people=self.feature_matrix(validation)
        state=fit(x,y,v,z,CLASSES[self.request['scope']['dataset']],scratch=self.output)
        arrays={**{'normalizer_'+k:value for k,value in state['normalizer'].items()},'beta':state['beta']};path=self.output/'state.npz';np.savez(path,**arrays);state_pin=source_pin(path);self.artifacts.append(state_pin)
        metadata={'kind':'fixed_spectral_ridge','selected_penalty':state['penalty'],'selected_validation_monitor':state['validation_monitor'],'training_rows':len(x),'validation_rows':len(v),'recipe':recipe,'normalizer_fitted_on_training_only':True,'feature_bands':[[1,4],[4,8],[8,13],[13,30],[30,45]],'all_configuration_metrics':state.get('all_configuration_metrics',[]),'seed_dependence':'deterministic given exact data; three logical repetitions are not independent fits'}
        meta=self.json('STATE.json',metadata);self.state_response([state_pin['path'],meta['path']],train,recipe,'fixed_features_no_pretrained_state')
        from .family_products import training_products
        training_products(self,self.request['output_contract']['products'],metadata)
    def state_response(self,files,train,recipe,initialization):
        self.response['generated_source']={'reuse':self.request['source_identity']};self.response['selected_state']={'files':files,'initialization':initialization,'train_support':train['whole_support_identity'],'recipe':identity(recipe),'rng':self.request['seed'],'trainability':recipe.get('trainability','all fitted ridge coefficients and training normalizer'),'state_change':'actual independent fitting performed in this original process','fit_kind':'new_fit'};self.response['decision']='select'
    def loader(self,document,batch_size,shuffle):
        import torch
        outer=self
        class EpochDataset(torch.utils.data.Dataset):
            def __len__(self):return len(document['rows'])
            def __getitem__(self,index):
                row=document['rows'][index];single={**document,'rows':[row]};x,y,_,_=next(outer.epochs(single));return torch.as_tensor(x,dtype=torch.float32),torch.as_tensor(-1 if y is None else y,dtype=torch.long)
        generator=torch.Generator();generator.manual_seed(self.request['seed']);return torch.utils.data.DataLoader(EpochDataset(),batch_size=batch_size,shuffle=shuffle,num_workers=0,generator=generator,drop_last=False)
    def fit_neural(self,recipe):
        import torch
        from .neural_kernel import downstream_model,fit_downstream
        train=self.rows('train');validation=self.rows('validation');need('reference_parent' in self.inputs or recipe['architecture']['checkpoint_role']=='trained_random_init','actual qualified original parent state, never nonexistent pretrained fallback')
        initial=None
        if 'reference_parent' in self.inputs:
            parent=load_json(self.inputs['reference_parent']/'STATE.json');initial=torch.load(self.inputs['reference_parent']/parent['encoder_state'],map_location='cpu',weights_only=True)
        model=downstream_model(self.inputs['author_source'],recipe['source_pins'],recipe['architecture'],initial);train_loader=self.loader(train,recipe['batch_size'],True);validation_loader=self.loader(validation,recipe['batch_size'],False);records=[];self._epoch=0
        def validation_reduce(rows):
            self._epoch+=1;rank=BinaryRankStore(self.output/('epoch-rank-%04d.sqlite'%self._epoch)) if CLASSES[self.request['scope']['dataset']]==2 else None
            with HandleCustody('original_validation_rank') as owned:
                if rank is not None:owned.own(rank,'rank_store')
                return classify(rows, CLASSES[self.request['scope']['dataset']], rank_store=rank)
        def save_epoch(epoch,model,optimizer,scheduler):
            path=self.output/('epoch-%04d.pt'%epoch);torch.save({'state_dict':model.state_dict(),'optimizer':optimizer.state_dict(),'scheduler':scheduler.state_dict()},path);pin=source_pin(path);self.artifacts.append(pin);return pin
        result=fit_downstream(model,train_loader,validation_loader,recipe['fit'],validation_reduce=validation_reduce,save_epoch=save_epoch,record_epoch=records.append)
        from .neural_kernel import architecture_census
        metadata={'kind':'eegpt_downstream','actual_architecture':architecture_census(model,recipe=recipe),'recipe':recipe,'selected_state':result['selected']['state']['path'],'all_epoch_selection_records':records,'actual_optimizer_membership':result['optimizer_membership'],'training_support':train['whole_support_identity'],'validation_support':validation['whole_support_identity'],'parent':None if initial is None else parent}
        meta=self.json('STATE.json',metadata);self.state_response([meta['path'],*[r['path'] for r in self.artifacts if r['path'].endswith('.pt')]],train,recipe,metadata['parent'])
        from .family_products import training_products
        training_products(self,self.request['output_contract']['products'],metadata)
    def fit_legacy(self,recipe):
        import torch
        from .legacy_reference import build_original_class,fit_original
        train=self.rows('train');validation=self.rows('validation');spec=self.request['scope'];model,binding=build_original_class(self.inputs['author_source'],spec['method'],spec['dataset'],recipe['class_binding']);result=fit_original(model,self.loader(train,recipe['batch_size'],True),self.loader(validation,recipe['batch_size'],False),recipe['fit'],self.output)
        states=[]
        for row in result['all_epoch_records']:
            pin=source_pin(row['checkpoint']);self.artifacts.append(pin);states.append(pin['path'])
        from .neural_kernel import architecture_census
        metadata={'kind':'retained_original_class','actual_architecture':architecture_census(model,recipe=recipe),'recipe':recipe,'binding':binding,'selected_state':Path(result['selected_checkpoint']).name,'all_epoch_selection_records':result['all_epoch_records'],'historical_parity':False};meta=self.json('STATE.json',metadata);self.state_response([meta['path'],*states],train,recipe,recipe['class_binding']['checkpoint_literal_bindings'])
        from .family_products import training_products
        training_products(self,self.request['output_contract']['products'],metadata)
    def predict(self):
        state_root=self.inputs['fitted'];state=load_json(state_root/'STATE.json');role='query' if 'query' in self.inputs else 'validation';document=self.rows(role);rows=document['rows'];classes=CLASSES[self.request['scope']['dataset']]
        if state['kind']=='temple_reference_v1':need(self.request['scope']['mode']=='P','prospective Temple state cannot serve unresolved historical H or out-of-scope I')
        if state['kind']=='arl_eegnet_v1':need(self.request['scope']['mode']=='I','EEGNet is the required I control')
        import numpy as np
        if state['kind']=='arl_eegnet_v1':
            from .eegnet_reference import predict
            probabilities=predict(self,state,document);logits=None
        elif state['kind']=='temple_reference_v1':
            from .temple_reference import predict
            probabilities=predict(self,state_root,state,document);logits=None
        elif state['kind']=='fixed_spectral_ridge':
            from .spectral import predict
            with np.load(state_root/'state.npz',allow_pickle=False) as archive:model={'normalizer':{k[11:]:archive[k] for k in archive.files if k.startswith('normalizer_')},'beta':archive['beta']}
            x,_,_=self.feature_matrix(document);probabilities=predict(model,x);logits=None
        else:
            import torch
            if state['kind']=='eegpt_downstream':
                from .neural_kernel import downstream_model,semantic_probabilities
                recipe=state['recipe'];initial=None
                if state['parent'] is not None:
                    need('reference_parent' in self.inputs,'same original encoder constructor resource preserved for inference');initial=torch.load(self.inputs['reference_parent']/state['parent']['encoder_state'],map_location='cpu',weights_only=True)
                model=downstream_model(self.inputs['author_source'],recipe['source_pins'],recipe['architecture'],initial);model.load_state_dict(torch.load(state_root/state['selected_state'],map_location='cpu',weights_only=True)['state_dict']);binary4=recipe['architecture']['source_binary4']
            elif state['kind']=='retained_original_class':
                from .legacy_reference import build_original_class
                from .neural_kernel import semantic_probabilities
                recipe=state['recipe'];spec=self.request['scope'];model,_=build_original_class(self.inputs['author_source'],spec['method'],spec['dataset'],recipe['class_binding']);model.load_state_dict(torch.load(state_root/state['selected_state'],map_location='cpu',weights_only=True)['state_dict']);binary4=recipe['source_binary4']
            else:raise Refusal('unrecognized actual fitted state kind')
            model.eval();all_logits=[]
            with torch.no_grad():
                for x,_ in self.loader(document,recipe['batch_size'],False):
                    value=model(x);value=value[-1] if isinstance(value,tuple) else value;all_logits.append(value.detach().cpu())
            logits=torch.cat(all_logits,dim=0);probabilities=semantic_probabilities(logits,source_binary4=binary4).double().numpy();logits=logits.double().numpy()
        need(probabilities.shape==(len(rows),classes) and np.isfinite(probabilities).all(),'complete real prediction population')
        raw_logits=None if logits is None else self.array('source_logits.npy',logits.astype('<f8'));raw_argmax=None if logits is None or logits.shape[1]!=4 or classes!=2 else self.array('source_argmax.npy',logits.argmax(axis=1).astype('<f8')[:,None])
        prob=self.array('probabilities.npy',probabilities.astype('<f8'));metadata={'probabilities':prob,'row_ids':[r['row_id'] for r in rows],'class_ids':list(range(classes)),'support_identity':document['whole_support_identity'],'role':role};self.json('PREDICTIONS.json',metadata)
        for expected in self.request['output_contract']['products']:
            if type(expected) is str:continue
            need(expected['type']=='T03','nonclassification diagnostics require their real independent producer call');body={'probabilities':'probabilities','row_ids':metadata['row_ids'],'class_ids':metadata['class_ids'],'logits':None,'source_auxiliary':None,'mapping':expected['support']['mapping']};arrays={'probabilities':prob}
            if expected['support'].get('source_auxiliary')=='bcic2b_original_four_logits':
                need(raw_logits is not None and raw_argmax is not None,'actual original full4-logit2B output preserved, never reconstructed from binary probabilities');arrays.update({'source_logits':raw_logits,'source_argmax':raw_argmax});body['logits']='source_logits';body['source_auxiliary']={'kind':'bcic2b_original_four_logits','original_argmax':'source_argmax','semantic_positive_column':1,'semantic_negative_probability':'one_minus_positive_probability','native_argmax_not_binary_argmax':True}
            self.products.append({'schema':'eegpt_product_v1','product_id':expected['product_id'],'type':'T03','status':'complete','scope':expected['scope'],'parents':expected['parents'],'support_identity':expected['support_identity'],'arrays':arrays,'body':body,'reason':None})
        self.response['diagnostics']={'prediction_manifest':'PREDICTIONS.json','full_rows':len(rows),'source_four_logit_auxiliary_observed':raw_argmax is not None}
    def reduce_validation(self):
        import numpy as np
        document=self.rows('validation');prediction=load_json(self.inputs['predictions']/'PREDICTIONS.json');rows=document['rows'];need(prediction['role']=='validation' and prediction['row_ids']==[r['row_id'] for r in rows] and prediction['support_identity']==document['whole_support_identity'],'actual complete same-fold validation prediction support')
        pin=prediction['probabilities'];path=self.inputs['predictions']/pin['path'];need(source_pin(path)==pin,'actual original validation probability bytes');p=np.load(path,allow_pickle=False);classes=CLASSES[self.request['scope']['dataset']];need(p.shape==(len(rows),classes),'full validation class axes')
        def reduce(indices,name):
            rank=BinaryRankStore(self.output/(name+'.sqlite')) if classes==2 else None
            with HandleCustody('original_validation_rank') as owned:
                if rank is not None:owned.own(rank,'rank_store')
                return classify(((rows[i]['label'], p[i].tolist(), 1) for i in indices), classes, rank_store=rank)
        metrics=reduce(range(len(rows)),'validation-full');people=sorted({r['person_id'] for r in rows});per_person={person:reduce([i for i,r in enumerate(rows) if r['person_id']==person],'validation-person-'+str(j)) for j,person in enumerate(people)}
        evidence=self.request['output_contract']['original_fit_evidence']
        fields(evidence,('state_declaration','state_identity','fit_call_id','fit_request_identity','fit_response_identity','actual_generated_source_identity','attempt','repetition','train_support_identity','validation_support_identity'),'host-issued opaque original fit evidence')
        need(identity(evidence['state_declaration'])==evidence['state_identity'] and evidence['validation_support_identity']==document['whole_support_identity'] and evidence['repetition']==self.request['scope']['repetition'],'actual state declaration and validation support; no hidden state serialization contract')
        summary={'status':'complete' if metrics[MONITOR[self.request['scope']['dataset']]] is not None else 'unavailable','monitor':metrics[MONITOR[self.request['scope']['dataset']]],'metrics':metrics,'support_identity':document['whole_support_identity'],'all_person_metrics':per_person,'all_configuration_metrics':{'original_fit_evidence':evidence,'selected_state_only_recomputed_here':True,'unobserved_configuration_metrics_imputed':False}};self.json('VALIDATION_SUMMARY.json',summary);self.response['diagnostics']=summary
    def run(self):
        call=self.request['call'];action=self.request['action']
        if call=='DESCRIBE':self.response['diagnostics']={'implemented':['fixed_spectral_ridge','qualified_EEGPT_source_or_prospective_heads','retained_original_BENDR_BIOT_LaBraM_classes','original_ARL_EEGNet_with_all7_full_epoch_adapters','all9_Temple_prospective_source_methods_with_continuous_adapters','trusted_fullcase_validation'],'unavailable_original_sources':['original no-predictor scientific wiring remains unresolved','exact original H Temple training recipe and seed ancestry unresolved'],'scientific_qualification':False}
        elif call=='PREPARE':
            from .family_products import training_products
            training_products(self,self.request['output_contract']['products'],{})
            self.response['diagnostics']={'supports':{name:self.rows(name)['whole_support_identity'] for name in ('train','validation','corpus_train','corpus_validation') if name in self.inputs},'candidate_dependent_learning_permitted_only_in_same_episode':True}
        elif call=='FIT':
            recipe=self.recipe();kind=recipe['kind']
            if kind in ('fixed_spectral_ridge','eegpt_downstream','retained_original_class'):
                import random,numpy as np,torch
                random.seed(self.request['seed']);np.random.seed(self.request['seed']);torch.manual_seed(self.request['seed'])
            if kind=='arl_eegnet_v1':
                from .eegnet_reference import fit
                fit(self,recipe)
            elif kind=='temple_reference_v1':
                from .temple_reference import fit
                fit(self,recipe)
            elif kind=='fixed_spectral_ridge':self.fit_spectral(recipe)
            elif kind=='eegpt_downstream':self.fit_neural(recipe)
            elif kind=='retained_original_class':self.fit_legacy(recipe)
            else:raise Refusal('G12: original reference producer absent or not constructed; no configured callback substitute: '+str(kind))
        elif call=='PRETRAIN':
            import random,numpy as np,torch
            random.seed(self.request['seed']);np.random.seed(self.request['seed']);torch.manual_seed(self.request['seed'])
            from .reference_science import pretrain
            pretrain(self)
        elif call in ('VALIDATE','PREDICT'):self.predict()
        elif call=='QUERY_TRANSFORM':
            from .reference_science import query_transform
            query_transform(self)
        elif call=='DIAGNOSE':
            from .reference_science import diagnose
            diagnose(self)
        elif call=='ANALYZE' and action=='reduce_validation':self.reduce_validation()
        elif call=='ANALYZE':
            from .reference_science import analyze
            analyze(self)
        else:raise Refusal('operator-only or unqualified scientific call cannot be invoked as an arbitrary reference callback: '+call+'/'+action)
        return self.response


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--request',required=True);parser.add_argument('--response',required=True);args=parser.parse_args(argv);request=load_json(args.request);worker=Worker(request,Path(args.response).parent)
    try:response=worker.run()
    except BaseException as exc:
        response=worker.response;response.update(status='failed',decision='failed',diagnostics={'original_failure':observation(exc),'scientific_qualification':False});Path(args.response).write_bytes(encode(response));return 2
    Path(args.response).write_bytes(encode(response));return 0
