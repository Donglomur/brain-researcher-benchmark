"""One invented-only full-shape construction check; no authentic file access."""
from pathlib import Path
from contextlib import contextmanager
from copy import deepcopy
import argparse
import hashlib
import json
import math
import os
import resource
import sys
import time
import h5py
import numpy as np

ROOT = Path(__file__).absolute().parent
sys.path.insert(0, str(ROOT / 'operator'))
from tms_figure import contract as C, outputs, reference, paired, reduction
from tms_figure.derivative import Derivative
from tms_operator import operator as production_operator
from tms_operator.capture import capture_output
from tms_figure.slab import SLAB_BYTES

AUTHENTIC_PIN = {'bytes':298290277,'sha256':'536e9513b13dc721cf60613334ee37ce546e7bf67154d95bd067ddc0f0023a95'}
ROWS = []
START = time.monotonic()


def body_pin(path):
    body = Path(path).read_bytes()
    return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}


def dump(path, value):
    body = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    Path(path).open('xb').write(body)
    return body_pin(path)


def check(name, condition, detail=None):
    if not condition:
        raise AssertionError(name)
    ROWS.append({'name':name,'pass':True, 'detail':detail})


def refusal(name, call, message=None):
    try:
        call()
    except (C.Refusal, ValueError) as error:
        if message is not None and message not in str(error):
            raise AssertionError((name, str(error), message)) from error
        check(name, True, {'error_type':type(error).__name__,'message':str(error)})
    else:
        raise AssertionError(name + ': accepted')


def peak_bytes():
    n = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(n if sys.platform == 'darwin' else n * 1024)


def finite_budget():
    # Logical buffer/capture charges include repeated full reference admission.
    return C.Budget(12 * 2**30, 4 * 2**30, max(1, 170 - (time.monotonic()-START)))


def fixture_identity(path):
    return {
        'schema':C.IDENTITY_SCHEMA, 'shape':[62,53,200,15],
        'participant_axis_identity':{
            'kind':'released_array_positions','positions':list(range(15)),
            'physical_id_map_verified':False,'source_order_preserved':True,
            'source_declared_study_roster':list(C.PARTICIPANTS)},
        'conditions':list(C.CONDITIONS),'labels':list(C.EXPECTED_LABELS),
        'frequency':np.linspace(2,40,53).tolist(),'time':np.linspace(-1.5,6,200).tolist(),
        'source':body_pin(path),
        'provenance':{'endpoint':'released_artifact_group_topography',
            'published_driver':dict(C.DRIVER_SOURCE),'published_helper':dict(C.HELPER_SOURCE),
            'units_interpretation':'dB_as_used_by_published_operator','storage':'MATLAB-double',
            'upstream_preprocessing_verified':False,'paired_person_inference_admitted':False}}


@contextmanager
def invented_boundary(identity):
    """Only the test process substitutes a body pin; no production fixture mode."""
    if C.MASTER_PIN != AUTHENTIC_PIN:
        raise AssertionError('fixture boundary requires original authentic pin')
    previous = C.MASTER_PIN
    C.MASTER_PIN = dict(identity['source'])
    try:
        yield
    finally:
        C.MASTER_PIN = previous
        if C.MASTER_PIN != AUTHENTIC_PIN:
            raise AssertionError('authentic pin not restored')


