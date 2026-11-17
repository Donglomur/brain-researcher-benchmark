"""Exact public capability projection and fold-local adaptive source admission."""
import hashlib
import hmac
import os
from pathlib import Path
from .protocol import HandleCustody,fields,need,integer,digest,descriptor,relative,identity,encode,decode,Directory,persist,stream_capture,read_metadata,observation

PUBLIC_ROW=('row_id','person_id','session_id','recording_id','event_id','interval','channels','sampling_hz','units','signal','label')
SOURCE_FIELDS=('schema','entrypoint','files','environment_identity','declared_resources','method_description')


def select_signal_view(original, dataset, method, mode):
    """Pure exact method/mode projection; private episode chooses the method."""
    from .temple_reference import METHODS, preparation_contract
    signal = original['signal']; selected_mode = 'H' if mode == 'H' else 'P_I'
    contract = None
    if dataset in ('TUAB', 'TUEV') and method in METHODS:
        fields(signal, ('by_mode', 'by_method'), 'complete standard and Temple method views')
        need(set(signal['by_method']) == set(METHODS), 'all nine Temple method signal views')
        method_views = signal['by_method'][method]
        need(set(method_views) == {'H', 'P_I'}, 'both complete method modes')
        view = method_views[selected_mode]
        fields(view, ('signal','channels','sampling_hz','units','interval','transform_ancestry','preparation_contract'), 'source-bound complete Temple view')
        contract = preparation_contract(dataset, method)
        need(view['preparation_contract'] == contract, 'actual selected source-owned Temple transform ancestry')
        need(view['channels'] == contract['output_channels'] and view['sampling_hz'] == contract['sampling_hz'] and view['units'] == contract['units'] and view['signal']['shape'] == [len(contract['output_channels']), contract['samples']], 'full source-bound method signal axes')
        digest(view['transform_ancestry'])
        return view, contract
    if 'by_mode' in signal:
        need(set(signal) in ({'by_mode'}, {'by_mode','by_method'}) and set(signal['by_mode']) == {'H','P_I'}, 'both complete original mode-specific views')
        view = signal['by_mode'][selected_mode]
        fields(view, ('signal','channels','sampling_hz','units','interval','transform_ancestry'), 'explicit complete original mode-specific view')
        return view, None
    return {**{k:original[k] for k in ('channels','sampling_hz','units','interval')}, 'signal': signal}, None


