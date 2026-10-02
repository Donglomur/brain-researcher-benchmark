"""MAPREL oracle source route; no import-time IO, grader or stager imports.

Generic lexical/authentication guards follow the reviewed PR192 oracle pattern.
The CIFTI-to-full-GIFTI join and reductions are separately implemented here.
NiBabel decoding and NumPy float64 means are disclosed shared dependencies.
Private pins and literal structural facts stay fail-closed until parent freeze.
"""
import base64
import hashlib
import json
import math
import numbers
import os
from pathlib import Path, PurePosixPath
import re
import stat
import xml.etree.ElementTree as ET
import zlib

import nibabel as nib
import numpy as np

import oracle_core as core

SOURCE_SHA = '279658ffc93a8957287298471b539fc034fb7e11f0836325de322acc4b232f7f'
METHOD_SHA = '54c6f851a5027b3e6b7cfe8e97e7b5af620d6f69b7235a681915affdcd23121e'
SCHEMA_SHA = 'bfbd7239bff8015340bc562db4c95c51c6a3a2f529164ec4a97f2d8f45ac550e'
SCIENCE = ('gradient_l','gradient_r','thickness_l','thickness_r','sphere_l','sphere_r','atlas')
STRUCTURES = {'CIFTI_STRUCTURE_CORTEX_LEFT':'L','CIFTI_STRUCTURE_CORTEX_RIGHT':'R'}
NETWORKS = ('Vis','SomMot','DorsAttn','SalVentAttn','Limbic','Cont','Default')
MAX_FILE, MAX_TOTAL = 16*1024**2, 32*1024**2
need = core.need


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_path(value):
    raw = os.fspath(value)
    need(type(raw) is str and raw.startswith('/') and '\0' not in raw
         and all(x not in ('.','..') for x in raw.split('/')), 'absolute lexical path')
    path = Path(raw)
    for item in (*reversed(path.parents), path):
        if os.path.lexists(item):
            mode = item.lstat().st_mode
            need(not stat.S_ISLNK(mode), 'source symlink')
            need(item == path or stat.S_ISDIR(mode), 'source directory ancestor')
    return path


def signature(s):
    return s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns


def read_bytes(path, pin, size=None, cap=MAX_FILE):
    path = safe_path(path); before = path.lstat()
    need(type(pin) is str and re.fullmatch('[0-9a-f]{64}',pin), 'frozen SHA required')
    need(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= cap, 'bounded regular file')
    need(size is None or type(size) is int and size == before.st_size, 'exact source size')
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as handle:
        need(signature(os.fstat(handle.fileno())) == signature(before), 'source replaced before read')
        raw = handle.read(before.st_size+1)
        need(len(raw) == before.st_size and signature(os.fstat(handle.fileno())) == signature(before),
             'source changed during read')
    need(signature(path.lstat()) == signature(before) and sha(raw) == pin, 'source identity')
    return raw


def strict_json(raw):
    def pairs(items):
        result = {}
        for key,value in items:
            need(key not in result,'duplicate JSON key'); result[key] = value
        return result
    def invalid(_):
        raise ValueError('nonfinite JSON')
    value = json.loads(raw.decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=invalid)
    def check(item,depth=0):
        need(depth <= 64,'JSON depth')
        if isinstance(item,float): need(math.isfinite(item),'nonfinite JSON')
        elif isinstance(item,dict):
            for v in item.values(): check(v,depth+1)
        elif isinstance(item,list):
            for v in item: check(v,depth+1)
    check(value)
    return value


