"""Trusted independently executed per-session empirical-core reference."""
import argparse,importlib.util,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--case',required=True);p.add_argument('--output',required=True);a=p.parse_args();case=json.loads(Path(a.case).read_text());s=case['session'];g=case['native_geometry']
    sys.path[:0]=[str(HERE/'native-source/operator'),str(HERE/'native-source/public'),str(HERE/'native-source/public/author_code')]
    import reference,protocol
    from panels import load_panels,geometry
    from provision import inspect_file,decoded_fields
    import torch
    path=Path(a.input);asset=case['asset'];record=inspect_file(path,asset,case['expanded_ceiling_bytes'],decoded_fields(s['modality']));protocol.need(record['sha256']==g['input_sha256'],'exactoriginalnativeinput')
    protocol.need(path.name==s['file'],'originalfilename');f2,f3,x,y=load_panels(path.parent,s,case['array_ceiling_bytes']);protocol.need(geometry(s,record['sha256'],f2,f3,x,y)==g,'complete native geometry')
    result=reference.analyze(s,f2,f3,x,y,torch.device(case['device']));design={'schema':'critical_init_design_v1','source_revision':protocol.REVISION,'records':[g]};value={'schema':'critical_init_result_v1','design_sha256':case['design_sha256'],'records':[result]};protocol.validate_result(value,design,case['design_sha256'],[s]);raw=(json.dumps(result,separators=(',',':'),allow_nan=False)+'\n').encode();protocol.need(len(raw)<=protocol.MAX_BYTES,'bounded native record')
    with open(a.output,'xb') as f:f.write(raw)
if __name__=='__main__':main()
