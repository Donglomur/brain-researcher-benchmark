"""Offline publisher-MD5 verification and full selected-member extraction. No network."""
import argparse,csv,hashlib,io,json,sys,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from delivery_io import need,json_file,put,fresh,pin
from array_io import capture


def provision(archives,output):
    acquisition=json_file(Path(__file__).with_name('ACQUISITION.json'),500000)
    out=fresh(output);records={}
    selected={a:{r['member']:r for r in acquisition['selected_members'] if r['archive']==a} for a in ['data_processed.zip','DNN.zip']}
    files={r['key']:r for r in acquisition['whole_archives']}
    for name in ['data_processed.zip','DNN.zip','transcription.zip']:
        meta=files[name];raw=capture(Path(archives)/name,meta['size'])
        need(len(raw)==meta['size'] and hashlib.md5(raw).hexdigest()==meta['checksum'].split(':')[-1],'Publisher whole archive identity')
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            need(len(z.namelist())==len(set(z.namelist())),'Unique archive paths')
            names=list(selected[name]) if name in selected else [f'transcription/cleaned/{s}.csv' for s in __import__('protocol').SESSIONS]
            for member in names:
                m=z.getinfo(member);need(m.file_size<=100000000 and not m.is_dir(),'Bounded selected member')
                body=z.read(member) # zipfile checks CRC; full archive MD5 verified first.
                if name in selected:
                    r=selected[name][member];need(len(body)==r['bytes'] and f'{m.CRC:08x}'==r['crc32'],'Selected census identity')
                target=out/member;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body);target.chmod(0o444)
                records[member]={'path':member,**pin(body),'archive':name,'archive_publisher_md5':meta['checksum']}
    put(out/'SELECTION.json',{'schema':'language_selected_v1','files':records},1000000)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--archives',required=True);a.add_argument('--output',required=True);v=a.parse_args();provision(v.archives,v.output)
