"""Task-specific WB-field projection, with required external clock/animal binding.

The real MAT is unavailable. This mapper is implemented against the author
builder fields and invented fixtures, not certified against any decoded row.
No nominal 0.6-second clock or unobserved animal identity is manufactured.
"""
import argparse
from pathlib import Path
from . import delivery_io as io
from .history import validate_record

SOURCE_PIN = {'bytes':236931813,'sha256':'4fcf5906d95d144ed1d6741cc86f4ef4fd332dec0f52e00ee5f34e8b75fe6d45'}


def mapping(export, binding, source_roster):
    io.exact(export, ['schema','source_pin','rows'])
    io.exact(binding, ['schema','source_pin','records'])
    io.need(export['schema']=='neural047-wb-fields-v1' and binding['schema']=='neural047-clock-animal-v1'
            and export['source_pin']==binding['source_pin']==SOURCE_PIN, 'Exact WT source identity')
    rows=export['rows']; annotations=binding['records']
    io.need(type(rows) is list and 3<=len(rows)<=256 and type(annotations) is list
            and len(rows)==len(annotations), 'Complete all-row source census and clock-binding roster')
    names=[r['Name'] for r in rows]
    io.need(all(type(n) is str and n in source_roster for n in names)
            and len(set(names))==len(names), 'Every WT recording joins exactly one publisher H5 name')
    io.need([r['recording_id'] for r in annotations]==names, 'Exact source order; no missing/extra row')
    records=[]; excluded=[]
    for row,a in zip(rows,annotations):
        io.exact(row,['Name','velocity','reversal_vec','dv','saav_matches'])
        io.exact(a,['recording_id','animal_id','time_seconds','native_frame0','evidence'])
        name=row['Name']; matches=row['saav_matches']
        io.need(type(matches) is list and len(matches)<=1, 'At most one exact SAAV identity; no best-cell selection')
        if not matches:
            excluded.append({'recording_id':name,'reason':'no_exact_SAAV_identity'})
            continue
        io.exact(matches[0],['name','row_index1','trace'])
        io.need(matches[0]['name']=='SAAV' and type(matches[0]['row_index1']) is int
                and matches[0]['row_index1']>0, 'Exact named SAAV source row')
        state=row['reversal_vec']
        io.need(type(state) is list and all(type(x) is int and x in (0,1) for x in state),
                'Original observed reversal vector, not fitted or target-derived events')
        starts=[i for i,x in enumerate(state) if x and (i==0 or state[i-1]==0)]
        ends=[i for i,x in enumerate(state) if x and (i==len(state)-1 or state[i+1]==0)]
        record=dict(recording_id=name,split_group=a['animal_id'],split_unit='animal',source_pin=SOURCE_PIN,
            evidence=a['evidence'],time_seconds=a['time_seconds'],native_frame0=a['native_frame0'],
            velocity=row['velocity'],dv=row['dv'],saav=matches[0]['trace'],reversal_state=state,
            events=[dict(event_id=f'reversal_{i:06d}',onset_index0=start,end_index0=end)
                    for i,(start,end) in enumerate(zip(starts,ends))])
        validate_record(record); records.append(record)
    io.need(len({r['split_group'] for r in records})>=3, 'At least three SAAV-identified independent animals')
    return dict(schema='neural047-normalized-native-v1',source_pin=SOURCE_PIN,
        complete_WT_recording_roster=names,excluded_recordings=excluded,records=records,
        mapping_status='source_implemented_external_clock_identity_binding_required')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mat',type=Path,required=True);p.add_argument('--field-export',type=Path,required=True)
    p.add_argument('--clock-binding',type=Path,required=True);p.add_argument('--inventory',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();out=io.regular(a.output);io.need(not out.exists(),'Fresh output before source reads')
    io.read(a.mat,SOURCE_PIN['bytes'],SOURCE_PIN,retain=False)
    inventory=io.json_file(a.inventory,1000000)
    names={r['name'] for r in inventory['files'] if r['name'].endswith('.h5')}
    v=mapping(io.json_file(a.field_export,64000000),io.json_file(a.clock_binding,32000000),names)
    io.put(out,v,64000000)


if __name__=='__main__': main()