def make_fixture(path, *, permuted=False, invalid=None, dense=True):
    """Invented complete geometry, no existing primary record is consulted."""
    orders = {}
    with h5py.File(path, 'w') as f:
        refs = f.create_group('refs')
        labels = []
        for i,label in enumerate(C.EXPECTED_LABELS):
            ds = refs.create_dataset('label'+str(i), data=np.array([ord(x) for x in label],dtype='<u2'))
            ds.attrs['MATLAB_class'] = np.bytes_('char'); labels.append(ds.ref)
        root = f.create_group('mTFR')
        for index,condition in enumerate(C.CONDITIONS):
            if invalid == 'missing_condition' and index == 3:
                continue
            node = root
            for part in condition.split('.'):
                node = node.require_group(part)
            n = 16 if invalid == 'sixteen_positions' and index == 0 else 15
            dtype = '<f4' if invalid == 'single_power' and index == 0 else '<f8'
            ds = node.create_dataset('powspctrm',shape=(n,200,53,62),dtype=dtype,
                chunks=(n,200,53,1),compression='gzip',compression_opts=1,fillvalue=0)
            ds.attrs['MATLAB_class'] = np.bytes_('single' if dtype == '<f4' else 'double')
            order = np.roll(np.arange(15), index+1) if permuted else np.arange(15)
            orders[condition] = order.tolist()
            if dense:
                base = np.broadcast_to((np.arange(15,dtype=np.float64)+index*10)[:,None,None],(15,200,53)).copy()
                for channel in range(62):
                    slab = base.copy()
                    if channel == 0:
                        slab[0,0,0]=np.nan
                        slab[14,1,0]=np.nan
                        slab[:,2,0]=np.nan
                        slab[0,3,0]=np.inf
                        slab[0,4,0]=np.inf;slab[14,4,0]=-np.inf
                    ds[:,:,:,channel] = slab[order,:,:]
            for name,values in [('freq',np.linspace(2,40,53)),('time',np.linspace(-1.5,6,200))]:
                field = values
                cls = 'double'
                if index == 0 and name == 'freq':
                    if invalid == 'character_axis':field=np.arange(53,dtype='<u2');cls='char'
                    if invalid == 'integer_axis':field=np.arange(53,dtype='<u2');cls='uint16'
                    if invalid == 'logical_axis':field=np.zeros(53,dtype='u1');cls='logical'
                    if invalid == 'single_axis':field=values.astype('<f4');cls='single'
                axis = node.create_dataset(name,data=field);axis.attrs['MATLAB_class']=np.bytes_(cls)
            node.create_dataset('label',data=np.array(labels,dtype=h5py.ref_dtype))
        if invalid == 'soft_link':
            node=f['mTFR/NT/pin/all'];del node['powspctrm'];node['powspctrm']=h5py.SoftLink('/mTFR/T/pin/all/powspctrm')
    return orders


def same_values(a,b):
    return len(a)==len(b) and all((math.isnan(x) and math.isnan(y)) or x==y for x,y in zip(a,b))


