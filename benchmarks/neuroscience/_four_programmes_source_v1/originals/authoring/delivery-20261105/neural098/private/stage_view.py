"""Copy one explicit A/B view. No model, scientific score or execution control."""
import argparse
import hashlib
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from io_utils import capture,read_json,write_json
from protocol import validate_packet


def stage(root,view,packet_path,packet_sha,output):
    root=Path(root).resolve();output=Path(output)
    if view not in ('A','B'):raise ValueError('A or B only')
    if output.exists() or output.is_symlink() or output.resolve().is_relative_to(root):raise ValueError('fresh view outside operator package')
    spec,_=read_json(root/'private/ACCESS_VIEWS.json')
    packet,actual=read_json(packet_path,expected=packet_sha)
    participants=read_json(root/'public/COHORT.json')[0]['participants']
    validate_packet(packet,participants)
    payloads=[];seen=set();total=0
    def add(target,body):
        nonlocal total
        p=Path(target)
        if p.is_absolute() or '..' in p.parts or target in seen or not p.parts:raise ValueError('safe unique view target')
        total+=len(body)
        if total>32000000:raise ValueError('32 MB captured view cap')
        seen.add(target);payloads.append((target,body))
    for row in spec['files']:
        if row['arm'] not in ('both',view):continue
        source=Path(row['source'])
        if source.parts[0]!='public' or source.is_absolute() or '..' in source.parts:raise ValueError('public source only')
        body,_=capture(root/source,4000000,row['sha256'])
        if len(body)!=row['bytes']:raise ValueError('public source size')
        add(row['target'],body)
    # Re-capture the already verified JSON and bind its digest again; the exact
    # captured bytes used here are the bytes written to the candidate view.
    add('data/packet.json',capture(packet_path,4000000,actual)[0])
    add('data/features.npy',capture(Path(packet_path).with_name('features.npy'),24000128,packet['features_sha256'])[0])
    output.mkdir()
    for target,body in payloads:
        destination=output/target;destination.parent.mkdir(parents=True,exist_ok=True)
        with destination.open('xb') as f:f.write(body)
    write_json(output/'VIEW.json',{'schema':'neural098-view-v1','access_view':view,'packet_sha256':actual,
        'source_files':[{'path':p,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for p,b in payloads],
        'private_benchmark_reference_included':False,'isolation_attested':False})


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--view',choices=['A','B'],required=True);ap.add_argument('--packet',type=Path,required=True);ap.add_argument('--packet-sha256',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    stage(Path(__file__).resolve().parents[1],a.view,a.packet,a.packet_sha256,a.output)
