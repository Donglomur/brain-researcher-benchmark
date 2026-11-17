"""Join accepted saved outputs into a fixed-map participant packet.

No authentic inputs were opened during authoring. This entry requires a later
selected offline owner and the exact immutable input/source manifest.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import time
from conditional_kernel import FAMILIES, CONTEXTS, need, reconstruct, rational, validate_packet
from endpoint_cli import decode, json_bytes, read, write

PFC = {'ACA','ILA','MOs','ORB','PL','AI','FRP','ACAd','ACAv','ORBm','ORBvl','ORBl','AId','AIv'}
INPUT_NAMES = {'lineage','linkage','cohort','order','gao_units','data_units','gao_stats','data_stats','hierarchy'}
READER_PIN = (15287,'b4fe488bb302ffb35b10dbae29bd0474bea443a5e6ff784370da4569226d80d7')
SCALAR_PIN = (21133,'dc8fb2d42183fb2393702246c1cb3819be362cebcaaf01a4de3d89863c12446b')


def opaque(kind, value):
    return hashlib.sha256((kind+'\0'+value).encode()).hexdigest()


def source_module(desc, pin):
    raw=read(desc['path'],1048576)
    need((len(raw),hashlib.sha256(raw).hexdigest()) == pin == (desc['bytes'],desc['sha256']), 'accepted reader pin')
    ns={'__name__':'_pfc_bounded_reader','__file__':desc['path']}
    exec(compile(raw,desc['path'],'exec'),ns)
    return ns


def family_labels(row):
    # Captured area already underwent original assign_parentregs. For a PFC
    # unit it is unchanged; non-PFC rows retain that accepted parent-area label.
    pfc=row['roi'] != 0 and row['area'] in PFC
    return pfc, [str(row['roi']),
        str(row['roi'])+'|'+re.sub('[^0-9]','',row['layer']) if pfc else row['area'],
        str(row['roi'])+'|'+('deep' if '5' in row['layer'] or '6' in row['layer'] else 'sup') if pfc else row['area']]


def prepare(selection_path, output_directory):
    import numpy as np
    import h5py
    selection=decode(read(selection_path,1048576))
    need(selection['schema']=='PFC_FULL99_CONDITIONAL_INPUT_SELECTION_V1' and
         set(selection['inputs'])==INPUT_NAMES, 'complete selected saved-input roster')
    reader=source_module(selection['reader'],READER_PIN)
    ledger=reader['Ledger'](256*1024**2,32*1024**2,time.monotonic()+120)
    scalar_raw=reader['exact'](selection['scalar_reader']['path'],selection['scalar_reader'],ledger,1048576)
    need((len(scalar_raw),hashlib.sha256(scalar_raw).hexdigest())==SCALAR_PIN,'accepted scalar reader')
    scalar=reader['scalar_reader'](scalar_raw,np,h5py,ledger)
    raw={k:reader['exact'](v['path'],v,ledger,32*1024**2) for k,v in selection['inputs'].items()}
    parsed={k:decode(b) for k,b in raw.items() if k not in ('gao_stats','data_stats','hierarchy')}
    lineage,linkage,census,order = parsed['lineage'],parsed['linkage'],parsed['cohort'],parsed['order']
    need(len(lineage)==29782 and len(census['rows'])==29782,'complete original source positions')
    by_source={v['source_identity']:v for v in lineage};by_opaque={v['unit_id']:v for v in lineage}
    decisions={v['unit_id']:v for v in census['rows']}
    need(len(by_source)==len(by_opaque)==len(decisions)==29782 and set(by_opaque)==set(decisions),'bijective original lineage/census')
    need(linkage['schema']=='pfc_animal_linkage_v1' and linkage['method']=='recording_to_explicit_source_subject_metadata',
         'witnessed participant linkage, never ID parsing')
    links={v['recid']:v for v in linkage['rows']}
    need(len(links)==len(linkage['rows'])==99,'all99 source recording joins')
    for row in links.values():
        need(row['recid']==row['probe_id'] and row['animal_id']==row['source_subject_value'] and
             row['source_asset_sha256']=='b5c9def32f885c73bb9e19bde81fd3f2e0afd47cae77b8f4ccc7fc7d6b522d2e',
             'accepted explicit participant witness')
    tasks={}
    for row in lineage:
        need(row['recid'] in links and row['native_fit']==decisions[row['unit_id']]['fit'],'complete eligibility/group join')
        wanted='Passive' if row['source_task']=='Opto' else row['source_task']
        need(row['effective_shuffle_task']==wanted and wanted in {'Passive','Aversion','Detection','Context','Attention'},
             'original effective task rule')
        need(row['recid'] not in tasks or tasks[row['recid']]==wanted,'recording task consistency')
        tasks[row['recid']]=wanted
    need(set(tasks)==set(links),'source positions account for every recording')
    scored=[k for k,v in decisions.items() if v['score']]
    scored_animals={links[by_opaque[k]['recid']]['animal_id'] for k in scored}
    need(len(scored)==10243 and len(scored_animals)==65,'accepted scored-PFC population remains distinct')
    fit={v['source_identity'] for v in lineage if v['native_fit']}
    need(len(order)==len(set(order))==19186 and fit==set(order),'exact complete original fitting population')
    routes=[parsed['gao_units'],parsed['data_units']]
    for route in routes:
        need(len(route)==19186 and [v['id'] for v in route]==order,'captured complete original route order')
    for left,right in zip(*routes):
        need(all(left[k]==right[k] for k in ['id','bmu','category','area','layer']),'same frozen map/category and non-ROI attributes')
    for source,row in zip(order,routes[0]):
        need(row['layer']==by_source[source]['source_layer'],'captured layer joins original source lineage')
    label_rows=[];pfc_flags=[]
    for route in routes:
        parsed_labels=[family_labels(v) for v in route]
        for ref in ['refall','refPFC']:
            for encoding in range(3):
                label_rows.append([labels[encoding] if ref=='refall' or ispfc else None for ispfc,labels in parsed_labels])
    families=[{'key':key,'labels':sorted({v for v in values if v is not None})} for key,values in zip(FAMILIES,label_rows)]
    indices=[{s:i for i,s in enumerate(f['labels'])} for f in families]
    units=[]
    for i,source in enumerate(order):
        row=by_source[source];rec=row['recid'];animal=links[rec]['animal_id']
        units.append({'id':row['unit_id'],'recording':opaque('record',rec),'animal':opaque('animal',animal),
                      'task':tasks[rec],'category':routes[0][i]['category'],
                      'labels':[index.get(values[i],-1) for index,values in zip(indices,label_rows)]})
    stats=[reader['hdf_arrays'](raw[name],np,h5py,scalar,ledger)[0] for name in ['gao_stats','data_stats']]
    historical=[]
    for fi,family in enumerate(families):
        route,ref,encoding=family['key'].split('/'); arrays=stats[0 if route=='gaoRois' else 1];prefix='/'+ref+'/'+encoding+'/'
        labels=arrays[prefix+'avals1'];need(labels.ndim==2 and labels.shape[1]==1,'original source string-vector representation')
        decoded=[v[0].decode('utf-8') for v in labels]
        need(decoded==family['labels'] and arrays[prefix+'avals2'].reshape(-1).tolist()==list(range(8)),
             'source lexical/category axes, no lost suffix or category omission')
        historical.append({'counts':arrays[prefix+'matches'].tolist(),'mean':arrays[prefix+'meanshuff'].tolist(),
                           'std':arrays[prefix+'stdshuff'].tolist()})
    hierarchy={}
    for row in list(csv.reader(io.StringIO(raw['hierarchy'].decode('utf-8'))))[1:]:
        roi=int(float(row[0]));value=float(row[1]);need(roi not in hierarchy,'unique hierarchy ROI')
        hierarchy[roi]=value if np.isfinite(value) else 'NaN' if np.isnan(value) else '+Infinity' if value>0 else '-Infinity'
    need(len(hierarchy)==60,'all60 original hierarchy rows')
    contexts=[]
    for key in CONTEXTS:
        route,ref,subset=key.split('/');encoding={'deepRois':'laydepth','nolayRois':'nolays','layeredRois':'lays','deepSupRois':'laydepth'}[subset]
        fi=FAMILIES.index('/'.join((route,ref,encoding)));labels=families[fi]['labels'];support=[sum(r) for r in historical[fi]['counts']]
        selected=[i for i,(label,n) in enumerate(zip(labels,support)) if n>20 and
                  ('|deep' in label if subset=='deepRois' else label!='0' if subset=='nolayRois' else '|' in label)]
        hs=None
        if route=='gaoRois' and subset in ('deepRois','nolayRois'):
            need(all(int(labels[i].split('|')[0]) in hierarchy for i in selected),'complete source hierarchy join')
            hs=[hierarchy[int(labels[i].split('|')[0])] for i in selected]
        contexts.append({'key':key,'family':fi,'indices':selected,'hierarchy':hs})
    historical_public=dict(selection['historical_diagnostics'])
    historical_public['source_comparison_report']={k:selection['historical_diagnostics']['source_comparison_report'][k]
                                                 for k in ['bytes','sha256']}
    packet={'schema':'PFC_FULL99_FIXED_MAP_PACKET_V1','units':units,'families':families,'contexts':contexts,
            'animals':sorted({u['animal'] for u in units}),
            'records':[{'id':opaque('record',r),'animal':opaque('animal',links[r]['animal_id']),'task':tasks[r]} for r in sorted(links)],
            'historical_diagnostics':historical_public}
    validate_packet(packet,expected_units=19186,expected_recordings=99)
    full=reconstruct(packet,tick=ledger.tick)
    diagnostic=[]
    for family,old in zip(full['families'],historical):
        need(family['counts']==old['counts'],'exact full-family count authentication; no reduced support')
        delta_mean=[];delta_sd=[]
        import math
        for mu,var,source_mu,source_sd in zip(family['mean'],family['variance'],old['mean'],old['std']):
            for m,v,sm,ss in zip(mu,var,source_mu,source_sd):
                delta_mean.append(float(rational(m))-sm);delta_sd.append(math.sqrt(float(rational(v)))-ss)
        diagnostic.append({'family':family['key'],'analytic_minus_saved1000_mean':delta_mean,
                           'analytic_minus_saved1000_sd':delta_sd,
                           'interpretation':'different estimators, no equivalence test; ddof0 sample variance expectation is999/1000 of analytic variance'})
    out=Path(output_directory);need(out.is_absolute() and not any(p.is_symlink() for p in out.parents),'ordinary output ancestry');out.mkdir(exist_ok=False)
    public=json_bytes(packet);private=json_bytes({'schema':'PFC_ANALYTIC_VS_SAVED_NULL_DIAGNOSTIC_V1','families':diagnostic,
        'input_pins':selection['inputs'],'fitting_animals':len(packet['animals']),'historical_diagnostics':selection['historical_diagnostics']})
    ledger.reserve_output(len(public)+len(private));write(out/'participant-packet.json',public,16*1024**2)
    write(out/'OWNER_ONLY_SOURCE_NULL_DIAGNOSTIC.json',private,16*1024**2)
    result={'packet_sha256':hashlib.sha256(public).hexdigest(),'packet_bytes':len(public),'owner_diagnostic_bytes':len(private),
            'recordings':99,'units':19186,'fitting_animals':len(packet['animals']),'families':12,'contexts':16,
            'separate_accepted_scored_PFC_units':len(scored),'separate_accepted_scored_PFC_animals':len(scored_animals),
            'managed_read_reservation':ledger.read_reserved,'retention_reserved':ledger.output_reserved,
            'source_moment_comparisons':12,'historical_48_geometry_recomputed':False,'scientific_readiness_delta':0}
    result_body=json_bytes(result);ledger.reserve_output(len(result_body))
    write(out/'PREPARATION_RESULT.json',result_body,1048576)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--selection',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(prepare(args.selection,args.output),sort_keys=True))
