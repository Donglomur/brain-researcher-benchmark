"""Plan-only by default; gated DEVCONN source structural inspection.

Two complete opaque authentication passes precede/cover immutable-buffer parsing.
Only BOLD header/extension bytes and selected table tokens are decoded. No BOLD
voxel, Power coordinate, ROI/global signal, cleaning, rank, or FC calculation exists.
Adapted from reviewed PR198 inspector SHA256
85091795d59ad3983782686ff60f2bde94a1d517eee62b2d6fd7720167845587.
No older estimator, stager or scientific kernel is imported. Nibabel is imported lazily only by the header decoder.
"""
from __future__ import annotations
import argparse
from collections import Counter
from contextlib import contextmanager
import csv
from dataclasses import dataclass
import hashlib
import importlib.metadata
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import signal
import stat
import struct
import time
import zlib

MANIFEST_SHA = '0fb419ee0dbea59376f5b0dc1e91d26502e8203d6e7b02334b979e6a1d9f66e3'
VERSIONS = {'numpy': '2.1.3', 'scipy': '1.14.1', 'nibabel': '5.3.2',
            'nilearn': '0.12.1', 'scikit-learn': '1.5.2', 'pandas': '2.2.3'}
IDS = tuple(f'sub-pixar{i:03d}' for i in range(1,156))
NUISANCE = ('trans_x','trans_y','trans_z','rot_x','rot_y','rot_z',
    *(f'a_comp_cor_{i:02d}' for i in range(6)), 'csf','white_matter')
FD_COLUMN = 'framewise_displacement'
MISSING_TOKENS = ('', 'n/a')  # Exact lexical amendment, not pandas' broad NA vocabulary.
DOCUMENTARY_TR_SECONDS = 2.0  # Release convention, never substituted into raw headers.
OPAQUE_MEMBERS = (
    ('atlas/power_2011.csv','coordinates'),
    ('provenance/nilearn_0_12_1/nilearn/datasets/description/power_2011.rst','provenance'),
    ('provenance/nilearn_0_12_1/nilearn/datasets/description/development_fmri.rst','provenance'),
    ('provenance/nilearn_0_12_1/LICENSE','provenance'),
    ('provenance/processing_README_version2.md','provenance'))
MIB = 1024**2


class Refusal(ValueError): pass


def need(condition,reason):
    if not condition: raise Refusal(reason)


@dataclass(frozen=True)
class Policy:
    manifest_sha: str | None
    versions: dict | None
    participant_ids: tuple = IDS
    task_id: str = 'DEVCONN-001'
    opaque_members: tuple = OPAQUE_MEMBERS
    manifest_schema: str = 'devconn-source-v2'
    max_member_bytes: int = 16*MIB
    max_manifest_bytes: int = 4*MIB
    max_source_bytes: int = 1_100_000_000
    max_header_bytes: int = MIB
    max_table_rows: int = 10000
    max_table_columns: int = 2048
    max_table_field_bytes: int = 4096
    wall_seconds: int = 300


def production_policy():
    return Policy(MANIFEST_SHA,VERSIONS)


def safe_path(value):
    raw=os.fspath(value)
    need(type(raw) is str and raw.startswith('/') and '\0' not in raw, 'absolute_path')
    need(not any(p in ('.','..') for p in raw.split('/')), 'lexical_traversal')
    path=Path(raw)
    for node in (*reversed(path.parents),path):
        if os.path.lexists(node):
            mode=node.lstat().st_mode
            need(not stat.S_ISLNK(mode), 'symlink_path')
            if node!=path: need(stat.S_ISDIR(mode), 'non_directory_ancestor')
    return path


def signature(info):
    return info.st_dev,info.st_ino,info.st_mode,info.st_size,info.st_mtime_ns,info.st_ctime_ns


