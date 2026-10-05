"""Authoring-only original-source recomputation; no oracle-imported numbers."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import numpy as np

from independent_source import load_inputs, build_payload
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tests'))
from proof_of_work import load_reference, validate_output_directory, sha256

def build(data_dir, method_contract, destination, outputs):
    inputs = load_inputs(data_dir, method_contract)
    payload, arrays = build_payload(inputs)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Original independent estimates are checked against full genuine outputs;
    # neither oracle CSVs nor the legacy reference supply the bank values.
    for output in outputs:
        validate_output_directory(output,payload)
    with tempfile.NamedTemporaryFile(prefix='.n400-reference-',suffix='.npz',dir=destination.parent,delete=False) as handle:
        temporary = Path(handle.name)
        np.savez_compressed(handle,reference_json=np.asarray(json.dumps(payload,allow_nan=False)),**arrays)
    try:
        load_reference(temporary)
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {'status':'ok','pipeline_id':payload['pipeline_id'],'reference_sha256':sha256(destination),
            'reference_size_bytes':destination.stat().st_size,'n_source_events':len(payload['tables']['source_events.csv']),
            'n_target_events':len(payload['tables']['trial_measurements.csv']),
            'n_subjects':payload['results']['n_subjects'],'checked_outputs':[str(Path(p)) for p in outputs]}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir',default='/app/data/erpcore_n400')
    parser.add_argument('--method-contract',default='/app/method_contract.json')
    parser.add_argument('--reference',type=Path,default=Path(__file__).resolve().parents[1]/'tests/reference.npz')
    parser.add_argument('--output-dir',type=Path,action='append',required=True)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    if args.report and args.report.exists():
        raise FileExistsError('Refusing to overwrite an existing authoring report')
    report=build(args.data_dir,args.method_contract,args.reference,args.output_dir)
    if args.report:
        args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))

if __name__=='__main__':
    main()
