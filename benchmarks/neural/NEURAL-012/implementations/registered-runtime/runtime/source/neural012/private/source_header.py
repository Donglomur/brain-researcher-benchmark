"""Parse an owned original EDF header, without opening any data source."""
import math
from scientific_contract import need, EEG, edge_mapping

def inspect_header(body, source_bytes, cohort, release_eeg_labels):
    need(type(body) is bytes and len(body) >= 256, 'owned complete header bytes')
    need(type(source_bytes) is int and source_bytes > len(body), 'original full extent')
    need(cohort in ('CHB', 'Siena'), 'known original cohort')
    need(type(release_eeg_labels) is list, 'explicit whitelist')
    if cohort == 'CHB':
        need(release_eeg_labels == [], 'CHB measured-edge selection')
    else:
        need(release_eeg_labels and len(set(release_eeg_labels)) == len(release_eeg_labels)
             and all(type(x) is str and EEG.fullmatch(x) for x in release_eeg_labels), 'Siena release whitelist')
    text = lambda a, b: body[a:b].decode('ascii').strip()
    need(text(0, 8) == '0', 'EDF version zero')
    n, hb, records, seconds = int(text(252, 256)), int(text(184, 192)), int(text(236, 244)), float(text(244, 252))
    need(0 < n <= 512 and hb == len(body) == 256 * (n + 1) and records > 0
         and math.isfinite(seconds) and seconds > 0, 'full original EDF geometry')
    need(text(192, 236) == '' or text(192, 236).startswith('EDF+C'), 'continuous original EDF')
    fields = {}; offset = 256
    for name, width in [('label',16),('transducer',80),('unit',8),('pmin',8),('pmax',8),
                        ('dmin',8),('dmax',8),('prefilter',80),('samples',8),('reserved',32)]:
        fields[name] = [body[offset+i*width:offset+(i+1)*width].decode('ascii').strip() for i in range(n)]
        offset += n * width
    counts = [int(x) for x in fields['samples']]; duration = records * seconds
    need(all(x > 0 for x in counts) and duration.is_integer() and 0 < duration <= 86400
         and source_bytes == hb + 2 * records * sum(counts), 'complete source duration and sample extent')
    selected = []; excluded = []; occurrences = {}; rate = 256 if cohort == 'CHB' else 512
    for i, original in enumerate(fields['label']):
        label = original
        if cohort == 'Siena':
            label = original[4:].upper() if original.startswith('EEG ') else ''
            valid = bool(EEG.fullmatch(label)) and label in release_eeg_labels
        else:
            parts = label.upper().split('-')
            valid = ((len(parts) == 1 and EEG.fullmatch(parts[0])) or
                     (len(parts) == 2 and EEG.fullmatch(parts[0]) and (EEG.fullmatch(parts[1]) or parts[1] in ('REF','CS2'))))
        if not valid:
            excluded.append({'source_index':i,'label':original,'reason':'outside_selected_EEG_support'}); continue
        factor = {'uV':1., 'mV':1000., 'V':1000000.}.get(fields['unit'][i])
        pmin, pmax = float(fields['pmin'][i]), float(fields['pmax'][i])
        dmin, dmax = int(fields['dmin'][i]), int(fields['dmax'][i])
        need(counts[i] / seconds == rate and factor is not None and math.isfinite(pmin) and math.isfinite(pmax)
             and pmin < pmax and -32768 <= dmin < dmax <= 32767, 'exact selected channel calibration/rate')
        scale = (pmax-pmin)/(dmax-dmin)*factor; bias = pmin*factor-dmin*scale
        need(math.isfinite(scale) and scale > 0 and math.isfinite(bias), 'finite affine calibration')
        occurrences[label] = occurrences.get(label, 0) + 1
        if cohort == 'Siena': need(occurrences[label] == 1, 'unique Siena electrode')
        selected.append({'source_index':i,'label':label,'scale_to_microvolts':scale,'offset_microvolts':bias})
    need(selected, 'whole original EEG selection')
    if cohort == 'Siena': need({x['label'] for x in selected} == set(release_eeg_labels), 'complete publisher-listed electrodes')
    edge_mapping([x['label'] for x in selected], cohort)
    return {'header_bytes':hb,'source_channels':n,'records':records,'record_seconds':seconds,
            'samples_per_source_record':counts,'duration_seconds':int(duration),'sample_rate_hz':rate,
            'selected_channels':selected,'excluded_channels':excluded,'registration_clock':text(176,184),
            'registration_date':text(168,176),'release_eeg_labels':list(release_eeg_labels)}