@contextmanager
def reader(path):
    path=safe_path(path); before=path.lstat()
    need(stat.S_ISREG(before.st_mode), 'regular_file_required')
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as stream:
        need(signature(os.fstat(stream.fileno()))==signature(before), 'changed_before_read')
        yield stream,before
        need(signature(os.fstat(stream.fileno()))==signature(before), 'changed_during_read')
    need(signature(path.lstat())==signature(before), 'changed_after_read')


def strict_json(raw):
    def pairs(items):
        out={}
        for key,value in items:
            need(key not in out, 'duplicate_json_key'); out[key]=value
        return out
    def bad(*unused): raise Refusal('nonfinite_json')
    value=json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)
    def check(obj,depth=0):
        need(depth<=64, 'json_depth')
        if isinstance(obj,float): need(math.isfinite(obj), 'nonfinite_json')
        elif isinstance(obj,(list,dict)):
            for item in obj.values() if isinstance(obj,dict) else obj: check(item,depth+1)
    check(value); return value


def frozen_manifest(source,manifest_path,policy):
    need(type(policy.manifest_sha) is str and re.fullmatch('[0-9a-f]{64}',policy.manifest_sha), 'manifest_unfrozen')
    need(type(policy.versions) is dict and policy.versions and
        all(type(k) is str and type(v) is str and v for k,v in policy.versions.items()), 'software_unfrozen')
    observed_versions={name:importlib.metadata.version(name) for name in policy.versions}
    need(observed_versions==policy.versions, 'software_identity')
    buffers=[]
    for path in (manifest_path,source/'source_manifest.json'):
        with reader(path) as (stream,info):
            need(0<info.st_size<=policy.max_manifest_bytes, 'manifest_cap')
            raw=stream.read(policy.max_manifest_bytes+1)
        need(len(raw)==info.st_size and hashlib.sha256(raw).hexdigest()==policy.manifest_sha, 'manifest_sha256')
        buffers.append(raw)
    need(buffers[0]==buffers[1], 'internal_manifest_identity')
    manifest=strict_json(buffers[0])
    need(manifest.get('task_id')==policy.task_id and manifest.get('schema_version')==policy.manifest_schema,
        'manifest_task_schema')
    rows=manifest.get('files')
    count=2*len(policy.participant_ids)+1
    need(type(rows) is list and len(rows)==count+len(policy.opaque_members), 'manifest_count')
    expected={f'{sid}_task-pixar_space-MNI152NLin2009cAsym_desc-preproc_bold.nii.gz':('bold',sid)
              for sid in policy.participant_ids}
    expected.update({f'{sid}_task-pixar_desc-confounds_regressors.tsv':('confounds',sid)
                     for sid in policy.participant_ids})
    expected['participants.tsv']=('participants',None)
    by_path={}; original=[]; opaque=[]
    for row in rows:
        need(type(row) is dict and type(row.get('path')) is str, 'manifest_row')
        name=row['path']; parts=name.split('/')
        need(name and not name.startswith('/') and '\\' not in name and '\0' not in name
            and all(p not in ('','.','..') for p in parts) and name!='source_manifest.json'
            and name not in by_path, 'manifest_path')
        need(type(row.get('role')) is str and row['role'] and
            type(row.get('size_bytes')) is int and 0<row['size_bytes']<=policy.max_member_bytes, 'manifest_member_size_role')
        for key,length in (('sha256',64),('md5',32),('git_blob_sha1',40)):
            if key=='sha256' or row.get(key) is not None:
                need(type(row.get(key)) is str and re.fullmatch('[0-9a-f]{'+str(length)+'}',row[key]), 'manifest_digest')
        if name in expected:
            need((row['role'],row.get('participant_id'))==expected[name], 'original_role_identity')
            original.append(name)
        else:
            need(name in dict(policy.opaque_members) and row['role']==dict(policy.opaque_members)[name]
                and row.get('participant_id') is None, 'opaque_role_identity')
            opaque.append(name)
        by_path[name]=row
    need(set(original)==set(expected), 'original_membership')
    total=sum(row['size_bytes'] for row in rows)
    need(total<=policy.max_source_bytes and type(manifest.get('n_files')) is int and
        manifest['n_files']==len(rows) and type(manifest.get('total_bytes')) is int and manifest['total_bytes']==total,
        'manifest_totals')
    need(manifest.get('participant_ids')==list(policy.participant_ids), 'manifest_cohort')
    need(set(opaque)==set(dict(policy.opaque_members)), 'opaque_membership')
    return manifest,by_path,original,opaque,observed_versions


