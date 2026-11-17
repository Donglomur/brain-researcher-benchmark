"""Future full original-source preparation; no reader executes at import.

CTF uses the original immutable131-member release. Elekta requires all114
independently authenticated original38-parcel FIFs; that missing historical
binding is not filled by a smaller/different release. Native source bytes stay
unchanged. Regional copies and physical retained-sample maps are separate.
"""
import ast
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile
from core import TASK, HMM, people, runs, identity, need, encoded, finite
from safe_io import capture, child, durable_new, new_json, pin, strict, write_array

CTF_BYTES = 684320829
CTF_SHA = 'c6bb9b81844e156af410071d96f53d6e460bc5fa9e0347ee63fc5ab691857463'


def ctf_demographics(raw):
    """Validate the released CSV's literal person/row join before using ages.

    The author scripts consume ages in row order. Reordering a malformed CSV
    here would silently change that literal analysis, so require the original
    subject00..subject64 order and retain the original member bytes separately.
    The returned records also support the explicitly separate age sensitivity.
    """
    need(type(raw) is bytes, 'Original demographics CSV bytes')
    try:
        reader = csv.reader(io.StringIO(raw.decode('utf-8'), newline=''), strict=True)
        header = next(reader, None)
        need(header is not None and len(header) == 4 and
             set(header) == {'name', 'age', 'gender', 'handedness'},
             'Exact released demographics columns, without duplicate headers')
        person_column, age_column = header.index('name'), header.index('age')
        roster = people('ctf_static')
        records = []
        for index, row in enumerate(reader):
            need(index < len(roster) and len(row) == len(header),
                 'Exactly65 complete demographics rows, without extra fields')
            person = row[person_column]
            need(person == roster[index],
                 'Literal ordered CTF person identity; no positional relabeling or sorting')
            try:
                age = float(row[age_column])
            except ValueError as error:
                raise ValueError('Original age must be numeric years') from error
            need(finite(age) and 0 < age < 130, 'Finite original age in years')
            records.append({'person': person, 'age': age})
        need(len(records) == len(roster), 'All65 original demographics rows')
    except (csv.Error, UnicodeDecodeError) as error:
        raise ValueError('Well-formed UTF-8 original demographics CSV') from error
    return records


def numeric_original(raw):
    """Primitive original NPY decoding, preserving its full dtype/order extent."""
    import numpy as np
    need(len(raw) >= 12 and raw[:6] == b'\x93NUMPY' and raw[6:8] in (b'\x01\x00', b'\x02\x00'),
         'Original primitive NPY1/2')
    width = 2 if raw[6] == 1 else 4
    start = 8+width
    size = int.from_bytes(raw[8:start], 'little')
    need(0 < size <= 65536 and start+size <= len(raw), 'Bounded complete original header')
    h = ast.literal_eval(raw[start:start+size].decode('latin1'))
    need(type(h) is dict and set(h) == {'descr','fortran_order','shape'} and
         h['descr'] in ('<f4','<f8','>f4','>f8') and type(h['fortran_order']) is bool and
         type(h['shape']) is tuple and len(h['shape']) in (1,2) and
         all(type(n) is int and n > 0 for n in h['shape']), 'Complete original real array axes')
    count = 1
    for n in h['shape']: count *= n
    need(start+size+count*int(h['descr'][-1]) == len(raw), 'Full original NPY extent')
    x = np.frombuffer(raw, dtype=h['descr'], offset=start+size).reshape(h['shape'], order='F' if h['fortran_order'] else 'C')
    if x.ndim == 1: x = x[:,None]
    need(np.isfinite(x).all(), 'Full finite original supplied run; no row dropping')
    return np.ascontiguousarray(x, dtype='<f8')


