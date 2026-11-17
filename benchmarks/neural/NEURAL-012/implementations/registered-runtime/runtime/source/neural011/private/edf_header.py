"""Validate a captured fixed EDF header; excludes every clinical/auxiliary field."""
import math,re
from io_contract import need
from scientific_contract import edge_mapping
EEG=re.compile(r'^(?:FP|AF|F|FC|FT|C|CP|T|P|PO|O)(?:[0-9]{1,2}|Z)$')
def inspect_header(body,source_bytes,release_eeg_labels):
 need(type(release_eeg_labels)is list and release_eeg_labels and all(type(x)is str and EEG.fullmatch(x) for x in release_eeg_labels) and len(release_eeg_labels)==len(set(release_eeg_labels)),'explicit unique release-listed EEG names; no label-regex substitute for publisher whitelist')
 need(len(body)>=256,'full fixed header');text=lambda a,b:body[a:b].decode('ascii').strip()
 need(text(0,8)=='0','EDF not BDF');n=int(text(252,256));hb=int(text(184,192));records=int(text(236,244));seconds=float(text(244,252))
 need(0<n<=512 and hb==len(body)==256*(n+1) and records>0 and math.isfinite(seconds) and seconds>0,'header geometry')
 need(text(192,236)=='' or text(192,236).startswith('EDF+C'),'continuous EDF only')
 fields={};offset=256
 for name,width in [('label',16),('transducer',80),('unit',8),('pmin',8),('pmax',8),('dmin',8),('dmax',8),('prefilter',80),('samples',8),('reserved',32)]:
  fields[name]=[body[offset+i*width:offset+(i+1)*width].decode('ascii').strip() for i in range(n)];offset+=width*n
 counts=[int(x) for x in fields['samples']];need(all(x>0 for x in counts),'positive source sample counts');duration=records*seconds
 need(duration.is_integer() and 0<duration<=86400 and source_bytes==hb+2*records*sum(counts),'complete source extent and one-day domain')
 selected=[];excluded=[]
 for i,label in enumerate(fields['label']):
  normalized=label[4:].upper() if label.startswith('EEG ') else ''
  if not EEG.fullmatch(normalized):excluded.append({'source_index':i,'label':label,'reason':'not_an_EEG_electrode'});continue
  if normalized not in release_eeg_labels:excluded.append({'source_index':i,'label':label,'reason':'not_in_release_EEG_whitelist'});continue
  pmin,pmax=map(float,(fields['pmin'][i],fields['pmax'][i]));dmin,dmax=map(int,(fields['dmin'][i],fields['dmax'][i]));factor={'uV':1.,'mV':1000.,'V':1000000.}.get(fields['unit'][i])
  need(counts[i]/seconds==512 and factor is not None and all(math.isfinite(v) for v in (pmin,pmax)) and pmin<pmax and -32768<=dmin<dmax<=32767,'valid512Hz physical EEG')
  scale=(pmax-pmin)/(dmax-dmin)*factor;bias=pmin*factor-dmin*scale
  need(math.isfinite(scale) and math.isfinite(bias) and scale>0,'finite calibration')
  need(normalized not in [x['label'] for x in selected],'ambiguous duplicate electrode')
  selected.append({'source_index':i,'label':normalized,'scale_to_microvolts':scale,'offset_microvolts':bias,'prefilter':fields['prefilter'][i]})
 need({x['label'] for x in selected}==set(release_eeg_labels),'every release-listed EEG electrode maps exactly once by name')
 edge_mapping([x['label'] for x in selected],'Siena')
 return {'header_bytes':hb,'source_channels':n,'records':records,'record_seconds':seconds,'samples_per_source_record':counts,'duration_seconds':int(duration),'sample_rate_hz':512,'selected_channels':selected,'excluded_channels':excluded,'release_eeg_labels':release_eeg_labels,'registration_clock':text(176,184),'registration_date':text(168,176)}