def closed_inventory(source,rows,check):
    wanted=set(rows)|{'source_manifest.json'}
    dirs={p.as_posix() for name in wanted for p in PurePosixPath(name).parents if p.as_posix()!='.'}
    seen_files=set(); seen_dirs=set()
    for node in source.rglob('*'):
        check(); mode=node.lstat().st_mode; relative=node.relative_to(source).as_posix()
        need(stat.S_ISREG(mode) or stat.S_ISDIR(mode), 'source_link_or_special')
        (seen_dirs if stat.S_ISDIR(mode) else seen_files).add(relative)
    need(seen_files==wanted and seen_dirs==dirs, 'closed_inventory')


def authenticated_bytes(path,row,check,*,retain=False):
    """Hashes the same immutable buffer consumed by parsing in the second pass."""
    digests={'sha256':hashlib.sha256()}
    if row.get('md5') is not None: digests['md5']=hashlib.md5()
    if row.get('git_blob_sha1') is not None:
        digests['git_blob_sha1']=hashlib.sha1(f"blob {row['size_bytes']}\0".encode())
    chunks=[]; total=0
    with reader(path) as (stream,info):
        need(info.st_size==row['size_bytes'], 'source_size')
        while True:
            check(); chunk=stream.read(min(65536,row['size_bytes']-total+1))
            if not chunk: break
            total+=len(chunk); need(total<=row['size_bytes'], 'source_overrun')
            for digest in digests.values(): digest.update(chunk)
            if retain: chunks.append(chunk)
        need(total==row['size_bytes'], 'source_size')
    for key,digest in digests.items(): need(digest.hexdigest()==row[key], 'source_'+key)
    return (b''.join(chunks) if retain else None),signature(info)


def literal(value):
    value=float(value)
    return value if math.isfinite(value) else 'NaN' if math.isnan(value) else '+Inf' if value>0 else '-Inf'


def decode_header(raw,policy):
    from nibabel import Nifti1Header
    need(len(raw)>=352, 'header_truncated')
    header=Nifti1Header(binaryblock=raw[:348],check=False)
    need(int(header['sizeof_hdr'])==348 and header['magic'].tobytes()==b'n+1\0', 'single_file_nifti1')
    shape=list(map(int,header.get_data_shape()))
    need(len(shape)==4 and all(n>0 for n in shape) and shape[3]<=policy.max_table_rows, 'bold_4d_shape')
    dtype=header.get_data_dtype(); need(dtype.kind in 'iuf', 'real_storage_dtype')
    affine=header.get_best_affine().tolist()
    need(all(math.isfinite(float(x)) for row in affine for x in row), 'affine_finite')
    a=affine
    determinant=(a[0][0]*(a[1][1]*a[2][2]-a[1][2]*a[2][1])-
        a[0][1]*(a[1][0]*a[2][2]-a[1][2]*a[2][0])+a[0][2]*(a[1][0]*a[2][1]-a[1][1]*a[2][0]))
    need(math.isfinite(determinant) and determinant!=0, 'affine_invertible')
    offset=float(header['vox_offset'])
    need(math.isfinite(offset) and offset.is_integer() and 352<=offset<=policy.max_header_bytes, 'header_offset')
    slope,inter=header.get_slope_inter(); units=header.get_xyzt_units()
    zooms=[literal(x) for x in header.get_zooms()]
    factor={'sec':1.,'msec':.001,'usec':.000001}.get(units[1])
    tr=zooms[3]*factor if type(zooms[3]) is float and factor is not None else None
    return dict(shape=shape,storage_dtype=dtype.str,endianness=header.endianness,
        spatial_units=units[0],temporal_units=units[1],zooms=zooms,pixdim=[literal(x) for x in header['pixdim']],
        header_tr_seconds=tr,raw_toffset=literal(header['toffset']),selected_affine=affine,
        qform_code=int(header['qform_code']),sform_code=int(header['sform_code']),
        qform=[[literal(x) for x in row] for row in header.get_qform()],
        sform=[[literal(x) for x in row] for row in header.get_sform()],
        raw_scl_slope=literal(header['scl_slope']),raw_scl_inter=literal(header['scl_inter']),
        effective_slope=1. if slope is None else float(slope),effective_intercept=0. if inter is None else float(inter),
        vox_offset=int(offset),extension_flag_hex=raw[348:352].hex(),header_sha256=hashlib.sha256(raw[:352]).hexdigest(),
        expected_decoded_file_bytes=int(offset)+math.prod(shape)*dtype.itemsize,
        decoded_file_length_verified=False)


