"""Independent tiny generated NPZ boundary inquiry; no authentic payloads."""
from pathlib import Path
import argparse
import hashlib, importlib.util, json, math, resource, signal, struct, time, zlib
EXPECTED_SHA='92f8b097c5692eb1182130faf808073f1fe42a806530f4bd8029b344c29645de'
def npy(values):
    text=repr({'descr':'<f8','fortran_order':False,'shape':(len(values),)})
    h=(text+' '*(-(10+len(text)+1)%64)+'\n').encode()
    return b'\x93NUMPY\x01\x00'+struct.pack('<H',len(h))+h+b''.join(struct.pack('<d',v) for v in values)
def archive(change=None,stored=False):
    rows=[('time.npy',npy([1.,2.])),('voltage.npy',npy([-70.,20.])),('stimulus.npy',npy([0.,10.]))]
    local=bytearray();central=bytearray()
    for i,(name,plain) in enumerate(rows):
        original=plain;method=0 if stored else 8;flags=0;local_flags=None
        local_crc=None;local_method=None;gap=b'';tail=b'';cut=False
        if i==0:
            if change=='trailing_compressed_bytes':tail=b'UNREAD'
            elif change=='truncated_deflate_eof':cut=True
            elif change=='false_uncompressed_extent':plain+=struct.pack('<d',3.)
            elif change=='local_crc_mismatch':local_crc=123
            elif change=='local_method_mismatch':local_method=0
            elif change=='reserved_flag':flags=0x4000
            elif change=='descriptor_flag_without_descriptor':flags=8
            elif change=='nul_name_alias':name+='\x00shadow'
            elif change=='inter_member_gap':gap=b'UNDECLARED'
            elif change=='local_flags_mismatch':local_flags=1
        if method==8:
            co=zlib.compressobj(level=6,wbits=-15);compressed=co.compress(plain)+co.flush()
        else:compressed=plain
        if cut:compressed=compressed[:-1]
        compressed+=tail
        name=name.encode();crc=zlib.crc32(original)&0xffffffff;cs=len(compressed);us=len(original);offset=len(local)
        lc=crc if local_crc is None else local_crc;lm=method if local_method is None else local_method
        lf=flags if local_flags is None else local_flags
        ls,lu=cs,us
        if flags&8:lc=ls=lu=0
        local+=struct.pack('<IHHHHHIIIHH',0x04034b50,20,lf,lm,0,0,lc,ls,lu,len(name),0)+name+compressed+gap
        central+=struct.pack('<IHHHHHHIIIHHHHHII',0x02014b50,20,20,flags,method,0,0,crc,cs,us,len(name),0,0,0,0,0,offset)+name
    return bytes(local+central+struct.pack('<IHHHHIIH',0x06054b50,0,0,3,3,len(central),len(local),0))
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("decoder", nargs="?", type=Path, default=Path(__file__).with_name("decoder.py"))
    D=parser.parse_args().decoder
    signal.alarm(8)
    started=time.monotonic();cpu0=sum(resource.getrusage(resource.RUSAGE_SELF)[:2])
    before=D.read_bytes();assert len(before)==10383 and hashlib.sha256(before).hexdigest()==EXPECTED_SHA
    spec=importlib.util.spec_from_file_location('reviewed_decoder',D);d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
    cases=[('valid_deflate',None,False,True),('valid_stored',None,True,True)]
    changes=['trailing_compressed_bytes','truncated_deflate_eof','false_uncompressed_extent','local_crc_mismatch','local_method_mismatch','reserved_flag','descriptor_flag_without_descriptor','nul_name_alias','inter_member_gap','local_flags_mismatch']
    cases += [(x,x,False,False) for x in changes]
    results=[]
    for name,change,stored,expected in cases:
        blob=archive(change,stored)
        assert len(blob)<2048
        row={'case':name,'generated_bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),'expected_acceptance':expected}
        try:
            value=d.describe_sweep(blob)
            row.update(outcome='ACCEPTED',accepted=True,time_count=value['channels']['time']['count'],time_first_hex=value['channels']['time']['first_hex'])
        except d.Refusal as e:row.update(outcome='REFUSED',accepted=False,reason=str(e))
        except Exception as e:row.update(outcome='UNEXPECTED_EXCEPTION',accepted=False,exception_type=type(e).__name__,reason=str(e))
        row['matches_expected']=row['accepted']==expected and row['outcome']!='UNEXPECTED_EXCEPTION'
        results.append(row)
    after=D.read_bytes();assert before==after
    out={'schema':'voltron-independent-generated-inner-zip-inquiry-v1','status':'DEFECTS_CONFIRMED' if any(not x['matches_expected'] for x in results) else 'ALL_CASES_MATCH_EXPECTED','decoder_source':{'path':str(D),'bytes':len(before),'sha256':EXPECTED_SHA},'cases':results,'mismatch_count':sum(not x['matches_expected'] for x in results),'source_unchanged':True,'authentic_array_reads':0,'network_requests':0,'source_file_read_bytes':len(before)+len(after),'CPU_seconds':sum(resource.getrusage(resource.RUSAGE_SELF)[:2])-cpu0,'wall_seconds':time.monotonic()-started,'ru_maxrss_platform_units':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    print(json.dumps(out,indent=2,sort_keys=True))
    if out["mismatch_count"]:
        raise AssertionError("generated inner-ZIP cases disagree with the reviewed acceptance policy")
if __name__=='__main__':main()
