"""Generated native-format controls; no authentic source or model execution."""
import csv
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import struct
import tempfile
import unittest
from unittest import mock
import warnings
import zipfile

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('abr_native_inputs',HERE.parent/'native_inputs.py')
native=importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def table(header,rows):
 stream=io.StringIO(newline='');writer=csv.writer(stream,lineterminator='\n')
 writer.writerow(header);writer.writerows(rows);return stream.getvalue().encode()


def target_csv(frequencies=(100,),repeat=False):
 header=['Freq(Hz)','Level(dB)']+[str(i) for i in range(1953)]
 samples=['0']*1953;samples[0]='1.25';samples[1]='-2.5';samples[-1]='3.75'
 rows=[[str(f),'95']+samples for f in frequencies]
 if repeat:rows.append(['100','95']+['0']*1953)
 return table(header,rows)


def manor_csv(**changes):
 header=['Freq(Hz)','Level(dB)','Samp. Per.','No. Samps.','O.S. Time','Data(uv)...','','..........()','..........()']+[str(i) for i in range(244)]+['']
 row=['4000','70','40.96','244','1.5','','','unused-one','unused-two']+[str(i/4) for i in range(244)]+['']
 for name,value in changes.items():row[header.index(name)]=value
 return table(header,[row])


def cfts(**changes):
 values={'frequency':'45.20','sample':'40','threshold':'80.0','ear':'R','levels':'70;75;80;'};values.update(changes)
 return (':RUN-6\tLEVEL SWEEP\tTEMP:31.34\n'
  f":SW EAR: {values['ear']}\tSW FREQ: {values['frequency']}\t# AVERAGES: 512\tSAMPLE (µsec): {values['sample']}\n"
  f":Threshold: {values['threshold']}\tITI (ms):28.64\n"
  ':CFTS Version: V2.37.1 (R3164)\n'
  f":LEVELS:{values['levels']}\n:DATA\n1 -2 3\n4 -5 6\n7 -8 9\n").encode('latin1')


def threshold_csv(ids=range(1,105),special100=True):
 header=['Mouse ID','Click']+[f'{f//1000} kHz' for f in native.TONES]+['Age','Sex']
 return table(header,[[str(i), '100' if special100 and i==1 else '40']+['45']*8+['30','F'] for i in ids])


