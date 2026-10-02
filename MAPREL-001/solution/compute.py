"""Independent MAPREL oracle authoring entrypoint; import-safe, no fetches.

Defaults retain original/seed0/1000; all three public methods and 100..4096
counts are available. Parsing and manual assignment are separate from grading;
the documented NumPy/SciPy numerical conventions remain shared dependencies.
"""
import argparse
import csv
import importlib.metadata
import json
import os
from pathlib import Path
import warnings

import numpy as np

import oracle_core as core
import source_reader as source

FILES = ('parcels.csv','spin_evidence.npz','results.json','run_metadata.json','findings.md')
ARRAYS = ('parcel_ids','rotation_ids','centroids','hemisphere','spin_parcel_ids')
FIELDS = ('parcel_id','label','network','hemisphere','n_vertices','support_sha256','gradient2','thickness')


def disjoint(left,right):
    return left != right and left not in right.parents and right not in left.parents


def destinations(args):
    output=source.safe_path(args.output_dir);private=source.safe_path(args.private_dir)
    core.need(disjoint(output,private),'separate output/private paths')
    code=Path(__file__).absolute().parent
    if (code.parent/'task.toml').is_file():code=code.parent
    protected=[code,*[source.safe_path(getattr(args,key)) for key in
                     ('data_dir','manifest_path','method_path','schema_path')]]
    for path in (output,private):
        core.need(path != Path('/') and all(disjoint(path,p) for p in protected),'output/input or code overlap')
        core.need(not os.path.lexists(path),'fresh exclusive output/private path')
        core.need(path.parent.is_dir(),'existing output parent required')
    # All guards precede either creation. No overwrite, cleanup or retry.
    output.mkdir(exist_ok=False);private.mkdir(exist_ok=False)
    return output,private


def write_json(path,document):
    text=json.dumps(document,sort_keys=True,indent=2,allow_nan=False)+'\n'
    with path.open('x',encoding='utf-8') as handle:handle.write(text)


def write_npz(path,arrays):
    with path.open('xb') as handle:np.savez_compressed(handle,**arrays)


def software():
    return {name:importlib.metadata.version(name) for name in ('numpy','scipy','nibabel','neuromaps')}


def parcel_rows(basis):
    for i,pid in enumerate(basis['parcel_ids']):
        yield dict(parcel_id=int(pid),label=basis['labels'][i],network=basis['networks'][i],
                   hemisphere='L' if basis['hemisphere'][i] == 0 else 'R',
                   n_vertices=int(basis['support_n'][i]),support_sha256=basis['support_sha256'][i],
                   gradient2=float(basis['maps'][i,0]),thickness=float(basis['maps'][i,1]))


def findings(result):
    observed='undefined' if result['pearson_r'] is None else format(result['pearson_r'],'.12g')
    p='undefined' if result['p_spin'] is None else format(result['p_spin'],'.12g')
    return (f"Signed parcel-map Pearson r: {observed}. Conditional centroid-spin p: {p}.\n\n"
            f"Method {result['spin_method']}, seed {result['seed']}, {result['n_permutations']} retained slots; "
            f"{result['n_null_defined']} defined null correlations. Inference status: {result['inference_status']}.\n\n"
            "This is a fixed published group-map method application, not a participant-level replication. "
            "The published gradient sign is retained. Centroid assignment approximates spatial structure; "
            "the conditional result does not establish causation, absence of association, universal null "
            "calibration, or benchmark difficulty. No parcel or rotation is removed according to its effect.\n")