def authenticate(data_dir,manifest_path,method_path,schema_path):
    root = safe_path(data_dir); need(root.is_dir(),'source directory')
    pins = dict(source_manifest_sha256=SOURCE_SHA,method_contract_sha256=METHOD_SHA,output_schema_sha256=SCHEMA_SHA)
    raw = read_bytes(manifest_path,SOURCE_SHA,cap=1024**2)
    need(read_bytes(root/'source_manifest.json',SOURCE_SHA,cap=1024**2) == raw,'internal/external manifest equality')
    manifest = strict_json(raw)
    method = strict_json(read_bytes(method_path,METHOD_SHA,cap=1024**2))
    schema = strict_json(read_bytes(schema_path,SCHEMA_SHA,cap=1024**2))
    need(all(type(doc) is dict and doc.get('task_id') == 'MAPREL-001' for doc in (manifest,method,schema)),
         'task identity')
    need(manifest.get('schema_version') == 'maprel-source-v2','source schema')
    rows = manifest.get('files'); need(type(rows) is list and 7 <= len(rows) <= 32,'source member count')
    names,roles,total = set(),set(),0
    for row in rows:
        need(type(row) is dict,'source record')
        name,role,size = row.get('path'),row.get('role'),row.get('size_bytes')
        need(type(name) is str and name and '\\' not in name and '\0' not in name
             and not re.match('[A-Za-z]:',name),'relative source path')
        path = PurePosixPath(name)
        need(not path.is_absolute() and path.as_posix() == name
             and all(p not in ('','.','..') for p in name.split('/'))
             and name != 'source_manifest.json' and name not in names,'unique source path')
        need(type(role) is str and re.fullmatch('[a-z][a-z0-9_]{0,79}',role) and role not in roles,'unique role')
        need(type(size) is int and 0 < size <= MAX_FILE,'bounded member size')
        total += size;names.add(name);roles.add(role)
    need(set(SCIENCE) <= roles and total <= MAX_TOTAL,'closed science roles/total cap')
    directories = {p.as_posix() for n in names for p in PurePosixPath(n).parents if p.as_posix() != '.'}
    actual_files,actual_dirs = set(),set()
    for item in root.rglob('*'):
        mode = item.lstat().st_mode
        need(stat.S_ISREG(mode) or stat.S_ISDIR(mode),'source link or special member')
        (actual_dirs if stat.S_ISDIR(mode) else actual_files).add(item.relative_to(root).as_posix())
    need(actual_files == names|{'source_manifest.json'} and actual_dirs == directories,'closed source inventory')
    payloads = {}
    for row in rows:
        raw = read_bytes(root/row['path'],row['sha256'],row['size_bytes'])
        if row.get('md5') is not None: need(hashlib.md5(raw).hexdigest() == row['md5'],'published MD5')
        if row.get('git_blob_sha1') is not None:
            need(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest() == row['git_blob_sha1'],
                 'published Git content identity')
        payloads[row['role']] = raw
    identities = [{key:row[key] for key in ('role','path','size_bytes','sha256')}
                  for row in sorted(rows,key=lambda row:row['path'])]
    return dict(payloads=payloads,pins=pins,source_files=identities,method=method,schema=schema)


def gifti_guard(raw):
    """Reject external storage and oversized declared arrays before NiBabel."""
    need(len(raw) <= MAX_FILE and b'<!ENTITY' not in raw.upper()
         and re.search(rb'<!DOCTYPE[^>]*\[',raw,re.IGNORECASE) is None,
         'bounded entity-free GIFTI')
    # Standard GIFTI serializers emit an inert external DTD declaration. Remove
    # it before either parser, never resolve its URL or accept an internal DTD.
    declaration = rb'<!DOCTYPE\s+GIFTI\s+SYSTEM\s+(?:"[^"<>\[\]]+"|\x27[^\x27<>\[\]]+\x27)\s*>'
    clean, count = re.subn(declaration,b'',raw,flags=re.IGNORECASE)
    need(count <= 1 and b'<!DOCTYPE' not in clean.upper(),'only inert GIFTI SYSTEM declaration')
    root = ET.fromstring(clean)
    need(root.tag == 'GIFTI','GIFTI root')
    arrays = root.findall('DataArray')
    need(1 <= len(arrays) <= 2,'GIFTI array count')
    for arr in arrays:
        need(arr.get('Encoding') in ('ASCII','Base64Binary','GZipBase64Binary')
             and not arr.get('ExternalFileName',''),'embedded GIFTI data only')
        ndim = int(arr.get('Dimensionality','-1'))
        need(1 <= ndim <= 2,'GIFTI dimensionality')
        dims = [int(arr.get('Dim'+str(i),'0')) for i in range(ndim)]
        need(all(d > 0 for d in dims) and math.prod(dims) <= 2_000_000,'GIFTI declared size')
        item_sizes = dict(NIFTI_TYPE_UINT8=1,NIFTI_TYPE_INT8=1,NIFTI_TYPE_INT16=2,
                          NIFTI_TYPE_UINT16=2,NIFTI_TYPE_INT32=4,NIFTI_TYPE_UINT32=4,
                          NIFTI_TYPE_FLOAT32=4,NIFTI_TYPE_FLOAT64=8)
        need(arr.get('DataType') in item_sizes,'bounded numeric GIFTI datatype')
        expected = math.prod(dims)*item_sizes[arr.get('DataType')]
        need(expected <= MAX_FILE,'GIFTI expanded capacity')
        if arr.get('Encoding') != 'ASCII':
            nodes = arr.findall('Data');need(len(nodes) == 1,'one embedded GIFTI payload')
            encoded = ''.join((nodes[0].text or '').split()).encode('ascii')
            binary = base64.b64decode(encoded,validate=True)
            if arr.get('Encoding') == 'GZipBase64Binary':
                decoder = zlib.decompressobj()
                binary = decoder.decompress(binary,expected+1)
                need(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,
                     'complete bounded GIFTI compressed payload')
            need(len(binary) == expected,'GIFTI payload matches declared capacity')
    return clean


