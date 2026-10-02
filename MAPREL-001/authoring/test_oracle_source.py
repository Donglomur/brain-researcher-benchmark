"""Only manufactured source buffers/files; never reads originals or a bank."""
import base64
import hashlib
import json
import os
import re
import zlib

import nibabel as nib
import numpy as np
import pytest

import source_reader as reader

IDS = (1,2,3,4)


def gifti(values, hemi, sphere=False):
    values = np.asarray(values,dtype=np.float32)
    arrays = [nib.gifti.GiftiDataArray(values,intent='NIFTI_INTENT_POINTSET' if sphere else 'NIFTI_INTENT_SHAPE')]
    if sphere:
        arrays.append(nib.gifti.GiftiDataArray(np.array([[0,1,2]],dtype=np.int32),intent='NIFTI_INTENT_TRIANGLE'))
    meta = nib.gifti.GiftiMetaData({'AnatomicalStructurePrimary':'CortexLeft' if hemi == 'L' else 'CortexRight'})
    return nib.gifti.GiftiImage(darrays=arrays,meta=meta).to_bytes()


def brain_axis():
    # Deliberately compressed, right-first and not ordered by local vertex.
    return (nib.cifti2.BrainModelAxis.from_surface(np.array([1,5,3,0]),6,name='CortexRight')
            +nib.cifti2.BrainModelAxis.from_surface(np.array([4,0,2,5]),6,name='CortexLeft'))


def atlas(brain=None,labels=None,table=None,transpose=False):
    brain = brain_axis() if brain is None else brain
    labels = np.array([3,4,4,0,2,1,1,0],dtype=np.int32) if labels is None else np.asarray(labels,dtype=np.int32)
    table = ({0:('background',(0.,0.,0.,0.)),**{
        i:(f'7Networks_{"LH" if i <= 2 else "RH"}_Vis_{i}',(1.,0.,0.,1.)) for i in IDS}}
        if table is None else table)
    axis = nib.cifti2.LabelAxis(['synthetic'],[table])
    axes = (brain,axis) if transpose else (axis,brain)
    data = labels[:,None] if transpose else labels[None,:]
    return nib.Cifti2Image(data,nib.cifti2.Cifti2Header.from_axes(axes)).to_bytes()


def payloads():
    points = np.column_stack((np.arange(1,7),np.arange(2,8),np.ones(6)*3))
    return dict(gradient_l=gifti([2,900,6,800,-4,700],'L'),
                thickness_l=gifti([10,90,14,80,3,70],'L'),
                gradient_r=gifti([900,-2,800,8,700,12],'R'),
                thickness_r=gifti([90,4,80,20,70,24],'R'),
                sphere_l=gifti(points,'L',True),sphere_r=gifti(points[:,[1,0,2]],'R',True),
                atlas=atlas())


def decoded(p=None):
    return reader.decode_join(payloads() if p is None else p,IDS)


def test_keyed_geometry_and_signed_means():
    joined = decoded(); result = reader.reduce_join(joined)
    assert [x.tolist() for x in joined['support']] == [[0,2],[4],[1],[3,5]]
    np.testing.assert_array_equal(result['maps'],[[4,12],[-4,3],[-2,4],[10,22]])
    np.testing.assert_allclose(np.linalg.norm(result['centroids'],axis=1),100)
    assert result['hemisphere'].tolist() == [0,0,1,1]
    assert result['support_n'].tolist() == [2,1,1,2]
    assert result['support_sha256'][0] == hashlib.sha256(b'MAPREL_support_v2\nL\n'+np.array([0,2],dtype='<i8').tobytes()).hexdigest()
    assert result['source_observed']['atlas']['excluded_zero_entries'] == 2


@pytest.mark.parametrize('operation',['axis_transpose','grayordinate_shuffle'])
def test_cifti_coherent_axis_and_vertex_permutations(operation):
    p = payloads()
    if operation == 'axis_transpose': p['atlas'] = atlas(transpose=True)
    else:
        order = np.array([6,1,4,0,7,2,5,3])
        p['atlas'] = atlas(brain_axis()[order],np.array([3,4,4,0,2,1,1,0])[order])
    result = reader.reduce_join(decoded(p)); base = reader.reduce_join(decoded())
    np.testing.assert_array_equal(result['maps'],base['maps'])
    np.testing.assert_array_equal(result['centroids'],base['centroids'])
    assert result['support_sha256'] == base['support_sha256']


def test_all400_fixed_parcels_are_required_and_supported():
    values = np.arange(202,dtype=np.float32)
    xyz = np.column_stack((values+1,values+2,values+3))
    p = {f'{role}_{h.lower()}':gifti(xyz if role=='sphere' else values,h,role=='sphere')
         for role in ('gradient','thickness','sphere') for h in ('L','R')}
    left=nib.cifti2.BrainModelAxis.from_surface(np.arange(200)[::-1],202,name='CortexLeft')
    right=nib.cifti2.BrainModelAxis.from_surface(np.arange(200)[::-1],202,name='CortexRight')
    table={0:('background',(0,0,0,0)),**{i:(f'7Networks_{"LH" if i<=200 else "RH"}_Default_{i}',(1,0,0,1)) for i in range(1,401)}}
    p['atlas']=atlas(right+left,np.r_[np.arange(201,401)[::-1],np.arange(1,201)[::-1]],table)
    result=reader.reduce_join(reader.decode_join(p))
    assert result['maps'].shape == (400,2)
    np.testing.assert_array_equal(result['maps'][:,0],np.tile(np.arange(200),2))
    assert np.all(result['support_n'] == 1)


