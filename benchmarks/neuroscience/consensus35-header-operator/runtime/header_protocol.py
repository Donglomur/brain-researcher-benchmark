"""Complete35 bounded primitive NPY metadata; no numerical payload decoding."""
import ast
import hashlib
import math

DTYPES = {'|u1': 1, '|i1': 1, '<u2': 2, '<i2': 2, '<u4': 4, '<i4': 4,
          '<u8': 8, '<i8': 8, '<f4': 4, '<f8': 8}
HEADER_CAP = 4096
LEAVES = {'all_lm_cells.npy','all_v1_cells.npy','all_times.npy','stim_times.npy','unique_ids.npy'}


def need(ok,why):
    if not ok:
        raise ValueError(why)


def remaining_header(index,row,magic,fetch):
    """Only the accepted donor NPY portion, with standalone offset zero."""
    prefix='f%02d-' % index
    data_start=0
    us=row['bytes']
    need(len(magic) == 8 and magic[:6] == b'\x93NUMPY', 'NPY magic')
    version = tuple(magic[6:8])
    need(version in ((1, 0), (2, 0)), 'only bounded primitive NPYv1/v2 metadata')
    width = 2 if version == (1, 0) else 4
    size_bytes = fetch(prefix + 'length', data_start + 8, width)
    need(len(size_bytes) == width, 'exact header-length field')
    size = int.from_bytes(size_bytes, 'little')
    need(0 < size <= HEADER_CAP and 8 + width + size <= us, 'bounded declared NPY header')
    header = fetch(prefix + 'header', data_start + 8 + width, size)
    need(len(header) == size and header.endswith(b'\n'), 'complete NPY header terminator')
    tree = ast.parse(header.decode('ascii').strip(), mode='eval')
    need(isinstance(tree.body, ast.Dict) and sum(1 for _ in ast.walk(tree)) <= 64, 'bounded header AST')
    keys = [ast.literal_eval(k) for k in tree.body.keys]
    need(len(keys) == 3 and set(keys) == {'descr', 'shape', 'fortran_order'}, 'unique exact NPY fields')
    meta = ast.literal_eval(tree)
    shape = meta['shape']
    need(type(meta['descr']) is str and meta['descr'] in DTYPES and
         type(meta['fortran_order']) is bool and type(shape) is tuple and
         1 <= len(shape) <= 3 and all(type(x) is int and 0 < x <= 2**40 for x in shape),
         'primitive numeric dtype/shape/order; objects and structures refused')
    payload_bytes = math.prod(shape) * DTYPES[meta['descr']]
    header_extent = 8 + width + size
    need(header_extent + payload_bytes == us, 'exact full NPY extent from header only')
    return {'index':index,'file_id':row['file_id'],'animal_id':row['animal_id'],
            'relative_path':row['relative_path'],'file_bytes':us,
            'NPY_version':list(version),'NPY_header_bytes':header_extent,
            'NPY_header_sha256':hashlib.sha256(magic+size_bytes+header).hexdigest(),
            'dtype':meta['descr'],'shape':list(shape),'fortran_order':meta['fortran_order'],
            'numeric_payload_bytes_declared':payload_bytes,
            'numeric_payload_bytes_read':0,'full_file_sha256':None}