def build(spec, output, limits):
    need(set(limits) == {'read_bytes','write_bytes','array_bytes'} and
         all(type(v) is int and v > 0 for v in limits.values()), 'Full prospective preparation allocation')
    root = Path(output)
    need(not root.exists() and not root.is_symlink(), 'Fresh original preparation tree')
    root.mkdir(mode=0o700, parents=True)
    used = {'read':0,'write':0}
    def read(path, descriptor):
        used['read'] += descriptor['bytes']
        need(used['read'] <= limits['read_bytes'], 'Original full-input read allocation')
        return capture(path, max(1, descriptor['bytes']), descriptor)
    def save(name, body):
        used['write'] += len(body)
        need(used['write'] <= limits['write_bytes'], 'Complete source/preparation write allocation')
        target = root/name;target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        return durable_new(target, body)
    def array(name, x):
        target=root/name;target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        d=write_array(target,np.ascontiguousarray(x),min(limits['array_bytes'],limits['write_bytes']-used['write']))
        used['write']+=d['bytes'];d['path']=name;return d
    need(spec['ctf_archive']['bytes'] == CTF_BYTES and spec['ctf_archive']['sha256'] == CTF_SHA,
         'Exact selected original CTF release, never another source')
    directory = strict(read(spec['ctf_directory']['path'], {k:spec['ctf_directory'][k] for k in ('bytes','sha256')}))['members']
    entries={x['member']:x for x in directory if not x['member'].endswith('/')}
    required={f'{family}/{p}.npy' for family in ('bursts','networks') for p in people('ctf_static')}|{'demographics.csv'}
    need(set(entries)==required and len(directory)==133, 'Complete original65+65+demographics directory')
    archive=read(spec['ctf_archive']['path'],{'bytes':CTF_BYTES,'sha256':CTF_SHA})
    regional={'ctf_bursts':[],'ctf_networks':[],'elekta':[]}; native_files={}; age_records=None
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        infos={i.filename:i for i in z.infolist() if not i.is_dir()}
        need(set(infos)==required and len(z.infolist())==133,'Exact original ZIP support')
        def read_member(name):
            d,i=entries[name],infos[name]
            need(i.file_size==d['bytes'] and i.compress_size==d['compressed_bytes'] and i.CRC==int(d['crc32'],16)
                 and not i.flag_bits&1, 'Exact released member metadata')
            used['read']+=i.file_size;need(used['read']<=limits['read_bytes'],'Expanded full source read charge')
            body=z.read(i);need(len(body)==i.file_size,'Complete CRC-checked member')
            return body
        # Check the age/person join before decoding signals or publishing data.
        demographics=read_member('demographics.csv')
        age_records=ctf_demographics(demographics)
        native_files['ctf/demographics.csv']=save('ctf/demographics.csv',demographics)
        import numpy as np
        for name in sorted(required-{'demographics.csv'}):
            body=read_member(name)
            native_files['ctf/'+name]=save('ctf/'+name,body)
            family,person=Path(name).parts[0],Path(name).stem
            x=numeric_original(body);need(x.shape[1]==(1 if family=='bursts' else 38),'All original channels')
            group='ctf_bursts' if family=='bursts' else'ctf_networks'
            desc=array(f'regional/{group}/{person}.npy',x)
            rowmap=array(f'physical_rows/{group}/{person}.npy',np.arange(len(x),dtype='<i8'))
            regional[group].append({'person':person,'run':1,'observations':desc,'physical_rows':rowmap,
                                    'original':{'path':'ctf/'+name,**native_files['ctf/'+name]}})
    del archive
    binding=strict(read(spec['elekta_binding']['path'],{k:spec['elekta_binding'][k] for k in ('bytes','sha256')}))
    need(binding['schema']=='osl_full_elekta_source_v1' and
         all(type(binding[k]) is str and binding[k] for k in ('source_url','source_version','historical_lineage')),
         'Authenticated historical full Elekta source, not inferred from availability')
    rows=sorted(binding['files'],key=lambda r:(r['person'],r['run']))
    need([(r['person'],r['run']) for r in rows]==runs('elekta_ae'), 'Full original19x6 input membership')
    import mne
    for row in rows:
        name=f"src/{row['person']}_run{row['run']:02d}/sflip_parc-raw.fif"
        need(row['file']==name, 'Exact original source object/run mapping')
        body=read(child(spec['elekta_root'],name),{k:row[k] for k in ('bytes','sha256')})
        native_files['elekta/'+name]=save('elekta/'+name,body);del body
        raw=mne.io.read_raw_fif(root/'elekta'/name,preload=False,verbose=False)
        try:
            misc=mne.pick_types(raw.info,misc=True,exclude=[])
            need(raw.info['sfreq']==250 and len(misc)==38 and len(mne.pick_types(raw.info,stim=True,exclude=[]))>0,
                 'Original250Hz38Giles channels and event stream')
            values,times=raw.get_data(picks='misc',reject_by_annotation='omit',return_times=True)
            x=np.ascontiguousarray(values.T,dtype='<f8')
            need(x.shape[1]==38 and len(x)>0 and np.isfinite(x).all(),'Full source-loader-retained rows')
            indices=np.rint(np.asarray(times)*250).astype('<i8')
            need(len(indices)==len(x) and (np.diff(indices)>0).all(),'Exact retained physical sample order')
            key=f"{row['person']}_run{row['run']:02d}"
            regional['elekta'].append({'person':row['person'],'run':row['run'],
                'observations':array('regional/elekta/'+key+'.npy',x),
                'physical_rows':array('physical_rows/elekta/'+key+'.npy',indices),
                'original':{'path':'elekta/'+name,**native_files['elekta/'+name]},
                'original_n_times':int(raw.n_times),'annotation_policy':'literal_native_omit',
                'parcel_order':[raw.ch_names[i] for i in misc]})
        finally:raw.close()
    lineage=identity({'ctf':spec['ctf_archive'],'elekta':spec['elekta_binding'],'native':native_files})
    packets={}
    for branch in HMM:
        group='elekta' if branch.startswith('elekta') else'ctf_bursts' if branch=='ctf_bursts' else'ctf_networks'
        packet={'schema':'osl_original_regional_packet_v1','task_id':TASK,'branch':branch,
                'sampling_frequency':HMM[branch][2],'channels':1 if branch=='ctf_bursts' else 38,
                'original_preparation_binding':lineage,'runs':regional[group]}
        name='packets/'+branch+'.json';packets[branch]={'path':name,**save(name,encoded(packet)), 'identity':identity(packet)}
    ages={'path':'AGES.json',**save('AGES.json',encoded(age_records)),'identity':identity(age_records)}
    result={'schema':'osl_complete_originals_v1','native_files':native_files,'packets':packets,'ages':ages,
            'lineage':lineage,'ctf_people':65,'elekta_people':19,'elekta_runs':114,'logical_IO':used,
            'original_bytes_preserved':True,'historical_elekta_lineage_requires_external_authentication':True}
    save('ORIGINALS.json',encoded(result))
    return result