class Projection:
    def __init__(self,census,secret,source_roots,issuer,budget,*,development_label_root,target_root):
        need(type(secret) is bytes and len(secret)>=32,'private pre-exposure alias key');self.census=census;self.secret=secret;self.roots=source_roots;self.issuer=issuer;self.budget=budget;self.maps={};self.development_label_root=development_label_root;self.target_root_path=str(target_root);self.target_cache={}
    def alias(self,kind,identity_value):
        return hmac.new(self.secret,encode({'kind':kind,'original':identity_value}),hashlib.sha256).hexdigest()[:32]
    def episode_rows(self,dataset,fold,mode,role):
        need(role in ('train','validation','query'),'closed scientific role');document=self.census['datasets'][dataset];split=document['folds'][fold]['H' if mode=='H' else 'P_I'];byid={r['id']:r for r in document['records']}
        return [byid[k] for k in split[role]]
    def materialize(self,episode,dataset,fold,mode,role,destination,parents,*,repetition):
        row=self.issuer.eligible(episode,parents,repetition=repetition);need(row['scope']['spec']['dataset']==dataset and row['scope']['spec']['outer_fold']=='f'+str(fold) and row['scope']['spec']['mode']==mode,'same original E projection')
        query=role=='query';need(row['status']==('closed_development' if query else 'development'),'protected query not available during development')
        records=[];mapping={};captures=[];method=row['scope']['spec']['method'];preparation=None
        with HandleCustody('projection_materialize') as owned:
            directory=owned.own(Directory(str(destination)),'destination')
            permitted_labels=None if query else self.development_labels(dataset,fold,mode,role)
            for index,original in enumerate(self.episode_rows(dataset,fold,mode,role)):
                # Names depend on scientific rows, never label or method score.
                public={k:original[k] for k in ('interval','channels','sampling_hz','units')}
                for original_key,public_key in (('id','row_id'),('person','person_id'),('session','session_id'),('recording','recording_id'),('event','event_id')):public[public_key]=self.alias(dataset+':'+original_key,original[original_key])
                view,selected_preparation=select_signal_view(original,dataset,method,mode);signal=view['signal'];public.update({k:view[k] for k in ('channels','sampling_hz','units','interval')})
                if selected_preparation is not None:
                    need(preparation is None or preparation==selected_preparation,'one complete source preparation contract per public support');preparation=selected_preparation
                fields(signal,('root','member','format','shape','label_free_evidence'),'qualified label-free signal capability');need(signal['root'] in self.roots and signal['format']=='npy_little_endian_c_float','qualified signal-only numerical format');digest(signal['label_free_evidence'])
                source=descriptor(signal['member']);name='signal-%08d.npy'%index
                capture=stream_capture(self.roots[signal['root']],source['path'],expected=source,ledger=self.budget,cap=self.budget.limits['per_file_bytes'],destination=directory,destination_name=name)
                captures.append(capture);public['signal']={'path':'/inputs/'+role+'/'+name,'format':signal['format'],'shape':signal['shape'],'bytes':source['bytes'],'sha256':source['sha256']}
                # Query label bytes and provenance never enter any public file,
                # alias, request, process argv/environment or candidate mount.
                public['label']=None if query else permitted_labels[original['id']];fields(public,PUBLIC_ROW,'closed candidate-visible row')
                records.append(public);mapping[public['row_id']]={'dataset':dataset,'original_id':original['id'],'person':original['person'],'source':source}
            document={'schema':'eegpt_public_rows_v1','role':role,'rows':records,'whole_support_identity':identity([r['row_id'] for r in records]),'labels_available':not query}
            if preparation is not None:document['preparation_contract']=preparation
            pin=persist(directory,'rows.json',encode(document),ledger=self.budget)
            receipt=self.issuer.publish_local(episode,'prepared',parents,{'role':role,'public_document':pin,'support_identity':document['whole_support_identity'],'original_support_identity':identity([r['original_id'] for r in mapping.values()]),'captures':captures,'label_masking':'query omitted from bytes and all visible transport surfaces' if query else 'development labels explicitly available'},repetition=repetition,query=query)
            self.maps[receipt['token']]=mapping
            return {'public':document,'member':pin,'receipt':receipt,'host_root':str(directory.path)}
    def development_labels(self,dataset,fold,mode,role):
        need(role in ('train','validation') and not self.issuer.global_closed and not self.issuer.targets_open,'only authorized development role before global closure')
        key=dataset+':f'+str(fold)+':'+('H' if mode=='H' else 'P_I')+':'+role;need(key in self.census['development_label_rosters'],'exact selected same-fold development label capability')
        pin=self.census['development_label_rosters'][key];document=decode(read_metadata(self.development_label_root,pin,cap=self.budget.limits['metadata_bytes'],ledger=self.budget))
        fields(document,('schema','dataset','fold','mode','role','labels','source_identity'),'complete authorized development label view');need(document['schema']=='eegpt_development_labels_v1' and document['dataset']==dataset and document['fold']==fold and document['mode']==('H' if mode=='H' else 'P_I') and document['role']==role,'actual exact label role, not a protected-target file alias')
        expected={r['id'] for r in self.episode_rows(dataset,fold,mode,role)};need(set(document['labels'])==expected,'exact complete permitted original development rows');digest(document['source_identity'])
        from .scope import CLASSES
        for label in document['labels'].values():integer(label,'actual development class',0,CLASSES[dataset]-1)
        return document['labels']
    def private_targets(self,query_receipt,closure):
        self.issuer.verify(query_receipt,'prepared');self.issuer.verify(closure,'global_close');need(self.issuer.targets_open and self.issuer.global_closed,'full original barrier before any protected target projection')
        need(query_receipt['token'] in self.maps,'actual original query projection');mapping=self.maps[query_receipt['token']];need(mapping,'complete actual query support');datasets={row['dataset'] for row in mapping.values()};need(len(datasets)==1,'one original dataset per target join');dataset=next(iter(datasets))
        if dataset not in self.target_cache:
            with HandleCustody('private_target_read') as owned:
                root=owned.own(Directory(self.target_root_path),'target')
                document=decode(read_metadata(root,self.census['target_rosters'][dataset],cap=self.budget.limits['metadata_bytes'],ledger=self.budget))
            fields(document,('schema','dataset','rows','source_identity','exposure'),'complete original protected target roster');need(document['schema']=='eegpt_protected_targets_v1' and document['dataset']==dataset,'actual selected protected dataset');digest(document['source_identity']);need(type(document['rows']) is dict,'exact target identity map')
            allowed={r['id'] for r in self.census['datasets'][dataset]['records'] if r['included']};need(set(document['rows'])==allowed,'all original included target rows, no available-subset scoring');self.target_cache[dataset]=document
        from .scope import CLASSES
        labels=self.target_cache[dataset]['rows'];out={}
        for public_id,row in mapping.items():
            label=labels[row['original_id']];integer(label,'actual protected class',0,CLASSES[dataset]-1);out[public_id]={**row,'label':label}
        return out