@pytest.mark.parametrize('kind',['gradient','thickness'])
def test_unused_nonfinite_and_supported_zero_are_not_hidden_qc(kind):
    p=payloads();p[kind+'_l']=gifti([0,np.nan,6,np.inf,-4,np.nan],'L')
    assert len(decoded(p)['parcel_ids']) == 4


@pytest.mark.parametrize('value',[np.nan,np.inf,-np.inf])
def test_nonfinite_supported_map_fails(value):
    p=payloads();p['gradient_l']=gifti([value,0,1,2,3,4],'L')
    with pytest.raises(ValueError,match='finite supported'):decoded(p)


@pytest.mark.parametrize('case',['duplicate_vertex','outside_vertex','wrong_full_size','missing_id','cross_hemi_id','wrong_label_hemi','missing_table','extra_table'])
def test_literal_membership_failures(case):
    p=payloads();b=brain_axis();labels=np.array([3,4,4,0,2,1,1,0])
    table={0:('background',(0,0,0,0)),**{i:(f'7Networks_{"LH" if i<3 else "RH"}_Vis_{i}',(1,0,0,1)) for i in IDS}}
    if case=='duplicate_vertex':b.vertex[-2]=0
    elif case=='outside_vertex':b.vertex[-2]=6
    elif case=='wrong_full_size':p['gradient_l']=gifti(np.arange(5),'L')
    elif case=='missing_id':labels[0]=4
    elif case=='cross_hemi_id':labels[3]=1
    elif case=='wrong_label_hemi':table[1]=('7Networks_RH_Vis_1',(1,0,0,1))
    elif case=='missing_table':del table[2]
    elif case=='extra_table':table[9]=('unused',(1,0,0,1))
    p['atlas']=atlas(b,labels,table)
    with pytest.raises(ValueError):decoded(p)


def test_noncortical_zero_only():
    b=brain_axis()+nib.cifti2.BrainModelAxis.from_mask(np.ones((1,1,1),bool),name='ThalamusLeft')
    p=payloads();p['atlas']=atlas(b,[3,4,4,0,2,1,1,0,0])
    assert len(decoded(p)['parcel_ids']) == 4
    p['atlas']=atlas(b,[3,4,4,0,2,1,1,0,3])
    with pytest.raises(ValueError,match='noncortical'):decoded(p)


def test_zero_centroid_has_no_arbitrary_pole_rescue():
    joined=decoded();joined['data']['sphere_l'][[0,2]]=[[1,0,0],[-1,0,0]]
    with pytest.raises(ValueError,match='centroid'):reader.reduce_join(joined)


def test_wrong_hemisphere_declaration():
    with pytest.raises(ValueError,match='hemisphere'):reader.decode_gifti(gifti(np.arange(6),'R'),'gradient_l')


def test_standard_inert_doctype_is_removed_without_resolution():
    raw=gifti(np.arange(6),'L')
    assert b'<!DOCTYPE' in raw
    clean=reader.gifti_guard(raw)
    assert b'<!DOCTYPE' not in clean
    values,_=reader.decode_gifti(raw,'gradient_l')
    np.testing.assert_array_equal(values,np.arange(6))


@pytest.mark.parametrize('case',['internal_entity','other_doctype','external_data','huge_shape','wrong_expansion','compressed_bomb','trailing_stream','bad_base64','complex_type'])
def test_predecode_capacity_and_xml_guards(case,monkeypatch):
    raw=gifti(np.arange(6),'L')
    if case=='internal_entity':raw=raw.replace(b'<!DOCTYPE',b'<!ENTITY leak SYSTEM "file:///never">\n<!DOCTYPE',1)
    elif case=='other_doctype':raw=raw.replace(b'<!DOCTYPE GIFTI',b'<!DOCTYPE OTHER',1)
    elif case=='external_data':raw=raw.replace(b'ExternalFileName=""',b'ExternalFileName="/never"',1)
    elif case=='huge_shape':raw=raw.replace(b'Dim0="6"',b'Dim0="2000001"',1)
    elif case=='wrong_expansion':raw=raw.replace(b'Dim0="6"',b'Dim0="5"',1)
    elif case=='complex_type':raw=raw.replace(b'NIFTI_TYPE_FLOAT32',b'NIFTI_TYPE_COMPLEX64',1)
    else:
        data = b'not-base64!' if case=='bad_base64' else base64.b64encode(zlib.compress(b'\0'*(4096 if case=='compressed_bomb' else 24))+(b'extra' if case=='trailing_stream' else b''))
        raw=re.sub(rb'<Data>.*?</Data>',b'<Data>'+data+b'</Data>',raw,count=1,flags=re.S)
    monkeypatch.setattr(nib.gifti.GiftiImage,'from_bytes',lambda *a:pytest.fail('decoder called before guard'))
    with pytest.raises(ValueError) as caught:reader.decode_gifti(raw,'gradient_l')
    assert 'decoder called' not in str(caught.value)


