"""Manufactured N170 fixtures; no original SET/FDT mounts or live requests.

Adapted from reviewed PR185 test_inspect_set_headers.py SHA256
567df80c282d0e64d37be8fa3b199ba25a4820b30a3154c82179386ac3d8d6e8.
"""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import zlib

import numpy as np
import pytest
from scipy.io import savemat

SCANNER = Path(__file__).resolve().parents[1]/'tests'/'mat_metadata.py'
SPEC = importlib.util.spec_from_file_location('n170_authoring_mat', SCANNER)
h = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(h)


def fields():
    return dict(data='fixture.fdt',nbchan=2,pnts=8,trials=1,srate=500.0,
                xmin=0.0,xmax=0.014,ref='literal-custom-reference',history='not a filter claim',
                unit='source-token',chanlocs=[dict(labels='PO7',type='custom',X=1.0),dict(labels='PO8',type='',X=2.0)],
                event=[dict(type=1,latency=2.5,duration=0,urevent=1,custom='keep'),
                       dict(type='41',latency=3.0,duration=1,urevent=2,custom='keep2'),
                       dict(type='boundary',latency=4.5,duration=2,urevent=3,custom='keep3')],
                urevent=[dict(type=1,latency=2.5),dict(type='41',latency=3.0),dict(type='boundary',latency=4.5)],
                times=np.arange(8)*2.0,icaweights=np.ones((2,2)),icasphere=np.eye(2),
                icawinv=np.eye(2),icachansind=np.arange(2)+1,icaact=np.zeros((2,8)))


def mat(values=None, nested=False, compressed=False):
    values=fields() if values is None else values
    buf=io.BytesIO();savemat(buf,{'EEG':values} if nested else values,do_compression=compressed)
    return buf.getvalue()


@pytest.mark.parametrize('nested',[False,True])
@pytest.mark.parametrize('compressed',[False,True])
def test_supported_layouts(nested,compressed):
    report=h.inspect_set(mat(nested=nested,compressed=compressed),2,'fixture.fdt',64)
    assert report['mat_layout']==('scalar_EEG_struct' if nested else 'flat_fields')
    assert report['header_fields']['srate']==500
    assert report['literal_data_pointer']=='fixture.fdt'
    assert report['requested_channel_matches']=={label:([0] if label=='PO7' else [1] if label=='PO8' else []) for label in h.SCALP_CHANNELS}
    assert report['observed_channel_count']==2 and not report['original_channel_count_matches_expected']
    assert report['channels'][0]['original_fields']['type']=='custom'
    assert report['n_events']==3 and report['n_boundaries']==1
    assert report['repeated_rounded_target_samples']==[{'sample':2,'source_event_indices':[0,1]}]
    assert report['events'][0]['original_fields']['custom']=='keep'
    assert len(report['urevents'])==3 and report['ica_fields_shapes_only']['icaweights']['shape']==[2,2]
    assert 'times' in report['other_fields_not_decoded']
    assert report['float32_byte_equation_matches'] and not report['fdt_decoded']


def test_only_selected_metadata_value_decoding(monkeypatch):
    called=[];original=h.MatScan.decode
    def observe(self,node):
        called.append(node['name']);return original(self,node)
    monkeypatch.setattr(h.MatScan,'decode',observe)
    h.inspect_set(mat(),2,'fixture.fdt',64)
    assert called[0]=='data'
    assert 'times' not in called and not set(h.ICA_FIELDS).intersection(called)
    assert set(called)==set(fields()).intersection(h.FIELDS)|{'data'}


@pytest.mark.parametrize('value',[np.zeros((2,8)),np.array(['x'],dtype=object),{'hidden':np.ones(9)}])
def test_inline_or_indirect_data_rejected_before_decoder(value,monkeypatch):
    f=fields();f['data']=value
    monkeypatch.setattr(h,'loadmat',lambda *a,**k:pytest.fail('decoder entered before external-data guard'))
    with pytest.raises(ValueError,match='external_character_data'):h.inspect_set(mat(f),2,'fixture.fdt',64)


def test_wrong_pointer_stops_before_other_decodes(monkeypatch):
    calls=[];original=h.MatScan.decode
    def observe(self,node):calls.append(node['name']);return original(self,node)
    monkeypatch.setattr(h.MatScan,'decode',observe)
    with pytest.raises(ValueError,match='pointer'):h.inspect_set(mat(),2,'other.fdt',64)
    assert calls==['data']