def validate_source_manifest(document,*,genesis_environment,allowed_resources):
    fields(document,SOURCE_FIELDS,'complete arbitrary submitted/generated source package')
    need(document['schema']=='eegpt_submitted_source_v1' and type(document['entrypoint']) is list and document['entrypoint'],'actual parsed entrypoint, not evaluator imports')
    need(all(type(x) is str and x and '\x00' not in x for x in document['entrypoint']),'literal entrypoint argv')
    need(document['environment_identity']==genesis_environment and set(document['declared_resources'])<=set(allowed_resources),'same original sealed runtime and eligible resources; source generation cannot add providers or checkpoints')
    need(all(r.get('path')!='SOURCE.json' for r in document['files']),'SOURCE.json reserved for the host-owned immutable source manifest')
    need(type(document['files']) is list and document['files'] and len({r['path'] for r in document['files']})==len(document['files']),'complete exact source file inventory')
    for member in document['files']:descriptor(member)
    need(any('/source/'+r['path'] in document['entrypoint'] for r in document['files']),'entrypoint is an actual captured submitted source member')
    need(type(document['method_description']) is str and document['method_description'],'actual scientific method declaration, not a source-trivia requirement')
    return document


def capture_source(output_root,destination,manifest,issuer,episode,parents,budget,*,repetition,environment,resources):
    validate_source_manifest(manifest,genesis_environment=environment,allowed_resources=resources);captures=[]
    with HandleCustody('capture_generated_source') as owned:
        target=owned.own(Directory(str(destination)),'destination')
        # Original names are preserved within an opaque /source mount. Parent
        # directories are operator-created before opening held output members.
        for member in manifest['files']:
            for parent in Path(member['path']).parents:
                if str(parent)=='.':continue
                (target.path/parent).mkdir(parents=True,exist_ok=True)
            captures.append(stream_capture(output_root,member['path'],expected=member,ledger=budget,cap=budget.limits['per_file_bytes'],destination=target,destination_name=member['path']))
        pin=persist(target,'SOURCE.json',encode(manifest),ledger=budget)
        from .protocol import exact_tree,seal_tree
        exact_tree(target,manifest['files'],extra=('SOURCE.json',));seal_tree(target)
        receipt=issuer.publish_local(episode,'generated',parents,{'source_identity':identity(manifest),'source_manifest':pin,'actual_captures':captures,'environment_identity':environment,'declared_resources':resources,'promotion_to_global_common_allowed':False},repetition=repetition)
        return {'manifest':manifest,'receipt':receipt,'host_root':str(target.path),'identity':identity(manifest)}


