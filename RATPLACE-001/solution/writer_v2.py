"""Fresh-directory oracle writer. Refuses resource-pilot results."""
import csv
import json
import os
from pathlib import Path
import numpy as np
import information_kernel as kernel
import source_io as io

FILES=('spatial_information.csv','spatial_evidence.npz','results.json','run_metadata.json','findings.md')
COLUMNS=('unit_id','n_spikes','mean_rate_hz','raw_bits_per_spike','null_mean_bits_per_spike',
         'shift_adjusted_bits_per_spike','p_upper','status')

def disjoint(destination,protected):
    for item in protected:
        p=io.safe_path(item)
        io.need(destination!=p and p not in destination.parents and destination not in p.parents,'protected_overlap')

def fresh_output(output,protected=()):
    destination=io.safe_path(output);disjoint(destination,protected)
    io.need(not os.path.lexists(destination),'output_exists')
    destination.mkdir(parents=True,exist_ok=False)
    return destination

def json_write(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')

def write(reference,output,*,protected=()):
    io.need(reference['status']=='complete','pilot_not_production')
    root=fresh_output(output,protected)
    try:
        a=reference['arrays']
        rows=kernel.replay(a['occupancy_seconds'],a['raw_counts'],a['shifted_counts'],a['unit_ids'])
        with (root/'spatial_evidence.npz').open('xb') as f:np.savez_compressed(f,**a)
        with (root/'spatial_information.csv').open('x',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=COLUMNS);w.writeheader();w.writerows(rows)
        results=kernel.summarize(rows);json_write(root/'results.json',results)
        json_write(root/'run_metadata.json',dict(schema_version='ratplace-output-v2',task_id='RATPLACE-001',
            status=results['status'],pins=reference['pins'],source_observed=reference['source_observed'],
            all_units=reference['all_units'],analysis=reference['analysis']))
        with (root/'findings.md').open('x',encoding='utf-8') as report:report.write(
            '# Mouse CA1 normalized-position methods case\n\n'
            'This single-session camera-window analysis uses a coarse dimensionless 4-by-5 grid. '
            'The source physical-unit conflict is retained, not resolved through arena or firing expectations. '
            'No running filter, source maze-epoch claim, rat/spaceflight comparison, or biological place-cell '
            'classification is made. The elapsed-time-shift comparison conditions on this observation window; '
            'negative adjusted information and undefined null cases remain valid outcomes. '
            'See the numeric receipts for the computed equal-unit summaries.\n')
        return root
    except BaseException as error:
        json_write(root/'failure_report.json',{'status':'failed_precondition','error_type':type(error).__name__})
        raise

def run(data_dir='/app/data/ratplace',documents='/app',output='/app/output'):
    import source_reader
    # /app/output may be below the public-doc directory; protect exact documents, not all /app.
    protected=(data_dir,*(io.safe_path(documents)/n for n in io.FILENAMES),Path(__file__).parent)
    destination=io.safe_path(output);disjoint(destination,protected)
    io.need(not os.path.lexists(destination),'output_exists')
    try:
        reference=source_reader.reconstruct(data_dir,documents)
        root=write(reference,output,protected=protected)
        io.recheck(io.authenticate(data_dir,documents))
        return root
    except BaseException as error:
        if not os.path.lexists(destination):destination.mkdir(parents=True,exist_ok=False)
        if destination.is_dir() and not os.path.lexists(destination/'failure_report.json'):
            json_write(destination/'failure_report.json',{'status':'failed_precondition','error_type':type(error).__name__})
        raise
