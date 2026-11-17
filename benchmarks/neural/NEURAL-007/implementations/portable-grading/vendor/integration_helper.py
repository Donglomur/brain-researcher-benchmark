"""Trusted operator conversion or separate grading; prepared, never run here."""
import hashlib
import io
import json
import math
from pathlib import Path
import stat
import sys
import time
import zipfile

sys.path.insert(0, '/source')
import numpy as np
import candidate_adapter as adapter


def require(value, message):
    if not value: raise ValueError(message)


def plain_lock(record):
    return {key: record[key] for key in ('bytes', 'sha256')}


def file_lock(path):
    return {'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def checked_json(path, lock):
    return json.loads(adapter._locked_bytes(path, plain_lock(lock)))


def specification(plan):
    return adapter.Specification(tuple(adapter.Case(c['case_id'],c['epochs']) for c in plan['cases']),('YASA','RF'))


def array_identity(value):
    return {'shape':list(value.shape),'dtype':value.dtype.str,
            'c_order_value_bytes_sha256':hashlib.sha256(value.tobytes(order='C')).hexdigest()}


def convert(plan):
    start=time.monotonic();spec=specification(plan);total=sum(c.epochs for c in spec.cases)
    out=Path('/out');require(not any(out.iterdir()),'fresh empty conversion output')
    records={}
    for name,source in plan['sources'].items():
        freeze=checked_json(Path('/inputs')/(name+'.freeze.json'),source['freeze'])
        require(freeze['status']=='predictions_frozen_before_private_grade' and freeze['predictor_stopped'] is True,
                'historical predictor stopped before source freeze')
        require(freeze['files']['predictions.npz']==plain_lock(source['probabilities']),'saved source freeze binding')
        data=adapter._locked_bytes(Path('/inputs')/(name+'.npz'),plain_lock(source['probabilities']))
        layout={'epoch_id':((total,),'ids'),**{key:((total,5),'probabilities') for key in source['all_probability_keys']}}
        adapter._inspect_headers(data,layout)
        with np.load(io.BytesIO(data),allow_pickle=False,max_header_size=4096) as arrays:
            ids=arrays['epoch_id'];prob=arrays[source['selected_key']]
        canonical=np.concatenate([adapter.expected_ids(c) for c in spec.cases])
        require(np.array_equal(ids,canonical),'source exact full-clock participant/epoch order')
        require(prob.dtype.kind=='f' and prob.dtype.itemsize in (4,8),'source float precision retained')
        bundle={'class_order':np.asarray(plan['class_order'],dtype='U')};offset=0;identity={}
        for case in spec.cases:
            end=offset+case.epochs
            bundle[case.case_id+'__epoch_id']=ids[offset:end]
            bundle[case.case_id+'__probabilities']=prob[offset:end]
            identity[case.case_id]={'epoch_id':array_identity(ids[offset:end]),'probabilities':array_identity(prob[offset:end])}
            offset=end
        path=out/source['output_name'];np.savez(path,**bundle)
        lock=file_lock(path);require(lock['bytes']<=plan['conversion_outputs'][path.name],'individual output cap')
        validated=adapter.validate_submission(path,lock,spec)
        for case in spec.cases:
            for key in ('epoch_id','probabilities'):
                require(array_identity(validated['people'][case.case_id][key])==identity[case.case_id][key],
                        'roundtrip exact values, dtype, shape and ID bytes')
        records[name]={'output':path.name,'lock':lock,'source':source['probabilities'],
                      'selected_key':source['selected_key'],'array_identities':identity,
                      'values_or_precision_changed':False,'source_predictor_stopped_receipt':source['freeze']}
    result={'status':'two_saved_references_converted_exactly_no_private_access','sources':records,
            'schema':'one operator aggregate NPZ per submission, with both complete participant arrays',
            'private_accesses':0,'models_or_fits':0,'recording_reads':0,
            'wall_seconds':time.monotonic()-start}
    (out/'conversion.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    require(sum(p.stat().st_size for p in out.iterdir())<=2500000,'aggregate conversion output cap')
    print('CONVERSION_COMPLETE',flush=True)


def target_headers(data, case):
    """Before private target allocation, inspect exact stored NPY geometry/types."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        entries=z.infolist();expected={'epoch_id.npy','stage.npy','score_mask.npy'}
        require(not z.comment and len(entries)==3 and {x.filename for x in entries}==expected,'exact private NPZ keys')
        for e in entries:
            require(not e.is_dir() and not e.flag_bits&1 and e.compress_type==zipfile.ZIP_STORED
                    and e.file_size==e.compress_size and not stat.S_ISLNK(e.external_attr>>16),'ordinary stored private NPY')
            with z.open(e) as stream:
                version=np.lib.format.read_magic(stream);require(version in ((1,0),(2,0)),'private NPY version')
                reader=np.lib.format.read_array_header_1_0 if version==(1,0) else np.lib.format.read_array_header_2_0
                shape,fortran,dtype=reader(stream,max_header_size=4096)
                require(shape==(case.epochs,) and not dtype.hasobject and dtype.fields is None,'private one-dimensional case shape')
                if e.filename=='epoch_id.npy':require(dtype.kind=='U' and 0<dtype.itemsize<=512,'private bounded Unicode IDs')
                elif e.filename=='stage.npy':require(dtype.kind in 'iu' and dtype.itemsize<=8,'private integer stage')
                else:require(dtype==np.dtype(bool),'private boolean mask')
                require(stream.tell()+case.epochs*dtype.itemsize==e.file_size,'private NPY exact payload size')


def compare_score(actual, expected, atol):
    require(len(actual['per_person'])==len(expected['per_person'])==2,'complete two-person parity')
    exact=('person_id','confusion','true_support','predicted_support','supported_class_count','scored_epochs')
    numeric=('macro_f1_fixed_five','balanced_accuracy_supported_classes')
    for a,b in zip(actual['per_person'],expected['per_person']):
        for key in exact:require(a[key]==b[key],'public historical integer/identity parity: '+key)
        for key in numeric:require(math.isclose(a[key],b[key],abs_tol=atol,rel_tol=0),'public historical metric parity: '+key)
        for x,y in zip(a['recall_by_stage'],b['recall_by_stage']):
            require((x is None and y is None) or (x is not None and y is not None and math.isclose(x,y,abs_tol=atol,rel_tol=0)),
                    'public historical stage recall parity')
    for key in ('person_mean_macro_f1','person_mean_balanced_accuracy_supported_classes'):
        require(math.isclose(actual[key],expected[key],abs_tol=atol,rel_tol=0),'equal-person historical mean parity')


def grade(plan):
    start=time.monotonic();spec=specification(plan);public=Path('/bundles')
    execution=json.loads(Path('/source/execution.json').read_text())
    freeze=checked_json(public/'bundle_freeze.json',execution['bundle_freeze'])
    require(freeze['conversion_worker_stopped_and_removed'] is True,'converter absence precedes private grading')
    require(set(p.name for p in public.iterdir())==set(freeze['files'])|{'bundle_freeze.json'},'exact frozen public inventory')
    require(set(freeze['files'])=={'yasa.npz','rf.npz','conversion.json'},'required two bundles and receipt')
    conversion=checked_json(public/'conversion.json',freeze['files']['conversion.json'])
    require(conversion['status']=='two_saved_references_converted_exactly_no_private_access' and conversion['private_accesses']==0,'conversion phase receipt')
    require(set(conversion['sources'])==set(plan['sources'])=={'YASA','RF'},'exact two converted source identities')
    for name,row in conversion['sources'].items():
        require(row['source']==plan['sources'][name]['probabilities'] and row['selected_key']==plan['sources'][name]['selected_key']
                and row['output']==plan['sources'][name]['output_name']
                and row['lock']==freeze['files'][row['output']] and row['values_or_precision_changed'] is False,'exact conversion lineage')
    expected={}
    for name,pin in plan['public_results'].items():
        report=checked_json(Path('/source')/(name+'_public_grade.json'),pin)
        arm='EEG_EOG_ensemble' if name=='YASA' else 'EEG_EOG_clock'
        require(report['prediction_freeze']['files']['predictions.npz']==plain_lock(plan['sources'][name]['probabilities']),
                'public historical metric source binding')
        require(report['private_manifest']==plain_lock(plan['private_files']['manifest.json']),'historical same private targets')
        expected[name]=report['arms'][arm]
    accesses={'private_loader_calls':0}
    def load_targets_once():
        accesses['private_loader_calls']+=1
        require(accesses['private_loader_calls']==1,'one private target-loader invocation')
        private=Path('/private');require(set(x.name for x in private.iterdir())==set(plan['private_files']),'exact three private-file boundary')
        manifest=checked_json(private/'manifest.json',plan['private_files']['manifest.json'])
        require(manifest==plan['private_manifest_expected'],'exact private lineage manifest')
        result={}
        for case in spec.cases:
            filename=case.case_id+'_labels.npz';data=adapter._locked_bytes(private/filename,plain_lock(plan['private_files'][filename]))
            target_headers(data,case)
            with np.load(io.BytesIO(data),allow_pickle=False,max_header_size=4096) as arrays:
                result[case.case_id]={key:arrays[key] for key in ('epoch_id','stage','score_mask')}
        return result
    refs={name:(public/plan['sources'][name]['output_name'],freeze['files'][plan['sources'][name]['output_name']]) for name in ('YASA','RF')}
    # evaluate validates candidate AND BOTH comparators before load_targets_once.
    scored=adapter.evaluate(*refs['YASA'],spec,load_targets_once,refs)
    require(accesses['private_loader_calls']==1,'one and only one private load')
    require(scored['candidate']==scored['comparators']['YASA'],'reused YASA candidate equals its comparator score')
    zero=scored['signed_comparator_differences']['YASA']
    require(zero['person_mean_macro_f1_delta']==0 and zero['person_mean_balanced_accuracy_delta']==0
            and all(r['macro_f1_delta']==0 and r['balanced_accuracy_delta']==0 for r in zero['per_person']),'YASA self difference exactly zero')
    for name in ('YASA','RF'):compare_score(scored['comparators'][name],expected[name],plan['numerical_parity_atol'])
    alternative=adapter._difference(scored['comparators']['RF'],scored['comparators']['YASA'])
    require(math.isclose(alternative['person_mean_macro_f1_delta'],plan['expected_RF_minus_YASA_person_mean_macro_f1'],abs_tol=plan['numerical_parity_atol'],rel_tol=0)
            and all(r['macro_f1_delta']<0 for r in alternative['per_person']),'signed RF alternative retained; no positive-gain gate')
    result={'status':'saved_reference_adapter_parity_passed','adapter_result':scored,'RF_minus_YASA':alternative,
            'RF_role_note':'RF used the identical generic validator as a comparator; reversing already scored roles makes no second target access or independent attempt.',
            **accesses,'all_public_bundles_validated_before_private_loader':True,'public_report_metric_parity':True,
            'new_models_fits_or_predictions':0,'candidate_attempt':False,'population_inference':False,
            'full_untrusted_collector_qualified':False,'pretraining_or_context_matched':False,
            'scope':plan['scope'],'wall_seconds':time.monotonic()-start}
    encoded=json.dumps(result,sort_keys=True,allow_nan=False);require(len(encoded.encode())<=100000,'bounded grading report')
    print('PARITY_JSON='+encoded,flush=True)


if __name__=='__main__':
    plan=json.loads(Path('/source/plan.json').read_text())
    require(len(sys.argv)==2 and sys.argv[1] in ('convert','grade'),'explicit trusted worker phase')
    (convert if sys.argv[1]=='convert' else grade)(plan)