def bundle(tmp_path,monkeypatch):
    root=tmp_path/'sources';root.mkdir();rows=[]
    for role,raw in {**payloads(),'provenance_notice':b'manufactured notice'}.items():
        name=f'members/{role}.bin';path=root/name;path.parent.mkdir(exist_ok=True);path.write_bytes(raw)
        rows.append(dict(role=role,path=name,size_bytes=len(raw),sha256=reader.sha(raw),
                         md5=hashlib.md5(raw).hexdigest(),git_blob_sha1=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()))
    manifest=dict(task_id='MAPREL-001',schema_version='maprel-source-v2',files=rows)
    paths=[]
    for stem,pin,doc in [('source_manifest','SOURCE_SHA',manifest),('method_contract','METHOD_SHA',{'task_id':'MAPREL-001'}),('output_schema','SCHEMA_SHA',{'task_id':'MAPREL-001'})]:
        raw=json.dumps(doc).encode();path=tmp_path/(stem+'.json');path.write_bytes(raw);paths.append(path)
        monkeypatch.setattr(reader,pin,reader.sha(raw))
        if pin=='SOURCE_SHA':(root/'source_manifest.json').write_bytes(raw)
    return root,paths,manifest


def repin(root,paths,manifest,monkeypatch):
    raw=json.dumps(manifest).encode();paths[0].write_bytes(raw);(root/'source_manifest.json').write_bytes(raw)
    monkeypatch.setattr(reader,'SOURCE_SHA',reader.sha(raw))


def test_closed_authenticated_same_buffers(tmp_path,monkeypatch):
    root,paths,manifest=bundle(tmp_path,monkeypatch)
    result=reader.authenticate(root,*paths)
    assert result['payloads']['atlas']==payloads()['atlas']
    assert len(result['source_files'])==8
    assert [r['path'] for r in result['source_files']]==sorted(r['path'] for r in manifest['files'])
    assert result['pins']['source_manifest_sha256']==reader.SOURCE_SHA


@pytest.mark.parametrize('case',['wrong_pin','changed_member','missing_member','extra_file','extra_directory','member_symlink','parent_symlink','fifo','internal_manifest_mismatch','bad_md5','bad_git','duplicate_role','duplicate_path','escape_path','absolute_path','missing_science','bool_size'])
def test_source_authentication_negatives_before_decode(tmp_path,monkeypatch,case):
    root,paths,manifest=bundle(tmp_path,monkeypatch);first=root/manifest['files'][0]['path']
    if case=='wrong_pin':monkeypatch.setattr(reader,'SOURCE_SHA','0'*64)
    elif case=='changed_member':first.write_bytes(b'x'*first.stat().st_size)
    elif case=='missing_member':first.unlink()
    elif case=='extra_file':(root/'extra').write_bytes(b'1')
    elif case=='extra_directory':(root/'empty').mkdir()
    elif case=='member_symlink':first.unlink();first.symlink_to(paths[1])
    elif case=='parent_symlink':link=tmp_path/'link';link.symlink_to(root,target_is_directory=True);root=link
    elif case=='fifo':first.unlink();os.mkfifo(first)
    elif case=='internal_manifest_mismatch':(root/'source_manifest.json').write_bytes(b'{}')
    else:
        row=manifest['files'][0]
        if case=='bad_md5':row['md5']='0'*32
        elif case=='bad_git':row['git_blob_sha1']='0'*40
        elif case=='duplicate_role':manifest['files'][1]['role']=row['role']
        elif case=='duplicate_path':manifest['files'][1]['path']=row['path']
        elif case=='escape_path':row['path']='../outside'
        elif case=='absolute_path':row['path']='/outside'
        elif case=='missing_science':row['role']='unused_role'
        elif case=='bool_size':row['size_bytes']=True
        repin(root,paths,manifest,monkeypatch)
    monkeypatch.setattr(reader,'decode_join',lambda *a:pytest.fail('decoded before complete authentication'))
    with pytest.raises(ValueError):reader.load_sources(root,*paths)


@pytest.mark.parametrize('raw',[b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":1e999}',b'['*66+b'0'+b']'*66])
def test_strict_json_duplicate_nonfinite_and_depth(raw):
    with pytest.raises(ValueError):reader.strict_json(raw)


def test_read_detects_changed_file_after_buffer_read(tmp_path,monkeypatch):
    path=tmp_path/'original';path.write_bytes(b'safe')
    true_signature=reader.signature;calls=[0]
    def changed(s):
        calls[0]+=1
        original=true_signature(s)
        return original+(calls[0],) if calls[0]>=3 else original
    monkeypatch.setattr(reader,'signature',changed)
    with pytest.raises(ValueError,match='changed during'):reader.read_bytes(path,reader.sha(b'safe'))