def decode_gifti(raw,role):
    clean = gifti_guard(raw)
    hemi = 'L' if role.endswith('_l') else 'R'
    anatomical = 'CortexLeft' if hemi == 'L' else 'CortexRight'
    image = nib.gifti.GiftiImage.from_bytes(clean)
    declarations,records = [],[]
    for metadata in [image.meta,*(arr.meta for arr in image.darrays)]:
        declared = dict(metadata).get('AnatomicalStructurePrimary')
        if declared is not None:
            need(declared == anatomical,'hemisphere metadata conflict');declarations.append(declared)
    for arr in image.darrays:
        need(arr.data is not None and arr.data.dtype.kind in 'iuf' and arr.data.dtype.itemsize <= 8,
             'numeric GIFTI array')
        need(arr.data.size <= 2_000_000,'decoded GIFTI size')
        transform = None
        if arr.coordsys is not None:
            matrix = np.asarray(arr.coordsys.xform,dtype=np.float64)
            need(matrix.shape == (4,4) and np.isfinite(matrix).all(),'finite GIFTI transform')
            transform = dict(dataspace=int(arr.coordsys.dataspace),xformspace=int(arr.coordsys.xformspace),matrix=matrix.tolist())
        records.append(dict(intent=int(arr.intent),shape=list(arr.data.shape),dtype=arr.data.dtype.str,
                            metadata=dict(arr.meta),coordinate_system=transform))
    if role.startswith('sphere_'):
        pointsets = [arr.data for arr in image.darrays if int(arr.intent) == 1008]
        facesets = [arr.data for arr in image.darrays if int(arr.intent) == 1009]
        need(len(pointsets) == len(facesets) == 1 and len(image.darrays) == 2,'sphere pointset/triangle intents')
        values = np.asarray(pointsets[0],dtype=np.float64);faces = facesets[0]
        need(values.ndim == 2 and values.shape[1] == 3 and np.isfinite(values).all(),'finite sphere points')
        need(faces.ndim == 2 and faces.shape[1] == 3 and faces.dtype.kind in 'iu' and faces.size > 0
             and np.all((faces >= 0)&(faces < len(values))),'sphere triangle topology')
    else:
        need(len(image.darrays) == 1 and int(image.darrays[0].intent) not in (1008,1009),'one scalar map')
        values = np.asarray(image.darrays[0].data,dtype=np.float64)
        if values.ndim == 2 and values.shape[1] == 1: values = values[:,0]
        need(values.ndim == 1,'scalar hemisphere map')
    need(2 <= len(values) <= 100000,'full hemisphere vertex bound')
    return values,dict(role=role,hemisphere=hemi,metadata=dict(image.meta),arrays=records,
                       vertex_count=len(values),declared_hemispheres=declarations)