def public_request(*,call,scope,request_id,source,parents,inputs,output_contract,resources,seed,feedback,context,action):
    """No private receipt MAC, host path, target or job-custody token escapes."""
    need(call in ('DESCRIBE','PREPARE','PRETRAIN','FIT','VALIDATE','PREDICT','QUERY_TRANSFORM','DIAGNOSE','ANALYZE','INTERPRET'),'actual participant-call API')
    need(type(scope) is dict and set(scope)=={'mode','access','policy_id','dataset','outer_fold','method','repetition'},'closed public scientific scope')
    for member in inputs:need(set(member)=={'name','guest_root','public_identity'} and member['guest_root'].startswith(('/inputs/','/state/')),'public capabilities contain guest paths only')
    digest(source);digest(context);integer(seed,'actual source/state random seed',0,2**32-1)
    return {'schema':'eegpt_science_v1','call':call,'action':action,'request_id':request_id,'scope':scope,'source_identity':source,'public_parent_identities':parents,'inputs':inputs,'output_contract':output_contract,'resource_policy':resources,'seed':seed,'feedback':feedback,'context_identity':context,'capabilities_only':True}


def _materialize_corpus(self,episode,corpus_plan,role,destination,parents):
    """Full five-source corpus projection; no downstream records or labels."""
    need(role in ('corpus_train','corpus_validation'),'only original independent corpus roles');scope=self.issuer.eligible(episode,parents)['scope']['spec'];need(scope['dataset']=='CORPUS' and scope['outer_fold']=='corpus','actual corpus-only source context')
    fields(corpus_plan,('support_identity','rows','split','overlap_evidence','qualified_exclusions'),'complete eligible original corpus population');digest(corpus_plan['overlap_evidence']);need(set(corpus_plan['split'])=={'corpus_train','corpus_validation'},'complete source-selected corpus train/validation partition')
    byid={r['id']:r for r in corpus_plan['rows']};need(len(byid)==len(corpus_plan['rows']) and set(r['corpus'] for r in byid.values())=={'PhysioMI','HGD','TSU','SEED','M3CV'},'all five original source families, not convenient available folders')
    need(not set(corpus_plan['split']['corpus_train'])&set(corpus_plan['split']['corpus_validation']),'exact nonoverlapping source row identities');need(set(corpus_plan['split']['corpus_train'])|set(corpus_plan['split']['corpus_validation'])==set(byid),'all eligible original corpus rows retained')
    records=[];captures=[]
    with HandleCustody('materialize_corpus') as owned:
        directory=owned.own(Directory(str(destination)),'destination')
        for index,row_id in enumerate(corpus_plan['split'][role]):
            row=byid[row_id];signal=row['signal'];source=descriptor(signal['member']);need(signal['root'] in self.roots and signal['format']=='npy_little_endian_c_float','actual complete signal-only corpus capability');digest(signal['label_free_evidence']);name='corpus-%09d.npy'%index
            capture=stream_capture(self.roots[signal['root']],source['path'],expected=source,ledger=self.budget,cap=self.budget.limits['per_file_bytes'],destination=directory,destination_name=name);captures.append(capture)
            record={key:row[key] for key in ('interval','channels','sampling_hz','units')}
            for original,public in (('id','row_id'),('person','person_id'),('session','session_id'),('recording','recording_id'),('event','event_id')):record[public]=self.alias(row['corpus']+':'+original,row[original])
            record['signal']={'path':'/inputs/'+role+'/'+name,'format':signal['format'],'shape':signal['shape'],'bytes':source['bytes'],'sha256':source['sha256']};record['label']=None;fields(record,PUBLIC_ROW,'same public corpus signal surface');records.append(record)
        document={'schema':'eegpt_public_rows_v1','role':role,'rows':records,'whole_support_identity':identity([r['row_id'] for r in records]),'labels_available':False};member=persist(directory,'rows.json',encode(document),ledger=self.budget)
        receipt=self.issuer.publish_local(episode,'prepared',parents,{'role':role,'public_document':member,'support_identity':document['whole_support_identity'],'complete_corpus_support':corpus_plan['support_identity'],'overlap_evidence':corpus_plan['overlap_evidence'],'captures':captures,'downstream_adaptive_ancestry':False},repetition=None)
        return {'public':document,'member':member,'receipt':receipt,'host_root':str(directory.path)}


