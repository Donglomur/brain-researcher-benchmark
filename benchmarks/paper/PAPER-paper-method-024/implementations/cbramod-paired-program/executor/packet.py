"""Explicit complete target-free interchange; never invent native preparation.

Train/validation labels must be independently qualified operator exports. Query
signals must be the accepted observations exporter outputs. The source protocol
does not qualify the original cohorts, transformations, labels or provenance.
"""
from pathlib import Path
import time
import safe_io as safe
import streaming
import operator_api
from engine import pin, read_pinned, write_bytes


def stage(r, host, destination, end):
    root = Path(r['packet_root'])
    raw = read_pinned(root/'PACKET.json', r['packet_pin'], 4_000_000)
    p = safe.strict(raw)
    safe.need(type(p) is dict and set(p) == {'schema', 'task_id', 'query', 'paper', 'datasets'}
              and p['schema'] == 'cbramod_participant_packet_v1' and p['task_id'] == operator_api.TASK,
              'Exact participant interchange packet')
    panel, contract = operator_api.public(host)
    safe.need(type(p['query']) is dict and set(p['query'])=={'path','bytes','sha256'} and
              p['query']['path']=='QUERY.json', 'Closed public query identity before reading')
    query_raw = safe.captured(root, p['query'], 256_000_000)
    q = safe.strict(query_raw); contract.validate_query(q, panel)
    safe.need(p['query']['path'] == 'QUERY.json' and p['paper']['path'] == 'paper.txt' and
              {k:p['paper'][k] for k in ('bytes','sha256')} == panel['paper_text_pin'], 'Exact shared query and paper')
    safe.need(type(p['datasets']) is list and [d['id'] for d in p['datasets']] ==
              [d['id'] for d in q['datasets']], 'Complete original12 dataset order')
    total = len(raw) + len(query_raw)
    safe.need(total <= r['public_bytes_limit'], 'Whole packet budget before staging')
    destination.mkdir(mode=0o755)
    write_bytes(destination/'QUERY.json', query_raw)
    def capture(row, relative):
        nonlocal total
        safe.need(type(row) is dict and set(row) == {'path','bytes','sha256'} and row['path'] == relative,
                  'Closed role-specific public path')
        pin({k:row[k] for k in ('bytes','sha256')}, r['public_bytes_limit'])
        total += row['bytes']; safe.need(total <= r['public_bytes_limit'], 'Whole declared participant packet allowance')
        path = destination/relative; path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        streaming.copy(root/relative, path, row, end, r['public_bytes_limit'])
        return path
    capture(p['paper'], 'paper.txt')
    for d, qr in zip(p['datasets'], q['datasets']):
        safe.need(set(d) == {'id','train','val','test'}, 'Only train/validation labels and target-free test signals')
        for split in ('train','val','test'):
            row=d[split]; base=d['id']+'/'+split
            safe.need(type(row) is dict and set(row) == ({'observations','signals'} if split=='test'
                      else {'observations','signals','labels'}), 'No query label slot or auxiliary public code')
            receipt_path=capture(row['observations'], base+'/OBSERVATIONS.json')
            obs=safe.strict(safe.read(receipt_path, 32_000_000))
            safe.need(set(obs) == {'schema','dataset_id','split','lineage','signal_file','contains_target_labels','source_parity_qualified'}
                      and obs['schema']=='cbramod_target_free_observations_v2' and obs['dataset_id']==d['id']
                      and obs['split']==split and obs['contains_target_labels'] is False,
                      'Accepted target-free observations receipt')
            line=obs['lineage']; expected=host.row_lineage(d['id'],split,line['source_keys'],line['group_by_key'])
            safe.need(line==expected, 'Complete exact official-loader lineage')
            groups=sorted(set(x['group'] for x in line['rows']))
            if split=='test':
                host.query_descriptor(obs, qr, contract.digest(q), base)
            else:
                safe.need(groups==qr['training_groups' if split=='train' else 'validation_groups'], 'Complete declared training/validation groups')
            signal=obs['signal_file']; shape=[len(line['source_keys']), *line['loader_sample_shape']]
            safe.need(set(signal)=={'path','shape','dtype','bytes','sha256','fortran_order'} and signal['path']=='observations.npy'
                      and signal['shape']==shape and signal['dtype']=='<f4' and signal['fortran_order'] is False,
                      'Full native source-shaped observation bank, including20-epoch ISRUC')
            safe.need(row['signals']=={'path':base+'/observations.npy','bytes':signal['bytes'],'sha256':signal['sha256']},
                      'Receipt signal pin joined exactly')
            path=capture(row['signals'],base+'/observations.npy'); streaming.npy_envelope(path,shape,'<f4')
            if split!='test':
                # A separate original-label join/producer must qualify this export.
                path=capture(row['labels'],base+'/labels.npy')
                streaming.npy_envelope(path,[len(line['rows'])],'<f8')
    write_bytes(destination/'PACKET.json',raw)
    return q, {'packet_pin':r['packet_pin'],'bytes':total,'primary_datasets':12,
               'authentic_input_qualification':False,'training_label_export_qualification':False}