def header_from_bytes(raw,policy,check):
    """zlib max_length stops output EXACTLY before any BOLD voxel payload."""
    decoder=zlib.decompressobj(16+zlib.MAX_WBITS); prefix=bytearray(); cursor=0
    def fill(target):
        nonlocal cursor
        while len(prefix)<target:
            check()
            if decoder.unconsumed_tail: chunk=decoder.unconsumed_tail
            else:
                need(cursor<min(len(raw),policy.max_header_bytes), 'compressed_header_cap_or_truncated')
                chunk=raw[cursor:min(cursor+1024,len(raw),policy.max_header_bytes)]; cursor+=len(chunk)
            data=decoder.decompress(chunk,target-len(prefix)); prefix.extend(data)
            need(data or not decoder.eof, 'logical_header_truncated')
    fill(352); result=decode_header(bytes(prefix),policy); fill(result['vox_offset'])
    extensions=[]; offset=352
    if prefix[348]:
        while offset<len(prefix):
            need(offset+8<=len(prefix), 'extension_header')
            size,code=struct.unpack(result['endianness']+'ii',prefix[offset:offset+8])
            need(size>=16 and size%16==0 and offset+size<=len(prefix), 'extension_size')
            extensions.append(dict(ecode=code,esize=size,sha256=hashlib.sha256(prefix[offset:offset+size]).hexdigest()))
            offset+=size
    else: need(not any(prefix[352:]), 'unflagged_nonzero_extension')
    result.update(extensions=extensions,logical_header_bytes_decoded=len(prefix),compressed_prefix_bytes_consumed=cursor,
        extension_region_sha256=hashlib.sha256(prefix[352:]).hexdigest(),bold_voxel_bytes_decoded=0)
    return result


def table(raw,policy):
    text=raw.decode('utf-8-sig'); need('\0' not in text, 'table_nul')
    # Exact TSV, never sniff commas or guess a reduced-cache schema.
    parsed=csv.reader(io.StringIO(text,newline=''),delimiter='\t',strict=True)
    columns=next(parsed,None)
    need(columns is not None and 1<=len(columns)<=policy.max_table_columns, 'table_shape')
    need(all(columns) and len(columns)==len(set(columns)), 'table_columns')
    need(all(len(token.encode())<=policy.max_table_field_bytes for token in columns), 'table_field_cap')
    rows=[]
    for row in parsed:
        need(len(rows)<policy.max_table_rows, 'table_shape')
        need(len(row)==len(columns), 'table_width')
        need(all(len(token.encode())<=policy.max_table_field_bytes for token in row), 'table_field_cap')
        rows.append(row)
    return columns,rows


def token_kind(token):
    if token=='': return 'empty',None
    try: value=float(token)
    except ValueError: return 'nonnumeric',None
    return ('finite',value) if math.isfinite(value) else ('nonfinite',None)


