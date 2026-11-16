"""Bounded NPZ validation and public identity joining before private target I/O."""
from pathlib import Path
import ast,hashlib,io,json,math,stat,struct,zipfile,zlib
import numpy as np
from bundle import npz_headers

ROWS=22091
MAX_FILE_BYTES=1_000_000
MAX_UNCOMPRESSED_BYTES=600_000
SCHEMAS={'case_id':(ROWS,), 'velocity_m_s':(ROWS,2)}


class InvalidSubmission(ValueError):pass


def require(ok,message):
    if not ok:raise ValueError(message)


def candidate_require(ok,message):
    if not ok:raise InvalidSubmission(message)


def pinned_bytes(path,pin,cap):
    path=Path(path);before=path.lstat()
    require(not path.is_symlink() and stat.S_ISREG(before.st_mode) and before.st_nlink==1
            and before.st_size==pin['bytes'] and 0<before.st_size<=cap,'Exact bounded ordinary pinned input')
    body=path.read_bytes();after=path.stat()
    require(len(body)==pin['bytes'] and hashlib.sha256(body).hexdigest()==pin['sha256']
            and (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
                (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'Pinned input changed')
    return body


def load_submission(path,pin):
    try:
        body=pinned_bytes(path,pin,MAX_FILE_BYTES)
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            infos=archive.infolist()
            candidate_require(len(infos)==2 and len({x.filename for x in infos})==2
                              and {x.filename for x in infos}=={k+'.npy' for k in SCHEMAS},'Exactly case_id and velocity_m_s')
            candidate_require(sum(x.file_size for x in infos)<=MAX_UNCOMPRESSED_BYTES,'Uncompressed archive cap')
            for info in infos:
                candidate_require(info.compress_type in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED)
                                  and not info.flag_bits&1 and not info.is_dir()
                                  and stat.S_IFMT(info.external_attr>>16) in (0,stat.S_IFREG),'Ordinary stored/deflated arrays only')
                with archive.open(info) as source:
                    magic=source.read(8)
                    candidate_require(magic[:6]==b'\x93NUMPY' and magic[6:] in (b'\x01\x00',b'\x02\x00',b'\x03\x00'),'Supported NPY header')
                    size_bytes=2 if magic[6:]==b'\x01\x00' else 4
                    raw_length=source.read(size_bytes)
                    candidate_require(len(raw_length)==size_bytes,'Complete NPY length')
                    length=int.from_bytes(raw_length,'little')
                    candidate_require(0<length<=4096,'Bounded header before allocation')
                    raw_header=source.read(length)
                    candidate_require(len(raw_header)==length,'Complete NPY header')
                    header=ast.literal_eval(raw_header.decode('utf8' if magic[6:]==b'\x03\x00' else 'latin1').strip())
                name=info.filename[:-4]
                candidate_require(type(header)is dict and set(header)=={'descr','fortran_order','shape'}
                                  and type(header['fortran_order'])is bool and type(header['shape'])is tuple
                                  and header['shape']==SCHEMAS[name] and type(header['descr'])is str,'Exact fixed public shape and scalar dtype')
                dtype=np.dtype(header['descr'])
                candidate_require(not dtype.hasobject and dtype.fields is None and dtype.subdtype is None,'No object or structured arrays')
                if name=='case_id':candidate_require(dtype.kind in 'iu' and dtype.itemsize in (2,4,8),'Integer case IDs')
                else:candidate_require(dtype.kind=='f' and dtype.itemsize in (2,4,8),'IEEE float16/32/64 velocities')
                candidate_require(info.file_size==8+size_bytes+length+math.prod(SCHEMAS[name])*dtype.itemsize,'Exact NPY extent')
        with np.load(io.BytesIO(body),allow_pickle=False,max_header_size=4096) as archive:
            ids=archive['case_id'];velocity=archive['velocity_m_s']
        candidate_require(ids.shape==(ROWS,) and velocity.shape==(ROWS,2),'Public array shape')
        candidate_require(np.all(ids>=3010) and np.all(ids<=25100),'Only declared assessment case IDs')
        order=np.argsort(ids,kind='stable');canonical=ids[order].astype(np.uint32)
        candidate_require(np.array_equal(canonical,np.arange(3010,25101,dtype=np.uint32)),'Each public case ID exactly once')
        candidate_require(np.isfinite(velocity).all(),'All velocity values finite')
        return {'case_id':canonical,'velocity_m_s':np.asarray(velocity[order],dtype=np.float64)}
    except InvalidSubmission:raise
    except (ValueError,TypeError,UnicodeError,SyntaxError,OverflowError,EOFError,zipfile.BadZipFile,struct.error,zlib.error) as error:
        raise InvalidSubmission('Invalid bounded velocity NPZ: '+type(error).__name__) from error


def load_target(path,pin):
    body=pinned_bytes(path,pin,1_000_000)
    npz_headers(body,{'case_id':('<u4',(ROWS,)), 'velocity_m_s':('<f8',(ROWS,2))})
    with np.load(io.BytesIO(body),allow_pickle=False,max_header_size=4096) as archive:
        value={k:archive[k] for k in SCHEMAS}
    require(np.array_equal(value['case_id'],np.arange(3010,25101,dtype=np.uint32))
            and np.isfinite(value['velocity_m_s']).all(),'Frozen private target identity/finite values')
    return value


def unique(pairs):
    value={}
    for key,item in pairs:
        require(key not in value,'Unique trusted JSON keys');value[key]=item
    return value


def load_reference(path,pin):
    body=pinned_bytes(path,pin,150000)
    value=json.loads(body.decode('utf8'),object_pairs_hook=unique,
                     parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Finite trusted JSON')))
    require(value['candidate_id']=='NEURAL-023' and value['status']=='fixed_reference_scored_and_independently_audited'
            and value['result']['primary_metric']=='mean_axis_r2','Exact existing reference endpoint')
    expected={'zero_velocity','source_mean_velocity','calibration_mean_velocity','source_only_ridge',
              'source_only_ridge_plus_calibration_mean_residual','calibration_only_ridge','balanced_pooled_ridge'}
    metrics=value['result']['metrics']
    require(set(metrics)==expected and all(v['rows']==ROWS for v in metrics.values()),'All seven references on identical support')
    return metrics


def generated_validation_checks():
    """Qualification only: generated public arrays, no empirical target reads."""
    import tempfile,time
    started=time.monotonic();checks=[]
    ids=np.arange(3010,25101,dtype=np.uint32)
    velocity=np.column_stack((np.arange(ROWS)%7,np.arange(ROWS)%11)).astype(np.float64)
    def encoded(a,b,compressed=False,extra=False):
        stream=io.BytesIO();values={'case_id':a,'velocity_m_s':b}
        if extra:values['extra']=np.zeros(1)
        (np.savez_compressed if compressed else np.savez)(stream,**values)
        return stream.getvalue()
    with tempfile.TemporaryDirectory(prefix='rtt-public-check-') as temporary:
        path=Path(temporary)/'candidate.npz'
        def check(name,body,valid):
            require(time.monotonic()-started<4,'Bounded generated public checks')
            path.write_bytes(body);pin={'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
            try:
                got=load_submission(path,pin)
                require(valid,'Invalid generated schema was accepted')
                require(np.array_equal(got['case_id'],ids) and np.array_equal(got['velocity_m_s'],velocity),
                        'Accepted public encoding preserves joined identity and values')
            except InvalidSubmission:
                require(not valid,'Valid generated standard NPZ was rejected')
            checks.append(name)
        check('stored_float64',encoded(ids,velocity),True)
        check('deflated_float32',encoded(ids.astype('>i8'),velocity.astype('>f4'),True),True)
        check('fortran_float16',encoded(ids.astype('<i2'),np.asfortranarray(velocity.astype('<f2'))),True)
        check('reversed_ids_join',encoded(ids[::-1],velocity[::-1]),True)
        bad=ids.copy();bad[0]=bad[1]
        check('duplicate_id',encoded(bad,velocity),False)
        bad=ids.copy();bad[0]=3009
        check('out_of_range_id',encoded(bad,velocity),False)
        check('missing_row',encoded(ids[:-1],velocity[:-1]),False)
        check('float_id',encoded(ids.astype(float),velocity),False)
        check('integer_velocity',encoded(ids,velocity.astype('i4')),False)
        check('wrong_velocity_shape',encoded(ids,velocity[:,0]),False)
        check('extra_member',encoded(ids,velocity,extra=True),False)
        bad=velocity.copy();bad[0,0]=np.nan
        check('nonfinite_nan',encoded(ids,bad),False)
        bad=velocity.copy();bad[0,0]=np.inf
        check('nonfinite_infinity',encoded(ids,bad),False)
        check('object_dtype',encoded(ids,velocity.astype(object)),False)
        check('invalid_zip',b'not an NPZ',False)
        check('empty_file',b'',False)
        good=encoded(ids,velocity)
        duplicate=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(good)) as source,zipfile.ZipFile(duplicate,'w') as target:
            # Duplicate ZIP filenames are legal at the ZIP layer but invalid here.
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter('ignore',UserWarning)
                for name in ('case_id.npy','velocity_m_s.npy','case_id.npy'):target.writestr(name,source.read(name))
        check('duplicate_zip_member',duplicate.getvalue(),False)
        oversized=io.BytesIO()
        with zipfile.ZipFile(oversized,'w',compression=zipfile.ZIP_DEFLATED) as target:
            target.writestr('case_id.npy',b'x'*600001);target.writestr('velocity_m_s.npy',b'x')
        check('compressed_uncompressed_cap',oversized.getvalue(),False)
    return {'status':'generated_public_validation_passed','checks':checks,'count':len(checks),
            'elapsed_seconds':time.monotonic()-started,'empirical_array_reads':0,'private_target_loads':0}