def main(out):
    out.mkdir(mode=0o700,exist_ok=False)
    check('authentic_source_pin_unchanged', C.MASTER_PIN==AUTHENTIC_PIN)
    core=ROOT/'operator'
    production_operator.source_admission(core,body_pin(core/'OPERATOR_LOCK.json'),finite_budget())
    check('actual_operator_full_source_admission',True)
    original=out/'invented.h5';permuted=out/'invented_permuted.h5'
    make_fixture(original);orders=make_fixture(permuted,permuted=True)
    identity=fixture_identity(original);other=fixture_identity(permuted)
    fixture_contract={'schema':'invented_tms_full_shape_fixture_contract_v1',
        'identity':identity,'permuted_identity':other,'condition_permutations':orders,
        'primary_input':False,'trusted_host_records':'invented test inputs, not authentic runtime authority'}
    dump(out/'FIXTURE_CONTRACT.json',fixture_contract)
    refusal('production_rejects_separate_fixture_contract',lambda:C.metadata(fixture_contract),'closed schema')
    refusal('production_rejects_fixture_body_pin',lambda:C.metadata(identity),'selected released derivative body')
    refusal('production_constructor_rejects_fixture',lambda:Derivative(original,identity,finite_budget(),metadata_read_reservation=2**20),'selected released derivative body')
    with invented_boundary(identity):
        check('source_position_profile_accepts_no_physical_join',C.metadata(identity)==identity)
        mutations=[
            ('no_old_admission_flag',lambda d:d['provenance'].update(admitted_by_operator=True),'closed schema'),
            ('physical_person_map_forbidden',lambda d:d['participant_axis_identity'].update(physical_id_map_verified=True),'physical-person'),
            ('paired_inference_forbidden',lambda d:d['provenance'].update(paired_person_inference_admitted=True),'paired-person'),
            ('preprocessing_claim_forbidden',lambda d:d['provenance'].update(upstream_preprocessing_verified=True),'preprocessing'),
            ('source_reordering_forbidden',lambda d:d['participant_axis_identity'].update(source_order_preserved=False),'reordering'),
            ('boolean_position_refused',lambda d:d['participant_axis_identity']['positions'].__setitem__(0,False),'15 original'),
            ('integer_flag_refused',lambda d:d['participant_axis_identity'].update(physical_id_map_verified=0),'physical-person'),
            ('incomplete_positions_refused',lambda d:d['participant_axis_identity'].update(positions=list(range(14))),'15 original'),
            ('boolean_axis_refused',lambda d:d['frequency'].__setitem__(0,False),'numeric axis'),
            ('float_shape_refused',lambda d:d['shape'].__setitem__(0,62.0),'geometry'),
            ('old_identity_schema_refused',lambda d:d.update(schema='tms_figure2b_derivative_identity_v1'),'geometry'),
        ]
        for name,mutate,message in mutations:
            changed=deepcopy(identity);mutate(changed)
            refusal(name,lambda d=changed:C.metadata(d),message)
        budget=finite_budget()
        with Derivative(original,identity,budget,metadata_read_reservation=2**20) as reader:
            with h5py.File(original,'r') as direct:
                for condition in C.CONDITIONS:
                    ds=direct['mTFR/'+condition.replace('.','/')+'/powspctrm']
                    for c,f,t in [(0,0,0),(0,0,1),(0,0,2),(0,0,3),(0,0,4),(61,52,199),(1,2,3),(0,3,4)]:
                        a=reader.stored_position_values(condition,c,f,t)
                        check('direct_slice_'+condition+'_'+str((c,f,t)),same_values(a,ds[:,t,f,c].tolist()))
            check('bounded_slab_extent',reader.slab.data.nbytes==SLAB_BYTES)
            reader.slab.close();before=reader.slab.loads;before_reads=budget.reads
            fields=reference.compute_fields(reader,identity)
            check('complete_reference_248_slabs',reader.slab.loads-before==248)
            check('complete_reference_exact_logical_power_reads',budget.reads-before_reads==630912000)
        check('cache_released_on_constructor_close',reader.slab.data is None)
        check('all_36_full_fields',len(fields)==36 and set(fields)==set(outputs.specs(identity)))
        for index,condition in enumerate(C.CONDITIONS):
            stem='mean.'+condition
            check('known_group_mean_'+condition,fields[stem+'.value'][200]==7.0+index*10)
            check('known_full_positions_'+condition,fields[stem+'.positions'][200]==32767 and fields[stem+'.contributors'][200]==15)
            check('known_missing_position_'+condition,fields[stem+'.positions'][0]==32766 and fields[stem+'.contributors'][0]==14)
        check('observed_memory_after_reference',peak_bytes()<=2*2**30)
    check('authentic_pin_restored_after_reference',C.MASTER_PIN==AUTHENTIC_PIN)
    with invented_boundary(other):
        with Derivative(permuted,other,finite_budget(),metadata_read_reservation=2**20) as reader:
            permuted_fields=reference.compute_fields(reader,other)
        for name in fields:
            if name.endswith('.positions'):
                condition=name[len('mean.'):-len('.positions')]
                old_masks=np.asarray(fields[name],dtype=np.uint16);order=orders[condition]
                expected=np.zeros(len(old_masks),dtype=np.uint16)
                for i,old_position in enumerate(order):
                    expected |= ((old_masks >> old_position) & 1) << i
                check('full_permutation_support_transform_'+condition,np.array_equal(np.asarray(permuted_fields[name],dtype=np.uint16),expected) and bool(np.any(expected!=old_masks)))
                del old_masks,expected
            else:
                check('full_permutation_invariance_'+name,same_values(fields[name],permuted_fields[name]))
        del permuted_fields
    check('finite_rounding_counterexample_preserved',reduction.mean_db([1e16,-1e16,1.0])[0]!=reduction.mean_db([1e16,1.0,-1e16])[0])
    for defect,message in [('character_axis','numeric axis'),('integer_axis','numeric axis'),('logical_axis','numeric axis'),('single_axis','numeric axis'),('single_power','double source'),('sixteen_positions','geometry'),('missing_condition','HDF5 links'),('soft_link','HDF5 links')]:
        path=out/('invalid_'+defect+'.h5');make_fixture(path,invalid=defect,dense=False);invalid=fixture_identity(path)
        with invented_boundary(invalid):
            refusal('constructor_refuses_'+defect,lambda:Derivative(path,invalid,finite_budget(),metadata_read_reservation=2**20),message)
    with invented_boundary(identity):
        ap=outputs.publish_fields(out/'A',identity,fields,finite_budget(),producer='invented-construction-A')
        fields['window.T.delay2.value'][0]+=0.125
        bp=outputs.publish_fields(out/'B',identity,fields,finite_budget(),producer='invented-construction-B-one-error')
        fields['window.T.delay2.value'][0]-=0.125
        del fields
        bad=out/'invalid_output';bad.mkdir()
        original_manifest=json.loads((out/'A/OUTPUT.json').read_bytes())
        for name in original_manifest['fields']:(bad/(name+'.bin')).touch()
        for name,mutate,message in [
            ('float_dimension',lambda d:d['fields']['mean.NT.pin.all.value']['shape'].__setitem__(0,62.0),'descriptor types'),
            ('float_byte_count',lambda d:d['fields']['mean.NT.pin.all.value'].update(bytes=float(d['fields']['mean.NT.pin.all.value']['bytes'])),'descriptor types'),
            ('wrong_dtype_type',lambda d:d['fields']['mean.NT.pin.all.value'].update(dtype=8),'descriptor types'),
            ('submitted_false_integer',lambda d:d['identity']['participant_axis_identity'].update(physical_id_map_verified=0),'physical-person'),
            ('submitted_true_integer',lambda d:d['identity']['participant_axis_identity'].update(source_order_preserved=1),'physical-person'),
            ('submitted_float_position',lambda d:d['identity']['participant_axis_identity']['positions'].__setitem__(0,0.0),'15 original'),
            ('submitted_preprocessing_integer',lambda d:d['identity']['provenance'].update(upstream_preprocessing_verified=0),'preprocessing'),
            ('submitted_paired_integer',lambda d:d['identity']['provenance'].update(paired_person_inference_admitted=0),'paired-person'),
            ('old_output_schema',lambda d:d.update(schema='tms_figure2b_full_output_v1'),'output identity'),
            ('missing_field',lambda d:d['fields'].pop('mean.NT.pin.all.positions'),'complete output fields'),
        ]:
            changed=deepcopy(original_manifest);mutate(changed)
            body=json.dumps(changed,allow_nan=False).encode();(bad/'OUTPUT.json').write_bytes(body)
            refusal('output_refuses_'+name,lambda:outputs.admit(bad,body_pin(bad/'OUTPUT.json'),identity,finite_budget()),message)
            if name.startswith('submitted_') or name=='old_output_schema':
                refused_destination=out/('refused_capture_'+name)
                refusal('capture_refuses_'+name,lambda:capture_output(source=bad,destination=refused_destination,meta=identity,budget=finite_budget()),message)
                check('capture_identity_refusal_creates_no_output_'+name,not refused_destination.exists())
        captures={}
        for arm,expected_pin in [('A',ap),('B',bp)]:
            captures[arm]=capture_output(source=out/arm,destination=out/('captured_'+arm),meta=identity,budget=finite_budget())
            check('actual_complete_capture_'+arm,captures[arm]['output']==expected_pin and captures[arm]['member_count']==37 and len(captures[arm]['members'])==36)
            accepted=outputs.admit(out/('captured_'+arm),captures[arm]['output'],identity,finite_budget())
            check('actual_capture_to_admit_'+arm,len(accepted)==36);del accepted
        dump(out/'CAPTURE_RECORDS.json',{'captures':captures,'producer_output_pins':{'A':ap,'B':bp},'both_complete_producer_outputs_preserved':True,'invented_only':True})

        pin={'bytes':1,'sha256':'0'*64}
        plan={'schema':'tms_figure2b_paired_plan_v1','identity':identity,
            'arms':{'A':{'trial_id':'invented-a','view':pin,'program':pin,'output':ap},'B':{'trial_id':'invented-b','view':pin,'program':pin,'output':bp}},
            'absolute_tolerance':1e-12,'relative_tolerance':1e-12,
            'tolerance_justification':pin,'matched_policy':pin,'source_lock':body_pin(core/'SOURCE_LOCK.json')}
        observations={arm:{'schema':'tms_figure2b_trusted_closure_v1','arm':arm,**plan['arms'][arm],
            'natural_exit':True,'returncode':0,'producer_closed':True,'capture_complete':True,
            'exclusive_custody':True,'isolation_qualified':True} for arm in ['A','B']}
        grant={'schema':'tms_figure2b_operator_grant_v1','plan_sha256':C.digest(plan),
            'observations_sha256':C.digest(observations),'operation':'compute-protected-reference-and-grade-pair','authorized_by_operator':True}
        grant_pin=dump(out/'INVENTED_GRANT.json',grant)
        dump(out/'INVENTED_PLAN_AND_OBSERVATIONS.json',{'plan':plan,'observations':observations,'not_authentic_runtime_evidence':True})
        report=paired.grade_pair(plan=plan,observations=observations,authority_path=out/'INVENTED_GRANT.json',authority_pin=grant_pin,
            source_lock_path=core/'SOURCE_LOCK.json',captures={'A':out/'captured_A','B':out/'captured_B'},derivative_path=original,
            private_output=out/'invented_grade',budget=finite_budget(),metadata_read_reservation=2**20)
        check('actual_scorer_all36_A_pass',report['arms']['A']['all_elements_pass'] and len(report['arms']['A']['fields'])==36)
        check('actual_scorer_B_exactly_one_deliberate_failure',not report['arms']['B']['all_elements_pass'] and sum(x['fail_count'] for x in report['arms']['B']['fields'].values())==1 and report['arms']['B']['fields']['window.T.delay2.value']['fail_count']==1)
        check('actual_scorer_never_qualifies',report['scientifically_qualified'] is False)
    check('authentic_pin_restored_finally',C.MASTER_PIN==AUTHENTIC_PIN)
    refusal('production_still_rejects_fixture_after_full_scorer',lambda:C.metadata(identity),'selected released derivative body')
    retained=sum(x.stat().st_size for x in out.rglob('*') if x.is_file())
    check('observed_final_memory',peak_bytes()<=2*2**30)
    check('retained_fixture_result_bound',retained+262144<=384*2**20)
    report={'schema':'tms_source_position_synthetic_result_v1','status':'PASS','checks':ROWS,
        'passed':len(ROWS),'failed':0,'elapsed_seconds':time.monotonic()-START,'peak_self_rss_bytes':peak_bytes(),
        'retained_bytes_before_result':retained,'primary_reads':0,'real_or_native_arithmetic_runs':0,
        'model_calls':0,'scientifically_qualified':False,'authentic_pin_restored':C.MASTER_PIN==AUTHENTIC_PIN,
        'fixture_boundary':'Only test-process input pin substitution; no authentic-custody or trusted-host qualification.',
        'complete_shape':[62,53,200,15],'conditions':4,'fields':36}
    dump(out/'RESULT.json',report)
    print(json.dumps({'status':'PASS','passed':len(ROWS),'failed':0,'elapsed_seconds':report['elapsed_seconds'],
        'peak_self_rss_bytes':report['peak_self_rss_bytes'],'retained_bytes_before_result':retained,'result_pin':body_pin(out/'RESULT.json')},sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    try:
        main(args.out)
    except BaseException as error:
        failed={'schema':'tms_source_position_synthetic_failure_v1','status':'FAILED','checks_completed':ROWS,
            'error_type':type(error).__name__,'error':str(error),'elapsed_seconds':time.monotonic()-START,
            'peak_self_rss_bytes':peak_bytes(),'authentic_pin_restored':C.MASTER_PIN==AUTHENTIC_PIN,
            'primary_reads':0,'no_retry_selected':True}
        if args.out.is_dir():dump(args.out/'FAILURE.json',failed)
        print(json.dumps(failed,sort_keys=True))
        raise