def confounds(raw,policy):
    """Describe fourteen nuisance columns and FD separately, never fit signals.

    Exact empty/n/a tokens at any row are declared zero-fill locations. Every
    other nonnumeric/nonfinite token is invalid; retain it in the report and
    return structural_issues/nonzero through inspect/execute. No input is edited.
    """
    columns,rows=table(raw,policy); diagnostics={}
    required=(*NUISANCE,FD_COLUMN)
    for column in required:
        if column not in columns: continue
        index=columns.index(column); counts=Counter(); exceptions=[]; finite=[]
        for row_index,row in enumerate(rows):
            token=row[index]
            if token in MISSING_TOKENS: kind,value='declared_missing',None
            else: kind,value=token_kind(token)
            counts[kind]+=1
            if kind!='finite':
                exceptions.append(dict(row_index=row_index,token=token,kind=kind,
                    applied_value=0.0 if kind=='declared_missing' else None))
            elif column==FD_COLUMN: finite.append(value)
        invalid=counts['empty']+counts['nonnumeric']+counts['nonfinite']
        item=dict(counts={key:counts[key] for key in
            ('finite','declared_missing','empty','nonnumeric','nonfinite')},
            exceptions=exceptions,n_invalid=invalid)
        if column==FD_COLUMN:
            summed=math.fsum(finite) if finite else 0.0
            need(math.isfinite(summed), 'FD_sum_overflow')
            item.update(observed_finite_count=len(finite),observed_finite_sum=summed,
                observed_finite_mean=summed/len(finite) if finite else None,
                finite_min=min(finite) if finite else None,finite_max=max(finite) if finite else None,
                n_negative=sum(value<0 for value in finite),
                missing_frame_indices=[e['row_index'] for e in exceptions if e['kind']=='declared_missing'],
                zero_filled_sum=summed if not invalid else None,
                zero_filled_mean=summed/len(rows) if rows and not invalid else None,
                denominator_original_rows=len(rows),finite_initial_zero_is_observed=True)
        diagnostics[column]=item
    return dict(columns=columns,n_rows=len(rows),selected_columns=list(NUISANCE),
        selected_source_order=[name for name in columns if name in NUISANCE],
        excluded_columns=[name for name in columns if name not in NUISANCE],
        separately_consumed_columns=[FD_COLUMN],
        unused_columns=[name for name in columns if name not in required],
        missing_required=[name for name in required if name not in columns],
        columns_diagnostics=diagnostics,delimiter='\\t',
        missing_policy=dict(exact_tokens=list(MISSING_TOKENS),permitted_rows='all_original_rows',
            replacement=0.0,scope='FD descriptive zero-filled sum/T only; no nuisance matrix constructed',
            amendment='Explicit lexical policy, not unconditional pandas NA equivalence'),
        source_values_changed=False,nuisance_matrix_materialized=False,rank_computed=False)

def phenotype(raw,policy):
    columns,rows=table(raw,policy)
    required=('participant_id','Age','Child_Adult')
    need(set(required)<=set(columns), 'phenotype_required_columns')
    positions=[columns.index(name) for name in required]; selected=[]; seen=set(); counts=Counter()
    for row_index,row in enumerate(rows):
        sid,age,group=(row[index] for index in positions)
        need(sid in policy.participant_ids and sid not in seen, 'phenotype_literal_membership')
        seen.add(sid); kind,value=token_kind(age); counts[group]+=1
        selected.append(dict(phenotype_row_index=row_index,participant_id=sid,age_token=age,
            age_kind=kind,age=value,group_token=group,group_known=group in ('child','adult')))
    need(seen==set(policy.participant_ids) and len(rows)==len(policy.participant_ids), 'phenotype_complete_cohort')
    return dict(columns=columns,n_rows=len(rows),selected=selected,group_token_counts=dict(sorted(counts.items())),
        age_kind_counts=dict(sorted(Counter(row['age_kind'] for row in selected).items())),
        age_min=min((row['age'] for row in selected if row['age'] is not None),default=None),
        age_max=max((row['age'] for row in selected if row['age'] is not None),default=None),
        unselected_phenotype_fields_not_reported=True)