def element(typ,payload,endian='<',small=False):
    if small:return struct.pack(endian+'I',(len(payload)<<16)|typ)+payload+b'\0'*(4-len(payload))
    return struct.pack(endian+'II',typ,len(payload))+payload+b'\0'*((-len(payload))%8)


def matrix(name,cls,shape,payload,endian='<'):
    body=element(6,struct.pack(endian+'II',cls,0),endian)
    body+=element(5,struct.pack(endian+'i'*len(shape),*shape),endian)
    body+=element(1,name.encode(),endian,small=0<len(name)<=4)+payload
    return element(14,body,endian)


def header(endian='<'):
    return b'MATLAB 5.0 MAT-file manufactured'.ljust(116,b' ')+b'\0'*8+struct.pack(endian+'H',256)+(b'IM' if endian=='<' else b'MI')


@pytest.mark.parametrize('endian',['<','>'])
@pytest.mark.parametrize('small',[False,True])
def test_endian_correct_normal_and_small_tag(endian,small):
    scanner=h.MatScan(header(endian))
    encoded=element(1,b'abc',endian,small)
    assert scanner.tag(encoded,0)==(1,b'abc',len(encoded))


@pytest.mark.parametrize('endian',['<','>'])
def test_endian_numeric_matrix_and_value_decoder(endian):
    raw=header(endian)+matrix('x',6,(1,1),element(9,struct.pack(endian+'d',500.0),endian),endian)
    scanner=h.MatScan(raw);nodes,_=scanner.fields()
    assert scanner.decode(nodes['x'])==500.0


@pytest.mark.parametrize('raw',[b'',b'MATLAB 7.3'+b' '*128,header()+b'x',header()+element(1,b'x'),header()+element(15,b'not-zlib')])
def test_invalid_or_unsupported_mat(raw):
    with pytest.raises((ValueError,zlib.error)):h.MatScan(raw)


def test_duplicate_variables_and_ambiguous_layout():
    one=mat({'x':1})
    with pytest.raises(ValueError,match='duplicate'):h.MatScan(one+one[128:]).fields()
    with pytest.raises(ValueError,match='ambiguous'):h.MatScan(mat({'EEG':fields(),'pnts':8})).fields()


def test_non_scalar_eeg_rejected():
    with pytest.raises(ValueError,match='non_scalar'):h.MatScan(mat({'EEG':[fields(),fields()]})).fields()


def test_compression_bound_and_trailing_stream(monkeypatch):
    payload=matrix('x',6,(1,1),element(9,struct.pack('<d',1.0)))
    monkeypatch.setattr(h,'MAX_EXPANDED_BYTES',8)
    compressed=zlib.compress(payload)
    raw=header()+struct.pack('<II',15,len(compressed))+compressed
    with pytest.raises(ValueError,match='compressed_mat'):h.MatScan(raw)
    monkeypatch.setattr(h,'MAX_EXPANDED_BYTES',10000)
    compressed+=b'tail';raw=header()+struct.pack('<II',15,len(compressed))+compressed
    with pytest.raises(ValueError,match='compressed_mat'):h.MatScan(raw)


@pytest.mark.parametrize('kind',['numeric_shape','nested_cell_shape','nested_struct_shape','depth','unsupported_class'])
def test_recursive_allocation_guards_before_loadmat(kind,monkeypatch):
    child=matrix('',6,(1,1),element(9,struct.pack('<d',1)))
    if kind=='numeric_shape':root=matrix('x',6,(2_000_001,1),b'')
    elif kind=='nested_cell_shape':root=matrix('x',1,(1,1),matrix('',6,(2_000_001,1),b''))
    elif kind=='nested_struct_shape':
        payload=element(5,struct.pack('<i',2),small=True)+element(1,b'a\0')+matrix('',6,(2_000_001,1),b'')
        root=matrix('x',2,(1,1),payload)
    elif kind=='unsupported_class':root=matrix('x',5,(1,1),b'')
    else:
        for _ in range(34):child=matrix('',1,(1,1),child)
        root=matrix('x',1,(1,1),child)
    scanner=h.MatScan(header()+root);nodes,_=scanner.fields()
    monkeypatch.setattr(h,'loadmat',lambda *a,**k:pytest.fail('decoder entered despite metadata bound'))
    with pytest.raises(ValueError):scanner.decode(nodes['x'])


