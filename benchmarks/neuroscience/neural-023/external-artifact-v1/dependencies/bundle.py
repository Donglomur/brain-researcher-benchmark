"""Bounded opaque packet publication; no NumPy imports or model execution."""
from pathlib import Path
import ast,hashlib,io,json,math,os,stat,struct,zipfile

def need(ok,message):
    if not ok:raise ValueError(message)

SCHEMAS={
 'public/source.npz':{'counts':('<u4',(18700,96)),'bin_edges_seconds':('<f8',(18701,)),'endpoint_bin':('<u4',(18691,)),'velocity_m_s':('<f8',(18691,2))},
 'public/calibration.npz':{'counts':('<u4',(3000,96)),'bin_edges_seconds':('<f8',(3001,)),'endpoint_bin':('<u4',(2991,)),'velocity_m_s':('<f8',(2991,2))},
 'public/assessment.npz':{'counts':('<u4',(22100,96)),'bin_edges_seconds':('<f8',(22101,)),'endpoint_bin':('<u4',(22091,))},
 'private/assessment.npz':{'case_id':('<u4',(22091,)),'velocity_m_s':('<f8',(22091,2))}}

def entries(archive,expected,cap):
    infos=archive.infolist();need(len(infos)==len(expected)and len({x.filename for x in infos})==len(infos)and {x.filename for x in infos}==set(expected),'Exact unique archive members')
    need(sum(x.file_size for x in infos)<=cap,'Bounded total uncompressed bytes')
    for x in infos:
        mode=x.external_attr>>16
        need(x.compress_type==zipfile.ZIP_STORED and not x.flag_bits&1 and not x.is_dir()and stat.S_IFMT(mode)in(0,stat.S_IFREG),'Only stored ordinary files, no encrypted/linked/directory members')
        need(x.file_size==x.compress_size and 0<x.file_size<=cap,'Exact uncompressed member extent')

def npz_headers(body,expected):
    with zipfile.ZipFile(io.BytesIO(body))as archive:
        entries(archive,{x+'.npy'for x in expected},19_000_000)
        for name,(dtype,shape)in expected.items():
            info=archive.getinfo(name+'.npy')
            with archive.open(info)as source:
                magic=source.read(10);need(magic[:8]==b'\x93NUMPY\x01\x00','Canonical NPY1 header')
                length=struct.unpack('<H',magic[8:])[0];need(0<length<=4096,'Bounded NPY header before payload')
                header=ast.literal_eval(source.read(length).decode('latin1').strip())
            need(header=={'descr':dtype,'fortran_order':False,'shape':shape},'Exact dtype/shape/order; no object arrays')
            itemsize = 4 if dtype == '<u4' else 8
            need(info.file_size==10+length+math.prod(shape)*itemsize,'Exact NPY byte extent')

def decode(body):
    need(type(body)is bytes and 0<len(body)<=19_000_000,'Bounded conversion bundle')
    with zipfile.ZipFile(io.BytesIO(body))as archive:
        names={x.filename for x in archive.infolist()}
        need('operator_summary.json'in names,'Operator status member required')
        expected=set(SCHEMAS)|{'public/manifest.json','operator_summary.json'}
        if names=={'operator_summary.json'}:expected=names
        entries(archive,expected,19_000_000)
        raw=archive.read('operator_summary.json');need(len(raw)<=200_000,'Bounded conversion summary')
        report=json.loads(raw,parse_constant=lambda x:(_ for _ in()).throw(ValueError('Nonfinite operator JSON')))
        need(report['candidate_id']=='NEURAL-023'and report['stage']=='conversion-v1'and report['scientific_fits']==0,'Fixed trusted converter result')
        if report['status']=='failed_preserved_no_packet':
            need(names=={'operator_summary.json'},'Failed conversion has no published packet');return report,{}
        need(report['status']=='converted_all_fixed_windows'and set(report['packet_files'])==expected-{'operator_summary.json'},'Exact successful complete packet inventory')
        need(report['generated_checks']['count']==11 and report['generated_checks']['elapsed_seconds']<=3,'Generated boundary guards before source values')
        files={}
        for name in sorted(expected-{'operator_summary.json'}):
            raw=archive.read(name);pin=report['packet_files'][name]
            need(len(raw)==pin['bytes']and hashlib.sha256(raw).hexdigest()==pin['sha256'],'Captured exact member identity')
            if name in SCHEMAS:npz_headers(raw,SCHEMAS[name])
            else:
                need(len(raw)<=20000,'Bounded public manifest');value=json.loads(raw)
                need(value['candidate_id']=='NEURAL-023'and value['channel_order']==[f'M1 {i:03d}'for i in range(1,97)]and value['lags']==10,'Declared public coordinate frame')
            files[name]=raw
        return report,files

def publish(body,root,budget):
    report,files=decode(body)
    if not files:return report,None
    temporary=root/'packet.incomplete';final=root/'packet';need(not temporary.exists()and not final.exists(),'One fresh packet publication')
    temporary.mkdir(mode=0o700);(temporary/'public').mkdir(mode=0o700);(temporary/'private').mkdir(mode=0o700)
    success=False
    try:
        for name,raw in files.items():budget.write(temporary/name,raw,mode=0o444)
        for name,raw in files.items():need(hashlib.sha256((temporary/name).read_bytes()).hexdigest()==hashlib.sha256(raw).hexdigest(),'Sealed packet byte parity')
        # Keep the staging root writable through rename on macOS. Its private
        # subdirectory stays0700. Publication authority is the later outer receipt.
        temporary.rename(final);(final/'public').chmod(0o555);success=True
        return report,{'path':str(final),'public_files':sorted(x for x in files if x.startswith('public/')),'private_files':sorted(x for x in files if x.startswith('private/')),'member_pins':report['packet_files'],'source_archive_retained':True,'authority':'Only successful outer conversion receipt, never directory presence'}
    finally:
        if not success and final.exists():
            final.chmod(0o700);final.rename(root/'packet.failed-publication')