def write_zip(path,members):
 with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as out:
  for name,body in members:out.writestr(name,body)
 return {'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'members':len(members),'expanded':sum(len(body) for _,body in members)}


def load_jsonl(path):
 with gzip.open(path,'rt') as stream:return [json.loads(line) for line in stream]


def generated_sources(root,missing_case=False,duplicate_wave1=False):
 paths={};pins={}
 groups={'manor':[('Manor_Lab_Cleaned/generated_tone.csv',manor_csv())],
  'liberman':[('Liberman_Data_ForUpload/WPZ001/ABR-001-L-45.2.tsv',cfts())],
  'marcotti':[('thresholds.csv',threshold_csv())]}
 for i in range(1,105):
  frequencies=(100,)+native.TONES
  if missing_case and i==104:frequencies=frequencies[:-1]
  groups['marcotti'].append((f'Mouse ABRs/{i}.csv',target_csv(frequencies,repeat=i==1)))
  wave1_id='001' if duplicate_wave1 and i==104 else str(i)
  groups['marcotti'].append((f'Wave 1 analysis/{wave1_id}.csv',b'Freq(Hz),Level(dB),P1\n100,95,0.5\n'))
 for lab,members in groups.items():
  paths[lab]=root/(lab+'.zip');pins[lab]=write_zip(paths[lab],members)
  pins[lab].update({'tables':len(members),'traces':1 if lab=='manor' else 3 if lab=='liberman' else 937-int(missing_case),'release':'generated_control','filename':paths[lab].name})
 return paths,pins


class NativeFormats(unittest.TestCase):
 def test_manor_unused_duplicate_headers_and_exact_timebase(self):
  [trace]=native.parse_wave_csv(manor_csv(),'manor')
  self.assertEqual(trace['samples'],[i/4 for i in range(244)])
  self.assertEqual(trace['axis']['unit'],'uV')
  self.assertAlmostEqual(trace['axis']['step_ms'],0.04096,places=12)
  self.assertEqual(trace['axis']['first_sample_ms'],1.5)
  self.assertAlmostEqual(243*trace['axis']['step_ms'],9.95328,places=10)
  self.assertNotEqual(243*trace['axis']['step_ms'],10)
  self.assertEqual([v['value'] for v in trace['private_metadata'] if v['name']=='..........()'],['unused-one','unused-two'])

 def test_duplicate_or_missing_signal_column_is_rejected(self):
  body=manor_csv().decode();header,rest=body.split('\n',1)
  fields=next(csv.reader([header]));fields[fields.index('243')]='242'
  changed=(','.join(fields)+'\n'+rest).encode()
  with self.assertRaisesRegex(native.SourceError,'sample indices'):list(native.parse_wave_csv(changed,'manor'))

 def test_nonfinite_waveform_and_declared_sample_mismatch(self):
  with self.assertRaisesRegex(native.SourceError,'declared sample'):list(native.parse_wave_csv(manor_csv(**{'No. Samps.':'245'}),'manor'))
  body=manor_csv().decode();rows=list(csv.reader(io.StringIO(body)));rows[1][rows[0].index('0')]='NaN'
  with self.assertRaisesRegex(native.SourceError,'nonfinite waveform'):list(native.parse_wave_csv(table(rows[0],rows[1:]),'manor'))

 def test_manor_required_metadata_duplicates_are_rejected(self):
  body=manor_csv().decode();rows=list(csv.reader(io.StringIO(body)))
  rows[0].insert(0,'Freq(Hz)');rows[1].insert(0,'4000')
  with self.assertRaisesRegex(native.SourceError,'duplicate required'):list(native.parse_wave_csv(table(rows[0],rows[1:]),'manor'))

 def test_cfts_segmented_headers_preserve_columns_and_no_assumed_units(self):
  traces=list(native.parse_cfts(cfts()))
  self.assertEqual([x['level_db'] for x in traces],[70,75,80])
  self.assertEqual([x['samples'] for x in traces],[[1,4,7],[-2,-5,-8],[3,6,9]])
  self.assertEqual(traces[0]['stimulus'],{'kind':'tone','frequency_hz':45200})
  self.assertEqual(traces[0]['axis']['kind'],'sample_index')
  self.assertIsNone(traces[0]['axis']['sample_period_ms'])
  self.assertNotIn('step_ms',traces[0]['axis'])
  self.assertEqual(traces[0]['axis']['header_sample_period_ms'],0.04)
  self.assertEqual(traces[0]['axis']['physical_layout'],'unresolved_continuous_or_concatenated')
  self.assertIsNone(traces[0]['axis']['first_sample_ms'])
  self.assertIsNone(traces[0]['axis']['unit'])
  self.assertEqual(traces[0]['private_metadata']['ear_header'],'R')
  self.assertEqual(traces[0]['private_metadata']['threshold_raw'],'80.0')
  self.assertNotIn('threshold_raw',{k:v for k,v in traces[0].items() if k!='private_metadata'})

 def test_cfts_all426_stored_values_survive_without_physical_remapping(self):
  header=cfts().split(b':DATA\n',1)[0]+b':DATA\n'
  # Distinct values on each side of the potential 213+213 boundary expose a
  # crop, split, interpolation or accidental averaging without authentic data.
  matrix=[[i,1000+i,-2000-i] for i in range(426)]
  body=header+''.join(' '.join(map(str,row))+'\n' for row in matrix).encode()
  traces=list(native.parse_cfts(body))
  self.assertEqual([trace['samples'] for trace in traces],[[row[j] for row in matrix] for j in range(3)])
  for trace in traces:
   self.assertEqual(len(trace['samples']),426)
   self.assertEqual(trace['axis']['kind'],'sample_index')
   self.assertIsNone(trace['axis']['sample_period_ms'])
   self.assertNotIn('step_ms',trace['axis'])
   self.assertEqual(trace['axis']['header_sample_period_ms'],0.04)
   self.assertIn('stored-row continuity',trace['axis']['reason'])

 def test_cfts_support_axis_survives_bundle_serialization(self):
  traces=list(native.parse_cfts(cfts()))
  with tempfile.TemporaryDirectory(dir=HERE) as d:
   root=Path(d)/'bundle';bundle=native.Bundle(root,b'g'*32)
   try:
    for trace in traces:
     bundle.json('observations/support/liberman/index.jsonl.gz',{'axis':trace['axis'],'sample_count':len(trace['samples'])})
   finally:bundle.close()
   rows=load_jsonl(root/'observations/support/liberman/index.jsonl.gz')
   self.assertEqual(rows,[{'axis':trace['axis'],'sample_count':3} for trace in traces])
   self.assertTrue(all(row['axis']['kind']=='sample_index' and row['axis']['sample_period_ms'] is None for row in rows))
   self.assertTrue(all('step_ms' not in row['axis'] and row['axis']['header_sample_period_ms']==0.04 for row in rows))

 def test_cfts_width_duplicate_header_and_period_failures(self):
  with self.assertRaisesRegex(native.SourceError,'width mismatch'):list(native.parse_cfts(cfts(levels='70;75;')))
  with self.assertRaisesRegex(native.SourceError,'sample period'):list(native.parse_cfts(cfts(sample='0')))
  body=cfts().replace(b':DATA',b':SW FREQ: 8\n:DATA')
  with self.assertRaisesRegex(native.SourceError,'duplicate CFTS'):list(native.parse_cfts(body))

 def test_target_all_samples_and_click_only_for_target_source(self):
  traces=list(native.parse_wave_csv(target_csv((100,3000),repeat=True),'marcotti'))
  self.assertEqual(len(traces),3)
  self.assertEqual([x['stimulus']['kind'] for x in traces],['click','tone','click'])
  self.assertEqual(traces[0]['samples'][0:2],[1.25,-2.5]);self.assertEqual(traces[0]['samples'][-1],3.75)
  self.assertEqual(len(traces[0]['samples']),1953)
  self.assertEqual(traces[0]['axis']['kind'],'sample_index')
  self.assertIsNone(traces[0]['axis']['unit'])
  self.assertEqual(native.stimulus(100),{'kind':'tone','frequency_hz':100})
  with self.assertRaisesRegex(native.SourceError,'unknown target frequency'):list(native.parse_wave_csv(target_csv((200,)),'marcotti'))

 def test_thresholds_complete_roster_and_no_sentinel_inference(self):
  annotations=native.parse_thresholds(threshold_csv())
  self.assertEqual(set(annotations),set(range(1,105)))
  value=annotations[1]['annotations'][0]
  self.assertEqual(value['source_numeric_value'],100)
  self.assertEqual(value['semantics'],'unresolved_exact_or_censored')
  self.assertEqual(value['stimulus'],{'kind':'click'})
  with self.assertRaisesRegex(native.SourceError,'all104'):native.parse_thresholds(threshold_csv(range(1,104)))
  with self.assertRaisesRegex(native.SourceError,'duplicate'):native.parse_thresholds(threshold_csv(list(range(1,105))+[1]))

 def test_target_id_keeps_all_declared_animals_without_training_exclusions(self):
  self.assertEqual([native.target_id(f'Mouse ABRs/{i}.csv') for i in [17,48,55,71,74,80,81,91,100,103]],[17,48,55,71,74,80,81,91,100,103])
  self.assertEqual(native.target_id('Mouse ABRs/001.csv'),1)
  with self.assertRaisesRegex(native.SourceError,'outside release'):native.target_id('Mouse ABRs/105.csv')
  with self.assertRaisesRegex(native.SourceError,'unrecognized'):native.target_id('Elsewhere/1.csv')


class ArchiveAndBundle(unittest.TestCase):
 def test_unsafe_path_symlink_duplicates_and_denominators(self):
  for name in ['../escape','/absolute','a\\b']:
   with self.subTest(name=name),tempfile.TemporaryDirectory(dir=HERE) as d:
    p=Path(d)/'x.zip';pin=write_zip(p,[(name,b'1')])
    with zipfile.ZipFile(p) as z, self.assertRaisesRegex(native.SourceError,'unsafe'):native.safe_members(z,pin)
  with tempfile.TemporaryDirectory(dir=HERE) as d:
   p=Path(d)/'x.zip';info=zipfile.ZipInfo('link');info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16
   with zipfile.ZipFile(p,'w') as z:z.writestr(info,'target')
   with zipfile.ZipFile(p) as z,self.assertRaisesRegex(native.SourceError,'symlink'):native.safe_members(z,{'members':1,'expanded':6})
   with zipfile.ZipFile(p) as z,self.assertRaisesRegex(native.SourceError,'denominator'):native.safe_members(z,{'members':2,'expanded':6})

 def test_duplicate_zip_members_are_rejected(self):
  with tempfile.TemporaryDirectory(dir=HERE) as d:
   p=Path(d)/'duplicates.zip'
   with warnings.catch_warnings():
    warnings.simplefilter('ignore',UserWarning)
    pin=write_zip(p,[('same.csv',b'1'),('same.csv',b'2')])
   with zipfile.ZipFile(p) as z,self.assertRaisesRegex(native.SourceError,'duplicate ZIP member'):native.safe_members(z,pin)

 def test_wrong_source_hash_fails_before_output_creation(self):
  with tempfile.TemporaryDirectory(dir=HERE) as d:
   root=Path(d);source=root/'not-source.zip';source.write_bytes(b'wrong')
   with self.assertRaisesRegex(native.SourceError,'hash mismatch'):native.prepare({k:source for k in native.PINS},root/'bundle',b'k'*32)
   self.assertFalse((root/'bundle').exists())

 def test_archive_path_replacement_cannot_change_consumed_members(self):
  # Tiny ZIPs exercise the real prepare/authenticate/open path. Stop after the
  # first member rather than constructing a generated complete source corpus.
  with tempfile.TemporaryDirectory(dir=HERE) as d:
   root=Path(d);paths={};pins={};seen=[]
   for lab in native.PINS:
    paths[lab]=root/(lab+'.zip')
    pins[lab]=write_zip(paths[lab],[('generated.csv',b'original')])
   replacement=root/'replacement.zip'
   write_zip(replacement,[('generated.csv',b'replaced')])
   bundle_class=native.Bundle
   def replacing_bundle(destination,key):
    bundle=bundle_class(destination,key)
    replacement.replace(paths['manor'])
    return bundle
   def stop_after_member(body,lab):
    seen.append((lab,body))
    raise native.SourceError('generated stop after member read')
   with mock.patch.object(native,'PINS',pins),mock.patch.object(native,'Bundle',side_effect=replacing_bundle),mock.patch.object(native,'parse_wave_csv',side_effect=stop_after_member):
    with self.assertRaisesRegex(native.SourceError,'generated stop'):
     native.prepare(paths,root/'bundle',b'g'*32)
   self.assertEqual(seen,[('manor',b'original')])
   self.assertFalse((root/'bundle/COMPLETE.json').exists())

 def test_retained_source_mutation_is_refused_before_completion(self):
  with tempfile.TemporaryDirectory(dir=HERE) as d:
   root=Path(d);paths={};pins={}
   for lab in native.PINS:
    paths[lab]=root/(lab+'.zip')
    pins[lab]=write_zip(paths[lab],[('generated.csv',b'original')])
   with mock.patch.object(native,'PINS',pins):
    with native.verified_sources(paths) as sources:
     native.check_sources(sources)
     with paths['manor'].open('ab') as stream:stream.write(b'changed')
     with self.assertRaisesRegex(native.SourceError,'source changed during preparation: manor'):
      native.check_sources(sources)
    self.assertTrue(all(stream.closed for stream,_ in sources.values()))

 def test_complete_generated_archive_roundtrip_and_private_projection(self):
  with tempfile.TemporaryDirectory(dir=HERE) as d:
   root=Path(d);paths,pins=generated_sources(root)
   with mock.patch.object(native,'PINS',pins):result=native.prepare(paths,root/'bundle',b'g'*32)
   self.assertFalse(result['candidate_delivery_admitted'])
   self.assertEqual(result['target_cases'],936)
   self.assertEqual(result['target_animals'],104)
   self.assertEqual(result['manifest']['target_trace_count'],937)
   self.assertTrue((root/'bundle/COMPLETE.json').is_file())
   support=load_jsonl(root/'bundle/observations/support/liberman/index.jsonl.gz')
   self.assertEqual(len(support),3)
   self.assertTrue(all(row['axis']['kind']=='sample_index' and row['axis']['sample_period_ms'] is None for row in support))
   self.assertTrue(all('step_ms' not in row['axis'] and row['axis']['header_sample_period_ms']==0.04 for row in support))
   self.assertTrue(any('stored-row continuity' in hold for hold in result['manifest']['holds']))
   cases=load_jsonl(root/'bundle/observations/target/cases.jsonl.gz')
   self.assertEqual(len(cases),936)
   repeated=[x for x in cases if x['repeated_levels_preserved']]
   self.assertEqual(len(repeated),1);self.assertEqual(len(repeated[0]['trace_ids']),2)
   index=load_jsonl(root/'bundle/observations/target/index.jsonl.gz')
   self.assertEqual(index[0]['sample_offset'],0)
   self.assertEqual(index[1]['sample_offset'],1953)
   with gzip.open(root/'bundle/observations/target/waveforms.f64le.gz','rb') as stream:
    first=struct.unpack('<1953d',stream.read(1953*8))
    remaining=stream.read()
   self.assertEqual(first[0:2],(1.25,-2.5));self.assertEqual(first[-1],3.75)
   self.assertEqual(len(remaining),(937-1)*1953*8)
   self.assertEqual(index[-1]['sample_offset']+index[-1]['sample_count'],937*1953)
   self.assertTrue(all(not {'animal_source_id','animal_id','genetic_background','metadata','member','threshold_raw','annotation'}.intersection(row) for row in index+cases))
   private=load_jsonl(root/'bundle/private/annotation-projection.jsonl.gz')
   self.assertEqual(len(private),936)
   self.assertEqual(sum(x['animal_source_id']<=54 for x in private),54*9)
   self.assertTrue(all(x['score_admission'] is False for x in private))
   target100=[x for x in private if x['annotation']['source_numeric_value']==100]
   self.assertEqual(len(target100),1);self.assertTrue(target100[0]['outside_observed_levels'])
   self.assertEqual(target100[0]['annotation']['semantics'],'unresolved_exact_or_censored')
   self.assertNotEqual(cases[0]['case_id'],'1')

 def test_missing_observed_case_cannot_be_filled_from_threshold_table(self):
  with tempfile.TemporaryDirectory(dir=HERE) as d:
   root=Path(d);paths,pins=generated_sources(root,missing_case=True)
   with mock.patch.object(native,'PINS',pins),self.assertRaisesRegex(native.SourceError,'observation/threshold.*join differs'):
    native.prepare(paths,root/'bundle',b'g'*32)
   self.assertTrue((root/'bundle').is_dir())
   self.assertFalse((root/'bundle/COMPLETE.json').exists())

 def test_annotation_file_count_cannot_replace_complete_animal_join(self):
  with tempfile.TemporaryDirectory(dir=HERE) as d:
   root=Path(d);paths,pins=generated_sources(root,duplicate_wave1=True)
   with mock.patch.object(native,'PINS',pins),self.assertRaisesRegex(native.SourceError,'duplicate or out-of-roster wave1'):
    native.prepare(paths,root/'bundle',b'g'*32)
   self.assertFalse((root/'bundle/COMPLETE.json').exists())


if __name__=='__main__':unittest.main(verbosity=2)
