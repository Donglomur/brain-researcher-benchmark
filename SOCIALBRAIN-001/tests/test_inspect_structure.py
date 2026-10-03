"""Manufactured header/table/authentication fixtures; no original sources.

The fake BOLD payload after vox_offset is deliberately NOT a valid voxel array.
Successful structural inspection must not decode it or claim its length checked.
"""
from dataclasses import replace
import gzip
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import signal
import struct
import sys
import zlib

import pytest

spec=importlib.util.spec_from_file_location('socialbrain_structure',Path(__file__).with_name('inspect_structure.py'))
s=importlib.util.module_from_spec(spec); sys.modules[spec.name]=s; spec.loader.exec_module(s)


def header(*,endian='<',shape=(3,4,5,6),datatype=16,bitpix=32,slope=1.,inter=0.,tr=2.,units=10,
           offset=352,extension=False,sform=1,qform=0):
    raw=bytearray(offset)
    struct.pack_into(endian+'i',raw,0,348)
    struct.pack_into(endian+'8h',raw,40,len(shape),*shape,*([1]*(7-len(shape))))
    struct.pack_into(endian+'hh',raw,70,datatype,bitpix)
    struct.pack_into(endian+'8f',raw,76,1.,3.,3.,3.,tr,1.,1.,1.)
    struct.pack_into(endian+'fff',raw,108,float(offset),slope,inter)
    raw[123]=units
    struct.pack_into(endian+'hh',raw,252,qform,sform)
    for i,row in enumerate(((3.,0.,0.,-6.),(0.,3.,0.,-6.),(0.,0.,3.,-6.))):
        struct.pack_into(endian+'4f',raw,280+16*i,*row)
    raw[344:348]=b'n+1\0'
    if extension:
        raw[348]=1
        struct.pack_into(endian+'ii',raw,352,offset-352,6)
        raw[360:offset]=b'x'*(offset-360)
    return bytes(raw)


def bold(**kwargs):
    return gzip.compress(header(**kwargs)+b'THIS IS NOT A VOXEL ARRAY',mtime=0)


def confounds(*,n=6,missing=None,columns=None):
    columns=list(s.NUISANCE if columns is None else columns)
    rows=[]
    for i in range(n):
        row=[str((i+1)/10) for _ in columns]
        if missing and i==missing[0]: row[columns.index(missing[1])]=missing[2]
        rows.append('\t'.join(row))
    return ('\t'.join(columns)+'\n'+'\n'.join(rows)+'\n').encode()


def table_rows(rows):
    return ('participant_id\tAge\tChild_Adult\tunrequested_private_field\n'+
            '\n'.join('\t'.join(row) for row in rows)+'\n').encode()