@pytest.mark.parametrize('field,value',[('nbchan',0),('pnts',1.5),('trials',-1),('srate',0),('srate',np.inf)])
def test_dimensions_and_rate(field,value):
    f=fields();f[field]=value
    with pytest.raises(ValueError,match='invalid_source'):h.inspect_set(mat(f),2,'fixture.fdt',64)


def test_structural_mismatch_and_unknown_units_are_observed_not_imputed():
    f=fields();f['unit']='unknown';f['chanlocs'][0]['type']='not-inferred'
    report=h.inspect_set(mat(f),2,'fixture.fdt',63)
    assert not report['float32_byte_equation_matches'] and report['header_fields']['unit']=='unknown'
    assert report['channels'][0]['original_fields']['type']=='not-inferred'


def test_literal_event_types_boundaries_missing_nonfinite_and_no_trial_selection():
    records=[dict(type='1',latency=1),dict(type='1.0',latency=2),dict(type=-99,latency=0),
             dict(type='custom',latency=np.nan,duration=np.inf),dict(type=[1,41],latency=9)]
    report=h.event_ledger(records,8)
    assert report['n_events']==5 and report['candidate_target_counts']=={'face':1}
    assert report['events'][1]['candidate_target_field'] is None
    assert report['events'][2]['diagnostic_sample_in_data'] is False
    assert report['events'][3]['original_latency']=={'source_nonfinite':'nan'}
    assert report['events'][4]['original_type']==[1,41]