def inspect(source,manifest_path,policy,check):
    manifest,rows,original,opaque,versions=frozen_manifest(source,manifest_path,policy)
    closed_inventory(source,rows,check); signatures={}
    for name,row in rows.items():
        _,signatures[name]=authenticated_bytes(source/name,row,check)
    # No header or table has been decoded before this COMPLETE pass.
    persons={sid:{} for sid in policy.participant_ids}; demographics=None
    for name,row in rows.items():
        raw,observed=authenticated_bytes(source/name,row,check,retain=name in original)
        need(observed==signatures[name], 'source_changed_between_passes')
        if row['role']=='bold': persons[row['participant_id']]['bold_header']=header_from_bytes(raw,policy,check)
        elif row['role']=='confounds': persons[row['participant_id']]['confounds']=confounds(raw,policy)
        elif row['role']=='participants': demographics=phenotype(raw,policy)
    issues=[]; grids={}
    for sid,person in persons.items():
        header,conf=person['bold_header'],person['confounds']
        if header['shape'][3]!=conf['n_rows']: issues.append(dict(participant_id=sid,issue='confound_frame_mismatch'))
        if conf['missing_required']: issues.append(dict(participant_id=sid,issue='missing_required_confound_columns'))
        for column,item in conf['columns_diagnostics'].items():
            if item['n_invalid']: issues.append(dict(participant_id=sid,issue='invalid_selected_or_fd_token',column=column))
        if header['spatial_units']!='mm': issues.append(dict(participant_id=sid,issue='spatial_units_not_mm'))
        person['documentary_clock']=dict(documented_TR_s=DOCUMENTARY_TR_SECONDS,
            authority='Pinned development-release documentation; not recovered from the raw header',
            raw_header_unchanged=True,frame_origin_s=0.0,
            alignment='original released frame index; no measured movie onset or slice reference')
        tr=header['header_tr_seconds']
        if tr is None or not math.isfinite(tr) or tr<=0: issues.append(dict(participant_id=sid,issue='unresolved_header_clock'))
        geometry=json.dumps([header['shape'][:3],header['selected_affine']],separators=(',',':')).encode()
        grid_id=hashlib.sha256(geometry).hexdigest(); person['grid_id']=grid_id
        grids.setdefault(grid_id,dict(shape=header['shape'][:3],selected_affine=header['selected_affine'],participant_ids=[]))['participant_ids'].append(sid)
    for row in demographics['selected']:
        if row['age_kind']!='finite' or not row['group_known']:
            issues.append(dict(participant_id=row['participant_id'],issue='phenotype_token_requires_policy'))
    closed_inventory(source,rows,check)
    for name,wanted in signatures.items(): need(signature((source/name).lstat())==wanted, 'postconsumption_source_stat_changed')
    # Internal/external identity rechecked after parsing; not counted as source payload passes.
    frozen_manifest(source,manifest_path,policy)
    total=sum(row['size_bytes'] for row in rows.values())
    return dict(status='structural_issues' if issues else 'ok',task_id=policy.task_id,
        source_manifest_sha256=policy.manifest_sha,participant_ids=list(policy.participant_ids),
        authentication=dict(all_members_verified_before_parse=True,n_files=len(rows),source_bytes=total,
            complete_opaque_hash_passes=2,total_source_bytes_hashed=2*total,
            consumption='second-pass authenticated immutable per-file bytes; final descriptor/stat inventory checks',
            original_members=len(original),opaque_only_members=opaque),versions=versions,
        source_files=[{key:row.get(key) for key in ('path','role','participant_id','size_bytes','sha256')} for row in rows.values()],
        persons=persons,phenotype=demographics,grids=grids,n_distinct_grids=len(grids),issues=issues,
        total_frames=sum(p['bold_header']['shape'][3] for p in persons.values()),
        source_writes=False,network_requests=0,bold_values_decoded=False,power_coordinates_decoded=False,
        power_or_ROI_support_computed=False,cleaning_rank_computed=False,connectivity_computed=False,
        interpretation='Structural tokens, clocks and declared zero-filled FD sum/T only. No source writes, nuisance matrix, eligibility, coordinate decoding, anatomical support, signal validity or scientific outcome admission.')