def row_identity(path,role,sid,raw):
    row=dict(path=path,role=role,participant_id=sid,size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    if role=='template': row['git_blob_sha1']=hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()
    else: row['md5']=hashlib.md5(raw).hexdigest()
    return row


@pytest.fixture
def bundle(tmp_path):
    source=tmp_path/'originals'; source.mkdir(); manifest_path=tmp_path/'source_manifest.json'
    ids=('sub-pixar001','sub-pixar002'); files=[]
    def add(path,role,sid,raw):
        target=source/path; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(raw)
        files.append(row_identity(path,role,sid,raw))
    for sid in ids:
        add(f'{sid}_task-pixar_space-MNI152NLin2009cAsym_desc-preproc_bold.nii.gz','bold',sid,bold())
        add(f'{sid}_task-pixar_desc-confounds_regressors.tsv','confounds',sid,confounds())
    add('participants.tsv','participants',None,table_rows([[ids[1],'20','adult','DO_NOT_REPORT'],[ids[0],'6','child','DO_NOT_REPORT']]))
    add('template/future.nii.gz','template',None,b'OPAQUE TEMPLATE; NEVER PARSE')
    manifest=dict(task_id='SOCIALBRAIN-001',schema_version='fixture-source-v1',participant_ids=list(ids),
        n_files=len(files),total_bytes=sum(row['size_bytes'] for row in files),files=files)
    raw=json.dumps(manifest).encode(); manifest_path.write_bytes(raw); (source/'source_manifest.json').write_bytes(raw)
    policy=s.Policy(hashlib.sha256(raw).hexdigest(),{'nibabel':importlib.metadata.version('nibabel')},participant_ids=ids)
    return dict(source=source,manifest_path=manifest_path,manifest=manifest,policy=policy,output=tmp_path/'evidence')


def repin(bundle):
    manifest=bundle['manifest']; manifest['n_files']=len(manifest['files'])
    manifest['total_bytes']=sum(row['size_bytes'] for row in manifest['files'])
    raw=json.dumps(manifest).encode()
    bundle['manifest_path'].write_bytes(raw); (bundle['source']/'source_manifest.json').write_bytes(raw)
    bundle['policy']=replace(bundle['policy'],manifest_sha=hashlib.sha256(raw).hexdigest())


def replace_member(bundle,name,raw):
    row=next(row for row in bundle['manifest']['files'] if row['path']==name)
    (bundle['source']/name).write_bytes(raw)
    row.update(row_identity(name,row['role'],row['participant_id'],raw)); repin(bundle)


def run(bundle):
    return s.execute(bundle['source'],bundle['manifest_path'],bundle['output'],policy=bundle['policy'])


def test_complete_metadata_only_two_passes_input_immutable(bundle):
    before={p:p.read_bytes() for p in bundle['source'].rglob('*') if p.is_file()}
    result=run(bundle)
    assert result['status']=='ok' and result['total_frames']==12
    assert result['authentication']['complete_opaque_hash_passes']==2
    assert result['authentication']['total_source_bytes_hashed']==2*bundle['manifest']['total_bytes']
    assert result['authentication']['original_members']==5
    assert result['authentication']['opaque_only_members']==['template/future.nii.gz']
    assert result['phenotype']['group_token_counts']=={'adult':1,'child':1}
    assert 'DO_NOT_REPORT' not in json.dumps(result)
    for person in result['persons'].values():
        h=person['bold_header']
        assert h['bold_voxel_bytes_decoded']==0 and h['logical_header_bytes_decoded']==352
        assert h['decoded_file_length_verified'] is False
        assert person['confounds']['columns_diagnostics']['framewise_displacement']['observed_finite_count']==6
    assert not any(result[key] for key in ('bold_values_decoded','template_values_decoded','template_or_ROI_support_computed',
        'cleaning_rank_computed','connectivity_computed','source_writes'))
    assert all(path.read_bytes()==raw for path,raw in before.items())
    assert set(p.name for p in bundle['output'].iterdir())=={'attempt.json','report.json'}
    assert signal.getitimer(signal.ITIMER_REAL)==(0.,0.)


@pytest.mark.parametrize('endian',['<','>'])
@pytest.mark.parametrize('scaling',[(1.,0.),(2.,-3.),(0.,99.),(float('nan'),float('nan'))])
def test_header_endianness_raw_and_effective_scaling(bundle,endian,scaling):
    result=s.header_from_bytes(bold(endian=endian,slope=scaling[0],inter=scaling[1]),bundle['policy'],lambda:None)
    assert result['endianness']==endian and result['shape']==[3,4,5,6]
    assert result['effective_slope']==(1. if scaling[0]==0 or scaling[0]!=scaling[0] else scaling[0])
    assert result['effective_intercept']==(0. if scaling[0]==0 or scaling[0]!=scaling[0] else scaling[1])
    assert result['bold_voxel_bytes_decoded']==0


@pytest.mark.parametrize('units,tr,expected',[(10,2.,2.),(18,2000.,2.),(26,2000000.,2.),(2,2.,None)])
def test_header_clock_is_observed_not_replaced(bundle,units,tr,expected):
    result=s.header_from_bytes(bold(units=units,tr=tr),bundle['policy'],lambda:None)
    assert result['header_tr_seconds']==expected and result['zooms'][3]==tr


def test_header_extensions_only_no_payload_decode(bundle):
    result=s.header_from_bytes(bold(offset=384,extension=True),bundle['policy'],lambda:None)
    assert result['logical_header_bytes_decoded']==384 and result['extensions'][0]['esize']==32
    assert result['extension_flag_hex']=='01000000'


@pytest.mark.parametrize('mode',['truncated','magic','shape3','zero_shape','complex','offset_small','offset_nonintegral',
    'offset_too_large','affine_nonfinite','affine_singular','bad_extension','unflagged_extension','bad_gzip'])
def test_malformed_header_fails_closed(bundle,mode):
    raw=bytearray(header())
    if mode=='truncated': payload=gzip.compress(bytes(raw[:100]))
    elif mode=='bad_gzip': payload=b'not gzip'
    else:
        if mode=='magic': raw[344:348]=b'ni1\0'
        elif mode=='shape3': struct.pack_into('<h',raw,40,3)
        elif mode=='zero_shape': struct.pack_into('<h',raw,42,0)
        elif mode=='complex': struct.pack_into('<hh',raw,70,32,64)
        elif mode=='offset_small': struct.pack_into('<f',raw,108,348.)
        elif mode=='offset_nonintegral': struct.pack_into('<f',raw,108,352.5)
        elif mode=='offset_too_large': struct.pack_into('<f',raw,108,2*s.MIB)
        elif mode=='affine_nonfinite': struct.pack_into('<f',raw,280,float('nan'))
        elif mode=='affine_singular': struct.pack_into('<4f',raw,280,0.,0.,0.,0.)
        elif mode=='bad_extension':
            raw=bytearray(header(offset=368,extension=True)); struct.pack_into('<i',raw,352,17)
        elif mode=='unflagged_extension': raw=bytearray(header(offset=368,extension=True)); raw[348]=0
        payload=gzip.compress(raw)
    with pytest.raises((ValueError,EOFError,zlib.error)):
        s.header_from_bytes(payload,bundle['policy'],lambda:None)


@pytest.mark.parametrize('token,kind',[('','empty'),('n/a','nonnumeric'),('NA','nonnumeric'),
    ('NaN','nonfinite'),('Infinity','nonfinite'),('-inf','nonfinite'),('True','nonnumeric'),(' 1.25 ','finite')])
def test_confound_literal_token_diagnostics_no_imputation(bundle,token,kind):
    report=s.confounds(confounds(missing=(0,'framewise_displacement',token)),bundle['policy'])
    item=report['columns_diagnostics']['framewise_displacement']
    assert item['counts'][kind]==(6 if kind=='finite' else 1)
    assert item['observed_finite_count']==(6 if kind=='finite' else 5)
    if kind!='finite': assert item['exceptions']==[dict(row_index=0,token=token,kind=kind)]
    assert report['imputation'] is False and item['missing_or_invalid_values_imputed'] is False


def test_all_nonfinite_fd_keeps_null_descriptive_statistics(bundle):
    columns=list(s.NUISANCE); idx=columns.index('framewise_displacement')
    rows=[['0']*len(columns) for _ in range(2)]
    for row in rows: row[idx]='nan'
    raw=('\t'.join(columns)+'\n'+'\n'.join('\t'.join(row) for row in rows)+'\n').encode()
    item=s.confounds(raw,bundle['policy'])['columns_diagnostics']['framewise_displacement']
    assert item['observed_finite_count']==0 and item['observed_finite_sum'] is None and item['observed_finite_mean'] is None


@pytest.mark.parametrize('mode',['duplicate_column','blank_column','ragged','comma_delimited','nul','field_too_long'])
def test_table_schema_and_bounds(bundle,mode):
    raw=confounds()
    if mode=='duplicate_column': raw=raw.replace(b'trans_y',b'trans_x',1)
    elif mode=='blank_column': raw=raw.replace(b'trans_x',b'',1)
    elif mode=='ragged': raw+=b'1\t2\n'
    elif mode=='comma_delimited': raw=raw.replace(b'\t',b',')
    elif mode=='nul': raw+=b'\0'
    else: raw=raw.replace(b'0.1',b'0'*(bundle['policy'].max_table_field_bytes+1),1)
    if mode=='comma_delimited':
        # Do not guess a delimiter; explicitly reports all required names missing.
        assert set(s.confounds(raw,bundle['policy'])['missing_required'])==set(s.NUISANCE)
    else:
        with pytest.raises(ValueError): s.confounds(raw,bundle['policy'])


def test_table_rows_bounded_during_parse(bundle):
    policy=replace(bundle['policy'],max_table_rows=2)
    with pytest.raises(ValueError,match='table_shape'):
        s.confounds(confounds(n=3),policy)


@pytest.mark.parametrize('mode',['duplicate','missing','alias','extra'])
def test_phenotype_exact_literal_cohort(bundle,mode):
    rows=[['sub-pixar001','6','child','ignored'],['sub-pixar002','20','adult','ignored']]
    if mode=='duplicate': rows[1][0]=rows[0][0]
    elif mode=='missing': rows.pop()
    elif mode=='alias': rows[0][0]='1'
    else: rows.append(['sub-pixar003','10','child','ignored'])
    with pytest.raises(ValueError): s.phenotype(table_rows(rows),bundle['policy'])


@pytest.mark.parametrize('mode',['selected_missing','selected_nonfinite','missing_column','frame_mismatch','unknown_group','bad_age','unknown_units'])
def test_structural_issues_preserved_without_eligibility_or_filling(bundle,mode):
    conf=next(row['path'] for row in bundle['manifest']['files'] if row['role']=='confounds')
    image=next(row['path'] for row in bundle['manifest']['files'] if row['role']=='bold')
    if mode=='selected_missing': replace_member(bundle,conf,confounds(missing=(2,'csf','n/a')))
    elif mode=='selected_nonfinite': replace_member(bundle,conf,confounds(missing=(2,'csf','nan')))
    elif mode=='missing_column': replace_member(bundle,conf,confounds(columns=s.NUISANCE[:-1]))
    elif mode=='frame_mismatch': replace_member(bundle,conf,confounds(n=5))
    elif mode=='unknown_units': replace_member(bundle,image,bold(units=0))
    else:
        rows=[['sub-pixar001','6','child','ignored'],['sub-pixar002','20','adult','ignored']]
        rows[0][2 if mode=='unknown_group' else 1]='unexpected'
        replace_member(bundle,'participants.tsv',table_rows(rows))
    result=run(bundle)
    assert result['status']=='structural_issues' and result['issues'] and len(result['persons'])==2
    assert (bundle['output']/'failure_report.json').is_file() and not result['connectivity_computed']


def test_all_files_authenticated_before_any_header_or_table(bundle,monkeypatch):
    last=bundle['manifest']['files'][-1]; (bundle['source']/last['path']).write_bytes(b'changed')
    def forbidden(*args,**kwargs): raise AssertionError('PARSED BEFORE FULL AUTH')
    monkeypatch.setattr(s,'header_from_bytes',forbidden); monkeypatch.setattr(s,'confounds',forbidden)
    result=run(bundle)
    assert result['status']=='failed' and result['reason'].startswith('source_')


@pytest.mark.parametrize('mode',['extra','missing','symlink','special','empty_dir','internal_manifest'])
def test_closed_bundle_and_internal_manifest(bundle,mode):
    path=bundle['source']/bundle['manifest']['files'][0]['path']
    if mode=='extra': (bundle['source']/'extra').write_bytes(b'x')
    elif mode=='missing': path.unlink()
    elif mode=='symlink': path.unlink(); path.symlink_to(bundle['manifest_path'])
    elif mode=='special':
        import os
        path.unlink(); os.mkfifo(path)
    elif mode=='empty_dir': (bundle['source']/'empty').mkdir()
    else: (bundle['source']/'source_manifest.json').write_bytes(b'{}')
    result=run(bundle)
    assert result['status']=='failed' and (bundle['output']/'failure_report.json').is_file()


@pytest.mark.parametrize('mode',['sha','md5','git','traversal','boolean_size','extra_scientific','cohort','n_files','total_bytes'])
def test_manifest_authority_and_identity_domains(bundle,mode):
    rows=bundle['manifest']['files']
    if mode=='sha': rows[0]['sha256']='0'*64
    elif mode=='md5': rows[0]['md5']='0'*32
    elif mode=='git': rows[-1]['git_blob_sha1']='0'*40
    elif mode=='traversal': rows[0]['path']='../escape'
    elif mode=='boolean_size': rows[0]['size_bytes']=True
    elif mode=='extra_scientific': rows[-1]['role']='bold'
    elif mode=='cohort': bundle['manifest']['participant_ids'].reverse()
    repin(bundle)
    if mode in ('n_files','total_bytes'):
        obj=bundle['manifest']; obj[mode]+=1
        raw=json.dumps(obj).encode(); bundle['manifest_path'].write_bytes(raw); (bundle['source']/'source_manifest.json').write_bytes(raw)
        bundle['policy']=replace(bundle['policy'],manifest_sha=hashlib.sha256(raw).hexdigest())
    result=run(bundle)
    assert result['status']=='failed'


@pytest.mark.parametrize('mode',['manifest','software','version'])
def test_unfrozen_and_wrong_software_fail_closed(bundle,mode):
    if mode=='manifest': bundle['policy']=replace(bundle['policy'],manifest_sha=None)
    elif mode=='software': bundle['policy']=replace(bundle['policy'],versions=None)
    else: bundle['policy']=replace(bundle['policy'],versions={'nibabel':'0.0.invalid'})
    assert run(bundle)['status']=='failed'


def test_default_cli_is_plan_only_even_with_nonexistent_paths(capsys,monkeypatch):
    def forbidden(*args,**kwargs): raise AssertionError('default read')
    monkeypatch.setattr(s,'safe_path',forbidden)
    assert s.main(['--source-dir','/nonexistent','--manifest','/never','--output-dir','/never'])==0
    assert json.loads(capsys.readouterr().out)['source_reads']==0


@pytest.mark.parametrize('mode',['existing','inside_source','source_ancestor','manifest_ancestor'])
def test_protected_and_fresh_evidence_no_write(bundle,mode):
    if mode=='existing': bundle['output'].mkdir(); (bundle['output']/'keep').write_bytes(b'keep')
    elif mode=='inside_source': bundle['output']=bundle['source']/'output'
    elif mode=='source_ancestor': bundle['output']=bundle['source'].parent
    else: bundle['output']=bundle['manifest_path'].parent
    before={p:p.read_bytes() for p in bundle['source'].rglob('*') if p.is_file()}
    with pytest.raises(ValueError): run(bundle)
    assert all(p.read_bytes()==raw for p,raw in before.items())


def test_between_pass_change_rejected(bundle,monkeypatch):
    original=s.authenticated_bytes; calls=0; n=len(bundle['manifest']['files'])
    def hook(path,row,check,**kwargs):
        nonlocal calls
        calls+=1
        if calls==n+1: path.write_bytes(b'changed')
        return original(path,row,check,**kwargs)
    monkeypatch.setattr(s,'authenticated_bytes',hook)
    assert run(bundle)['status']=='failed'


def test_postconsumption_signature_change_rejected(bundle,monkeypatch):
    original=s.confounds; changed=False
    def hook(raw,policy):
        nonlocal changed
        result=original(raw,policy)
        if not changed:
            import os
            path=bundle['source']/bundle['manifest']['files'][0]['path']; info=path.stat()
            os.utime(path,ns=(info.st_atime_ns,info.st_mtime_ns+1_000_000_000)); changed=True
        return result
    monkeypatch.setattr(s,'confounds',hook)
    result=run(bundle)
    assert result['status']=='failed' and result['reason']=='postconsumption_source_stat_changed'