def run(args):
    method,seed,count=core.configuration(args.spin_method,args.seed,args.n_permutations)
    output,private=destinations(args)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            versions=software()
            core.need(all(versions[name]==version for name,version in
                          dict(numpy='2.2.6',scipy='1.17.0',neuromaps='0.0.7').items()),
                      'public numerical versions required for oracle')
            basis=source.load_sources(args.data_dir,args.manifest_path,args.method_path,args.schema_path)
            ids=core.integers(basis['parcel_ids'])
            core.need(np.array_equal(ids,np.arange(1,401)) and basis['maps'].shape==(400,2),
                      'complete canonical 400-parcel basis')
            # Preserve primitives before spin generation and any downstream failure.
            write_npz(private/'source_primitives.npz',dict(parcel_ids=ids,maps=basis['maps'],
                      centroids=basis['centroids'],hemisphere=basis['hemisphere'],support_n=basis['support_n']))
            write_json(private/'source_identity.json',dict(pins=basis['pins'],source_files=basis['source_files'],
                                                         source_observed=basis['source_observed']))
            spins=core.generate_spins(basis['centroids'],basis['hemisphere'],ids,
                                      method=method,seed=seed,count=count)
            write_npz(private/'spin_diagnostics.npz',{key:spins[key] for key in
                      ('attempts','retained_duplicate','assignment_cost')})
            maps=basis['maps']
            support=core.source_fidelity(maps[:,0],maps[:,1],maps[:,0],maps[:,1],ids,spins['spin_parcel_ids'])
            derived=core.derive(maps[:,0],maps[:,1],ids,spins['spin_parcel_ids'],spins['rotation_ids'],support)
            result=dict(schema_version='maprel-results-v2',status='complete',n_parcels=400,
                        null_family='centroid_spin',spin_method=method,seed=seed,n_permutations=count,**derived)
            with (output/'parcels.csv').open('x',encoding='utf-8',newline='') as handle:
                writer=csv.DictWriter(handle,fieldnames=FIELDS);writer.writeheader();writer.writerows(parcel_rows(basis))
            write_npz(output/'spin_evidence.npz',{key:spins[key] for key in ARRAYS})
            write_json(output/'results.json',result)
            with (output/'findings.md').open('x',encoding='utf-8') as handle:handle.write(findings(result))
        warning_strings=[str(item.message) for item in caught]
        metadata=dict(schema_version='maprel-metadata-v2',task_id='MAPREL-001',status='ok',**basis['pins'],
                      source_files=basis['source_files'],source_observed=basis['source_observed'],
                      analysis_observed=dict(map_support=[dict(map_id='gradient2',active=support['gradient']),
                                                         dict(map_id='thickness',active=support['thickness'])],
                                             remapped_gradient=dict(n_expected=count,n_active=int(support['null_gradient'].sum()))),
                      software_versions=versions,warnings=warning_strings)
        write_json(output/'run_metadata.json',metadata)
        report=dict(status='complete',n_parcels=400,n_permutations=count,spin_method=method,seed=seed,
                    inference_status=result['inference_status'],n_null_defined=result['n_null_defined'],
                    warnings=warning_strings,artifacts=list(FILES))
        write_json(private/'report.json',report)
        return report
    except Exception as exc:
        # A late failure must invalidate even a previously written success marker.
        failure=dict(status='failed',type=type(exc).__name__,reason=str(exc))
        for root in (output,private):
            if not os.path.lexists(root/'failure_report.json'):write_json(root/'failure_report.json',failure)
        raise


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir',default=os.environ.get('DATA_DIR','/app/data/maprel'))
    p.add_argument('--manifest-path',default=os.environ.get('SOURCE_MANIFEST','/app/source_manifest.json'))
    p.add_argument('--method-path',default=os.environ.get('METHOD_CONTRACT','/app/method_contract.json'))
    p.add_argument('--schema-path',default=os.environ.get('OUTPUT_SCHEMA','/app/output_schema.json'))
    p.add_argument('--output-dir',default=os.environ.get('OUTPUT_DIR','/app/output'))
    p.add_argument('--private-dir',default=os.environ.get('PRIVATE_DIR','/tmp/maprel-oracle-private'))
    p.add_argument('--spin-method',choices=core.METHODS,default='original')
    p.add_argument('--seed',type=int,default=0)
    p.add_argument('--n-permutations',type=int,default=1000)
    p.add_argument('--print-contract',action='store_true')
    return p


def main():
    args=parser().parse_args()
    if args.print_contract:
        print(json.dumps(dict(task_id='MAPREL-001',source_manifest_sha256=source.SOURCE_SHA,
                             method_contract_sha256=source.METHOD_SHA,output_schema_sha256=source.SCHEMA_SHA,
                             methods=list(core.METHODS),default_method='original',default_seed=0,
                             default_n=1000,min_n=100,max_n=4096,artifacts=list(FILES)),sort_keys=True))
    else:print(json.dumps(run(args),sort_keys=True,allow_nan=False))


if __name__=='__main__':main()
