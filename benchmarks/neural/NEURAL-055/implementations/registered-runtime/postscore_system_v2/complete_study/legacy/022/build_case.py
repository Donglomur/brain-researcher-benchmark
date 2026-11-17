"""Prepare one isolated outer-person public case and its private target.

Future operator command: source preparation/copying only, no model fitting or
scoring. Does not expose target-person training EEG. Fail closed unless every
input is pinned and the source row/image join has an operator attestation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np
from source_io import verify_file, safe_numeric, descriptor, save_json
from metadata_core import PARTICIPANTS, validate_metadata, split_plan, case_identity, validate_staged_participant_bindings, calibration_panels


def local_descriptor(root, d):
    if type(d) is not dict or set(d) != {'path','bytes','sha256'}:raise ValueError('exact descriptor required')
    rel=Path(d['path'])
    if rel.is_absolute() or '..' in rel.parts or str(rel)!=d['path']:raise ValueError('safe relative descriptor path required')
    base=Path(root).resolve(strict=True);source=base/rel;cursor=base
    for part in rel.parts:
        cursor=cursor/part
        if cursor.is_symlink():raise ValueError('symlink source paths inside root forbidden')
    verify_file(source,d);return source


def copy_pinned(source,destination):
    with Path(source).open('rb') as inp,Path(destination).open('xb') as out:
        shutil.copyfileobj(inp,out,1024*1024)


def finite_rows(array, name):
    for start in range(0,len(array),128):
        if not np.isfinite(array[start:start+128]).all():raise ValueError(name+': nonfinite values')


def build(staging_manifest, feature_manifest, join_attestation, heldout, secret, output, maximum_output_bytes):
    if heldout not in PARTICIPANTS:raise ValueError('unknown outer participant')
    stage_path=Path(staging_manifest);stage=json.loads(stage_path.read_text())
    if set(stage)!={'schema','people'} or stage['schema']!='neural055-staging-index-v1' or set(stage['people'])!=set(PARTICIPANTS):raise ValueError('exact ten-person staging index required')
    people={}
    for person in PARTICIPANTS:
        manifest_file=local_descriptor(stage_path.parent,stage['people'][person]);m=json.loads(manifest_file.read_text())
        if m.get('schema')!='neural055-safe-staged-person-v1' or m.get('participant')!=person:raise ValueError('staged person identity mismatch')
        people[person]=(manifest_file,m)
    validate_staged_participant_bindings({person:m for person,(mf,m) in people.items()})
    # Verify metadata/coordinates across people without loading withheld EEG.
    metadata=None;coordinates=None;means={};staged_pins={}
    for person,(mf,m) in people.items():
        meta_file=local_descriptor(mf.parent,m['files']['image_metadata.json']);meta=validate_metadata(json.loads(meta_file.read_text()))
        coord_file=local_descriptor(mf.parent,m['files']['coordinates.json']);coord=json.loads(coord_file.read_text())
        if metadata is not None and (meta!=metadata or coord!=coordinates):raise ValueError('cross-person image identity or coordinate mismatch')
        metadata=meta;coordinates=coord
        name='test_mean.npy' if person==heldout else 'train_mean.npy'
        means[person]=local_descriptor(mf.parent,m['files'][name])
        staged_pins[person]=stage['people'][person]
    attest_path=Path(join_attestation);attest=json.loads(attest_path.read_text())
    if set(attest)!={'schema','staging_index_sha256','operator_review_id','all_ten_event_image_joins_verified','participant_archive_mapping_verified','participant_archives','basis'} or attest['schema']!='neural055-operator-join-attestation-v1':raise ValueError('exact join attestation schema required')
    if attest['staging_index_sha256']!=hashlib.sha256(stage_path.read_bytes()).hexdigest() or attest['all_ten_event_image_joins_verified'] is not True or attest['participant_archive_mapping_verified'] is not True or not attest['operator_review_id'] or not attest['basis']:raise ValueError('source join remains unverified; no final case produced')
    if type(attest['participant_archives']) is not dict or set(attest['participant_archives'])!=set(PARTICIPANTS) or any(attest['participant_archives'][person]!=people[person][1]['source_archive'] for person in PARTICIPANTS):raise ValueError('reviewed participant-to-archive mappings must exactly match staged source pins')
    fp=Path(feature_manifest);fm=json.loads(fp.read_text())
    required={'schema','training_features','test_features','image_metadata_sha256','checkpoint_sha256','extraction_recipe_sha256','representation_name','trained_transform_scope'}
    if set(fm)!=required or fm['schema']!='neural055-image-feature-manifest-v1':raise ValueError('exact image feature manifest required')
    encoded=json.dumps(metadata,sort_keys=True,separators=(',',':')).encode()
    if fm['image_metadata_sha256']!=hashlib.sha256(encoded).hexdigest():raise ValueError('feature-to-image ordering identity mismatch')
    if fm['trained_transform_scope']!='fixed_checkpoint_no_dataset_fitted_transform_no_EEG' or not fm['representation_name']:raise ValueError('permitted image-feature provenance required')
    for k in ['checkpoint_sha256','extraction_recipe_sha256']:
        if type(fm[k]) is not str or len(fm[k])!=64 or any(c not in '0123456789abcdef' for c in fm[k]):raise ValueError('exact checkpoint and recipe pins required')
    train_features_path=local_descriptor(fp.parent,fm['training_features']);test_features_path=local_descriptor(fp.parent,fm['test_features'])
    features=safe_numeric(train_features_path);test_features=safe_numeric(test_features_path)
    if features.ndim!=2 or features.shape[0]!=16540 or features.shape[1]<1 or test_features.shape!=(200,features.shape[1]):raise ValueError('exact train/test image feature axes required')
    finite_rows(features,'training features');finite_rows(test_features,'test features')
    plan=split_plan(metadata);case,target,qorder,corder=case_identity(metadata,heldout,secret)
    # Budget before output: exact copied files plus bounded new arrays and metadata.
    needed=sum(p.stat().st_size for p in means.values())+train_features_path.stat().st_size+test_features.nbytes+16*1024*1024
    if type(maximum_output_bytes) is not int or maximum_output_bytes<needed:raise ValueError('explicit output cap insufficient for complete case')
    out=Path(output);out.mkdir(parents=False,exist_ok=False);public=out/'public';private=out/'private';public.mkdir();private.mkdir();(public/'train').mkdir()
    query=safe_numeric(means[heldout],shape=(200,17,100));finite_rows(query,'query EEG')
    np.save(public/'query.npy',np.asarray(query[qorder],dtype='<f8'),allow_pickle=False)
    np.save(public/'candidate_features.npy',np.asarray(test_features[corder]),allow_pickle=False)
    copy_pinned(train_features_path,public/'training_image_features.npy')
    training=[]
    for person in PARTICIPANTS:
        if person==heldout:continue
        a=safe_numeric(means[person],shape=(16540,17,100));finite_rows(a,'training EEG')
        dest=public/'train'/(person+'.npy');copy_pinned(means[person],dest)
        training.append({'person_id':person,'eeg':descriptor(dest,public)})
    save_json(public/'CASE.json',case);save_json(public/'coordinates.json',coordinates)
    # Training identities are permissible labels. No200 assessment filename/concept enters this file.
    save_json(public/'TRAINING.json',{'schema':'neural055-training-v1','people':training,
        'training_image_ids':['train_'+str(i).zfill(5) for i in range(16540)],
        'original_THINGS_training_concept_ids':metadata['train_img_concepts_THINGS'],
        'inner_development_row_indices':plan['development_training_row_indices'],
        'reference_calibration_panels':calibration_panels(metadata),
        'inner_participant_holdouts':[x for x in PARTICIPANTS if x!=heldout],
        'image_features':descriptor(public/'training_image_features.npy',public),
        'rule':'Inner fits exclude selected330 concepts and innerheldperson; final fold-specific refit may use allother9 originaltraining data after policy freeze.'})
    save_json(public/'ASSETS.json',{'schema':'neural055-case-assets-v1','case_id':case['case_id'],
        'query_eeg':descriptor(public/'query.npy',public),'candidate_features':descriptor(public/'candidate_features.npy',public),
        'coordinates':descriptor(public/'coordinates.json',public),'training':descriptor(public/'TRAINING.json',public),
        'query_repeats_averaged':80,'target_person_labeled_calibration':False,
        'image_representation':{k:fm[k] for k in ['checkpoint_sha256','extraction_recipe_sha256','representation_name','trained_transform_scope']}})
    save_json(private/'TARGET.json',target)
    save_json(private/'PROVENANCE.json',{'schema':'neural055-case-provenance-v1','outer_participant':heldout,
        'public_case':descriptor(public/'CASE.json',out),'private_target':descriptor(private/'TARGET.json',out),
        'staging_index':descriptor(stage_path,stage_path.parent),'feature_manifest':descriptor(fp,fp.parent),
        'join_attestation':descriptor(attest_path,attest_path.parent),'split_plan':plan,
        'operator_key_sha256':hashlib.sha256(secret).hexdigest(),'payloads_public_only_inside_this_one_fold':True,
        'warning':'Never mount other outer-fold public directories to this candidate; they contain its held-out-person training data.'})
    actual=sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
    if actual+65536>maximum_output_bytes:raise ValueError('complete case exceeds explicit output cap; not admitted')
    save_json(out/'PREPARED.json',{'schema':'neural055-prepared-case-v1','source_construction_only':True,
        'case_id':case['case_id'],'outer_participant':heldout,'public_case':descriptor(public/'CASE.json',out),
        'private_target':descriptor(private/'TARGET.json',out),'public_assets':descriptor(public/'ASSETS.json',out),
        'operator_provenance':descriptor(private/'PROVENANCE.json',out),'no_model_or_scoring_run':True})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['staging-index','feature-manifest','join-attestation','heldout','id-key-file','output']:p.add_argument('--'+name,required=True)
    p.add_argument('--max-output-bytes',type=int,required=True);a=p.parse_args()
    key=Path(a.id_key_file).read_bytes()
    build(a.staging_index,a.feature_manifest,a.join_attestation,a.heldout,key,a.output,a.max_output_bytes)


if __name__=='__main__':main()