def bundle(tmp_path,monkeypatch):
    source=tmp_path/'source';source.mkdir();rows=[]
    for subject in h.SUBJECTS:
        f=fields();f['data']=f'{subject}_N170_shifted_ds.fdt'
        for role,raw in [('set',mat(f)),('fdt',b'\x81'*64)]:
            path=f'{subject}_N170_shifted_ds.{role}';(source/path).write_bytes(raw)
            rows.append(dict(subject=subject,role=role,path=path,size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    monkeypatch.setattr(h,'EXPECTED_SOURCE_BYTES',sum(row['size_bytes'] for row in rows))
    manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps({'files':rows}))
    return source,manifest,hashlib.sha256(manifest.read_bytes()).hexdigest()


def test_complete_manufactured_bundle_and_reports(tmp_path,monkeypatch):
    source,manifest,pin=bundle(tmp_path,monkeypatch);out=tmp_path/'report'
    result=h.run(source,manifest,pin,out)
    assert result['n_authenticated_originals']==74 and len(result['subject_summaries'])==37
    assert len(list(out.glob('subject_*.json')))==37 and not (out/'failure_report.json').exists()
    assert all(v['float32_byte_equation_matches'] for v in result['subject_summaries'])


@pytest.mark.parametrize('mode',['manifest_hash','source_hash','missing','extra_file','empty_dir','symlink','dangling','fifo'])
def test_authentication_precedes_any_set_parse(mode,tmp_path,monkeypatch):
    source,manifest,pin=bundle(tmp_path,monkeypatch)
    if mode=='manifest_hash':manifest.write_bytes(manifest.read_bytes()+b' ')
    elif mode=='source_hash':(source/'13_N170_shifted_ds.fdt').write_bytes(b'\x82'*64)
    elif mode=='missing':(source/'13_N170_shifted_ds.fdt').unlink()
    elif mode=='extra_file':(source/'extra').write_text('x')
    elif mode=='empty_dir':(source/'empty').mkdir()
    elif mode=='fifo':os.mkfifo(source/'pipe')
    else:(source/'link').symlink_to('2_N170_shifted_ds.fdt' if mode=='symlink' else 'absent')
    monkeypatch.setattr(h,'inspect_set',lambda *a,**k:pytest.fail('SET parsed before complete authentication'))
    out=tmp_path/'report'
    with pytest.raises((ValueError,FileNotFoundError)):h.run(source,manifest,pin,out)
    receipt=json.loads((out/'failure_report.json').read_text())
    assert receipt['phase']=='authenticate_all_74_originals' and receipt['completed_subjects']==[]


@pytest.mark.parametrize('mode',['existing','inside_source','source_ancestor','symlink_parent','dotdot','code_directory'])
def test_destination_safety(mode,tmp_path,monkeypatch):
    source,manifest,pin=bundle(tmp_path,monkeypatch);out=tmp_path/'report'
    if mode=='existing':out.mkdir();(out/'preserve').write_text('unchanged')
    elif mode=='inside_source':out=source/'report'
    elif mode=='source_ancestor':out=tmp_path
    elif mode=='symlink_parent':(tmp_path/'alias').symlink_to(tmp_path,target_is_directory=True);out=tmp_path/'alias'/'report'
    elif mode=='dotdot':out=str(tmp_path)+'/source/../report'
    else:out=Path(h.__file__).parent/'new-evidence'
    with pytest.raises(ValueError):h.run(source,manifest,pin,out)
    if mode=='existing':assert (out/'preserve').read_text()=='unchanged'


def test_late_parser_failure_retains_partial_evidence(tmp_path,monkeypatch):
    source,manifest,pin=bundle(tmp_path,monkeypatch);original=h.inspect_set
    def fail_second(raw,subject,*args):
        if subject==3:raise ValueError('manufactured unsupported metadata')
        return original(raw,subject,*args)
    monkeypatch.setattr(h,'inspect_set',fail_second);out=tmp_path/'report'
    with pytest.raises(ValueError):h.run(source,manifest,pin,out)
    assert (out/'subject_002.json').is_file() and not (out/'report.json').exists()
    assert json.loads((out/'failure_report.json').read_text())['completed_subjects']==[2]


@pytest.mark.parametrize('raw',[b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":[1e999]}'])
def test_strict_json(raw):
    with pytest.raises(ValueError):h.strict_json(raw)


def test_default_plan_does_not_read_paths(monkeypatch,capsys):
    monkeypatch.setattr(h,'run',lambda *a:pytest.fail('implicit original execution'))
    assert h.main(['--source-dir','/not-mounted','--manifest','/not-mounted/manifest'])==0
    assert json.loads(capsys.readouterr().out)['status']=='plan_only'


def test_import_does_not_enter_main():
    result=subprocess.run([sys.executable,'-c','import mat_metadata'],cwd=Path(h.__file__).parent,
                          capture_output=True,text=True,timeout=20)
    assert result.returncode==0 and result.stdout=='' and result.stderr==''


def test_fixed_n170_cohort_and_prospective_bounds():
    assert h.SUBJECTS==tuple(s for s in range(1,41) if s not in (1,5,16))
    assert len(h.SUBJECTS)==37 and h.SOURCE_FILE_COUNT==74
    assert h.EXPECTED_SOURCE_BYTES==788438272 and h.MAX_SET_BYTES==16*1024**2
    assert len(h.SCALP_CHANNELS)==len(set(h.SCALP_CHANNELS))==30
    assert h.EXPECTED_ORIGINAL_CHANNEL_COUNT==33


@pytest.mark.parametrize('mode',['excluded_subject','missing_role','duplicate_role','wrong_basename','total_bytes'])
def test_exact_n170_manifest_identity_before_member_reads(mode,tmp_path,monkeypatch):
    source,manifest,_=bundle(tmp_path,monkeypatch)
    doc=json.loads(manifest.read_bytes())
    if mode=='excluded_subject':doc['files'][0]['subject']=1
    elif mode=='missing_role':doc['files'].pop()
    elif mode=='duplicate_role':doc['files'][-1]=doc['files'][0].copy()
    elif mode=='wrong_basename':doc['files'][0]['path']='2_N2pc_shifted_ds.set'
    else:monkeypatch.setattr(h,'EXPECTED_SOURCE_BYTES',h.EXPECTED_SOURCE_BYTES+1)
    manifest.write_text(json.dumps(doc));pin=hashlib.sha256(manifest.read_bytes()).hexdigest()
    monkeypatch.setattr(h,'file_hash',lambda *a:pytest.fail('member read before manifest validation'))
    with pytest.raises(ValueError):h.authenticate(source,manifest,pin)


def test_original_33_channel_records_and_all_30_scalp_matches():
    f=fields();labels=list(h.SCALP_CHANNELS)+['manufactured-EOG-A','manufactured-EOG-B','manufactured-extra']
    f['nbchan']=33
    f['chanlocs']=[dict(labels=label,type='literal-'+str(i),custom={'retained':i}) for i,label in enumerate(labels)]
    report=h.inspect_set(mat(f),2,'fixture.fdt',33*8*4)
    assert report['observed_channel_labels']==labels and report['original_channel_count_matches_expected']
    assert report['requested_channel_matches']=={label:[i] for i,label in enumerate(h.SCALP_CHANNELS)}
    assert report['missing_scalp_labels']==report['duplicate_scalp_labels']==[]
    assert report['channels'][32]['original_fields']['type']=='literal-32'
    assert report['channels'][32]['original_fields']['custom']=={'retained':32}


def test_missing_duplicate_and_case_variant_channels_reported_without_repair():
    f=fields();f['nbchan']=3
    f['chanlocs']=[dict(labels='PO8'),dict(labels='PO8'),dict(labels='po7')]
    report=h.inspect_set(mat(f),2,'fixture.fdt',96)
    assert report['requested_channel_matches']['PO8']==[0,1]
    assert report['requested_channel_matches']['PO7']==[]
    assert report['duplicate_scalp_labels']==['PO8'] and 'PO7' in report['missing_scalp_labels']
    assert report['observed_channel_labels']==['PO8','PO8','po7']


@pytest.mark.parametrize('pointer', ['../fixture.fdt','/fixture.fdt','fixture.FDT','other.fdt',''])
def test_n170_external_pointer_literal_and_first(pointer,monkeypatch):
    f=fields();f['data']=pointer;calls=[];original=h.MatScan.decode
    def observe(self,node):calls.append(node['name']);return original(self,node)
    monkeypatch.setattr(h.MatScan,'decode',observe)
    with pytest.raises(ValueError,match='pointer'):h.inspect_set(mat(f),2,'fixture.fdt',64)
    assert calls==['data']


def test_face_car_all_codes_and_n2pc_codes_not_reused():
    tokens=list(range(1,81))+[0,81,111,112,121,122,211,212,221,222]
    report=h.event_ledger([dict(type=code,latency=i+1) for i,code in enumerate(tokens)],1000)
    assert report['n_events']==90 and report['candidate_target_counts']=={'face':40,'car':40}
    assert [row['original_type'] for row in report['events']]==tokens
    assert all(row['candidate_target_field'] is None for row in report['events'][80:])


def test_boundary_tokens_keep_literal_types_and_all_events():
    tokens=[-99,'-99',' Boundary ','boundary','BOUNDARY','-99.0','custom',1,'40',41,'80']
    report=h.event_ledger([dict(type=code,latency=2.5,duration=0,urevent=i+1) for i,code in enumerate(tokens)],8)
    assert [row['original_type'] for row in report['events']]==tokens
    assert report['boundary_event_indices']==[0,1,2,3,4]
    assert report['candidate_target_counts']=={'face':2,'car':2}
    assert report['repeated_rounded_target_samples']==[{'sample':2,'source_event_indices':[7,8,9,10]}]


def test_no_nonmetadata_arrays_or_external_fdt_decoder(tmp_path,monkeypatch):
    source,manifest,pin=bundle(tmp_path,monkeypatch)
    calls=[];decoder=h.loadmat
    def only_buffer(stream,*args,**kwargs):
        assert isinstance(stream,io.BytesIO) and kwargs['variable_names']==['value']
        calls.append(True);return decoder(stream,*args,**kwargs)
    monkeypatch.setattr(h,'loadmat',only_buffer)
    monkeypatch.setattr(h.np,'fromfile',lambda *a,**k:pytest.fail('FDT numerical read'))
    result=h.run(source,manifest,pin,tmp_path/'report')
    assert calls and not result['fdt_signal_decoded'] and not result['original_inline_EEG_signal_decoded']
    first=json.loads((tmp_path/'report/subject_002.json').read_bytes())
    assert {'times',*h.ICA_FIELDS}<=set(first['other_fields_not_decoded'])


def test_last_original_authenticated_before_first_set_decode(tmp_path,monkeypatch):
    source,manifest,pin=bundle(tmp_path,monkeypatch);seen=[];hash_file=h.file_hash;parse=h.inspect_set
    def track(path,size):seen.append(Path(path).name);return hash_file(path,size)
    def check(*args):
        assert len(seen)==74 and seen[-1]=='40_N170_shifted_ds.fdt'
        return parse(*args)
    monkeypatch.setattr(h,'file_hash',track);monkeypatch.setattr(h,'inspect_set',check)
    h.run(source,manifest,pin,tmp_path/'report')


def test_execution_alarm_is_300_seconds_without_reading_any_input(monkeypatch):
    alarms=[]
    monkeypatch.setattr(h.signal,'alarm',alarms.append)
    monkeypatch.setattr(h.signal,'signal',lambda *args:object())
    monkeypatch.setattr(h,'run',lambda *args:dict(status='structure_only',n_authenticated_originals=74,fdt_signal_decoded=False))
    assert h.main(['--inspect-headers','--source-dir','/unopened','--manifest','/unopened.json',
                   '--manifest-sha256','0'*64,'--output-dir','/uncreated'])==0
    assert alarms==[300,0]