Projection.materialize_corpus=_materialize_corpus


def _register_query_transform(self,episode,repetition,original,result):
    """Closed case-local unlabeled derivative; unchanged private target mapping."""
    need(not self.issuer.targets_open and self.issuer.episodes[episode]['status']=='closed_development','transductive operation never reopens development');need(result['phase']=='captured' and result['response']['status']=='ok','actual original full transformation process')
    need(result['response']['generated_source'] is None and result['response']['selected_state'] is None and not result['response']['products'],'A07 cannot change frozen source/model or submit a score')
    pins={r['path']:r for r in result['response']['artifacts']};need('rows.json' in pins,'complete actual transformed query manifest')
    with HandleCustody('query_transform_read') as owned:
        root=owned.own(Directory(result['capture_root']),'capture')
        document=decode(read_metadata(root,pins['rows.json'],cap=self.budget.limits['metadata_bytes'],ledger=self.budget))
    expected_fields=('schema','role','rows','whole_support_identity','labels_available')+(('preparation_contract',) if 'preparation_contract' in original['public'] else ());fields(document,expected_fields,'closed original transformed query document');need(document.get('preparation_contract')==original['public'].get('preparation_contract'),'unchanged actual method preparation provenance');need(document['schema']=='eegpt_public_rows_v1' and document['role']=='query' and document['labels_available'] is False and document['whole_support_identity']==original['public']['whole_support_identity'],'unchanged full original query support with no labels');need(len(document['rows'])==len(original['public']['rows']),'all original query rows')
    for row,prior in zip(document['rows'],original['public']['rows'],strict=True):
        fields(row,PUBLIC_ROW,'closed transformed query row');need({k:v for k,v in row.items() if k!='signal'}=={k:v for k,v in prior.items() if k!='signal'} and row['label'] is None,'no altered original query identities, semantic axes, timing or metadata side channel');signal=row['signal'];fields(signal,('path','format','shape','bytes','sha256'),'actual transformed signal');need(signal['path'].startswith('/inputs/query/'),'only contained readonly transformed query capabilities');name=signal['path'][len('/inputs/query/'):];relative(name);need(name in pins and signal['bytes']==pins[name]['bytes'] and signal['sha256']==pins[name]['sha256'] and signal['shape']==prior['signal']['shape'] and signal['format']==prior['signal']['format'],'actual full captured same-shape transform, not a filename assertion')
    receipt=self.issuer.publish_local(episode,'prepared',[original['receipt'],result['process_receipt'],result['capture_receipt']],{'role':'query','public_document':pins['rows.json'],'support_identity':document['whole_support_identity'],'case_local_transduction':True,'protected_targets_unchanged':True},repetition=repetition,query=True);self.maps[receipt['token']]=dict(self.maps[original['receipt']['token']]);return {'public':document,'member':pins['rows.json'],'receipt':receipt,'host_root':result['capture_root']}

Projection.register_query_transform=_register_query_transform


# Same original episode/operator budget before and after each information view.
from .protocol import budget_method
for _name in ('materialize','development_labels','private_targets'):
    setattr(Projection,_name,budget_method(getattr(Projection,_name)))