def decode_join(payloads,expected_ids=tuple(range(1,401))):
    """Independent per-entry keyed join; expected_ids is small only in fixtures."""
    data,observed = {},{}
    for role in SCIENCE[:-1]:data[role],observed[role] = decode_gifti(payloads[role],role)
    atlas = nib.Cifti2Image.from_bytes(payloads['atlas'])
    need(len(atlas.shape) == 2 and math.prod(atlas.shape) <= 200000,'bounded CIFTI matrix')
    axes = [atlas.header.get_axis(i) for i in range(2)]
    label_index = [i for i,axis in enumerate(axes) if isinstance(axis,nib.cifti2.LabelAxis)]
    brain_index = [i for i,axis in enumerate(axes) if isinstance(axis,nib.cifti2.BrainModelAxis)]
    need(len(label_index) == len(brain_index) == 1 and label_index != brain_index,'CIFTI typed axes')
    li,bi = label_index[0],brain_index[0];label_axis,brain = axes[li],axes[bi]
    need(len(label_axis) == 1 and len(brain) == atlas.shape[bi],'single label map')
    raw_labels = np.take(np.asarray(atlas.dataobj,dtype=np.float64),0,axis=li)
    need(raw_labels.shape == (len(brain),) and np.isfinite(raw_labels).all()
         and np.all(raw_labels == np.floor(raw_labels)),'integer CIFTI labels')
    labels = raw_labels.astype(np.int64);table = label_axis.label[0]
    need(set(np.unique(labels)) <= {0,*expected_ids} and set(np.unique(labels))-{0} == set(expected_ids),
         'complete fixed parcel support')
    need(set(table) == {0,*expected_ids},'complete literal label table')
    declared = brain.nvertices
    structure_names = list(dict.fromkeys(brain.name.tolist()))
    joins,structure_records = {},[]
    for structure in structure_names:
        positions = [i for i,name in enumerate(brain.name) if name == structure]
        info = dict(brain_structure=structure,entries=len(positions),
                    nonzero_entries=sum(labels[i] != 0 for i in positions))
        info['nonzero_entries'] = int(info['nonzero_entries'])
        if structure not in STRUCTURES:
            need(all(labels[i] == 0 for i in positions),'noncortical nonzero support')
        else:
            hemi = STRUCTURES[structure];suffix = hemi.lower();full = declared.get(structure)
            need(isinstance(full,numbers.Integral) and not isinstance(full,(bool,np.bool_))
                 and 2 <= full <= 100000,'full surface declaration')
            need(all(len(data[kind+'_'+suffix]) == full for kind in ('gradient','thickness','sphere')),
                 'full GIFTI vertex alignment')
            vertices = [int(brain.vertex[i]) for i in positions]
            need(len(set(vertices)) == len(vertices) and all(0 <= v < full for v in vertices),
                 'unique in-range cortical vertex IDs')
            joins[hemi] = {vertex:int(labels[pos]) for pos,vertex in zip(positions,vertices)}
            info.update(hemisphere=hemi,full_surface_vertices=int(full),
                        vertex_ids_sha256=sha(np.asarray(vertices,dtype='<i8').tobytes()))
        structure_records.append(info)
    need(set(joins) == {'L','R'},'both cortical hemispheres')
    support,hemisphere,names,networks = [],[],[],[]
    for pid in expected_ids:
        hits = {h:sorted(v for v,label in mapping.items() if label == pid) for h,mapping in joins.items()}
        present = [h for h,vertices in hits.items() if vertices]
        need(len(present) == 1,'nonempty hemisphere-pure parcel')
        h = present[0];vertices = np.asarray(hits[h],dtype=np.int64);name = table[pid][0]
        need(type(name) is str and bool(name),'literal parcel label')
        parsed = re.fullmatch(r'7Networks_(LH|RH)_('+ '|'.join(NETWORKS) +r')_.+',name)
        need(parsed is not None and parsed.group(1) == h+'H','hemisphere/network label')
        for kind in ('gradient','thickness'):
            need(np.isfinite(data[kind+'_'+h.lower()][vertices]).all(),'finite supported map values')
        support.append(vertices);hemisphere.append(0 if h == 'L' else 1);names.append(name);networks.append(parsed.group(2))
    observed['atlas'] = dict(shape=list(atlas.shape),label_axis_index=li,brain_model_axis_index=bi,
        label_map_name=str(label_axis.name[0]),structures=structure_records,
        excluded_zero_entries=int(np.count_nonzero(labels == 0)),label_keys=sorted(map(int,table)),
        cortical_join='brain_structure_and_local_vertex_id',sphere_coordinate_transform='stored_pointset_no_transform',
        map_support='nonzero_cortical_labels_no_imputation')
    return dict(data=data,support=support,parcel_ids=np.asarray(expected_ids,dtype=np.int64),
                hemisphere=np.asarray(hemisphere,dtype=np.int64),labels=names,networks=networks,source_observed=observed)


def reduce_join(join):
    means,centroids,digests = [],[],[]
    for vertices,code in zip(join['support'],join['hemisphere']):
        h = 'L' if code == 0 else 'R';suffix = h.lower()
        means.append([np.mean(join['data'][role+'_'+suffix][vertices],dtype=np.float64)
                      for role in ('gradient','thickness')])
        xyz = np.mean(join['data']['sphere_'+suffix][vertices],axis=0,dtype=np.float64)
        norm = np.linalg.norm(xyz)
        need(np.isfinite(xyz).all() and math.isfinite(norm) and norm > 0,'nonzero finite mean centroid')
        centroids.append(xyz/norm*100.)
        digests.append(sha(b'MAPREL_support_v2\n'+h.encode()+b'\n'+vertices.astype('<i8').tobytes()))
    maps = np.asarray(means,dtype=np.float64);centroids = np.asarray(centroids,dtype=np.float64)
    need(np.isfinite(maps).all() and np.isfinite(centroids).all(),'finite parcel primitives')
    return dict(parcel_ids=join['parcel_ids'],labels=join['labels'],networks=join['networks'],
                hemisphere=join['hemisphere'],support_n=np.array([len(v) for v in join['support']],dtype=np.int64),
                support_sha256=digests,centroids=centroids,maps=maps,source_observed=join['source_observed'])


def load_sources(data_dir,manifest_path,method_path,schema_path):
    inputs = authenticate(data_dir,manifest_path,method_path,schema_path)
    basis = reduce_join(decode_join(inputs['payloads']))
    return dict(basis,pins=inputs['pins'],source_files=inputs['source_files'])