def geometry(headers,rows):
    need(len(headers)==len(rows)==35,'complete35 header and operand scope')
    need([h['index'] for h in headers]==list(range(35)),'ordered complete35')
    lookup={}
    animals=[]
    for h,r in zip(headers,rows):
        need((h['file_id'],h['animal_id'],h['relative_path'])==
             (r['file_id'],r['animal_id'],r['relative_path']),'header/operand identity join')
        animal,leaf=r['relative_path'].split('/')
        need(animal==r['animal_id'] and leaf in LEAVES,'original animal/role identity')
        need((animal,leaf) not in lookup,'no duplicate header')
        lookup[(animal,leaf)]=h
        if animal not in animals:animals.append(animal)
    need(len(animals)==7,'seven animals')
    joins=[]
    total_json=0
    for animal in animals:
        need({leaf for a,leaf in lookup if a==animal}==LEAVES,'allfive roles per animal')
        lm,v1,a,s,c=(lookup[(animal,n)] for n in
          ('all_lm_cells.npy','all_v1_cells.npy','all_times.npy','stim_times.npy','unique_ids.npy'))
        errors=[]; n=channels=retained_time=None
        if len(lm['shape'])!=3 or len(v1['shape'])!=3:
            errors.append('spikes_not_rank3')
        elif (lm['shape'][0],lm['shape'][2])!=(v1['shape'][0],v1['shape'][2]):
            errors.append('spike_trial_or_time_shape_mismatch')
        else:
            n=lm['shape'][0];channels=lm['shape'][1]+v1['shape'][1];retained_time=lm['shape'][2]-100
            if retained_time<=0:errors.append('no_time_bins_after_declared100bin_drop')
        if any(h['dtype'] not in ('<f4','<f8') for h in (lm,v1)):
            errors.append('spike_dtype_not_admitted_floating_header')
        for name,h,width in [('all_times',a,1),('stim_times',s,1),('conditions',c,2)]:
            if len(h['shape'])!=2 or h['shape'][1]!=width or (n is not None and h['shape'][0]!=n):
                errors.append(name+'_shape_incompatible_with_current_converter')
        conditional=None
        if not errors:
            conditional=n*((17*channels+2)*retained_time+2)
            total_json+=conditional
        joins.append({'animal_id':animal,'necessary_header_conditions_pass':not errors,
                      'issues':errors,'trials_if_spikes_join':n,'channels_if_spikes_join':channels,
                      'retained_time_bins_if_spikes_join':retained_time,
                      'conditional_count_JSON_upper_bytes':conditional})
    return {'animals':joins,'all_necessary_header_conditions_pass':all(not x['issues'] for x in joins),
            'conditional_count_JSON_upper_bytes':total_json if all(not x['issues'] for x in joins) else None,
            'bound_condition':'Only if later authentic count-domain validation admits integers0..2**53; protocol/lineage/other products and native workspace are additional.',
            'biological_identity_or_clock_values_verified':False,
            'numeric_value_or_full_hash_validation':False,
            'normalization_or_scientific_readiness':False}


def collect(rows,transport):
    need(len(rows)==35 and [r['index'] for r in rows]==list(range(35)),'all35 ordered originals')
    assets=[dict(file_id=r['file_id'],bytes=r['bytes'],
                 filename=r['relative_path'].split('/')[-1],
                 download_url=r['canonical_download_url'],
                 provider_computed_md5=r['published_computed_md5']) for r in rows]
    magic=[]
    for i,(r,a) in enumerate(zip(rows,assets)):
        b=transport.fetch(a,0,8,'f%02d-magic'%i)
        need(len(b)==8 and b[:6]==b'\x93NUMPY' and tuple(b[6:]) in ((1,0),(2,0)),
             'all35 NPYv1/v2 prefixes before further reads')
        magic.append(b)
    headers=[]
    for i,(r,a,b) in enumerate(zip(rows,assets,magic)):
        h=remaining_header(i,r,b,lambda label,start,size,a=a:transport.fetch(a,start,size,label))
        h['strong_etag']=transport.etag(a)
        headers.append(h)
    receipt=transport.receipt()
    need(receipt['logical_ranges']==105 and receipt['transactions']==210
         and receipt['redirects']==105 and receipt['complete_header_objects']==35,
         'complete35 three-range canonical redirect protocol')
    return {'schema':'consensus35_primitive_header_report_v1','complete_metadata_inquiry':True,
            'headers':headers,'geometry':geometry(headers,rows),
            'logical_ranges':105,'HTTP_transactions':210,
            'returned_entity_bytes':receipt['body_returned_bytes'],
            'numeric_payload_ranges_requested':0,'full_file_hashes_verified':False,
            'scientific_readiness':False}
