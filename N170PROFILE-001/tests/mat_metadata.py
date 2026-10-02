"""Plan-first N170 shifted_ds SET metadata/event inspection; FDT is hashed, never decoded.

Classic MAT-v5 flat fields and a scalar EEG structure are supported. A bounded
container scan exposes field headers before any selected metadata is decoded.
Only the external-data character field is decoded first; inline EEG data stops
inspection. Whole EEG structures, times and ICA arrays are never passed to
loadmat. Unknown representations stop for review, without fallback readers.

Source-text adaptation of reviewed PR185 inspect_set_headers.py, SHA256
3b7e721ee66bc7f905b30ebd944cf30f91b07df32ecaba7d2ce8d8829f307b43.
MatScan is unchanged; cohort, filenames, event categories and channel diagnostics
are N170-specific. No trial selection or scientific estimator is executed.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import struct
import zlib

import numpy as np
from scipy.io import loadmat

SUBJECTS = tuple(s for s in range(1,41) if s not in (1,5,16))
SOURCE_FILE_COUNT = 74
EXPECTED_SOURCE_BYTES = 788_438_272
SCALP_CHANNELS = ('FP1','F3','F7','FC3','C3','C5','P3','P7','P9','PO7','PO3','O1','Oz','Pz','CPz',
                  'FP2','Fz','F4','F8','FC4','FCz','Cz','C4','C6','P4','P8','P10','PO8','PO4','O2')
EXPECTED_ORIGINAL_CHANNEL_COUNT = 33
MAX_SET_BYTES = 16 * 1024**2
MAX_EXPANDED_BYTES = 128 * 1024**2
MAX_METADATA_ELEMENTS = 2_000_000
MAX_EVENTS = 100_000
MAX_JSON_BYTES = 128 * 1024**2
FACE_CODES, CAR_CODES = frozenset(range(1,41)), frozenset(range(41,81))
FIELDS = frozenset(("setname filename filepath subject group condition session nbchan trials pnts srate xmin xmax ref saved datfile history comments unit units chanlocs chaninfo event urevent".split()))
ICA_FIELDS = frozenset(("icaweights icasphere icawinv icachansind icaact".split()))
TASK_ROOT = Path('/home/zijiaochen/projects/brain-researcher-benchmark-repairs/20260930/pr-197')
REPOSITORY_ROOT = Path('/home/zijiaochen/projects/brain_researcher_benchmark')


def need(ok, code):
    if not ok: raise ValueError(code)


def safe_path(value):
    text = os.fspath(value)
    need(isinstance(text,str) and text.startswith('/') and '\0' not in text, 'absolute_path_required')
    need(not any(v in ('.','..') for v in text.split('/')), 'path_traversal')
    path = Path(text)
    for p in (*reversed(path.parents),path):
        if os.path.lexists(p):
            mode=p.lstat().st_mode
            need(not stat.S_ISLNK(mode), 'symlink_path')
            if p!=path:need(stat.S_ISDIR(mode),'non_directory_ancestor')
    return path


def bytes_file(path, limit):
    path=safe_path(path);before=path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_size<=limit,'regular_file_size_bound')
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as handle:raw=handle.read(limit+1)
    need(len(raw)==before.st_size and len(raw)<=limit,'file_size_changed')
    need(path.stat().st_mtime_ns==before.st_mtime_ns,'file_modified')
    return raw


def strict_json(raw):
    def unique(pairs):
        out={}
        for k,v in pairs:need(k not in out,'duplicate_json_key');out[k]=v
        return out
    def invalid(_):raise ValueError('nonfinite_json')
    value=json.loads(raw,object_pairs_hook=unique,parse_constant=invalid)
    def finite(v):
        if isinstance(v,float):need(math.isfinite(v),'nonfinite_json')
        elif isinstance(v,dict):
            for x in v.values():finite(x)
        elif isinstance(v,list):
            for x in v:finite(x)
    finite(value);return value


def file_hash(path, size):
    path=safe_path(path);before=path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_size==size,'source_regular_size')
    identity=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    h=hashlib.sha256();count=0
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as stream:
        need(identity(os.fstat(stream.fileno()))==identity(before),'source_replaced_before_hash')
        while chunk:=stream.read(1024**2):
            h.update(chunk);count+=len(chunk);need(count<=size,'source_grew')
        need(identity(os.fstat(stream.fileno()))==identity(before),'source_changed_during_hash')
    need(count==size and identity(path.lstat())==identity(before),'source_changed_after_hash')
    return h.hexdigest()


def authenticate(source_dir, manifest_path, manifest_sha256):
    source=safe_path(source_dir);manifest_path=safe_path(manifest_path)
    need(source.is_dir(),'source_directory_required')
    need(re.fullmatch('[0-9a-f]{64}',manifest_sha256) is not None,'explicit_manifest_pin_required')
    raw=bytes_file(manifest_path,262144)
    need(hashlib.sha256(raw).hexdigest()==manifest_sha256,'manifest_sha256')
    doc=strict_json(raw);files=doc.get('files')
    need(isinstance(files,list) and len(files)==SOURCE_FILE_COUNT,'exact_74_file_manifest')
    keys=set();paths=set();dirs=set()
    for row in files:
        need(isinstance(row,dict),'manifest_record')
        subject,role,path=row.get('subject'),row.get('role'),row.get('path')
        need(type(subject) is int and subject in SUBJECTS and role in ('set','fdt'),'subject_role')
        need((subject,role) not in keys,'duplicate_subject_role');keys.add((subject,role))
        need(isinstance(path,str) and path and '\\' not in path and '\0' not in path
             and not path.startswith('/') and all(v not in ('','.','..') for v in path.split('/')),'unsafe_manifest_path')
        need(path not in paths and Path(path).name==f'{subject}_N170_shifted_ds.{role}','source_path_or_role');paths.add(path)
        dirs.update(str(p) for p in Path(path).parents if str(p)!='.')
        size=row.get('size_bytes');sha=row.get('sha256')
        need(type(size) is int and 0<size<=512*1024**2,'source_size_bound')
        need(isinstance(sha,str) and re.fullmatch('[0-9a-f]{64}',sha),'source_hash_format')
        if role=='set':need(size<=MAX_SET_BYTES,'set_metadata_size_bound')
    need(keys=={(s,r) for s in SUBJECTS for r in ('set','fdt')},'closed_cohort')
    need(sum(v['size_bytes'] for v in files)==EXPECTED_SOURCE_BYTES,'exact_total_source_bytes')
    if manifest_path.is_relative_to(source):
        relative=manifest_path.relative_to(source);paths.add(str(relative))
        dirs.update(str(p) for p in relative.parents if str(p)!='.')
    got_files=set();got_dirs=set()
    for parent,subdirs,names in os.walk(source,followlinks=False):
        for name in subdirs+names:
            p=Path(parent)/name;mode=p.lstat().st_mode
            need(stat.S_ISREG(mode) or stat.S_ISDIR(mode),'special_or_link_source')
            (got_dirs if stat.S_ISDIR(mode) else got_files).add(str(p.relative_to(source)))
    need(got_files==paths and got_dirs==dirs,'closed_source_inventory')
    for row in files:need(file_hash(source/row['path'],row['size_bytes'])==row['sha256'],'source_sha256')
    return source,doc


class MatScan:
    """MAT-v5 headers only; numeric payload conversion occurs only in decode()."""
    def __init__(self, raw):
        need(len(raw)>=128 and not raw.startswith(b'MATLAB 7.3'),'unsupported_mat_representation')
        need(raw[126:128] in (b'IM',b'MI'),'unsupported_mat_endian')
        self.endian='<' if raw[126:128]==b'IM' else '>'
        need(struct.unpack(self.endian+'H',raw[124:126])[0]==0x0100,'unsupported_mat_version')
        self.header=raw[:128];self.expanded=0;self.nodes=0;self.metadata_elements=0
        self.top=self.elements(raw,128)

    def tag(self, raw, pos):
        need(0<=pos and pos+8<=len(raw),'truncated_mat_tag')
        packed=struct.unpack_from(self.endian+'I',raw,pos)[0]
        typ,small=packed&65535,packed>>16
        if small:
            need(0<small<=4 and 1<=typ<=18,'invalid_small_mat_tag')
            return typ,raw[pos+4:pos+4+small],pos+8
        typ,size=struct.unpack_from(self.endian+'II',raw,pos)
        need(1<=typ<=18 and pos+8+size<=len(raw),'mat_tag_bounds')
        end=pos+8+size
        nxt=end if typ==15 else end+((-size)%8)
        need(nxt<=len(raw),'truncated_mat_padding')
        return typ,raw[pos+8:end],nxt

    def matrix(self, body):
        self.nodes+=1;need(self.nodes<=50000,'matrix_count_bound')
        typ,flags,p1=self.tag(body,0);need(typ==6 and len(flags)==8,'matrix_flags')
        fl=struct.unpack_from(self.endian+'I',flags)[0]
        typ,dims,p2=self.tag(body,p1);need(typ==5 and len(dims)%4==0 and 0<len(dims)<=32,'matrix_dimensions')
        shape=struct.unpack(self.endian+'i'*(len(dims)//4),dims)
        need(all(v>=0 for v in shape) and math.prod(shape)<=128_000_000,'matrix_shape_bound')
        typ,name,p3=self.tag(body,p2);need(typ in (1,16),'matrix_name_storage')
        name=name.decode('utf-8');need('\0' not in name,'matrix_name')
        return dict(name=name,matlab_class=fl&255,shape=list(shape),is_complex=bool(fl&2048),
                    flags_and_dimensions=body[:p2],payload=body[p3:],body=body)

    def elements(self, raw, pos):
        result=[]
        while pos<len(raw):
            typ,payload,pos=self.tag(raw,pos)
            if typ==15:
                z=zlib.decompressobj();remaining=MAX_EXPANDED_BYTES-self.expanded
                block=z.decompress(payload,remaining+1)
                need(len(block)<=remaining and z.eof and not z.unused_data and not z.unconsumed_tail,'compressed_mat_bound_or_stream')
                self.expanded+=len(block)
                # Only one compression level is supported, never nested streams.
                inner_type,body,end=self.tag(block,0)
                need(inner_type==14 and end==len(block),'compressed_mat_structure')
                result.append(self.matrix(body))
            else:
                need(typ==14,'unsupported_top_mat_element');result.append(self.matrix(payload))
        return result

    def fields(self):
        roots={}
        for node in self.top:need(node['name'] not in roots,'duplicate_mat_variable');roots[node['name']]=node
        if 'EEG' not in roots:return roots,'flat_fields'
        need(len(roots)==1,'ambiguous_eeg_and_flat_fields')
        eeg=roots['EEG'];need(eeg['matlab_class']==2 and math.prod(eeg['shape'])==1,'non_scalar_eeg_struct')
        typ,value,p=self.tag(eeg['payload'],0);need(typ==5 and len(value)==4,'struct_field_name_width')
        width=struct.unpack(self.endian+'i',value)[0];need(0<width<=256,'struct_field_width_bound')
        typ,names,p=self.tag(eeg['payload'],p);need(typ==1 and len(names)%width==0,'struct_field_names')
        keys=[names[i:i+width].split(b'\0',1)[0].decode('utf-8') for i in range(0,len(names),width)]
        need(len(keys)<=512 and all(keys) and len(keys)==len(set(keys)),'struct_field_keys')
        fields={}
        for key in keys:
            typ,body,p=self.tag(eeg['payload'],p);need(typ==14,'struct_field_matrix')
            fields[key]=self.matrix(body)
        need(p==len(eeg['payload']),'unexpected_struct_tail')
        return fields,'scalar_EEG_struct'

    def decode(self, node):
        self.validate_metadata(node)
        # Repackage only this already selected field. Neither a whole EEG struct
        # nor a non-character data field enters scipy's value decoder.
        name=b'value';name_tag=struct.pack(self.endian+'II',1,len(name))+name+b'\0'*((-len(name))%8)
        body=node['flags_and_dimensions']+name_tag+node['payload']
        matrix=struct.pack(self.endian+'II',14,len(body))+body+b'\0'*((-len(body))%8)
        value=loadmat(io.BytesIO(self.header+matrix),variable_names=['value'],simplify_cells=True,verify_compressed_data_integrity=True)['value']
        return value

    def validate_metadata(self, node, depth=0):
        """Bound every nested cell/struct before scipy can allocate values."""
        count=math.prod(node['shape']);self.metadata_elements+=count
        need(depth<=32 and not node['is_complex'] and self.metadata_elements<=MAX_METADATA_ELEMENTS,'metadata_decode_bound')
        cls=node['matlab_class'];raw=node['payload'];pos=0
        if cls==2:
            typ,width,pos=self.tag(raw,pos);need(typ==5 and len(width)==4,'metadata_struct_width')
            width=struct.unpack(self.endian+'i',width)[0];need(0<width<=256,'metadata_struct_width_bound')
            typ,names,pos=self.tag(raw,pos);need(typ==1 and len(names)%width==0,'metadata_struct_names')
            keys=[names[i:i+width].split(b'\0',1)[0] for i in range(0,len(names),width)]
            need(len(keys)<=512 and all(keys) and len(keys)==len(set(keys)),'metadata_struct_keys')
            count*=len(keys)
        if cls in (1,2):
            need(count<=MAX_METADATA_ELEMENTS,'metadata_child_count_bound')
            for _ in range(count):
                typ,body,pos=self.tag(raw,pos);need(typ==14,'metadata_child_matrix')
                # Classic MAT-v5 permits a zero-byte miMATRIX child to denote
                # an empty value. Only selected metadata containers admit it;
                # top-level/data/EEG matrices still require ordinary headers.
                if body:self.validate_metadata(self.matrix(body),depth+1)
        elif cls==4:
            typ,data,pos=self.tag(raw,pos)
            need(typ in (1,2,4,16,17,18) and len(data)<=4*count,'metadata_character_storage')
        elif cls in range(6,16):
            typ,data,pos=self.tag(raw,pos)
            widths={1:1,2:1,3:2,4:2,5:4,6:4,7:4,9:8,12:8,13:8}
            need(typ in widths and len(data)==count*widths[typ],'metadata_numeric_storage')
        else:raise ValueError('unsupported_metadata_matlab_class')
        need(pos==len(raw),'metadata_payload_tail')


def scalar(value, budget=None):
    if budget is None:budget=[MAX_METADATA_ELEMENTS]
    budget[0]-=1;need(budget[0]>=0,'metadata_value_count_bound')
    if isinstance(value,np.generic):return scalar(value.item(),budget)
    if isinstance(value,np.ndarray):
        if value.size==0:return None
        if value.size==1:return scalar(value.reshape(-1)[0],budget)
        return scalar(value.tolist(),budget)
    if isinstance(value,bytes):return value.decode('utf-8')
    if value is None or isinstance(value,(str,bool,int)):return value
    if isinstance(value,float):return value if math.isfinite(value) else {'source_nonfinite':repr(value)}
    if isinstance(value,dict):return {str(k):scalar(v,budget) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [scalar(v,budget) for v in value]
    raise ValueError('unsupported_metadata_value_type')


def records(value):
    if value is None:return []
    if isinstance(value,dict):return [value]
    if isinstance(value,np.ndarray):return list(value.reshape(-1))
    if isinstance(value,(list,tuple)):return list(value)
    raise ValueError('unsupported_metadata_record_layout')


def numeric(value):
    return type(value) in (int,float) and math.isfinite(value)


def type_code(value):
    if numeric(value) and value==int(value):return int(value)
    if isinstance(value,str) and re.fullmatch(r'[+-]?[0-9]+',value.strip()):return int(value)
    return None


def event_ledger(value, total_samples):
    rows=records(value);need(len(rows)<=MAX_EVENTS,'event_count_bound')
    result=[];target_samples={};labels=Counter();boundaries=[]
    for i,original in enumerate(rows):
        need(isinstance(original,dict),'unsupported_event_record')
        fields=scalar(original);typ=fields.get('type');lat=fields.get('latency');code=type_code(typ)
        label=json.dumps(typ,sort_keys=True,ensure_ascii=False,allow_nan=False);labels[label]+=1
        nearest=int(np.rint(lat-1)) if numeric(lat) and abs(lat)<2**52 else None
        target='face' if code in FACE_CODES else 'car' if code in CAR_CODES else None
        boundary=(isinstance(typ,str) and typ.strip().casefold()=='boundary') or code==-99
        row=dict(source_event_index=i,original_fields=fields,
                 original_type=typ,original_latency=lat,original_duration=fields.get('duration'),original_urevent=fields.get('urevent'),
                 candidate_target_field=target,is_boundary_token=boundary,
                 diagnostic_nearest_even_zero_based_sample=nearest,
                 diagnostic_sample_in_data=None if nearest is None else 0<=nearest<total_samples,
                 fractional_source_latency=None if not numeric(lat) else lat!=math.floor(lat))
        result.append(row)
        if target is not None and nearest is not None:target_samples.setdefault(nearest,[]).append(i)
        if boundary:boundaries.append(i)
    return dict(events=result,n_events=len(result),event_type_counts=dict(sorted(labels.items())),boundary_event_indices=boundaries,
                n_boundaries=len(boundaries),candidate_target_counts=dict(Counter(v['candidate_target_field'] for v in result if v['candidate_target_field'])),
                repeated_rounded_target_samples=[dict(sample=k,source_event_indices=v) for k,v in sorted(target_samples.items()) if len(v)>1],
                rounding_note='Diagnostic only: rint(MATLAB one-based latency minus1), ties-to-even; no event, epoch or boundary policy is frozen by this report')


def inspect_set(raw, subject, fdt_basename, fdt_size_bytes):
    scanner=MatScan(raw);nodes,layout=scanner.fields()
    need('data' in nodes and nodes['data']['matlab_class']==4,'external_character_data_required_before_decode')
    pointer=scalar(scanner.decode(nodes['data']))
    need(isinstance(pointer,str) and pointer==fdt_basename,'literal_paired_fdt_pointer_mismatch')
    decoded={name:scanner.decode(node) for name,node in nodes.items() if name in FIELDS}
    values={name:scalar(v) for name,v in decoded.items() if name not in ('event','urevent','chanlocs','chaninfo')}
    for name in ('nbchan','pnts','trials'):
        need(numeric(values.get(name)) and values[name]>0 and values[name]==int(values[name]),'invalid_source_dimension_'+name)
    need(numeric(values.get('srate')) and values['srate']>0,'invalid_source_sample_rate')
    nbchan,pnts,trials=(int(values[k]) for k in ('nbchan','pnts','trials'))
    channels=records(decoded.get('chanlocs'));need(len(channels)==nbchan and all(isinstance(v,dict) for v in channels),'channel_metadata_count')
    channel_rows=[dict(source_channel_index=i,original_fields=scalar(c)) for i,c in enumerate(channels)]
    channel_matches={label:[r['source_channel_index'] for r in channel_rows
                            if r['original_fields'].get('labels')==label] for label in SCALP_CHANNELS}
    shapes={k:dict(matlab_class=v['matlab_class'],shape=v['shape'],is_complex=v['is_complex']) for k,v in nodes.items()}
    urevents=records(decoded.get('urevent'));need(len(urevents)<=MAX_EVENTS,'urevent_count_bound')
    result=dict(subject=subject,mat_layout=layout,literal_data_pointer=pointer,header_fields=values,
                original_field_storage=shapes,channels=channel_rows,chaninfo=scalar(decoded.get('chaninfo')),
                requested_channel_matches=channel_matches,expected_scalp_channel_order=list(SCALP_CHANNELS),
                observed_channel_count=nbchan,expected_original_channel_count=EXPECTED_ORIGINAL_CHANNEL_COUNT,
                original_channel_count_matches_expected=nbchan==EXPECTED_ORIGINAL_CHANNEL_COUNT,
                observed_channel_labels=[r['original_fields'].get('labels') for r in channel_rows],
                missing_scalp_labels=[label for label,indices in channel_matches.items() if not indices],
                duplicate_scalp_labels=[label for label,indices in channel_matches.items() if len(indices)>1],
                channel_support_note='Literal labels and all original channel fields retained; expected30/33 counts are diagnostics, not imputed source facts or a channel-selection operation.',
                urevents=[dict(source_urevent_index=i,original_fields=scalar(v)) for i,v in enumerate(urevents)],
                ica_fields_shapes_only={k:v for k,v in shapes.items() if k in ICA_FIELDS},
                other_fields_not_decoded=[k for k in nodes if k not in FIELDS and k!='data'],
                fdt_size_bytes=fdt_size_bytes,float32_storage_size_candidate=4*nbchan*pnts*trials,
                float32_byte_equation_matches=fdt_size_bytes==4*nbchan*pnts*trials,
                storage_note='Byte equation is a structural consistency check, not alone proof of endian, units, calibration or signal values.',
                fdt_decoded=False,filtering_epoching_or_measurement_performed=False)
    result.update(event_ledger(decoded.get('event'),pnts*trials))
    return result


def write_json(path,value):
    raw=(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()
    need(len(raw)<=MAX_JSON_BYTES,'report_byte_bound')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(raw)


def destination(value, source, manifest):
    path=safe_path(value);need(not os.path.lexists(path) and path.parent.is_dir(),'fresh_destination_parent_required')
    for protected in (safe_path(source),safe_path(manifest),Path(__file__).resolve().parent,TASK_ROOT,REPOSITORY_ROOT):
        need(path!=protected and protected not in path.parents and path not in protected.parents,'source_or_code_output_overlap')
    return path


def run(source_dir,manifest_path,manifest_sha256,output_dir):
    out=destination(output_dir,source_dir,manifest_path);out.mkdir(mode=0o700)
    completed=[];phase='authenticate_all_74_originals'
    try:
        source,manifest=authenticate(source_dir,manifest_path,manifest_sha256)
        by_key={(r['subject'],r['role']):r for r in manifest['files']}
        summaries=[]
        for subject in SUBJECTS:
            phase='set_metadata_'+str(subject);s,f=by_key[subject,'set'],by_key[subject,'fdt']
            raw=bytes_file(source/s['path'],MAX_SET_BYTES)
            need(hashlib.sha256(raw).hexdigest()==s['sha256'],'set_changed_after_authentication')
            report=inspect_set(raw,subject,Path(f['path']).name,f['size_bytes'])
            report.update(set_path=s['path'],set_sha256=s['sha256'],fdt_path=f['path'],fdt_sha256=f['sha256'])
            write_json(out/f'subject_{subject:03d}.json',report);completed.append(subject)
            summaries.append({k:report[k] for k in ('subject','mat_layout','n_events','n_boundaries','candidate_target_counts','float32_byte_equation_matches','fdt_size_bytes')})
        result=dict(status='structure_only',manifest_sha256=manifest_sha256,subjects=list(SUBJECTS),n_authenticated_originals=SOURCE_FILE_COUNT,
                    source_bytes_authenticated=sum(r['size_bytes'] for r in manifest['files']),
                    subject_summaries=summaries,original_FDT_bytes_read_for_sha_only=True,fdt_signal_decoded=False,
                    original_inline_EEG_signal_decoded=False,filtering_epoching_or_measurement_performed=False)
        write_json(out/'report.json',result);return result
    except BaseException as error:
        write_json(out/'failure_report.json',dict(status='failed_structural_inspection',phase=phase,completed_subjects=completed,error_type=type(error).__name__,
                                                reason=str(error)[:1000],fdt_signal_decoded=False))
        raise


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('source-dir','manifest','manifest-sha256','output-dir'):p.add_argument('--'+key)
    p.add_argument('--inspect-headers',action='store_true');a=p.parse_args(argv)
    if not a.inspect_headers:
        print(json.dumps(dict(status='plan_only',subjects=SUBJECTS,files=SOURCE_FILE_COUNT,expected_source_bytes=EXPECTED_SOURCE_BYTES,
                              expected_scalp_channel_order=SCALP_CHANNELS,expected_original_channels=EXPECTED_ORIGINAL_CHANNEL_COUNT,
                              candidate_face_codes=sorted(FACE_CODES),candidate_car_codes=sorted(CAR_CODES),
                              serial=True,wall_seconds=300,requires_frozen_manifest_and_parent_gate=True,
                              mat_support='classic-v5 flat fields or scalar EEG struct; no alternate-reader fallback',fdt_signal_decoded=False)))
        return 0
    need(all((a.source_dir,a.manifest,a.manifest_sha256,a.output_dir)),'explicit_paths_and_manifest_pin_required')
    def deadline(*_):raise TimeoutError('structural_wall_time_limit')
    old=signal.signal(signal.SIGALRM,deadline);signal.alarm(300)
    try:
        report=run(a.source_dir,a.manifest,a.manifest_sha256,a.output_dir)
        print(json.dumps({k:report[k] for k in ('status','n_authenticated_originals','fdt_signal_decoded')}));return 0
    except Exception as error:
        print(json.dumps(dict(status='failed',error_type=type(error).__name__)));return 1
    finally:signal.alarm(0);signal.signal(signal.SIGALRM,old)


if __name__=='__main__':raise SystemExit(main())