def execute(source,manifest_path,output,*,policy=None):
    policy=production_policy() if policy is None else policy
    source,manifest_path,output=map(safe_path,(source,manifest_path,output))
    need(source.is_dir() and output.parent.is_dir(), 'existing_parents')
    for protected in (source,Path(__file__).absolute().parent):
        need(output!=protected and output not in protected.parents and protected not in output.parents, 'protected_overlap')
    need(output!=manifest_path and output not in manifest_path.parents, 'protected_manifest')
    need(not os.path.lexists(output), 'fresh_output_required')
    need(signal.getitimer(signal.ITIMER_REAL)==(0.,0.), 'existing_alarm')
    output.mkdir(); start=time.monotonic()
    def check(): need(time.monotonic()-start<policy.wall_seconds, 'wall_deadline')
    def expired(*unused): raise Refusal('wall_deadline')
    old=signal.getsignal(signal.SIGALRM); signal.signal(signal.SIGALRM,expired)
    signal.setitimer(signal.ITIMER_REAL,policy.wall_seconds)
    def publish(name,obj):
        with (output/name).open('x',encoding='utf-8') as stream:
            json.dump(obj,stream,indent=2,sort_keys=True,allow_nan=False); stream.write('\n')
    try:
        publish('attempt.json',dict(status='running',manifest_sha256=policy.manifest_sha,source_writes=False,
            network_requests=0,max_source_bytes_per_pass=policy.max_source_bytes,complete_hash_passes=2,
            max_total_source_bytes_hashed=2*policy.max_source_bytes,wall_seconds=policy.wall_seconds))
        result=inspect(source,manifest_path,policy,check)
    except BaseException as exc:
        result=dict(status='failed',reason=str(exc) if isinstance(exc,Refusal) else 'io_or_structure_error',
            error_type=type(exc).__name__,source_writes=False,network_requests=0,bold_values_decoded=False,
            power_coordinates_decoded=False,connectivity_computed=False)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0); signal.signal(signal.SIGALRM,old)
    result['elapsed_seconds']=time.monotonic()-start
    if result['status']!='ok': publish('failure_report.json',dict(status=result['status'],reason=result.get('reason','structural_policy_review_required')))
    publish('report.json',result); return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-structure-approved',action='store_true')
    parser.add_argument('--source-dir'); parser.add_argument('--manifest'); parser.add_argument('--output-dir')
    args=parser.parse_args(argv)
    if not args.execute_structure_approved:
        print(json.dumps(dict(status='plan_only',source_reads=0,network_requests=0,
            scope='316 members:311 originals +5 opaque Power/provenance; two complete auth passes, BOLD headers,14 nuisance columns and separate FD/phenotype tokens only',
            manifest_frozen=MANIFEST_SHA is not None,software_frozen=VERSIONS is not None,
            proposed_resources='1 CPU / 2 GiB / 300s inner + 330s recorder; 2.2GB maximum source hashes')))
        return 0
    try:
        result=execute(args.source_dir,args.manifest,args.output_dir)
        print(json.dumps(dict(status=result['status'],report=str(Path(args.output_dir)/'report.json'))))
        return 0 if result['status']=='ok' else 1
    except Exception as exc:
        print(json.dumps(dict(status='refused',error_type=type(exc).__name__,
            reason=str(exc) if isinstance(exc,Refusal) else 'io_error'))); return 1


if __name__=='__main__': raise SystemExit(main())
